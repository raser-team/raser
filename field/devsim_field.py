#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
@File    :   devsim.py
@Time    :   2023/06/04
@Author  :   Henry Stone 
@Version :   1.0
'''

import pickle
import ROOT
import numpy as np
from scipy.interpolate import interp1d as p1d
from scipy.interpolate import interp2d as p2d
from scipy.interpolate import griddata
from scipy.interpolate import LinearNDInterpolator as LNDI

diff_res = 1e-5 # difference resolution in cm

x_bin = 1000
y_bin = 1000
z_bin = 1000

class DevsimField:
    def __init__(self, device_name, dimension, voltage, read_ele_num, l_z):
        self.name = device_name
        self.voltage = voltage # float
        self.dimension = dimension
        self.read_ele_num = int(read_ele_num) 
        self.l_z = l_z # used for planar weighting field TODO: auto weighting field

        PotentialFile = "./output/field/{}/Potential_{}V.pkl".format(self.name, self.voltage)
        TrappingRate_pFile = "./output/field/{}/TrappingRate_p_{}V.pkl".format(self.name, self.voltage)
        TrappingRate_nFile = "./output/field/{}/TrappingRate_n_{}V.pkl".format(self.name, self.voltage)

        self.set_potential(PotentialFile) #self.potential, self.x_efield, self.y_efield, self.z_efield
        self.set_trap_p(TrappingRate_pFile) # self.TrappingRate_p
        self.set_trap_n(TrappingRate_nFile) # self.TrappingRate_n
        self.set_w_p() #self.weighting_potential[]

    def set_potential(self, PotentialFile):
        try:
            with open(PotentialFile,'rb') as file:
                PotentialNotUniform=pickle.load(file)
                print("Potential file loaded for {}".format(self.name))
                if PotentialNotUniform['metadata']['dimension'] < self.dimension:
                    print("Potential dimension not match")
                    return
        except FileNotFoundError:
            print("Potential file not found, please run field simulation first")
            print("or manually set the potential file")
            return
        
        if PotentialNotUniform['metadata']['dimension'] == 1:
            PotentialUniform = get_common_interpolate_1d(PotentialNotUniform)
        elif PotentialNotUniform['metadata']['dimension'] == 2:
            PotentialUniform =get_common_interpolate_2d(PotentialNotUniform)
        elif PotentialNotUniform['metadata']['dimension'] == 3:
            PotentialUniform =get_common_interpolate_3d(PotentialNotUniform)

        self.Potential = PotentialUniform

    def set_w_p(self):
        self.WeightingPotentials = [] #length = ele_num
        if self.read_ele_num == 1:
            print("Linear weighting potential loaded")
            pass
        elif self.read_ele_num >= 2:  
            for i in range(self.read_ele_num):
                self.WeightingPotentials.append(strip_w_p(i))
                print("Weighting potential loaded for {}, strip {}".format(self.name, i+1))
        else:
            raise ValueError(self.read_ele_num)

    def set_trap_p(self, TrappingRate_pFile):
        try:
            with open(TrappingRate_pFile,'rb') as file:
                TrappingRate_pNotUniform=pickle.load(file)
                print("TrappingRate_p file loaded for {}".format(self.name))
                if TrappingRate_pNotUniform['metadata']['dimension'] < self.dimension:
                    print("TrappingRate_p dimension not match")
                    return
        except FileNotFoundError:
            print("TrappingRate_p file not found, please run field simulation first")
            print("or manually set the hole trapping rate file")
            return
        
        if TrappingRate_pNotUniform['metadata']['dimension'] == 1:
            TrappingRate_pUniform = get_common_interpolate_1d(TrappingRate_pNotUniform)
        elif TrappingRate_pNotUniform['metadata']['dimension'] == 2:
            TrappingRate_pUniform =get_common_interpolate_2d(TrappingRate_pNotUniform)
        elif TrappingRate_pNotUniform['metadata']['dimension'] == 3:
            TrappingRate_pUniform =get_common_interpolate_3d(TrappingRate_pNotUniform)

        self.TrappingRate_p = TrappingRate_pUniform
    
    def set_trap_n(self, TrappingRate_nFile):
        try:
            with open(TrappingRate_nFile,'rb') as file:
                TrappingRate_nNotUniform=pickle.load(file)
                print("TrappingRate_n file loaded for {}".format(self.name))
                if TrappingRate_nNotUniform['metadata']['dimension'] != self.dimension:
                    print("TrappingRate_n dimension not match")
                    return
        except FileNotFoundError:
            print("TrappingRate_n file not found, please run field simulation first")
            print("or manually set the electron trapping rate file")
            return
        
        if TrappingRate_nNotUniform['metadata']['dimension'] == 1:
            TrappingRate_nUniform = get_common_interpolate_1d(TrappingRate_nNotUniform)
        elif TrappingRate_nNotUniform['metadata']['dimension'] == 2:
            TrappingRate_nUniform =get_common_interpolate_2d(TrappingRate_nNotUniform)
        elif TrappingRate_nNotUniform['metadata']['dimension'] == 3:
            TrappingRate_nUniform =get_common_interpolate_3d(TrappingRate_nNotUniform)

        self.TrappingRate_n = TrappingRate_nUniform
        
    # DEVSIM dimension order: x, y, z
    # RASER dimension order: z, x, y
    
    def get_potential(self, x, y, z):
        '''
            input: position in um
            output: potential in V
        '''
        x, y, z = x/1e4, y/1e4, z/1e4 # um to cm
        if self.dimension == 1:
            return self.Potential(z)
        elif self.dimension == 2:
            return self.Potential(z, x)
        elif self.dimension == 3:
            return self.Potential(z, x, y)
    
    def get_e_field(self, x, y, z): 
        '''
            input: position in um
            output: intensity in V/um
        ''' 
        x, y, z = x/1e4, y/1e4, z/1e4 # um to cm  
        if self.dimension == 1:
            try:
                E_z = - ((self.Potential(z+diff_res/2) - self.Potential(z-diff_res/2))) / diff_res
            except ValueError:
                try:
                    E_z = - ((self.Potential(z+diff_res) - self.Potential(z))) / diff_res
                except ValueError:
                    try:
                        E_z = - ((self.Potential(z) - self.Potential(z-diff_res))) / diff_res
                    except ValueError:
                        raise ValueError("Point {} might be out of bound z".format(z))
            return (0, 0, E_z)
        
        elif self.dimension == 2:
            try:
                E_z = - ((self.Potential(z+diff_res/2, x) - self.Potential(z-diff_res/2, x))) / diff_res
            except ValueError:
                try:
                    E_z = - ((self.Potential(z+diff_res, x) - self.Potential(z, x))) / diff_res
                except ValueError:
                    try:
                        E_z = - ((self.Potential(z, x) - self.Potential(z-diff_res, x))) / diff_res
                    except ValueError:
                        raise ValueError("Point {} might be out of bound z".format(z))
            try:
                E_x = - ((self.Potential(z, x+diff_res/2) - self.Potential(z, x-diff_res/2))) / diff_res
            except ValueError:
                try:
                    E_x = - ((self.Potential(z, x+diff_res) - self.Potential(z, x))) / diff_res
                except ValueError:
                    try:
                        E_x = - ((self.Potential(z, x) - self.Potential(z, x-diff_res))) / diff_res
                    except ValueError:
                        raise ValueError("Point {} might be out of bound x".format(x))
            return (E_x, 0, E_z)
        
        elif self.dimension == 3:
            try:
                E_z = - ((self.Potential(z+diff_res/2, x, y) - self.Potential(z-diff_res/2, x, y))) / diff_res
            except ValueError:
                try:
                    E_z = - ((self.Potential(z+diff_res, x, y) - self.Potential(z, x, y))) / diff_res
                except ValueError:
                    try:
                        E_z = - ((self.Potential(z, x, y) - self.Potential(z-diff_res, x, y))) / diff_res
                    except ValueError:
                        raise ValueError("Point {} might be out of bound z".format(z))
            try:
                E_x = - ((self.Potential(z, x+diff_res/2, y) - self.Potential(z, x-diff_res/2, y))) / diff_res
            except ValueError:
                try:
                    E_x = - ((self.Potential(z, x+diff_res, y) - self.Potential(z, x, y))) / diff_res
                except ValueError:
                    try:
                        E_x = - ((self.Potential(z, x, y) - self.Potential(z, x-diff_res, y))) / diff_res
                    except ValueError:
                        raise ValueError("Point {} might be out of bound x".format(x))
            try:
                E_y = - ((self.Potential(z, x, y+diff_res/2) - self.Potential(z, x, y-diff_res/2))) / diff_res
            except ValueError:
                try:
                    E_y = - ((self.Potential(z, x, y+diff_res) - self.Potential(z, x, y))) / diff_res
                except ValueError:
                    try:
                        E_y = - ((self.Potential(z, x, y) - self.Potential(z, x, y-diff_res))) / diff_res
                    except ValueError:
                        raise ValueError("Point {} might be out of bound y".format(y))
            return (E_x, E_y, E_z)

    def get_w_p(self, x, y, z, i):
        '''
            input: position in um
            output: weighting potential in 1
        '''
        if self.read_ele_num == 1:
            return linear_w_p(z, self.l_z)
        elif self.read_ele_num > 1:
            return self.WeightingPotentials[i].Interpolate(z, x)
    
    def get_trap_e(self, x, y, z):
        '''
            input: position in um
            output: electron trapping rate in s^-1     
        '''
        x, y, z = x/1e4, y/1e4, z/1e4 # um to cm
        if self.dimension == 1:
            return self.TrappingRate_n(z)
        elif self.dimension == 2:
            return self.TrappingRate_n(z, x)
        elif self.dimension == 3:
            return self.TrappingRate_n(z, x, y)
    
    def get_trap_h(self, x, y, z):
        '''
            input: position in um
            output: hole trapping rate in s^-1     
        '''
        x, y, z = x/1e4, y/1e4, z/1e4 # um to cm
        if self.dimension == 1:
            return self.TrappingRate_p(z)
        elif self.dimension == 2:
            return self.TrappingRate_p(z, x)
        elif self.dimension == 3:
            return self.TrappingRate_p(z, x, y)

def get_common_interpolate_1d(data):
    values = data['values']
    points = data['points']
    f = p1d(points, values)
    return f

def get_common_interpolate_2d(data):
    values = data['values']
    points_x = []
    points_y = []
    for point in data['points']:
        points_x.append(point[0])
        points_y.append(point[1])
    new_x = np.linspace(min(points_x), max(points_x), x_bin)
    new_y = np.linspace(min(points_y), max(points_y), y_bin)
    new_points = np.array(np.meshgrid(new_x, new_y)).T.reshape(-1, 2)
    new_values = griddata((points_x, points_y), values, new_points, method='linear')
    f = p2d(new_x, new_y, new_values)
    return f

def get_common_interpolate_3d(data):
    values = data['values']
    points_x = []
    points_y = []
    points_z = []
    for point in data['points']:
        points_x.append(point[0])
        points_y.append(point[1])
        points_z.append(point[2])
    new_x = np.linspace(min(points_x), max(points_x), x_bin)
    new_y = np.linspace(min(points_y), max(points_y), y_bin)
    new_z = np.linspace(min(points_z), max(points_z), z_bin)
    new_points = np.array(np.meshgrid(new_x, new_y, new_z)).T.reshape(-1, 3)
    new_values = griddata((points_x, points_y, points_z), values, new_points, method='linear')
    lndi = LNDI(new_points, new_values)
    def f(x, y, z):
        point = [x, y, z]
        return lndi(point)
    return f

def linear_w_p(z, l_z):
    if z >= l_z:
        w_potential = 0
    elif z >= 1:
        w_potential = 1 - (1/(l_z-1)) * (z-1)
    else:
        w_potential = 1
    return w_potential

def strip_w_p(ele_number):
    nx = 51  
    ny = 321  
    xmin, xmax = 0.0, 50.0  
    ymin, ymax = 0.0, 320.0 
    dx = (xmax - xmin) / (nx - 1)  
    dy = (ymax - ymin) / (ny - 1) 

    u = np.zeros((ny, nx))
    u[ele_number*75:(ele_number*75+20), 0] = 1.0  
    u[:, -1] = 0.0  

    max_iter = 100000  
    tolerance = 1e-6  
    for iteration in range(max_iter):
        u_old = u.copy()
        for i in range(1, ny - 1):
            for j in range(1, nx - 1):
                u[i, j] = (u[i+1, j] + u[i-1, j] + u[i, j+1] + u[i, j-1]) / 4
        diff = np.abs(u - u_old).max()
        if diff < tolerance:
            break

    x = np.linspace(xmin, xmax, nx)
    y = np.linspace(ymin, ymax, ny)
    w_potential=ROOT.TGraph2D()
    for i in range(len(y)):
        for j in range(len(x)):
            w_potential.SetPoint(int(i*len(x)+j),x[j]*6,y[i],u[i][j])
    return w_potential

if __name__ == "__main__":
    testField = DevsimField("ITk-Si-strip", 2, -500.0, 4)
    print(testField.get_e_field(100,100,50))