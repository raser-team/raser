#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
@File    :   devsim_field.py
@Time    :   2025/11/11
@Author  :   Henry Stone, Sen Zhao, Dai Zhong
@Version :   3.0
'''

import pickle
import os
import logging

import ROOT
from .assets import resolve_field_pickle
from raser.supports.math import calculate_gradient
from raser.supports.math import get_common_interpolate_1d
from raser.supports.math import get_common_interpolate_2d
from raser.supports.math import get_common_interpolate_3d
from raser.supports.paths import project_path
ROOT.gROOT.SetBatch(True)

verbose = 0
logger = logging.getLogger(__name__)

# 缓存配置常量
max_size = 50000  # 50 mm
resolution_default_1d = {'z': 0.05, 'x': 10000.0, 'y': 10000.0} 
resolution_default_2d = {'z': 0.1, 'x': 0.5, 'y': 10000.0}
resolution_default_plugin_2d = {'x': 0.1, 'y': 0.1, 'z': 10000.0}
resolution_default_3d = {'z': 0.5, 'x': 1, 'y': 1}

class DevsimField:
    def __init__(self, device_name, dimension, voltage, read_out_contact, mesher, is_plugin=False, irradiation_flux=0, 
                 bounds=None, resolution=None, field_set="default",):
        self.name = device_name
        self.voltage = voltage
        self.dimension = dimension
        self.read_out_contact = read_out_contact
        self.is_plugin = is_plugin  # 保存插件标志
        self.mesher = mesher  # 保存mesher标志

        # 初始化缓存相关属性
        if self.dimension == 1:
            resolution_default = resolution_default_1d
        elif self.dimension == 2:
            if is_plugin:
                resolution_default = resolution_default_plugin_2d
            else:
                resolution_default = resolution_default_2d
        elif self.dimension == 3:
            resolution_default = resolution_default_3d

        try:
            self.resolution = resolution or resolution_default
            # 验证字典中的所有分辨率值
            for key, value in self.resolution.items():
                try:
                    float_value = float(value)
                    if float_value <= 0:
                        self.resolution[key] = resolution_default[key]
                    else:
                        self.resolution[key] = float_value
                except (TypeError, ValueError):
                    self.resolution[key] = resolution_default[key]
        except (TypeError, AttributeError):
            # 如果resolution不是字典，使用默认值
            logger.warning("Invalid resolution format, using default resolution: {}".format(resolution_default))
            self.resolution = resolution_default
        
        self.bounds = bounds or {}
        
        # 初始化缓存字典
        self.e_field_cache = {}
        self.doping_cache = {}
        self.w_p_cache = {}
        self.trap_h_cache = {}  # 空穴陷阱率缓存
        self.trap_e_cache = {}  # 电子陷阱率缓存
        
        # 缓存统计
        self._cache_stats = {
            'hits': 0, 'misses': 0, 'errors': 0, 'fallbacks': 0,
            'trap_h_hits': 0, 'trap_h_misses': 0,
            'trap_e_hits': 0, 'trap_e_misses': 0,
        }

        path = str(project_path("field", field_set)) + os.sep

        # Weighting Potential is universal for all irradiation flux
        # TODO: Net Doping should be here too
        WeightingPotentialFiles = []
        for contact in read_out_contact:
            WeightingPotentialFiles.append(path + "weightingfield/{}/Potential_{}V.pkl".format(contact['name'], 1))

        if irradiation_flux != 0 and field_set == "default":
            path = str(project_path("field", str(irradiation_flux))) + os.sep

        DopingFile = None
        doping_file_pattern = re.compile(r'^NetDoping_(-?\d+\.?\d*)V\.pkl$')
        for filename in os.listdir(path):
            if doping_file_pattern.match(filename):
                DopingFile = path + filename
                # example: DopingFile = path + "NetDoping_0V.pkl"
                break

        PotentialFile = resolve_field_pickle(path, "Potential", self.voltage)
        TrappingRate_pFile = resolve_field_pickle(path, "TrappingRate_p", self.voltage)
        TrappingRate_nFile = resolve_field_pickle(path, "TrappingRate_n", self.voltage)

        self.set_doping(DopingFile) #self.Doping
        self.set_potential(PotentialFile) #self.Potential, self.x_efield, self.y_efield, self.z_efield
        self.set_trap_p(TrappingRate_pFile) # self.TrappingRate_p
        self.set_trap_n(TrappingRate_nFile) # self.TrappingRate_n
        self.set_w_p(WeightingPotentialFiles) #self.weighting_potential[]
        
        logger.info(f"DevsimField initialization complete, resolution: {self.resolution} um")

    def set_doping(self, DopingFile):
        try:
            with open(DopingFile,'rb') as file:
                DopingNotUniform=pickle.load(file)
                print("Doping file loaded for {}".format(self.name))
                if DopingNotUniform['metadata']['dimension'] < self.dimension:
                    print("Doping dimension not match")
                    return
        except (FileNotFoundError, TypeError):
            print("Doping file not found at {}, please run field simulation first".format(DopingFile))
            print("or manually set the doping file")
            return
        
        if DopingNotUniform['metadata']['dimension'] == 1:
            DopingUniform = get_common_interpolate_1d(DopingNotUniform)
        elif DopingNotUniform['metadata']['dimension'] == 2:
            DopingUniform = get_common_interpolate_2d(DopingNotUniform)
        elif DopingNotUniform['metadata']['dimension'] == 3:
            DopingUniform = get_common_interpolate_3d(DopingNotUniform)

        self.Doping = DopingUniform

    def set_potential(self, PotentialFile):
        try:
            with open(PotentialFile,'rb') as file:
                PotentialNotUniform=pickle.load(file)
                print("Potential file loaded for {}".format(self.name))
                if PotentialNotUniform['metadata']['dimension'] < self.dimension:
                    print("Potential dimension not match")
                    return
        except FileNotFoundError:
            print("Potential file not found at {}, please run field simulation first".format(PotentialFile))
            print("or manually set the potential file")
            return
        
        if PotentialNotUniform['metadata']['dimension'] == 1:
            PotentialUniform = get_common_interpolate_1d(PotentialNotUniform)
        elif PotentialNotUniform['metadata']['dimension'] == 2:
            PotentialUniform = get_common_interpolate_2d(PotentialNotUniform)
        elif PotentialNotUniform['metadata']['dimension'] == 3:
            PotentialUniform = get_common_interpolate_3d(PotentialNotUniform)

        self.Potential = PotentialUniform

    def set_w_p(self, WeightingPotentialFiles):
        self.WeightingPotential = []
        for i in range(len(self.read_out_contact)):
            WeightingPotentialFile = self._resolve_voltage_pickle(
                os.path.dirname(WeightingPotentialFiles[i]), "Potential", 1
            )
            try:
                with open(WeightingPotentialFile,'rb') as file:
                    WeightingPotentialNotUniform=pickle.load(file)
                    print("Weighting Potential file loaded for {} at electrode {}".format(self.name, i+1))
                    if ( WeightingPotentialNotUniform['metadata']['dimension'] < self.dimension
                    ):
                        print("Weighting Potential dimension not match")
                        return
            except FileNotFoundError:
                print("Weighting Potential file not found at {}, please run field simulation first".format(WeightingPotentialFile))
                print("or manually set the Weighting Potential file")
                return
            
            if WeightingPotentialNotUniform['metadata']['dimension'] == 1:
                WeightingPotentialUniform = get_common_interpolate_1d(WeightingPotentialNotUniform)
            elif WeightingPotentialNotUniform['metadata']['dimension'] == 2:
                WeightingPotentialUniform = get_common_interpolate_2d(WeightingPotentialNotUniform)
            elif WeightingPotentialNotUniform['metadata']['dimension'] == 3:
                WeightingPotentialUniform = get_common_interpolate_3d(WeightingPotentialNotUniform)

            self.WeightingPotential.append(WeightingPotentialUniform)
    
    def set_trap_p(self, TrappingRate_pFile):
        try:
            with open(TrappingRate_pFile,'rb') as file:
                TrappingRate_pNotUniform=pickle.load(file)
                print("TrappingRate_p file loaded for {}".format(self.name))
                if TrappingRate_pNotUniform['metadata']['dimension'] < self.dimension:
                    print("TrappingRate_p dimension not match")
                    return
        except FileNotFoundError:
            print("TrappingRate_p file not found at {}, please run field simulation first".format(TrappingRate_pFile))
            print("or manually set the hole trapping rate file")
            return
        
        if TrappingRate_pNotUniform['metadata']['dimension'] == 1:
            TrappingRate_pUniform = get_common_interpolate_1d(TrappingRate_pNotUniform)
        elif TrappingRate_pNotUniform['metadata']['dimension'] == 2:
            TrappingRate_pUniform = get_common_interpolate_2d(TrappingRate_pNotUniform)
        elif TrappingRate_pNotUniform['metadata']['dimension'] == 3:
            TrappingRate_pUniform = get_common_interpolate_3d(TrappingRate_pNotUniform)

        self.TrappingRate_p = TrappingRate_pUniform
    
    def set_trap_n(self, TrappingRate_nFile):
        try:
            with open(TrappingRate_nFile,'rb') as file:
                TrappingRate_nNotUniform=pickle.load(file)
                print("TrappingRate_n file loaded for {}".format(self.name))
                if TrappingRate_nNotUniform['metadata']['dimension'] != self.dimension:
                    print("TrappingRate_n dimension not match")
                    return
        except FileNotFoundError:
            print("TrappingRate_n file not found at {}, please run field simulation first".format(TrappingRate_nFile))
            print("or manually set the electron trapping rate file")
            return
        
        if TrappingRate_nNotUniform['metadata']['dimension'] == 1:
            TrappingRate_nUniform = get_common_interpolate_1d(TrappingRate_nNotUniform)
        elif TrappingRate_nNotUniform['metadata']['dimension'] == 2:
            TrappingRate_nUniform = get_common_interpolate_2d(TrappingRate_nNotUniform)
        elif TrappingRate_nNotUniform['metadata']['dimension'] == 3:
            TrappingRate_nUniform = get_common_interpolate_3d(TrappingRate_nNotUniform)

        self.TrappingRate_n = TrappingRate_nUniform
        
    # 3D pickle points are stored in detector order (x, y, z).
    # 2D planar fields keep the legacy (z, x) convention.

    def _get_doping(self, x, y, z):
        """
        input: position in um
        output: doping in cm^-3
        """
        x, y, z = x/1e4, y/1e4, z/1e4 # um to cm
        if self.dimension == 1:
            return self.Doping(z)
        elif self.dimension == 2:
            if self.is_plugin:
                return self.Doping(x, y)  # 2D插件使用x,y
            else:
                return self.Doping(z, x)
        elif self.dimension == 3:
            if self.mesher == "sde": # SDE使用x,y,z坐标
                return self.Doping(x, y, z)
            else :
                return self.Doping(z, x, y)
    
    def _get_potential(self, x, y, z):
        """
        input: position in um
        output: potential in V
        """
        x, y, z = x/1e4, y/1e4, z/1e4 # um to cm
        if self.dimension == 1:
            return self.Potential(z)
        elif self.dimension == 2:
            if self.is_plugin:
                return self.Potential(x, y)  # 2D插件使用x,y
            else:
                return self.Potential(z, x)
        elif self.dimension == 3:
            if self.mesher == "sde": # SDE使用x,y,z坐标
                return self.Potential(x, y, z)
            else:
                return self.Potential(z, x, y)
    
    def _get_e_field(self, x, y, z):
        """
        input: position in um
        output: intensity in V/cm
        """ 
        x, y, z = x / 1e4, y / 1e4, z / 1e4  # um to cm

        if self.dimension == 1:
            nabla_U = calculate_gradient(self.Potential, ['z'], [z])
            E_z = -1 * nabla_U[0]
            return (0, 0, E_z)

        elif self.dimension == 2:
            if self.is_plugin:
                # 2D插件使用x,y坐标
                nabla_U = calculate_gradient(self.Potential, ['x', 'y'], [x, y])
                E_x = -1 * nabla_U[0]
                E_y = -1 * nabla_U[1]
                return (E_x, E_y, 0)
            else:
                nabla_U = calculate_gradient(self.Potential, ['z', 'x'], [z, x])
                E_z = -1 * nabla_U[0]
                E_x = -1 * nabla_U[1]
                return (E_x, 0, E_z)

        elif self.dimension == 3:
            if self.mesher == "sde": # SDE使用x,y,z坐标
                nabla_U = calculate_gradient(self.Potential, ['x', 'y', 'z'], [x, y, z])
                E_x = -1 * nabla_U[0]
                E_y = -1 * nabla_U[1]
                E_z = -1 * nabla_U[2]
                return (E_x, E_y, E_z)
            else:
                nabla_U = calculate_gradient(self.Potential, ['z', 'x', 'y'], [z, x, y])
                E_z = -1 * nabla_U[0]
                E_x = -1 * nabla_U[1]
                E_y = -1 * nabla_U[2]
                return (E_x, E_y, E_z)

    def _get_w_p(self, x, y, z, i): # used in cal current
        x, y, z = x/1e4, y/1e4, z/1e4 # um to cm
        if self.dimension == 1:
            U_w = self.WeightingPotential[i](z)
        elif self.dimension == 2:
            if self.is_plugin:
                U_w = self.WeightingPotential[i](x, y)  # 2D插件使用x,y
            else:
                U_w = self.WeightingPotential[i](z, x)
        elif self.dimension == 3:
            if self.mesher == "sde": # SDE使用x,y,z坐标
                U_w = self.WeightingPotential[i](x, y, z)
            else:
                U_w = self.WeightingPotential[i](z, x, y)

        # exclude non-physical values
        if U_w < 0:
            if verbose > 0:
                print('U_w is negative at',x*1e4,y*1e4,z*1e4,i,'as',U_w)
            return 0
        elif U_w > 1:
            if verbose > 0:
                print('U_w is greater than 1 at',x*1e4,y*1e4,z*1e4,i,'as',U_w)
            return 1
        elif U_w != U_w:
            if verbose > 0:
                print('U_w is nan at',x*1e4,y*1e4,z*1e4,i)
            return 0
        else:
            return U_w

    
    def _get_trap_e(self, x, y, z):
        """
        input: position in um
        output: electron trapping rate in s^-1
        """
        x, y, z = x/1e4, y/1e4, z/1e4 # um to cm
        if self.dimension == 1:
            return self.TrappingRate_n(z)
        
        elif self.dimension == 2:
            if self.is_plugin:
                return self.TrappingRate_n(x, y)  # 2D插件使用x,y
            else:
                return self.TrappingRate_n(z, x)
        
        elif self.dimension == 3:
            if self.mesher == "sde": # SDE使用x,y,z坐标
                return self.TrappingRate_n(x, y, z)
            else:
                return self.TrappingRate_n(z, x, y)

    def _get_trap_h(self, x, y, z):
        """
        input: position in um
        output: hole trapping rate in s^-1
        """
        x, y, z = x/1e4, y/1e4, z/1e4 # um to cm
        if self.dimension == 1:
            return self.TrappingRate_p(z)
        elif self.dimension == 2:
            if self.is_plugin:
                return self.TrappingRate_p(x, y)  # 2D插件使用x,y
            else:
                return self.TrappingRate_p(z, x)
        elif self.dimension == 3:
            if self.mesher == "sde": # SDE使用x,y,z坐标
                return self.TrappingRate_p(x, y, z)
            else:
                return self.TrappingRate_p(z, x, y)

    # 缓存方法
    def get_e_field_cached(self, x, y, z):
        try:
            if not self._is_position_valid(x, y, z):
                return self._get_e_field(x, y, z) # 不缓存异常位置的电场值，继承报错
                
            key_x, key_y, key_z = self._get_index_coords(x, y, z)
            key = (key_x, key_y, key_z)
            
            if key in self.e_field_cache:
                self._cache_stats['hits'] += 1
                return self.e_field_cache[key]
            else:
                self._cache_stats['misses'] += 1
                e_field = self._get_e_field(x, y, z)
                if e_field is not None:
                    self.e_field_cache[key] = e_field
                return e_field
                
        except Exception as e:
            self._cache_stats['errors'] += 1
            logger.warning(f"failed when getting field cache ({x:.1f}, {y:.1f}, {z:.1f}): {e}")
            return self._get_e_field(x, y, z) # 出错时不使用缓存，直接计算电场值，继承报错
    
    def get_doping_cached(self, x, y, z):
        try:
            if not self._is_position_valid(x, y, z):
                return self._get_doping(x, y, z)
                
            key_x, key_y, key_z = self._get_index_coords(x, y, z)
            key = (key_x, key_y, key_z)
            
            if key in self.doping_cache:
                return self.doping_cache[key]
            else:
                doping = self._get_doping(x, y, z)
                if doping is not None:
                    self.doping_cache[key] = doping
                return doping
        except Exception as e:
            logger.warning(f"failed when getting doping cache ({x:.1f}, {y:.1f}, {z:.1f}): {e}")
            return 0.0  # 默认掺杂浓度
        
    def get_w_p_cached(self, x, y, z, n):
        try:
            if not self._is_position_valid(x, y, z):
                return self._get_w_p(x, y, z, n)
            key_x, key_y, key_z = self._get_index_coords(x, y, z)
            key = (key_x, key_y, key_z, n)
            if key in self.w_p_cache:
                return self.w_p_cache[key]
            else:
                w_p = self._get_w_p(x, y, z, n)
                if w_p is not None:
                    self.w_p_cache[key] = w_p
                return w_p
        except Exception as e:
            logger.warning(f"failed when getting w_p cache ({x:.1f}, {y:.1f}, {z:.1f}, {n}): {e}")
            return None
    
    def get_trap_h_cached(self, x, y, z):
        """获取空穴陷阱率 - 带缓存"""
        try:
            if not self._is_position_valid(x, y, z):
                return self._get_trap_h(x, y, z)
                
            key_x, key_y, key_z = self._get_index_coords(x, y, z)
            key = (key_x, key_y, key_z)
            
            if key in self.trap_h_cache:
                self._cache_stats['trap_h_hits'] += 1
                return self.trap_h_cache[key]
            else:
                self._cache_stats['trap_h_misses'] += 1
                trap_rate = self._get_trap_h(x, y, z)
                if trap_rate is not None:
                    self.trap_h_cache[key] = trap_rate
                return trap_rate
                
        except Exception as e:
            logger.warning(f"failed when getting hole trap rate cache ({x:.1f}, {y:.1f}, {z:.1f}): {e}")
            return 0.0  # 默认陷阱率
    
    def get_trap_e_cached(self, x, y, z):
        """获取电子陷阱率 - 带缓存"""
        try:
            if not self._is_position_valid(x, y, z):
                return self._get_trap_e(x, y, z)
                
            key_x, key_y, key_z = self._get_index_coords(x, y, z)
            key = (key_x, key_y, key_z)
            
            if key in self.trap_e_cache:
                self._cache_stats['trap_e_hits'] += 1
                return self.trap_e_cache[key]
            else:
                self._cache_stats['trap_e_misses'] += 1
                trap_rate = self._get_trap_e(x, y, z)
                if trap_rate is not None:
                    self.trap_e_cache[key] = trap_rate
                return trap_rate
                
        except Exception as e:
            logger.warning(f"failed when getting electron trap rate cache ({x:.1f}, {y:.1f}, {z:.1f}): {e}")
            return 0.0  # 默认陷阱率

    # 缓存辅助方法
    def _is_position_valid(self, x, y, z):
        if (abs(x) > max_size or abs(y) > max_size or abs(z) > max_size or
            math.isnan(x) or math.isnan(y) or math.isnan(z) or
            math.isinf(x) or math.isinf(y) or math.isinf(z)):
            return False
        return True
    
    def _get_index_coords(self, x, y, z):
        return (
            self._get_index_axis(x, 'x'),
            self._get_index_axis(y, 'y'),
            self._get_index_axis(z, 'z'),
        )
    
    def _get_index_axis(self, value, axis):
        tol = 1e-12
        bounds = self.bounds.get(axis)
        idx = int(math.floor(value / self.resolution[axis]))
        if bounds:
            lower, upper = bounds
            if lower is not None:
                lower_idx = int(math.floor(lower / self.resolution[axis]))
                idx = max(idx, lower_idx)
            if upper is not None:
                # 略微缩小上边界，避免刚好落在网格外
                adjusted_upper = upper - tol
                upper_idx = int(math.floor(adjusted_upper / self.resolution[axis]))
                idx = min(idx, upper_idx)
        return idx

    def get_cache_stats(self):
        total = ( self._cache_stats['hits'] + self._cache_stats['misses'] + self._cache_stats['errors']
        )
        hit_rate = self._cache_stats['hits'] / total if total > 0 else 0
        
        # 陷阱率缓存统计
        trap_h_total = ( self._cache_stats['trap_h_hits'] + self._cache_stats['trap_h_misses']
        )
        trap_h_hit_rate = ( self._cache_stats['trap_h_hits'] / trap_h_total if trap_h_total > 0 else 0
        )
        
        trap_e_total = ( self._cache_stats['trap_e_hits'] + self._cache_stats['trap_e_misses']
        )
        trap_e_hit_rate = ( self._cache_stats['trap_e_hits'] / trap_e_total if trap_e_total > 0 else 0
        )
        
        return {
            'hits': self._cache_stats['hits'],
            'misses': self._cache_stats['misses'],
            'errors': self._cache_stats['errors'],
            'fallbacks': self._cache_stats['fallbacks'],
            'hit_rate': hit_rate,
            'total_entries': len(self.e_field_cache),
            'trap_h_hits': self._cache_stats['trap_h_hits'],
            'trap_h_misses': self._cache_stats['trap_h_misses'],
            'trap_h_hit_rate': trap_h_hit_rate,
            'trap_h_entries': len(self.trap_h_cache),
            'trap_e_hits': self._cache_stats['trap_e_hits'],
            'trap_e_misses': self._cache_stats['trap_e_misses'],
            'trap_e_hit_rate': trap_e_hit_rate,
            'trap_e_entries': len(self.trap_e_cache),
        }
    
    def clear_cache(self):
        """清空所有缓存"""
        self.e_field_cache.clear()
        self.doping_cache.clear()
        self.w_p_cache.clear()
        self.trap_h_cache.clear()
        self.trap_e_cache.clear()
        logger.info("所有缓存已清空")

if __name__ == "__main__":
    pass
