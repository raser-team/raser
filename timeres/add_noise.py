#!/usr/bin/env python3

"""
author: tanyuhang
time: 2021.3.8
Use: 1.Read the data of Raser induced current
     2.Add the noise on induced current
     3.Get the time resolution with constant CFD   
"""

from array import array
import contextlib
import os
import sys
import re
import ROOT
import math
from util.output import output

noise_avg = -0.133
noise_rms = 2.671

# ROOT file parameters difinition
Events=array('i',[0])
h_pulse_time=ROOT.std.vector(float)()

h_pulse_height=ROOT.std.vector(float)()
h_nps_height=ROOT.std.vector(float)()
h_max_nps_height=array('f',[0])
h_max_pulse_time=array('f',[0])
h_time_resolution=array('f',[0])
h_per80_20_dvdt=array('f',[0])
h_per80_20_time=array('f',[0])


h_dVdt=array('f',[0])

h_noise_height_jitter=array('f',[0])
h_noise_height_RMS=array('f',[0])
h_noise_height=ROOT.std.vector(float)()

h_pulse_time.clear()
h_pulse_height.clear()
h_nps_height.clear()
h_max_nps_height[0]=0.0
h_max_pulse_time[0]=0.0
h_time_resolution[0]=0.0
h_per80_20_dvdt[0]=0.0
h_per80_20_time[0]=0.0

h_dVdt[0]=0.0

h_noise_height_jitter[0]=0.0
h_noise_height_RMS[0]=0.0
h_noise_height.clear()


# The judge parameter configuration and read data
class NoiseSetting:
    def __init__(self):
        """
        @description: The judge parameter configuration
         
        @param:
            thre_vth - Signal threshold
            CFD - Constant ratio timing ratio		 
        @Returns:
            None
        @Modify:
            2021/08/31
        """
        self.thre_vth=18 # mv
        self.CFD=0.5
        self.effective_event_number=0
        self.CFD_time=[]
        self.CFD_jitter=[]

        self.max_voltage=[]
        self.current_integral=[]
        
    def create_outpath(self,path):
        """
        @description: If the path is not exit, create the path
         
        @param:
            None
        @Returns:
            None
        @Modify:
            2021/08/31
        """
        if not os.access(path, os.F_OK):
            os.makedirs(path, exist_ok=True)

    @contextlib.contextmanager
    def open_func(self,file_name):
        """
        @description: Open file with context manager
         
        @param:
            None
        @Returns:
            None
        @Modify:
            2021/08/31
        """
        # print('open file:', file_name, 'in __enter__')
        file_handler = open(file_name, 'r')

        try:
            yield file_handler
        except Exception as exc:
            print('the exception was thrown')
        finally:
            # print('close file:', file_name, 'in __exit__')
            file_handler.close()
        return

    def write_list(self,path,list_c):
        """
        @description: Save the file contents in list_c
         
        @param:
            None
        @Returns:
            None
        @Modify:
            2021/08/31
        """
        with self.open_func(path) as file_in:
            for line in file_in:
                if not (is_number(line.split(",")[0])):
                    continue
                list_c.append(line)

# Add noise in the wavefroms and save the data in dictionaries
class AddNoise:
    def __init__(self):
        self.time=0.0
        self.ampl_nps = 0.0
        self.ampl_s = 0.0
        self.time_list = []
        self.ampl_paras = {}
        self.ampl_nps_list = []
        self.ampl_s_list = []
        self.noise_height_list = []

        self.list_c = []
        self.Fv = 0    
        self.dVdt = 0
        self.CFD_time_r = 0
        self.noist_height_jitter = 0
        self.per80_20_time = 0
        self.per80_20_dvdt = 0

    def add_n(self,list_c):
        """
        @description: 
            Add Gaussian noise from data fitting at the waveforms
        @param:
            nps -- Noise plus signal
            s -- Signal
        @Returns:
            None
        @Modify:
            2021/08/31
        """
        ROOT.gRandom.SetSeed(0)
        random_gauss = ROOT.gRandom.Gaus
        for j in range (0,len(list_c)):
            time= float(list(filter(None,list_c[j].split(",")))[0])
            noise_height=random_gauss(noise_avg,noise_rms)
            ampl_nps=-float(list(filter(None,list_c[j].split(",")))[1])+noise_height
            ampl_s=-float(list(filter(None,list_c[j].split(",")))[1])
            self.time_list.append(time)
            self.noise_height_list.append(noise_height)
            self.ampl_nps_list.append(ampl_nps)
            self.ampl_s_list.append(ampl_s)
        self.noise_height_RMS= math.sqrt(sum([x**2 
                                              for x in self.noise_height_list])
                                              /len(self.noise_height_list))
        h_noise_height_RMS[0]=self.noise_height_RMS
        self.get_max()
        self.get_integral()
        self.fill_dic()

    def get_max(self):
        """
        @description: 
            Get the max waveform height and height index
        @param:
            None
        @Returns:
            None
        @Modify:
            2021/08/31
        """
        self.max_nps_height=max(self.ampl_nps_list)
        self.max_index=self.ampl_nps_list.index(max(self.ampl_nps_list))
        self.max_pulse_time=self.time_list[self.max_index]
        self.max_s_height=max(self.ampl_s_list)
        self.max_s_index=self.ampl_s_list.index(max(self.ampl_s_list))
        self.max_s_time=self.time_list[self.max_s_index]

    def get_integral(self):
        """
        @description: 
            Get the time integral of the waveform
        @param:
            None
        @Returns:
            None
        @Modify:
            2022/08/08
        """
        self.integral_nps_height=0.
        self.integral_s_height=0.

        for i in range(len(self.time_list)-1):
            self.integral_nps_height+=self.ampl_nps_list[i]*(self.time_list[i+1]-self.time_list[i])
            self.integral_s_height+=self.ampl_s_list[i]*(self.time_list[i+1]-self.time_list[i])

        
    def fill_dic(self):
        """
        @description: 
            Fill the parameter in the ampl_paras dictionaries
        @param:
            None
        @Returns:
            None
        @Modify:
            2021/08/31
        """
        self.ampl_paras["max_nps_height"] = self.max_nps_height
        self.ampl_paras["max_pulse_time"] = self.max_pulse_time
        self.ampl_paras["ampl_nps_list"] =  self.ampl_nps_list
        self.ampl_paras["ampl_s_list"] =    self.ampl_s_list
        self.ampl_paras["max_s_height"] =   self.max_s_height
        self.ampl_paras["max_s_time"] =     self.max_s_time
        self.ampl_paras["integral_nps_height"] = self.integral_nps_height
        self.ampl_paras["integral_s_height"] = self.integral_s_height

        self.ampl_paras["time_list"] =         self.time_list
        self.ampl_paras["noise_height_list"] = self.noise_height_list

# Root file init definition and fill
class RootFile:
    def init_parameter(self):
        h_max_nps_height[0] = 0.0
        h_max_pulse_time[0] = 0.0  
        h_time_resolution[0] = 0.0
        h_noise_height_jitter[0] = 0.0
        h_per80_20_dvdt[0]=0.0
        h_per80_20_time[0]=0.0
        h_dVdt[0] = 0.0
        h_pulse_time.clear()
        h_nps_height.clear()	
        h_pulse_height.clear()	
        h_noise_height.clear()

    def root_define(self):
        """ Root tree branch definition """
        self.tree_out=ROOT.TTree('tree','tree')
        self.tree_out.Branch('Events',Events,'Events/I')
        self.tree_out.Branch('h_pulse_time',h_pulse_time)
        self.tree_out.Branch('h_pulse_height',h_pulse_height)
        self.tree_out.Branch('h_nps_height',h_nps_height)  
        self.tree_out.Branch('h_dVdt',h_dVdt,'h_dVdt/F')
        self.tree_out.Branch('h_noise_height',h_noise_height)  # noise

        self.tree_out.Branch('h_max_nps_height',
                              h_max_nps_height,'h_max_nps_height/F')    
        self.tree_out.Branch('h_max_pulse_time',
                              h_max_pulse_time,'h_max_pulse_time/F')
        self.tree_out.Branch('h_time_resolution',
                              h_time_resolution,'h_time_resolution/F')
        self.tree_out.Branch('h_noise_height_jitter',
                              h_noise_height_jitter,
                             'h_noise_height_jitter/F')
        self.tree_out.Branch('h_noise_height_RMS',
                              h_noise_height_RMS,
                             'h_noise_height_RMS/F')               
        self.tree_out.Branch('h_per80_20_dvdt',
                              h_per80_20_dvdt,
                             'h_per80_20_dvdt/F')
        self.tree_out.Branch('h_per80_20_time',
                              h_per80_20_time,
                             'h_per80_20_time/F')
    
          
    def fill_ampl(self,addNoise,rset,max_height,max_time):
        """ Fill parameters """
        h_max_nps_height[0]=addNoise.ampl_paras[max_height]
        h_max_pulse_time[0]=addNoise.ampl_paras[max_time]                      
        h_time_resolution[0]=addNoise.CFD_time_r

        rset.CFD_time.append(addNoise.CFD_time_r)
        rset.CFD_jitter.append(addNoise.noist_height_jitter)
        rset.max_voltage.append(addNoise.ampl_paras["max_s_height"])
        rset.current_integral.append(addNoise.ampl_paras["integral_s_height"])
        
        h_dVdt[0]=addNoise.dVdt
        h_noise_height_jitter[0]=addNoise.noist_height_jitter
        h_per80_20_dvdt[0]=addNoise.per80_20_dvdt
        h_per80_20_time[0]=addNoise.per80_20_time
        addNoise.Fv=1  
              
    def fill_vector(self,rset,addNoise):
        """ Fill parameters from vector """ 
        if addNoise.Fv==1 :
            for j in range(0,len(addNoise.time_list)):
                h_pulse_time.push_back(addNoise.time_list[j])
                h_pulse_height.push_back(addNoise.ampl_paras["ampl_s_list"][j])
                h_nps_height.push_back(addNoise.ampl_paras["ampl_nps_list"][j])
                h_noise_height.push_back(addNoise.ampl_paras["noise_height_list"][j])

def judge_threshold(addNoise,rset,tree_class):
    """
    @description: 
        Judge the pluse height of waveform is larger than threshold or not.
        If Yes, the parameters of the waveform will be saved.
    @param:
        None
    @Returns:
        None
    @Modify:
        2021/08/31
    """
    #if (addNoise.ampl_paras[max_height]>rset.thre_vth and addNoise.ampl_paras[max_time]<80):
    get_CFD_time(addNoise,addNoise.ampl_paras,rset)
    tree_class.fill_ampl(addNoise,rset,"max_nps_height","max_pulse_time")

def get_CFD_time(addNoise,Ampl_paras,rset):
    """
    @description: 
        Get the time resolution for constance CFD value
        Time resolution is jitter + Landau fluctuation
    @param:
        None
    @Returns:
        None
    @Modify:
        2021/08/31
    """
    noise_from_sensor_capacitance()
    random_gauss = ROOT.gRandom.Gaus

    CFD_time=0.0
    jitter=9999
    dVdt=0.0
    per20_time = 0.0
    per20_ampl = 0.0
    per80_time = 0.0
    per80_ampl = 0.0

    time_list=[]
    time_list=addNoise.time_list
    CFD50 = 0
    CFD20 = 0
    CFD80 = 0
    for i in range (0,len(time_list)):
        if abs(Ampl_paras["ampl_nps_list"][i])>=abs(Ampl_paras["max_nps_height"]*rset.CFD) \
           and time_list[i]<Ampl_paras["max_pulse_time"] and CFD50==0 \
           and time_list[i+3]<Ampl_paras["max_pulse_time"] and time_list[i-3]>1.0e-9 :
            
            dVdt=(Ampl_paras["ampl_nps_list"][i+3]
                  -Ampl_paras["ampl_nps_list"][i-3]) \
                  /(time_list[i+3]-time_list[i-3])/1e9/1.38 # parameterized
                   
            if (dVdt!=0):
                jitter=random_gauss(0,addNoise.noise_height_RMS/dVdt)
                # 3.85 is the initial time by personal customization 
                CFD_time = 3.85+time_list[i]*1e9+jitter
            else:
                CFD_time=0
            CFD50 = 1

        if Ampl_paras["ampl_nps_list"][i]>=Ampl_paras["max_nps_height"]*0.2 \
           and time_list[i]<Ampl_paras["max_pulse_time"] and CFD20 == 0:
            per20_time = time_list[i]
            per20_ampl = Ampl_paras["ampl_nps_list"][i]
            CFD20 = 1

        if Ampl_paras["ampl_nps_list"][i]>=Ampl_paras["max_nps_height"]*0.8 \
           and time_list[i]<Ampl_paras["max_pulse_time"] and CFD80 == 0:
            per80_time = time_list[i]
            per80_ampl = Ampl_paras["ampl_nps_list"][i]
            CFD80 = 1            

    # Fill the parameter to the AddNoise class
    addNoise.CFD_time_r = CFD_time
    addNoise.dVdt = dVdt
    addNoise.noist_height_jitter = jitter 
    if CFD20 == 1 and CFD80 == 1:
        addNoise.per80_20_time =  per80_time - per20_time 
        if per80_time - per20_time > 0:
            addNoise.per80_20_dvdt =  (per80_ampl - per20_ampl) /  (per80_time - per20_time)     
        else:
            addNoise.per80_20_dvdt = 0.0
    else:
        addNoise.per80_20_time = 0.0
        addNoise.per80_20_dvdt = 0.0

def noise_from_sensor_capacitance():
    """
    @description: 
        This is the noise from the sensor capacitance.
        The model does not complete.
    @param:
        None
    @Returns:
        None
    @Modify:
        2021/08/31
    """
    perm_sic = 9.76  # Permittivity SiC
    DCap = 5000*5000/100*perm_sic*8.851e-3 # fF backplane
    DCap += 0.014*perm_sic*4*5000  # fF n layer
    DCap +=50 # fF fixed 
    noise_sen = 2.0*DCap/math.sqrt(1) 

def save_waveform_threshold(output_file,event_n,addNoise):
    """ Save waveform in the outputfile """ 
    # print(output_file)
    output_path = output_file + "out_txt/"
    if not os.access(output_path, os.F_OK):
        os.makedirs(output_path, exist_ok=True) 
    f1 = open(output_path+"t_"+str(event_n)+".csv","w")
    f1.write("time[ns], Amplitude [mV] \n")
    for i in range(len(addNoise.ampl_paras["time_list"])):
        time = addNoise.ampl_paras["time_list"][i]
        nps =   addNoise.ampl_paras["ampl_nps_list"][i]
        f1.write("%s,%s \n"%(time,nps))
    f1.close()
    return event_n+1        

def FormatLegend(leg):
    """ ROOT Lengend setting """ 
    leg.SetBorderSize(False)
    leg.SetTextFont(43)
    leg.SetTextSize(40)
    leg.SetFillStyle(1)
    leg.SetFillColor(1)
    leg.SetLineColor(0) 
    leg.SetLineStyle(0)

def set_color_marker(color,marker,i,gr):
    """ ROOT color and marker setting """ 
    f=marker[i]
    gr.SetMarkerStyle(f)
    gr.SetMarkerSize(1)
    k=color[i]
    gr.SetLineColor(k)
    gr.SetLineWidth(2)
    gr.SetMarkerColor(k)
    return gr

def fill_legend(leg,gr,name):
    """ Fill graph name in lengend """ 
    leg.AddEntry(gr,name,"LP")
    return leg

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

def draw_2D_CFD_time(CFD_time,out_put,model):
    """
    @description: 
        Draw and fit time distribution.
        Get the time resolution with constant CFD
    @param:
        None
    @Returns:
        None
    @Modify:
        2021/08/31
    """
    c1 =  ROOT.TCanvas("c1"+model,"c1"+model,200,10,800,600)
    ROOT.gStyle.SetOptStat(0)
    c1.SetGrid()
    c1.SetLeftMargin(0.2)
    c1.SetTopMargin(0.12)
    c1.SetBottomMargin(0.2)
    # Define lengend th1f and root gstyle
    leg = ROOT.TLegend(0.25, 0.6, 0.35, 0.8)
    if "jitter" in model:
        step = 0.01
        x2_min = -0.2
        x2_max = 0.2
        n2_bin = int((x2_max-x2_min)/step)
        histo=ROOT.TH1F("","",n2_bin,x2_min,x2_max)
        for i in range(0,len(CFD_time)):
            if CFD_time[i]< 9000:	
                histo.Fill(CFD_time[i])
    else:
        step = 0.05
        x2_min = 4.8
        x2_max = 5.6
        n2_bin = int((x2_max-x2_min)/step)
        histo=ROOT.TH1F("","",n2_bin,x2_min,x2_max)
        for i in range(0,len(CFD_time)):
            if CFD_time[i]>0:
                histo.Fill(CFD_time[i])
    # Fit data
    fit_func_1,sigma,error=fit_data_normal(histo,x2_min,x2_max)# in nanosecond
    sigma=sigma*1000 # in picosecond
    error=error*1000
    histo=ToA_TH1F_define(histo)
    # Legend setting
    leg.AddEntry(fit_func_1,"Fit","L")
    leg.AddEntry(histo,"Sim","L")
    # Draw
    histo.Draw()
    fit_func_1.Draw("same")
    leg.Draw("same")
    # Text set
    root_tex_time_resolution(sigma,error)
    # Save
    c1.SaveAs(out_put+'/'+model+".pdf")
    c1.SaveAs(out_put+'/'+model+".C")
    del c1
    return sigma, error

def draw_max_voltage(max_voltage_list,out_put,model):
    """
    @description: 
        Draw and fit max voltage, mainly for getting gain efficiency
    @param:
        None
    @Returns:
        None
    @Modify:
        2022/08/08
    """
    c1 =  ROOT.TCanvas("c1"+model,"c1"+model,200,10,800,600)
    ROOT.gStyle.SetOptStat(0)
    c1.SetGrid()
    c1.SetLeftMargin(0.2)
    c1.SetTopMargin(0.12)
    c1.SetBottomMargin(0.2)
    # Define lengend th1f and root gstyle
    leg = ROOT.TLegend(0.25, 0.6, 0.35, 0.8)
    x2_min = min(max_voltage_list)
    # Exclude data with great deviation
    x2_max = sorted(max_voltage_list)[int(len(max_voltage_list)*0.95)]

    n2_bin = 100
    #test
    histo=ROOT.TH1F("","",n2_bin,x2_min,x2_max)
    for i in range(0,len(max_voltage_list)):
        #if max_voltage_list[i]>0:
        histo.Fill(max_voltage_list[i])
    # Fit data
    fit_func_1,sigma,error=fit_data_normal(histo,x2_min,x2_max)
    histo=max_voltage_TH1F_define(histo)
    # Legend setting
    leg.AddEntry(fit_func_1,"Fit","L")
    leg.AddEntry(histo,"Sim","L")
    # Draw
    histo.Draw()
    fit_func_1.Draw("same")
    leg.Draw("same")
    # Text set
    root_tex_max_voltage(sigma,error)
    # Save
    c1.SaveAs(out_put+model+"/max_voltage.pdf")
    c1.SaveAs(out_put+model+"/max_voltage.C")
    del c1
    return sigma, error
    
def draw_current_integral(current_integral_list,out_put,model):
    """
    @description: 
        Draw and fit current integral, mainly for getting gain efficiency
    @param:
        None
    @Returns:
        None
    @Modify:
        2022/08/08
    """
    c1 =  ROOT.TCanvas("c1"+model,"c1"+model,200,10,800,600)
    ROOT.gStyle.SetOptStat(0)
    c1.SetGrid()
    c1.SetLeftMargin(0.2)
    c1.SetTopMargin(0.12)
    c1.SetBottomMargin(0.2)
    # Define lengend th1f and root gstyle
    leg = ROOT.TLegend(0.25, 0.6, 0.35, 0.8)
    x2_min = min(current_integral_list)
    # Exclude data with great deviation
    x2_max = sorted(current_integral_list)[int(len(current_integral_list)*0.95)]
    n2_bin = 100
    #test
    histo=ROOT.TH1F("","",n2_bin,x2_min,x2_max)
    for i in range(0,len(current_integral_list)):
        #if current_integral_list[i]>0:
        histo.Fill(current_integral_list[i])
    # Fit data
    fit_func_1,sigma,error=fit_data_normal(histo,x2_min,x2_max)
    histo=current_integral_TH1F_define(histo)
    # Legend setting
    leg.AddEntry(fit_func_1,"Fit","L")
    leg.AddEntry(histo,"Sim","L")
    # Draw
    histo.Draw()
    fit_func_1.Draw("same")
    leg.Draw("same")
    # Text set
    root_tex_current_integral(sigma,error)
    # Save
    c1.SaveAs(out_put+"/"+model+"/current_integral.pdf")
    c1.SaveAs(out_put+"/"+model+"/current_integral.C")
    del c1
    return sigma, error    

def fit_data_normal(histo,x_min,x_max):
    """ Fit data distribution """
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

def ToA_TH1F_define(histo):
    """ TH1f definition """
    histo.GetXaxis().SetTitle("ToA [ns]")
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

def max_voltage_TH1F_define(histo):
    """ TH1f definition """
    histo.GetXaxis().SetTitle("max voltage [V]")
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

def current_integral_TH1F_define(histo):
    """ TH1f definition """
    histo.GetXaxis().SetTitle("current integral [a.u.]")
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

def root_tex_time_resolution(sigma,error):
    """　Latex definition """
    tex = ROOT.TLatex()
    tex.SetNDC(1)
    tex.SetTextFont(43)
    tex.SetTextSize(25)
    tex.DrawLatexNDC(0.65, 0.7, "CFD=0.5")
    tex.DrawLatexNDC(0.65, 0.6, "#sigma = %.1f #pm %.1f ps"%(sigma,error))

def root_tex_max_voltage(sigma,error):
    """　Latex definition """
    tex = ROOT.TLatex()
    tex.SetNDC(1)
    tex.SetTextFont(43)
    tex.SetTextSize(25)
    tex.DrawLatexNDC(0.65, 0.6, "V_{max}= %.1f #pm %.1f V"%(sigma,error))

def root_tex_current_integral(sigma,error):
    """　Latex definition """
    tex = ROOT.TLatex()
    tex.SetNDC(1)
    tex.SetTextFont(43)
    tex.SetTextSize(25)
    tex.DrawLatexNDC(0.65, 0.6, "Q = %.2g #pm %.1g a.u."%(sigma,error))

def root_set():
    """ ROOT gstyle setting"""
    ROOT.gStyle.SetOptFit()
    ROOT.gStyle.SetOptStat(0)
    ROOT.gROOT.SetBatch(1)

def save_time_resolution(input_file,sigma,error,efficiency,sigma_jitter,Landau_timing):
    o_ls=input_file.split("/")[:]
    out_file=output(__file__, o_ls[2])+"/time_resolution_scan.csv"

    with open(out_file,"a") as f:
        f.write("sigma,error,efficiency,jitter,Landau_timing \n")
        f.write(str(sigma) + "," + str(error) + ","
                + str(efficiency) + "," + str(sigma_jitter) + "," + str(Landau_timing) + "\n")

def save_gain_efficiency(input_file, max_voltage, error_max_voltage, current_integral, error_current_integral):
    o_ls=input_file.split("/")[:]
    out_file=output(__file__, o_ls[2])+"/gain_efficiency_scan.csv"

    with open(out_file,"a") as f:
        f.write("max_voltage, error_max_voltage, current_integral, error_current_integral \n")
        f.write(str(max_voltage)+ "," + str(error_max_voltage) + ","
                + str(current_integral) + ","+ str(error_current_integral) + "\n")
                
# Loop and add noise in the raser
def loop_addNoise(input_file,rset,tree_class):
    for root,dirs,files in os.walk(input_file):
        for file in files:    
            if rset.effective_event_number<100000:    
                print("................events:%s..............."%(Events[0])) 
                print("................Save events:%s..............."%rset.effective_event_number)
                path = os.path.join(input_file, file)
                Events[0]+=1

                addNoise = AddNoise() 
                rset.write_list(path,addNoise.list_c)
                if len(addNoise.list_c)>5:
                    addNoise.add_n(addNoise.list_c)
                    judge_threshold(addNoise,rset,tree_class) 
                    tree_class.fill_vector(rset,addNoise) 
                    #if addNoise.CFD_time_r>0:      
                    tree_class.tree_out.Fill()
                    rset.effective_event_number += 1
                    tree_class.init_parameter()
            else:
                break
    efficiency = rset.effective_event_number / Events[0]
    return efficiency

def main(kwargs):
    model = kwargs['det_name']
    # Outfilename and init_parameter
    rset = NoiseSetting()
    output_path = output(__file__, model)
    input_file = "output/gen_signal/" + model + "/batch"
    # Root defined
    out_root_f=ROOT.TFile(output_path+"/out.root","RECREATE")
    tree_class=RootFile()
    tree_class.root_define()
    # Add noise
    efficiency = loop_addNoise(input_file,rset,tree_class)
    # Draw time resolution for constant CFD
    sigma, error=draw_2D_CFD_time(rset.CFD_time,output_path,'time_resolution')
    sigma_jit, error_jit=draw_2D_CFD_time(rset.CFD_jitter,output_path,'jitter')
    Landau_timing = math.sqrt(abs(sigma*sigma-sigma_jit*sigma_jit))
    tree_class.tree_out.Write()
    out_root_f.Close()
    save_time_resolution(input_file,sigma,error,efficiency,sigma_jit,Landau_timing)  

    if "lgad3D" in model:
        # Draw gain efficiency, max voltage and current integral
        max_voltage, error_max_voltage = draw_max_voltage(rset.max_voltage,output_path)
        current_integral, error_current_integral = draw_current_integral(rset.current_integral,output_path)
        save_gain_efficiency(input_file, max_voltage, error_max_voltage, current_integral, error_current_integral)

if __name__ == '__main__':
    args = sys.argv[1:]
    kwargs = {}
    kwargs['det_name'] = args[0]
    main(kwargs)

