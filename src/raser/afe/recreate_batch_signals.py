#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

'''
@Description: Signal re-formation for events of great amount
@Date       : 2025/04/09 15:24:27
@Author     : Chenxi Fu
@version    : 1.0
'''

import os
from array import array

import ROOT

from ..device.build_device import Detector
from ..current.cross_talk import cross_talk
from ..afe.readout import Amplifier

def main(amp_name, det_name, file_name, tct=None):    
    my_d = Detector(det_name)
    file_pointer = ROOT.TFile(file_name, "UPDATE")
    tree = file_pointer.Get("tree")

    current_time_bin = 50e-12 # TODO: relate this to setting in calcurrent.py
    current_duration = 1e-6
    amplified_waveform_time_bin = 50e-12 # TODO: relate this to setting in readout.py
    amplified_waveform_duration = 1e-6
    current = [ROOT.TH1F("current_%s"%(i), "current_%s"%(i), int(current_duration/current_time_bin), 0, current_duration) for i in range(my_d.read_ele_num)]
    cross_talked_current = [ROOT.TH1F("cross_talked_current_%s"%(i), "cross_talked_current_%s"%(i), int(current_duration/current_time_bin), 0, current_duration) for i in range(my_d.read_ele_num)]
    amplified_waveform = [ROOT.TH1F("amplified_waveform_%s"%(i), "amplified_waveform_%s"%(i), int(amplified_waveform_duration/amplified_waveform_time_bin), 0, amplified_waveform_duration) for i in range(my_d.read_ele_num)]

    for i in range(my_d.read_ele_num):
        tree.SetBranchAddress("current_{i}".format(i=i), current[i])
        tree.SetBranchAddress("cross_talked_current_{i}".format(i=i), cross_talked_current[i])
        tree.SetBranchAddress("amplified_waveform_{i}".format(i=i), amplified_waveform[i])
        
    new_tree = tree.CloneTree(0)
    new_tree.SetName("new_tree")

    if "strip" in my_d.det_model:
        temp_cross_talked_current = cross_talk(det_name, my_d.cross_talk, current)
    else:
        temp_cross_talked_current = current

    n = tree.GetEntries()
    for i in range(n):
        tree.GetEntry(i)
        for j in range(my_d.read_ele_num):
            cross_talked_current[j].Reset()
            cross_talked_current[j].Add(temp_cross_talked_current[j])

        amp = Amplifier(cross_talked_current, amp_name, seed=i)
        for j in range(my_d.read_ele_num):
            amplified_waveform[j].Reset()
            amplified_waveform[j].Add(amp.amplified_currents[j])

        new_tree.Fill()


    # if you define TH1F during TFile opened, after TFile closed TH1F will become None
    # SetDirectory(0) is needed to prevent this

    file_pointer.Delete("tree;*")
    new_tree.SetName("tree")
    new_tree.Write()

    print("read {n} events from {file_name}".format(n=n,file_name=file_name))
    file_pointer.Close()


