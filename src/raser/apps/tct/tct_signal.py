#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

'''
Description:  tct_signal.py
@Date       : 2023
@Author     : Yu Zhao, Chenxi Fu
@version    : 2.0
'''

import sys
import os
from pathlib import Path
import array
import time
import subprocess
import time

import ROOT
ROOT.gROOT.SetBatch(True)

from raser.core.device import build_device as bdv
from raser.core.field import devsim_field as devfield
from raser.core.field.solved import solved_field
from raser.core.current import cal_current as ccrt
from raser.core.current.currents import EventCurrents, append_currents
from raser.core.frontend.toy_readout import Amplifier
from raser.core.interaction.laser import LaserInjection
from raser.supports.output import output, create_path

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
        Laser -- Electron and hole pairs distibution
        CalCurrent -- Drift of e-h pairs and induced current
        Amplifier -- Readout electronics simulation
    Modify:
    ---------
        2021/09/02
    """
    start = time.time()

    det_name = kwargs['det_name']
    my_d = bdv.Detector(det_name, kwargs["_files"]["device"])
    files = kwargs["_files"]
    laser_dic = dict(files["laser"])
    amplifier = str(files["afe"].get("name") or Path(str(kwargs["amplifier"])).stem)
    
    my_f = devfield.DevsimField(
        my_d.device,
        my_d.voltage,
        my_d.read_out_contact,
        irradiation_flux=my_d.irradiation_flux,
        bounds=my_d.bound,
        field_directory=solved_field(my_d, my_d.voltage, my_d.irradiation_flux),
        interpolation_bins=my_d.device_dict.get("field_interpolation_bins"),
    )
    my_l = LaserInjection(my_d, laser_dic)

    my_current = ccrt.CalCurrentLaser(my_d, my_f, my_l)
    job = kwargs.get("job_index") or 0
    currents_path = os.path.join(kwargs["_run_batch_path"], "currents_%s.h5" % (job))
    if os.path.exists(currents_path):  # of an earlier start of this job
        os.remove(currents_path)
    # One laser pulse is the one event of the job.
    append_currents(
        currents_path,
        my_current.electrodes,
        my_current.t_bin,
        EventCurrents(
            0, my_current.t_start, my_current.current, my_current.charge, my_current.pairs
        ),
    )
    path = os.path.join(kwargs["_run_path"], "plots", "job_%s" % (job))
    os.makedirs(path, exist_ok=True)

    ele_current = Amplifier(
        my_current.sum_cu,
        amplifier,
        CDet=my_d.capacitance,
    )
    my_current.draw_currents(path) # Draw current
    ele_current.draw_waveform(my_current.sum_cu, path) # Draw waveform

    my_l.draw_nocarrier3D(path)
    my_l.draw_nocarrier2D(path)

    print("total time used:%s"%(time.time()-start))

if __name__ == '__main__':
    args = sys.argv[1:]
    kwargs = {}
    for arg in args:
        key, value = arg.split('=')
        kwargs[key] = value
    main(kwargs)
