#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
'''
@Description: The main program of Raser induced current simulation,(quickly checkout under different Votage)      
@Date       : 2025/02/11 
@Author     : Lin Zhu
@version    : 2.0
'''

#TODO: need rewrite

import sys
import os
import array
import time
import subprocess
import json
import random

import ROOT
ROOT.gROOT.SetBatch(True)

from raser.core.device import build_device as bdv
from raser.core.interaction.interaction import GeneralG4Interaction
from raser.core.field import devsim_field as devfield
from raser.core.current import cal_current as ccrt
from raser.core.afe import readout as rdo
from .draw_save import energy_deposition, draw_drift_path
from raser.supports.output import output


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
    if kwargs['voltage'] != None:
        if kwargs['g4experiment'] != None:
            g4experiment = kwargs['g4experiment']
        else:
            g4experiment = my_d.g4experiment
        if kwargs['amplifier'] != None:
            amplifier = kwargs['amplifier']
        else:
            amplifier = my_d.amplifier

        g4_seed = random.randint(0,1e7)
        my_g4 = GeneralG4Interaction(my_d, g4experiment, g4_seed)

        voltage_max = int(kwargs['voltage'])
        for i in range(1,abs(voltage_max)+1):
            if voltage_max<0:
                voltage = -1*int(i)
            else:
                voltage = int(i)
            
            # my_f = devfield.DevsimField(my_d.device, my_d.dimension, voltage, my_d.read_out_contact, my_d.irradiation_flux)
            if "strip" in det_name:
                my_f = devfield.DevsimField(my_d.device, my_d.dimension, voltage, my_d.read_ele_num, my_d.l_z)
            else: 
                my_f = devfield.DevsimField(my_d.device, my_d.dimension, voltage, 1, my_d.l_z)

            
            my_current = ccrt.CalCurrentG4P(my_d, my_f, my_g4, -1)
            now = time.strftime("%Y_%m%d_%H%M%S")
            path = output(__file__, my_d.det_name, now)

            #energy_deposition(my_g4)   # Draw Geant4 depostion distribution
            draw_drift_path(my_d,my_g4,my_f,my_current,path)

            my_current.save_current(my_d)
            if 'ngspice' not in amplifier:
                ele_current = rdo.Amplifier(my_current.sum_cu, amplifier)
                my_current.draw_currents(path) # Draw current
                ele_current.draw_waveform(my_current.sum_cu, path) # Draw waveform
                if 'strip' in my_d.det_model:
                    my_current.charge_collection_strip(path)
            
            del my_f
            end = time.time()
            print("total_time:%s"%(end-start))
    
    else:
        if kwargs['g4experiment'] != None:
            g4experiment = kwargs['g4experiment']
        else:
            g4experiment = my_d.g4experiment
        if kwargs['amplifier'] != None:
            amplifier = kwargs['amplifier']
        else:
            amplifier = my_d.amplifier
    
        g4_seed = random.randint(0,1e7)
        my_g4 = GeneralG4Interaction(my_d, g4experiment, g4_seed)

        voltage_max = int(my_d.voltage)
        for i in range(500,abs(voltage_max)+1,10):
            if voltage_max<0:
                # voltage = -1*int(i)
                voltage = -1*float(i)
            else:
                # voltage = int(i)
                voltage = float(i)
            
            my_f = devfield.DevsimField(my_d.device, my_d.dimension, voltage, my_d.read_out_contact, is_plugin=my_d.is_plugin(), irradiation_flux=my_d.irradiation_flux, bounds=my_d.bound)
            
            my_current = ccrt.CalCurrentG4P(my_d, my_f, my_g4, -1)
            # if "strip" in det_name:
            #     my_current = ccrt.CalCurrentStrip(my_d, my_f, my_g4, 0)
            # else: 
            #     my_current = ccrt.CalCurrentG4P(my_d, my_f, my_g4, -1)

            now = time.strftime("%Y_%m%d_%H%M%S")
            path = output(__file__, my_d.det_name, now)

            #energy_deposition(my_g4)   # Draw Geant4 depostion distribution
            draw_drift_path(my_d,my_g4,my_f,my_current,path)

            my_current.save_current(my_d)
            if 'ngspice' not in amplifier:
                ele_current = rdo.Amplifier(my_current.sum_cu, amplifier)
                my_current.draw_currents(path) # Draw current
                ele_current.draw_waveform(my_current.sum_cu, path) # Draw waveform
                if 'strip' in my_d.det_model:
                    my_current.charge_collection_strip(path)
            
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

