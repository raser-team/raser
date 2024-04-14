#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import os
import sys
#sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import raser

# TODO: Need to be rewritten or deleted!

import time
from . import save_TTree
from array import array
import ROOT

args = sys.argv[1:]
start = time.time()
dset = raser.Setting(args)
if "parameter_alter=True" in args:
    # need to put the changed value at the end of the parameter list
    key,_,value=args[-1].rpartition('=')
    value=float(value)
    dset.laser_paras.update({key:value})
my_d = raser.R3dDetector(dset)
my_f = raser.FenicsCal(my_d, dset.fenics)
my_l = raser.TCTTracks(my_d, dset.laser)

my_current = raser.CalCurrentLaser(my_d, my_f, my_l)
ele_current = raser.Amplifier(my_current, dset.amplifier)
save_TTree.save_signal_TTree(dset,my_d,my_l.fx_rel,ele_current,my_f)
my_current.save_current(dset,my_d,my_l,my_f,"fx_rel")

current_SiC = array("d")
T_SiC = array("d")

myFile = ROOT.TFile("output/pintct/NJU-PIN/sim-TCT-current0.5.root")
myt = myFile.tree
for entry in myt:
    current_SiC.append(entry.current0 * 1e3)
    T_SiC.append(entry.time * 1e9)

volt_ele = array("d")
T_ele = array("d")

myFile = ROOT.TFile("output/pintct/NJU-PIN/sim-TCT0.5.root")
myt = myFile.tree
for entry in myt:
    volt_ele.append(entry.volt)
    T_ele.append(entry.time * 1e9)

c_max = min(current_SiC)
for i in range(0, len(current_SiC)):
    if current_SiC[i] < c_max * 0.05:
        t1 = T_SiC[i]
        for j in range(i, len(current_SiC)):
            if current_SiC[j] == c_max:
                t2 = T_SiC[j]
            if current_SiC[j] > c_max * 0.05:
                t3 = T_SiC[j]
                break
        break

t_start = t1
t_rise = t2 - t1
t_fall = t3 - t2

with open('paras/T1.cir', 'r') as f:
    lines = f.readlines()
    lines[113] = 'I1 2 0 pulse(0 ' + str(c_max) + 'u ' + str(t_start) + 'n ' + str(t_rise) + 'n ' + str(t_fall) + 'n 0.00000001n ' + str((T_ele[len(T_ele) - 1])) + 'n 0)\n'
    lines[140] = 'tran 0.1p ' + str((T_ele[len(T_ele) - 1])) + 'n\n'
    lines[142] = 'wrdata output/t1.raw v(out)\n'
    f.close()
with open('output/T1_tmp.cir', 'w') as f:
    f.writelines(lines)
    f.close()

