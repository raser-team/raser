#!/usr/bin/env python3
import sys
import os
import math
import ROOT
from array import array

def save_experiment_data(Vbias, z_init, z_0, t_init, myt, out):

    n = myt.Draw("-(volt-aBlineMean):(time-{})".format(t_init),
                    "Vbias=={}\
                    &&(z-{}-{}>-0.0001)\
                    &&(z-{}-{}<0.0001)\
                    &&((time-{})>0)\
                    &&((time-{})<10)".format(Vbias,z_init,z_0,z_init,z_0,t_init,t_init),
                    "goff")
    graph1 = ROOT.TGraph(n,myt.GetV2(),myt.GetV1())
    v1 = array('d')
    t1 = array('d')
    for i in range(n):
        v1.append(graph1.GetPointY(i))
        t1.append(graph1.GetPointX(i))

    volt = array('d',[999.])
    time = array('d',[999.])
    fout = ROOT.TFile(out+".root", "RECREATE")
    t_out = ROOT.TTree("tree", "signal")
    t_out.Reset()
    t_out.Branch("volt", volt, "volt/D")
    t_out.Branch("time", time, "time/D")
    for i in range(len(t1)):
        time[0]=t1[i]
        volt[0]=v1[i]
        t_out.Fill()
    t_out.Write()
    fout.Close()
    del t_out
    print(out+".root Saved")

if not os.access('output/pintct/HPK-Si-PIN/data/', os.F_OK):
    os.makedirs('output/pintct/HPK-Si-PIN/data/', exist_ok=True) 
if not os.access('output/lgadtct/HPK-Si-LGAD/data/', os.F_OK):
    os.makedirs('output/lgadtct/HPK-Si-LGAD/data/', exist_ok=True)  

myPinFile = ROOT.TFile("/afs/ihep.ac.cn/users/f/fuchenxi/disk/1/edge_voltage_2019_10_24_15_12_57_HPK-EPI-W2-200-DS-SE5PINNM-01.txt.root")
myPinTree = myPinFile.Get("edge")
myLgadFile = ROOT.TFile("/afs/ihep.ac.cn/users/f/fuchenxi/disk/1/edge_voltage_2019_10_09_12_26_57_HPK-EPI-W2-200-DS-SE5-04.txt.root")
myLgadTree = myLgadFile.Get("edge")
# myPinTree.Show(17) # checkout the members

z_init_pin = "11.986"
z_init_lgad = "11.954"
t_init_pin = "10.853"
t_init_lgad = "10.803"

for j in range(-10, 60+1):
    rel_z = 0.02*j
    z_0 = str(1e-3*j) # in milimeter
    save_experiment_data(-200, z_init_pin, z_0, t_init_pin, myPinTree,"output/pintct/HPK-Si-PIN/data/exp-TCT"+str(round(rel_z,2))+"fz_rel")
    save_experiment_data(-200, z_init_lgad, z_0, t_init_lgad, myLgadTree,"output/lgadtct/HPK-Si-LGAD/data/exp-TCT"+str(round(rel_z,2))+"fz_rel")

for V in range(-200, -40, 20):
    z_0 = str(1e-3*25)
    save_experiment_data(V, z_init_pin, z_0, t_init_pin, myPinTree,"output/pintct/HPK-Si-PIN/data/exp-TCT"+str(round(V,0))+"voltage")
    save_experiment_data(V, z_init_lgad, z_0, t_init_lgad, myLgadTree,"output/lgadtct/HPK-Si-LGAD/data/exp-TCT"+str(round(V,0))+"voltage")