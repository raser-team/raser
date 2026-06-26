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
from raser.core.afe.set_pwl_input import set_pwl_input as pwlin
from raser.supports.output import output
from raser.supports.paths import project_path
from. import bmos
import numpy as np

def mkdir(folder_name):
    try:
        os.makedirs(folder_name)
    except Exception as e:
            pass

def readfile(path, root_name): 
    file = ROOT.TFile(os.path.join(path, root_name), "READ")
    tree = file.Get("tree")

    amplitudes = []
    for i in range(tree.GetEntries()):       
        tree.GetEntry(i)
        amplitudes.append(tree.amplitude)

    file.Close()
    return amplitudes

def data(root_path, root_name):
    file_name = os.path.splitext(root_name)[0]
    amplitudes = readfile(root_path, root_name)
    mean = np.mean(amplitudes)
    std = np.std(amplitudes)
    # amplitudes = [amplitude*17.925/0.138*0.8847486018957982 for amplitude in amplitudes if amplitude > mean - 3*std and amplitude < mean + 3*std]
    amplitudes = [amplitude*17.925/0.138 for amplitude in amplitudes if amplitude > mean - 3*std and amplitude < mean + 3*std]

    return amplitudes, file_name


def draw(amplitudes, file_name):
    c = ROOT.TCanvas( 'c', 'c', 8000, 6000 )
    c.cd()
 
    minsignal = float(min(amplitudes))
    maxsignal = float(max(amplitudes))
    binnum = 50
    binwidth = (maxsignal - minsignal)/binnum
    wave_graph = ROOT.TH1F('','', binnum + 2, minsignal - binwidth, maxsignal + binwidth)
    for amplitude in amplitudes:
        wave_graph.Fill(amplitude)

    f1 = ROOT.TF1("f1", "landau")
    wave_graph.Fit(f1)

    wave_graph.SetTitle(file_name)
    wave_graph.SetLineColor(1)
    wave_graph.SetLineWidth(2)

    wave_graph.GetXaxis().SetTitle('mV')
    wave_graph.GetXaxis().SetTitleSize(0.05)
    wave_graph.GetXaxis().SetTitleOffset(0.9)
    wave_graph.GetYaxis().SetTitle('events')
    wave_graph.GetYaxis().SetTitleSize(0.05)
    wave_graph.GetYaxis().SetTitleOffset(0.9)
    # wave_graph.GetXaxis().SetRangeUser(0, 1300)
    # wave_graph.GetXaxis().SetLimits(0, 1300)
    wave_graph.Draw()
    maxevent = wave_graph.GetMaximum()

    latex = ROOT.TLatex(0.4*minsignal + 0.6*maxsignal, 0.7*maxevent, f"MPV:{round(f1.GetParameter(1), 3)}mV",)
    latex.SetTextSize(0.05)
    latex.SetTextColor(1)
    latex.SetTextFont(42)
    latex.Draw()

    pdf_path = project_path("bmos", "histogram", "pdf")
    mkdir(pdf_path)

    c.SaveAs(os.path.join(pdf_path, f"{file_name}.pdf",))

    

def main(choose):
    tag = 'proton_80MeV'
    # tag = ''
    root_path = project_path("bmos", "histogram", "root", tag)
    root_names = os.listdir(root_path)

    if choose == "all":
        for root_name in root_names:
            amplitudes, file_name = data(root_path, root_name)
            draw(amplitudes, file_name)
    elif choose == "one":
        c = ROOT.TCanvas( 'c', 'c', 8000, 6000 )
        his = []

        for i in range(len(root_names)):
            c.cd()

            amplitudes, file_name = data(root_path, root_names[i])
            # minsignal = float(min(amplitudes))
            # maxsignal = float(max(amplitudes))
            # binnum = 50
            # binwidth = (maxsignal - minsignal)/binnum
            # his.append(ROOT.TH1F('','', binnum + 2, minsignal - binwidth, maxsignal + binwidth))
            his.append(ROOT.TH1F('','', 150, 0, 1500))

            for amplitude in amplitudes:
                his[i].Fill(amplitude)

            his[i].Draw("same")
            his[i].Fit("landau")

            his[i].SetTitle(tag)
            his[i].SetLineColor(1)
            his[i].SetLineWidth(2)

            his[i].GetXaxis().SetTitle('mV')
            his[i].GetXaxis().SetTitleSize(0.05)
            his[i].GetXaxis().SetTitleOffset(0.9)
            # his[i].GetXaxis().SetRangeUser(0, 1300)
            # his[i].GetXaxis().SetLimits(0, 1300)
            his[i].GetYaxis().SetTitle('events')
            his[i].GetYaxis().SetTitleSize(0.05)
            his[i].GetYaxis().SetTitleOffset(0.9)
            his[i].GetYaxis().SetRangeUser(0, 150)

        pdf_path = project_path("bmos", "histogram", "pdf", tag)
        mkdir(pdf_path)
        c.SaveAs(os.path.join(pdf_path, f"{file_name}_all.pdf",))

    
    
