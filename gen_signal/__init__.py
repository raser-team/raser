#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
'''
@Description: The main program of Raser induced current simulation      
@Date       : 2024/02/20 18:12:26
@Author     : tanyuhang, Chenxi Fu
@version    : 2.0
'''
import sys
import os
import time

from field import build_device as bdv
from particle import g4simulation as g4s
from field import devsim_field as devfield
from current import cal_current as ccrt
from elec import ele_readout as rdout
from elec import ngspice_set_input as ngsip
from elec import ngspice as ng

from . import draw_save
from util.output import output

import json

import random

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
        DevsimCal -- Get the electric field and weighting potential 
        Particles -- Electron and hole paris distibution
        CalCurrent -- Drift of e-h pais and induced current
        Amplifier -- Readout electronics simulation
        draw_plots -- Draw electric field, drift path and energy deposition        
    Modify:
    ---------
        2021/09/02
    """
    start = time.time()

    det_name = kwargs['det_name']
    my_d = bdv.Detector(det_name)
    
    if kwargs['voltage'] != None:
        voltage = float(kwargs['voltage'])
    else:
        voltage = float(my_d.voltage)

    if kwargs['absorber'] != None:
        absorber = kwargs['absorber']
    else:
        absorber = my_d.absorber

    if kwargs['amplifier'] != None:
        amplifier = kwargs['amplifier']
    else:
        amplifier = my_d.amplifier

    if "strip" in det_name:
        my_f = devfield.DevsimField(my_d.device, my_d.dimension, voltage, my_d.read_ele_num, my_d.l_z)
    else: 
        my_f = devfield.DevsimField(my_d.device, my_d.dimension, voltage, 1, my_d.l_z)

    if kwargs['scan'] != None:
        geant4_json = "./setting/absorber/" + absorber + ".json"
        with open(geant4_json) as f:
            g4_dic = json.load(f)

        total_events = int(g4_dic['total_events'])
        for i in range(kwargs['scan']):
            # TODO: change this into multithread
            instance_number = i
            g4_seed = instance_number * total_events
            my_g4p = g4s.Particles(my_d, absorber, g4_seed)
            batch_loop(my_d, my_f, my_g4p, amplifier, g4_seed, total_events, instance_number)
            del my_g4p
        return
    
    else:  
        g4_seed = random.randint(0,1e7)
        my_g4p = g4s.Particles(my_d, absorber, g4_seed)

    if "strip" in det_name:
        my_current = ccrt.CalCurrentStrip(my_d, my_f, my_g4p, 0)
    else: 
        my_current = ccrt.CalCurrentG4P(my_d, my_f, my_g4p, 0)

    if 'ngspice' in amplifier:
        my_current.save_current(my_d, my_f, "fz_abs")
        input_p=ngsip.set_input(my_current, my_d, "fz_abs")
        input_c=','.join(input_p)
        ng.ngspice(input_c, input_p)
    else:
        ele_current = rdout.Amplifier(my_current, amplifier)
        draw_save.draw_plots(my_d,ele_current,my_f,my_g4p,my_current)
    
    del my_f
    end = time.time()
    print("total_time:%s"%(end-start))



def batch_loop(my_d, my_f, my_g4p, amplifier, g4_seed, total_events, instance_number):
    """
    Description:
        Batch run some events to get time resolution
    Parameters:
    ---------
    start_n : int
        Start number of the event
    end_n : int
        end number of the event 
    detection_efficiency: float
        The ration of hit particles/total_particles           
    @Returns:
    ---------
        None
    @Modify:
    ---------
        2021/09/07
    """
    path = output(__file__, my_d.det_name, 'batch')
    if "plugin" in my_d.det_model:
        draw_save.draw_ele_field(my_d,my_f,"xy",my_d.det_model,my_d.l_z*0.5,path)
    else:
        draw_save.draw_ele_field_1D(my_d,my_f,path)
        draw_save.draw_ele_field(my_d,my_f,"xz",my_d.det_model,my_d.l_y*0.5,path)

    start_n = instance_number * total_events
    end_n = (instance_number + 1) * total_events

    effective_number = 0
    for event in range(start_n,end_n):
        print("run events number:%s"%(event))
        if len(my_g4p.p_steps[event-start_n]) > 5:
            effective_number += 1
            my_current = ccrt.CalCurrentG4P(my_d, my_f, my_g4p, event-start_n)
            ele_current = rdout.Amplifier(my_current, amplifier)
            draw_save.save_signal_time_resolution(my_d,event,ele_current,my_g4p,start_n,my_f)
            del ele_current
    detection_efficiency =  effective_number/(end_n-start_n) 
    print("detection_efficiency=%s"%detection_efficiency)

if __name__ == '__main__':
    args = sys.argv[1:]
    kwargs = {}
    for arg in args:
        key, value = arg.split('=')
        kwargs[key] = value
    main(kwargs)
    