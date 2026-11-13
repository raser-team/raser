#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

"""
Description:  Define physical models for different materials
@Date       : 2025/11/11
@Author     : Yuhang Tan, Tao Yang, Chenxi Fu
@version    : 3.0
"""

import json
from functools import cached_property
from pathlib import Path

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
    def __init__(self, device_name, device_dict=None):
        device_json = device_file(device_name)
        # A run hands in the content it recorded; otherwise the file is read.
        if device_dict is None:
            with open(device_json) as f:
                device_dict = json.load(f)
        self.device_dict = device_dict
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

        if "planar" in self.det_model or "lgad" == self.det_model:
            self.p_x = self.device_dict['l_x']
            self.p_y = self.device_dict['l_y']

        if "strip" in self.det_model:
            self.p_x = self.device_dict['p_x']
            self.p_y = self.device_dict['l_y']

        if "pixel" in self.det_model:
            self.p_x = self.device_dict["p_x"]
            self.p_y = self.device_dict["p_y"]

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

    @cached_property
    def capacitance(self):
        """Detector capacitance in pF: capacitance_pF of the json, otherwise
        the parallel-plate value of the readout area over the depletion depth."""
        if "capacitance_pF" in self.device_dict:
            return float(self.device_dict["capacitance_pF"])

        if "3d" in self.det_model.lower():
            return None

        depletion_depth = float(self.device_dict.get("depletion_depth", self.l_z))
        if depletion_depth <= 0:
            raise ValueError("depletion_depth must be positive")

        material = Material(self.material)
        area_um2 = self._readout_area_um2()
        capacitance_f = (
            EPSILON_0_F_PER_M
            * material.permittivity
            * area_um2
            * 1e-12
            / (depletion_depth * 1e-6)
        )
        return capacitance_f * 1e12

    def is_plugin(self):
        if ( "plugin" in self.det_model or "3d" in self.det_model or "3D" in self.det_model
        ):
            return True
        else:
            return False

if __name__ == "__main__":
    import sys
    Detector(sys.argv[1])
