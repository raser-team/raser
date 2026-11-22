#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
'''
@Description: Draw and plot drift path and induced current       
@Date       : 2021/08/31 11:09:40
@Author     : Yuhang Tan
@version    : 1.0
'''
from array import array

import ROOT

from raser.core.current.draw import _place_legend
from raser.supports import figures

ROOT.gROOT.SetBatch(True)

def draw_drift_path(my_d, deposits, my_f, my_current, path, event):
    c1 = figures.canvas(columns=1, rows=2)
    hole_color = figures.root_color(figures.HOLE)
    electron_color = figures.root_color(figures.ELECTRON)
    gain_hole_color = figures.root_color(figures.GAIN_HOLE)
    gain_electron_color = figures.root_color(figures.GAIN_ELECTRON)
    deposit_color = figures.root_color(figures.DEPOSIT)

    c1.cd(1)
    ROOT.gPad.SetMargin(0.15, 0.1, 0.15, 0.05)
    # an empty histogram that only draws the box of the device: one bin
    # each way, since a bin of every 50 um of a row of strips 10 cm wide
    # makes it too large for ROOT to write
    structure = ROOT.TH3D("","",1,0,my_d.l_x,
                                1,0,my_d.l_y,
                                1,0,my_d.l_z)
        
    structure.SetFillColor(1)
    structure.GetXaxis().SetTitle(figures.label("x", "um", root=True))
    structure.GetYaxis().SetTitle(figures.label("y", "um", root=True))
    structure.GetZaxis().SetTitle(figures.label("z", "um", root=True))
    structure.GetXaxis().SetNdivisions(5)
    structure.GetYaxis().SetNdivisions(5)
    structure.GetZaxis().SetNdivisions(5)
    # the titles of the 3D box stand off its tick labels
    structure.GetXaxis().SetTitleOffset(1.6)
    structure.GetYaxis().SetTitleOffset(1.8)
    structure.GetZaxis().SetTitleOffset(1.4)
    structure.Draw("ISO")

    c1.Update()
    x_array=array('f')
    y_array=array('f')
    z_array=array('f')

    mg = ROOT.TMultiGraph("mg","") # graph for page 2
    
    # 绘制空穴漂移路径
    if hasattr(my_current, 'hole_system') and my_current.hole_system:
        for carrier_idx in range(len(my_current.hole_system.paths)):
            path_data = my_current.hole_system.paths[carrier_idx]
            if len(path_data) > 0:
                x_array.extend([step[0] for step in path_data])
                y_array.extend([step[1] for step in path_data]) 
                z_array.extend([step[2] for step in path_data])              
                gr_p = ROOT.TPolyLine3D(len(path_data), x_array, y_array, z_array)
                gr_p.SetLineColor(hole_color)
                gr_p.SetLineStyle(1)
                gr_p.Draw("SAME")
                gr_2D_p = ROOT.TGraph(len(path_data), x_array, z_array)
                gr_2D_p.SetMarkerColor(hole_color)
                gr_2D_p.SetLineColor(hole_color)
                gr_2D_p.SetLineStyle(1)
                mg.Add(gr_2D_p)
                del x_array[:]
                del y_array[:]
                del z_array[:]
    
    # 绘制电子漂移路径
    if hasattr(my_current, 'electron_system') and my_current.electron_system:
        for carrier_idx in range(len(my_current.electron_system.paths)):
            path_data = my_current.electron_system.paths[carrier_idx]
            if len(path_data) > 0:
                x_array.extend([step[0] for step in path_data])
                y_array.extend([step[1] for step in path_data])
                z_array.extend([step[2] for step in path_data])                
                gr_n = ROOT.TPolyLine3D(len(path_data), x_array, y_array, z_array)
                gr_n.SetLineColor(electron_color)
                gr_n.SetLineStyle(1)
                gr_n.Draw("SAME")
                gr_2D_n = ROOT.TGraph(len(path_data), x_array, z_array)
                gr_2D_n.SetMarkerColor(electron_color)
                gr_2D_n.SetLineColor(electron_color)
                gr_2D_n.SetLineStyle(1)
                mg.Add(gr_2D_n)
                del x_array[:]
                del y_array[:]
                del z_array[:]
    
    # 绘制增益载流子路径（如果存在）
    if hasattr(my_current, 'gain_current') and my_current.gain_current:
        # 增益空穴
        if hasattr(my_current.gain_current, 'hole_system') and my_current.gain_current.hole_system:
            for carrier_idx in range(len(my_current.gain_current.hole_system.paths)):
                path_data = my_current.gain_current.hole_system.paths[carrier_idx]
                if len(path_data) > 0:
                    x_array.extend([step[0] for step in path_data])
                    y_array.extend([step[1] for step in path_data]) 
                    z_array.extend([step[2] for step in path_data])              
                    gr_p = ROOT.TPolyLine3D(len(path_data), x_array, y_array, z_array)
                    gr_p.SetLineColor(gain_hole_color)
                    gr_p.SetLineStyle(1)
                    gr_p.Draw("SAME")
                    gr_2D_p = ROOT.TGraph(len(path_data), x_array, z_array)
                    gr_2D_p.SetMarkerColor(gain_hole_color)
                    gr_2D_p.SetLineColor(gain_hole_color)
                    gr_2D_p.SetLineStyle(1)
                    mg.Add(gr_2D_p)
                    del x_array[:]
                    del y_array[:]
                    del z_array[:]
        
        # 增益电子
        if hasattr(my_current.gain_current, 'electron_system') and my_current.gain_current.electron_system:
            for carrier_idx in range(len(my_current.gain_current.electron_system.paths)):
                path_data = my_current.gain_current.electron_system.paths[carrier_idx]
                if len(path_data) > 0:
                    x_array.extend([step[0] for step in path_data])
                    y_array.extend([step[1] for step in path_data])
                    z_array.extend([step[2] for step in path_data])                
                    gr_n = ROOT.TPolyLine3D(len(path_data), x_array, y_array, z_array)
                    gr_n.SetLineColor(gain_electron_color)
                    gr_n.SetLineStyle(1)
                    gr_n.Draw("SAME")
                    gr_2D_n = ROOT.TGraph(len(path_data), x_array, z_array)
                    gr_2D_n.SetMarkerColor(gain_electron_color)
                    gr_2D_n.SetLineColor(gain_electron_color)
                    gr_2D_n.SetLineStyle(1)
                    mg.Add(gr_2D_n)
                    del x_array[:]
                    del y_array[:]
                    del z_array[:]
    
    # the deposits, as points: the deposits do not tell which particle made
    # each, so a line through them would join different particles
    n = len(deposits)
    if n > 0:
        x_array.extend([step[0] for step in deposits])
        y_array.extend([step[1] for step in deposits])
        z_array.extend([step[2] for step in deposits])
        gr = ROOT.TPolyMarker3D(n)
        for index, (x, y, z) in enumerate(zip(x_array, y_array, z_array)):
            gr.SetPoint(index, x, y, z)
        gr.SetMarkerColor(deposit_color)
        gr.SetMarkerStyle(20)
        gr.SetMarkerSize(0.6)
        gr.Draw("SAME")
        gr_2D = ROOT.TGraph(n, x_array, z_array)
        gr_2D.SetMarkerColor(deposit_color)
        gr_2D.SetMarkerStyle(20)
        gr_2D.SetMarkerSize(0.6)
        mg.Add(gr_2D, "P")
        del x_array[:]
        del y_array[:]
        del z_array[:]
    
    c1.cd(2)
    ROOT.gPad.SetMargin(0.15, 0.1, 0.15, 0.05)
    mg.GetXaxis().SetTitle(figures.label("x", "um", root=True))
    mg.GetYaxis().SetTitle(figures.label("z", "um", root=True))
    mg.GetXaxis().SetNdivisions(5)
    mg.GetYaxis().SetNdivisions(5)
    mg.Draw("APL")
    c1.Update()
    
    # 添加图例
    legend = _place_legend(ROOT.gPad, [mg], 0.22, 0.18)
    
    # 创建临时图形用于图例
    dummy_hole = ROOT.TGraph()
    dummy_hole.SetLineColor(hole_color)
    dummy_electron = ROOT.TGraph()
    dummy_electron.SetLineColor(electron_color)
    dummy_particle = ROOT.TGraph()
    dummy_particle.SetMarkerColor(deposit_color)
    dummy_particle.SetMarkerStyle(20)

    legend.AddEntry(dummy_particle, "deposits", "p")
    legend.AddEntry(dummy_hole, "holes", "l")
    legend.AddEntry(dummy_electron, "electrons", "l")
    
    if hasattr(my_current, 'gain_current') and my_current.gain_current:
        dummy_gain_hole = ROOT.TGraph()
        dummy_gain_hole.SetLineColor(gain_hole_color)
        dummy_gain_electron = ROOT.TGraph()
        dummy_gain_electron.SetLineColor(gain_electron_color)
        legend.AddEntry(dummy_gain_hole, "gain holes", "l")
        legend.AddEntry(dummy_gain_electron, "gain electrons", "l")
    
    legend.Draw()
    c1.Update()
    
    figures.save_canvas(c1, path, "drift_path", event)
    del c1
