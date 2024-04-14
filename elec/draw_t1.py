#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import time
import os
from array import array
import ROOT
import csv

def T1():
    c = ROOT.TCanvas('c', '', 800, 600)
    c.SetFillColor(0)
    c.SetFrameFillColor(0)
    ROOT.gStyle.SetPadColor(0)
    ROOT.gStyle.SetCanvasColor(0)
    ROOT.gStyle.SetOptStat(0)
    c.SetLeftMargin(0.15)
    c.SetRightMargin(0.15)
    c.SetTopMargin(0.1)
    c.SetBottomMargin(0.15)

    mg=ROOT.TMultiGraph("mg","")
    
    c_file = ROOT.TFile("output/pintct/NJU-PIN/sim-TCT-current0.5.root")
    c_t = c_file.Get("tree")
    c_n = c_t.Draw("1000*current0:time","","goff")
    graph1 = ROOT.TGraph(c_n,c_t.GetV2(),c_t.GetV1())
    #A-mA
    """
    m_file = ROOT.TFile("output/pintct/NJU-PIN/sim-TCT0.5.root")
    m_t = m_file.Get("tree")
    m_n = m_t.Draw("volt:time","","goff")
    graph2 = ROOT.TGraph(m_n,m_t.GetV2(),m_t.GetV1())
    #mV
    """
    in_file = ROOT.TFile("output/pintct/NJU-PIN/input0.5.root")
    in_t = in_file.Get("tree")
    in_n = in_t.Draw("1000*current:time","","goff")
    graph3 = ROOT.TGraph(in_n,in_t.GetV2(),in_t.GetV1())

    s_volt = []
    s_t = []
    J=0
    with open('output/t1.raw') as f:
        lines = f.readlines()
        for line in lines:
            s_volt.append(float(line.split()[1]))
            s_t.append(float(line.split()[0]))
            J=J+1
    graph4 = ROOT.TGraph()
    for i in range(J):
        graph4.SetPoint(i, s_t[i], s_volt[i])
    

    #graph4 = ROOT.TGraph("output/t1.raw","%D %D" )
    graph1.SetLineColor(8)
    graph1.SetLineWidth(2)

    #graph2.SetLineColor(2)
    #graph2.SetLineWidth(2)
    
    graph3.SetLineColor(4)
    graph3.SetLineWidth(2)

    graph4.SetLineColor(6)
    graph4.SetLineWidth(2)

    mg.Add(graph1)
    #mg.Add(graph2)
    mg.Add(graph3)
    mg.Add(graph4)
    mg.GetYaxis().SetTitle('Current [mA]')
    mg.GetXaxis().SetTitle('Time [s]')
    mg.GetYaxis().SetLabelSize(0.05)
    mg.GetYaxis().SetTitleSize(0.05)
    mg.GetXaxis().SetLabelSize(0.05)
    mg.GetXaxis().SetTitleSize(0.05)

    legend = ROOT.TLegend(0.5, 0.3, 0.8, 0.6)
    #legend.AddEntry(graph2, "voltage:simulation", "l")
    legend.AddEntry(graph1, "current:e+h", "l")
    legend.AddEntry(graph3, "current:T1-input", "l")
    legend.AddEntry(graph4, "voltage:T1-output", "l")
    legend.SetBorderSize(0)

    mg.Draw('al')
    legend.Draw("")

    now = time.strftime("%Y_%m%d_%H%M%S")
    path = os.path.join("output/fig", str(now))
    os.makedirs(path)
    c.SaveAs(os.path.join('output/fig', str(now), 't1.pdf'))

if __name__ == '__main__':
    T1()