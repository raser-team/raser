#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
'''
@Description: Draw and plot drift path and induced current       
@Date       : 2021/08/31 11:09:40
@Author     : tanyuhang
@version    : 1.0
'''
from array import array
import math
import ROOT
import sys
import os
import time

from util.output import output

def draw_plots(my_d,ele_current,my_f,my_g4p,my_current,my_l=None):
    """
    @description:
        Draw electric field ,drift path and energy deposition
    @param:
        None     
    @Returns:
        None
    @Modify:
        2021/08/31
    """
    now = time.strftime("%Y_%m%d_%H%M%S")
    path = output(__file__, my_d.det_name, now)

    if "plugin" in my_d.det_model:
        draw_ele_field(my_d,my_f,"xy",my_d.det_model,my_d.l_z*0.5,path)
    else:
        draw_ele_field_1D(my_d,my_f,path)
        draw_ele_field(my_d,my_f,"xz",my_d.det_model,my_d.l_y*0.5,path)
    for i in range(my_f.read_ele_num):
        draw_current(my_d, my_current,ele_current.ele,i,ele_current.ele_name,path) # Draw current
    #energy_deposition(my_g4p)   # Draw Geant4 depostion distribution
    if my_l != None:
        my_l.draw_nocarrier3D(path)
        my_l.draw_nocarrier2D(path)
    else: 
        draw_drift_path(my_d,my_f,my_current,path)
    if 'strip' in my_d.det_name:
        cce(my_d, my_f, my_current, path)




def save_signal_time_resolution(my_d,batch_number,ele_current,my_g4p,start_n,my_f):

    " Save data to the file"

    output_path = output(__file__, my_d.det_name, 'batch')

    if "strip" in my_d.det_model: # under construction
        for k in range(ele_current.read_ele_num):
            save_signal_csv(ele_current,my_g4p,batch_number,start_n,k,output_path)

    else:
        save_signal_csv(ele_current,my_g4p,batch_number,start_n,0,output_path)

    del ele_current

def save_signal_csv(ele_current,my_g4p,number,start_n,k,output_path="none"):
    """ Save induced current after amplification"""
    charge = "_charge=%.2f_"%(ele_current.qtot[k]*1e15)  #fc
    e_dep = "dep=%.5f_"%(my_g4p.edep_devices[number-start_n]) #mv
    output_file = output_path + "/t_" +str(number)+charge+e_dep+"events.csv"
    f1 = open(output_file,"w")
    f1.write("time[ns], Amplitude [mV] \n")
    for i in range(ele_current.ele[k].GetNbinsX()):
        f1.write("%s,%s \n"%(i*ele_current.time_unit,
                                ele_current.ele[k][i]))
    f1.close()

    print("output_file:%s"%output_file)

def draw_ele_field(my_d,my_f,plane,sensor_model,depth,path):
    """
    @description:
        Draw eletric field
    @param:
        None     
    @Returns:
        None
    @Modify:
        2021/08/31
    """
    c1 = ROOT.TCanvas("c", "canvas",2000, 2000)
    ROOT.gStyle.SetOptStat(ROOT.kFALSE)
    ROOT.gStyle.SetOptFit()
    c1.SetLeftMargin(0.12)
    c1.SetRightMargin(0.2)
    c1.SetBottomMargin(0.14)
    c1.SetRightMargin(0.12)
    q = int(math.sqrt(my_f.read_ele_num+2))+1
    c1.Divide(q,q)
    model = ["E","P","WP"]
    e_field=[]
    i=1
    c1.cd(i)
    c1.GetPad(i).SetRightMargin(0.2)
    e_field.append(fill_his(model[i-1],depth,my_d,my_f,plane,sensor_model,i))
    e_field[i-1].Draw("CONT4Z")
    i=2
    c1.cd(i)
    c1.GetPad(i).SetRightMargin(0.2)
    e_field.append(fill_his(model[i-1],depth,my_d,my_f,plane,sensor_model,i))
    e_field[i-1].Draw("CONT4Z")
    for i in range(3,my_f.read_ele_num+3):
        c1.cd(i)
        c1.GetPad(i).SetRightMargin(0.2)
        e_field.append(fill_his(model[2],depth,my_d,my_f,plane,sensor_model,i))
        e_field[i-1].Draw("COLZ")
    c1.SaveAs(path+'/'+my_d.det_model+plane+str(depth)+".pdf")
    c1.SaveAs(path+'/'+my_d.det_model+plane+str(depth)+".root")
    del c1

def draw_ele_field_1D(my_d,my_f,path):
    c1 = ROOT.TCanvas("c", "canvas",1000, 1000)
    ROOT.gStyle.SetOptStat(ROOT.kFALSE)
    ROOT.gStyle.SetOptFit()
    c1.SetLeftMargin(0.18)
    c1.SetRightMargin(0.2)
    c1.SetBottomMargin(0.14)
    c1.SetRightMargin(0.12)
    '''
    c1.Divide(2,2)
    model = ["E","P","WP"]
    i=1
    c1.cd(i)
    c1.GetPad(i).SetRightMargin(0.2)
    e_field1=fill_his_1D(model[i-1],my_d,my_f)
    e_field1.Draw("COLZ")
    i=2
    c1.cd(i)
    c1.GetPad(i).SetRightMargin(0.2)
    e_field2=fill_his_1D(model[i-1],my_d,my_f)
    e_field2.Draw("COLZ")
    i=3
    c1.cd(i)
    c1.GetPad(i).SetRightMargin(0.2)
    e_field3=fill_his_1D(model[i-1],my_d,my_f)
    e_field3.Draw("COLZ")
    '''
    e_field1=fill_his_1D('E',my_d,my_f)
    e_field1.Draw("COLZ")
    e_field1.GetXaxis().SetTitleSize(0.05)
    e_field1.GetXaxis().SetLabelSize(0.05)
    e_field1.GetYaxis().SetTitleSize(0.05)
    e_field1.GetYaxis().SetLabelSize(0.05)
    e_field1.SetLineWidth(2)
    e_field1.SetTitle("")
    c1.SaveAs(path+'/'+my_d.det_model+".pdf")
    c1.SaveAs(path+'/'+my_d.det_model+".root")
    del c1

def fill_his(model,depth,my_d,my_f,plane,sensor_model,k):
    """
    @description:
        Draw eletric field - Fill histrogram
    @param:
        None     
    @Returns:
        None
    @Modify:
        2021/08/31
    """
    nx_e=100
    ny_e=100
    d_r=confirm_range(my_d,my_f,plane,sensor_model,depth)
    e_v = ROOT.TH2F("",""+str(k),nx_e,d_r[0],d_r[1],ny_e,d_r[2],d_r[3])
    for j in range (ny_e):
        for i in range(nx_e):
            x_v = (i+1)*((d_r[1]-d_r[0])/nx_e)+d_r[0]
            y_v = (j+1)*((d_r[3]-d_r[2])/ny_e)+d_r[2]
            f_v=0.0
            try:
                f_v,e_v = get_f_v(x_v,y_v,depth,model,my_f,plane,e_v,d_r,k)
                if model == "E":
                    f_v = math.sqrt(math.pow(f_v[0],2)
                                    +math.pow(f_v[1],2)
                                    +math.pow(f_v[2],2))                           
            except RuntimeError:
                f_v = 0.0
            e_v.SetBinContent(i+1,j+1,f_v)
    if plane == "xy":
        e_v.GetXaxis().SetTitle("x")
        e_v.GetYaxis().SetTitle("y")
    elif plane == "yz":
        e_v.GetXaxis().SetTitle("y")
        e_v.GetYaxis().SetTitle("z")
    elif plane == "xz":
        e_v.GetXaxis().SetTitle("x [um]")
        e_v.GetYaxis().SetTitle("z [um]")
        e_v.GetXaxis().SetTitleSize(0.05)
        e_v.GetXaxis().SetLabelSize(0.05)
        e_v.GetYaxis().SetTitleSize(0.05)
        e_v.GetYaxis().SetLabelSize(0.05) 
    return e_v

def fill_his_1D(model,my_d,my_f):
    nz_e=2000
    d_r=confirm_range_1D(my_d)
    e_v = ROOT.TH1F("","",nz_e,d_r[0],d_r[1])
    for i in range(nz_e):
        z_v = (i+1)*((d_r[1]-d_r[0])/nz_e)+d_r[0]
        f_v=0.0
        try:
            f_v,e_v = get_f_v_1D(160,my_d.l_y/2,z_v,model,my_f,e_v,d_r)
            if model == "E":
                f_v = math.sqrt(math.pow(f_v[0],2)
                                +math.pow(f_v[1],2)
                                +math.pow(f_v[2],2))
                e_v.GetYaxis().SetTitle(model+"[V/cm]")                        
        except RuntimeError:
            f_v = 0.0
        e_v.SetBinContent(i+1,f_v)
    e_v.GetXaxis().SetTitle("z[\mu m]") 
    return e_v

def get_f_v(i_x,i_y,i_z,model,my_f,plane,e_v,d_r,k):
    """
    @description:
        Draw eletric field - Get parameters
    @param:
        "E" -- electric
        "P" -- potential
        "WP" -- weighting potential    
    @Returns:
        None
    @Modify:
        2021/08/31
    """
    if plane == "xy":
        input_x=i_x
        input_y=i_y
        input_z=i_z
    elif plane == "yz":
        input_x=i_z
        input_y=i_x
        input_z=i_y
    elif plane == "xz":
        input_x=i_x
        input_y=i_z
        input_z=i_y
    if model == "E":
        e_v.SetTitle("electric field "+d_r[4])
        f_v=my_f.get_e_field(input_x,input_y,input_z)
    elif model == "P":
        e_v.SetTitle("potential "+d_r[4])
        f_v=my_f.get_potential(input_x,input_y,input_z)
    elif model =="WP":
        e_v.SetTitle("weighting potential "+d_r[4]+" No."+str(k-2)+"electrode") 
        f_v=my_f.get_w_p(input_x,input_y,input_z,k-3)
    return f_v,e_v

def get_f_v_1D(i_x,i_y,i_z,model,my_f,e_v,d_r):
    input_x=i_x
    input_y=i_y
    input_z=i_z
    if model == "E":
        e_v.SetTitle("electric field "+d_r[2])
        f_v=my_f.get_e_field(input_x,input_y,input_z)
    elif model == "P":
        e_v.SetTitle("potential "+d_r[2])
        f_v=my_f.get_potential(input_x,input_y,input_z)
    elif model =="WP":
        e_v.SetTitle("weighting potential "+d_r[2]) 
        f_v=my_f.get_w_p(input_x,input_y,input_z)
    return f_v,e_v

def confirm_range(my_d,my_f,plane,sensor_model,depth):
    """
    @description:
        Draw eletric field - Confirm draw electric field detector range
    @param:
        None     
    @Returns:
        None
    @Modify:
        2021/08/31
    """
    if "plugin3D" in sensor_model:
        l_xl = my_f.sx_l
        l_xr = my_f.sx_r 
        if plane == "xy":
            l_yl = my_f.sy_l
            l_yr = my_f.sy_r
        elif plane == "yz" or plane == "xz":
            l_yl = 0
            l_yr = my_d.l_z
        else:
            print("the draw plane is not existing")
    elif "planar3D" in sensor_model or "planarRing" in sensor_model or "lgad3D" in sensor_model:
        l_xl = 0
        l_yl = 0 
        if plane == "xy":
            l_xr = my_d.l_x 
            l_yr = my_d.l_y
        elif plane == "yz":
            l_xr = my_d.l_y
            l_yr = my_d.l_z
        elif plane == "xz":
            l_xr = my_d.l_x
            l_yr = my_d.l_z
        else:
            print("the draw plane is not existing")
    else:
        print("sensor model is wrong")
        raise NameError
    for x in "xyz":
        if x not in plane:
            t_name = plane + " at " + x + " = " + str(depth)
    return [l_xl,l_xr,l_yl,l_yr,t_name]

def confirm_range_1D(my_d):
    l_xl=0
    l_xr=my_d.l_z
    t_name = "z"
    return [l_xl,l_xr,t_name]

def draw_current(my_d, my_current, ele_current, read_ele_num, model, path, tag=""):
    """
    @description:
        Save current in root file
    @param:
        None     
    @Returns:
        None
    @Modify:
        2021/08/31
    """
    c=ROOT.TCanvas("c","canvas1",1000,1000)
    c.cd()
    c.Update()
    c.SetLeftMargin(0.12)
    # c.SetTopMargin(0.12)
    c.SetRightMargin(0.12)
    c.SetBottomMargin(0.14)
    ROOT.gStyle.SetOptStat(ROOT.kFALSE)
    ROOT.gStyle.SetOptStat(0)

    #my_current.sum_cu.GetXaxis().SetTitleOffset(1.2)
    #my_current.sum_cu.GetXaxis().SetTitleSize(0.05)
    #my_current.sum_cu.GetXaxis().SetLabelSize(0.04)
    my_current.sum_cu[read_ele_num].GetXaxis().SetNdivisions(510)
    #my_current.sum_cu.GetYaxis().SetTitleOffset(1.1)
    #my_current.sum_cu.GetYaxis().SetTitleSize(0.05)
    #my_current.sum_cu.GetYaxis().SetLabelSize(0.04)
    my_current.sum_cu[read_ele_num].GetYaxis().SetNdivisions(505)
    #my_current.sum_cu.GetXaxis().CenterTitle()
    #my_current.sum_cu.GetYaxis().CenterTitle() 
    my_current.sum_cu[read_ele_num].GetXaxis().SetTitle("Time [s]")
    my_current.sum_cu[read_ele_num].GetYaxis().SetTitle("Current [A]")
    my_current.sum_cu[read_ele_num].GetXaxis().SetLabelSize(0.05)
    my_current.sum_cu[read_ele_num].GetXaxis().SetTitleSize(0.05)
    my_current.sum_cu[read_ele_num].GetYaxis().SetLabelSize(0.05)
    my_current.sum_cu[read_ele_num].GetYaxis().SetTitleSize(0.05)
    my_current.sum_cu[read_ele_num].Draw("HIST")
    my_current.positive_cu[read_ele_num].Draw("SAME HIST")
    my_current.negative_cu[read_ele_num].Draw("SAME HIST")
    my_current.gain_positive_cu[read_ele_num].Draw("SAME HIST")
    my_current.gain_negative_cu[read_ele_num].Draw("SAME HIST")
    my_current.sum_cu[read_ele_num].Draw("SAME HIST")

    my_current.positive_cu[read_ele_num].SetLineColor(877)#kViolet-3
    my_current.negative_cu[read_ele_num].SetLineColor(600)#kBlue
    my_current.gain_positive_cu[read_ele_num].SetLineColor(617)#kMagneta+1
    my_current.gain_negative_cu[read_ele_num].SetLineColor(867)#kAzure+7
    my_current.sum_cu[read_ele_num].SetLineColor(418)#kGreen+2

    my_current.positive_cu[read_ele_num].SetLineWidth(2)
    my_current.negative_cu[read_ele_num].SetLineWidth(2)
    my_current.gain_positive_cu[read_ele_num].SetLineWidth(2)
    my_current.gain_negative_cu[read_ele_num].SetLineWidth(2)
    my_current.sum_cu[read_ele_num].SetLineWidth(2)
    c.Update()

    if ele_current[read_ele_num].GetMinimum() < 0:
        rightmax = 1.1*ele_current[read_ele_num].GetMinimum()
    else:
        rightmax = 1.1*ele_current[read_ele_num].GetMaximum()
    if rightmax == 0:
        n_scale=0
    elif ele_current[read_ele_num].GetMinimum() <0:
        n_scale = ROOT.gPad.GetUymin() / rightmax
    else:
        n_scale = ROOT.gPad.GetUymax() / rightmax
    ele_current[read_ele_num].Scale(n_scale)
    ele_current[read_ele_num].Draw("SAME HIST")
    ele_current[read_ele_num].SetLineWidth(2)   
    ele_current[read_ele_num].SetLineColor(8)
    ele_current[read_ele_num].SetLineColor(2)
    c.Update()

    axis = ROOT.TGaxis(ROOT.gPad.GetUxmax(), ROOT.gPad.GetUymin(), 
                       ROOT.gPad.GetUxmax(), ROOT.gPad.GetUymax(), 
                       min(0,rightmax), max(0,rightmax), 510, "+L")
    axis.SetLineColor(2)
    axis.SetTextColor(2)
    axis.SetTextSize(0.02)
    axis.SetTextFont(40)
    axis.SetLabelColor(2)
    axis.SetLabelSize(0.035)
    axis.SetLabelFont(42)
    axis.SetTitle("Ampl [V]")
    axis.SetTitleFont(40)
    axis.SetTitleOffset(1.2)
    #axis.CenterTitle()
    axis.Draw("SAME HIST")

    legend = ROOT.TLegend(0.5, 0.3, 0.8, 0.6)
    legend.AddEntry(my_current.negative_cu[read_ele_num], "electron", "l")
    legend.AddEntry(my_current.positive_cu[read_ele_num], "hole", "l")
    legend.AddEntry(my_current.gain_negative_cu[read_ele_num], "gain electron", "l")
    legend.AddEntry(my_current.gain_positive_cu[read_ele_num], "gain hole", "l")
    legend.AddEntry(my_current.sum_cu[read_ele_num], "e+h", "l")
    #legend.AddEntry(ele_current, "electronics", "l")
    legend.SetBorderSize(0)
    #legend.SetTextFont(43)
    #legend.SetTextSize(42)
    legend.Draw("same")
    c.Update()
    c.SaveAs(path+'/'+model+my_d.det_model+tag+"No_"+str(read_ele_num+1)+"electrode"+"_basic_infor.pdf")
    c.SaveAs(path+'/'+model+my_d.det_model+tag+"No_"+str(read_ele_num+1)+"electrode"+"_basic_infor.root")
    del c

def draw_drift_path(my_d,my_f,my_current,path):
    ROOT.gStyle.SetOptStat(0)
    # # ROOT.gROOT.SetBatch(1)
    c1 = ROOT.TCanvas("c", "canvas1", 200,10,1000, 1000)
    c1.Divide(1,2)

    if "plugin3D" in my_d.det_model:
        n_bin=[int((my_f.sx_r-my_f.sx_l)/5),
                int((my_f.sy_r-my_f.sy_l)/5),int((my_d.l_z)/10)]
        structure = ROOT.TH3D("","",n_bin[0],my_f.sx_l,my_f.sx_r,
                                    n_bin[1],my_f.sy_l,my_f.sy_r,
                                    n_bin[2],0,my_d.l_z)
    elif "planar3D" in my_d.det_model or "lgad3D" in my_d.det_model or "planarRing" in my_d.det_model:
        n_bin=[int(my_d.l_x/50),int(my_d.l_y/50),int(my_d.l_z)]
        structure = ROOT.TH3D("","",n_bin[0],0,my_d.l_x,
                                    n_bin[1],0,my_d.l_y,
                                    n_bin[2],0,my_d.l_z)
    c1.cd(1)
    for k in range(n_bin[2]):
        for j in range (n_bin[1]):
            for i in range(n_bin[0]):
                if "plugin3D" in my_d.det_model:
                    x_v = (i+1)*((my_f.sx_r-my_f.sx_l)/n_bin[0])+my_f.sx_l
                    y_v = (j+1)*((my_f.sx_r-my_f.sx_l)/n_bin[1])+my_f.sx_l
                    z_v = (k+1)*(my_d.l_z/n_bin[2])
                elif "planar3D" in my_d.det_model or "lgad3D" in my_d.det_model or "planarRing"in my_d.det_model:
                    x_v = (i+1)*(my_d.l_x/n_bin[0])
                    y_v = (j+1)*(my_d.l_y/n_bin[1])
                    z_v = (k+1)*(my_d.l_z/n_bin[2])
                try:
                    x_value,y_value,z_value = my_f.get_e_field(x_v,y_v,z_v)
                    if x_value==0 and y_value==0 and z_value ==0:
                        structure.SetBinContent(i+1,j+1,k+1,1)
                    else:                       
                        structure.SetBinContent(i+1,j+1,k+1,0)
                except RuntimeError:
                    structure.SetBinContent(i+1,j+1,k+1,1)
    structure.SetFillColor(1)
    structure.GetXaxis().SetTitle("x axis")
    structure.GetYaxis().SetTitle("y axis")
    structure.GetZaxis().SetTitle("z axis")
    structure.GetXaxis().CenterTitle()
    structure.GetYaxis().CenterTitle() 
    structure.GetZaxis().CenterTitle() 
    structure.GetXaxis().SetTitleSize(0.05)
    structure.GetYaxis().SetTitleSize(0.05)
    structure.GetZaxis().SetTitleSize(0.05)
    structure.Draw("ISO")

    mg = ROOT.TMultiGraph("mg","")
    x_array=array('f')
    y_array=array('f')
    z_array=array('f')
    for hole in my_current.holes:
        n=len(hole.path)
        if(n>0):
            x_array.extend([step[0] for step in hole.path])
            y_array.extend([step[1] for step in hole.path]) 
            z_array.extend([step[2] for step in hole.path])              
            gr_p = ROOT.TPolyLine3D(n,x_array,y_array,z_array)
            gr_p.SetLineColor(2)
            gr_p.SetLineStyle(1)
            gr_p.Draw("SAME")
            gr_2D_p=ROOT.TGraph(n,x_array,z_array)
            gr_2D_p.SetMarkerColor(2)
            gr_2D_p.SetLineColor(2)
            gr_2D_p.SetLineStyle(1)
            mg.Add(gr_2D_p)
            del x_array[:]
            del y_array[:]
            del z_array[:]
    for electron in my_current.electrons:
        m=len(electron.path)
        if(m>0):
            x_array.extend([step[0] for step in electron.path])
            y_array.extend([step[1] for step in electron.path])
            z_array.extend([step[2] for step in electron.path])                
            gr_n = ROOT.TPolyLine3D(m,x_array,y_array,z_array)
            gr_n.SetLineColor(4)
            gr_n.SetLineStyle(1)
            gr_n.Draw("SAME")
            gr_2D_n=ROOT.TGraph(m,x_array,z_array)
            gr_2D_n.SetMarkerColor(4)
            gr_2D_n.SetLineColor(4)
            gr_2D_n.SetLineStyle(1)
            mg.Add(gr_2D_n)
            del x_array[:]
            del y_array[:]
            del z_array[:]
    c1.cd(2)
    mg.Draw("APL")
    mg.GetXaxis().SetTitle("x axis")
    mg.GetYaxis().SetTitle("z axis")
    c1.SaveAs(path+'/'+my_d.det_model+"_drift_path.pdf")
    c1.SaveAs(path+'/'+my_d.det_model+"_drift_path.root")
    del c1

def energy_deposition(my_g4v):
    """
    @description:
        Energy_deposition for multi events of Geant4 simulation
    @param:
        None     
    @Returns:
        None
    @Modify:
        2021/08/31
    """
    c1=ROOT.TCanvas("c1","canvas1",1000,1000)
    h1 = ROOT.TH1F("Edep_device", "Energy deposition in SiC", 100, 0., 0.1)
    for i in range (len(my_g4v.edep_devices)):
        h1.Fill(my_g4v.edep_devices[i])
    g1 = ROOT.TF1("m1","landau",0,0.1)
    h1.Fit(g1,"S")
    print("MPV:%s"%g1.GetParameter(1))
    h1.Draw()
    now = time.strftime("%Y_%m%d_%H%M")
    c1.SaveAs("output/fig/dep_SiC"+"_"+now+"_energy.pdf")
    c1.SaveAs("output/fig/dep_SiC"+"_"+now+"_energy.root")

def create_path(path):
    """ If the path does not exit, create the path"""
    if not os.access(path, os.F_OK):
        os.makedirs(path, exist_ok=True) 


def draw_scat_angle(evnets_angle,angle,model):
    """Draw scatting angle of events"""
    c1=ROOT.TCanvas("c1","canvas1",1000,1000)
    c1.Divide(1,2)
    c1.cd(1)
    n=len(evnets_angle)
    ROOT.gStyle.SetOptStat(0)
    h1 = ROOT.TH1F("event angle", "Source Angle = "+str(angle), n, 0., n)
    for i in range(n):
        if evnets_angle[i] != None:
            h1.SetBinContent(i,evnets_angle[i])
    h1.GetXaxis().SetTitle(" Event number ")
    h1.GetYaxis().SetTitle(" Scattering Angle ")
    h1.GetXaxis().CenterTitle()
    h1.GetYaxis().CenterTitle() 
    h1.SetLineWidth(2)
    h1.SetLineColor(2)
    h1.Draw("HIST")
    c1.cd(2)
    events = [ evnets_angle[i] for i in range(n) if evnets_angle[i] != None ]
    h2 = ROOT.TH1F("angle distribution", "Source Angle = "+str(angle), 
                   100, 0., max(events))
    for i in range(n):
        if evnets_angle[i] != None:
            h2.Fill(evnets_angle[i])
    h2.GetXaxis().SetTitle(" Scattering Angle ")
    h2.GetYaxis().SetTitle(" number ")
    h2.GetXaxis().CenterTitle()
    h2.GetYaxis().CenterTitle() 
    h2.SetLineWidth(2)
    h2.SetLineColor(2)
    h2.Draw("HIST")    
    c1.SaveAs("scat_angle"+model+".pdf")

def get_beam_number(my_g4p,ele_current):
    now = time.strftime("%Y_%m%d_%H%M")
    path = "output/" + "beam_monitor/" + now + "/" 
    create_path(path) 
    number = array('d',[999.])
    hittotal = array('d',[999.])
    number[0] = int(-ele_current.max_BB_height/18.8)
    hittotal[0]=my_g4p.hittotal
    fout = ROOT.TFile(path + "beam_monitor.root", "RECREATE")
    t_out = ROOT.TTree("tree", "beam_number")
    t_out.Branch("cal_number", number, "cal_number/D")
    t_out.Branch("real_number", hittotal, "real_number/D")
    t_out.Fill()
    t_out.Write()
    fout.Close()

    c1=ROOT.TCanvas("c1","canvas1",1000,1000)
    h1 = ROOT.TH1F("Edep_device", "Energy deposition in SiC", 100, 0., 0.1)
    for i in range (len(my_g4p.edep_devices)):
        h1.Fill(my_g4p.edep_devices[i])
    h1.Draw()
    h1.GetXaxis().SetTitle("energy[MeV]")
    h1.GetYaxis().SetTitle("number")
    c1.SaveAs(path+"_energy.pdf")
    c1.SaveAs(path+"_energy.root")


def get1_beam_number(my_g4p):
    now = time.strftime("%Y_%m%d_%H%M")
    path = "output/" + "SiITk/" + now + "/" 
    create_path(path) 
    number = array('d',[999.])
    hittotal = array('d',[999.])
    # number[0] = int(-ele_current.max_BB_height/18.8)
    # hittotal[0]=my_g4p.hittotal
    # fout = ROOT.TFile(path + "SiITk.root", "RECREATE")
    # t_out = ROOT.TTree("tree", "beam_number")
    # t_out.Branch("cal_number", number, "cal_number/D")
    # t_out.Branch("real_number", hittotal, "real_number/D")
    # t_out.Fill()
    # t_out.Write()
    # fout.Close()

    c1=ROOT.TCanvas("c1","canvas1",1200,1000)
    h1 = ROOT.TH1F("Edep", "Energy deposition in W208", 100, 0., 1)
    h2 = ROOT.TH1F("Edep", "Energy deposition in W207", 100, 0., 1)
    h3 = ROOT.TH1F("Edep", "Energy deposition in W199", 100, 0., 1)
    for i in range (len(my_g4p.edep_devices)):
        h1.Fill(my_g4p.edep_devices[i])
        h2.Fill(my_g4p.edep_devices1[i])
        h3.Fill(my_g4p.edep_devices2[i])
    h1.Draw()
    h1.GetXaxis().SetTitle("energy[MeV]")
    h1.GetYaxis().SetTitle("number")
    c1.SaveAs(path+"_energy1.pdf")
    c1.SaveAs(path+"_energy1.root")
    
    c2=ROOT.TCanvas("c2","canvas2",1200,1000)
    h2.Draw()
    h2.GetXaxis().SetTitle("energy[MeV]")
    h2.GetYaxis().SetTitle("number")
    c2.SaveAs(path+"_energy2.pdf")
    c2.SaveAs(path+"_energy2.root")
    
    c3=ROOT.TCanvas("c3","canvas3",1200,1000)
    h3.Draw()
    h3.GetXaxis().SetTitle("energy[MeV]")
    h3.GetYaxis().SetTitle("number")
    c3.SaveAs(path+"_energy3.pdf")
    c3.SaveAs(path+"_energy3.root")
    
    # c4=ROOT.TCanvas("c4","canvas4",1000,1000)
    # h1.SetMarkerStyle(kFullCircle)
    # h2.SetMarkerStyle(kFullSquare)
    # h3.SetMarkerStyle(kFullTriangleUp)
    # h1.Draw()
    # h2.Draw("same")
    # h3.Draw("same")
    # h1.GetXaxis().SetTitle("energy[MeV]")
    # h1.GetYaxis().SetTitle("number")
    # c4.SaveAs(path+"_energyall.pdf")
    # c4.SaveAs(path+"_energyall.root")    
    


def cce(my_d,my_f,my_current, path):
    charge=array('d')
    x=array('d')
    for i in range(my_f.read_ele_num):
        x.append(i+1)
        sum_charge=0
        for j in range(my_current.n_bin):
            sum_charge=sum_charge+my_current.sum_cu[i].GetBinContent(j)*my_current.t_bin
        charge.append(sum_charge/1.6e-19)
    print(charge)
    n=int(len(charge))
    c1=ROOT.TCanvas("c1","canvas1",1000,1000)
    cce=ROOT.TGraph(n,x,charge)
    cce.SetMarkerStyle(3)
    cce.Draw()
    cce.SetTitle("Charge Collection Efficiency")
    cce.GetXaxis().SetTitle("elenumber")
    cce.GetYaxis().SetTitle("charge[Coulomb]")
    c1.SaveAs(path+"/cce.pdf")
    c1.SaveAs(path+"/cce.root")
    



def save_current_geant4(my_d,dset,event,my_current,my_g4p,start_n,my_f):
    if "planar3D" in my_d.det_model or "planarRing" in my_d.det_model:
        path = os.path.join('output', 'pin3D', dset.det_name, )
    elif "lgad3D" in my_d.det_model:
        path = os.path.join('output', 'lgad3D', dset.det_name, )
    create_path(path) 
    L = event
    #L is defined by different keys
    e_dep = array('d', [999.])
    time = array('d', [999.])
    current = array('d', [999.])
    fout = ROOT.TFile(os.path.join(path, "beam-monitor-current") + str(L) + ".root", "RECREATE")
    t_out = ROOT.TTree("tree", "signal")
    t_out.Branch("time", time, "time/D")
    
    for i in range(my_f.tol_elenumber):
        t_out.Branch("current"+str(i), current, "current"+str(i)+"/D")
        for j in range(my_current.n_bin):
            current[0]=my_current.sum_cu[i].GetBinContent(j)
            time[0]=j*my_current.t_bin
            t_out.Fill()
        t_out.Write()
    t_out.Branch("edep", e_dep, "edep/D")
    e_dep[0] = my_g4p.edep_devices[event-start_n]
    t_out.Fill()
    t_out.Write()
    fout.Close()

