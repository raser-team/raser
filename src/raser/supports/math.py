#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

"""
Description:
    Math Objects
@Date       : 2024/09/19 20:57:33
@Author     : Chenxi Fu
@version    : 1.0
"""

import math
from typing import Callable

import numpy as np
from scipy.interpolate import interp1d as p1d
from scipy.interpolate import interp2d as p2d
from scipy.interpolate import interpn as pn
from scipy.interpolate import griddata, RegularGridInterpolator
import ROOT
ROOT.gROOT.SetBatch(True)

x_bin_2d = 200
y_bin_2d = 200

x_bin_3d = 50
y_bin_3d = 50
z_bin_3d = 50

class Vector:
    def __init__(self,a1,a2,a3):
        self.components = [a1,a2,a3]
        
    def cross(self,Vector_b):
        """Get vector cross product of self and another Vector"""
        o1 = ( self.components[1]*Vector_b.components[2]-self.components[2]*Vector_b.components[1]
        )
        o2 = ( self.components[2]*Vector_b.components[0]-self.components[0]*Vector_b.components[2]
        )
        o3 = ( self.components[0]*Vector_b.components[1]-self.components[1]*Vector_b.components[0]
        )
        return Vector(o1,o2,o3)

    def get_length(self):
        "Return length of self"
        return math.sqrt(self.components[0]*self.components[0]+self.components[1]*self.components[1]+self.components[2]*self.components[2])

    def add(self,Vector_b):
        "Return the sum of two Vectors. eg: [1,2,3]+[1,2,3] = [2,4,6]"
        o1 = self.components[0]+Vector_b.components[0]
        o2 = self.components[1]+Vector_b.components[1]
        o3 = self.components[2]+Vector_b.components[2]
        return Vector(o1,o2,o3)

    def sub(self,Vector_b):
        "Return the subtraction of two Vectors. eg: [1,2,3]-[1,2,3] = [0,0,0]"
        o1 = self.components[0]-Vector_b.components[0]
        o2 = self.components[1]-Vector_b.components[1]
        o3 = self.components[2]-Vector_b.components[2]
        return Vector(o1,o2,o3)
    
    def mul(self,k):
        "Return Vector multiplied by number. eg: 2 * [1,2,3] = [2,4,6]"
        return Vector(self.components[0]*k,self.components[1]*k,self.components[2]*k)


def get_common_interpolate_1d(data):
    values = data['values']
    points = data['points']
    interpolator = p1d(points, values)

    def f(x):
        return interpolator(x)
    return f

def get_common_interpolate_2d(data):
    values = data['values']
    points_x = []
    points_y = []
    for point in data['points']:
        points_x.append(point[0])
        points_y.append(point[1])
    new_x = np.linspace(min(points_x), max(points_x), x_bin_2d)
    new_y = np.linspace(min(points_y), max(points_y), y_bin_2d)
    new_points = np.array(np.meshgrid(new_x, new_y)).T.reshape(-1, 2)
    new_values = griddata((points_x, points_y), values, new_points, method='linear')
    interpolator = p2d(new_x, new_y, new_values)

    def f(x, y):
        return interpolator(x, y)[0]
    return f


def get_common_interpolate_3d(data):
    values = np.asarray(data['values'])
    points = np.asarray(data['points'])  # shape: (N, 3)
    points_x = points[:, 0]
    points_y = points[:, 1]
    points_z = points[:, 2]
    x_min, x_max = points_x.min(), points_x.max()
    y_min, y_max = points_y.min(), points_y.max()
    z_min, z_max = points_z.min(), points_z.max()
    new_x = np.linspace(x_min, x_max, x_bin_3d, endpoint=True)
    new_y = np.linspace(y_min, y_max, y_bin_3d, endpoint=True)
    new_z = np.linspace(z_min, z_max, z_bin_3d, endpoint=True)
    grid_x, grid_y, grid_z = np.meshgrid(new_x, new_y, new_z, indexing='xy')
    new_values = griddata(
        (points_x, points_y, points_z), values, (grid_x, grid_y, grid_z),
        method='linear', fill_value=0.0,
    )
    interpolator = RegularGridInterpolator(
        (new_x, new_y, new_z), new_values.transpose(1, 0, 2),
        method='linear', bounds_error=False, fill_value=0.0,
    )
    
    def f(x, y, z):
        x_c = np.clip(x, x_min, x_max)
        y_c = np.clip(y, y_min, y_max)
        z_c = np.clip(z, z_min, z_max)
        return interpolator([[x_c, y_c, z_c]])[0]
    return f

def signal_convolution(signal_original: ROOT.TH1F, signal_convolved: ROOT.TH1F, pulse_responce_function_list: list[Callable[[float],float]],):
    so = signal_original
    sc = signal_convolved
    n_bin = so.GetNbinsX()
    if sc.GetNbinsX() != n_bin:
        raise ValueError("signal_convolved must have the same number of bins")
    if so.GetXaxis().GetXmin() != sc.GetXaxis().GetXmin() or so.GetXaxis().GetXmax() != sc.GetXaxis().GetXmax():
        raise ValueError("signal_convolved must have the same time range")

    t_bin = so.GetBinWidth(1)
    if t_bin <= 0:
        raise ValueError(f"Histogram bin width must be positive, got {t_bin}")

    axis = so.GetXaxis()
    centers = np.array(
        [axis.GetBinCenter(bin_idx) for bin_idx in range(1, n_bin + 1)],
        dtype=np.float64,
    )
    source = np.array(
        [so.GetBinContent(bin_idx) for bin_idx in range(1, n_bin + 1)],
        dtype=np.float64,
    )
    for pr in pulse_responce_function_list:
        target = np.zeros(n_bin, dtype=np.float64)
        for source_bin, source_value in enumerate(source):
            if source_value == 0.0:
                continue
            response = np.array(
                [pr(time - centers[source_bin]) for time in centers],
                dtype=np.float64,
            )
            target += source_value * response * t_bin
        source = target

    sc.Reset()
    for bin_idx, value in enumerate(source, start=1):
        sc.SetBinContent(bin_idx, float(value))


def calculate_gradient(function: Callable, component: list, coordinate: list):
    diff_res = 1e-5 # difference resolution in cm
    diff_steps = [(diff_res / 2, diff_res / 2), (diff_res, 0), (0, diff_res)]

    gradient = []
    for i in range(len(coordinate)):
        for diff1, diff2 in diff_steps:
            try:
                args_plus = [c + diff1 if i == j else c for j, c in enumerate(coordinate)]
                args_minus = [c - diff2 if i == j else c for j, c in enumerate(coordinate)] 
                gradient_trial = (function(*args_plus) - function(*args_minus)) / diff_res
                gradient.append(gradient_trial)
                break
            except ValueError as e:
                if "out of bound" in str(e) or "interpolation range" in str(e):
                    continue
                else:
                    raise e
        else:
            raise ValueError(f"Point {coordinate} might be out of bound")
    
    return gradient

def inversed_fast_fourier_transform():
    pass

def is_number(s):
    """
    Define the input s is number or not.
    if Yes, return True, else return False.
    """ 
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        pass
    try:
        import unicodedata
        unicodedata.numeric(s)
        return True
    except (TypeError, ValueError):
        pass
    return False

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
    mean=fit_func_1.GetParameter(1)
    mean_error=fit_func_1.GetParError(1)
    sigma=fit_func_1.GetParameter(2)
    sigma_error=fit_func_1.GetParError(2)
    fit_func_1.SetLineWidth(2)
    return fit_func_1,mean,mean_error,sigma,sigma_error

def fit_data_landau(histo,x_min,x_max):
    """Fit data distribution"""
    fit_func_1 = ROOT.TF1('fit_func_1','landau',x_min,x_max)
    histo.Fit("fit_func_1","ROQ+","",x_min,x_max)

    print("constant:%s"%fit_func_1.GetParameter(0))
    print("constant_error:%s"%fit_func_1.GetParError(0))
    print("mpv:%s"%fit_func_1.GetParameter(1))
    print("mpv_error:%s"%fit_func_1.GetParError(1))
    print("sigma:%s"%fit_func_1.GetParameter(2))
    print("sigma_error:%s"%fit_func_1.GetParError(2))
    mean=fit_func_1.GetParameter(1)
    mean_error=fit_func_1.GetParError(1)
    sigma=fit_func_1.GetParameter(2)
    sigma_error=fit_func_1.GetParError(2)
    fit_func_1.SetLineWidth(2)
    return fit_func_1,mean,mean_error,sigma,sigma_error
