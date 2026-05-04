import sys
import os
from array import array
import time
import subprocess
import json
import random

import matplotlib.pyplot as plt
import numpy as np


import ROOT
ROOT.gROOT.SetBatch(True)
from ..device import build_device as bdv
from ..util.output import output




def read_events(events_path, my_d, electrode_index=0):
    #read file
    waveforms = None
    for file in os.listdir(events_path):
        if file.endswith(".root"):
            root_file = os.path.join(events_path, file)
            f = ROOT.TFile(root_file)
            tree = f.Get("tree")
            branches = tree.GetListOfBranches()
            branch_name = f"amplified_waveform_{electrode_index}"
            print(root_file)
            tree.GetEntry(0)
            hist = getattr(tree, branch_name)
            n_bins = hist.GetNbinsX()
            waveform = np.zeros(n_bins)
            times = np.zeros(n_bins)
            for j in range(n_bins):
                waveform[j] = hist.GetBinContent(j + 1)
                times[j] = hist.GetBinCenter(j + 1)
            now = time.strftime("%Y_%m%d_%H%M%S")
            path = output(__file__, my_d.det_name, now)
            draw_fit_curve(waveform, path, 50, my_d.det_name)
            
                
            f.Close()
        plt.plot(times, waveform)

def draw_fit_curve(peaks, path, bins, det_model):
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(peaks)
    x = np.linspace(min(peaks), max(peaks), 200)
    ax.set_xlabel('time')
    ax.set_ylabel('Amplitude [mV]')
    ax.set_title('Waveform')
    ax.legend()
    ax.grid(alpha=0.3)
    fig.savefig(os.path.join(path, f"{det_model}_fit_curve.pdf"))
    plt.close(fig)


def main(kwargs):
    det_name = kwargs['det_name']
    my_d = bdv.Detector(det_name)
    read_events("/afs/ihep.ac.cn/users/s/shaochangpu/raser/output/sweep/NJU-PiN/par_energy_2026-03-28-19-02-50", my_d, electrode_index=0)