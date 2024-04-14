# -*- encoding: utf-8 -*-
'''
Description: 
    Simulate induced current through BB or CSA amplifier 
@Date       : 2021/09/02 14:11:57
@Author     : tanyuhang
@version    : 1.0
'''

import math
import ROOT

import json

# TODO: Need to be TOTALLY rewritten

# CSA and BB amplifier simulation
class Amplifier:
    def __init__(self,my_current,amplifier,mintstep="50e-12"):
        """
        Description:
            Get current after CSA and BB amplifier
        Parameters:
        ---------
        CSA_par : dic
            All input paramters of CSA in CSA_par
        BB_par : dic
            All input paramters of BB in CSA_par
        mintstep : float
            The readout time step (bin width)        
        @Modify:
        ---------
            2021/09/09
        """
        self.ele = []

        ele_json = "./setting/electronics/" + amplifier + ".json"
        with open(ele_json) as f:
            ampl_par = json.load(f)

        self.ele_name = ampl_par['ele_name']
        self.read_ele_num = my_current.read_ele_num
        self.ampli_define(ampl_par)
        self.sampling_charge(my_current,mintstep)
        self.ampl_sim()

    def ampli_define(self,ampl_par):
        """
        Description:
            The parameters of CSA and BB amplifier.
            Details introduction can be got in setting module.
        @Modify:
        ---------
            2021/09/09
        """
        if ampl_par['ele_name'] == 'CSA':
            self.t_rise    = ampl_par['t_rise']
            self.t_fall    = ampl_par['t_fall']
            self.trans_imp = ampl_par['trans_imp']
            self.CDet      = ampl_par['CDet']
            self.BBW       = ampl_par['BBW']
            self.BBGain    = ampl_par['BBGain']
            self.BB_imp    = ampl_par['BB_imp']
            self.OscBW     = ampl_par['OscBW'] 

            tau_BB_RC = 1.0e-12*self.BB_imp*self.CDet     #BB RC
            tau_BB_BW = 0.35/(1.0e9*self.BBW)/2.2    #BB Tau

            self.tau_BBA = math.sqrt(pow(tau_BB_RC,2)+pow(tau_BB_BW,2))

        elif ampl_par['ele_name'] == 'BB':
            self.t_rise    = ampl_par['t_rise']
            self.t_fall    = ampl_par['t_fall']
            self.CDet      = ampl_par['CDet']
            self.BBW       = ampl_par['BBW']
            self.BBGain    = ampl_par['BBGain']
            self.BB_imp    = ampl_par['BB_imp']
            self.OscBW     = ampl_par['OscBW'] 
            ##BB simualtion parameter
            tau_C50 = 1.0e-12*50.*self.CDet          #Oscil. RC
            tau_BW = 0.35/(1.0e9*self.OscBW)/2.2      #Oscil. RC
            tau_BB_RC = 1.0e-12*self.BB_imp*self.CDet     #BB RC
            tau_BB_BW = 0.35/(1.0e9*self.BBW)/2.2    #BB Tau
            self.tau_scope = math.sqrt(pow(tau_C50,2)+pow(tau_BW,2))
            self.tau_BBA = math.sqrt(pow(tau_BB_RC,2)+pow(tau_BB_BW,2))

    def sampling_charge(self,my_current,mintstep):
        """ Transform current to charge 
        with changing bin width to oscilloscope bin width
        """
        self.max_num=[]
        self.itot=[]
        for i in range(self.read_ele_num):
            self.max_num.append(my_current.sum_cu[i].GetNbinsX())
            self.itot.append([0.0]*self.max_num[i])

        self.max_hist_num = my_current.n_bin
        self.undersampling = int(float(mintstep)/my_current.t_bin)
        self.time_unit = my_current.t_bin*self.undersampling
        self.CDet_j = 0     # CSA readout mode
        
        self.qtot = [0.0]*self.read_ele_num
        # get total charge
        for k in range(self.read_ele_num):
            i=0
            for j in range(0,self.max_hist_num,self.undersampling):
                self.itot[k][i] = my_current.sum_cu[k].GetBinContent(j)
                self.qtot[k] = self.qtot[k] + self.itot[k][i]*self.time_unit
                i+=1
        max_hist_num = int(self.max_hist_num/self.undersampling)
        IintTime = max(2.0*(self.t_rise+self.t_fall)*1e-9/self.time_unit,
                       3.0*self.tau_BBA/self.time_unit)
        self.IMaxSh = int(max_hist_num + IintTime)

    def ampl_sim(self):
        """
        Description:
            CSA and BB amplifier Simulation         
        Parameters:
        ---------
        arg1 : int
            
        @Modify:
        ---------
            2021/09/09
        """
        IMaxSh = self.IMaxSh
        preamp_Q = [] 
        for i in range(self.read_ele_num):
            preamp_Q.append([0.0]*IMaxSh)
        step=1

        for k in range(self.read_ele_num):
            for i in range(IMaxSh-step):
                if(i>0 and i <self.max_hist_num-step):
                    preamp_Q[k][i] = 0.0
                    for il in range(i,i+step):
                        preamp_Q[k][i] += self.itot[k][il]*self.time_unit
                elif (i != 0):
                    preamp_Q[k][i]=0.0

        if self.ele_name == 'CSA':
            for k in range(self.read_ele_num):
                self.CSA_p_init()
                for i in range(IMaxSh-step):
                    if i >= step:
                        dif_shaper_Q = preamp_Q[k][i]
                    else:
                        dif_shaper_Q = 0
                    for j in range(IMaxSh-i):
                        self.fill_CSA_out(i,j,dif_shaper_Q)
                    self.max_CSA(i)
                self.fill_CSA_th1f(k)

        elif self.ele_name == 'BB':
            for k in range(self.read_ele_num):
                self.BB_p_init()
                for i in range(IMaxSh-step):
                    if i >= step:
                        dif_shaper_Q = preamp_Q[k][i]
                    else:
                        dif_shaper_Q = 0
                    for j in range(IMaxSh-i):
                        self.fill_BB_out(i,j,dif_shaper_Q)
                self.fill_BB_th1f(k)

    def CSA_p_init(self):
        """ CSA parameter initialization"""
        t_rise = self.t_rise
        t_fall = self.t_fall
        self.tau_rise = t_rise/2.2*1e-9
        self.tau_fall = t_fall/2.2*1e-9
        if (self.tau_rise == self.tau_fall):
            self.tau_rise *= 0.9
        self.sh_max = 0.0  
        self.shaper_out_Q = [0.0]*self.IMaxSh
        self.shaper_out_V = [0.0]*self.IMaxSh

    def BB_p_init(self):
        """ BB parameter initialization"""
        self.Vout_scope = [0.0]*self.IMaxSh
        self.Iout_BB_RC = [0.0]*self.IMaxSh
        self.Iout_C50 = [0.0]*self.IMaxSh   
        self.BBGraph = [0.0]*self.IMaxSh

    def fill_CSA_out(self,i,j,dif_shaper_Q):
        """ Fill CSA out variable"""     
        self.shaper_out_Q[i+j] += self.tau_rise/(self.tau_fall-self.tau_rise) \
                                  * dif_shaper_Q*(math.exp(-j*self.time_unit
                                  / self.tau_fall)-math.exp(
                                  - j*self.time_unit/self.tau_rise))

    def fill_BB_out(self,i,j,dif_shaper_Q):
        """ Fill BB out variable"""   
        self.Iout_C50[i+j] += (dif_shaper_Q)/self.tau_scope \
                                * math.exp(-j*self.time_unit/self.tau_scope)
        self.Iout_BB_RC[i+j] += (dif_shaper_Q)/self.tau_BBA \
                                * math.exp(-j*self.time_unit/self.tau_BBA)
        self.BBGraph[i+j] = self.BBGain * self.Iout_BB_RC[i+j]
        R_in = 50 # the input impedance of the amplifier
        self.Vout_scope[i+j] = self.BBGain * R_in * self.Iout_BB_RC[i+j]
#        if (abs(self.BBGraph[i+j]) > 800):
#            self.BBGraph[i+j] = 800*self.BBGraph[i+j]/abs(self.BBGraph[i+j])

    def max_CSA(self,i):
        """ Get max out value of CSA"""               
        if (abs(self.shaper_out_Q[i]) > abs(self.sh_max)):
            self.sh_max = self.shaper_out_Q[i]

    def fill_CSA_th1f(self,k):
        """ Change charge to amplitude [mV]
            and save in the th1f
        """
        Ci = 3.5e-11  #fF
        Qfrac = 1.0/(1.0+self.CDet*1e-12/Ci)
        
        self.ele.append(ROOT.TH1F("electronics"+str(k+1), "electronics",
                                self.IMaxSh, 0, self.IMaxSh*self.time_unit))
        for i in range(self.IMaxSh):
            if self.sh_max == 0.0:
                self.shaper_out_V[i] = 0.0
            elif self.CDet_j == 0:

                #self.shaper_out_V[i] = self.shaper_out_Q[i]*self.trans_imp\
                #                       * 1e15*self.qtot[k]*Qfrac/self.sh_max     
                self.shaper_out_V[i] = self.shaper_out_Q[i]*self.trans_imp/(self.CDet*1e-12) #C_D=3.7pF
                
            elif self.CDet_j ==1:
                self.shaper_out_V[i] = self.shaper_out_Q[i]*self.trans_imp\
                                       * 1e15*self.qtot[k]/self.sh_max
            self.ele[k].SetBinContent(i,self.shaper_out_V[i])
        #Print the max current time of CSA
        min_CSA_height, max_CSA_height = min(self.shaper_out_V), max(self.shaper_out_V)
        if abs(min_CSA_height) < abs(max_CSA_height):
            time_t = self.shaper_out_V.index(max_CSA_height)
        else:
            time_t = self.shaper_out_V.index(min_CSA_height)
        print("CSA peak time={:.2e}".format(time_t*self.time_unit))

    def fill_BB_th1f(self,k):
        """ Change charge to amplitude [V]
            and save in the th1f
        """
        
        self.ele.append(ROOT.TH1F("electronics BB"+str(k+1),"electronics BB",
                                self.IMaxSh,0,self.IMaxSh*self.time_unit))
        for i in range(len(self.Vout_scope)+1):
            if i == 0:
                self.ele[k].SetBinContent(i,0)
            else:
                self.ele[k].SetBinContent(i,self.Vout_scope[i-1])
        # Print the max current time of BB
        min_BB_height, max_BB_height = min(self.Vout_scope), max(self.Vout_scope)
        if abs(min_BB_height) < abs(max_BB_height):
            time_t = self.Vout_scope.index(max_BB_height)
            self.max_BB_height = abs(max_BB_height)
        else:
            time_t = self.Vout_scope.index(min_BB_height)
            self.max_BB_height = abs(min_BB_height)
        print("BB peak time={:.2e}".format(time_t*self.time_unit))

    def __del__(self):
        pass
