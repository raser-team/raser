#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

'''
@Description:
    Get the signal induced by particle interaction in BMOS detector
@Date       : 2024
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
from raser.core.afe.set_pwl_input import set_pwl_input as pwlin
from raser.supports.output import output
from raser.supports.paths import component_path
from. import bmos

def get_signal(sensor):

    geant4_json = component_path("g4experiment", "bmos.json")
    with open(geant4_json) as f:
         g4_dic = json.load(f)

    det_name = sensor

    start = time.time()

    my_d = bdv.Detector(det_name)
    
    voltage = my_d.voltage
    amplifier = my_d.amplifier

#     print(my_d.device)
#     print(voltage)
    
    my_f = devfield.DevsimField(my_d.device, my_d.dimension, voltage, my_d.read_out_contact, my_d.mesher, is_plugin=my_d.is_plugin(), irradiation_flux=my_d.irradiation_flux, bounds=my_d.bound,)

    my_g4 = bmos.bmosG4Interaction(my_d)

    my_current = ccrt.CalCurrentG4P(my_d, my_f, my_g4, -1)
    totalengry = my_g4.energy_steps

    now = time.strftime("%Y_%m%d_%H%M%S")
    output_path = output(__file__, my_d.det_name, now)
    tag = f"{g4_dic['par_type']}_{g4_dic['par_energy']}MeV_{g4_dic['par_num']}particle"
    root_name = f"{g4_dic['CurrentName'].split('.')[0]}_{tag}.root"
    pwl_name = f"pwl{g4_dic['CurrentName'].split('.')[0]}_{tag}.txt"
    filename_after_ngspice = f"UCSC_output_{tag}.raw"

    save_current(my_current, output_path, root_name, pwl_name, 1)

    # TODO: fix this
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

    draw(output_path, pwl_name, filename_after_ngspice, tag, totalengry)

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
        # print(my_current.sum_cu[0][i])
        # print(current_pwl)
        # sleep(1)
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

def read_file_current(file_path, file_name):
    with open(os.path.join(file_path, file_name)) as f:
        lines = f.readlines()
        time_c,curr = [],[]

        for line in lines:
            time_c.append(float(line.split()[0])*1e9)
            curr.append(float(line.split()[1])*1e6)

    time_c = numpy.array(time_c ,dtype='float64')
    curr = numpy.array(curr, dtype='float64')

    return time_c, curr


def draw(output_path, pwl_name, filename_after_ngspice, tag, totalengry):
    file_path = output_path
    
    # geant4_json = os.getenv("RASER_SETTING_PATH")+"/g4experiment/cflm.json"
    # with open(geant4_json) as f:
    #      g4_dic = json.load(f)

    file_name_v = filename_after_ngspice
    file_name_c = pwl_name

    time_v, volt, time_c, curr = [], [], [], []

    time_v, volt = read_file_voltage(file_path,file_name_v)
    length_v = len(time_v)
    time_c, curr = read_file_current(file_path,file_name_c)
    length_c = len(time_c)


    ROOT.gROOT.SetBatch()
        
    c = ROOT.TCanvas('c','c',4000,2000)
    
    pad1 = ROOT.TPad("pad1", "pad1", 0.05, 0.05, 0.45, 0.95)
    pad2 = ROOT.TPad("pad2", "pad2", 0.55, 0.05, 0.95, 0.95)

    pad1.Draw()
    pad2.Draw()
    
    pad1.cd()
    f1 = ROOT.TGraph(length_c, time_c, curr)
    f1.SetTitle(tag)
    f1.SetLineColor(2)
    f1.SetLineWidth(2)
    f1.GetXaxis().SetTitle('Time [ns]')
    f1.GetXaxis().SetLimits(0,10)
    f1.GetXaxis().CenterTitle()
    f1.GetXaxis().SetTitleSize(0.05)
    f1.GetXaxis().SetTitleOffset(0.8)
    f1.GetYaxis().SetTitle('Current [uA]')
    # f1.GetYaxis().SetLimits(0,-5)
    f1.GetYaxis().CenterTitle()
    f1.GetYaxis().SetTitleSize(0.07)
    f1.GetYaxis().SetTitleOffset(0.7)
    f1.Draw('AL')
    pad1.Update()

    pad2.cd()
    f2 = ROOT.TGraph(length_v, time_v, volt)
    f2.SetTitle(f"Energy Deposition:{sum(totalengry[0])}MeV")
    f2.SetLineColor(2)
    f2.SetLineWidth(2)
    f2.GetXaxis().SetTitle('Time [ns]')
    f2.GetXaxis().SetLimits(0,10)
    f2.GetXaxis().CenterTitle()
    f2.GetXaxis().SetTitleSize(0.05)
    f2.GetXaxis().SetTitleOffset(0.8)
    f2.GetYaxis().SetTitle('Voltage [mV]')
    # f2.GetYaxis().SetLimits(0,-5)
    f2.GetYaxis().CenterTitle()
    f2.GetYaxis().SetTitleSize(0.07)
    f2.GetYaxis().SetTitleOffset(0.7)
    f2.Draw('AL')
    pad2.Update()

    c.SaveAs(os.path.join(output_path, f"Signal_{tag}.pdf"))
