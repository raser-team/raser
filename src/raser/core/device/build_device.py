#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

"""
Description:  Define physical models for different materials
@Date       : 2025/11/11
@Author     : Yuhang Tan, Tao Yang, Chenxi Fu
@version    : 3.0
"""

import json
import math
from pathlib import Path

import numpy as np

from ..current.model import Material
from raser.supports.paths import component_file_path
from raser.supports.paths import work_root

EPSILON_0_F_PER_M = 8.8541878128e-12


def device_file(device_name):
    """The json of a device: a file, a folder holding device.json, or a name
    looked up in work/<name>/device.json and then in the device components."""
    candidate = Path(device_name).expanduser()
    if candidate.is_dir():
        return candidate / "device.json"
    if candidate.suffix or len(candidate.parts) > 1:
        return candidate
    project = work_root() / str(device_name) / "device.json"
    if project.is_file():
        return project
    return component_file_path("device", str(device_name))


class Detector:
    """
    Description:
    ---------
        Different types detectors parameters assignment.
    Parameters:
    ---------
    device_name : string
        name the device and define the device by device.json
    dimension : int
        the dimension of devsim mesh
    Modify:
    ---------
        2023/12/03
    """ 
    def __init__(self, device_name):
        device_json = device_file(device_name)
        with open(device_json) as f:
            self.device_dict = json.load(f)
        self.definition_path = device_json.resolve()

        # Every key of the json is an attribute of the same name.
        self.__dict__.update(self.device_dict)

        # Values that sit deeper in the json and are in common use.
        self.voltage = float(self.device_dict['bias']['voltage'])
        if "irradiation" in self.device_dict:
            self.irradiation_model = self.device_dict['irradiation']['irradiation_model']
            self.irradiation_flux = self.device_dict['irradiation']['irradiation_flux']
        else:
            self.irradiation_model = None
            self.irradiation_flux = 0
        self.mesher = self.device_dict.get('mesh', {}).get('mesher')

        # What follows from several keys.
        self.det_name = self.device_dict.get('det_name', device_json.stem)
        self.device = self.det_name
        self.region = self.det_name
        self.dimension = self.device_dict.get(
            'field_dimension', self.device_dict['default_dimension']
        )
        self.bound = {'x':(0, self.l_x), 'y':(0, self.l_y), 'z':(0, self.l_z)}
        self.input_doping = self._net_doping_cm3(self.doping, self.device_dict)

        if "strip" in self.det_model:
            self.x_ele_num = self.read_ele_num
            self.y_ele_num = 1
        elif "pixel" in self.det_model:
            self.read_ele_num = self.x_ele_num * self.y_ele_num
        else:
            self.x_ele_num = 1
            self.y_ele_num = 1
            self.read_ele_num = 1

        self.gain_rate = 0.0
        self.avalanche_model = self.device_dict.get('avalanche_model')
        self.avalanche_bond = self.device_dict.get('avalanche_bond')
        enable_gain = bool(
            self.device_dict.get(
                'enable_gain',
                "lgad" in self.det_model.lower() or 'gain_algorithm' in self.device_dict,
            )
        )
        if enable_gain and self.avalanche_model is None:
            raise ValueError("gain is enabled but `avalanche_model` is missing in detector settings")
        self.has_avalanche = self.avalanche_model is not None and enable_gain
        default_gain_algorithm = ( "local_path" if self.dimension == 3 else "planar_integral"
        )
        self.gain_algorithm = self.device_dict.get('gain_algorithm', default_gain_algorithm)
        if self.gain_algorithm not in ("planar_integral", "local_path"):
            raise ValueError("Unsupported gain_algorithm: {}".format(self.gain_algorithm))
        self.gain_pair_threshold = float(self.device_dict.get('gain_pair_threshold', 0.05))
        self.gain_max_carriers = int(self.device_dict.get('gain_max_carriers', 50000))
        self.local_gain_emit_slices = max(1, int(self.device_dict.get('local_gain_emit_slices', 1)))
        self.local_gain_integration_steps = max(1, int(self.device_dict.get('local_gain_integration_steps', 3)))

        if "planar" in self.det_model or "lgad" == self.det_model:
            self.p_x = self.device_dict['l_x']
            self.p_y = self.device_dict['l_y']

        if "strip" in self.det_model:
            self.p_x = self.device_dict['p_x']
            self.p_y = self.device_dict['l_y']

        if "pixel" in self.det_model:
            self.p_x = self.device_dict["p_x"]
            self.p_y = self.device_dict["p_y"]

        self.depletion_depth = float(self.device_dict.get("depletion_depth", self.l_z))
        self.capacitance = self._resolve_capacitance()

    def _readout_area_um2(self):
        det_model = self.det_model.lower()
        if "strip" in det_model:
            return float(self.p_x) * float(self.p_y)
        if "pixel" in det_model:
            return float(self.p_x) * float(self.p_y)
        return float(self.l_x) * float(self.l_y)

    @staticmethod
    def _net_doping_cm3(doping, device_dict):
        if "input_doping" in device_dict:
            return float(device_dict["input_doping"])
        try:
            donors = float(doping.get("Donors", 0.0))
            acceptors = float(doping.get("Acceptors", 0.0))
        except (TypeError, ValueError):
            return 1.0e12
        return donors - acceptors

    def _resolve_capacitance(self):
        if "capacitance_pF" in self.device_dict:
            return float(self.device_dict["capacitance_pF"])
        if "capacitance" in self.device_dict:
            return float(self.device_dict["capacitance"])

        if "3d" in self.det_model.lower():
            return None

        if self.depletion_depth <= 0:
            raise ValueError("depletion_depth must be positive")

        material = Material(self.material)
        area_um2 = self._readout_area_um2()
        capacitance_f = (
            EPSILON_0_F_PER_M
            * material.permittivity
            * area_um2
            * 1e-12
            / (self.depletion_depth * 1e-6)
        )
        return capacitance_f * 1e12

    def is_plugin(self):
        if ( "plugin" in self.det_model or "3d" in self.det_model or "3D" in self.det_model
        ):
            return True
        else:
            return False

    def gain_rate_cal(self, my_f):
        # gain = exp[K(d_gain)] / {1-int[alpha_minor * K(x) dx]}
        # K(x) = exp{int[(alpha_major - alpha_minor) dx]}

        # TODO: support non-uniform field in gain layer
        self.gain_rate = 0
        if not self.has_avalanche:
            self.gain_rate = 0
            return
        if self.gain_algorithm != "planar_integral":
            return
        if self.avalanche_bond is None:
            raise ValueError("planar_integral gain algorithm requires `avalanche_bond` in detector settings")
        
        cal_coefficient = Material(self.material, avalanche_model=self.avalanche_model).cal_coefficient

        n = 1001
        if "ilgad" in self.det_model:
            z_list = np.linspace(self.avalanche_bond * 1e-4, self.l_z, n) # in cm
        else:
            z_list = np.linspace(0, self.avalanche_bond * 1e-4, n) # in cm
        alpha_n_list = np.zeros(n)
        alpha_p_list = np.zeros(n)
        for i in range(n):
            Ex,Ey,Ez = my_f._get_e_field(0.5*self.l_x,0.5*self.l_y,z_list[i] * 1e4) # in V/cm, get original field to improve accuracy
            E_field = math.sqrt(Ex * Ex + Ey * Ey + Ez * Ez)
            alpha_n = cal_coefficient(E_field, -1, self.temperature)
            alpha_p = cal_coefficient(E_field, +1, self.temperature)
            alpha_n_list[i] = alpha_n
            alpha_p_list[i] = alpha_p

        if my_f._get_e_field(0, 0, self.avalanche_bond)[2] > 0:
            alpha_major_list = alpha_n_list # multiplication contributed mainly by electrons in conventional Si LGAD
            alpha_minor_list = alpha_p_list
        else:
            alpha_major_list = alpha_p_list # multiplication contributed mainly by holes in conventional SiC LGAD
            alpha_minor_list = alpha_n_list

        # the integral supports iLGAD as well
        
        diff_list = alpha_major_list - alpha_minor_list
        int_alpha_list = np.zeros(n-1)

        for i in range(1,n):
            int_alpha = 0
            for j in range(i):
                int_alpha += (
                    (diff_list[j] + diff_list[j+1]) * (z_list[j+1] - z_list[j]) /2
                )
            int_alpha_list[i-1] = int_alpha
        exp_list = np.exp(int_alpha_list)

        det = 0 # determinant of breakdown
        for i in range(0,n-1):
            average_alpha_minor = (alpha_minor_list[i] + alpha_minor_list[i+1])/2
            det_derivative = average_alpha_minor * exp_list[i]
            det += det_derivative*(z_list[i+1]-z_list[i])        
        if det>1:
            print("determinant=%s, larger than 1, detector break down", det)
            raise(ValueError)
        
        self.gain_rate = exp_list[n-2]/(1-det) -1

if __name__ == "__main__":
    import sys
    Detector(sys.argv[1])
