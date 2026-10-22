'''
Description:  
   Carrier system using vectorization
@Date       : 2025/11/11
@Author     : Dai Zhong, Chenxi Fu
@version    : 1.0
'''

import math
import logging
import time
import random

import numpy as np

from .model import Material
from .vector import Vector
from raser.core.field.simple import AnalyticStripPixelField

tolerance_default = 1e-6

min_intensity = 1 # V/cm

logger = logging.getLogger(__name__)
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger.setLevel(logging.INFO)

class VectorizedCarrierSystem:
    """完全自包含的向量化载流子系统 - 替代CarrierCluster"""
    
    def __init__(self, all_positions, all_charges, all_times, all_signals, material, carrier_type="electron", 
                read_out_contact=None, my_d=None, keep_drift_paths=True):
        # 输入数据验证
        self._validate_inputs(all_positions, all_charges, all_times)
            
        # 初始化数组
        self.positions = np.array(all_positions, dtype=np.float64)
        self.charges = np.array(all_charges, dtype=np.float64)
        self.times = np.array(all_times, dtype=np.int32)
        self.active = np.ones(len(all_charges), dtype=bool)
        self.end_conditions = np.zeros(len(all_charges), dtype=np.int8)
        self.steps_drifted = np.zeros(len(all_charges), dtype=np.int32)
        self.carrier_type = carrier_type
        self.read_out_contact = read_out_contact
        self.my_d = my_d
        self.keep_drift_paths = bool(keep_drift_paths)


        self.device_dict = {}
        self._trap_rng = None
        self.last_trapping_statistics = {}
        self.trapping_statistics_total = {
            "initial_particle_count": 0,
            "capture_count": 0,
            "release_count": 0,
            "lifetime_loss_count": 0,
            "final_mobile_count": 0,
            "final_trapped_count": 0,
            "final_dead_count": 0,
        }
        
        
        # Material 对象
        self.material = self._create_material(material)
        
        # 初始化
        self._params = self._initialize_params(my_d)
        self._initialize_other_attributes(all_positions)
        self._boundary_log_count = 0
        
        # 物理常数
        self.kboltz = 8.617385e-5
        self.e0 = 1.60217733e-19
        self.mobility = Material(my_d.material).cal_mobility
        self._mobility_cache = {}

        # 性能统计
        self.performance_stats = {
            'total_steps': 0,
            'field_calculations': 0,
            'boundary_checks': 0,
            'carriers_terminated': 0,
            'low_field_terminations': 0,
            'boundary_terminations': 0,
            'collection_terminations': 0
        }
        
        # 信号存储
        self.signals = self._initialize_signal_storage_per_carrier(len(all_charges), read_out_contact)
        self._signal_warning_logged = False
        
        logger.info(f"向量化系统初始化: {len(all_charges)}个{carrier_type}")
        logger.info(f"探测器尺寸: {my_d.l_x:.1f} × {my_d.l_y:.1f} × {my_d.l_z:.1f} um")

    @staticmethod
    def _scalar_float(value, name):
        array_value = np.asarray(value)
        if array_value.size != 1:
            raise ValueError(f"{name} must be scalar, got shape {array_value.shape}")
        return float(array_value.reshape(-1)[0])

    def _initialize_params(self, my_d):
        params = {}
        try:
            if my_d is not None:
                params['temperature'] = self._get_param(my_d, 'temperature', 300.0)
                params['field_resolution'] = self._resolve_field_resolution(my_d)
                params['boundary_tolerance'] = self._resolve_boundary_tolerance(my_d)
                params['max_drift_time'] = 100e-9   # 增加最大漂移时间
                params['min_field_strength'] = self._resolve_min_field_strength(my_d)
                params['max_vector_steps'] = self._get_param(my_d, 'vector_max_steps', 200000, param_type=int)
                params["collection_weighting_epsilon"] = (
                    self._resolve_collection_weighting_epsilon(my_d)
                )
                params["enable_trapping"] = bool(my_d.device_dict.get("enable_trapping",False,))

                if self.carrier_type == "electron":
                    lifetime_key = "electron_lifetime"
                else:
                    lifetime_key = "hole_lifetime"

                params["carrier_lifetime"] = float(my_d.device_dict.get(lifetime_key,float("inf"),))
                logger.info("探测器参数提取成功")
                
        except Exception as e:
            logger.error(f"探测器参数提取失败: {e}")
            raise e
            
        return params
    
    def _get_param(self, my_d, param_name, default, param_type=float):
        """安全获取参数"""
        try:
            value = getattr(my_d, param_name, default)
            return param_type(value)
        except (TypeError, ValueError) as e:
            logger.warning(f"参数 {param_name} 转换失败，使用默认值 {default}: {e}")
            return default

    def _initialize_other_attributes(self, all_positions):
        """初始化其他属性 - 增强版本"""
        # 初始化 reduced_positions
        self.reduced_positions = np.zeros((len(all_positions), 2), dtype=np.float64)
        
        # 初始化路径存储
        self.paths = [[] for _ in range(len(all_positions))] if self.keep_drift_paths else []
        self.paths_reduced = [[] for _ in range(len(all_positions))]
        
        # 初始化每个载流子的路径
        for i, pos in enumerate(all_positions):
            x, y, z = pos
            t = self.times[i]
            
            # 完整路径
            if self.keep_drift_paths:
                self.paths[i].append([x, y, z, t])
            
            # 简化坐标路径
            x_reduced, y_reduced = self._calculate_reduced_coords(x, y, self.my_d)
            x_num, y_num = self._calculate_electrode_numbers(x, y, self.my_d)
            self.paths_reduced[i].append([x_reduced, y_reduced, z, t, x_num, y_num])
            
            # 存储简化坐标
            self.reduced_positions[i] = [x_reduced, y_reduced]
    
    def _initialize_signal_storage_per_carrier(self, n_carriers, read_out_contact):
        """为每个载流子初始化信号存储结构"""
        if read_out_contact and len(read_out_contact) == 1:
            try:
                x_span = read_out_contact[0].get('x_span', 0)
                y_span = read_out_contact[0].get('y_span', 0)
                # 每个载流子有 (2*x_span+1)*(2*y_span+1) 个电极信号
                n_electrodes = (2 * x_span + 1) * (2 * y_span + 1)
                # 返回一个列表，每个元素是一个载流子的所有电极信号（空列表）
                return [[] for _ in range(n_carriers)]
            except:
                # 默认每个载流子有1个电极信号
                return [[] for _ in range(n_carriers)]
        else:
            # 多电极情况，每个载流子有 len(read_out_contact) 个电极信号
            n_electrodes = len(read_out_contact) if read_out_contact else 1
            return [[] for _ in range(n_carriers)]

    def _initialize_signal_storage(self, read_out_contact):
        """初始化信号存储结构"""
        if read_out_contact and len(read_out_contact) == 1:
            try:
                x_span = read_out_contact[0].get('x_span', 0)
                y_span = read_out_contact[0].get('y_span', 0)
                signal_length = max(1, (2*x_span+1)*(2*y_span+1))
                return [[] for _ in range(signal_length)]
            except:
                return [[]]
        else:
            return [[] for _ in range(len(read_out_contact) if read_out_contact else 1)]
    
    def _validate_inputs(self, positions, charges, times):
        """输入数据验证"""
        if len(positions) == 0:
            raise ValueError("载流子位置列表不能为空")
        if len(positions) != len(charges) or len(positions) != len(times):
            raise ValueError("位置、电荷和时间数组长度不一致")
        
        # 检查位置数据有效性
        for i, pos in enumerate(positions):
            if len(pos) != 3:
                raise ValueError(f"位置数据 {i} 格式错误，应为 [x, y, z]")
            x, y, z = pos
            if math.isnan(x) or math.isnan(y) or math.isnan(z):
                raise ValueError(f"位置数据 {i} 包含 NaN 值")
    
    def _create_material(self, material):
        """安全的 Material 对象创建"""
        try:
            return Material(material)
        except Exception as e:
            logger.warning(f"Material对象创建失败 {material}，使用默认硅材料: {e}")
            try:
                return Material("si")
            except:
                # 最终备用方案
                class FallbackMaterial:
                    def __init__(self):
                        self.name = "fallback_si"
                return FallbackMaterial()

    def _resolve_field_resolution(self, my_d):
        """获取用于缓存和容差的电场分辨率"""
        resolution = getattr(my_d, "vector_field_resolution", None)
        if resolution is None:
            resolution = getattr(my_d, "field_resolution", None)
        try:
            resolution = float(resolution)
        except (TypeError, ValueError):
            resolution = None
        if resolution is None or resolution <= 0:
            resolution = tolerance_default
        my_d.resolution = resolution

    def _resolve_boundary_tolerance(self, my_d):
        """根据探测器和网格分辨率决定边界容差"""
        custom_tol = getattr(my_d, "vector_boundary_tolerance", None)
        try:
            if custom_tol is not None:
                custom_tol = float(custom_tol)
        except (TypeError, ValueError):
            custom_tol = None
        if custom_tol is not None and custom_tol > 0:
            logger.info("使用用户配置的边界容差: %.2f um", custom_tol)
            return custom_tol

        field_res = my_d.resolution
        tolerance = max(tolerance_default, field_res)
        logger.info(
            "自动计算边界容差: %.2f um (field_res=%.2f)",
            tolerance, field_res
        )
        return tolerance

    def _resolve_min_field_strength(self, my_d):
        """获取载流子终止的最小电场强度阈值"""
        custom_min_field = getattr(my_d, "vector_min_field_strength", None)
        try:
            if custom_min_field is not None:
                custom_min_field = float(custom_min_field)
        except (TypeError, ValueError):
            logger.warning(
                "参数 vector_min_field_strength 转换失败，使用默认值 1.0 V/cm: %s",
                custom_min_field
            )
            custom_min_field = None
        if custom_min_field is not None and custom_min_field > 0:
            logger.info("使用用户配置的最小电场强度: %.2f V/cm", custom_min_field)
            return custom_min_field
        return 1.0

    def _resolve_collection_weighting_epsilon(self, my_d):
        value = getattr(my_d, "vector_collection_weighting_epsilon", None)
        if value is None and hasattr(my_d, "device_dict"):
            value = my_d.device_dict.get("vector_collection_weighting_epsilon")
        if value is None:
            return 5e-3
        value = float(value)
        if not 0 < value < 0.5:
            raise ValueError(
                "vector_collection_weighting_epsilon must be between 0 and 0.5"
            )
        return value
    
    def _calculate_reduced_coords(self, x, y, my_d):
        """计算简化坐标"""
        #use_reduced = (self.read_out_contact and 
                      #len(self.read_out_contact) == 1)
        use_reduced = False  # 先不使用简化坐标，直接用全局坐标进行电场计算和边界检查

        if not use_reduced:
            return x, y
        
        try:
            my_d.field_shift_x = float(my_d.field_shift_x)
        except:
            my_d.field_shift_x = 0.0

        try:
            my_d.field_shift_y = float(my_d.field_shift_y)
        except:
            my_d.field_shift_y = 0.0
        
        x_reduced = (x - my_d.l_x/2 + (my_d.x_ele_num%2)*my_d.p_x/2.0) % my_d.p_x + my_d.field_shift_x
        y_reduced = (y - my_d.l_y/2 + (my_d.y_ele_num%2)*my_d.p_y/2.0) % my_d.p_y + my_d.field_shift_y
        
        return x_reduced, y_reduced

    def _should_terminate_at_contact(self, my_f, x_reduced, y_reduced, z):
        if not self.read_out_contact or len(self.read_out_contact) != 1:
            return False
        potential = my_f.get_w_p_cached(x_reduced, y_reduced, z, 0)
        if potential is None:
            raise RuntimeError("Weighting potential is required for contact collection")
        return potential >= 1.0 - self._params["collection_weighting_epsilon"]
    
    def _calculate_electrode_numbers(self, x, y, my_d):
        """计算电极编号"""
        try:
            x_num = int((x - my_d.l_x/2 + (my_d.x_ele_num%2)*my_d.p_x/2.0) // my_d.p_x + my_d.x_ele_num/2)
            y_num = int((y - my_d.l_y/2 + (my_d.y_ele_num%2)*my_d.p_y/2.0) // my_d.p_y + my_d.y_ele_num/2)
            return x_num, y_num
        except Exception as e:
            logger.warning(f"电极编号计算失败，使用默认值: {e}")
            # 返回中心电极
            return my_d.x_ele_num//2, my_d.y_ele_num//2

    def _check_boundary_conditions(self, x, y, z, my_d):
        """边界条件检查 - 大型器件优化"""
        l_x, l_y, l_z = my_d.l_x, my_d.l_y, my_d.l_z
        tolerance = self._params['boundary_tolerance']
        
        # 使用容差检查边界
        out_of_bound = (x <= -tolerance or x >= l_x + tolerance or 
                       y <= -tolerance or y >= l_y + tolerance or 
                       z <= -tolerance or z >= l_z + tolerance)

        if out_of_bound and self._boundary_log_count < 10:
            self._boundary_log_count += 1
            logger.info(
                "%s 越界终止 #%d: (x=%.3f, y=%.3f, z=%.3f) um, 容差=%.2f, 盒界=(%.2f, %.2f, %.2f)",
                self.carrier_type, self._boundary_log_count, x, y, z,
                tolerance, l_x, l_y, l_z
            )
        
        return out_of_bound

    def drift_batch(self, my_d, my_f, delta_t=1e-12, max_steps=None):
        """批量漂移主函数 - 大型器件优化"""
        params = self._params
        max_drift_time = params.get('max_drift_time', 0.0)
        if self.performance_stats['total_steps'] == 0:
            logger.debug(
                "漂移参数: boundary_tolerance=%.2f um, field_resolution=%.2f um",
                params.get('boundary_tolerance', -1.0),
                params.get('field_resolution', -1.0)
            )

        if delta_t <= 0:
            raise ValueError("delta_t must be positive for drift simulation")

        target_steps = int(math.ceil(max_drift_time / delta_t)) if max_drift_time > 0 else 0
        planned_steps = max(target_steps, 1)
        if max_steps is not None and max_steps > 0:
            planned_steps = max(planned_steps, int(max_steps))

        max_vector_steps = int(params.get('max_vector_steps', 200000))
        if planned_steps > max_vector_steps:
            logger.debug(
                "调整向量化漂移步数: 请求=%s, 限制=%s (max_vector_steps)",
                planned_steps, max_vector_steps
            )
            planned_steps = max_vector_steps

        logger.info(
            f"开始批量漂移{self.carrier_type}，时间步长{delta_t}s，计划步数{planned_steps} "
            f"(max_drift_time={max_drift_time:.2e}s)"
        )
        
        start_time = time.time()
        
        total_carriers = len(self.active)
        initial_active = np.sum(self.active)
        
        logger.info(f"初始状态: {initial_active}/{total_carriers} 个活跃载流子")
        
        active_indices = np.arange(total_carriers)

        for step in range(planned_steps):
            if step % 100 == 0:
                self._log_progress_drift(step, total_carriers)
            
            n_terminated = self.drift_step_batch(my_d, my_f, delta_t, step, active_indices)
            self.performance_stats['total_steps'] += 1
            active_indices = active_indices[self.active[active_indices]]
            
            if len(active_indices) == 0:
                logger.info("所有载流子停止漂移")
                break
        else:
            remaining = int(np.sum(self.active))
            if remaining > 0:
                logger.warning(
                    "向量化漂移达到最大步数仍有 %s 个载流子未终止，可适当增加 max_drift_time 或 max_vector_steps",
                    remaining
                )
        executed_steps = min(self.performance_stats['total_steps'], planned_steps)
        
        self._log_final_stats(start_time, executed_steps)
        return True

    def drift_step_batch(self, my_d, my_f, delta_t, step=0, active_indices=None):
        """批量单步漂移 - 核心算法"""
        if active_indices is None:
            active_indices = np.flatnonzero(self.active)
        if len(active_indices) == 0:
            return 0
            
        n_terminated = 0
        params = self._params
        
        for idx in active_indices:
            x, y, z = self.positions[idx]
            x_reduced, y_reduced = self.reduced_positions[idx]
            charge = self.charges[idx]
            
            # 边界检查
            self.performance_stats['boundary_checks'] += 1
            if self._check_boundary_conditions(x, y, z, my_d):
                self.active[idx] = False
                self.end_conditions[idx] = 1
                n_terminated += 1
                self.performance_stats['boundary_terminations'] += 1
                continue
            
            # 时间检查
            #if self.times[idx] > params['max_drift_time']:
            if self.steps_drifted[idx] >= params['max_vector_steps']:
                self.active[idx] = False
                self.end_conditions[idx] = 4
                n_terminated += 1
                continue
            
            # 电场获取和处理
            e_field = self._get_e_field_reduced(my_f, x, y, z, idx, x_reduced, y_reduced)
            if e_field is None:
                continue
                
            Ex, Ey, Ez = e_field
            intensity = math.sqrt(Ex*Ex + Ey*Ey + Ez*Ez)
            
            # 电场强度检查（降低阈值）
            if intensity <= params['min_field_strength']:
                self.active[idx] = False
                self.end_conditions[idx] = 3
                n_terminated += 1
                self.performance_stats['low_field_terminations'] += 1
                continue
            
            # 迁移率计算
            try:
                doping = self._scalar_float(
                    my_f.get_doping_cached(x_reduced, y_reduced, z),
                    "doping",
                )
                intensity = self._scalar_float(intensity, "electric field intensity")
                mobility_key = (params['temperature'], doping, bool(charge > 0), intensity)
                if mobility_key in self._mobility_cache:
                    mu = self._mobility_cache[mobility_key]
                else:
                    mu = self.mobility(params['temperature'], doping, charge, intensity)
                    self._mobility_cache[mobility_key] = mu
                diffusion_constant = math.sqrt(2.0 * self.kboltz * params['temperature'] * mu * delta_t) * 1e4
            except Exception as e:
                raise RuntimeError(f"迁移率计算失败: {e}")
            
            # 速度和位移计算
            delta_x, delta_y, delta_z = self._calculate_displacement(charge, e_field, mu, delta_t)
            
            # 扩散位移
            dif_x, dif_y, dif_z = self._calculate_diffusion(diffusion_constant)
            
            # 更新位置
            self._update_carrier_position(idx, delta_x, delta_y, delta_z, dif_x, dif_y, dif_z)

            new_x_reduced, new_y_reduced = self.reduced_positions[idx]
            new_z = self.positions[idx][2]
            if self._check_boundary_conditions(
                self.positions[idx][0], self.positions[idx][1], new_z, my_d
            ):
                self._clamp_position_to_device(idx, my_d)
                new_x_reduced, new_y_reduced = self.reduced_positions[idx]
                new_z = self.positions[idx][2]
                if self._should_terminate_at_contact(
                    my_f, new_x_reduced, new_y_reduced, new_z
                ):
                    self.end_conditions[idx] = 5
                    self.performance_stats["collection_terminations"] += 1
                else:
                    self.end_conditions[idx] = 1
                    self.performance_stats["boundary_terminations"] += 1
                self.active[idx] = False
                n_terminated += 1
                continue
            if self._should_terminate_at_contact(
                my_f, new_x_reduced, new_y_reduced, new_z
            ):
                self.active[idx] = False
                self.end_conditions[idx] = 5
                self.performance_stats["collection_terminations"] += 1
                n_terminated += 1
        
        self.performance_stats['carriers_terminated'] += n_terminated
        return n_terminated

    def _clamp_position_to_device(self, idx, my_d):
        x, y, z = self.positions[idx]
        x = min(max(x, 0.0), my_d.l_x)
        y = min(max(y, 0.0), my_d.l_y)
        z = min(max(z, 0.0), my_d.l_z)
        self.positions[idx] = [x, y, z]
        self.reduced_positions[idx] = self._calculate_reduced_coords(x, y, my_d)
        if self.keep_drift_paths:
            self.paths[idx][-1] = [x, y, z, self.times[idx]]
        x_num, y_num = self._calculate_electrode_numbers(x, y, my_d)
        self.paths_reduced[idx][-1] = [
            self.reduced_positions[idx][0],
            self.reduced_positions[idx][1],
            z,
            self.times[idx],
            x_num,
            y_num,
        ]

    def _get_e_field_reduced(self, my_f, x, y, z, idx, field_x=None, field_y=None):
        """安全的电场获取"""
        fx = x if field_x is None else field_x
        fy = y if field_y is None else field_y
        try:
            self.performance_stats['field_calculations'] += 1
            e_field = my_f.get_e_field_cached(fx, fy, z)
            if e_field is None or len(e_field) != 3:
                raise ValueError("无效的电场值")
            e_field_array = np.asarray(e_field, dtype=np.float64)

            if not np.all(np.isfinite(e_field_array)):
                logger.warning(
                    "载流子 %d 电场包含 NaN/Inf，终止该载流子: "
                    "(x=%.3f, y=%.3f, z=%.3f), E=%s",
                    idx,
                    x,
                    y,
                    z,
                    e_field,
                )
                self.active[idx] = False
                self.end_conditions[idx] = 2
                return None

            return tuple(e_field_array)                
            #return e_field
        except Exception as e:
            logger.warning(f"载流子 {idx} 电场获取失败: {e}")
            self.active[idx] = False
            self.end_conditions[idx] = 2
            return None

    def _calculate_displacement(self, charge, e_field, mu, delta_t):
        """计算位移"""
        Ex, Ey, Ez = e_field
        if charge > 0:  # 空穴
            vx = Ex * mu
            vy = Ey * mu
            vz = Ez * mu
        else:  # 电子
            vx = -Ex * mu
            vy = -Ey * mu
            vz = -Ez * mu
        
        return vx * delta_t * 1e4, vy * delta_t * 1e4, vz * delta_t * 1e4

    def _calculate_diffusion(self, diffusion_constant):
        """计算扩散位移"""
        try:
            return (random.gauss(0.0, diffusion_constant),
                   random.gauss(0.0, diffusion_constant), 
                   random.gauss(0.0, diffusion_constant))
        except:
            return 0.0, 0.0, 0.0

    def _update_carrier_position(self, idx, delta_x, delta_y, delta_z, dif_x, dif_y, dif_z):
        """更新载流子位置"""
        x, y, z = self.positions[idx]
        
        new_x = x + delta_x + dif_x
        new_y = y + delta_y + dif_y
        new_z = z + delta_z + dif_z
        
        # 更新坐标
        self.positions[idx] = [new_x, new_y, new_z]
        self.reduced_positions[idx] = self._calculate_reduced_coords(new_x, new_y, self.my_d)
        self.times[idx] += 1
        self.steps_drifted[idx] += 1
        
        # 更新路径
        if self.keep_drift_paths:
            self.paths[idx].append([new_x, new_y, new_z, self.times[idx]])
        x_num, y_num = self._calculate_electrode_numbers(new_x, new_y, self.my_d)
        self.paths_reduced[idx].append([
            self.reduced_positions[idx][0], self.reduced_positions[idx][1], 
            new_z, self.times[idx], x_num, y_num
        ])

    def _log_progress_drift(self, step, total_carriers):
        """记录进度"""
        active_count = np.sum(self.active)
        progress = (total_carriers - active_count) / total_carriers * 100
        logger.info(f"  步骤 {step}: {active_count}个活跃载流子 ({progress:.1f}%完成)")

    def _log_final_stats(self, start_time, max_steps):
        """记录最终统计"""
        end_time = time.time()
        total_time = end_time - start_time
        final_stats = self.get_statistics()
        perf_stats = self.get_performance_stats()
        
        logger.info(f"批量漂移完成: 共{self.performance_stats['total_steps']}步，耗时{total_time:.2f}秒")
        logger.info(f"最终状态: {final_stats['active_carriers']}个活跃，平均步数{final_stats['average_steps']:.1f}")
        logger.info(f"性能统计: {perf_stats}")

    def get_statistics(self):
        """获取统计信息"""
        n_total = len(self.active)
        n_active = np.sum(self.active)
        
        if np.any(self.steps_drifted > 0):
            avg_steps = np.mean(self.steps_drifted[self.steps_drifted > 0])
            max_steps = np.max(self.steps_drifted)
        else:
            avg_steps = 0
            max_steps = 0
            
        # 终止原因统计
        end_condition_counts = {
            'boundary': np.sum(self.end_conditions == 1),
            'field_error': np.sum(self.end_conditions == 2),
            'low_field': np.sum(self.end_conditions == 3),
            'timeout': np.sum(self.end_conditions == 4),
            'collection': np.sum(self.end_conditions == 5),
            'active': n_active
        }
        
        return {
            'total_carriers': n_total,
            'active_carriers': n_active,
            'inactive_carriers': n_total - n_active,
            'average_steps': avg_steps,
            'max_steps': max_steps,
            'carrier_type': self.carrier_type,
            'end_conditions': end_condition_counts
        }
    
    def get_performance_stats(self):
        """获取性能统计"""
        return self.performance_stats.copy()
    
    def _reinitialize_signal_list(self, carrier):
        """重新初始化信号列表"""
        try:
            if hasattr(carrier, 'read_out_contact') and carrier.read_out_contact:
                if len(carrier.read_out_contact) == 1:
                    x_span = carrier.read_out_contact[0].get('x_span', 0)
                    y_span = carrier.read_out_contact[0].get('y_span', 0)
                    signal_length = max(1, (2*x_span+1)*(2*y_span+1))
                    carrier.signal = [[] for _ in range(signal_length)]
                else:
                    carrier.signal = [[] for _ in range(len(carrier.read_out_contact))]
            else:
                carrier.signal = [[]]
        except Exception as e:
            carrier.signal = [[]]
    def get_signal_batch(self, my_d, my_f, delta_t=1e-12):
        """批量计算载流子信号 - 重新设计版本"""

        # 保存设备配置，供俘获模型读取
        self.device_dict = getattr(
            my_d,
            "device_dict",
            {},
        )

        if not isinstance(self.device_dict, dict):
            self.device_dict = {}



        self._trap_scale_logged = False

        

        trapping_cfg = self.device_dict.get(
            "trapping_model",
            {},
        )

        if not isinstance(trapping_cfg, dict):
            trapping_cfg = {}

        # 每次信号计算重新累计统计结果
        self.trapping_statistics_total = {
            "initial_particle_count": 0,
            "capture_count": 0,
            "release_count": 0,
            "lifetime_loss_count": 0,
            "final_mobile_count": 0,
            "final_trapped_count": 0,
            "final_dead_count": 0,
        }

        logger.info(
            "[TrapConfig] enabled=%s, mode=%s, "
            "electron_lifetime=%s, hole_lifetime=%s, "
            "electron_release_time=%s, hole_release_time=%s",
            trapping_cfg.get("enabled", False),
            trapping_cfg.get("mode", "deterministic"),
            self.device_dict.get("electron_lifetime"),
            self.device_dict.get("hole_lifetime"),
            trapping_cfg.get("electron_release_time"),
            trapping_cfg.get("hole_release_time"),
        )




        start_time = time.time()
        e0 = 1.60217733e-19

        # Field 中是否启用 Diamond3Level 等显式辐照缺陷
        field_traps_enabled = (
            getattr(my_d, "irradiation_model", None) is not None
        )

        # CCE 中是否启用有限载流子寿命
        lifetime_decay_enabled = bool(
            my_d.device_dict.get("enable_trapping", False)
        )

        # 只要显式陷阱或有限寿命任一启用，
        # 就需要计算输运过程中的有效电荷
        has_irradiation = (
            field_traps_enabled or lifetime_decay_enabled
        )

        logger.info("=== 信号计算调试信息 ===")
        logger.info("载流子类型: %s", self.carrier_type)
        logger.info("总载流子数: %s", len(self.positions))
        logger.info("活跃载流子数: %s", np.sum(self.active))
        logger.info("读取电极配置: %s", self.read_out_contact)
        logger.info("Field辐照缺陷模型: %s", field_traps_enabled)
        logger.info("CCE有限寿命衰减: %s", lifetime_decay_enabled)
        logger.info("是否计算载流子电荷衰减: %s", has_irradiation)
    # def get_signal_batch(self, my_d, my_f, delta_t=1e-12):
    #     """批量计算载流子信号 - 重新设计版本"""
    #     start_time = time.time()
    #     e0 = 1.60217733e-19
    #     # has_irradiation = my_d.irradiation_model is not None
    #     has_irradiation = (
    #                     bool(
    #                         my_d.device_dict.get(
    #                             "enable_trapping",
    #                             False,
    #                         )
    #                     )
    #                     or my_d.irradiation_model is not None
    #                 )
    #     # 调试信息
    #     logger.info(f"=== 信号计算调试信息 ===")
    #     logger.info(f"载流子类型: {self.carrier_type}")
    #     logger.info(f"总载流子数: {len(self.positions)}")
    #     logger.info(f"活跃载流子数: {np.sum(self.active)}")
    #     logger.info(f"读取电极配置: {self.read_out_contact}")
    #     logger.info(f"是否有辐射损伤: {has_irradiation}")
        
        # 检查路径数据
        valid_paths = 0
        for i, path in enumerate(self.paths_reduced):
            if len(path) > 1:
                valid_paths += 1
        
        logger.info(f"有效路径数: {valid_paths}/{len(self.paths_reduced)}")
        
        if valid_paths == 0:
            logger.warning("没有有效的路径数据，无法计算信号！")
            return
        
        # 处理所有载流子
        all_indices = np.arange(len(self.positions))
        
        if len(self.read_out_contact) == 1:
            self._calculate_signal_single_contact(all_indices, my_f, e0, delta_t, has_irradiation, my_d)
        else:
            self._calculate_signal_multi_contact(all_indices, my_f, e0, delta_t, has_irradiation, my_d)
        
        # 统计信号计算结果
        total_carriers_with_signals = sum(1 for carrier_signals in self.signals if carrier_signals)
        total_signal_points = self._count_signal_points(self.signals)
        
        logger.info(f"信号计算完成: {total_carriers_with_signals}个载流子有信号, 总信号点数={total_signal_points}")
        
        if total_signal_points == 0:
            logger.warning("警告: 信号计算结果为0！")
        
        end_time = time.time()
        logger.info(f"批量信号计算完成: 耗时{end_time - start_time:.2f}秒")


        stats = getattr(
            self,
            "last_trapping_statistics",
            None,
        )

        if stats is not None:
            logger.info(
                "%s trapping statistics: %s",
                self.carrier_type,
                stats,
            )

    def _count_signal_points(self, values):
        if isinstance(values, (list, tuple)):
            return sum(self._count_signal_points(value) for value in values)
        return 1

    def _calculate_signal_single_contact(self, all_indices, my_f, e0, delta_t, has_irradiation, my_d):
        """单电极情况下的信号计算"""
        x_span = self.read_out_contact[0]['x_span']
        y_span = self.read_out_contact[0]['y_span']
        p_x = my_d.p_x
        p_y = my_d.p_y
        
        total_electrodes = (2 * x_span + 1) * (2 * y_span + 1)
        logger.info(f"单电极配置: x_span={x_span}, y_span={y_span}, 总电极数={total_electrodes}")
        
        # 处理所有载流子
        processed_count = 0
        for carrier_idx in all_indices:
            if self._process_carrier_signal_single(carrier_idx, my_f, e0, delta_t, has_irradiation, 
                                                x_span, y_span, p_x, p_y, total_electrodes):
                processed_count += 1

            if carrier_idx % 10 == 0:
                self._log_progress_signal(carrier_idx, len(all_indices))
        
        # 统计信号数据
        total_carriers_with_signals = sum(1 for carrier_signals in self.signals if carrier_signals)
        logger.info(f"单电极信号计算完成: 处理了{processed_count}个载流子, {total_carriers_with_signals}个载流子有信号")

    def _process_carrier_signal_single(self, carrier_idx, my_f, e0, delta_t, has_irradiation, 
                                    x_span, y_span, p_x, p_y, total_electrodes):
        """处理单个载流子在单电极配置下的信号 - 修复存储结构"""
        charge = self.charges[carrier_idx]
        path_reduced = self.paths_reduced[carrier_idx]
        
        # 检查是否有有效的路径数据
        if len(path_reduced) <= 1:
            return False
        
        try:
            n_points = len(path_reduced) - 1
            
            # 为这个载流子初始化电极信号存储
            carrier_electrode_signals = [[] for _ in range(total_electrodes)]
            
            # 提取坐标和时间
            x_coords = [point[0] for point in path_reduced[:-1]]
            y_coords = [point[1] for point in path_reduced[:-1]]  
            z_coords = [point[2] for point in path_reduced[:-1]]

            delta_n_x = [path_reduced[i+1][4] - path_reduced[i][4] for i in range(len(path_reduced)-1)]
            delta_n_y = [path_reduced[i+1][5] - path_reduced[i][5] for i in range(len(path_reduced)-1)]
            
            # 计算时间差
            d_times = [path_reduced[i+1][3] - path_reduced[i][3] for i in range(len(path_reduced)-1)]
            
            # 处理所有电极偏移
            success_count = 0
            use_local_analytic = isinstance(my_f, AnalyticStripPixelField)
            x_coords_end = [point[0] for point in path_reduced[1:]]
            y_coords_end = [point[1] for point in path_reduced[1:]]
            z_coords_end = [point[2] for point in path_reduced[1:]]
            
            for j in range(2 * x_span + 1):
                x_shift = (j - x_span) * p_x
                for k in range(2 * y_span + 1):
                    y_shift = (k - y_span) * p_y
                    electrode_idx = j * (2 * y_span + 1) + k
                    if use_local_analytic:
                        start_x = [x - x_shift for x in x_coords]
                        start_y = [y - y_shift for y in y_coords]
                        end_x = [x - x_shift for x in x_coords_end]
                        end_y = [y - y_shift for y in y_coords_end]
                    else:
                        start_x = [
                            x - x_shift + dn_x * p_x
                            for x, dn_x in zip(x_coords, delta_n_x)
                        ]
                        start_y = [
                            y - y_shift + dn_y * p_y
                            for y, dn_y in zip(y_coords, delta_n_y)
                        ]
                        end_x = [
                            x - x_shift + dn_x * p_x
                            for x, dn_x in zip(x_coords_end, delta_n_x)
                        ]
                        end_y = [
                            y - y_shift + dn_y * p_y
                            for y, dn_y in zip(y_coords_end, delta_n_y)
                        ]
                    
                    try:
                        # 批量计算起点和终点的权重电势
                        U_w_1 = self._get_weighting_potentials_batch(
                            my_f, start_x, start_y, z_coords, 0
                        )
                        
                        # 获取终点的权重电势
                        U_w_2 = self._get_weighting_potentials_batch(
                            my_f, end_x, end_y, z_coords_end, 0
                        )
                        
                        # 计算电势差
                        dU_w = [u2 - u1 for u1, u2 in zip(U_w_1, U_w_2)]
                        
                        # 处理陷阱效应
                        if has_irradiation:
                            charges = self._calculate_trapped_charges(
                                charge, x_coords, y_coords, z_coords, d_times, delta_t, my_f
                            )
                        else:
                            charges = [charge] * n_points
                        
                        # 计算信号
                        signals = [q * e0 * du for q, du in zip(charges, dU_w)]
                        
                        # 存储到这个载流子的对应电极
                        carrier_electrode_signals[electrode_idx] = signals
                        success_count += 1
                        
                    except Exception as e:
                        if not self._signal_warning_logged:
                            carrier_type = "hole" if charge > 0 else "electron"
                            logger.warning("%s 载流子%d电极%d信号计算失败: %s", carrier_type, carrier_idx, electrode_idx, e)
                            self._signal_warning_logged = True
                        raise
            
            # 存储这个载流子的所有电极信号
            if success_count > 0:
                self.signals[carrier_idx] = carrier_electrode_signals
            
            return success_count > 0
            
        except Exception as e:
            raise RuntimeError(f"处理载流子{carrier_idx}信号时出错: {e}") from e
     
    def _calculate_signal_multi_contact(self, all_indices, my_f, e0, delta_t, has_irradiation, my_d):
        """多电极情况下的向量化信号计算 - 处理所有载流子"""
        n_electrodes = len(self.read_out_contact)
        
        logger.info(f"多电极信号计算: {n_electrodes}个电极")
        
        # 批量处理所有载流子
        processed_count = 0
        for carrier_idx in all_indices:
            if self._process_carrier_signal_multi(carrier_idx, my_f, e0, delta_t, has_irradiation, n_electrodes):
                processed_count += 1

            if carrier_idx % 10 == 0:
                self._log_progress_signal(carrier_idx, len(all_indices))
        
        # 统计信号数据
        total_signal_points = self._count_signal_points(self.signals)
        non_empty_carriers = sum(1 for carrier_signals in self.signals if carrier_signals)
        
        logger.info(f"多电极信号计算完成: 处理了{processed_count}个载流子, {n_electrodes}个电极")
        logger.info(f"有信号的载流子: {non_empty_carriers}/{len(self.positions)}, 总信号点数={total_signal_points}")

    def _process_carrier_signal_multi(self, carrier_idx, my_f, e0, delta_t, has_irradiation, n_electrodes):
        """处理单个载流子在多电极配置下的信号 - 返回是否成功处理"""
        charge = self.charges[carrier_idx]
        path_reduced = self.paths_reduced[carrier_idx]
        
        if len(path_reduced) <= 1:
            return False
        
        try:
            n_points = len(path_reduced) - 1
            
            # 调试信息
            if carrier_idx < 5:  # 只打印前几个载流子的调试信息
                logger.debug(f"多电极-载流子{carrier_idx}: 电荷={charge}, 路径点数={len(path_reduced)}")
            
            # 提取坐标和时间
            x_coords = [point[0] for point in path_reduced[:-1]]
            y_coords = [point[1] for point in path_reduced[:-1]]
            z_coords = [point[2] for point in path_reduced[:-1]]
            times = [point[3] for point in path_reduced[:-1]]
            d_times = [path_reduced[i+1][3] - path_reduced[i][3] for i in range(len(path_reduced)-1)]
            
            # 为每个电极计算信号
            success_count = 0
            electrode_signals = []  # 按电极存储信号
            
            for j in range(n_electrodes):
                try:
                    # 批量计算起点和终点的权重电势
                    U_w_1 = self._get_weighting_potentials_batch(
                        my_f, x_coords, y_coords, z_coords, j
                    )
                    
                    # 获取终点的权重电势
                    x_coords_end = [point[0] for point in path_reduced[1:]]
                    y_coords_end = [point[1] for point in path_reduced[1:]]
                    z_coords_end = [point[2] for point in path_reduced[1:]]
                    
                    U_w_2 = self._get_weighting_potentials_batch(
                        my_f, x_coords_end, y_coords_end, z_coords_end, j
                    )
                    
                    # 计算电势差
                    dU_w = [u2 - u1 for u1, u2 in zip(U_w_1, U_w_2)]
                    
                    # 检查权重电势值
                    if carrier_idx < 3 and j < 3:  # 前几个载流子和电极
                        logger.debug(f"电极{j}权重电势: U_w_1={U_w_1[:3]}, U_w_2={U_w_2[:3]}, dU_w={dU_w[:3]}")
                    
                    # 处理陷阱效应
                    if has_irradiation:
                        charges = self._calculate_trapped_charges(
                            charge, x_coords, y_coords, z_coords, d_times, delta_t, my_f
                        )
                    else:
                        charges = [charge] * n_points
                    
                    # 计算信号
                    signals = [q * e0 * du for q, du in zip(charges, dU_w)]
                    
                    # 检查信号值
                    if carrier_idx < 3 and j < 3 and any(s != 0 for s in signals[:3]):
                        logger.debug(f"电极{j}信号: {signals[:3]}")
                    
                    # 存储信号
                    electrode_signals.append(signals)
                    
                    success_count += 1
                    
                except Exception as e:
                    if not getattr(self, '_signal_warning_logged', False):
                        carrier_type = "hole" if charge > 0 else "electron"
                        logger.warning("%s 载流子%d电极%d信号计算失败: %s", carrier_type, carrier_idx, j, e)
                        self._signal_warning_logged = True
                    raise
            
            # 记录这个载流子的信号统计
            if electrode_signals and carrier_idx < 3:
                total_signals = sum(len(sigs) for sigs in electrode_signals)
                non_zero_total = sum(1 for sigs in electrode_signals for s in sigs )
                logger.debug(f"多电极-载流子{carrier_idx}: 总信号数={total_signals}, 非零信号数={non_zero_total}")

            if success_count > 0:
                self.signals[carrier_idx] = electrode_signals
            
            return success_count > 0
            
        except Exception as e:
            raise RuntimeError(
                f"处理载流子{carrier_idx}多电极信号时出错: {e}"
            ) from e
    
    def _get_weighting_potentials_batch(self, my_f, x_coords, y_coords, z_coords, electrode_idx):
        """获取路径点的权重电势。"""
        potentials = []
        
        for i in range(len(x_coords)):
            try:
                potential = my_f.get_w_p_cached(x_coords[i], y_coords[i], z_coords[i], electrode_idx)
            except Exception as e:
                raise RuntimeError(
                    f"权重电势获取失败: ({x_coords[i]}, {y_coords[i]}, {z_coords[i]}), 电极{electrode_idx}: {e}"
                ) from e
            if potential is None:
                raise RuntimeError(
                    f"权重电势获取失败: ({x_coords[i]}, {y_coords[i]}, {z_coords[i]}), "
                    f"电极{electrode_idx}: 返回 None"
                )

            potentials.append(potential)
            
            if i < 3 and len(potentials) < 10:
                logger.debug(f"权重电势[{i}]: ({x_coords[i]:.1f}, {y_coords[i]:.1f}, {z_coords[i]:.1f}) -> {potential:.6f}")
        return potentials
    def _calculate_trapped_charges_stochastic(
        self,
        initial_charge,
        x_coords,
        y_coords,
        z_coords,
        d_times,
        delta_t,
        my_f,
    ):
        """
        逐载流子随机俘获、释放和寿命湮灭模型。

        返回值：
            每个轨迹点上的可移动电荷。
            被捕获或湮灭期间返回 0。
        """

        n_points = len(x_coords)

        device_dict = getattr(my_f, "device_dict", {})
        trapping_cfg = device_dict.get("trapping_model", {})

        if not trapping_cfg.get("enabled", False):
            return [initial_charge for _ in range(n_points)]

        carrier_type = str(self.carrier_type).lower()

        if carrier_type.startswith("electron"):
            release_key = "electron_release_time"
            lifetime_key = "electron_lifetime"
            carrier_is_electron = True
        else:
            release_key = "hole_release_time"
            lifetime_key = "hole_lifetime"
            carrier_is_electron = False

        release_time = trapping_cfg.get(
            release_key,
            float("inf"),
        )

        lifetime = device_dict.get(
            lifetime_key,
            float("inf"),
        )

        if not math.isfinite(float(lifetime)) or float(lifetime) <= 0.0:
            lifetime_rate = 0.0
        else:
            lifetime_rate = 1.0 / float(lifetime)

        if (
            not math.isfinite(float(release_time))
            or float(release_time) <= 0.0
        ):
            release_rate = 0.0
        else:
            release_rate = 1.0 / float(release_time)

        seed = int(
            trapping_cfg.get(
                "random_seed",
                0,
            )
        )

        # 电子、空穴使用不同的随机序列
        seed += 0 if carrier_is_electron else 1

        rng = np.random.default_rng(seed)

        state_mobile = 0
        state_trapped = 1
        state_dead = 2

        state = state_mobile
        mobile_charge = float(initial_charge)
        trapped_charge = 0.0

        output_charge = []

        capture_count = 0
        release_count = 0
        lifetime_loss_count = 0

        for i in range(n_points):
            try:
                if carrier_is_electron:
                    trapping_rate = my_f.get_trap_e_cached(
                        float(x_coords[i]),
                        float(y_coords[i]),
                        float(z_coords[i]),
                    )
                else:
                    trapping_rate = my_f.get_trap_h_cached(
                        float(x_coords[i]),
                        float(y_coords[i]),
                        float(z_coords[i]),
                    )
            except Exception:
                trapping_rate = 0.0

            if not math.isfinite(float(trapping_rate)):
                trapping_rate = 0.0

            trapping_rate = max(float(trapping_rate), 0.0)

            try:
                step_time = max(
                    float(d_times[i]),
                    0.0,
                ) * float(delta_t)
            except Exception:
                step_time = 0.0

            if state == state_mobile:
                total_rate = trapping_rate + lifetime_rate

                if total_rate > 0.0 and step_time > 0.0:
                    event_probability = -math.expm1(
                        -total_rate * step_time
                    )

                    if rng.random() < event_probability:
                        # 决定是陷阱捕获，还是寿命湮灭
                        if (
                            trapping_rate > 0.0
                            and rng.random()
                            < trapping_rate / total_rate
                        ):
                            state = state_trapped
                            trapped_charge = mobile_charge
                            mobile_charge = 0.0
                            capture_count += 1
                        else:
                            state = state_dead
                            mobile_charge = 0.0
                            lifetime_loss_count += 1

            elif state == state_trapped:
                if release_rate > 0.0 and step_time > 0.0:
                    release_probability = -math.expm1(
                        -release_rate * step_time
                    )

                    if rng.random() < release_probability:
                        state = state_mobile
                        mobile_charge = trapped_charge
                        trapped_charge = 0.0
                        release_count += 1

            if state == state_mobile:
                output_charge.append(mobile_charge)
            else:
                output_charge.append(0.0)

        self.last_trapping_statistics = {
            "capture_count": capture_count,
            "release_count": release_count,
            "lifetime_loss_count": lifetime_loss_count,
            "final_state": int(state),
        }

        return output_charge    
    # 10.10日 添加新的缺陷捕获前的代码    

    def _get_carrier_lifetime(self):
        """
        读取当前载流子的寿命。

        优先读取 MIM-Diamond.json 中明确设置的：
            electron_lifetime
            hole_lifetime

        只有 JSON 中没有时，才使用 self._params。
        """
        carrier_type = str(
            getattr(self, "carrier_type", "")
        ).strip().lower()

        if carrier_type.startswith("electron"):
            lifetime_key = "electron_lifetime"
        else:
            lifetime_key = "hole_lifetime"

        # 首先从 MIM-Diamond.json 读取
        lifetime = self.device_dict.get(
            lifetime_key,
            None,
        )

        lifetime_source = (
            f"device_dict.{lifetime_key}"
        )

        # JSON 中不存在时，再尝试旧参数
        if lifetime is None:
            params = getattr(
                self,
                "_params",
                {},
            )

            if isinstance(params, dict):
                lifetime = params.get(
                    "carrier_lifetime",
                    None,
                )

                lifetime_source = (
                    "_params.carrier_lifetime"
                )

        # 两处都没有时，表示不使用寿命损失
        if lifetime is None:
            lifetime = float("inf")
            lifetime_source = "default_inf"

        try:
            lifetime = float(lifetime)
        except (TypeError, ValueError):
            logger.warning(
                "%s lifetime is invalid: %r",
                self.carrier_type,
                lifetime,
            )

            lifetime = float("inf")
            lifetime_source = "invalid_inf"

        logger.info(
            "[LifetimeDebug] carrier=%s, "
            "source=%s, lifetime=%.6e s",
            self.carrier_type,
            lifetime_source,
            lifetime,
        )

        return lifetime


    def _get_trapping_rate_scale(self):
        """
        读取当前载流子的俘获率倍增因子。
        该因子只用于 CCE，不修改 Field 和 IV。
        """
        device_dict = getattr(
            self,
            "device_dict",
            {},
        )

        if not isinstance(device_dict, dict):
            device_dict = {}

        trapping_cfg = device_dict.get(
            "trapping_model",
            {},
        )

        if not isinstance(trapping_cfg, dict):
            trapping_cfg = {}

        scale_config = trapping_cfg.get(
            "trapping_rate_scale",
            1.0,
        )

        carrier_type = str(
            getattr(self, "carrier_type", "")
        ).strip().lower()

        if isinstance(scale_config, dict):
            if carrier_type.startswith("electron"):
                scale = scale_config.get(
                    "electron",
                    scale_config.get(
                        "default",
                        1.0,
                    ),
                )
            else:
                scale = scale_config.get(
                    "hole",
                    scale_config.get(
                        "default",
                        1.0,
                    ),
                )
        else:
            scale = scale_config

        try:
            scale = float(scale)
        except (TypeError, ValueError):
            scale = 1.0

        if (
            not math.isfinite(scale)
            or scale < 0.0
        ):
            scale = 1.0

        return scale

    #倍增因子
    def _get_local_trapping_rate(
        self,
        my_f,
        x,
        y,
        z,
    ):
        """
        获取当前位置的有效俘获率。

        effective_rate =
            raw_field_rate * trapping_rate_scale
        """
        carrier_type = str(
            getattr(self, "carrier_type", "")
        ).strip().lower()

        try:
            if carrier_type.startswith("electron"):
                raw_rate = my_f.get_trap_e_cached(
                    float(x),
                    float(y),
                    float(z),
                )
            else:
                raw_rate = my_f.get_trap_h_cached(
                    float(x),
                    float(y),
                    float(z),
                )

        except Exception as exc:
            logger.warning(
                "%s trap rate failed at "
                "(%.3f, %.3f, %.3f): %s",
                self.carrier_type,
                float(x),
                float(y),
                float(z),
                exc,
            )
            return 0.0

        try:
            raw_rate = float(raw_rate)
        except (TypeError, ValueError):
            return 0.0

        if (
            not math.isfinite(raw_rate)
            or raw_rate < 0.0
        ):
            return 0.0

        scale = self._get_trapping_rate_scale()

        effective_rate = raw_rate * scale

        if (
            not math.isfinite(effective_rate)
            or effective_rate < 0.0
        ):
            return 0.0

        if not getattr(
            self,
            "_trap_scale_logged",
            False,
        ):
            logger.info(
                "[TrapScale] carrier=%s, "
                "raw_rate=%.6e s^-1, "
                "scale=%.6e, "
                "effective_rate=%.6e s^-1",
                self.carrier_type,
                raw_rate,
                scale,
                effective_rate,
            )

            self._trap_scale_logged = True

        return effective_rate
    # def _get_local_trapping_rate(
    #     self,
    #     my_f,
    #     x,
    #     y,
    #     z,
    #     ):
    #     """取得当前位置当前载流子的陷阱俘获率。"""
    #     carrier_type = str(
    #         getattr(self, "carrier_type", "")
    #     ).strip().lower()

    #     try:
    #         if carrier_type.startswith("electron"):
    #             trapping_rate = my_f.get_trap_e_cached(
    #                 float(x),
    #                 float(y),
    #                 float(z),
    #             )
    #         else:
    #             trapping_rate = my_f.get_trap_h_cached(
    #                 float(x),
    #                 float(y),
    #                 float(z),
    #             )
    #     except Exception as exc:
    #         logger.warning(
    #             "%s trap rate failed at "
    #             "(%.3f, %.3f, %.3f): %s",
    #             self.carrier_type,
    #             float(x),
    #             float(y),
    #             float(z),
    #             exc,
    #         )
    #         return 0.0

    #     try:
    #         trapping_rate = float(trapping_rate)
    #     except (TypeError, ValueError):
    #         return 0.0

    #     if (
    #         not math.isfinite(trapping_rate)
    #         or trapping_rate < 0.0
    #     ):
    #         return 0.0

    #     return trapping_rate


    def _calculate_trapped_charges(
        self,
        initial_charge,
        x_coords,
        y_coords,
        z_coords,
        d_times,
        delta_t,
        my_f,
        ):
        """
        俘获模型统一入口。

        deterministic:
            原来的平均指数衰减。

        stochastic:
            宏观载流子包内部的随机俘获、释放和寿命湮灭。

        两种模型二选一，不会连续计算两遍。
        """
        trapping_cfg = self.device_dict.get(
            "trapping_model",
            {},
        )

        if not isinstance(trapping_cfg, dict):
            trapping_cfg = {}

        enabled = bool(
            trapping_cfg.get(
                "enabled",
                False,
            )
        )

        mode = str(
            trapping_cfg.get(
                "mode",
                "deterministic",
            )
        ).strip().lower()

        if enabled and mode == "stochastic":
            return (
                self._calculate_trapped_charges_stochastic(
                    initial_charge,
                    x_coords,
                    y_coords,
                    z_coords,
                    d_times,
                    delta_t,
                    my_f,
                )
            )

        return (
            self._calculate_trapped_charges_deterministic(
                initial_charge,
                x_coords,
                y_coords,
                z_coords,
                d_times,
                delta_t,
                my_f,
            )
        )


    def _calculate_trapped_charges_deterministic(
        self,
        initial_charge,
        x_coords,
        y_coords,
        z_coords,
        d_times,
        delta_t,
        my_f,
        ):
        """
        原来的确定性平均衰减模型：

        q(t) = q0 * exp[-∫(trap_rate + lifetime_rate) dt]
        """
        n_points = min(
            len(x_coords),
            len(y_coords),
            len(z_coords),
            len(d_times),
        )

        if n_points <= 0:
            return []

        lifetime = self._get_carrier_lifetime()

        if (
            math.isfinite(lifetime)
            and lifetime > 0.0
        ):
            lifetime_rate = 1.0 / lifetime
        else:
            lifetime_rate = 0.0

        output_charges = []
        cumulative_hazard = 0.0

        max_trapping_rate = 0.0
        total_path_time = 0.0
        integrated_trap_hazard = 0.0

        for i in range(n_points):
            trapping_rate = (
                self._get_local_trapping_rate(
                    my_f,
                    x_coords[i],
                    y_coords[i],
                    z_coords[i],
                )
            )

            try:
                step_time = (
                    max(float(d_times[i]), 0.0)
                    * float(delta_t)
                )
            except (TypeError, ValueError):
                step_time = 0.0

            total_rate = (
                trapping_rate
                + lifetime_rate
            )

            cumulative_hazard += (
                total_rate * step_time
            )

            total_path_time += step_time

            integrated_trap_hazard += (
                trapping_rate * step_time
            )

            max_trapping_rate = max(
                max_trapping_rate,
                trapping_rate,
            )

            decay_factor = math.exp(
                -min(cumulative_hazard, 700.0)
            )

            output_charges.append(
                float(initial_charge)
                * decay_factor
            )

        self.last_trapping_statistics = {
            "mode": "deterministic",
            "path_time_s": total_path_time,
            "max_trapping_rate_1_s": (
                max_trapping_rate
            ),
            "trap_hazard": (
                integrated_trap_hazard
            ),
            "lifetime_hazard": (
                lifetime_rate
                * total_path_time
            ),
            "final_decay_factor": math.exp(
                -min(cumulative_hazard, 700.0)
            ),
        }

        logger.info(
                "%s total trapping statistics: %s",
                self.carrier_type,
                self.trapping_statistics_total,
            )

        return output_charges


    def _calculate_trapped_charges_stochastic(
        self,
        initial_charge,
        x_coords,
        y_coords,
        z_coords,
        d_times,
        delta_t,
        my_f,
        ):
        """
        宏观载流子包内部的随机模型。

        每个宏观载流子包包含多个真实电子或空穴，
        因此使用二项分布抽样，而不是把整个载流子包
        当作一个粒子进行一次随机判断。

        移动载流子可能：
            1. 被缺陷捕获；
            2. 因有限寿命而永久湮灭。

        已捕获载流子可能：
            1. 按 release_time 随机释放；
            2. 重新进入移动载流子总体。
        """
        n_points = min(
            len(x_coords),
            len(y_coords),
            len(z_coords),
            len(d_times),
        )

        if n_points <= 0:
            return []

        trapping_cfg = self.device_dict.get(
            "trapping_model",
            {},
        )

        if not isinstance(trapping_cfg, dict):
            trapping_cfg = {}

        carrier_type = str(
            getattr(self, "carrier_type", "")
        ).strip().lower()

        is_electron = carrier_type.startswith(
            "electron"
        )

        if is_electron:
            release_key = "electron_release_time"
            carrier_seed_offset = 0
        else:
            release_key = "hole_release_time"
            carrier_seed_offset = 1

        lifetime = self._get_carrier_lifetime()

        if (
            math.isfinite(lifetime)
            and lifetime > 0.0
        ):
            lifetime_rate = 1.0 / lifetime
        else:
            lifetime_rate = 0.0

        try:
            release_time = float(
                trapping_cfg.get(
                    release_key,
                    float("inf"),
                )
            )
        except (TypeError, ValueError):
            release_time = float("inf")

        if (
            math.isfinite(release_time)
            and release_time > 0.0
        ):
            release_rate = 1.0 / release_time
        else:
            release_rate = 0.0

        stochastic_lifetime = bool(
            trapping_cfg.get(
                "stochastic_lifetime",
                True,
            )
        )

        # max_release_cycles=0 表示关闭释放；
        # 大于0时允许释放。
        # 当前总体模型按有限轨迹点前进，不会产生无限循环。
        try:
            max_release_cycles = int(
                trapping_cfg.get(
                    "max_release_cycles",
                    8,
                )
            )
        except (TypeError, ValueError):
            max_release_cycles = 8

        release_enabled = (
            max_release_cycles > 0
            and release_rate > 0.0
        )

        # 初始化随机数发生器
        if self._trap_rng is None:
            try:
                random_seed = int(
                    trapping_cfg.get(
                        "random_seed",
                        20261010,
                    )
                )
            except (TypeError, ValueError):
                random_seed = 20261010

            self._trap_rng = np.random.default_rng(
                random_seed
                + carrier_seed_offset
            )

        rng = self._trap_rng

        initial_charge = float(
            initial_charge
        )

        if initial_charge == 0.0:
            return [
                0.0
                for _ in range(n_points)
            ]

        # 当前 RASER 中的 initial_charge 不是库仑，
        # 而是该宏观载流子包所代表的电子/空穴数量。
        initial_particle_count = max(
            int(
                round(
                    abs(initial_charge)
                )
            ),
            1,
        )

        # 保留原始载流子包的符号和总权重。
        # 之后的信号计算会统一乘基本电荷 e0。
        charge_per_particle = (
            initial_charge
            / float(initial_particle_count)
        )

        max_binomial_count = (
                    np.iinfo(np.int64).max
                )

        if (
            initial_particle_count
            > max_binomial_count
        ):
            raise ValueError(
                "initial_particle_count is too large: "
                f"{initial_particle_count}, "
                "please check the unit of initial_charge="
                f"{initial_charge}"
            )

        logger.info(
            "%s stochastic packet: "
            "initial_charge=%.6e, "
            "particle_count=%d, "
            "charge_per_particle=%.6e",
            self.carrier_type,
            initial_charge,
            initial_particle_count,
            charge_per_particle,
        )



        mobile_count = (
            initial_particle_count
        )

        trapped_count = 0
        dead_count = 0

        output_charges = []

        capture_count = 0
        release_count = 0
        lifetime_loss_count = 0

        total_path_time = 0.0
        integrated_trap_hazard = 0.0
        max_trapping_rate = 0.0

        for i in range(n_points):
            trapping_rate = (
                self._get_local_trapping_rate(
                    my_f,
                    x_coords[i],
                    y_coords[i],
                    z_coords[i],
                )
            )

            try:
                step_time = (
                    max(float(d_times[i]), 0.0)
                    * float(delta_t)
                )
            except (TypeError, ValueError):
                step_time = 0.0

            total_path_time += step_time

            integrated_trap_hazard += (
                trapping_rate * step_time
            )

            max_trapping_rate = max(
                max_trapping_rate,
                trapping_rate,
            )

            # 只允许本步开始前已经被捕获的载流子
            # 在本步释放，防止刚捕获就立即释放。
            old_trapped_count = (
                trapped_count
            )

            # ==================================
            # 移动载流子的俘获和寿命湮灭
            # ==================================

            if stochastic_lifetime:
                active_lifetime_rate = (
                    lifetime_rate
                )
            else:
                active_lifetime_rate = 0.0

            total_event_rate = (
                trapping_rate
                + active_lifetime_rate
            )

            new_capture_count = 0
            new_lifetime_loss_count = 0

            if (
                mobile_count > 0
                and total_event_rate > 0.0
                and step_time > 0.0
            ):
                event_probability = (
                    -math.expm1(
                        -total_event_rate
                        * step_time
                    )
                )

                event_probability = min(
                    max(
                        event_probability,
                        0.0,
                    ),
                    1.0,
                )

                event_count = int(
                    rng.binomial(
                        int(mobile_count),
                        event_probability,
                    )
                )

                if (
                    event_count > 0
                    and trapping_rate > 0.0
                ):
                    capture_fraction = (
                        trapping_rate
                        / total_event_rate
                    )

                    capture_fraction = min(
                        max(
                            capture_fraction,
                            0.0,
                        ),
                        1.0,
                    )

                    new_capture_count = int(
                        rng.binomial(
                            int(event_count),
                            capture_fraction,
                        )
                    )

                new_lifetime_loss_count = (
                    event_count
                    - new_capture_count
                )

                mobile_count -= event_count

                trapped_count += (
                    new_capture_count
                )

                dead_count += (
                    new_lifetime_loss_count
                )

                capture_count += (
                    new_capture_count
                )

                lifetime_loss_count += (
                    new_lifetime_loss_count
                )

            # ==================================
            # 已捕获载流子的随机释放
            # ==================================

            released_count = 0

            if (
                release_enabled
                and old_trapped_count > 0
                and step_time > 0.0
            ):
                release_probability = (
                    -math.expm1(
                        -release_rate
                        * step_time
                    )
                )

                release_probability = min(
                    max(
                        release_probability,
                        0.0,
                    ),
                    1.0,
                )

                released_count = int(
                    rng.binomial(
                        int(old_trapped_count),
                        release_probability,
                    )
                )

                trapped_count -= (
                    released_count
                )

                mobile_count += (
                    released_count
                )

                release_count += (
                    released_count
                )

            # 当前只有移动电荷产生漂移感应信号
            current_mobile_charge = (
                charge_per_particle
                * mobile_count
            )

            output_charges.append(
                current_mobile_charge
            )

        lifetime_hazard = (
            lifetime_rate
            * total_path_time
            if stochastic_lifetime
            else 0.0
        )

        self.last_trapping_statistics = {
            "mode": "stochastic",

            "initial_particle_count": (
                initial_particle_count
            ),
            
            "trapping_rate_scale": (
                self._get_trapping_rate_scale()
            ),

            "capture_count": (
                capture_count
            ),

            "release_count": (
                release_count
            ),

            "lifetime_loss_count": (
                lifetime_loss_count
            ),

            "final_mobile_count": (
                mobile_count
            ),

            "final_trapped_count": (
                trapped_count
            ),

            "final_dead_count": (
                dead_count
            ),

            "path_time_s": (
                total_path_time
            ),

            "max_trapping_rate_1_s": (
                max_trapping_rate
            ),

            "trap_hazard": (
                integrated_trap_hazard
            ),
            "lifetime_s": lifetime,

            "lifetime_rate_1_s": (
                lifetime_rate
            ),
            
            "stochastic_lifetime": (
                stochastic_lifetime
            ),

            "lifetime_hazard": (
                lifetime_hazard
            ),
        }

        # 累计整个电子或空穴系统，而不是只保留最后一个包
        for key in (
            "initial_particle_count",
            "capture_count",
            "release_count",
            "lifetime_loss_count",
            "final_mobile_count",
            "final_trapped_count",
            "final_dead_count",
        ):
            self.trapping_statistics_total[key] += int(
                self.last_trapping_statistics[key]
            )

        logger.info(
            "%s trapping packet statistics: %s",
            self.carrier_type,
            self.last_trapping_statistics,
        )

        return output_charges




    #最初版本
    # def _calculate_trapped_charges(self, initial_charge, x_coords, y_coords, z_coords, d_times, delta_t, my_f):
    #     """计算考虑陷阱效应的电荷 - 使用列表推导式版本"""
    #     n_points = len(x_coords)
        
    #     # 批量获取陷阱率
    #     trapping_rates = []
    #     for i in range(n_points):
    #         try:
    #             if initial_charge >= 0:  # 空穴
    #                 trapping_rate = my_f.get_trap_h_cached(x_coords[i], y_coords[i], z_coords[i])
    #             else:  # 电子
    #                 trapping_rate = my_f.get_trap_e_cached(x_coords[i], y_coords[i], z_coords[i])
    #             trapping_rates.append(trapping_rate)
    #         except Exception as e:
    #             trapping_rates.append(0.0)
        
    #     # 计算累积衰减因子
    #     decay_factors = []
    #     cumulative_factor = 0.0
    #     for i in range(n_points):
    #         cumulative_factor += trapping_rates[i] * d_times[i] * delta_t
    #         decay_factors.append(math.exp(-cumulative_factor))
        
    #     return [initial_charge * factor for factor in decay_factors]
    
    def verify_signal_transfer(self, original_carriers):
        """验证信号是否正确传递到原始载流子"""
        logger.info("=== 信号传递验证 ===")
        
        valid_carriers = 0
        total_electrodes_with_signals = 0
        total_signal_points = 0
        
        for i, carrier in enumerate(original_carriers):
            if hasattr(carrier, 'signal') and carrier.signal:
                carrier_electrodes_with_signals = 0
                carrier_signal_points = 0
                
                for electrode_idx, sig_list in enumerate(carrier.signal):
                    if sig_list:  # 检查信号列表是否非空
                        carrier_electrodes_with_signals += 1
                        carrier_signal_points += len(sig_list)
                
                if carrier_electrodes_with_signals > 0:
                    valid_carriers += 1
                    total_electrodes_with_signals += carrier_electrodes_with_signals
                    total_signal_points += carrier_signal_points
                    
                    if i < 3:  # 只打印前3个载流子的详细信息
                        logger.info(f"载流子{i}: {carrier_electrodes_with_signals}个电极有信号, {carrier_signal_points}个信号点")
        
        logger.info(f"信号传递验证结果: {valid_carriers}个载流子有信号, 共{total_electrodes_with_signals}个电极, {total_signal_points}个信号点")
        
        if valid_carriers == 0:
            logger.error("错误: 没有信号传递到原始载流子!")
            return False
        else:
            return True

    def _log_progress_signal(self, carrier_idx, len_all_indices):
        """记录进度"""
        progress = carrier_idx / len_all_indices * 100
        logger.info(f"第{carrier_idx}个载流子收集到信号 ({progress:.1f}%完成)")
