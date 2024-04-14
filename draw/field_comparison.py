#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
'''
@Description: compare the difference of the electric field of p-i-n and LGAD
@Date       : 2023/02/14 17:00:00
@Author     : Chenxi Fu
@version    : 1.0

Usage : 
source ./run raser
raser 'python/paper4/field_comparison.py'
'''

# TODO: Need to be rewritten or deleted!

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import raser
import time
import ROOT
import math

def draw_fields(my_pin_field,my_lgad_field,path):

    c1 = ROOT.TCanvas("c", "canvas",1200, 1000)
    ROOT.gStyle.SetOptStat(ROOT.kFALSE)
    ROOT.gStyle.SetOptFit()
    c1.SetLeftMargin(0.18)
    c1.SetBottomMargin(0.14)

    n = 2000
    lgad_field_histo = ROOT.TH1F("","",n,0,50)
    lgad_field_histo.GetXaxis().SetTitle("z[\mu m]") 
    lgad_field_histo.GetYaxis().SetTitle("E[V/\mu m]") 
    pin_field_histo = ROOT.TH1F("","",n,0,50)
    pin_field_histo.GetXaxis().SetTitle("z[\mu m]") 
    pin_field_histo.GetYaxis().SetTitle("E[V/\mu m]") 

    for i in range(n):
        z = (i+1)*50/n
        le = my_lgad_field.get_e_field(650,650,z-0.01)[2]
        lgad_field_histo.SetBinContent(i+1,le)
        pe = my_pin_field.get_e_field(650,650,z-0.01)[2]
        pin_field_histo.SetBinContent(i+1,pe)

    lgad_field_histo.SetTitle("")
    lgad_field_histo.SetLineColor(6)
    lgad_field_histo.SetMarkerColor(6)
    lgad_field_histo.SetMarkerStyle(20)
    lgad_field_histo.Draw("HIST")
    lgad_field_histo.Draw("SAME P")
    pin_field_histo.SetLineColor(4)
    pin_field_histo.SetMarkerColor(4)
    pin_field_histo.SetMarkerStyle(22)
    pin_field_histo.Draw("SAME HIST")
    pin_field_histo.Draw("SAME P")

    lgad_field_histo.GetXaxis().SetTitleSize(0.05)
    lgad_field_histo.GetXaxis().SetLabelSize(0.05)
    lgad_field_histo.GetYaxis().SetTitleSize(0.05)
    lgad_field_histo.GetYaxis().SetLabelSize(0.05)

    legend = ROOT.TLegend(0.5, 0.6, 0.8, 0.8)
    legend.AddEntry(pin_field_histo, "p-i-n", "pl")
    legend.AddEntry(lgad_field_histo, "LGAD", "pl")
    legend.SetTextSize(0.05)
    legend.SetBorderSize(0)
    legend.Draw("same")

    c1.SaveAs(path+"field_comparison"+".pdf")
    c1.SaveAs(path+"field_comparison"+".root")

def draw_sigma(field,path):
    n = 100
    E = ROOT.TH1F("","",n,0,50)
    E.GetXaxis().SetTitle("z[\mu m]") 
    E.GetYaxis().SetTitle("E[V/\mu m]") 

    S = ROOT.TH1F("","",n,0,50) 
    S.GetXaxis().SetTitle("z[\mu m]") 
    S.GetYaxis().SetTitle("\sigma^{-2}[\mu m^{-2}]")  

    e_2 = field.get_e_field(650,650,2)[2]
    for i in range(n):
        z = (i+1)*50/n
        e = field.get_e_field(650,650,z-0.01)[2]
        if z<2:
            s=0
        else:
            s = 1/(450 + 49 + 2.8*(1+2*math.log(e_2/e))**2) # temporal_FWHM^2 v^2 + sigma_0^2 + (k_{B}Tε/q^2N_{eff})(1+2ln(E_2/E)^2)
        E.SetBinContent(i+1,e)
        S.SetBinContent(i+1,s)

    c1 = ROOT.TCanvas("c", "canvas",1000, 1000)
    ROOT.gStyle.SetOptStat(ROOT.kFALSE)
    ROOT.gStyle.SetOptFit()
    c1.SetLeftMargin(0.18)
    c1.SetRightMargin(0.2)
    c1.SetBottomMargin(0.14)
    c1.SetRightMargin(0.12)

    E.Draw("COLZ")
    E.GetXaxis().SetTitleSize(0.05)
    E.GetXaxis().SetLabelSize(0.05)
    E.GetYaxis().SetTitleSize(0.05)
    E.GetYaxis().SetLabelSize(0.05)
    E.SetLineWidth(2)
    E.SetTitle("")
    c1.SaveAs(path+"Field.pdf")
    c1.SaveAs(path+"Field.root")
    del c1

    c2 = ROOT.TCanvas("c", "canvas",1000, 1000)
    ROOT.gStyle.SetOptStat(ROOT.kFALSE)
    ROOT.gStyle.SetOptFit()
    c2.SetLeftMargin(0.18)
    c2.SetRightMargin(0.2)
    c2.SetBottomMargin(0.14)
    c2.SetRightMargin(0.12)

    S.Draw("COLZ")
    S.GetXaxis().SetTitleSize(0.05)
    S.GetXaxis().SetLabelSize(0.05)
    S.GetYaxis().SetTitleSize(0.05)
    S.GetYaxis().SetLabelSize(0.05)
    S.SetLineWidth(2)
    S.SetTitle("")
    c2.SaveAs(path+"Sigma.pdf")
    c2.SaveAs(path+"Sigma.root")
    del c2

def main():
    path = "output/lgadtct/HPK-Si-LGAD/"
    if not os.access(path, os.F_OK):
        os.makedirs(path, exist_ok=True) 

    pin_paras = ["det_name=HPK-Si-PIN","parfile=paras/setting.json"]
    pin_set = raser.Setting(pin_paras)
    my_pin = raser.R3dDetector(pin_set)
    my_pin_field = raser.FenicsCal(my_pin,pin_set.fenics)

    lgad_paras = ["det_name=HPK-Si-LGAD","parfile=paras/setting.json"]
    lgad_set = raser.Setting(lgad_paras)
    my_lgad = raser.R3dDetector(lgad_set)
    my_lgad_field = raser.FenicsCal(my_lgad,lgad_set.fenics)

    draw_fields(my_pin_field,my_lgad_field,path)
    draw_sigma(my_lgad_field,path)

if __name__ == "__main__":
    main()