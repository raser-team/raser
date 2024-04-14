#!/usr/bin/env python
import numpy as np
import ROOT

def draw_double_iv(path1, path2, start):
    data1=np.loadtxt(path1, skiprows=start-1, comments="END")
    v1=-data1.T[0]
    i1=-data1.T[1]
    data2=np.loadtxt(path2, skiprows=start-1, comments="END")
    v2=-data2.T[0]
    i2=-data2.T[1]

    c = ROOT.TCanvas('c', '', 800, 600)
    c.SetFillColor(0)
    c.SetFrameFillColor(0)
    ROOT.gStyle.SetPadColor(0)
    ROOT.gStyle.SetCanvasColor(0)
    ROOT.gStyle.SetOptStat(0)
    c.SetLeftMargin(0.15)
    c.SetBottomMargin(0.15)

    c.SetLogy()

    mg=ROOT.TMultiGraph("mg","")
    n1=len(v1)
    graph1 = ROOT.TGraph(n1,v1,i1)
    n2=len(v2)
    graph2 = ROOT.TGraph(n2,v2,i2)

    graph1.SetLineColor(4)
    graph2.SetLineColor(6)
    graph1.SetMarkerColor(4)
    graph2.SetMarkerColor(6)
    graph1.SetMarkerStyle(20)
    graph2.SetMarkerStyle(22)

    mg.Add(graph1)
    mg.Add(graph2)
    mg.Draw('apl')
    mg.SetMinimum(7e-10)
    mg.SetMaximum(1.5e-4)
    
    mg.GetYaxis().SetTitle('Current [A]')
    mg.GetXaxis().SetTitle('Reverse Bias Voltage [V]')
    mg.GetYaxis().SetLabelSize(0.05)
    mg.GetYaxis().SetTitleSize(0.05)
    mg.GetXaxis().SetLabelSize(0.05)
    mg.GetXaxis().SetTitleSize(0.05)

    legend = ROOT.TLegend(0.2, 0.6, 0.4, 0.75)
    legend.AddEntry(graph1, "p-i-n", "pl")
    legend.AddEntry(graph2, "LGAD", "pl")
    legend.SetTextSize(27)
    legend.SetTextFont(43)

    legend.SetBorderSize(0)
    legend.SetFillColor(0)
    legend.Draw()

    c.SaveAs("output/iv_comparison.pdf")


def draw_double_cv(path1, path2, start):
    data1=np.loadtxt(path1, skiprows=start-1, comments="END")
    v1=-data1.T[0]
    c1=data1.T[1]
    data2=np.loadtxt(path2, skiprows=start-1, comments="END")
    v2=-data2.T[0]
    c2=data2.T[1]

    c = ROOT.TCanvas('c', '', 800, 600)
    c.SetFillColor(0)
    c.SetFrameFillColor(0)
    ROOT.gStyle.SetPadColor(0)
    ROOT.gStyle.SetCanvasColor(0)
    ROOT.gStyle.SetOptStat(0)
    c.SetLeftMargin(0.15)
    c.SetBottomMargin(0.15)


    mg=ROOT.TMultiGraph("mg","")
    n1=len(v1)
    graph1 = ROOT.TGraph(n1,v1,c1**(-2))
    n2=len(v2)
    graph2 = ROOT.TGraph(n2,v2,c2**(-2))

    graph1.SetLineColor(4)
    graph2.SetLineColor(6)
    graph1.SetMarkerColor(4)
    graph2.SetMarkerColor(6)
    graph1.SetMarkerStyle(20)
    graph2.SetMarkerStyle(22)

    mg.Add(graph1)
    mg.Add(graph2)
    mg.Draw('apl')
    
    mg.GetYaxis().SetTitle('Capacitance^{-2} [F^{-2}]')
    mg.GetXaxis().SetTitle('Reverse Bias Voltage [V]')
    mg.GetYaxis().SetLabelSize(0.05)
    mg.GetYaxis().SetTitleSize(0.05)
    mg.GetXaxis().SetLabelSize(0.05)
    mg.GetXaxis().SetTitleSize(0.05)

    legend = ROOT.TLegend(0.6, 0.2, 0.8, 0.35)
    legend.AddEntry(graph1, "p-i-n", "pl")
    legend.AddEntry(graph2, "LGAD", "pl")
    legend.SetTextSize(27)
    legend.SetTextFont(43)

    legend.SetBorderSize(0)
    legend.SetFillColor(0)
    legend.Draw()

    c.SaveAs("output/cv_comparison.pdf")

pin_iv = '/afs/ihep.ac.cn/users/f/fuchenxi/disk/1/hpk_ivcv/HPK-EPI-W2-200-DS-SE5PINNM-01/HPK-EPI-W2-200-DS-SE5PINNM-01_2019-09-03_1.iv'
pin_cv = '/afs/ihep.ac.cn/users/f/fuchenxi/disk/1/hpk_ivcv/HPK-EPI-W2-200-DS-SE5PINNM-01/HPK-EPI-W2-200-DS-SE5PINNM-01_2019-09-03_1.cv'
lgad_iv = '/afs/ihep.ac.cn/users/f/fuchenxi/disk/1/hpk_ivcv/HPK-EPI-W2-200-DS-SE5-01/HPK-EPI-W2-200-DS-SE5-01_2019-08-26_1.iv'
lgad_cv = '/afs/ihep.ac.cn/users/f/fuchenxi/disk/1/hpk_ivcv/HPK-EPI-W2-200-DS-SE5-01/HPK-EPI-W2-200-DS-SE5-01_2019-08-28_1.cv'
iv_start = 66
cv_start = 71
draw_double_iv(pin_iv, lgad_iv, iv_start)
draw_double_cv(pin_cv, lgad_cv, cv_start)