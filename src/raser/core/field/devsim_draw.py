#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

"""
Description:  This module is for drawing IV, CV, noise, electron, hole, electric field plots.
@Date       : 2023
@Author     : Tao Yang, Xingchen Li, Zaiyi Li
@version    : 2.0
"""

import csv
from array import array
import os

import ROOT
ROOT.gROOT.SetBatch(True)
import matplotlib.pyplot

from raser.supports.output import output

def draw_iv(device,V,I,path):

    fig2=matplotlib.pyplot.figure()
    matplotlib.pyplot.semilogy(V,I)
    matplotlib.pyplot.xlabel('Voltage (V)')
    matplotlib.pyplot.ylabel('Current (A)')
    matplotlib.pyplot.yscale('log')
    fig2.savefig(os.path.join(path, "{}_iv.png".format(device)))
    fig2.clear()


    file = ROOT.TFile(os.path.join(path, "simIV{}to{}.root".format(min(V),max(V))), "RECREATE")
    tree = ROOT.TTree("SicarTestIV", "SicarTest with impactgen")
    x = array('d', [0])
    y = array('d', [0])

    tree.Branch("voltage", x, "x/D")
    tree.Branch("Current", y, "y/D")

    for point in zip(V,I):
        x[0], y[0] = point
        tree.Fill()

    file.Write()
    file.Close()

    file = ROOT.TFile(os.path.join(path, "simIV{}to{}.root".format(min(V),max(V))), "READ")
    tree = file.Get("SicarTestIV")

    graph = ROOT.TGraph(tree.GetEntries())
    for i, entry in enumerate(tree):
        x = entry.x
        y = entry.y
        graph.SetPoint(i, x, y)

    canvas = ROOT.TCanvas("canvas", "Graph", 800, 600)
    graph.SetMarkerStyle(ROOT.kFullCircle)
    graph.SetMarkerSize(0.5)
    graph.SetMarkerColor(ROOT.kBlue)
    graph.SetLineColor(ROOT.kWhite)
    graph.Draw("AP")

    graph.SetTitle("Current vs Voltage")
    graph.GetXaxis().SetTitle("Voltage(V)")
    graph.GetYaxis().SetTitle("Current(A)")

    canvas.Update()
    canvas.SaveAs(os.path.join(path, "simIV{}to{}_picture.root".format(min(V),max(V))))
    canvas.SaveAs(os.path.join(path, "simIV{}to{}_picture.pdf".format(min(V),max(V))))


def draw_noise(device,V,noise,path):
    fig2=matplotlib.pyplot.figure()
    matplotlib.pyplot.semilogy(V,noise)
    matplotlib.pyplot.xlabel('Voltage (V)')
    matplotlib.pyplot.ylabel('Current (A)')
    matplotlib.pyplot.yscale('log')
    fig2.savefig(os.path.join(path, "{}_noise.png".format(device)))
    fig2.clear()


    file = ROOT.TFile(os.path.join(path, "simnoise{}to{}.root".format(min(V),max(V))), "RECREATE")
    tree = ROOT.TTree("SicarTestnoise", "SicarTest with impactgen")
    x = array('d', [0])
    y = array('d', [0])

    tree.Branch("voltage", x, "x/D")
    tree.Branch("Current", y, "y/D")

    for point in zip(V,noise):
        x[0], y[0] = point
        tree.Fill()

    file.Write()
    file.Close()

    file = ROOT.TFile(os.path.join(path, "simnoise{}to{}.root".format(min(V),max(V))), "READ")
    tree = file.Get("SicarTestnoise")

    graph = ROOT.TGraph(tree.GetEntries())
    for i, entry in enumerate(tree):
        x = entry.x
        y = entry.y
        graph.SetPoint(i, x, y)

    canvas = ROOT.TCanvas("canvas", "Graph", 800, 600)
    graph.SetMarkerStyle(ROOT.kFullCircle)
    graph.SetMarkerSize(0.5)
    graph.SetMarkerColor(ROOT.kBlue)
    graph.SetLineColor(ROOT.kWhite)
    graph.Draw("AP")

    graph.SetTitle("NoiseCurrent vs Voltage")
    graph.GetXaxis().SetTitle("Voltage(V)")
    graph.GetYaxis().SetTitle("NoiseCurrent(A)")

    canvas.Update()
    canvas.SaveAs(os.path.join(path, "simnoise{}to{}_picture.root".format(min(V),max(V))))
    canvas.SaveAs(os.path.join(path, "simnoise{}to{}_picture.pdf".format(min(V),max(V))))




def draw_cv(device,V,C,path):
    fig3=matplotlib.pyplot.figure(num=4,figsize=(4,4))
    # matplotlib.pyplot.plot(V, C)
    matplotlib.pyplot.semilogy(V, C,'.')
    matplotlib.pyplot.xlabel('Voltage (V)')
    matplotlib.pyplot.ylabel('Capacitance (pF)')
    #matplotlib.pyplot.axis([-200, 0, 0, 20])
    matplotlib.pyplot.subplots_adjust(left=0.15) 
     
    fig3.savefig(os.path.join(path, "{}_cv.png".format(device)))
    fig3.clear()

    fig4=matplotlib.pyplot.figure(num=4,figsize=(4,4))
    C_minus2 = []
    for c in C:
        C_minus2.append(1/c**2)
    matplotlib.pyplot.plot(V, C_minus2)
    matplotlib.pyplot.xlabel('Voltage (V)')
    matplotlib.pyplot.ylabel('1/C^2 (pF^{-2})')
    #matplotlib.pyplot.axis([-200, 0, 0, 20])
     
    fig4.savefig(os.path.join(path, "{}_c^-2v.png".format(device)))
    fig4.clear()


    file = ROOT.TFile(os.path.join(path, "simCV{}to{}.root".format(min(V),max(V))), "RECREATE")
    tree = ROOT.TTree("SicarTestCV", "SicarTest with impactgen")
    x = array('d', [0])
    y = array('d', [0])

    tree.Branch("voltage", x, "x/D")
    tree.Branch("CAP", y, "y/D")

    for point in zip(V,C):
        x[0], y[0] = point
        tree.Fill()

    file.Write()
    file.Close()

    file = ROOT.TFile(os.path.join(path, "simCV{}to{}.root".format(min(V),max(V))), "READ")
    tree = file.Get("SicarTestCV")

    graph = ROOT.TGraph(tree.GetEntries())
    for i, entry in enumerate(tree):
        x = entry.x
        y = entry.y
        graph.SetPoint(i, x, y)

    canvas = ROOT.TCanvas("canvas", "Graph", 800, 600)
    graph.SetMarkerStyle(ROOT.kFullCircle)
    graph.SetMarkerSize(0.5)
    graph.SetMarkerColor(ROOT.kBlue)
    graph.SetLineColor(ROOT.kWhite)
    graph.Draw("AP")

    graph.SetTitle("CAP vs Voltage")
    graph.GetXaxis().SetTitle("Voltage")
    graph.GetYaxis().SetTitle("CAP(pF)")

    canvas.Update()
    canvas.SaveAs(os.path.join(path, "simCV{}to{}_picture.root".format(min(V),max(V))))
    canvas.SaveAs(os.path.join(path, "simCV{}to{}_picture.pdf".format(min(V),max(V))))

def draw_electrons(device, positions, electrons, bias_voltages,path):
    fig1=matplotlib.pyplot.figure()
    ax1 = fig1.add_subplot(111)
    for x,n,V in zip(positions, electrons, bias_voltages):
        matplotlib.pyplot.plot(x,n,label="%s"%(str(V)))
    matplotlib.pyplot.xlabel('Depth [cm]')
    matplotlib.pyplot.ylabel('Electron Density [cm^{-3}]')
    matplotlib.pyplot.ticklabel_format(axis="y", style="sci", scilimits=(0,0))
    matplotlib.pyplot.yscale('log')
    ax1.legend(loc='upper right')
    if device == "SICAR-1.1.8":
        ax1.set_xlim(0,5e-4)
    fig1.show()
     
    fig1.savefig(os.path.join(path, "{}_electrons.png".format(device)))
    fig1.clear()

def draw_holes(device, positions, holes, bias_voltages,path):
    fig1=matplotlib.pyplot.figure()
    ax1 = fig1.add_subplot(111)
    for x,p,V in zip(positions, holes, bias_voltages):
        matplotlib.pyplot.plot(x,p,label="%s"%(str(V)))
    matplotlib.pyplot.xlabel('Depth [cm]')
    matplotlib.pyplot.ylabel('Hole Density [cm^{-3}]')
    matplotlib.pyplot.ticklabel_format(axis="y", style="sci", scilimits=(0,0))
    matplotlib.pyplot.yscale('log')

    ax1.legend(loc='upper right')
    if device == "SICAR-1.1.8":
        ax1.set_xlim(0,5e-4)
    fig1.show()
     
    fig1.savefig(os.path.join(path, "{}_holes.png".format(device)))
    fig1.clear()

def draw_field(device, positions,intensities, bias_voltages,path):
    fig1=matplotlib.pyplot.figure()
    ax1 = fig1.add_subplot(111)
    for x,E,V in zip(positions,intensities, bias_voltages):
        matplotlib.pyplot.plot(x,E,label="%s"%(str(V)))
    matplotlib.pyplot.xlabel('Depth [cm]')
    matplotlib.pyplot.ylabel('E (V/cm)')
    matplotlib.pyplot.ticklabel_format(axis="y", style="sci", scilimits=(0,0))
    ax1.legend(loc='upper right')
    if device == "SICAR-1.1.8":
        ax1.set_xlim(0,5e-4)
    fig1.show()
     
    fig1.savefig(os.path.join(path, "{}_electricfield.png".format(device)))
    fig1.clear()

def save_field(device, positions, intensities, bias_voltages,path):
    for x,E,V in zip(positions,intensities, bias_voltages):
        header_iv = ["Depth [cm]","E (V/cm)"]
         
        f=open(os.path.join(path, str(V)+'V_x_E.csv'),'w')
        writer_E = csv.writer(f)
        writer_E.writerow(header_iv)
        for per_x,per_E in zip(x,E):
            writer_E.writerow([float(per_x),float(per_E)])

def draw1D(x,y,title,xtitle,ytitle,v,path):
    graph = ROOT.TGraph()
    for i in range(len(x)):
        graph.SetPoint(i, x[i]*1e4, y[i])
    graph.SetTitle(title)
    canvas = ROOT.TCanvas("canvas", title, 800, 600)
    canvas.SetLeftMargin(0.15)
    graph.Draw("AL") 
    graph.GetXaxis().SetTitle(xtitle)
    graph.GetYaxis().SetTitle(ytitle)
    canvas.Draw()
    canvas.SaveAs(os.path.join(path, title+"{}_1d.png".format(v)))

def draw2D(x,y,value,title,v,path):
    title = str(title)
    graph = ROOT.TGraph2D()
    graph_1d = ROOT.TGraph()
    j = 0
    y_middle = 0.5*(max(y)-min(y))
    x_middle = 0.5*(max(x)-min(x))
    for i in range(len(x)):
        graph.SetPoint(i, y[i]*1e4, x[i]*1e4, value[i]) 
        if abs(y[i]*1e4 - y_middle) < 0.1 :
            graph_1d.SetPoint(j, x[i]*1e4, value[i])
            j=j+1
    canvas = ROOT.TCanvas("canvas",title, 1000, int(1000*x_middle/y_middle))
    canvas.SetRightMargin(0.15)
    graph.Draw("CONT4Z")
    canvas.Draw()
    graph.GetXaxis().SetTitle("x [um]")
    graph.GetYaxis().SetTitle("z [um]")
    graph.SetTitle(title)
    canvas.SaveAs(os.path.join(path, title+"{}_2d.pdf".format(v)))
    # Using png will cause crash in ROOT
    canvas.SaveAs(os.path.join(path, title+"{}_2d.root".format(v)))

    canvas1 = ROOT.TCanvas("canvas1", title, 1700, 1000)
    graph_1d.Draw("AL")
    canvas1.Draw()
    graph_1d.GetXaxis().SetTitle("z [um]")
    graph_1d.GetYaxis().SetTitle("Potential")
    canvas1.SaveAs(os.path.join(path, title+"{}_1d.pdf".format(v)))
    canvas1.SaveAs(os.path.join(path, title+"{}_1d.root".format(v)))


def draw3D(x, y, z, value, title, v, path):
    title = str(title)
    unit_conv = 1e4  
    z_mid = (max(z) + min(z)) / 2 
    x_mid = (max(x) + min(x)) / 2  
    y_mid = (max(y) + min(y)) / 2  
    threshold = 0.5 / unit_conv  
    
    graph_3d_1d = ROOT.TGraph()
    x_middle_1d = 0.5 * (max(x) - min(x)) * unit_conv 
    y_middle_1d = 0.5 * (max(y) - min(y)) * unit_conv
    z_1d = []
    value_1d = []
    for i in range(len(x)):
        x_um = x[i] * unit_conv
        y_um = y[i] * unit_conv
        if abs(x_um - x_middle_1d) < 0.5 and abs(y_um - y_middle_1d) < 0.5:
            z_1d.append(z[i] * unit_conv)  
            value_1d.append(value[i]) 
    sorted_data = sorted(zip(z_1d, value_1d), key=lambda d: d[0])
    for j, (z_val, val) in enumerate(sorted_data):
        graph_3d_1d.SetPoint(j, z_val, val)
    canvas3d_1d = ROOT.TCanvas("canvas3d_1d", title, 1700, 1000)
    graph_3d_1d.Draw("ALP") 
    graph_3d_1d.GetXaxis().SetTitle("z [um]")
    graph_3d_1d.GetYaxis().SetTitle(title.split()[0])
    graph_3d_1d.SetTitle(f"{title}")
    canvas3d_1d.Draw()
    canvas3d_1d.SaveAs(os.path.join(path, f"{title}_{v}_3d_1d.pdf"))
    canvas3d_1d.SaveAs(os.path.join(path, f"{title}_{v}_3d_1d.root"))

    graph_xy = ROOT.TGraph2D()
    for i in range(len(x)):
        if abs(z[i] - z_mid) < threshold: 
            graph_xy.SetPoint(graph_xy.GetN(), 
                             x[i] * unit_conv,  
                             y[i] * unit_conv,  
                             value[i])         
    if graph_xy.GetN() > 0:
        x_range = max(x) - min(x)
        y_range = max(y) - min(y)
        max_xy_range = max(x_range, y_range)
        canvas_xy = ROOT.TCanvas("canvas_xy", f"{title}_XY", 
                                int(2000 * x_range / max_xy_range), 
                                int(2000 * y_range / max_xy_range),)
        canvas_xy.SetRightMargin(0.15)
        graph_xy.Draw("CONT4Z")
        graph_xy.GetXaxis().SetTitle("x [um]")
        graph_xy.GetYaxis().SetTitle("y [um]")
        graph_xy.GetZaxis().SetTitle(f"{title.split()[0]} [unit]")
        graph_xy.SetTitle(f"{title} (XY, z={z_mid * unit_conv:.1f}um)")
        canvas_xy.Draw()
        canvas_xy.SaveAs(os.path.join(path, f"{title}_{v}_XY.pdf"))
        canvas_xy.SaveAs(os.path.join(path, f"{title}_{v}_XY.root"))

    graph_yz = ROOT.TGraph2D()
    for i in range(len(x)):
        if abs(x[i] - x_mid) < threshold:  
            graph_yz.SetPoint(graph_yz.GetN(), 
                             y[i] * unit_conv,  
                             z[i] * unit_conv, 
                             value[i])          
    if graph_yz.GetN() > 0:
        y_range = max(y) - min(y)
        z_range = max(z) - min(z)
        max_yz_range = max(y_range, z_range)
        canvas_yz = ROOT.TCanvas("canvas_yz", f"{title}_YZ", 
                            int(2000 * y_range / max_yz_range), 
                            int(2000 * z_range / max_yz_range),)
        canvas_yz.SetRightMargin(0.15)
        graph_yz.Draw("CONT4Z")
        graph_yz.GetXaxis().SetTitle("y [um]")
        graph_yz.GetYaxis().SetTitle("z [um]")
        graph_yz.GetZaxis().SetTitle(f"{title.split()[0]} [unit]")
        graph_yz.SetTitle(f"{title} (YZ, x={x_mid * unit_conv:.1f}um)")
        canvas_yz.Draw()
        canvas_yz.SaveAs(os.path.join(path, f"{title}_{v}_YZ.pdf"))
        canvas_yz.SaveAs(os.path.join(path, f"{title}_{v}_YZ.root"))

    graph_xz = ROOT.TGraph2D()
    for i in range(len(x)):
        if abs(y[i] - y_mid) < threshold: 
            graph_xz.SetPoint(graph_xz.GetN(), 
                             x[i] * unit_conv, 
                             z[i] * unit_conv,  
                             value[i])          
    if graph_xz.GetN() > 0:
        x_range = max(x) - min(x)
        z_range = max(z) - min(z)
        max_xz_range = max(x_range, z_range)
        canvas_xz = ROOT.TCanvas("canvas_xz", f"{title}_XZ", 
                                int(2000 * x_range / max_xz_range), 
                                int(2000 * z_range / max_xz_range),)
        canvas_xz.SetRightMargin(0.15)
        graph_xz.Draw("CONT4Z")
        graph_xz.GetXaxis().SetTitle("x [um]")
        graph_xz.GetYaxis().SetTitle("z [um]")
        graph_xz.GetZaxis().SetTitle(f"{title.split()[0]} [unit]")
        graph_xz.SetTitle(f"{title} (XZ, y={y_mid * unit_conv:.1f}um)")
        canvas_xz.Draw()
        canvas_xz.SaveAs(os.path.join(path, f"{title}_{v}_XZ.pdf"))
        canvas_xz.SaveAs(os.path.join(path, f"{title}_{v}_XZ.root"))
