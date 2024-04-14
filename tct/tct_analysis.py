#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""
author: wanghaobo
time: 2022.12.25
Use: 1.Read the data of Raser eTCT induced current
     2.Add experimental noise on induced current
     3.Get the risertime,charge collection and velocity profile
"""

from array import array
import contextlib
import os
import sys
import ROOT
import math
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import raser
    
def collect_data(path, model, volt_scale, time_scale, keys, key_name):
    amplitude = array("d")
    risetime = array("d")
    charge = array("d")
    velprof = array("d")
    difprof = array("d")
    volts = []
    times = []

    for key in keys:
        volt=array("d",[0.])
        time=array("d",[0.])
        rootfile=path+model+str(key)+key_name+".root"
        volt,time=read_rootfile(rootfile, volt_scale, time_scale)
        volts.append(volt)
        times.append(time)
        J=len(volt)

        amplitude.append(get_amplitude(volt,J))
        charge.append(get_charge(volt,J))
        velprof.append(get_velprof(volt,time,J))
        risetime.append(get_risetime(volt,time,J))
        difprof.append(get_difprof(volt,time,J))
      
    return amplitude, charge, risetime, velprof, difprof, volts, times

def read_rootfile(rootfile,volt_scale,time_scale):
    J=0
    v1=array("d")
    t1=array("d")
    myFile = ROOT.TFile(str(rootfile))
    myt = myFile.tree
    for entry in myt:
       v1.append(volt_scale*entry.volt)
       t1.append(time_scale*entry.time)
       J=J+1
    return v1,t1

def add_noise(rootfile,J,v1,t1):
    v2=array("d",[0.])
    t2=array("d",[0.])
    noise=np.array([0])
    fout = ROOT.TFile("noise_"+str(rootfile), "RECREATE")
    t_out = ROOT.TTree("tree", "signal")
    t_out.Branch("volt", v2, "volt/D")
    t_out.Branch("time", t2, "time/D")
    for i in range(J):
          t2[0]=t1[i]
          v2[0]=v1[i]+noise[i]
          t_out.Fill()
    t_out.Write()
    fout.Close()

def get_amplitude(volt,J):
    Vmax = max(volt)
    for Max in range(J):
        if volt[Max] - Vmax > -1e-5*Vmax:
            break
    for min in range(Max,0,-1):
        if volt[min-1] > volt[min]:
            #Vmin = volt[min]
            Vmin = 0
            break
        else:
            #Vmin = volt[0]
            Vmin = 0
    return(Vmax-Vmin)

def get_charge(volt,J):
    sum_volt=0
    for j in range(J):
        sum_volt+=volt[j]
    return sum_volt*50e-12/(100*0.65e-9/2.2/(3.7e-12))*1e15
    # t_bin = 50e-12 A = 100 τ_RC_D = 0.65e-9/2.2 C_D = 3.7e-12 result in fC

def get_velprof(volt,time,J):
    t = 1.1 #ns
    for j in range(J):
        if time[j] >= t:
            break
    return volt[j]

def get_difprof(volt,time,J):
    max_diff = 0
    for i in range(J-1):
        if volt[i+1]-volt[i] > max_diff:
            max_diff = volt[i+1]-volt[i]
    return max_diff/(100*0.65e-9/2.2/(3.7e-12))/50e-12/2.24e-4/16992*1e-6
    # A = 100 τ_RC_D = 0.65e-9/2.2 C_D = 3.7e-12 t_bin = 50e-12 k_2hν = 2.24e-4 E_p/hν = 19992 result in μm

def get_risetime(volt,time,J):
    x=array("d")
    y=array("d")
    Vmax=max(volt)
    for Max in range(J):
        if volt[Max] - Vmax > -1e-5*Vmax:
            break
    for min in range(Max,0,-1):
        if volt[min-1] > volt[min]and volt[min]<0.1*Vmax:
            Vmin = volt[min]
            break
        else:
            Vmin = volt[0]
    for k in range(J):
        if (volt[k] - Vmin)<0.1*(Vmax - Vmin)<(volt[k+1] - Vmin):
            break
    for l in range(J):
        if (volt[l-1] - Vmin)<0.9*(Vmax - Vmin)<(volt[l] - Vmin):
            break
    n=l-k
    for j in range(k,l+1):
        x.append(time[j])
        y.append(volt[j])

    graph1 = ROOT.TGraph(n,x,y)
    f=ROOT.TF1("f","[0]+[1]*x",0,10)
    graph1.Fit(f,"Q")
    b=f.GetParameter(1)
    c=f.GetParameter(0)
    e1=np.true_divide((0.2*(Vmax-Vmin)-c),b)
    e2=np.true_divide((0.8*(Vmax-Vmin)-c),b)
    risetime=np.true_divide((e2-e1),0.6)
    return risetime

def draw_graphs(array1,keys,key_name,name,path):
    n=len(array1)
    g = ROOT.TCanvas('g', '', 800, 600)
    g.SetFillColor(0)
    g.SetFrameFillColor(0)
    ROOT.gStyle.SetPadColor(0)
    ROOT.gStyle.SetCanvasColor(0)
    ROOT.gStyle.SetOptStat(0)
    g.SetLeftMargin(0.15)
    g.SetRightMargin(0.15)
    g.SetTopMargin(0.1)
    g.SetBottomMargin(0.15)

    graph=ROOT.TGraph(n,keys,array1)
    graph.SetMarkerStyle(3)
    graph.Draw('ap')

    legend = ROOT.TLegend(0.6,0.7, 0.83, 0.89)
    legend.AddEntry(graph,"RASER Simulation", "p")
    legend.SetTextSize(18)
    legend.SetTextFont(43)
    legend.SetBorderSize(0)
    legend.SetFillColor(0)
    legend.Draw()

    g.SaveAs(path+name+".pdf")
  
    return

def draw_double_graphs(array1,array2,keys1,keys2,key_name,name,path):
    c = ROOT.TCanvas('c', '', 800, 600)
    c.SetFillColor(0)
    c.SetFrameFillColor(0)
    ROOT.gStyle.SetPadColor(0)
    ROOT.gStyle.SetCanvasColor(0)
    ROOT.gStyle.SetOptStat(0)
    c.SetLeftMargin(0.15)
    c.SetBottomMargin(0.15)

    mg=ROOT.TMultiGraph("mg","")
    n1=len(array1)
    graph1 = ROOT.TGraph(n1,keys1,array1)
    n2=len(array2)
    graph2 = ROOT.TGraph(n2,keys2,array2)

    graph1.SetLineColor(2)
    graph2.SetLineColor(1)
    graph1.SetMarkerColor(2)
    graph2.SetMarkerColor(1)
    graph1.SetMarkerStyle(26)
    graph2.SetMarkerStyle(4)

    mg.Add(graph1)
    mg.Add(graph2)
    mg.Draw('ap')

    if name == 'Amplitude':
        Y_title = 'Amplitude [V]'
        if 'LGAD' in path:
            mg.GetYaxis().SetRangeUser(0,1.13)
        else:
            mg.GetYaxis().SetRangeUser(0,0.04)

    if name == 'Charge':
        Y_title = 'Charge [fC]'
        if 'LGAD' in path:
            mg.GetYaxis().SetRangeUser(0,200)
        else:
            mg.GetYaxis().SetRangeUser(0,6)

    if name == 'VelProf':
        Y_title = 'Ve+Vh [a.u.]'
        if 'LGAD' in path:
            mg.GetYaxis().SetRangeUser(0,0.1)
        else:
            mg.GetYaxis().SetRangeUser(0,0.015)

    if name == 'RiseTime':
        Y_title = 'RiseTime [ns]'
        if 'LGAD' in path:
            mg.GetYaxis().SetRangeUser(0,1.5)
        else:
            mg.GetYaxis().SetRangeUser(0,1.5)

    if name == 'DifProf':
        Y_title = '1/\sigma [\mu m^{-1}]'
        if 'LGAD' in path:
            mg.GetYaxis().SetRangeUser(0,0.1)
        else:
            mg.GetYaxis().SetRangeUser(0,0.003)
    
    mg.GetYaxis().SetTitle(Y_title)
    if key_name == "z":
        mg.GetXaxis().SetTitle('z [\mu m]')
    elif key_name == "voltage":
        mg.GetXaxis().SetTitle('Reverse bias voltage [V]')
    mg.GetYaxis().SetLabelSize(0.05)
    mg.GetYaxis().SetTitleSize(0.05)
    mg.GetXaxis().SetLabelSize(0.05)
    mg.GetXaxis().SetTitleSize(0.05)

    legend = ROOT.TLegend(0.45,0.65, 0.81, 0.86)
    legend.AddEntry(graph1, "RASER simulation", "p")
    legend.AddEntry(graph2, "TCT measurement", "p")
    legend.SetTextSize(27)
    legend.SetTextFont(43)

    legend.SetBorderSize(0)
    legend.SetFillColor(0)
    legend.Draw()

    c.SaveAs(path+name+"_"+key_name+"_comparison.pdf")

def draw_triple_graphs(array1,array2,array3,keys1,keys2,keys3,key_name,name,path):
    c = ROOT.TCanvas('c', '', 800, 600)
    c.SetFillColor(0)
    c.SetFrameFillColor(0)
    ROOT.gStyle.SetPadColor(0)
    ROOT.gStyle.SetCanvasColor(0)
    ROOT.gStyle.SetOptStat(0)
    c.SetLeftMargin(0.15)
    c.SetBottomMargin(0.15)

    mg=ROOT.TMultiGraph("mg","")
    n1=len(array1)
    graph1 = ROOT.TGraph(n1,keys1,array1)
    n2=len(array2)
    graph2 = ROOT.TGraph(n2,keys2,array2)
    n3=len(array3)
    graph3 = ROOT.TGraph(n3,keys3,array3)

    graph1.SetLineColor(2)
    graph2.SetLineColor(1)
    graph3.SetLineColor(35)
    graph1.SetMarkerColor(2)
    graph2.SetMarkerColor(1)
    graph3.SetMarkerColor(35)
    graph1.SetMarkerStyle(26)
    graph2.SetMarkerStyle(4)
    graph3.SetMarkerStyle(32)

    graph3.SetLineWidth(4)

    # fill the background
    # gain layer
    x1 = array("d",[0,2,2,0,0])
    y1 = array("d",[0,0,0.1,0.1,0])
    excl1 = ROOT.TGraph(5,x1,y1)
    excl1.SetLineColor(ROOT.kPink+1)
    excl1.SetFillColor(ROOT.kPink+1)
    # bulk
    x2 = array("d",[2,50,50,2,2])
    y2 = array("d",[0,0,0.1,0.1,0])
    excl2 = ROOT.TGraph(5,x2,y2)
    excl2.SetLineColor(ROOT.kCyan-10)
    excl2.SetFillColor(ROOT.kCyan-10)

    mg.Add(excl1,"f")
    mg.Add(excl2,"f")

    mg.Add(graph1,"p")
    mg.Add(graph2,"p")
    mg.Add(graph3,"l")
    mg.Draw("a*")

    ROOT.gPad.RedrawAxis()
    ROOT.gPad.RedrawAxis("G")

    if name == 'Amplitude':
        Y_title = 'Amplitude [V]'
        if 'LGAD' in path:
            mg.GetYaxis().SetRangeUser(0,1.13)
        else:
            mg.GetYaxis().SetRangeUser(0,0.04)

    if name == 'Charge':
        Y_title = 'Charge [fC]'
        if 'LGAD' in path:
            mg.GetYaxis().SetRangeUser(0,200)
        else:
            mg.GetYaxis().SetRangeUser(0,6)

    if name == 'VelProf':
        Y_title = 'Ve+Vh [a.u.]'
        if 'LGAD' in path:
            mg.GetYaxis().SetRangeUser(0,0.1)
        else:
            mg.GetYaxis().SetRangeUser(0,0.015)

    if name == 'RiseTime':
        Y_title = 'RiseTime [ns]'
        if 'LGAD' in path:
            mg.GetYaxis().SetRangeUser(0,1.5)
        else:
            mg.GetYaxis().SetRangeUser(0,1.5)

    if name == 'DifProf':
        Y_title = '1/\sigma [\mu m^{-1}]'
        if 'LGAD' in path:
            mg.GetYaxis().SetRangeUser(0,0.1)
        else:
            mg.GetYaxis().SetRangeUser(0,0.003)

        Box=ROOT.TBox(8,0.03,42,0.05)
        Box.SetLineColor(ROOT.kRed)
        Box.SetFillStyle(0)
        Box.SetLineStyle(2)
        Box.Draw()

        l=ROOT.TLatex()
        l.SetTextSize(20)
        l.SetTextFont(43)
        l.DrawLatex(11,0.022,"Full Gaussian shape region")
    
    mg.GetYaxis().SetTitle(Y_title)
    if key_name == "z":
        mg.GetXaxis().SetTitle('z [\mu m]')
    elif key_name == "voltage":
        mg.GetXaxis().SetTitle('Reverse bias voltage [V]')
    mg.GetYaxis().SetLabelSize(0.05)
    mg.GetYaxis().SetTitleSize(0.05)
    mg.GetXaxis().SetLabelSize(0.05)
    mg.GetXaxis().SetTitleSize(0.05)

    legend = ROOT.TLegend(0.4,0.65, 0.76, 0.85)
    legend.AddEntry(graph1, "RASER simulation", "p")
    legend.AddEntry(graph2, "TCT measurement", "p")
    legend.AddEntry(graph3, "Expected value", "l")
    legend.SetTextSize(27)
    legend.SetTextFont(43)

    legend.SetBorderSize(0)
    legend.SetFillColor(0)
    legend.Draw()

    c.SaveAs(path+name+"_"+key_name+"_theory_comparison.pdf")

def draw_double_signals(time_1,time_2,signal_1,signal_2,key,key_name,path):
    c = ROOT.TCanvas('c', '', 800, 600)
    c.SetFillColor(0)
    c.SetFrameFillColor(0)
    ROOT.gStyle.SetPadColor(0)
    ROOT.gStyle.SetCanvasColor(0)
    ROOT.gStyle.SetOptStat(0)
    c.SetLeftMargin(0.15)
    c.SetBottomMargin(0.15)

    mg=ROOT.TMultiGraph("mg","")
    n1=len(time_1)
    graph1 = ROOT.TGraph(n1,time_1,signal_1)
    n2=len(time_2)
    graph2 = ROOT.TGraph(n2,time_2,signal_2)

    graph1.SetLineColor(2)
    graph2.SetLineColor(1)
    graph1.SetMarkerColor(2)
    graph2.SetMarkerColor(1)
    graph1.SetMarkerStyle(26)
    graph2.SetMarkerStyle(4)

    mg.Add(graph1)
    mg.Add(graph2)
    mg.Draw('apl')
    
    mg.GetYaxis().SetTitle('Signal [V]')
    mg.GetXaxis().SetTitle('Time [ns]')
    mg.GetYaxis().SetLabelSize(0.05)
    mg.GetYaxis().SetTitleSize(0.05)
    mg.GetXaxis().SetLabelSize(0.05)
    mg.GetXaxis().SetTitleSize(0.05)

    mg.GetXaxis().SetLimits(0,10)

    legend = ROOT.TLegend(0.45,0.65, 0.81, 0.86)
    legend.AddEntry(graph1, "RASER simulation", "pl")
    legend.AddEntry(graph2, "TCT measurement", "pl")
    legend.SetTextSize(27)
    legend.SetTextFont(43)

    legend.SetBorderSize(0)
    legend.SetFillColor(0)
    legend.Draw()

    c.SaveAs(path+str(key)+key_name+"_comparison.pdf")

def analysis_depth(path,output_path,pulse_energy_scale):
    Z = array("d")
    rel_z = array("d")
    for L in range(-8,59):
        Z.append(L)
        rel_z.append(round(0.02*L,2))

    if "experiment" in sys.argv:
        amplitude, charge, risetime, velprof, difprof, volts, times = collect_data(path, "sim-TCT", pulse_energy_scale, 1e9, rel_z, 'fz_rel')
        amplitude_exp, charge_exp, risetime_exp, velprof_exp, difprof_exp, volts_exp, times_exp = collect_data(path, "exp-TCT", 1, 1, rel_z, 'fz_rel')
        draw_double_graphs(amplitude,amplitude_exp,Z,Z,"z","Amplitude",output_path)
        draw_double_graphs(charge,charge_exp,Z,Z,"z","Charge",output_path)
        draw_double_graphs(risetime,risetime_exp,Z,Z,"z","RiseTime",output_path)
        draw_double_graphs(velprof,velprof_exp,Z,Z,"z","VelProf",output_path)
        draw_double_graphs(difprof,difprof_exp,Z,Z,"z","DifProf",output_path)

        velprof_theory, difprof_theory = dif_cal()
        Z_vel = array("d")
        Z_dif = array("d")
        for L in range(0,51):
            Z_vel.append(L)
        for L in range(2,51):
            Z_dif.append(L)
        draw_triple_graphs(velprof,velprof_exp,velprof_theory,Z,Z,Z_vel,"z","VelProf",output_path)   
        draw_triple_graphs(difprof,difprof_exp,difprof_theory,Z,Z,Z_dif,"z","DifProf",output_path)   

        for volt,time,volt_exp,time_exp,z in zip(volts, times, volts_exp, times_exp, list(Z)):
            draw_double_signals(time,time_exp,volt,volt_exp,z,"z",output_path)

    else:
        amplitude, charge, risetime, velprof, difprof, volts, times= collect_data(path, "sim-TCT", pulse_energy_scale, 1e9, rel_z, 'fz_rel')
        draw_graphs(amplitude,Z,"z","Amplitude",output_path)
        draw_graphs(charge,Z,"z","Charge",output_path)
        draw_graphs(risetime,Z,"z","RiseTime",output_path)
        draw_graphs(velprof,Z,"z","VelProf",output_path)
        draw_graphs(difprof,Z,"z","DifProf",output_path)

def analysis_voltage(path,output_path,pulse_energy_scale):
    V = array("d")
    VN = array("i")
    for L in range(60,220,20):
        V.append(L)
        VN.append(-L)

    if "experiment" in sys.argv:
        amplitude, charge, risetime, velprof, difprof, volts, times = collect_data(path, "sim-TCT", pulse_energy_scale, 1e9, V, 'voltage')
        amplitude_exp, charge_exp, risetime_exp, velprof_exp, difprof_exp, volts_exp, times_exp = collect_data(path, "exp-TCT", 1, 1, VN, 'voltage')
        draw_double_graphs(charge,charge_exp,V,V,"voltage","Charge",output_path)

        for volt,time,volt_exp,time_exp,v in zip(volts, times, volts_exp, times_exp, list(V)):
            draw_double_signals(time,time_exp,volt,volt_exp,v,"voltage",output_path)

    else:
        amplitude, charge, risetime, velprof, difprof, volts, times= collect_data(path, "sim-TCT", pulse_energy_scale, 1e9, V, 'voltage')
        draw_graphs(charge,V,"voltage","Charge",output_path)

def dif_cal():
    lgad_paras = ["det_name=HPK-Si-LGAD","parfile=paras/setting.json"]
    lgad_set = raser.Setting(lgad_paras)
    my_lgad = raser.R3dDetector(lgad_set)
    my_lgad_field = raser.FenicsCal(my_lgad,lgad_set.fenics)

    field = array("d") # in [0,50]
    dif = array("d")   # in [2,50]
    E_2 = my_lgad_field.get_e_field(650,650,2)[2]
    for i in range(0,51):
        E = my_lgad_field.get_e_field(650,650,i)[2]
        field.append(0.002*E)
        if i not in range(2,51):
            continue
        fE = (E_2/E)**2
        C = (350e-12*1e5*1e6/2)**2/2/np.log(2) # τ^2v^2
        z1C0 = (6.8/2)**2 # w_0^2/4
        z1C2 = 1.064**2/4/np.pi**2/(6.8/2)**2/11.9**2
        z2 = 2.8
        alpha = 9.87e-4
        def f(x):
            return np.exp(-alpha*x)*alpha/(C + (z1C2 * x**2 + z1C0) * fE + z2/2 * (fE-1))**0.5

        n = 1301
        x_list = np.linspace(0, 1300, n) # in cm
        f_list = np.zeros(n)
        for j in range(n):
            f_list[j] = f(x_list[j])

        int_f = 0
        for j in range(n-1):
            int_f += (f_list[j] + f_list[j+1]) * (x_list[j+1] - x_list[j]) /2

        dif.append(int_f)

    return field,dif

def main():
    path=sys.argv[1]
    output_path=sys.argv[2]
    if not os.access(output_path, os.F_OK):
        os.makedirs(output_path, exist_ok=True) 
    if 'LGAD' in path:
        pulse_energy_scale = 1.58
    else:
        pulse_energy_scale = 1
    # the pulse energy difference in experiment
    analysis_depth(path,output_path,pulse_energy_scale)
    analysis_voltage(path,output_path,pulse_energy_scale)             

if __name__ == "__main__":
    main()
