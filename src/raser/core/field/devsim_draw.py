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

import numpy as np
import ROOT
from raser.supports import figures
ROOT.gROOT.SetBatch(True)
import matplotlib.pyplot

from raser.supports.output import output

OUTLIER_DECADES = 6  # a point this far below the median of its curve is not drawn


def draw_iv(V, I, path):
    """Write the IV points as `simIV<min>to<max>.root` and draw `iv` into `<path>/plots`.

    V [V] and I [A] are lists of the same length; the figure shows |V| and |I|.
    """
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

    figure, axis = figures.new()
    # a point far below the rest of its curve, as the one at 0 V beside
    # currents of pA, hides the curve on the log axis: it is left out of the
    # figure (the file keeps it). A curve that is small as a whole is drawn
    # as it is
    bias, current = np.abs(V), np.abs(I)
    kept = current > np.median(current) / 10**OUTLIER_DECADES
    axis.plot(bias[kept], current[kept], color=figures.TOTAL, marker="o", markersize=3)
    axis.set_yscale("log")
    axis.set_xlabel(figures.label("Reverse bias", "V"))
    axis.set_ylabel(figures.label("Leakage current", "A"))
    figures.save(figure, os.path.join(path, "plots"), "iv")


def draw_noise(V, noise, path):
    """Write the noise points as `simnoise<min>to<max>.root` and draw `noise` into `<path>/plots`.

    V [V] and noise [A] are lists of the same length.
    """
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

    figure, axis = figures.new()
    axis.plot(np.abs(V), np.abs(noise), color=figures.TOTAL, marker="o", markersize=3)
    axis.set_yscale("log")
    axis.set_xlabel(figures.label("Reverse bias", "V"))
    axis.set_ylabel(figures.label("Noise current", "A"))
    figures.save(figure, os.path.join(path, "plots"), "noise")


def draw_cv(V, C, path):
    """Write the CV points as `simCV<min>to<max>.root` and draw `cv` into `<path>/plots`.

    V [V] and C [pF] are lists of the same length; the figure shows C and
    1/C^2 against |V|.
    """
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

    bias = np.abs(V)
    capacitance = np.asarray(C, dtype=float)
    figure, (left, right) = figures.new(1, 2)
    left.plot(bias, capacitance, color=figures.TOTAL, marker="o", markersize=3)
    left.set_xlabel(figures.label("Reverse bias", "V"))
    left.set_ylabel(figures.label("Capacitance", "pF"))
    right.plot(bias, 1 / capacitance**2, color=figures.TOTAL, marker="o", markersize=3)
    right.set_xlabel(figures.label("Reverse bias", "V"))
    right.set_ylabel(r"$1/C^2$ [pF$^{-2}$]")
    figures.save(figure, os.path.join(path, "plots"), "cv")

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

def doping_boundaries(depth, doping):
    """Depths [um] of the boundaries inside the device, ascending.

    depth is the ascending depth [um]; doping is the net doping at the same
    points, in any unit. A boundary lies midway between two neighbouring points
    whose |doping| differs by more than a factor of ten (one of them may be 0).
    Boundaries closer than 0.5 um to each other are merged into their mean.
    """
    magnitude = np.abs(np.asarray(doping, dtype=float))
    depth = np.asarray(depth, dtype=float)
    low = np.minimum(magnitude[:-1], magnitude[1:])
    high = np.maximum(magnitude[:-1], magnitude[1:])
    middles = 0.5 * (depth[:-1] + depth[1:])[(high > 10 * low) & (high > 0)]
    merged = []
    group = []
    for position in middles:
        if group and position - group[-1] >= 0.5:
            merged.append(float(np.mean(group)))
            group = []
        group.append(float(position))
    if group:
        merged.append(float(np.mean(group)))
    return merged


def draw_profile(x, curves, ylabel, path, name, *suffixes, log=False, boundaries=()):
    """Draw curves against the depth into `<path>/plots` as `<name>_<suffixes>`.

    x is the depth [um]; curves is a list of (y, color, legend text or None),
    y in the unit of ylabel; log makes the vertical axis logarithmic;
    boundaries are the depths [um] of the boundaries inside the device, each
    drawn as a thin dashed vertical line.
    """
    figure, axis = figures.new()
    for depth in boundaries:
        axis.axvline(depth, color="0.5", linestyle="--", linewidth=0.8)
    for y, color, text in curves:
        axis.plot(x, y, color=color, label=text)
    if log:
        axis.set_yscale("log")
    axis.set_xlabel(figures.label("Depth", "um"))
    axis.set_ylabel(ylabel)
    if any(text is not None for _, _, text in curves):
        axis.legend()
    figures.save(figure, os.path.join(path, "plots"), name, *suffixes)

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
