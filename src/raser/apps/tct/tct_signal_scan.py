#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""
@Description: The main program of Raser induced current simulation
@Date       : 2024/09/26 15:11:20
@Author     : Lin Zhu
@version    : 2.0
"""
import os
from pathlib import Path
import array
import time

import ROOT
ROOT.gROOT.SetBatch(True)

from raser.core.device import build_device as bdv
from raser.core.field import devsim_field as devfield
from raser.core.current import cal_current as ccrt
from raser.core.frontend.legacy_readout import Amplifier
from raser.supports.output import output

from raser.core.interaction.laser import LaserInjection


def job_main(kwargs):
    det_name = kwargs['det_name']
    my_d = bdv.Detector(det_name, kwargs["_files"]["device"])
    files = kwargs["_files"]
    laser_dic = dict(files["laser"])
    amplifier = str(files["afe"].get("name") or Path(str(kwargs["amplifier"])).stem)
    
    my_f = devfield.DevsimField(
        my_d.device,
        my_d.dimension,
        my_d.voltage,
        my_d.read_out_contact,
        my_d.mesher,
        is_plugin=my_d.is_plugin(),
        irradiation_flux=my_d.irradiation_flux,
        bounds=my_d.bound,
        field_directory=kwargs["_field_directory"],
        interpolation_bins=my_d.device_dict.get("field_interpolation_bins"),
    )
    my_l = LaserInjection(my_d, laser_dic)

    my_current = ccrt.CalCurrentLaser(my_d, my_f, my_l)
    path = kwargs["_run_batch_path"]

    ele_current = Amplifier(
        my_current.sum_cu,
        amplifier,
        CDet=my_d.capacitance,
    )
    if kwargs['job_index'] is not None:
        # key = my_l.fz_rel
        tag = kwargs['job_index']
        ele_current.save_signal_TTree(path, tag)
    else:
        my_current.draw_currents(path) # Draw current
        ele_current.draw_waveform(my_current.sum_cu, path) # Draw waveform

        my_l.draw_nocarrier3D(path)
        my_l.draw_nocarrier2D(path)
        
    print('successfully')
