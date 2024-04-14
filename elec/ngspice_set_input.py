import os
import ROOT
from array import array

def set_input(my_current,my_l,my_d,key):
    if "planar3D" in my_d.det_model or "planarRing" in my_d.det_model:
        path = os.path.join('output', 'pintct', my_d.det_name, )
    elif "lgad3D" in my_d.det_model:
        path = os.path.join('output', 'lgadtct', my_d.det_name, )
    L = eval("my_l.{}".format(key))
    current=[]
    time=[]
    myFile = ROOT.TFile(os.path.join(path,"sim-TCT-current")+str(L)+".root")
    myt = myFile.tree
    for entry in myt:
       current.append(entry.current0)
       time.append(entry.time)
    input_c=[]
    if abs(min(current))>max(current): #set input signal
        c_max=min(current)
        for i in range(0, len(current)):
            if current[i] < c_max * 0.01:
                input_c.append(str(0))
                input_c.append(str(0))
                input_c.append(str(time[i]))
                input_c.append(str(0))
                break
            else:
                current[i]=0
        for j in range(i, len(current)):
            input_c.append(str(time[j]))
            input_c.append(str(current[j]))
            if current[j] > c_max * 0.01:
                break
        input_c.append(str(time[j]))
        input_c.append(str(0))
        input_c.append(str(time[len(time)-1]))
        input_c.append(str(0))
        for k in range(j, len(current)):
            current[i]=0
    else:
        c_max=max(current)
        for i in range(0, len(current)):
            current[i]=0
            if current[i] > c_max * 0.01:
                input_c.append(str(0))
                input_c.append(str(0))
                input_c.append(str(time[i]))
                input_c.append(str(0))
                break
        for j in range(i, len(current)):
            input_c.append(str(time[j]))
            input_c.append(str(current[j]))
            if current[j] < c_max * 0.01:
                break
        input_c.append(str(time[j]))
        input_c.append(str(0))
        input_c.append(str(time[len(time)-1]))
        input_c.append(str(0))
        for k in range(j, len(current)):
            current[i]=0
    in_put=array("d",[0.])
    t=array("d",[0.])
    fout = ROOT.TFile(os.path.join(path, "input") + str(L) + ".root", "RECREATE")
    t_out = ROOT.TTree("tree", "signal")
    t_out.Branch("time", t, "time/D")
    t_out.Branch("current", in_put, "current/D")
    for m in range(my_current.n_bin):
        in_put[0]=current[m]
        t[0]=time[m]
        t_out.Fill()
    t_out.Write()
    fout.Close()
    return input_c
