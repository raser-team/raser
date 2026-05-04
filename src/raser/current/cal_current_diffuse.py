# -*- encoding: utf-8 -*-

'''
Description:  
    Simulate e-h pairs diffusing and calculate induced current in MAPS
@Date       : 2023
@Author     : Haobo Wang, Yiming Hu
@version    : 2.0
'''

import random
import math
import os

import numpy as np
import ROOT
ROOT.gROOT.SetBatch(True)

from .model import Material
from ..interaction.carrier_list import PixelCarrierListFromG4P
from ..util.math import Vector

t_bin = 50e-12
t_end = 1e-6
t_start = 0
delta_t = 50e-12
pixel = 25 #um
min_intensity = 1 # V/cm

class CarrierCluster:
    """
    Description:
        Definition of carriers and the record of their movement
    Parameters:
        x_init, y_init, z_init, t_init : float
            initial space and time coordinates in um and s
        charge : float
            a set of drifting carriers, absolute value for number, sign for charge
    Attributes:
        x, y, z, t : float
            space and time coordinates in um and s
        path : float[]
            recording the carrier path in [x, y, z, t]
        charge : float
            a set of drifting carriers, absolute value for number, sign for charge
        signal : float[]
            the generated signal current on the reading electrode
        end_condition : 0/string
            tag of how the carrier ended drifting
    Modify:
        2022/10/28
    """
    def __init__(self, x_init, y_init, z_init, t_init, charge, read_ele_num):
        self.x = x_init
        self.y = y_init
        self.z = z_init
        self.t = t_init
        self.t_end = t_end
        self.pixel = pixel
        self.path = [[x_init, y_init, z_init, t_init]]
        self.signal = [[] for j in range(int(read_ele_num))]
        self.diffuse_end_condition = 0
        self.row=0
        self.column=0

        self.charge = charge       

    def diffuse_single_step(self,my_d):
        delta_t = t_bin
        #e_field = my_f.get_e_field(self.x,self.y,self.z)
        intensity = 0

        kboltz = 8.617385e-5 #eV/K
        mobility = Material(my_d.material)
        Neff = float(my_d.doping['Donors']) - float(my_d.doping['Acceptors']) # assuming able to convert
        mu = mobility.cal_mobility(my_d.temperature, Neff, self.charge, intensity)
        diffusion = (2.0*kboltz*mu*my_d.temperature*delta_t)**0.5
        #diffusion = 0.0
        dif_x=random.gauss(0.0,diffusion)*1e4
        dif_y=random.gauss(0.0,diffusion)*1e4
        dif_z=0

        if((self.x+dif_x)>=my_d.l_x): 
            self.x = my_d.l_x
        elif((self.x+dif_x)<0):
            self.x = 0
        else:
            self.x = self.x+dif_x
        # y axis
        if((self.y+dif_y)>=my_d.l_y): 
            self.y = my_d.l_y
        elif((self.y+dif_y)<0):
            self.y = 0
        else:
            self.y = self.y+dif_y
        # z axis
        if((self.z+dif_z)>=my_d.l_z): 
            self.z = my_d.l_z
        elif((self.z+dif_z)<0):
            self.z = 0
        else:
            self.z = self.z+dif_z
        #time
        self.t = self.t+delta_t
        #record
        self.path.append([self.x,self.y,self.z,self.t])

    def diffuse_end(self):
        if (self.z<=0):
        #    self.end_condition = "out of bound"
            self.diffuse_end_condition = "collect"
        return self.diffuse_end_condition

    def diffuse_not_in_sensor(self,my_d):
        if (self.x<=0) or (self.x>=my_d.l_x)\
            or (self.y<=0) or (self.y>=my_d.l_y)\
            or (self.z>=my_d.l_z):
            self.diffuse_end_condition = "out of bound"
        mod_x = self.x % self.pixel
        mod_y = self.y % self.pixel
        if ((mod_x> 7.5) & (mod_x<17.5)) & ((mod_y> 7.5) & (mod_y<17.5)) \
           & (self.t <= self.t_end):
            self.diffuse_end_condition = "collect"
        return self.diffuse_end_condition

        '''
        if (self.z<= 0) or (self.t >= self.t_end):
            self.diffuse_end_condition = "collect"
        #print("diffuse end")
        return self.diffuse_end_condition
        '''

    def pixel_position(self,my_d):
        if self.diffuse_end_condition == "collect":
            self.row = self.x // self.pixel
            self.column = self.y // self.pixel
        else:
            self.row = -1
            self.column = -1
        return  self.row,self.column,abs(self.charge)



class CalCurrentDiffuse:
    """Calculation of diffusion electrons in pixel detector"""
    def __init__(self, my_d, my_g4):
        batch = len(my_g4.localpositions)
        layer = len(my_g4.ltz)
        G4P_carrier_list = PixelCarrierListFromG4P(my_d, my_g4)                 
        self.collected_charge=[] #temp paras don't save as self.
        self.sum_signal = []
        self.event = []        
        for k in range(batch):
            l_dict = {}
            signal_charge = []
            for j in range(layer):
                self.electrons = []
                self.charge,self.collected_charge = [],[]#same like before
                self.row,self.column=[],[]
                Hit = {'index':[],'charge':[]} 
                #print(len(G4P_carrier_list.ionized_pairs[k][j]))
                print("%f pairs of carriers are generated from G4 in event_ %d layer %d" %(sum(G4P_carrier_list.ionized_pairs[k][j]),k,j))
                #print(G4P_carrier_list.track_position[k][j])
                for i in range(len(G4P_carrier_list.track_position[k][j])):
                    electron = CarrierCluster(G4P_carrier_list.track_position[k][j][i][0],\
                                       G4P_carrier_list.track_position[k][j][i][1],\
                                       G4P_carrier_list.track_position[k][j][i][2],\
                                       0,\
                                       -1*G4P_carrier_list.ionized_pairs[k][j][i],\
                                       1)
                    if not electron.diffuse_not_in_sensor(my_d):
                        self.electrons.append(electron)
                self.diffuse_loop(my_d)

                Xbins=int(my_d.l_x // electron.pixel)
                Ybins=int(my_d.l_y // electron.pixel)
                Xup=my_d.l_x // electron.pixel
                Yup=my_d.l_y // electron.pixel
                test_charge = ROOT.TH2F("charge", "charge",Xbins, 0, Xup, Ybins, 0, Yup)
                for i in range(len(self.row)):
                    #test_charge.SetBinContent(int(self.row[i]),int(self.column[i]),self.charge[i])
                    test_charge.Fill(self.row[i],self.column[i],self.charge[i])
                    
                sum_fired = ROOT.TH2F("charge", "Pixel Detector charge",Xbins, 0, Xup, Ybins, 0, Yup)
                sum_fired.Add(test_charge)
                
                self.sum_charge = ROOT.TH2F("charge", "Pixel Detector charge",Xbins, 0, Xup, Ybins, 0, Yup)
                self.sum_charge.Add(test_charge)
                
                test_charge.Reset
                collected_charge=self.pixel_charge(my_d,Xbins,Ybins)
                signal_charge.append(collected_charge)
                
                Hit["index"],Hit["charge"] = self.pixel_fired(sum_fired,Xbins,Ybins)
                l_dict[j] = Hit
                print("%f electrons are collected in event_ %d,layer %d" %(sum(self.charge),k,j))
            self.sum_signal.append(signal_charge)
            self.event.append(l_dict)
            #print(signal_charge)
            del signal_charge
        #print(self.sum_signal)
        #print(self.event)

    def diffuse_loop(self, my_d):
        for electron in self.electrons:
            while not electron.diffuse_not_in_sensor(my_d):
                electron.diffuse_single_step(my_d)
                electron.diffuse_end()
            x,y,charge_quantity = electron.pixel_position(my_d)
            if (x != -1)&(y != -1): 
                self.row.append(x)
                self.column.append(y)
                self.charge.append(charge_quantity)

    def pixel_charge(self,my_d,Xbins,Ybins):
        for x in range(Xbins):
            for y in range(Ybins):
                charge =self.sum_charge.GetBinContent(x,y)
                if (charge>0.2):
                    self.collected_charge.append([x,y,charge])        
        return self.collected_charge
    
    def pixel_fired(self,tot,Xbins,Ybins):
        Hit = {'index':[],'charge':[]} 
        for x in range(Xbins):
            for y in range(Ybins):
                charge =tot.GetBinContent(x,y)
                if (charge>0.2):
                    Hit["index"].append([x,y])
                    Hit["charge"].append(charge)       
        return Hit["index"],Hit["charge"]

