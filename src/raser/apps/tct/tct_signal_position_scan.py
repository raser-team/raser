#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""
@Description: The main program of Raser induced current simulation
@Date       : 2024/09/26 15:11:20
@Author     : Lin Zhu
@version    : 2.0
"""
import sys
import os
from array import array
import time
import subprocess
import json
import random
import numpy as np

import ROOT
ROOT.gROOT.SetBatch(True)

from raser.core.device import build_device as bdv
from raser.core.field import devsim_field as devfield
from raser.core.current import cal_current as ccrt
from raser.core.analog.readout import Amplifier
from ..signal import draw_save
from raser.supports.output import output
from raser.supports.paths import component_path
from raser.supports.paths import project_path
from raser.supports.root_tree import root_tree_to_csv as rt2csv

from raser.core.interaction.laser import LaserInjection

def is_number(s):
    """
    Define the input s is number or not.
    if Yes, return True, else return False.
    """ 
    try:
        float(s)
        return True
    except ValueError:
        pass
    try:
        import unicodedata
        unicodedata.numeric(s)
        return True
    except (TypeError, ValueError):
        pass
    return False

def position_scan(kwargs,my_l,laser_dic,effective_pos_num):
    input_file = str(project_path("tct", my_l.model+'position'))
    # 根据strip电极条数+1确定数字形状
    pos_scan_pos = []
    pos_scan_strip1 =[]
    pos_scan_strip2 =[]
    pos_scan_strip3 =[]
    for root,dirs,files in os.walk(input_file):
        for i in range(laser_dic['pos_points_num']+1):
            for file in files:
                # pos_scan[i][0] = laser_dic["pos_start_fx"]+(laser_dic["pos_end_fx"]-laser_dic["pos_start_fx"])/laser_dic["pos_points_num"]*i
                if ('.csv' in file) and(('pos'+str(i)+'_') in file):
                    if'No_0' in file:    
                        path = os.path.join(input_file, file)
                        list_c = []
                        with open(path, 'r') as file_in: 
                            for line in file_in:
                                if not (is_number(line.split(",")[0])):
                                    continue
                                list_c.append(line)
                        if len(list_c)>5:
                            ampl_signal_list = []
                            for j in range (0,len(list_c)):
                                ampl_s=abs(float(list(filter(None,list_c[j].split(",")))[1]))
                                ampl_signal_list.append(ampl_s)
                            max_signal_height=max(ampl_signal_list)
                            pos_scan_strip1.append(max_signal_height)
                            for s in range(1):
                                pos_scan_pos.append(round(420*(laser_dic["pos_start_fx"]+(laser_dic["pos_end_fx"]-laser_dic["pos_start_fx"])/laser_dic["pos_points_num"]*i),2,))
                    elif'No_1' in file:
                        path = os.path.join(input_file, file)
                        list_c = []
                        with open(path, 'r') as file_in: 
                            for line in file_in:
                                if not (is_number(line.split(",")[0])):
                                    continue
                                list_c.append(line)
                        if len(list_c)>5:
                            ampl_signal_list = []
                            for j in range (0,len(list_c)):
                                ampl_s=abs(float(list(filter(None,list_c[j].split(",")))[1]))
                                ampl_signal_list.append(ampl_s)
                            max_signal_height=max(ampl_signal_list)
                            pos_scan_strip2.append(max_signal_height)

                    elif'No_2' in file:
                        path = os.path.join(input_file, file)
                        list_c = []
                        with open(path, 'r') as file_in: 
                            for line in file_in:
                                if not (is_number(line.split(",")[0])):
                                    continue
                                list_c.append(line)
                        if len(list_c)>5:
                            ampl_signal_list = []
                            for j in range (0,len(list_c)):
                                ampl_s=abs(float(list(filter(None,list_c[j].split(",")))[1]))
                                ampl_signal_list.append(ampl_s)
                            max_signal_height=max(ampl_signal_list)
                            pos_scan_strip3.append(max_signal_height)
    pos_scan = np.column_stack((pos_scan_pos,  pos_scan_strip1, pos_scan_strip2, pos_scan_strip3))
    pos = array('d', [0.0])
    volt_No_0 = array('d', [0.0])
    volt_No_1 = array('d', [0.0])
    volt_No_2 = array('d', [0.0])
    tree_file_name = os.path.join(input_file, "position-scan") +".root"
    csv_file_name = os.path.join(input_file, "position-scan") + ".csv"
    
    tree_file = ROOT.TFile(tree_file_name, "RECREATE")
    t_out = ROOT.TTree("tree", "signal")
    t_out.Branch("position_um", pos, "position_um/D")
    t_out.Branch("volt0_mV", volt_No_0 , "volt0_mV/D")
    t_out.Branch("volt1_mV", volt_No_1 , "volt1_mV/D")
    t_out.Branch("volt2_mV", volt_No_2 , "volt2_mV/D")

    for i in range(pos_scan.shape[0]):
        pos[0]=pos_scan[i][0]
        # pos[0]=round(pos_scan[i][0]*420,1)
        volt_No_0[0] = pos_scan[i][1]
        volt_No_1[0] = pos_scan[i][2]
        volt_No_2[0] = pos_scan[i][3]
        # print(f"Writing: {pos[0]}, {volt_No_0[0]}, {volt_No_1[0]}, {volt_No_2[0]}")
        t_out.Fill()
    tree_file.Write()
    tree_file.Close()

    rt2csv(csv_file_name, tree_file_name, "tree")
    return pos_scan


def TH1F_define(histo):
    """TH1f definition"""
    histo.GetXaxis().SetTitle("Recon_Laser [um]")
    histo.GetYaxis().SetTitle("Events")
    histo.GetXaxis().SetTitleOffset(1.2)
    histo.GetXaxis().SetTitleSize(0.07)
    histo.GetXaxis().SetLabelSize(0.05)
    histo.GetXaxis().SetNdivisions(510)
    histo.GetYaxis().SetTitleOffset(1.1)
    histo.GetYaxis().SetTitleSize(0.07)
    histo.GetYaxis().SetLabelSize(0.05)
    histo.GetYaxis().SetNdivisions(505)
    histo.GetXaxis().CenterTitle()
    histo.GetYaxis().CenterTitle()
    histo.SetLineWidth(2)
    return histo

def draw_2D_position_error(position_error,out_put,model='position_resolution'):
    c1 =  ROOT.TCanvas("c1"+model,"c1"+model,200,10,800,600)
    ROOT.gStyle.SetOptStat(0)
    c1.SetGrid()
    c1.SetLeftMargin(0.2)
    c1.SetTopMargin(0.12)
    c1.SetBottomMargin(0.2)
    # Define lengend th1f and root gstyle
    leg = ROOT.TLegend(0.25, 0.6, 0.35, 0.8)
    
    step = 0.4
    x2_min = -5
    x2_max = 5
    n2_bin = int((x2_max-x2_min)/step)
    histo=ROOT.TH1F("","",n2_bin,x2_min,x2_max)
    for i in range(0,len(position_error)):
        if position_error[i]<60:
            histo.Fill(position_error[i])
    # Fit data
    fit_func_1,sigma,error=fit_data_normal(histo,x2_min,x2_max)# in nanosecond
    sigma=sigma # in um
    error=error
    histo=TH1F_define(histo)
    # Legend setting
    leg.AddEntry(fit_func_1,"Fit","L")
    leg.AddEntry(histo,"Sim","L")
    # Draw
    histo.Draw()
    fit_func_1.Draw("same")
    leg.Draw("same")
    # Text set
    root_tex_position_resolution(sigma,error)
    # Save
    c1.SaveAs(out_put+'/'+model+".pdf")
    c1.SaveAs(out_put+'/'+model+".C")
    del c1
    return sigma, error

def fit_data_normal(histo,x_min,x_max):
    """Fit data distribution"""
    fit_func_1 = ROOT.TF1('fit_func_1','gaus',x_min,x_max)
    histo.Fit("fit_func_1","ROQ+","",x_min,x_max)

    print("constant:%s"%fit_func_1.GetParameter(0))
    print("constant_error:%s"%fit_func_1.GetParError(0))
    print("mean:%s"%fit_func_1.GetParameter(1))
    print("mean_error:%s"%fit_func_1.GetParError(1))
    print("sigma:%s"%fit_func_1.GetParameter(2))
    print("sigma_error:%s"%fit_func_1.GetParError(2))
    sigma=fit_func_1.GetParameter(2)
    error=fit_func_1.GetParError(2)
    fit_func_1.SetLineWidth(2)
    return fit_func_1,sigma,error

def root_tex_position_resolution(sigma,error):
    """Latex definition"""
    tex = ROOT.TLatex()
    tex.SetNDC(1)
    tex.SetTextFont(43)
    tex.SetTextSize(25)
    # tex.DrawLatexNDC(0.65, 0.7, "CFD=0.5")
    tex.DrawLatexNDC(0.65, 0.6, "#sigma = %.1f #pm %.1f um"%(sigma,error))

def job_main(kwargs):
    det_name = kwargs['det_name']
    my_d = bdv.Detector(det_name)
    
    if kwargs['voltage'] != None:
        voltage = kwargs['voltage']
    else:
        voltage = my_d.voltage

    if kwargs['laser'] != None:
        laser = kwargs['laser']
        laser_json = component_path("source", "laser", laser + ".json")
        with open(laser_json) as f:
            laser_dic = json.load(f)
            print(laser_dic)
            effective_pos_num = 0
            for i in range(laser_dic['pos_points_num']+1):
                laser_dic["fx_rel"]= (laser_dic["pos_start_fx"]+(laser_dic["pos_end_fx"]-laser_dic["pos_start_fx"])/laser_dic["pos_points_num"]*i
                )
                if (laser_dic["fx_rel"]>0.428) and  (laser_dic["fx_rel"]<0.5714):
                    pass
                else:
                    print(laser_dic["fx_rel"])
                    effective_pos_num = effective_pos_num +1
                    if kwargs['amplifier'] != None:
                        amplifier = kwargs['amplifier']
                    else:
                        amplifier = my_d.amplifier

                    my_f = devfield.DevsimField(my_d.device, my_d.dimension, voltage, my_d.read_out_contact, my_d.mesher, is_plugin=my_d.is_plugin(), irradiation_flux=my_d.irradiation_flux, bounds=my_d.bound,)
                    if "lgad" in my_d.det_model:
                        my_d.gain_rate_cal(my_f)
                    my_l = LaserInjection(my_d, laser_dic)

                    my_current = ccrt.CalCurrentLaser(my_d, my_f, my_l)
                    path = output(__file__, my_l.model+'position')

                    ele_current = Amplifier(my_current.sum_cu, amplifier, CDet=my_d.capacitance)
                    if kwargs['scan'] != None: #assume parameter alter
                        # key = my_l.fz_rel
                        tag = 'pos'+str(i)+'_'+'job'+str(kwargs['job'])
                        ele_current.save_signal_TTree(path, tag)
                    else:
                        my_current.draw_currents(path) # Draw current
                        ele_current.draw_waveform(my_current.sum_cu, path) # Draw waveform

                        my_l.draw_nocarrier3D(path)
                        my_l.draw_nocarrier2D(path)
                    
            print('successfully')
    else:
        # TCT must be with laser
        raise NameError
    pos_scan = position_scan(kwargs,my_l,laser_dic,effective_pos_num)

    if (np.where(pos_scan[:, 0]>=120)[0].size > 0) and (np.where(pos_scan[:, 0]<=180)[0].size > 0):
        start_gap1 = np.where(pos_scan[:, 0]>120)[0][0]
        end_gap1 = np.where(pos_scan[:, 0]<=180)[0][-1]
    else:
        raise ValueError("No points in gap1")
    if (np.where(pos_scan[:, 0]>=240)[0].size > 0) and (np.where(pos_scan[:, 0]<=300)[0].size > 0):
        start_gap2 = np.where(pos_scan[:, 0]>240)[0][0]
        end_gap2 = np.where(pos_scan[:, 0]<=300)[0][-1]
    else:
        raise ValueError("No points in gap2")
    
    pos_scan_fit_1 = pos_scan[start_gap1:end_gap1+1,:]
    pos_scan_fit_2 = pos_scan[start_gap2:end_gap2+1,:]
    R_fit1 = pos_scan_fit_1[:,2]/(pos_scan_fit_1[:,1]+pos_scan_fit_1[:,2])
    R_fit2 = pos_scan_fit_2[:,3]/(pos_scan_fit_2[:,2]+pos_scan_fit_2[:,3])

    k_gap1, c_gap1 = np.polyfit(pos_scan_fit_1[:,0]-120, R_fit1, 1)
    k_gap2, c_gap2 = np.polyfit(pos_scan_fit_2[:,0]-240, R_fit2, 1)
    # error_gap1 = R_fit1-(k_gap1*(pos_scan_fit_1[:,0]-120)+c_gap1)
    # error_gap2 = R_fit2-(k_gap2*(pos_scan_fit_2[:,0]-240)+c_gap2)
    # error_data = np.concatenate((error_gap1, error_gap2))
    error_gap1 = (pos_scan_fit_1[:,0]-120)-((R_fit1-c_gap1)/k_gap1)
    error_gap2 = (pos_scan_fit_2[:,0]-240)-((R_fit2-c_gap2)/k_gap2)
    error_data = np.concatenate((error_gap1, error_gap2))


    output_file = str(project_path("tct", my_l.model+'position'))
    draw_2D_position_error(error_data,output_file)


def main(kwargs):
    scan_number = kwargs['scan']
    for i in range(scan_number):
        command = ' '.join(['python3', 'src/raser', '-b', 'tct position_signal',sys.argv[3],sys.argv[4], '--job', str(i),] + sys.argv[5:]) # 'raser', '-sh', 'signal'
        # command = ' '.join(['python3', 'raser', 'tct signal',sys.argv[3],sys.argv[4], '--job', str(i)] + sys.argv[5:]) # 'raser', '-sh', 'signal'
        print(command)
        subprocess.run([command], shell=True)
    
