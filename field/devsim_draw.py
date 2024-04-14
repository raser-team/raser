#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import ROOT
import matplotlib.pyplot
import csv
from array import array
import os

from util.output import output

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

def draw_cv(device,V,C,path):
    fig3=matplotlib.pyplot.figure(num=4,figsize=(4,4))
    matplotlib.pyplot.plot(V, C)
    matplotlib.pyplot.xlabel('Voltage (V)')
    matplotlib.pyplot.ylabel('Capacitance (pF)')
    #matplotlib.pyplot.axis([-200, 0, 0, 20])
     
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
    for (x,n,V) in zip(positions, electrons, bias_voltages):
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
    for (x,p,V) in zip(positions, holes, bias_voltages):
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
    for (x,E,V) in zip(positions,intensities, bias_voltages):
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
    for (x,E,V) in zip(positions,intensities, bias_voltages):
        header_iv = ["Depth [cm]","E (V/cm)"]
         
        f=open(os.path.join(path, str(V)+'V_x_E.csv'),'w')
        writer_E = csv.writer(f)
        writer_E.writerow(header_iv)
        for (per_x,per_E) in zip(x,E):
            writer_E.writerow([float(per_x),float(per_E)])

def draw1D(x,y,title,xtitle,ytitle,v,path):
    graph = ROOT.TGraph()
    for i in range(len(x)):
        graph.SetPoint(i, x[i],y[i])
    graph.SetTitle(title)
    canvas = ROOT.TCanvas("canvas", title, 1900, 600)
    graph.Draw("AL") 
    graph.GetXaxis().SetTitle(xtitle)
    graph.GetYaxis().SetTitle(ytitle)
    canvas.Draw()
    canvas.SaveAs(os.path.join(path, title+"{}_1d.png".format(v)))

def draw2D(x,y,value,title,v,path):
    graph = ROOT.TGraph2D()
    for i in range(len(x)):
        graph.SetPoint(i, y[i]*1e4, x[i]*1e4, value[i]) 
    canvas = ROOT.TCanvas("canvas", title, 1700, 1000)
    graph.Draw("CONT4Z")
    canvas.Draw()
    graph.GetXaxis().SetTitle("x [um]")
    graph.GetYaxis().SetTitle("z [um]")
    
    graph.SetTitle(title)
    canvas.SaveAs(os.path.join(path, title+"{}_2d.png".format(v)))
    canvas.SaveAs(os.path.join(path, title+"{}_2d.root".format(v)))

