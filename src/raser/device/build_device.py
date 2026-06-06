#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

'''
Description:  Define physical models for different materials  
@Date       : 2025/11/11 
@Author     : Yuhang Tan, Tao Yang, Chenxi Fu
@version    : 3.0
'''

import json
import os

import numpy as np

from ..current.model import Material
from ..util.math import Vector

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
        self.det_name = device_name
        device_json = os.getenv("RASER_SETTING_PATH")+"/detector/" + device_name + ".json"
        with open(device_json) as f:
            self.device_dict = json.load(f)
        self.field_source = self.device_dict.get('field_source', device_name)
        self.device = self.field_source
        self.region = self.field_source
        self.dimension = self.device_dict['default_dimension']

        self.l_x = self.device_dict['l_x'] 
        self.l_y = self.device_dict["l_y"]  
        self.l_z = self.device_dict["l_z"] 
        self.bound = {'x':(0, self.l_x), 'y':(0, self.l_y), 'z':(0, self.l_z)}
        
        self.voltage = float(self.device_dict['bias']['voltage'])
        self.temperature = self.device_dict['temperature']
        self.material = self.device_dict['material']

        self.det_model = self.device_dict['det_model']
        self.doping = self.device_dict['doping']
        self.read_out_contact = self.device_dict["read_out_contact"]
        if "irradiation" in self.device_dict:
            self.irradiation_model = self.device_dict['irradiation']['irradiation_model']
            self.irradiation_flux = self.device_dict['irradiation']['irradiation_flux']
        else:
            self.irradiation_model = None
            self.irradiation_flux = 0

        if "cross_talk" in self.device_dict:
            self.cross_talk = self.device_dict['cross_talk']
        else:
            self.cross_talk = None

        self.g4experiment = self.device_dict['g4experiment']
        self.amplifier = self.device_dict['amplifier']
        self.daq = self.device_dict['daq']

        if "mesh" in self.device_dict:
            try:
                self.mesher = self.device_dict['mesh']['mesher']
            except (TypeError, ValueError, KeyError):
                self.mesher = None
        else:
            self.mesher = None
        if "vector_delta_t" in self.device_dict:
            try:
                self.vector_delta_t = float(self.device_dict["vector_delta_t"])
            except (TypeError, ValueError):
                pass
        if "vector_boundary_tolerance" in self.device_dict:
            try:
                self.vector_boundary_tolerance = float(self.device_dict["vector_boundary_tolerance"])
            except (TypeError, ValueError):
                pass
        if "vector_field_resolution" in self.device_dict:
            try:
                self.vector_field_resolution = float(self.device_dict["vector_field_resolution"])
            except (TypeError, ValueError):
                pass
        if "vector_field_fallback" in self.device_dict:
            self.vector_field_fallback = self.device_dict["vector_field_fallback"]
        if "vector_max_steps" in self.device_dict:
            try:
                self.vector_max_steps = int(self.device_dict["vector_max_steps"])
            except (TypeError, ValueError):
                pass
        if "vector_min_field_strength" in self.device_dict:
            try:
                self.vector_min_field_strength = float(self.device_dict["vector_min_field_strength"])
            except (TypeError, ValueError):
                pass
        if "current_smoothing_window" in self.device_dict:
            try:
                self.current_smoothing_window = int(self.device_dict["current_smoothing_window"])
            except (TypeError, ValueError):
                pass
        if "current_savgol_window" in self.device_dict:
            try:
                self.current_savgol_window = int(self.device_dict["current_savgol_window"])
            except (TypeError, ValueError):
                pass
        if "current_savgol_poly" in self.device_dict:
            try:
                self.current_savgol_poly = int(self.device_dict["current_savgol_poly"])
            except (TypeError, ValueError):
                pass

        if "strip" in self.det_model:
            self.x_ele_num = self.device_dict['read_ele_num']
            self.y_ele_num = 1
            self.read_ele_num = self.device_dict['read_ele_num']
            self.field_shift_x = self.device_dict['field_shift_x']
        elif "pixel" in self.det_model:
            self.x_ele_num = self.device_dict['x_ele_num']
            self.y_ele_num = self.device_dict['y_ele_num']
            self.read_ele_num = self.device_dict['x_ele_num']*self.device_dict['y_ele_num']
            self.field_shift_x = self.device_dict['field_shift_x']
            self.field_shift_y = self.device_dict['field_shift_y']
        elif "hexagonal" in self.det_model:
            pass
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
        default_gain_algorithm = "local_path" if self.dimension == 3 else "planar_integral"
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

        if "hexagonal" in self.det_model:
            self.p_r = self.device_dict["p_r"]

    def is_plugin(self):
        if "plugin" in self.det_model or "3d" in self.det_model or "3D" in self.det_model:
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
            E_field = Vector(Ex,Ey,Ez).get_length()
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
                int_alpha += (diff_list[j] + diff_list[j+1]) * (z_list[j+1] - z_list[j]) /2
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
