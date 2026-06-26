import sys
import os
import math
import time
from array import array

import ROOT
ROOT.gROOT.SetBatch(True)
import numpy as np

from raser.supports.output import create_path

# TODO: tagged orphan file

def get_beam_number(my_g4,ele_current):
    now = time.strftime("%Y_%m%d_%H%M")
    path = "output/" + "beam_monitor/" + now + "/" 
    create_path(path) 
    number = array('d',[999.])
    hittotal = array('d',[999.])
    number[0] = int(-ele_current.max_Broad_Band_height/18.8)
    hittotal[0]=my_g4.hittotal
    fout = ROOT.TFile(path + "beam_monitor.root", "RECREATE")
    t_out = ROOT.TTree("tree", "beam_number")
    t_out.Branch("cal_number", number, "cal_number/D")
    t_out.Branch("real_number", hittotal, "real_number/D")
    t_out.Fill()
    t_out.Write()
    fout.Close()

    c1=ROOT.TCanvas("c1","canvas1",1000,1000)
    h1 = ROOT.TH1F("Edep_device", "Energy deposition in SiC", 100, 0., 0.1)
    for i in range (len(my_g4.edep_devices)):
        h1.Fill(my_g4.edep_devices[i])
    h1.Draw()
    h1.GetXaxis().SetTitle("energy[MeV]")
    h1.GetYaxis().SetTitle("number")
    c1.SaveAs(path+"_energy.pdf")
    c1.SaveAs(path+"_energy.root")

def main():
    # beam monitor main program
    pass