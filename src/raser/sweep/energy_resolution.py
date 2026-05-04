#Xray_energy_resolution
#!/usr/bin/env python3
# -*- encoding: utf-8 -*-


import sys
import os
from array import array
import time
import subprocess
import json
import random
from scipy.stats import norm
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

import ROOT
ROOT.gROOT.SetBatch(True)
from ..device import build_device as bdv
from ..util.output import output

def read_events(event_folder_path, electrode_index=0):
    #read file
    nbins = None
    events_number = 0
    for file in os.listdir(event_folder_path):
        file_path = os.path.join(event_folder_path,file)
        f = ROOT.TFile(file_path)
        tree = f.Get("tree")
        events_number += tree.GetEntries()
        if nbins is None:
            tree.GetEntry(0)
            hist = getattr(tree, f"amplified_waveform_{electrode_index}")
            nbins = hist.GetNbinsX()
        f.Close()

    waveforms = np.zeros((events_number, nbins))
    event_number = 0

    for file in os.listdir(event_folder_path):
        file_path = os.path.join(event_folder_path,file)
        f = ROOT.TFile(file_path)
        tree = f.Get("tree")
        branches = tree.GetListOfBranches()
        branch_name = f"amplified_waveform_{electrode_index}"
        print(file_path)
        for event in range(tree.GetEntries()):
            tree.GetEntry(event)
            hist = getattr(tree, branch_name)
            n_bins = hist.GetNbinsX()
            waveform = np.zeros(n_bins)
            array = hist.GetArray()
            #print(array)
            for j in range(n_bins):
                waveform[j] = hist.GetBinContent(j + 1)
            waveforms[event_number,:] = waveform
            event_number += 1
            
 
        f.Close()
    print(waveforms)

    return waveforms



def Energy_resolution(waveforms, my_d):
    peaks = []
    for i in range(waveforms.shape[0]):
        peak_i = max(abs(waveforms[i,:]))
        peaks.append(peak_i)
        peaks.sort()
    print(peaks)
    # peaks_len = len(peaks)
    # extreme_num = int(peaks_len * 0.05)
    # peaks = peaks[extreme_num:peaks_len-extreme_num]
    sep=50
    mu, sigma = norm.fit(peaks)
    fwhm= 2 * np.sqrt(2 * np.log(2)) * sigma
    if hasattr(my_d, 'sweep') ==False or my_d.sweep == None:
        print("draw fit curve for single energy test...")
        now = time.strftime("%Y_%m%d_%H%M%S")
        path = output(__file__, my_d.det_name, now)
        #画拟合图，暂时未写入命令行参数，后续再完善
        draw_fit_curve(peaks,mu,sigma,path,sep,my_d.det_name)
    energy_resolution = fwhm / mu
    print(f"Energy resolution: {energy_resolution:.2%}")
    return energy_resolution
#possion
#def Energy_resolution(waveforms, my_d):
    peaks = []
    for i in range(waveforms.shape[0]):
        peak_i = max(abs(waveforms[i,:]))
        peaks.append(peak_i)
    peaks = np.array(peaks)
    # 泊松分布的 λ 估计 = 样本均值
    lam = np.mean(peaks)
    # 能量分辨率 = FWHM / 均值 = 2.355 * sqrt(λ) / λ
    energy_resolution = 2.355 / np.sqrt(lam)
    
    # 绘图（需要传入 lam）
    if not (hasattr(my_d, 'sweep') and my_d.sweep):
        now = time.strftime("%Y_%m%d_%H%M%S")
        path = output(__file__, my_d.det_name, now)
        draw_fit_curve(peaks, lam=lam, path=path, bins=50, det_model=my_d.det_name)
    
    print(f"Energy resolution: {energy_resolution:.2%}")
    return energy_resolution

#possion
#def draw_fit_curve(peaks, lam, path, bins, det_model):
    """
    绘制泊松分布拟合图
    peaks  : 原始数据（应为非负整数计数）
    lam    : 泊松分布的参数 λ（均值）
    path   : 保存路径
    bins   : 直方图的分箱边界
    det_model : 模型名称，用于文件名
    """
    fig, ax1 = plt.subplots(figsize=(8, 5))

    # 左轴：频数直方图（建议 density=True 使与 PMF 量纲一致）
    ax1.hist(peaks, bins=bins, density=True, alpha=0.6, color='steelblue',
             edgecolor='black', linewidth=0.5, label='peaks')
    ax1.set_xlabel('current (count)')
    ax1.set_ylabel('Probability density / mass', color='steelblue')
    ax1.tick_params(axis='y', labelcolor='steelblue')
    ax1.grid(alpha=0.3)

    # 右轴：泊松分布的概率质量函数（PMF）
    ax2 = ax1.twinx()
    # 确定 x 的范围（整数）
    x_min, x_max = int(np.min(peaks)), int(np.max(peaks))
    x_ints = np.arange(x_min, x_max + 1)
    pmf = stats.poisson.pmf(x_ints, lam)
    
    # 绘制离散 PMF：用红色圆点 + 竖线（更符合离散分布表达）
    ax2.vlines(x_ints, 0, pmf, colors='red', lw=2, alpha=0.7, label=f'Poisson PMF (λ={lam:.2f})')
    ax2.plot(x_ints, pmf, 'ro', markersize=5, alpha=0.7)
    ax2.set_ylabel('Poisson probability mass', color='red')
    ax2.tick_params(axis='y', labelcolor='red')
    ax2.set_ylim(bottom=0)

    # 合并图例
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='best')

    ax1.set_title(f'Poisson fit for {det_model}')
    fig.savefig(os.path.join(path, f"{det_model}_poisson_fit.pdf"))
    print(f"Poisson fit curve saved to {os.path.join(path, f'{det_model}_poisson_fit.pdf')}")
    plt.close(fig)
    
# Draw Gaussian distribution fit curve
def draw_fit_curve(peaks, mu, sigma, path, bins, det_model):
    fig, ax1 = plt.subplots(figsize=(8, 5))

    # 左轴：频数直方图
    ax1.hist(peaks, bins=bins, density=False, alpha=0.6, color='steelblue',
             edgecolor='black', linewidth=0.5, label='peaks')
    ax1.set_xlabel('current')
    ax1.set_ylabel('Frequency', color='steelblue')
    ax1.tick_params(axis='y', labelcolor='steelblue')
    ax1.grid(alpha=0.3)

    # 右轴：概率密度曲线
    ax2 = ax1.twinx()
    x = np.linspace(min(peaks), max(peaks), 200)
    pdf = stats.norm.pdf(x, mu, sigma)
    ax2.plot(x, pdf, 'r-', lw=2.5, label=f'fit_curve $N({mu:.2f}, {sigma:.2f}^2)$')
    ax2.set_ylabel('Probability density', color='red')
    ax2.tick_params(axis='y', labelcolor='red')

    # 合并图例
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='best')

    ax1.set_title('fit curve')
    fig.savefig(os.path.join(path, f"{det_model}_fit_curve.pdf"))
    print(f"Fit curve saved to {os.path.join(path, f'{det_model}_fit_curve.pdf')}")
    plt.close(fig)

def main(kwargs):
    #设置部分
    det_name = kwargs['det_name']
    my_d = bdv.Detector(det_name)
    
    my_d = bdv.Detector(det_name)
    if kwargs['voltage'] != None:
        my_d.voltage = kwargs['voltage']

    if kwargs['irradiation'] != None:
        my_d.irradiation_flux = float(kwargs['irradiation'])

    if kwargs['g4experiment'] != None:
        my_d.g4experiment = kwargs['g4experiment']

    if kwargs['amplifier'] != None:
        my_d.amplifier = kwargs['amplifier']

    if 'subfolder_path' in kwargs:
        if kwargs['subfolder_path'] != None:
            my_d.subfolder_path = kwargs['subfolder_path']

    if 'sweep' in kwargs:
        if kwargs['sweep'] != None:
            my_d.sweep = kwargs['sweep']


    
    #events_path = "/afs/ihep.ac.cn/users/s/shaochangpu/raser/output/sweep/NJU-PiN/par_energy_2026-04-04-17-03-21/par_energy_5"
    event_folder_path = "/afs/ihep.ac.cn/users/w/wangpeiyao/raser/output/signal/MIM-Diamond/rms=2new2000"
    if hasattr(my_d, 'subfolder_path') and my_d.subfolder_path != None:
        event_folder_path = my_d.subfolder_path
    print(event_folder_path)
    if not os.path.exists(event_folder_path):
        print(f"Error: {event_folder_path} does not exist.")
        return
    if hasattr(my_d, 'sweep') and my_d.sweep != None:
        print("sweep mode, skip energy resolution calculation.")
        amplified_waveforms = read_events(event_folder_path)
        energy_resolution = Energy_resolution(amplified_waveforms, my_d)
        return energy_resolution

    else:
        print("single energy test mode, calculate energy resolution...")
            #单能量测试 
        amplified_waveforms = read_events(event_folder_path)
        energy_resolution = Energy_resolution(amplified_waveforms, my_d)

