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
from ..util.math import Vector

tolerance_default = 1e-6

min_intensity = 1 # V/cm

logger = logging.getLogger(__name__)
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger.setLevel(logging.INFO)

class VectorizedCarrierSystem:
    """完全自包含的向量化载流子系统 - 替代CarrierCluster"""
    
    def __init__(self, all_positions, all_charges, all_times, all_signals, material, carrier_type="electron", 
                read_out_contact=None, my_d=None):
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

        # 性能统计
        self.performance_stats = {
            'total_steps': 0,
            'field_calculations': 0,
            'boundary_checks': 0,
            'carriers_terminated': 0,
            'low_field_terminations': 0,
            'boundary_terminations': 0
        }
        
        # 信号存储
        self.signals = self._initialize_signal_storage_per_carrier(len(all_charges), read_out_contact)
        self._signal_warning_logged = False
        
        logger.info(f"向量化系统初始化: {len(all_charges)}个{carrier_type}")
        logger.info(f"探测器尺寸: {my_d.l_x:.1f} × {my_d.l_y:.1f} × {my_d.l_z:.1f} um")

    def _initialize_params(self, my_d):
        params = {}
        try:
            if my_d is not None:
                params['temperature'] = self._get_param(my_d, 'temperature', 300.0)
                params['field_resolution'] = self._resolve_field_resolution(my_d)
                params['boundary_tolerance'] = self._resolve_boundary_tolerance(my_d)
                params['max_drift_time'] = 10000e-9   # 增加最大漂移时间
                params['min_field_strength'] = self._resolve_min_field_strength(my_d)
                params['max_vector_steps'] = self._get_param(my_d, 'vector_max_steps', 200000, param_type=int)
                
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
        self.paths = [[] for _ in range(len(all_positions))]
        self.paths_reduced = [[] for _ in range(len(all_positions))]
        
        # 初始化每个载流子的路径
        for i, pos in enumerate(all_positions):
            x, y, z = pos
            t = self.times[i]
            
            # 完整路径
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
    
    def _calculate_reduced_coords(self, x, y, my_d):
        """计算简化坐标"""
        use_reduced = (self.read_out_contact and 
                      len(self.read_out_contact) == 1)
        
        try:
            my_d.field_shift_x = float(my_d.field_shift_x)
        except:
            my_d.field_shift_x = 0.0

        try:
            my_d.field_shift_y = float(my_d.field_shift_y)
        except:
            my_d.field_shift_y = 0.0
        
        if use_reduced:
            x_reduced = (x - my_d.l_x/2 + (my_d.x_ele_num%2)*my_d.p_x/2.0) % my_d.p_x + my_d.field_shift_x
            y_reduced = (y - my_d.l_y/2 + (my_d.y_ele_num%2)*my_d.p_y/2.0) % my_d.p_y + my_d.field_shift_y
        else:
            x_reduced = x
            y_reduced = y
        
        return x_reduced, y_reduced
    
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
        
        for step in range(planned_steps):
            if step % 100 == 0:
                self._log_progress_drift(step, total_carriers)
            
            n_terminated = self.drift_step_batch(my_d, my_f, delta_t, step)
            self.performance_stats['total_steps'] += 1
            
            if not np.any(self.active):
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

    def drift_step_batch(self, my_d, my_f, delta_t, step=0):
        """批量单步漂移 - 核心算法"""
        if not np.any(self.active):
            return 0
            
        n_terminated = 0
        params = self._params
        
        for idx in range(len(self.active)):
            if not self.active[idx]:
                continue
                
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
            if self.times[idx] > params['max_vector_steps']:
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
                doping = my_f.get_doping_cached(x_reduced, y_reduced, z)
                mu = self.mobility(params['temperature'], doping, charge, intensity)
                diffusion_constant = math.sqrt(2.0 * self.kboltz * params['temperature'] * mu * delta_t) * 1e4
            except Exception as e:
                raise RuntimeError(f"迁移率计算失败: {e}")
            
            # 速度和位移计算
            delta_x, delta_y, delta_z = self._calculate_displacement(charge, e_field, mu, delta_t)
            
            # 扩散位移
            dif_x, dif_y, dif_z = self._calculate_diffusion(diffusion_constant)
            
            # 更新位置
            self._update_carrier_position(idx, delta_x, delta_y, delta_z, dif_x, dif_y, dif_z)
        
        self.performance_stats['carriers_terminated'] += n_terminated
        return n_terminated

    def _get_e_field_reduced(self, my_f, x, y, z, idx, field_x=None, field_y=None):
        """安全的电场获取"""
        fx = x if field_x is None else field_x
        fy = y if field_y is None else field_y
        try:
            self.performance_stats['field_calculations'] += 1
            e_field = my_f.get_e_field_cached(fx, fy, z)
            if e_field is None or len(e_field) != 3:
                raise ValueError("无效的电场值")
            return e_field
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
        start_time = time.time()
        e0 = 1.60217733e-19
        has_irradiation = my_d.irradiation_model is not None
        
        # 调试信息
        logger.info(f"=== 信号计算调试信息 ===")
        logger.info(f"载流子类型: {self.carrier_type}")
        logger.info(f"总载流子数: {len(self.positions)}")
        logger.info(f"活跃载流子数: {np.sum(self.active)}")
        logger.info(f"读取电极配置: {self.read_out_contact}")
        logger.info(f"是否有辐射损伤: {has_irradiation}")
        
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
        total_signal_points = sum(len(electrode_signals) for carrier_signals in self.signals for electrode_signals in carrier_signals)
        
        logger.info(f"信号计算完成: {total_carriers_with_signals}个载流子有信号, 总信号点数={total_signal_points}")
        
        if total_signal_points == 0:
            logger.warning("警告: 信号计算结果为0！")
        
        end_time = time.time()
        logger.info(f"批量信号计算完成: 耗时{end_time - start_time:.2f}秒")

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
            
            for j in range(2 * x_span + 1):
                x_shift = (j - x_span) * p_x
                for k in range(2 * y_span + 1):
                    y_shift = (k - y_span) * p_y
                    electrode_idx = j * (2 * y_span + 1) + k
                    
                    try:
                        # 批量计算起点和终点的权重电势
                        U_w_1 = self._get_weighting_potentials_batch(
                            my_f, 
                            [x - x_shift + delta_n_x * p_x for (x,delta_n_x) in zip(x_coords, delta_n_x)], 
                            [y - y_shift + delta_n_y * p_y for (y,delta_n_y) in zip(y_coords, delta_n_y)], 
                            z_coords, 0
                        )
                        
                        # 获取终点的权重电势
                        x_coords_end = [point[0] for point in path_reduced[1:]]
                        y_coords_end = [point[1] for point in path_reduced[1:]]
                        z_coords_end = [point[2] for point in path_reduced[1:]]
                        
                        U_w_2 = self._get_weighting_potentials_batch(
                            my_f, 
                            [x - x_shift + delta_n_x * p_x for (x,delta_n_x) in zip(x_coords_end, delta_n_x)],
                            [y - y_shift + delta_n_y * p_y for (y,delta_n_y) in zip(y_coords_end, delta_n_y)],
                            z_coords_end, 0
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
                        continue
            
            # 存储这个载流子的所有电极信号
            if success_count > 0:
                self.signals[carrier_idx] = carrier_electrode_signals
            
            return success_count > 0
            
        except Exception as e:
            logger.warning(f"处理载流子{carrier_idx}信号时出错: {e}")
            return False
     
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
        total_signal_points = sum(len(sig_list) for sig_list in self.signals[:n_electrodes])
        non_empty_electrodes = sum(1 for sig_list in self.signals[:n_electrodes] if len(sig_list) > 0)
        
        logger.info(f"多电极信号计算完成: 处理了{processed_count}个载流子, {n_electrodes}个电极")
        logger.info(f"有信号的电极: {non_empty_electrodes}/{n_electrodes}, 总信号点数={total_signal_points}")

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
                    
                    # 确保信号列表足够长
                    while len(self.signals) <= j:
                        self.signals.append([])
                    
                    # 存储信号到对应的电极列表
                    self.signals[j].extend(signals)
                    success_count += 1
                    
                except Exception as e:
                    if not getattr(self, '_signal_warning_logged', False):
                        carrier_type = "hole" if charge > 0 else "electron"
                        logger.warning("%s 载流子%d电极%d信号计算失败: %s", carrier_type, carrier_idx, j, e)
                        self._signal_warning_logged = True
                    continue
            
            # 记录这个载流子的信号统计
            if electrode_signals and carrier_idx < 3:
                total_signals = sum(len(sigs) for sigs in electrode_signals)
                non_zero_total = sum(1 for sigs in electrode_signals for s in sigs )
                logger.debug(f"多电极-载流子{carrier_idx}: 总信号数={total_signals}, 非零信号数={non_zero_total}")
            
            return success_count > 0
            
        except Exception as e:
            logger.warning(f"处理载流子{carrier_idx}多电极信号时出错: {e}")
            return False
    
    def _get_weighting_potentials_batch(self, my_f, x_coords, y_coords, z_coords, electrode_idx):
        """批量获取权重电势 - 带缺失值处理版本"""
        potentials = []
        valid_points = []  # 存储有效点的坐标和电势值
        
        # 第一次遍历：收集所有有效点
        for i in range(len(x_coords)):
            try:
                potential = my_f.get_w_p_cached(x_coords[i], y_coords[i], z_coords[i], electrode_idx)
            except Exception as e:
                logger.warning(f"权重电势获取失败: ({x_coords[i]}, {y_coords[i]}, {z_coords[i]}), 电极{electrode_idx}: {e}")
                potentials.append(None)
                
            potentials.append(potential)
            valid_points.append((x_coords[i], y_coords[i], z_coords[i], potential))
            
            if i < 3 and len(potentials) < 10:
                logger.debug(f"权重电势[{i}]: ({x_coords[i]:.1f}, {y_coords[i]:.1f}, {z_coords[i]:.1f}) -> {potential:.6f}")
        
        # 如果有缺失值，进行插值处理
        if None in potentials and valid_points:
            potentials = self._fill_missing_potentials(potentials, x_coords, y_coords, z_coords, valid_points)
        
        return potentials

    def _fill_missing_potentials(self, potentials, x_coords, y_coords, z_coords, valid_points):
        """使用最近邻有效值填充缺失的电势值"""
        filled_potentials = potentials.copy()
        
        for i, potential in enumerate(potentials):
            if potential is None:
                # 找到最近的有效点
                nearest_potential = self._find_nearest_valid_potential(
                    x_coords[i], y_coords[i], z_coords[i], valid_points
                )
                filled_potentials[i] = nearest_potential
                logger.debug(f"填充缺失电势[{i}]: 使用最近邻值 {nearest_potential:.6f}")
        
        return filled_potentials

    def _find_nearest_valid_potential(self, x, y, z, valid_points):
        """找到距离最近的有效点电势"""
        min_distance = float('inf')
        nearest_potential = 0.0  # 默认值
        
        for vx, vy, vz, potential in valid_points:
            distance = ((x - vx) ** 2 + (y - vy) ** 2 + (z - vz) ** 2) ** 0.5
            if distance < min_distance:
                min_distance = distance
                nearest_potential = potential
        
        return nearest_potential

    def _calculate_trapped_charges(self, initial_charge, x_coords, y_coords, z_coords, d_times, delta_t, my_f):
        """计算考虑陷阱效应的电荷 - 使用列表推导式版本"""
        n_points = len(x_coords)
        
        # 批量获取陷阱率
        trapping_rates = []
        for i in range(n_points):
            try:
                if initial_charge >= 0:  # 空穴
                    trapping_rate = my_f.get_trap_h_cached(x_coords[i], y_coords[i], z_coords[i])
                else:  # 电子
                    trapping_rate = my_f.get_trap_e_cached(x_coords[i], y_coords[i], z_coords[i])
                trapping_rates.append(trapping_rate)
            except Exception as e:
                trapping_rates.append(0.0)
        
        # 计算累积衰减因子
        decay_factors = []
        cumulative_factor = 0.0
        for i in range(n_points):
            cumulative_factor += trapping_rates[i] * d_times[i] * delta_t
            decay_factors.append(math.exp(-cumulative_factor))
        
        return [initial_charge * factor for factor in decay_factors]
    
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
