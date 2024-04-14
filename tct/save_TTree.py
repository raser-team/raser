import os
from util.output import output
from array import array
import ROOT

def save_signal_TTree(dset,my_d,key,ele_current,my_f):
    if "planar3D" in my_d.det_model or "planarRing" in my_d.det_model:
        path = os.path.join("output", "pintct", dset.det_name, "data",)
    elif "lgad3D" in my_d.det_model:
        path = os.path.join("output", "lgadtct", dset.det_name, "data",)
    create_path(path) 
    for j in range(my_f.read_ele_num):
        volt = array('d', [999.])
        time = array('d', [999.])
        if my_f.read_ele_num==1:
            fout = ROOT.TFile(os.path.join(path, "sim-TCT") + str(key) + ".root", "RECREATE")
        else:
            fout = ROOT.TFile(os.path.join(path, "sim-TCT") + str(key)+"No_"+str(j)+".root", "RECREATE")
        t_out = ROOT.TTree("tree", "signal")
        t_out.Branch("volt", volt, "volt/D")
        t_out.Branch("time", time, "time/D")
        for i in range(ele_current.CSA_ele[j].GetNbinsX()):
            time[0]=i*ele_current.time_unit
            volt[0]=ele_current.CSA_ele[j][i]
            t_out.Fill()
        t_out.Write()
        fout.Close()
