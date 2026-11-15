#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
@File    :   devsim_field.py
@Time    :   2025/11/11
@Author  :   Henry Stone, Sen Zhao, Dai Zhong
@Version :   3.0
'''

import json
import pickle
import os
import logging
import math
import re
from pathlib import Path

import numpy as np
import ROOT
from scipy.spatial import Delaunay
from scipy.spatial import cKDTree
from ..current.model import Material
from .assets import field_pickle_path
from .gradient import gradient
from .interpolation import interpolate_1d
from .interpolation import interpolate_2d
from .interpolation import interpolate_3d
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
    def __init__(self, device_name, voltage, read_out_contact, irradiation_flux=0,
                 bounds=None, resolution=None, field_set="default", field_directory=None,
                 interpolation_bins=None):
        self.name = device_name
        self.voltage = voltage
        self.irradiation_flux = irradiation_flux
        self.read_out_contact = read_out_contact
        self.interpolation_bins = interpolation_bins

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

        explicit_directory = field_directory is not None
        path = str(
            Path(field_directory)
            if explicit_directory
            else project_path("field", field_set)
        ) + os.sep

        # The weighting potential of each read-out electrode at the bias of the field.
        WeightingPotentialFiles = []
        for contact in read_out_contact:
            WeightingPotentialFiles.append(path + "weightingfield/{}/Potential_{}V.pkl".format(contact['name'], voltage))

        # TODO: Select assets only through an explicit field set.
        if irradiation_flux != 0 and field_set == "default" and not explicit_directory:
            path = str(project_path("field", str(irradiation_flux))) + os.sep

        # The device axis along each coordinate of the stored points.
        record = os.path.join(path, "run.json")
        if not os.path.exists(record):
            raise FileNotFoundError(
                "{} is missing: solve the field again, or write the axes of its "
                'files there, for example {{"axes": ["z"]}}'.format(record)
            )
        with open(record) as file:
            self.axes = tuple(json.load(file)["axes"])

        # 初始化缓存相关属性
        if len(self.axes) == 1:
            resolution_default = resolution_default_1d
        elif self.axes == ("x", "y"):
            resolution_default = resolution_default_plugin_2d
        elif len(self.axes) == 2:
            resolution_default = resolution_default_2d
        else:
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
        
        DopingFile = None
        doping_file_pattern = re.compile(r'^NetDoping_(-?\d+\.?\d*)V\.pkl$')
        for filename in os.listdir(path):
            if doping_file_pattern.match(filename):
                DopingFile = path + filename
                # example: DopingFile = path + "NetDoping_0V.pkl"
                break

        PotentialFile = field_pickle_path(path, "Potential", self.voltage)
        TrappingRate_pFile = field_pickle_path(path, "TrappingRate_p", self.voltage)
        TrappingRate_nFile = field_pickle_path(path, "TrappingRate_n", self.voltage)
        ConductiveFile = field_pickle_path(path, "Conductive", self.voltage)

        self.set_doping(DopingFile) #self.Doping
        self.set_potential(PotentialFile) #self.Potential, self.x_efield, self.y_efield, self.z_efield
        self.set_trap_p(TrappingRate_pFile) # self.TrappingRate_p
        self.set_trap_n(TrappingRate_nFile) # self.TrappingRate_n
        self.set_w_p(WeightingPotentialFiles) #self.weighting_potential[]
        self.set_conductive(ConductiveFile) # self.conductive_nodes, self.conductive_values
        
        logger.info(f"DevsimField initialization complete, resolution: {self.resolution} um")

    def _stored(self, file, what):
        """What one file of the field holds. A file that is missing, or that
        has fewer dimensions than the field, is an error that names it."""
        if file is None or not os.path.exists(file):
            raise FileNotFoundError(
                "the {} of {} at {} V is not solved: {} is missing".format(
                    what, self.name, self.voltage, file or "its file"
                )
            )
        with open(file, 'rb') as stream:
            stored = pickle.load(stream)
        if stored['metadata']['dimension'] < len(self.axes):
            raise ValueError(
                "the {} in {} has {} dimensions, the field has {}".format(
                    what, file, stored['metadata']['dimension'], len(self.axes)
                )
            )
        return stored

    def set_doping(self, DopingFile):
        DopingNotUniform = self._stored(DopingFile, "net doping")
        
        if DopingNotUniform['metadata']['dimension'] == 1:
            DopingUniform = interpolate_1d(DopingNotUniform)
        elif DopingNotUniform['metadata']['dimension'] == 2:
            DopingUniform = interpolate_2d(DopingNotUniform)
        elif DopingNotUniform['metadata']['dimension'] == 3:
            DopingUniform = interpolate_3d(
                DopingNotUniform, bins=self.interpolation_bins
            )

        self.Doping = DopingUniform

    def set_potential(self, PotentialFile):
        PotentialNotUniform = self._stored(PotentialFile, "potential")
        
        if PotentialNotUniform['metadata']['dimension'] == 1:
            PotentialUniform = interpolate_1d(PotentialNotUniform)
        elif PotentialNotUniform['metadata']['dimension'] == 2:
            PotentialUniform = interpolate_2d(PotentialNotUniform)
        elif PotentialNotUniform['metadata']['dimension'] == 3:
            PotentialUniform = interpolate_3d(
                PotentialNotUniform, bins=self.interpolation_bins
            )

        self.Potential = PotentialUniform
        # The ends of the mesh along each of its axes, in cm.
        points = np.asarray(PotentialNotUniform['points'], dtype=float).reshape(
            len(PotentialNotUniform['points']), -1
        )
        self.potential_ranges = list(zip(points.min(axis=0).tolist(), points.max(axis=0).tolist()))
        self.potential_points = points

    def set_w_p(self, WeightingPotentialFiles):
        self.WeightingPotential = []
        for i in range(len(self.read_out_contact)):
            WeightingPotentialFile = field_pickle_path(
                os.path.dirname(WeightingPotentialFiles[i]), "Potential", self.voltage
            )
            WeightingPotentialNotUniform = self._stored(
                WeightingPotentialFile,
                "weighting potential of {}".format(self.read_out_contact[i]['name']),
            )
            
            if WeightingPotentialNotUniform['metadata']['dimension'] == 1:
                WeightingPotentialUniform = interpolate_1d(WeightingPotentialNotUniform)
            elif WeightingPotentialNotUniform['metadata']['dimension'] == 2:
                WeightingPotentialUniform = interpolate_2d(WeightingPotentialNotUniform)
            elif WeightingPotentialNotUniform['metadata']['dimension'] == 3:
                WeightingPotentialUniform = interpolate_3d(
                    WeightingPotentialNotUniform, bins=self.interpolation_bins
                )

            self.WeightingPotential.append(WeightingPotentialUniform)
    
    def set_trap_p(self, TrappingRate_pFile):
        TrappingRate_pNotUniform = self._stored(TrappingRate_pFile, "hole trapping rate")
        
        if TrappingRate_pNotUniform['metadata']['dimension'] == 1:
            TrappingRate_pUniform = interpolate_1d(TrappingRate_pNotUniform)
        elif TrappingRate_pNotUniform['metadata']['dimension'] == 2:
            TrappingRate_pUniform = interpolate_2d(TrappingRate_pNotUniform)
        elif TrappingRate_pNotUniform['metadata']['dimension'] == 3:
            TrappingRate_pUniform = interpolate_3d(
                TrappingRate_pNotUniform, bins=self.interpolation_bins
            )

        self.TrappingRate_p = TrappingRate_pUniform
    
    def set_trap_n(self, TrappingRate_nFile):
        TrappingRate_nNotUniform = self._stored(TrappingRate_nFile, "electron trapping rate")
        
        if TrappingRate_nNotUniform['metadata']['dimension'] == 1:
            TrappingRate_nUniform = interpolate_1d(TrappingRate_nNotUniform)
        elif TrappingRate_nNotUniform['metadata']['dimension'] == 2:
            TrappingRate_nUniform = interpolate_2d(TrappingRate_nNotUniform)
        elif TrappingRate_nNotUniform['metadata']['dimension'] == 3:
            TrappingRate_nUniform = interpolate_3d(
                TrappingRate_nNotUniform, bins=self.interpolation_bins
            )

        self.TrappingRate_n = TrappingRate_nUniform
        

    def set_conductive(self, ConductiveFile):
        stored = self._stored(ConductiveFile, "conductive part")
        points = np.asarray(stored['points'], dtype=float).reshape(len(stored['points']), -1)
        self.conductive_nodes = cKDTree(points)
        self.conductive_values = np.asarray(stored['values']) > 0.5
        # The cells of the mesh: the intervals between its nodes in one
        # dimension, the simplices that join its nodes otherwise.
        if points.shape[1] == 1:
            self.conductive_order = np.argsort(points[:, 0])
            self.conductive_line = points[self.conductive_order, 0]
        else:
            self.conductive_cells = Delaunay(points)

    def _along_axes(self, x, y, z):
        """A position, as the coordinates the field files are stored in."""
        position = {"x": x, "y": y, "z": z}
        return [position[axis] for axis in self.axes]

    def get_doping(self, x, y, z):
        """
        input: position in um
        output: doping in cm^-3
        """
        x, y, z = x/1e4, y/1e4, z/1e4 # um to cm
        return self.Doping(*self._along_axes(x, y, z))
    
    def get_potential(self, x, y, z):
        """
        input: position in um
        output: potential in V
        """
        x, y, z = x/1e4, y/1e4, z/1e4 # um to cm
        return self.Potential(*self._along_axes(x, y, z))
    
    def get_e_field(self, x, y, z):
        """
        input: position in um
        output: intensity in V/cm
        """ 
        x, y, z = x / 1e4, y / 1e4, z / 1e4  # um to cm

        nabla_U = gradient(self.Potential, self._along_axes(x, y, z), self.potential_ranges)
        E = {axis: -1 * component for axis, component in zip(self.axes, nabla_U)}
        return (E.get("x", 0), E.get("y", 0), E.get("z", 0))

    def get_w_p(self, x, y, z, i): # used in cal current
        x, y, z = x/1e4, y/1e4, z/1e4 # um to cm
        U_w = self.WeightingPotential[i](*self._along_axes(x, y, z))

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

    
    def get_conductive(self, x, y, z):
        """
        input: position in um
        output: whether the device conducts there at the bias of the field:
        every node of the cell of the mesh that holds the position does, as
        in the weighting field, where an edge conducts when both its nodes
        do; a position outside the mesh is answered by the nearest node
        """
        x, y, z = x/1e4, y/1e4, z/1e4 # um to cm
        place = self._along_axes(x, y, z)
        if len(place) == 1:
            after = int(np.searchsorted(self.conductive_line, place[0]))
            if 0 < after < len(self.conductive_line):
                ends = self.conductive_order[after - 1 : after + 1]
                return bool(self.conductive_values[ends].all())
        else:
            cell = int(self.conductive_cells.find_simplex(place))
            if cell >= 0:
                return bool(self.conductive_values[self.conductive_cells.simplices[cell]].all())
        return bool(self.conductive_values[self.conductive_nodes.query(place)[1]])

    def get_trap_e(self, x, y, z):
        """
        input: position in um
        output: electron trapping rate in s^-1
        """
        x, y, z = x/1e4, y/1e4, z/1e4 # um to cm
        return self.TrappingRate_n(*self._along_axes(x, y, z))

    def get_trap_h(self, x, y, z):
        """
        input: position in um
        output: hole trapping rate in s^-1
        """
        x, y, z = x/1e4, y/1e4, z/1e4 # um to cm
        return self.TrappingRate_p(*self._along_axes(x, y, z))

    # 缓存方法
    _planar_gain = None

    def planar_gain(self, my_d):
        """Gain of a planar device for the pairs made in its bulk: on the side
        of the gain layer that is away from the face the layer lies at."""
        self._integrate_planar_gain(my_d)
        return self._planar_gain

    def planar_gain_at(self, my_d, z):
        """Gain of a planar device for a pair made at the depth z in um: how
        many more pairs it becomes. The pairs made in front of the gain layer
        send the other carrier through it, and have another gain."""
        self._integrate_planar_gain(my_d)
        nodes, log_growth, det = self._planar_gain_profile
        return float(np.exp(np.interp(z * 1e-4, nodes, log_growth)) / (1 - det) - 1)

    def _integrate_planar_gain(self, my_d):
        """One integration through the whole depth, along the line through the
        middle of the device."""
        # gain(z) = K(z) / {1 - int[alpha_p * K dz]} - 1
        # K(z) = exp{int_b^z[(alpha_n - alpha_p) dz]}
        # b is the face the electrons leave by; a pair made there sends its
        # hole through the device, a pair made at the other face its electron
        if self._planar_gain is not None:
            return
        if "z" not in self.axes:
            raise ValueError(
                "the field of {} is stored along {}, without the depth z: it has no planar gain".format(
                    self.name, self.axes
                )
            )
        cal_coefficient = Material(my_d.material, avalanche_model=my_d.avalanche_model).cal_coefficient

        # One field in every interval of the mesh, as the solve has it: the
        # potential is linear between two nodes.
        z = np.unique(self.potential_points[:, self.axes.index("z")])  # cm
        potential = np.array(
            [self.get_potential(0.5 * my_d.l_x, 0.5 * my_d.l_y, depth * 1e4) for depth in z], dtype=float
        )
        width = np.diff(z)
        field = -np.diff(potential) / width  # V/cm
        alpha_n = np.array([cal_coefficient(abs(E), -1, my_d.temperature) for E in field])
        alpha_p = np.array([cal_coefficient(abs(E), +1, my_d.temperature) for E in field])

        # The gain layer is where the field is strongest, and the multiplied
        # carriers start from the middle of that interval.
        strongest = int(np.argmax(np.abs(field)))
        self._planar_gain_depth = 0.5 * (z[strongest] + z[strongest + 1]) * 1e4  # um
        # Electrons drift against the field, holes along it.
        electrons_to_front = field[strongest] > 0
        # The carriers of the bulk that multiply are the ones that drift
        # towards the face the layer lies at.
        layer_at_front = z[strongest] + z[strongest + 1] <= z[0] + z[-1]
        self._planar_gain_carrier = -1 if electrons_to_front == layer_at_front else +1

        # K at the nodes, counted from the face the electrons leave by. Both
        # integrals are exact for a field that is constant in each interval.
        rate = alpha_n - alpha_p
        steps = rate * width
        if electrons_to_front:
            log_growth = np.concatenate([[0.0], np.cumsum(steps)])
            nearer = log_growth[:-1]
        else:
            log_growth = np.concatenate([np.cumsum(steps[::-1])[::-1], [0.0]])
            nearer = log_growth[1:]
        even = rate == 0
        within = np.where(even, width, np.expm1(steps) / np.where(even, 1.0, rate))
        det = float(np.sum(alpha_p * np.exp(nearer) * within))  # determinant of breakdown
        if det >= 1:
            raise ValueError(
                "{} breaks down at {} V: the breakdown integral is {:.4g}, not below 1".format(
                    self.name, self.voltage, det
                )
            )

        # K at every node comes with the one integration
        self._planar_gain_profile = (z, log_growth, det)
        bulk = log_growth[-1] if layer_at_front else log_growth[0]
        self._planar_gain = float(np.exp(bulk) / (1 - det) - 1)

    def planar_gain_depth(self, my_d):
        """The depth in um that the carriers of the planar gain start from:
        the middle of the mesh interval where the field is strongest."""
        self.planar_gain(my_d)
        return self._planar_gain_depth

    def planar_gain_carrier(self, my_d):
        """The charge sign of the carriers that the planar gain multiplies:
        -1 for electrons, +1 for holes. They drift from the bulk into the gain layer."""
        self.planar_gain(my_d)
        return self._planar_gain_carrier

    def get_e_field_cached(self, x, y, z):
        try:
            if not self._is_position_valid(x, y, z):
                return self.get_e_field(x, y, z) # 不缓存异常位置的电场值，继承报错
                
            key_x, key_y, key_z = self._get_index_coords(x, y, z)
            key = (key_x, key_y, key_z)
            
            if key in self.e_field_cache:
                self._cache_stats['hits'] += 1
                return self.e_field_cache[key]
            else:
                self._cache_stats['misses'] += 1
                e_field = self.get_e_field(x, y, z)
                if e_field is not None:
                    self.e_field_cache[key] = e_field
                return e_field
                
        except Exception as e:
            self._cache_stats['errors'] += 1
            logger.warning(f"failed when getting field cache ({x:.1f}, {y:.1f}, {z:.1f}): {e}")
            return self.get_e_field(x, y, z) # 出错时不使用缓存，直接计算电场值，继承报错
    
    # TODO: Propagate invalid field data instead of returning physical zero values.
    def get_doping_cached(self, x, y, z):
        try:
            if not self._is_position_valid(x, y, z):
                return self.get_doping(x, y, z)
                
            key_x, key_y, key_z = self._get_index_coords(x, y, z)
            key = (key_x, key_y, key_z)
            
            if key in self.doping_cache:
                return self.doping_cache[key]
            else:
                doping = self.get_doping(x, y, z)
                if doping is not None:
                    self.doping_cache[key] = doping
                return doping
        except Exception as e:
            logger.warning(f"failed when getting doping cache ({x:.1f}, {y:.1f}, {z:.1f}): {e}")
            return 0.0  # 默认掺杂浓度
        
    def get_w_p_cached(self, x, y, z, n):
        try:
            if not self._is_position_valid(x, y, z):
                return self.get_w_p(x, y, z, n)
            key_x, key_y, key_z = self._get_index_coords(x, y, z)
            key = (key_x, key_y, key_z, n)
            if key in self.w_p_cache:
                return self.w_p_cache[key]
            else:
                w_p = self.get_w_p(x, y, z, n)
                if w_p is not None:
                    self.w_p_cache[key] = w_p
                return w_p
        except Exception as e:
            logger.warning(f"failed when getting w_p cache ({x:.1f}, {y:.1f}, {z:.1f}, {n}): {e}")
            raise RuntimeError(
                f"failed when getting w_p cache ({x:.1f}, {y:.1f}, {z:.1f}, {n})"
            ) from e
    
    def get_trap_h_cached(self, x, y, z):
        """获取空穴陷阱率 - 带缓存"""
        try:
            if not self._is_position_valid(x, y, z):
                return self.get_trap_h(x, y, z)
                
            key_x, key_y, key_z = self._get_index_coords(x, y, z)
            key = (key_x, key_y, key_z)
            
            if key in self.trap_h_cache:
                self._cache_stats['trap_h_hits'] += 1
                return self.trap_h_cache[key]
            else:
                self._cache_stats['trap_h_misses'] += 1
                trap_rate = self.get_trap_h(x, y, z)
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
                return self.get_trap_e(x, y, z)
                
            key_x, key_y, key_z = self._get_index_coords(x, y, z)
            key = (key_x, key_y, key_z)
            
            if key in self.trap_e_cache:
                self._cache_stats['trap_e_hits'] += 1
                return self.trap_e_cache[key]
            else:
                self._cache_stats['trap_e_misses'] += 1
                trap_rate = self.get_trap_e(x, y, z)
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
