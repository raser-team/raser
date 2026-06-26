#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

'''
@Date       : 2023
@Author     : Ye He, Kaibo Xie
@version    : 2.0
'''

import sys
import os
import array
import time
import subprocess
import re
import json

import ROOT
ROOT.gROOT.SetBatch(True)
import numpy

from raser.core.device import build_device as bdv
from raser.core.field import devsim_field as devfield
from raser.core.current import cal_current as ccrt
from raser.core.analog.set_pwl_input import set_pwl_input as pwlin
from raser.supports.output import output
from raser.supports.paths import app_file_path
from raser.supports.paths import component_path
from . import bmos

def mkdir(folder_name):
    try:
        os.makedirs(folder_name)
    except Exception as e:
            pass
    
def get_signal():
    signal = []

    geant4_json = app_file_path("bmos", "bmos.json")
    with open(geant4_json) as f:
         g4_dic = json.load(f)

    detector_json = component_path("detector")
    with open(os.path.join(detector_json , g4_dic['DetModule'])) as q:
         det_dic = json.load(q)

    start = time.time()

    det_name = det_dic['det_name']
    my_d = bdv.Detector(det_name)
    
    voltage = det_dic['bias']['voltage']
    amplifier = det_dic['amplifier']
    
    my_f = devfield.DevsimField(my_d.device, my_d.dimension, voltage, my_d.read_out_contact, my_d.mesher, is_plugin=my_d.is_plugin(), irradiation_flux=my_d.irradiation_flux, bounds=my_d.bound,)

    my_g4 = bmos.bmosG4Interaction(my_d)

    output_path = output(__file__)
    tag = f"{g4_dic['par_type']}_{g4_dic['par_energy']}MeV_{g4_dic['par_num']}particle"
    dirname = f"{g4_dic['par_type']}_{g4_dic['par_energy']}MeV"
    root_name = f"{g4_dic['CurrentName'].split('.')[0]}_{tag}.root"
    pwl_name = f"pwl{g4_dic['CurrentName'].split('.')[0]}_{tag}.txt"
    filename_after_ngspice = f"UCSC_output_{tag}.raw"
    
    for i in range(len(my_g4.p_steps_current)):
        my_current = ccrt.CalCurrentG4P(my_d, my_f, my_g4, i)

        save_current(my_current, output_path, root_name, pwl_name, 1)

        pwlin(os.path.join(output_path, pwl_name), os.path.join(os.path.dirname(__file__), 'ucsc.cir'), os.path.join(output_path, filename_after_ngspice), output_path,)
        subprocess.run(
            [
                "ngspice",
                "-b",
                "-r",
                os.path.join(output_path, "xxx.raw"),
                os.path.join(output_path, "ucsc_tmp.cir"),
            ],
            check=True,
        )
        time_v, volt = read_file_voltage(output_path, filename_after_ngspice)
        signal.append(max(volt))

    print(signal)
    draw(output_path, signal, tag, dirname)

    # draw(output_path, pwl_name, filename_after_ngspice, tag, totalengry)

    end = time.time()
    print("total_time:%s"%(end - start))

def save_current(my_current, output_path, root_name, pwl_name, read_ele_num):
    time = array.array('d', [999.0])
    current = array.array('d', [999.0])

    fout = ROOT.TFile(os.path.join(output_path, root_name), "RECREATE")
    t_out = ROOT.TTree("tree", "signal")
    t_out.Branch("time", time, "time/D")
    for i in range(read_ele_num):
        t_out.Branch("current"+str(i), current, "current"+str(i)+"/D")
        for j in range(my_current.n_bin):
            current[0]=my_current.sum_cu[i].GetBinContent(j)
            time[0]=j*my_current.t_bin
            t_out.Fill()
    t_out.Write()
    fout.Close()
   
    file = ROOT.TFile(os.path.join(output_path, root_name), "READ")
    tree = file.Get("tree")

    pwl_file = open(os.path.join(output_path, pwl_name), "w")

    for i in range(tree.GetEntries()):       
        tree.GetEntry(i)
        time_pwl = tree.time
        current_pwl = tree.current0
        pwl_file.write(str(time_pwl) + " " + str(current_pwl) + "\n")
    
    pwl_file.close()
    file.Close()

def read_file_voltage(file_path, file_name):
    with open(os.path.join(file_path, file_name)) as f:
        lines = f.readlines()
        time_v,volt = [],[]

        for line in lines:
            time_v.append(float(line.split()[0])*1e9)
            volt.append(float(line.split()[1])*1e3)

    time_v = numpy.array(time_v ,dtype='float64')
    volt = numpy.array(volt,dtype='float64')

    return time_v,volt

def draw(output_path, signal, tag, dirname):
    ROOT.gROOT.SetBatch(True)
    c = ROOT.TCanvas( 'c', 'c', 8000, 6000 )
    # c.SetCanvasSize(800, 600)
    # c.SetWindowSize(800, 600)
    c.cd()
    minsignal = float(min(signal))
    maxsignal = float(max(signal))
    binnum = 50
    binwidth = (maxsignal - minsignal)/binnum
    wave_graph = ROOT.TH1F('','', binnum + 2, minsignal - binwidth, maxsignal + binwidth)

    mkdir(os.path.join(output_path, 'histogram', 'root', dirname))
    file = ROOT.TFile(os.path.join(output_path, 'histogram', 'root', dirname, f"Histogram_{tag}.root"), "RECREATE",)
    amplitude = ROOT.TTree("tree", "amplitude")
    amp =array.array('d', [0.0])
    amplitude.Branch("amplitude", dirname, "amplitude/D")
    # amplitude.Write()
    # file.Close()

    for sig in signal:
        amp[0] = sig
        amplitude.Fill()
        wave_graph.Fill(sig)

    # if ifnoise(time, volt, noisestd):
    #     num_noise += 1
    #     continue
    # num_signal += 1
    wave_graph.Draw()
    wave_graph.SetTitle(' ')
    wave_graph.SetLineColor(1)
    wave_graph.SetLineWidth(2)

    wave_graph.GetXaxis().SetTitle('mV')
    wave_graph.GetXaxis().SetTitleSize(0.05)
    wave_graph.GetXaxis().SetTitleOffset(0.9)
    wave_graph.GetYaxis().SetTitle('events')
    wave_graph.GetYaxis().SetTitleSize(0.05)
    wave_graph.GetYaxis().SetTitleOffset(0.9)
    # wave_graph.Fit("gaus")
    wave_graph.Fit("landau")

    mkdir(os.path.join(output_path, 'histogram', 'pdf', dirname))
    # c.SaveAs(os.path.join(output_path, f"Histogram_{tag}.root"))
    c.SaveAs(os.path.join(output_path, 'histogram', 'pdf', dirname, f"Histogram_{tag}.pdf"))

    amplitude.Write()
    wave_graph.Write()
    file.Close()

    
