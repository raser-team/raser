#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
'''
@Description: The main program of Raser induced current simulation      
@Date       : 2024/09/26 15:11:20
@Author     : Yuhang Tan, Chenxi Fu
@version    : 2.0
'''
import sys
import os
from array import array
import time
import subprocess
import json
import random

import ROOT
ROOT.gROOT.SetBatch(True)

from ..device import build_device as bdv
from ..interaction.interaction import GeneralG4Interaction
from ..field import devsim_field as devfield
from ..current import cal_current as ccrt
from ..current.cross_talk import cross_talk
from ..afe import readout as rdo
from ..util.output import output
from ..util.math import inversed_fast_fourier_transform as ifft

def batch_loop(my_d, my_f, my_g4, g4_seed, total_events, instance_number):
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
    start_n = instance_number * total_events
    end_n = (instance_number + 1) * total_events

    effective_number = 0

    # datas that varies in each event

    event_array = array('i', [0])
    e_dep_array = array('d', [0.])
    par_in_array = array('d', [0., 0., 0.])
    par_out_array = array('d', [0., 0., 0.])

    # TODO: manage the extra datas inside a dict

    tree = ROOT.TTree("tree", "Waveform Data")
    tree.Branch("event", event_array, "event/I")
    tree.Branch("e_dep", e_dep_array, "e_dep/D")
    tree.Branch("par_in", par_in_array, "par_in[3]/D")
    tree.Branch("par_out", par_out_array, "par_out[3]/D")

    # datas that are constant in each event

    voltage_array = array('d', [my_d.voltage])
    irradiation_array = array('d', [my_d.irradiation_flux])
    g4_str = ROOT.std.string()
    g4_str.assign(my_d.g4experiment)
    amplifier_str = ROOT.std.string()
    amplifier_str.assign(my_d.amplifier)
    
    tree.Branch("voltage", voltage_array, "voltage/D")
    tree.Branch("irradiation_flux", irradiation_array, "irradiation_flux/D")
    tree.Branch("g4experiment", g4_str)
    tree.Branch("amplifier", amplifier_str)

    current_time_bin = 50e-12 # TODO: relate this to setting in calcurrent.py
    current_duration = 1e-6
    amplified_waveform_time_bin = 50e-12 # TODO: relate this to setting in readout.py
    amplified_waveform_duration = 1e-6
    # TODO: make the time setting match the .tran in the .cir file
    current = [ROOT.TH1F("current_%s"%(i), "current_%s"%(i), int(current_duration/current_time_bin), 0, current_duration) for i in range(my_d.read_ele_num)]
    cross_talked_current = [ROOT.TH1F("cross_talked_current_%s"%(i), "cross_talked_current_%s"%(i), int(current_duration/current_time_bin), 0, current_duration) for i in range(my_d.read_ele_num)]
    amplified_waveform = [ROOT.TH1F("amplified_waveform_%s"%(i), "amplified_waveform_%s"%(i), int(amplified_waveform_duration/amplified_waveform_time_bin), 0, amplified_waveform_duration) for i in range(my_d.read_ele_num)]
    for i in range(my_d.read_ele_num):
        tree.Branch("current_%s"%(i), current[i])
        tree.Branch("cross_talked_current_%s"%(i), cross_talked_current[i])
        tree.Branch("amplified_waveform_%s"%(i), amplified_waveform[i])

    # Note: TTree.Branch() needs the binded variable (namely the address) to be valid and the same while Fill(), 
    # so don't put the Branch() into other methods/functions!

    for event in range(start_n,end_n):
        print("run events number:%s"%(event))
        if len(my_g4.p_steps[event-start_n]) > 5:
            effective_number += 1
            my_current = ccrt.CalCurrentG4P(my_d, my_f, my_g4, event-start_n)

            if ("strip" in my_d.det_model or "pixel" in my_d.det_model) and my_d.cross_talk != None:
                my_current.cross_talk_cu = cross_talk(my_d.det_name, my_d.cross_talk, my_current.sum_cu)
            else:
                my_current.cross_talk_cu = my_current.sum_cu

            ele_current = rdo.Amplifier(my_current.cross_talk_cu, my_d.amplifier, seed=event, is_cut=True)

            event_array[0] = event
            e_dep_array[0] = my_g4.edep_devices[event-start_n]
            # assume the list of electrons is sorted by particle injection trace
            # and all inside the active region of the detector
            par_in_array[0], par_in_array[1], par_in_array[2] = my_g4.p_steps_current[my_g4.selected_batch_number][0]
            par_out_array[0], par_out_array[1], par_out_array[2] = my_g4.p_steps_current[my_g4.selected_batch_number][-1]

            # Note: TTree.Fill() needs the binded variable (namely the address) to be valid and the same with Branch(), 
            # so don't put Fill() into other methods/functions!
            for i in range(my_d.read_ele_num):
                current[i].Reset()
                current[i].Add(my_current.sum_cu[i])
                cross_talked_current[i].Reset()
                cross_talked_current[i].Add(my_current.cross_talk_cu[i])
                amplified_waveform[i].Reset()
                amplified_waveform[i].Add(ele_current.amplified_currents[i])

            # Barely clone another TH1F will cause segmentation fault
            tree.Fill()

    detection_efficiency =  effective_number/(end_n-start_n) 
    print("detection_efficiency=%s"%detection_efficiency)

    file_path = os.path.join(my_d.subfile_path+
                             "sweep"+
                             str(instance_number)+
                             str(my_d.voltage)+
                             #str(my_d.irradiation_flux, my_d.bound)+
                             str(my_d.g4experiment)+
                             str(my_d.amplifier)+
                             ".root")
    file = ROOT.TFile(file_path, "RECREATE")
    tree.Write()
    file.Close()

def main(kwargs):
    #监测点
    print("Starting sweep...")
    #
    det_name = kwargs['det_name']
    
    my_d = bdv.Detector(det_name)
    if kwargs['voltage'] != None:
        my_d.voltage = kwargs['voltage']

    if kwargs['irradiation'] != None:
        my_d.irradiation_flux = float(kwargs['irradiation'])

    if kwargs['g4experiment'] != None:
        my_d.g4experiment = kwargs['g4experiment']

    if kwargs['amplifier'] != None:
        my_d.amplifier = kwargs['amplifier']

    if kwargs['subfile_path'] != None:
        my_d.subfile_path = kwargs['subfile_path']


    my_f = devfield.DevsimField(my_d.device, my_d.dimension, my_d.voltage, 
    my_d.read_out_contact, is_plugin=my_d.is_plugin(), 
    irradiation_flux=my_d.irradiation_flux, bounds=my_d.bound) 

    if "lgad" in my_d.det_model:
        my_d.gain_rate_cal(my_f)

    geant4_json = os.getenv("RASER_SETTING_PATH")+"/g4experiment/" + my_d.g4experiment + ".json"
    with open(geant4_json) as f:
        g4_dic = json.load(f)

    total_events = int(g4_dic['total_events'])
        
        
    job_number = kwargs['job']
    instance_number = job_number

    g4_seed = instance_number * total_events
    my_g4 = GeneralG4Interaction(my_d, my_d.g4experiment, g4_seed)

    ele_json = os.getenv("RASER_SETTING_PATH")+"/electronics/" + my_d.amplifier + ".json"
    ele_cir = os.getenv("RASER_SETTING_PATH")+"/electronics/" + my_d.amplifier + ".cir"
    if os.path.exists(ele_json):
        ROOT.gRandom.SetSeed(instance_number) # to ensure time resolution result reproducible
    elif os.path.exists(ele_cir):
        # subprocess.run(['ngspice -b '+ele_cir], shell=True)
        # noise_raw = "./output/elec/" + amplifier + "/noise.raw" # need to be fixed in the .cir
        # try:
        #     with open(noise_raw, 'r') as f_in:
        #         lines = f_in.readlines()
        #         freq, noise = [],[]
        #         for line in lines:
        #             freq.append(float(line.split()[0]))
        #         noise.append(float(line.split()[1]))
        # except FileNotFoundError:
        #     print("Warning: ngspice .noise experiment is not set.")
        #     print("Please check the .cir file or make sure you have set an TRNOISE source.")
        # TODO: fix noise seed, add noise from ngspice .noise spectrum
        pass
    
    batch_loop(my_d, my_f, my_g4, g4_seed, total_events, instance_number)
    del my_g4


