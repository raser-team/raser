#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
@File    :   devsim_field.py
@Time    :   2025/11/11
@Author  :   Henry Stone, Sen Zhao, Dai Zhong
@Version :   3.0
'''

import pickle
import re
import os
import logging
import math
import time

import ROOT
ROOT.gROOT.SetBatch(True)
import numpy as np

from ..util.math import *

verbose = 0
logger = logging.getLogger(__name__)

# 缓存配置常量
max_size = 50000  # 50 mm
resolution_default_1d = {'z': 0.05, 'x': 10000.0, 'y': 10000.0} 
resolution_default_2d = {'z': 0.1, 'x': 0.5, 'y': 10000.0}
resolution_default_plugin_2d = {'x': 0.1, 'y': 0.1, 'z': 10000.0}
resolution_default_3d = {'z': 0.5, 'x': 1, 'y': 1}

class DevsimField:
    def __init__(self, device_name, dimension, voltage, read_out_contact, is_plugin=False, irradiation_flux=0, 
                 bounds=None, resolution=None, interpolation_bins=None):
        self.name = device_name
        self.voltage = voltage
        self.dimension = dimension
        self.read_out_contact = read_out_contact
        self.is_plugin = is_plugin  # 保存插件标志
        self.interpolation_bins = interpolation_bins
        
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
        self.potential_bounds_um = {}
        self.weighting_bounds_um = []
        
        # 初始化缓存字典
        self.e_field_cache = {}
        self.gain_e_field_cache = {}
        self.doping_cache = {}
        self.w_p_cache = {}
        self.trap_h_cache = {}  # 空穴陷阱率缓存
        self.trap_e_cache = {}  # 电子陷阱率缓存
        self._potential_points = None
        self._potential_values = None
        self._potential_point_tree = None
        
        # 缓存统计
        self._cache_stats = {
            'hits': 0, 'misses': 0, 'errors': 0, 'fallbacks': 0,
            'gain_hits': 0, 'gain_misses': 0, 'gain_fallbacks': 0, 'gain_errors': 0,
            'trap_h_hits': 0, 'trap_h_misses': 0,
            'trap_e_hits': 0, 'trap_e_misses': 0
        }

        path = "./output/field/{}/".format(self.name)

        # Weighting Potential is universal for all irradiation flux
        # TODO: Net Doping should be here too
        WeightingPotentialFiles = []
        for contact in read_out_contact:
            WeightingPotentialFiles.append(path + "weightingfield/{}/Potential_{}V.pkl".format(contact['name'], 1))

        if irradiation_flux != 0:
            path = "./output/field/{}/{}/".format(self.name, irradiation_flux)

        DopingFile = None
        doping_file_pattern = re.compile(r'^NetDoping_(-?\d+\.?\d*)V\.pkl$')
        for filename in os.listdir(path):
            if doping_file_pattern.match(filename):
                DopingFile = path + filename
                # example: DopingFile = path + "NetDoping_0V.pkl"
                break

        PotentialFile = self._resolve_voltage_pickle(path, "Potential", self.voltage)
        TrappingRate_pFile = self._resolve_voltage_pickle(path, "TrappingRate_p", self.voltage)
        TrappingRate_nFile = self._resolve_voltage_pickle(path, "TrappingRate_n", self.voltage)

        self.set_doping(DopingFile) #self.Doping
        self.set_potential(PotentialFile) #self.Potential, self.x_efield, self.y_efield, self.z_efield
        self.set_trap_p(TrappingRate_pFile) # self.TrappingRate_p
        self.set_trap_n(TrappingRate_nFile) # self.TrappingRate_n
        self.set_w_p(WeightingPotentialFiles) #self.weighting_potential[]

        missing_models = []
        if not hasattr(self, "Doping"):
            missing_models.append(f"Doping ({DopingFile})")
        if not hasattr(self, "Potential"):
            missing_models.append(f"Potential ({PotentialFile})")
        if not hasattr(self, "TrappingRate_p"):
            missing_models.append(f"TrappingRate_p ({TrappingRate_pFile})")
        if not hasattr(self, "TrappingRate_n"):
            missing_models.append(f"TrappingRate_n ({TrappingRate_nFile})")
        if not hasattr(self, "WeightingPotential"):
            missing_models.append("WeightingPotential")
        if missing_models:
            raise FileNotFoundError(
                "Failed to initialize field models for {}: {}".format(
                    self.name, ", ".join(missing_models)
                )
            )

        if self.interpolation_bins is not None:
            logger.info("DevsimField interpolation bins override for %s: %s", self.name, self.interpolation_bins)
        
        logger.info(f"DevsimField initialization complete, resolution: {self.resolution} um")

    def _build_interpolation_cache_path(self, source_path, dimension, bins=None):
        if dimension < 2 or source_path is None:
            return None

        try:
            stat_result = os.stat(source_path)
        except OSError:
            return None

        axes = ('x', 'y') if dimension == 2 else ('x', 'y', 'z')
        if isinstance(bins, dict):
            bin_label = "_".join(f"{axis}{bins.get(axis, 'd')}" for axis in axes)
        elif bins is None:
            bin_label = "default"
        else:
            bin_label = f"all{bins}"

        base_name = os.path.basename(source_path)
        cache_name = (
            f".{base_name}.interp{dimension}d_v2_{bin_label}_"
            f"{stat_result.st_size}_{stat_result.st_mtime_ns}.npz"
        )
        return os.path.join(os.path.dirname(source_path), cache_name)

    def _get_auxiliary_interpolation_bins(self, dimension):
        if dimension < 2:
            return None

        if dimension == 2:
            clamp_default = {'x': 120, 'y': 120}
        else:
            clamp_default = {'x': 30, 'y': 30, 'z': 30}

        if not isinstance(self.interpolation_bins, dict):
            return clamp_default

        bins = {}
        for axis, clamp in clamp_default.items():
            raw_value = self.interpolation_bins.get(axis, clamp)
            try:
                bins[axis] = max(2, min(int(raw_value), clamp))
            except (TypeError, ValueError):
                bins[axis] = clamp
        return bins

    def _resolve_voltage_pickle(self, path, prefix, voltage):
        exact_path = os.path.join(path, f"{prefix}_{voltage}V.pkl")
        if os.path.exists(exact_path):
            return exact_path

        try:
            target_voltage = float(voltage)
        except (TypeError, ValueError):
            return exact_path

        pattern = re.compile(r"^{}_(-?\d+(?:\.\d+)?)V\.pkl$".format(re.escape(prefix)))
        for filename in os.listdir(path):
            match = pattern.match(filename)
            if not match:
                continue
            try:
                file_voltage = float(match.group(1))
            except ValueError:
                continue
            if math.isclose(file_voltage, target_voltage, rel_tol=0.0, abs_tol=1e-9):
                return os.path.join(path, filename)

        return exact_path

    def _extract_model_bounds_um(self, field_data):
        try:
            points = np.asarray(field_data.get("points", []), dtype=np.float64)
            dimension = int(field_data.get("metadata", {}).get("dimension", self.dimension))
        except Exception:
            return {}

        if points.size == 0:
            return {}

        if dimension == 1:
            reshaped = points.reshape(-1, 1)
            axes = ("z",)
        else:
            reshaped = points.reshape(-1, points.shape[-1])
            if dimension == 2:
                axes = ("x", "y") if self.is_plugin else ("z", "x")
            elif dimension == 3:
                axes = ("x", "y", "z")
            else:
                return {}

        bounds = {}
        for idx, axis in enumerate(axes):
            axis_values = reshaped[:, idx] * 1e4
            bounds[axis] = (float(np.min(axis_values)), float(np.max(axis_values)))
        return bounds

    def _clip_position_to_model_bounds(self, x, y, z, bounds_um):
        if not bounds_um:
            return x, y, z

        values = {"x": float(x), "y": float(y), "z": float(z)}
        for axis in ("x", "y", "z"):
            if axis not in bounds_um:
                continue

            lower, upper = bounds_um[axis]
            resolution = float(self.resolution.get(axis, 0.0))
            tolerance = max(resolution * 0.6, 1e-6)
            edge_offset = max(resolution * 1e-3, 1e-6)
            value = values[axis]

            if value < lower and lower - value <= tolerance:
                values[axis] = lower + edge_offset
            elif value > upper and value - upper <= tolerance:
                values[axis] = upper - edge_offset

        return values["x"], values["y"], values["z"]

    def set_doping(self, DopingFile):
        start_time = time.time()
        try:
            with open(DopingFile,'rb') as file:
                DopingNotUniform=pickle.load(file)
                print("Doping file loaded for {}".format(self.name))
                if DopingNotUniform['metadata']['dimension'] < self.dimension:
                    print("Doping dimension not match")
                    return
        except FileNotFoundError:
            print("Doping file not found at {}, please run field simulation first".format(DopingFile))
            print("or manually set the doping file")
            return
        interpolation_bins = self._get_auxiliary_interpolation_bins(DopingNotUniform['metadata']['dimension'])

        if DopingNotUniform['metadata']['dimension'] == 1:
            DopingUniform = get_common_interpolate_1d(DopingNotUniform)
        elif DopingNotUniform['metadata']['dimension'] == 2:
            DopingUniform = get_common_interpolate_2d(
                DopingNotUniform,
                interpolation_bins,
                cache_path=self._build_interpolation_cache_path(
                    DopingFile,
                    DopingNotUniform['metadata']['dimension'],
                    interpolation_bins
                )
            )
        elif DopingNotUniform['metadata']['dimension'] == 3:
            DopingUniform = get_common_interpolate_3d(
                DopingNotUniform,
                interpolation_bins,
                cache_path=self._build_interpolation_cache_path(
                    DopingFile,
                    DopingNotUniform['metadata']['dimension'],
                    interpolation_bins
                )
            )

        self.Doping = DopingUniform
        logger.info("Doping interpolation ready for %s in %.2fs", self.name, time.time() - start_time)

    def set_potential(self, PotentialFile):
        start_time = time.time()
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
            PotentialUniform = get_common_interpolate_2d(
                PotentialNotUniform,
                self.interpolation_bins,
                cache_path=self._build_interpolation_cache_path(
                    PotentialFile,
                    PotentialNotUniform['metadata']['dimension'],
                    self.interpolation_bins
                )
            )
        elif PotentialNotUniform['metadata']['dimension'] == 3:
            PotentialUniform = get_common_interpolate_3d(
                PotentialNotUniform,
                self.interpolation_bins,
                cache_path=self._build_interpolation_cache_path(
                    PotentialFile,
                    PotentialNotUniform['metadata']['dimension'],
                    self.interpolation_bins
                )
            )

        self.Potential = PotentialUniform
        self.potential_bounds_um = self._extract_model_bounds_um(PotentialNotUniform)
        if PotentialNotUniform['metadata']['dimension'] == 3:
            self._potential_points = np.asarray(PotentialNotUniform.get("points", []), dtype=np.float64)
            self._potential_values = np.asarray(PotentialNotUniform.get("values", []), dtype=np.float64)
            self._potential_point_tree = None
        logger.info("Potential interpolation ready for %s in %.2fs", self.name, time.time() - start_time)

    def set_w_p(self, WeightingPotentialFiles):
        self.WeightingPotential = []
        self.weighting_bounds_um = []
        for i in range(len(self.read_out_contact)):
            start_time = time.time()
            WeightingPotentialFile = self._resolve_voltage_pickle(
                os.path.dirname(WeightingPotentialFiles[i]),
                "Potential",
                1
            )
            try:
                with open(WeightingPotentialFile,'rb') as file:
                    WeightingPotentialNotUniform=pickle.load(file)
                    print("Weighting Potential file loaded for {} at electrode {}".format(self.name, i+1))
                    if WeightingPotentialNotUniform['metadata']['dimension'] < self.dimension:
                        print("Weighting Potential dimension not match")
                        return
            except FileNotFoundError:
                print("Weighting Potential file not found at {}, please run field simulation first".format(WeightingPotentialFile))
                print("or manually set the Weighting Potential file")
                return
            
            if WeightingPotentialNotUniform['metadata']['dimension'] == 1:
                WeightingPotentialUniform = get_common_interpolate_1d(WeightingPotentialNotUniform)
            elif WeightingPotentialNotUniform['metadata']['dimension'] == 2:
                WeightingPotentialUniform = get_common_interpolate_2d(
                    WeightingPotentialNotUniform,
                    self.interpolation_bins,
                    cache_path=self._build_interpolation_cache_path(
                        WeightingPotentialFile,
                        WeightingPotentialNotUniform['metadata']['dimension'],
                        self.interpolation_bins
                    )
                )
            elif WeightingPotentialNotUniform['metadata']['dimension'] == 3:
                WeightingPotentialUniform = get_common_interpolate_3d(
                    WeightingPotentialNotUniform,
                    self.interpolation_bins,
                    cache_path=self._build_interpolation_cache_path(
                        WeightingPotentialFile,
                        WeightingPotentialNotUniform['metadata']['dimension'],
                        self.interpolation_bins
                    )
                )

            self.WeightingPotential.append(WeightingPotentialUniform)
            self.weighting_bounds_um.append(self._extract_model_bounds_um(WeightingPotentialNotUniform))
            logger.info(
                "Weighting potential interpolation ready for %s electrode %d in %.2fs",
                self.name,
                i + 1,
                time.time() - start_time
            )
    
    def set_trap_p(self, TrappingRate_pFile):
        start_time = time.time()
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
        interpolation_bins = self._get_auxiliary_interpolation_bins(TrappingRate_pNotUniform['metadata']['dimension'])

        if TrappingRate_pNotUniform['metadata']['dimension'] == 1:
            TrappingRate_pUniform = get_common_interpolate_1d(TrappingRate_pNotUniform)
        elif TrappingRate_pNotUniform['metadata']['dimension'] == 2:
            TrappingRate_pUniform = get_common_interpolate_2d(
                TrappingRate_pNotUniform,
                interpolation_bins,
                cache_path=self._build_interpolation_cache_path(
                    TrappingRate_pFile,
                    TrappingRate_pNotUniform['metadata']['dimension'],
                    interpolation_bins
                )
            )
        elif TrappingRate_pNotUniform['metadata']['dimension'] == 3:
            TrappingRate_pUniform = get_common_interpolate_3d(
                TrappingRate_pNotUniform,
                interpolation_bins,
                cache_path=self._build_interpolation_cache_path(
                    TrappingRate_pFile,
                    TrappingRate_pNotUniform['metadata']['dimension'],
                    interpolation_bins
                )
            )

        self.TrappingRate_p = TrappingRate_pUniform
        logger.info("Hole trapping interpolation ready for %s in %.2fs", self.name, time.time() - start_time)
    
    def set_trap_n(self, TrappingRate_nFile):
        start_time = time.time()
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
        interpolation_bins = self._get_auxiliary_interpolation_bins(TrappingRate_nNotUniform['metadata']['dimension'])

        if TrappingRate_nNotUniform['metadata']['dimension'] == 1:
            TrappingRate_nUniform = get_common_interpolate_1d(TrappingRate_nNotUniform)
        elif TrappingRate_nNotUniform['metadata']['dimension'] == 2:
            TrappingRate_nUniform = get_common_interpolate_2d(
                TrappingRate_nNotUniform,
                interpolation_bins,
                cache_path=self._build_interpolation_cache_path(
                    TrappingRate_nFile,
                    TrappingRate_nNotUniform['metadata']['dimension'],
                    interpolation_bins
                )
            )
        elif TrappingRate_nNotUniform['metadata']['dimension'] == 3:
            TrappingRate_nUniform = get_common_interpolate_3d(
                TrappingRate_nNotUniform,
                interpolation_bins,
                cache_path=self._build_interpolation_cache_path(
                    TrappingRate_nFile,
                    TrappingRate_nNotUniform['metadata']['dimension'],
                    interpolation_bins
                )
            )

        self.TrappingRate_n = TrappingRate_nUniform
        logger.info("Electron trapping interpolation ready for %s in %.2fs", self.name, time.time() - start_time)
        
    # 3D pickle points are saved in physical detector order (x, y, z).
    # 2D planar fields still use the legacy (z, x) convention.

    def _get_doping(self, x, y, z):
        '''
            input: position in um
            output: doping in cm^-3
        '''
        x, y, z = x/1e4, y/1e4, z/1e4 # um to cm
        if self.dimension == 1:
            return self.Doping(z)
        elif self.dimension == 2:
            if self.is_plugin:
                return self.Doping(x, y)  # 2D插件使用x,y
            else:
                return self.Doping(z, x)
        elif self.dimension == 3:
            return self.Doping(x, y, z)
    
    def _get_potential(self, x, y, z):
        '''
            input: position in um
            output: potential in V
        '''
        x, y, z = x/1e4, y/1e4, z/1e4 # um to cm
        if self.dimension == 1:
            return self.Potential(z)
        elif self.dimension == 2:
            if self.is_plugin:
                return self.Potential(x, y)  # 2D插件使用x,y
            else:
                return self.Potential(z, x)
        elif self.dimension == 3:
            return self.Potential(x, y, z)
    
    def _get_e_field(self, x, y, z):
        '''
            input: position in um
            output: intensity in V/cm
        ''' 
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
            nabla_U = calculate_gradient(self.Potential, ['x', 'y', 'z'], [x, y, z])
            E_x = -1 * nabla_U[0]
            E_y = -1 * nabla_U[1]
            E_z = -1 * nabla_U[2]
            return (E_x, E_y, E_z)

    def _get_point_cloud_e_field(self, x, y, z, neighbors=128):
        if self.dimension != 3 or self._potential_points is None or self._potential_values is None:
            return self._get_e_field(x, y, z)

        points = self._potential_points
        values = self._potential_values
        if points.size == 0 or values.size == 0:
            return self._get_e_field(x, y, z)

        if self._potential_point_tree is None:
            self._potential_point_tree = cKDTree(points)

        query = np.array([x / 1e4, y / 1e4, z / 1e4], dtype=np.float64)
        neighbor_count = max(8, min(int(neighbors), len(points)))
        distances, indices = self._potential_point_tree.query(query, k=neighbor_count)
        distances = np.asarray(distances, dtype=np.float64).reshape(-1)
        indices = np.asarray(indices).reshape(-1)

        local_points = points[indices]
        local_values = values[indices]
        finite_mask = np.isfinite(local_points).all(axis=1) & np.isfinite(local_values)
        local_points = local_points[finite_mask]
        local_values = local_values[finite_mask]
        distances = distances[finite_mask]
        if len(local_points) < 8:
            return self._get_e_field(x, y, z)

        # TCAD point clouds can contain duplicated interface nodes. Collapsing
        # exact duplicates prevents zero-distance discontinuities from
        # dominating the local fit.
        duplicate_tolerance_cm = 1e-12
        rounded_points = np.round(local_points / duplicate_tolerance_cm).astype(np.int64)
        _, unique_indices = np.unique(rounded_points, axis=0, return_index=True)
        unique_indices.sort()
        local_points = local_points[unique_indices]
        local_values = local_values[unique_indices]
        distances = distances[unique_indices]
        if len(local_points) < 8:
            return self._get_e_field(x, y, z)

        design = np.column_stack((np.ones(len(local_points)), local_points - query))
        weights = 1.0 / np.maximum(distances, 1e-7)
        weighted_design = design * weights[:, np.newaxis]
        weighted_values = local_values * weights
        try:
            coefficients, _, rank, _ = np.linalg.lstsq(weighted_design, weighted_values, rcond=None)
        except np.linalg.LinAlgError:
            return self._get_e_field(x, y, z)
        if rank < 4:
            return self._get_e_field(x, y, z)

        gradient = coefficients[1:]
        if not np.isfinite(gradient).all():
            return self._get_e_field(x, y, z)
        return (-float(gradient[0]), -float(gradient[1]), -float(gradient[2]))

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
            U_w = self.WeightingPotential[i](x, y, z)

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
        '''
            input: position in um
            output: electron trapping rate in s^-1     
        '''
        x, y, z = x/1e4, y/1e4, z/1e4 # um to cm
        if self.dimension == 1:
            return self.TrappingRate_n(z)
        
        elif self.dimension == 2:
            if self.is_plugin:
                return self.TrappingRate_n(x, y)  # 2D插件使用x,y
            else:
                return self.TrappingRate_n(z, x)
        
        elif self.dimension == 3:
            return self.TrappingRate_n(x, y, z)
    
    def _get_trap_h(self, x, y, z):
        '''
            input: position in um
            output: hole trapping rate in s^-1     
        '''
        x, y, z = x/1e4, y/1e4, z/1e4 # um to cm
        if self.dimension == 1:
            return self.TrappingRate_p(z)
        elif self.dimension == 2:
            if self.is_plugin:
                return self.TrappingRate_p(x, y)  # 2D插件使用x,y
            else:
                return self.TrappingRate_p(z, x)
        elif self.dimension == 3:
            return self.TrappingRate_p(x, y, z)

    # 缓存方法
    def get_e_field_cached(self, x, y, z):
        try:
            x, y, z = self._clip_position_to_model_bounds(x, y, z, self.potential_bounds_um)
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

    def get_gain_e_field_cached(self, x, y, z, method="point_lsq", neighbors=128, max_field=1.0e6):
        if method != "point_lsq" or self.dimension != 3:
            return self.get_e_field_cached(x, y, z)

        x, y, z = self._clip_position_to_model_bounds(x, y, z, self.potential_bounds_um)
        if not self._is_position_valid(x, y, z):
            return self._get_point_cloud_e_field(x, y, z, neighbors)

        key = (round(float(x), 3), round(float(y), 3), round(float(z), 3), int(neighbors), float(max_field))
        if key in self.gain_e_field_cache:
            self._cache_stats['gain_hits'] += 1
            return self.gain_e_field_cache[key]

        try:
            self._cache_stats['gain_misses'] += 1
            e_field = self._get_point_cloud_e_field(x, y, z, neighbors)
            if max_field > 0.0 and Vector(*e_field).get_length() > max_field:
                self._cache_stats['gain_fallbacks'] += 1
                e_field = self.get_e_field_cached(x, y, z)
        except Exception as e:
            self._cache_stats['gain_errors'] += 1
            logger.warning(f"failed when getting gain field ({x:.1f}, {y:.1f}, {z:.1f}): {e}")
            e_field = self.get_e_field_cached(x, y, z)
        if e_field is not None:
            self.gain_e_field_cache[key] = e_field
        return e_field
    
    def get_doping_cached(self, x, y, z):
        try:
            x, y, z = self._clip_position_to_model_bounds(x, y, z, self.potential_bounds_um)
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
            bounds_um = self.weighting_bounds_um[n] if 0 <= n < len(self.weighting_bounds_um) else {}
            x, y, z = self._clip_position_to_model_bounds(x, y, z, bounds_um)
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
            x, y, z = self._clip_position_to_model_bounds(x, y, z, self.potential_bounds_um)
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
            x, y, z = self._clip_position_to_model_bounds(x, y, z, self.potential_bounds_um)
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
            self._get_index_axis(z, 'z')
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
        total = self._cache_stats['hits'] + self._cache_stats['misses'] + self._cache_stats['errors']
        hit_rate = self._cache_stats['hits'] / total if total > 0 else 0
        
        # 陷阱率缓存统计
        trap_h_total = self._cache_stats['trap_h_hits'] + self._cache_stats['trap_h_misses']
        trap_h_hit_rate = self._cache_stats['trap_h_hits'] / trap_h_total if trap_h_total > 0 else 0
        
        trap_e_total = self._cache_stats['trap_e_hits'] + self._cache_stats['trap_e_misses']
        trap_e_hit_rate = self._cache_stats['trap_e_hits'] / trap_e_total if trap_e_total > 0 else 0
        
        return {
            'hits': self._cache_stats['hits'],
            'misses': self._cache_stats['misses'],
            'errors': self._cache_stats['errors'],
            'fallbacks': self._cache_stats['fallbacks'],
            'hit_rate': hit_rate,
            'total_entries': len(self.e_field_cache),
            'gain_hits': self._cache_stats['gain_hits'],
            'gain_misses': self._cache_stats['gain_misses'],
            'gain_fallbacks': self._cache_stats['gain_fallbacks'],
            'gain_errors': self._cache_stats['gain_errors'],
            'gain_entries': len(self.gain_e_field_cache),
            'trap_h_hits': self._cache_stats['trap_h_hits'],
            'trap_h_misses': self._cache_stats['trap_h_misses'],
            'trap_h_hit_rate': trap_h_hit_rate,
            'trap_h_entries': len(self.trap_h_cache),
            'trap_e_hits': self._cache_stats['trap_e_hits'],
            'trap_e_misses': self._cache_stats['trap_e_misses'],
            'trap_e_hit_rate': trap_e_hit_rate,
            'trap_e_entries': len(self.trap_e_cache)
        }
    
    def clear_cache(self):
        """清空所有缓存"""
        self.e_field_cache.clear()
        self.gain_e_field_cache.clear()
        self.doping_cache.clear()
        self.w_p_cache.clear()
        self.trap_h_cache.clear()
        self.trap_e_cache.clear()
        logger.info("所有缓存已清空")

if __name__ == "__main__":
    pass
