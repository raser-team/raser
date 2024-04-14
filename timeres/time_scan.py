#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
from array import array
import subprocess
import sys
import os
import time
import csv
import ROOT


def main():
    args = sys.argv[1:]
    print(args[1])
    if args[1] == "scan":
        time_scan(args)
    
    elif args[1] == "draw_voltage":
        draw_scan(args[0],1,args[1],args[2])
    elif args[1] == "draw_tmp":
        draw_scan(args[0],3,args[1],args[2])
    elif args[1] == "draw_doping":
        draw_scan(args[0],0,args[1],args[2])
    elif args[1] == "draw_gap":
        draw_scan(args[0],2,args[1],args[2])
    elif args[1] == "draw_thick":
        draw_scan(args[0],4,args[1],args[2])

    elif args[1] == "gain_voltage":
        draw_scan_gain(args[0],1,args[1],args[2])
    elif args[1] == "gain_tmp":
        draw_scan_gain(args[0],3,args[1],args[2])
    elif args[1] == "gain_doping":
        draw_scan_gain(args[0],0,args[1],args[2])
    elif args[1] == "gain_gap":
        pass
    elif args[1] == "gain_thick":
        draw_scan_gain(args[0],4,args[1],args[2])

def time_scan(args):
    """ Time scan add noise for some files in one dictionary """
    path_list = []
    for root,dirs,files in os.walk(args[0]):
        for dir in dirs:
            if "outfile" not in dir and "_d" in dir :
                path_list.append(root+dir)
    o_ls=args[0].split("/")[:]		
    for file in path_list:
        # out_file=o_ls[0]+"/"+o_ls[1]+"/time_resolution_scan"+".csv"
        job_name = str(time.time())
        job_command = "./python/add_noise_raser.py " + file
        runcmd("mkdir output/job/ -p")
        with open('output/job/'+job_name+".sh","w") as f:
            f.write(job_command)
        runcmd("chmod +x output/job/"+job_name+".sh")
        command =  "output/job/"+job_name+".sh"
        print(command)
        job_sub =  "hep_sub ./" + "output/job/"+job_name+".sh"
        runcmd(job_sub)

def draw_scan(input,index,model,eff):
    o_ls=input.split("/")[:]	
    out_file=o_ls[0]+"/"+o_ls[1]+"/"+o_ls[2]+"/time_resolution_scan"

    xa_axis = array( 'f' )
    ya_axis = array( 'f' )
    za_axis = array( 'f' )
    za1_axis = array( 'f' )
    za2_axis = array( 'f' )
    xa_error = array( 'f' )
    ya_error = array( 'f' )
    za_error = array( 'f' )
    za1_error = array( 'f' )
    za2_error = array( 'f' )
    x_list = []
    y_list = []
    z_list = []
    z1_list = []
    z2_list = []
    x_error_list = []
    y_error_list = []
    z_error_list = []
    z1_error_list = []
    z2_error_list = []
    if eff == "0":
        with open(input) as f:
            reader = csv.reader(f)
            for row in reader:
                if is_number(row[index]):
                    x_list.append(abs(float(row[index])))
                    y_list.append(float(row[5]))# CSA time resolution
                    z_list.append(float(row[6]))# BB time resolution
                    z1_list.append(float(row[10]))# jitter
                    z2_list.append(float(row[11]))# Landau timing
                    x_error_list.append(0)
                    y_error_list.append(float(row[7]))# CSA time resolution error
                    z_error_list.append(float(row[8]))# BB time resolution error
                    z1_error_list.append(0)
                    z2_error_list.append(0)
        x_list, y_list, z_list, z1_list, z2_list, x_error_list, y_error_list, z_error_list, z1_error_list, z2_error_list\
            = zip(*sorted(zip(x_list, y_list, z_list, z1_list, z2_list, x_error_list, y_error_list, z_error_list, z1_error_list, z2_error_list)))
        xa_axis.extend(x_list)
        ya_axis.extend(y_list)
        za_axis.extend(z_list)
        za1_axis.extend(z1_list)
        za2_axis.extend(z2_list)
        xa_error.extend(x_error_list)
        ya_error.extend(y_error_list)
        za_error.extend(z_error_list)
        za1_error.extend(z1_error_list)
        za2_error.extend(z2_error_list)

        gr3 = ROOT.TGraphErrors(len(xa_axis), xa_axis, ya_axis, xa_error, ya_error)
        gr3 = graph_set_time_resolution(gr3,model,eff)
        gr3.SetTitle("CSA")   
        gr4 = ROOT.TGraphErrors(len(xa_axis), xa_axis, za_axis, xa_error, za_error)
        gr4 = graph_set_time_resolution(gr4,model,eff)    
        gr4.SetTitle("") 
        gr5 = ROOT.TGraphErrors(len(xa_axis), xa_axis, za1_axis, xa_error, za1_error)
        gr5 = graph_set_time_resolution(gr5,model,eff)   
        gr6 = ROOT.TGraphErrors(len(xa_axis), xa_axis, za2_axis, xa_error, za2_error)
        gr6 = graph_set_time_resolution(gr6,model,eff)     
    else:
        with open(input) as f:
            reader = csv.reader(f)
            for row in reader:
                if is_number(row[index]):
                    x_list.append(abs(float(row[index])))
                    y_list.append(float(row[-3])*100)
        x_list, y_list = zip(*sorted(zip(x_list, y_list))) 
        xa_axis.extend(x_list)
        ya_axis.extend(y_list)   
        gr4 = ROOT.TGraphErrors(len(xa_axis), xa_axis, ya_axis)
        gr4 = graph_set_time_resolution(gr4,model,eff)     
        gr4.SetTitle(" ") 
    c1 = ROOT.TCanvas("c1", "c1",200,10,2000,1600)
    ROOT.gStyle.SetOptStat(0)
    c1.SetTopMargin(0.05)
    c1.SetRightMargin(0.12)
    c1.SetLeftMargin(0.16)
    c1.SetBottomMargin(0.16)
    gr4.Draw("APL")

    c1.SaveAs(out_file+eff+".pdf")
    c1.SaveAs(out_file+eff+".C")
    c1.SaveAs(out_file+eff+".root")

    if eff == "0":
        c2 = ROOT.TCanvas("c2", "c2",200,10,1200,1600)
        ROOT.gStyle.SetOptStat(0)
        c2.SetTopMargin(0.05)
        c2.SetRightMargin(0.12)
        c2.SetLeftMargin(0.16)
        c2.SetBottomMargin(0.16)
        mg = ROOT.TMultiGraph("mg","")
        leg=ROOT.TLegend(0.7,0.6,0.9,0.9)

        gr5.SetMarkerColor(2)
        gr5.SetLineColor(2)  
        gr6.SetMarkerColor(4)
        gr6.SetLineColor(4)  
        gr4.SetMarkerStyle(3)
        gr5.SetMarkerStyle(4)
        gr6.SetMarkerStyle(26)
        gr4.SetMarkerSize(3)
        gr5.SetMarkerSize(3)
        gr6.SetMarkerSize(3)
        mg.Add(gr4)
        mg.Add(gr5)
        mg.Add(gr6) 
        mg = mggraph_set(mg,model)
        mg.Draw("APL")
        leg.AddEntry(gr4,"#sigma_{t}","LP")
        leg.AddEntry(gr5,"#sigma_{jitter}","LP")
        leg.AddEntry(gr6,"#sigma_{tw}","LP")
        FormatLegend(leg)
        leg.Draw("same")
        c2.SaveAs(out_file+eff+"2.pdf")
        c2.SaveAs(out_file+eff+"2.C")

def draw_scan_gain(input,index,model,eff):
    o_ls=input.split("/")[:]	
    out_file=o_ls[0]+"/"+o_ls[1]+"/"+o_ls[2]+"/gain_efficiency_scan"

    xa_axis = array( 'f' )
    ya_axis = array( 'f' )
    za_axis = array( 'f' )
    xa_error = array( 'f' )
    ya_error = array( 'f' )
    za_error = array( 'f' )
    x_list = []
    y_list = []
    z_list = []
    x_error_list = []
    y_error_list = []
    z_error_list = []
    if eff == "0":
        with open(input) as f:
            reader = csv.reader(f)
            for row in reader:
                if is_number(row[index]):
                    x_list.append(abs(float(row[index])))
                    y_list.append(float(row[5]))# CSA max voltage
                    z_list.append(float(row[7]))# BB current integral
                    x_error_list.append(0)
                    y_error_list.append(float(row[6]))# CSA max voltage error
                    z_error_list.append(float(row[8]))# BB current integral error
        x_list, y_list, z_list, x_error_list, y_error_list, z_error_list\
            = zip(*sorted(zip(x_list, y_list, z_list, x_error_list, y_error_list, z_error_list)))
        xa_axis.extend(x_list)
        ya_axis.extend(y_list)
        za_axis.extend(z_list)
        xa_error.extend(x_error_list)
        ya_error.extend(y_error_list)
        za_error.extend(z_error_list)

        gr3 = ROOT.TGraphErrors(len(xa_axis), xa_axis, ya_axis, xa_error, ya_error)
        gr3 = graph_set_gain_efficiency(gr3,model,eff)
        gr3.SetTitle("CSA")   
        gr4 = ROOT.TGraphErrors(len(xa_axis), xa_axis, za_axis, xa_error, za_error)
        gr4 = graph_set_gain_efficiency(gr4,model,eff)    
        gr4.SetTitle("BB") 

    c1 = ROOT.TCanvas("c1", "c1",200,10,1200,1600)
    ROOT.gStyle.SetOptStat(0)
    c1.SetTopMargin(0.05)
    c1.SetRightMargin(0.12)
    c1.SetLeftMargin(0.16)
    c1.SetBottomMargin(0.16)
    gr3.Draw("APL")

    c1.SaveAs(out_file+"_CSA.pdf")
    c1.SaveAs(out_file+"_CSA.C")
    c1.SaveAs(out_file+"_CSA.root")

    c2 = ROOT.TCanvas("c2", "c2",200,10,1200,1600)
    ROOT.gStyle.SetOptStat(0)
    c2.SetTopMargin(0.05)
    c2.SetRightMargin(0.12)
    c2.SetLeftMargin(0.16)
    c2.SetBottomMargin(0.16)
    gr4.Draw("APL")

    c2.SaveAs(out_file+"_BB.pdf")
    c2.SaveAs(out_file+"_BB.C")
    c2.SaveAs(out_file+"_BB.root")

def graph_set_time_resolution(gr,model,eff):
    gr.SetMarkerStyle(8)
    gr.SetMarkerColor(1)
    gr.SetLineColor(1)  
    gr.SetLineWidth(2)
    gr.SetMarkerSize(2)
    gr.GetHistogram().GetYaxis().CenterTitle()
    gr.GetHistogram().GetXaxis().CenterTitle() 
    gr.GetXaxis().SetTitleOffset(1.4)
    gr.GetXaxis().SetTitleSize(0.05)
    gr.GetXaxis().SetLabelSize(0.05)
    gr.GetXaxis().SetNdivisions(510)
    gr.GetYaxis().SetTitleOffset(1.4)
    gr.GetYaxis().SetTitleSize(0.05)
    gr.GetYaxis().SetLabelSize(0.05)
    gr.GetYaxis().SetNdivisions(510)
    if model == "draw_voltage":
        gr.GetXaxis().SetTitle("Voltage [V]")
        #if eff == "1":
        #    pass
        #else:
        #    gr.GetYaxis().SetRangeUser(30,60)
    elif model == "draw_tmp":
        gr.GetXaxis().SetTitle("Temperature [K]")
        #if eff == "1":
        #    pass
        #else:
        #    gr.GetYaxis().SetRangeUser(30,60)
    elif model == "draw_doping":
        gr.GetXaxis().SetTitle("Doping Concentration [1e12 cm^{-3}]")
    elif model == "draw_thick":
        gr.GetXaxis().SetTitle("Thickness [ #mum]")
    elif model == "draw_gap":
        gr.GetXaxis().SetTitle("Column Spacing [ #mum]")
    if eff == "1":
        gr.GetYaxis().SetTitle("Efficiency [%]")        
    else:
        gr.GetYaxis().SetTitle("Time Resolution [ps]")
    return gr

def graph_set_gain_efficiency(gr,model,eff):
    gr.SetMarkerStyle(8)
    gr.SetMarkerColor(1)
    gr.SetLineColor(1)  
    gr.SetLineWidth(2)
    gr.SetMarkerSize(2)
    gr.GetHistogram().GetYaxis().CenterTitle()
    gr.GetHistogram().GetXaxis().CenterTitle() 
    gr.GetXaxis().SetTitleOffset(1.4)
    gr.GetXaxis().SetTitleSize(0.05)
    gr.GetXaxis().SetLabelSize(0.05)
    gr.GetXaxis().SetNdivisions(510)
    gr.GetYaxis().SetTitleOffset(1.4)
    gr.GetYaxis().SetTitleSize(0.05)
    gr.GetYaxis().SetLabelSize(0.05)
    gr.GetYaxis().SetNdivisions(510)
    if model == "gain_voltage":
        gr.GetXaxis().SetTitle("Voltage [V]")
        #if eff == "1":
        #    pass
        #else:
        #    gr.GetYaxis().SetRangeUser(30,60)
    elif model == "gain_tmp":
        gr.GetXaxis().SetTitle("Temperature [K]")
        #if eff == "1":
        #    pass
        #else:
        #    gr.GetYaxis().SetRangeUser(30,60)
    elif model == "gain_doping":
        gr.GetXaxis().SetTitle("Doping Concentration [1e12 cm^{-3}]")
    elif model == "gain_thick":
        gr.GetXaxis().SetTitle("Thickness [ #mum]")
    elif model == "gain_gap":
        gr.GetXaxis().SetTitle("Column Spacing [ #mum]")
    if eff == "1":
        gr.GetYaxis().SetTitle("Efficiency [%]")        
    else:
        gr.GetYaxis().SetTitle("Gain efficiency [a.u.]")
    return gr

def mggraph_set(gr,model):
    if model == "draw_voltage":
        gr.GetXaxis().SetTitle("Voltage [V]")
        gr.GetYaxis().SetRangeUser(20,55)
    elif model == "draw_tmp":
        gr.GetXaxis().SetTitle("Temperature [K]")
        gr.GetYaxis().SetRangeUser(20,55)
    elif model == "draw_doping":
        gr.GetXaxis().SetTitle("Doping concentration [1e12 cm^{-3}]")
    elif model == "draw_thick":
        gr.GetXaxis().SetTitle("Thickness [ #mum]")
    elif model == "draw_gap":
        gr.GetXaxis().SetTitle("Column Spacing [ #mum]")
    gr.GetYaxis().SetTitle("Time Resolution [ps]")
    gr.GetXaxis().CenterTitle()
    gr.GetYaxis().CenterTitle()
    gr.GetXaxis().SetTitleOffset(1.4)
    gr.GetXaxis().SetTitleSize(0.05)
    gr.GetXaxis().SetLabelSize(0.05)
    gr.GetXaxis().SetNdivisions(505)
    gr.GetYaxis().SetTitleOffset(1.4)
    gr.GetYaxis().SetTitleSize(0.05)
    gr.GetYaxis().SetLabelSize(0.05)
    gr.GetYaxis().SetNdivisions(505)
    return gr

def FormatLegend(leg):
    
    leg.SetBorderSize(0)
    leg.SetTextFont(43)
    leg.SetTextSize(80)
    leg.SetFillStyle(0)
    leg.SetFillColor(0)
    leg.SetLineColor(0)

def runcmd(command):
    """ Run linux command in python """
    ret = subprocess.run([command],shell=True)


def rm_path(path):
    """ If the path exits, rm the path"""
    if os.access(path, os.F_OK):
        runcmd("rm "+path) 


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


if __name__ == '__main__':
    main()