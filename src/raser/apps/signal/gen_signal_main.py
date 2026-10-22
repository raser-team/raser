#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
'''
@Description: The main program of Raser induced current simulation      
@Date       : 2024/02/20 18:12:26
@Author     : Yuhang Tan, Chenxi Fu
@version    : 2.0
'''
import sys
import os
import array
import time
import subprocess
import json

import ROOT
ROOT.gROOT.SetBatch(True)

from raser.core.device import build_device as bdv
from raser.core.interaction.detector_construction import GeneralDetectorConstruction
from raser.core.interaction.action_initialization import GeneralActionInitialization
from raser.core.field import devsim_field as devfield
from raser.core.frontend.legacy_readout import Amplifier
from raser.apps._planning import execution_seed
from .draw_save import energy_deposition, draw_drift_path
from .runtime import apply_signal_plan
from .runtime import build_current
from .runtime import build_interaction


def main(kwargs):
    """
    Description:
        The main program of Raser induced current simulation      
    Parameters:
    ---------
    dset : class
        Parameters of simulation
    Function or class:
        Detector -- Define the basic parameters and mesh structure of the detector
        DevsimField -- Get the electric field and weighting potential 
        G4Interaction -- Electron and hole paris distibution
        CalCurrent -- Drift of e-h pais and induced current
        Amplifier -- Readout electronics simulation  
    Modify:
    ---------
        2021/09/02
    """
    start = time.time()

    det_name = kwargs['det_name']
    my_d = bdv.Detector(det_name)
    apply_signal_plan(my_d, kwargs)
    if kwargs['voltage'] is not None:
        my_d.voltage = float(kwargs['voltage'])

    if kwargs['irradiation'] != None:
        my_d.irradiation_flux = float(kwargs['irradiation'])
    if kwargs.get("events_per_job") is not None:
        my_d.g4_config["total_events"] = int(kwargs["events_per_job"])
    if kwargs.get("g4_vis_driver"):
        my_d.g4_config["g4_vis_driver"] = kwargs["g4_vis_driver"]

    g4_vis = kwargs['g4_vis']
    if g4_vis:
        my_d.g4_config["g4_vis_output"] = os.path.join(
            kwargs["_run_path"],
            "g4_geometry",
        )
    my_f = devfield.DevsimField(
        my_d.device,
        my_d.dimension,
        my_d.voltage,
        my_d.read_out_contact,
        my_d.mesher,
        is_plugin=my_d.is_plugin(),
        irradiation_flux=my_d.irradiation_flux,
        bounds=my_d.bound,
        field_set=kwargs["_field_set"],
        field_directory=kwargs["_field_directory"],
        interpolation_bins=my_d.device_dict.get("field_interpolation_bins"),
    )
    if "lgad" in my_d.det_model:
        my_d.gain_rate_cal(my_f)
    
    g4_seed = execution_seed(kwargs)
    interaction_options = {}
    if kwargs.get("_g4_action_initialization") is not None:
        interaction_options["MyActionInitialization"] = kwargs[
            "_g4_action_initialization"
        ]
    my_g4 = build_interaction(
        my_d,
        g4_seed,
        g4_vis,
        **interaction_options,
    )
    try:
        batch = 0 if my_g4.geant4_model == "toy_mip" else -1
        my_current = build_current(my_d, my_f, my_g4, batch)
        ele_current = Amplifier(
            my_current.sum_cu,
            my_d.amplifier,
            seed=g4_seed,
            CDet=my_d.capacitance,
        )

        path = kwargs["_run_path"]
        #energy_deposition(my_g4)   # Draw Geant4 depostion distribution
        draw_drift_path(my_d,my_g4,my_f,my_current,path)
        my_current.draw_currents(path) # Draw current
        ele_current.draw_waveform(my_current.sum_cu, path)

        if 'strip' in my_d.det_model:
            my_current.charge_collection_strip(path)
        if 'pixel' in my_d.det_model:
            my_current.charge_collection_pixel(path)
    finally:
        my_g4.close()
    
    del my_f
    end = time.time()
    print("total_time:%s"%(end-start))


if __name__ == '__main__':
    args = sys.argv[1:]
    kwargs = {}
    for arg in args:
        key, value = arg.split('=')
        kwargs[key] = value
    main(kwargs)
