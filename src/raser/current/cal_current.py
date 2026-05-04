# -*- encoding: utf-8 -*-

'''
Description:  
    Simulate e-h pairs drifting and calculate induced current
@Date       : 2025/11/11
@Author     : Yuhang Tan, Chenxi Fu, Dai Zhong
@version    : 3.0
'''

import random
import math
import os
from array import array
import csv
import time
import logging
import numpy as np
import ROOT
ROOT.gROOT.SetBatch(True)

from .model import Material
from .carrier import VectorizedCarrierSystem

from ..interaction.carrier_list import CarrierListFromG4P
from ..util.math import Vector, signal_convolution
from ..util.output import output

t_bin = {
    1: 5e-12,
    2: 50e-12,
    3: 50e-12  # resolution of oscilloscope
}

t_start = 0

t_end = {
    1: 5e-9,
    2: 1e-6,
    3: 1e-6
}

delta_t = {
    1: 2e-12,  # simulation time step
    2: 50e-12,
    3: 50e-12
}

t_tol = 1e-20


logger = logging.getLogger(__name__)
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger.setLevel(logging.INFO)

class CalCurrent:
    """
    Description:
        Calculate sum of the generated current by carriers drifting
    Parameters:
        my_d : Detector
        my_f : FieldCache
        ionized_pairs : float[]
            the generated carrier amount from MIP or laser
        track_position : float[]
            position of the generated carriers
    Attributes:
        electrons, holes : VectorizedCarrierSystem[]
            the generated carriers, able to calculate their movement
    Modify:
        2024/11/09
    """
    def __init__(self, my_d, my_f, ionized_pairs, track_position):
        start_time = time.time()
        logger.info("current calculation start...")
        self.t_bin = t_bin[my_d.dimension]
        self.t_end = t_end[my_d.dimension]
        self.t_start = t_start
        self.delta_t = delta_t[my_d.dimension]
        self.n_bin = int((self.t_end+t_tol-self.t_start)/self.t_bin)
        if my_d.is_plugin():
            self.t_bin = t_bin[1]
            self.t_end = t_end[1]
            self.t_start = t_start
            self.delta_t = delta_t[1]

        self.read_ele_num = my_d.read_ele_num
        if hasattr(my_d, "x_ele_num") and hasattr(my_d, "y_ele_num"):
            self.x_ele_num = my_d.x_ele_num
            self.y_ele_num = my_d.y_ele_num
        self.read_out_contact = my_d.read_out_contact
        
        self.electron_system = None
        self.hole_system = None
        
        self.smoothing_window = max(0, int(getattr(my_d, "current_smoothing_window", 0)))
        self.savgol_window = max(0, int(getattr(my_d, "current_savgol_window", 0)))
        self.savgol_poly = max(0, int(getattr(my_d, "current_savgol_poly", 0)))
        if self.savgol_window and self.savgol_window % 2 == 0:
            self.savgol_window += 1  # Savitzky-Golay 需要奇数窗口
        if self.savgol_window and self.savgol_poly >= self.savgol_window:
            self.savgol_poly = max(0, self.savgol_window - 1)
        self._savgol_kernel = None

        # 准备载流子数据
        electron_positions = []
        electron_charges = []
        electron_times = []
        electron_signals = []
        
        hole_positions = []
        hole_charges = []
        hole_times = []
        hole_signals = []

        for i in range(len(track_position)):
            x, y, z, t = track_position[i]
            t_num = int(t / self.delta_t + t_tol)
            charge = ionized_pairs[i]
            
            # 过滤在探测器边界外的载流子
            if self._is_in_sensor(x, y, z, my_d) and self._is_in_field_range(x, y, my_d, my_d.x_ele_num, my_d.y_ele_num):
                # 电子
                electron_positions.append([x, y, z])
                electron_charges.append(-charge)  # 电子带负电
                electron_times.append(t_num)
                electron_signals.append([])  # 空信号列表
                
                # 空穴
                hole_positions.append([x, y, z])
                hole_charges.append(charge)  # 空穴带正电
                hole_times.append(t_num)
                hole_signals.append([])

        logger.info(f"载流子过滤完成: {len(electron_positions)}个电子, {len(hole_positions)}个空穴")

        # 创建向量化系统
        if electron_positions:
            self.electron_system = VectorizedCarrierSystem(
                electron_positions, electron_charges, electron_times, electron_signals,
                my_d.material, "electron", self.read_out_contact, my_d
            )
        
        if hole_positions:
            self.hole_system = VectorizedCarrierSystem(
                hole_positions, hole_charges, hole_times, hole_signals,
                my_d.material, "hole", self.read_out_contact, my_d
            )

        init_time = time.time() - start_time
        logger.info(f"向量化系统初始化完成, 耗时: {init_time:.2f}s")
        
        # 执行漂移和信号计算
        self.drifting_loop(my_d, my_f)

        # 初始化电流直方图
        self.current_define(self.read_ele_num)
        for i in range(self.read_ele_num):
            self.sum_cu[i].Reset()
            self.positive_cu[i].Reset()
            self.negative_cu[i].Reset()
        
        # 计算电流
        self.get_current(my_d.x_ele_num, my_d.y_ele_num, self.read_out_contact)
        
        # 合并电流
        for i in range(self.read_ele_num):
            self.sum_cu[i].Add(self.positive_cu[i])
            self.sum_cu[i].Add(self.negative_cu[i])
        
        if self.smoothing_window > 1:
            self._apply_smoothing()

        self.det_model = my_d.det_model
        if "lgad" in self.det_model:
            self.gain_current = CalCurrentGain(my_d, my_f, self)
            for i in range(self.read_ele_num):
                self.sum_cu[i].Add(self.gain_current.negative_cu[i])
                self.sum_cu[i].Add(self.gain_current.positive_cu[i])

    def _is_in_sensor(self, x, y, z, my_d):
        """检查位置是否在探测器内"""
        return (0 <= x <= my_d.l_x and 
                0 <= y <= my_d.l_y and 
                0 <= z <= my_d.l_z)

    def _is_in_field_range(self, x, y, my_d, n_x, n_y):
        """检查位置是否在电场范围内"""
        # 计算电极编号
        try:
            x_num = int((x - my_d.l_x/2) // getattr(my_d, 'p_x', my_d.l_x) + n_x/2.0)
            y_num = int((y - my_d.l_y/2) // getattr(my_d, 'p_y', my_d.l_y) + n_y/2.0)
            return (0 <= x_num < n_x and 0 <= y_num < n_y)
        except:
            return True  # 如果计算失败，默认在范围内

    def drifting_loop(self, my_d, my_f):
        """漂移循环 - 使用向量化系统"""
        logger.info(f"向量化漂移: 电子系统={self.electron_system is not None}, 空穴系统={self.hole_system is not None}")
        start_time = time.time()
        delta_t_sim = getattr(my_d, "vector_delta_t", self.delta_t)
        
        try:            
            # 批量处理电子
            if self.electron_system:
                logger.info(f"电子数量: {len(self.electron_system.positions)}")
                self.electron_system.drift_batch(my_d, my_f, delta_t=delta_t_sim)
                logger.info("电子漂移结束，开始信号计算...")
                self.electron_system.get_signal_batch(my_d, my_f)
            
            # 批量处理空穴
            if self.hole_system:
                logger.info(f"空穴数量: {len(self.hole_system.positions)}")
                self.hole_system.drift_batch(my_d, my_f, delta_t=delta_t_sim)
                logger.info("空穴漂移结束，开始信号计算...")
                self.hole_system.get_signal_batch(my_d, my_f)
                            
            cache_stats = my_f.get_cache_stats()
            logger.info(
                "电场缓存统计: 命中=%d, 未命中=%d, 错误=%d, 备用=%d, 命中率=%.2f%%",
                cache_stats['hits'], cache_stats['misses'], cache_stats['errors'],
                cache_stats['fallbacks'], cache_stats['hit_rate'] * 100.0
            )
                            
        except Exception as e:
            logger.exception("漂移循环错误: %s", e)
            raise
    
        end_time = time.time()
        logger.info(f"漂移和信号计算完成, 耗时: {end_time - start_time:.2f}s")

    def current_define(self, read_ele_num):
        """定义电流直方图"""
        self.positive_cu = []
        self.negative_cu = []
        self.sum_cu = []

        for i in range(read_ele_num):
            self.positive_cu.append(ROOT.TH1F("charge+"+str(i+1), " No."+str(i+1)+"Positive Current",
                                        self.n_bin, self.t_start, self.t_end))
            self.negative_cu.append(ROOT.TH1F("charge-"+str(i+1), " No."+str(i+1)+"Negative Current",
                                        self.n_bin, self.t_start, self.t_end))
            self.sum_cu.append(ROOT.TH1F("charge"+str(i+1),"Total Current"+" No."+str(i+1)+"electrode",
                                    self.n_bin, self.t_start, self.t_end))
            
    def get_current(self, n_x, n_y, read_out_contact):
        """从向量化系统获取电流"""
        logger.info("开始计算电流...")
        
        # 重置电流直方图
        for i in range(self.read_ele_num):
            self.positive_cu[i].Reset()
            self.negative_cu[i].Reset()
        
        hole_signals_found = 0
        electron_signals_found = 0
        
        # 单电极配置
        if len(read_out_contact) == 1:
            x_span = read_out_contact[0]['x_span']
            y_span = read_out_contact[0]['y_span']
            total_electrodes = (2 * x_span + 1) * (2 * y_span + 1)
            
            logger.info(f"电流计算: 单电极配置, x_span={x_span}, y_span={y_span}, 总电极数={total_electrodes}")
            
            # 处理空穴电流
            if self.hole_system:
                hole_signals_found = self._process_system_current(
                    self.hole_system, n_x, n_y, 
                    x_span, y_span, total_electrodes, "hole"
                )
            
            # 处理电子电流
            if self.electron_system:
                electron_signals_found = self._process_system_current(
                    self.electron_system, n_x, n_y,
                    x_span, y_span, total_electrodes, "electron"
                )
        
        logger.info(f"电流计算完成: 空穴{hole_signals_found}点, 电子{electron_signals_found}点")
        
        # 验证电流结果
        for i in range(self.read_ele_num):
            hole_integral = self.positive_cu[i].Integral() * self.t_bin
            electron_integral = self.negative_cu[i].Integral() * self.t_bin
            logger.info(f"电极{i}: 空穴电荷={hole_integral:.2e}C, 电子电荷={electron_integral:.2e}C")

    def _process_system_current(self, carrier_system, n_x, n_y, 
                              x_span, y_span, total_electrodes, carrier_type):
        """处理单个载流子系统的电流计算"""
        signals_found = 0
        
        for carrier_idx in range(len(carrier_system.positions)):
            # 检查这个载流子是否有信号
            if (carrier_idx >= len(carrier_system.signals) or 
                not carrier_system.signals[carrier_idx]):
                continue
            
            carrier_signals = carrier_system.signals[carrier_idx]
            path_reduced = carrier_system.paths_reduced[carrier_idx]
            
            # 处理每个电极
            for electrode_idx in range(total_electrodes):
                if electrode_idx >= len(carrier_signals):
                    continue
                
                electrode_signals = carrier_signals[electrode_idx]
                if not electrode_signals:
                    continue
                
                # 计算电极的j,k坐标
                j = electrode_idx // (2 * y_span + 1)
                k = electrode_idx % (2 * y_span + 1)
                
                # 处理每个路径段的信号
                for step_idx in range(len(path_reduced)-1):                    
                    signal_value = electrode_signals[step_idx]

                    # 获取路径点的电极编号
                    x_num = path_reduced[step_idx][4] + (j - x_span)
                    y_num = path_reduced[step_idx][5] + (k - y_span)
                    
                    # 检查电极编号是否有效
                    if 0 <= x_num < n_x and 0 <= y_num < n_y:
                        target_electrode = x_num * n_y + y_num
                        if target_electrode < self.read_ele_num:
                            time_point = path_reduced[step_idx][3]
                            current_value = signal_value / self.t_bin
                                    # 根据载流子类型选择正确的电流直方图
                            if carrier_type == "hole":
                                self.positive_cu[target_electrode].Fill(time_point*self.delta_t+t_tol, current_value)
                            elif carrier_type == "electron":
                                self.negative_cu[target_electrode].Fill(time_point*self.delta_t+t_tol, current_value)
                            else:
                                logger.warning(f"未知的载流子类型: {carrier_type}")
                                return signals_found
                            signals_found += 1
                            
                            # 调试前几个信号
                            if signals_found <= 3:
                                logger.info(f"{carrier_type}信号: t={time_point*self.delta_t+t_tol:.2e}s, I={current_value:.2e}A, 电极={target_electrode}")
        
        return signals_found
    
    def _apply_smoothing(self):
        """对电流直方图进行多阶段平滑，减少高频噪声"""
        def _moving_average(hist, kernel, window):
            nbins = hist.GetNbinsX()
            if nbins == 0 or nbins < window:
                return
            data = np.array([hist.GetBinContent(i) for i in range(1, nbins + 1)], dtype=np.float64)
            pad_left = window // 2
            pad_right = window - 1 - pad_left
            padded = np.pad(data, (pad_left, pad_right), mode='edge')
            smoothed = np.convolve(padded, kernel, mode='valid')
            for idx, value in enumerate(smoothed, start=1):
                hist.SetBinContent(idx, float(value))

        def _savgol(hist):
            nbins = hist.GetNbinsX()
            window = self.savgol_window
            if nbins == 0 or window <= 1 or nbins < window:
                return
            data = np.array([hist.GetBinContent(i) for i in range(1, nbins + 1)], dtype=np.float64)
            kernel = self._get_savgol_kernel()
            pad = window // 2
            padded = np.pad(data, (pad, pad), mode='edge')
            smoothed = np.convolve(padded, kernel, mode='valid')
            for idx, value in enumerate(smoothed, start=1):
                hist.SetBinContent(idx, float(value))

        targets = [self.positive_cu, self.negative_cu, self.sum_cu]
        if hasattr(self, "cross_talk_cu"):
            targets.append(getattr(self, "cross_talk_cu"))
        if hasattr(self, "gain_current"):
            targets.append(getattr(self.gain_current, "positive_cu", []))
            targets.append(getattr(self.gain_current, "negative_cu", []))

        if self.smoothing_window > 1:
            ma_window = self.smoothing_window
            if ma_window % 2 == 0:
                ma_window += 1
            kernel = np.ones(ma_window, dtype=np.float64) / float(ma_window)
            logger.info("应用滑动窗口平滑 (窗口=%d)", ma_window)
            for hist_list in targets:
                for hist in hist_list:
                    _moving_average(hist, kernel, ma_window)

        if self.savgol_window > 1:
            logger.info(
                "应用 Savitzky-Golay 平滑 (窗口=%d, 多项式阶=%d)",
                self.savgol_window,
                self.savgol_poly,
            )
            for hist_list in targets:
                for hist in hist_list:
                    _savgol(hist)

    def _get_savgol_kernel(self):
        if self._savgol_kernel is not None:
            return self._savgol_kernel
        window = self.savgol_window
        if window <= 1:
            self._savgol_kernel = np.array([1.0], dtype=np.float64)
            return self._savgol_kernel
        poly = min(self.savgol_poly, window - 1)
        half = window // 2
        x = np.arange(-half, half + 1, dtype=np.float64)
        A = np.vander(x, poly + 1, increasing=True)
        ATA = A.T @ A
        ATA_inv = np.linalg.pinv(ATA)
        coeffs = ATA_inv @ A.T
        kernel = coeffs[0]
        kernel /= np.sum(kernel)
        self._savgol_kernel = kernel
        return self._savgol_kernel

    def draw_currents(self, path, tag=""):
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
        for read_ele_num in range(self.read_ele_num):
            c=ROOT.TCanvas("c","canvas1",1600,1300)
            c.cd()
            c.Update()
            c.SetLeftMargin(0.25)
            # c.SetTopMargin(0.12)
            c.SetRightMargin(0.15)
            c.SetBottomMargin(0.17)
            ROOT.gStyle.SetOptStat(ROOT.kFALSE)
            ROOT.gStyle.SetOptStat(0)

            #self.sum_cu.GetXaxis().SetTitleOffset(1.2)
            #self.sum_cu.GetXaxis().SetTitleSize(0.05)
            #self.sum_cu.GetXaxis().SetLabelSize(0.04)
            self.sum_cu[read_ele_num].GetXaxis().SetNdivisions(510)
            #self.sum_cu.GetYaxis().SetTitleOffset(1.1)
            #self.sum_cu.GetYaxis().SetTitleSize(0.05)
            #self.sum_cu.GetYaxis().SetLabelSize(0.04)
            self.sum_cu[read_ele_num].GetYaxis().SetNdivisions(505)
            #self.sum_cu.GetXaxis().CenterTitle()
            #self.sum_cu.GetYaxis().CenterTitle() 
            self.sum_cu[read_ele_num].GetXaxis().SetTitle("Time [s]")
            self.sum_cu[read_ele_num].GetYaxis().SetTitle("Current [A]")
            self.sum_cu[read_ele_num].GetXaxis().SetLabelSize(0.08)
            self.sum_cu[read_ele_num].GetXaxis().SetTitleSize(0.08)
            self.sum_cu[read_ele_num].GetYaxis().SetLabelSize(0.08)
            self.sum_cu[read_ele_num].GetYaxis().SetTitleSize(0.08)
            self.sum_cu[read_ele_num].GetYaxis().SetTitleOffset(1.2)
            self.sum_cu[read_ele_num].SetTitle("")
            self.sum_cu[read_ele_num].SetNdivisions(5)
            self.sum_cu[read_ele_num].Draw("HIST")
            self.positive_cu[read_ele_num].Draw("SAME HIST")
            self.negative_cu[read_ele_num].Draw("SAME HIST")
            self.sum_cu[read_ele_num].Draw("SAME HIST")

            self.positive_cu[read_ele_num].SetLineColor(877)#kViolet-3
            self.negative_cu[read_ele_num].SetLineColor(600)#kBlue
            self.sum_cu[read_ele_num].SetLineColor(418)#kGreen+2

            self.positive_cu[read_ele_num].SetLineWidth(2)
            self.negative_cu[read_ele_num].SetLineWidth(2)
            self.sum_cu[read_ele_num].SetLineWidth(2)
            c.Update()

            if "lgad" in self.det_model:
                self.gain_current.positive_cu[read_ele_num].Draw("SAME HIST")
                self.gain_current.negative_cu[read_ele_num].Draw("SAME HIST")
                self.gain_current.positive_cu[read_ele_num].SetLineColor(617)#kMagneta+1
                self.gain_current.negative_cu[read_ele_num].SetLineColor(867)#kAzure+7
                self.gain_current.positive_cu[read_ele_num].SetLineWidth(2)
                self.gain_current.negative_cu[read_ele_num].SetLineWidth(2)

            if "strip" in self.det_model or "pixel" in self.det_model:
                # make sure you run cross_talk() first and attached cross_talk_cu to self
                self.cross_talk_cu[read_ele_num].Draw("SAME HIST")
                self.cross_talk_cu[read_ele_num].SetLineColor(420)#kGreen+4
                self.cross_talk_cu[read_ele_num].SetLineWidth(2)

            legend = ROOT.TLegend(0.5, 0.2, 0.8, 0.5)
            legend.AddEntry(self.negative_cu[read_ele_num], "electron", "l")
            legend.AddEntry(self.positive_cu[read_ele_num], "hole", "l")

            if "lgad" in self.det_model:
                legend.AddEntry(self.gain_current.negative_cu[read_ele_num], "electron gain", "l")
                legend.AddEntry(self.gain_current.positive_cu[read_ele_num], "hole gain", "l")

            if "strip" in self.det_model:
                legend.AddEntry(self.cross_talk_cu[read_ele_num], "cross talk", "l")

            legend.AddEntry(self.sum_cu[read_ele_num], "total", "l")
            
            legend.SetBorderSize(0)
            #legend.SetTextFont(43)
            legend.SetTextSize(0.08)
            legend.Draw("same")
            c.Update()

            c.SaveAs(path+'/'+tag+"No_"+str(read_ele_num+1)+"electrode"+"_basic_infor.pdf")
            c.SaveAs(path+'/'+tag+"No_"+str(read_ele_num+1)+"electrode"+"_basic_infor.root")
            del c

    def charge_collection_strip(self, path):
        charge=array('d')
        x=array('d')
        for i in range(self.read_ele_num):
            x.append(i+1)
            sum_charge=0
            for j in range(self.n_bin):
                sum_charge=sum_charge+self.cross_talk_cu[i].GetBinContent(j)*self.t_bin
            charge.append(sum_charge/1.6e-19)
        logger.info("Collected charge per electrode (e): %s", list(charge))
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

    def charge_collection_pixel(self, path):
        charge = []
        c1=ROOT.TCanvas("c1","canvas1",1000,1000)
        cce=ROOT.TH2I("cce", "Charge Collection Efficiency", self.x_ele_num, 0, self.x_ele_num, self.y_ele_num, 0, self.y_ele_num)
        for i in range(self.x_ele_num*self.y_ele_num):
            sum_charge=0
            for j in range(self.n_bin):
                sum_charge=sum_charge+self.cross_talk_cu[i].GetBinContent(j)*self.t_bin
            cce.Fill(i%self.x_ele_num, i//self.x_ele_num, sum_charge/1.6e-19)
            charge.append(sum_charge/1.6e-19)
        logger.info("Collected charge per electrode (e): %s", list(charge))
        cce.Draw("COLZ")
        cce.SetTitle("Charge Collection Efficiency")
        cce.GetXaxis().SetTitle("x_elenumber")
        cce.GetYaxis().SetTitle("y_elenumber")
        cce.GetZaxis().SetTitle("charge[Coulomb]")
        c1.SaveAs(path+"/cce.pdf")
        c1.SaveAs(path+"/cce.root")
    
class CalCurrentGain(CalCurrent):
    '''Calculation of gain carriers and gain current, simplified version'''
    def __init__(self, my_d, my_f, my_current):
        self.t_bin = t_bin[my_d.dimension]
        self.t_end = t_end[my_d.dimension]
        self.t_start = t_start
        self.delta_t = delta_t[my_d.dimension]
        self.n_bin = int((self.t_end+t_tol-self.t_start)/self.t_bin)
    
        self.read_ele_num = my_current.read_ele_num
        self.read_out_contact = my_current.read_out_contact

        # 创建增益载流子系统
        self.electron_system = None
        self.hole_system = None
        
        gain_rate = my_d.gain_rate
        logger.info("gain_rate=%s", gain_rate)
        
        # 创建增益载流子
        gain_positions = []
        gain_electron_charges = []
        gain_hole_charges = []
        gain_times = []
        gain_signals = []
        
        if my_d.voltage < 0:  # p层在d=0，空穴倍增为电子
            if my_current.hole_system:
                for i in range(len(my_current.hole_system.positions)):
                    last_pos = my_current.hole_system.paths[i][-1]
                    gain_positions.append([last_pos[0], last_pos[1], my_d.avalanche_bond])
                    gain_electron_charges.append(-my_current.hole_system.charges[i] * gain_rate)
                    gain_hole_charges.append(my_current.hole_system.charges[i] * gain_rate)
                    gain_times.append(last_pos[3])
                    gain_signals.append([])
            else:
                logger.warning("No hole system found for gain calculation in p-layer multiplication.")
        else:  # n层在d=0，电子倍增为空穴
            if my_current.electron_system:
                for i in range(len(my_current.electron_system.positions)):
                    last_pos = my_current.electron_system.paths[i][-1]
                    gain_positions.append([last_pos[0], last_pos[1], my_d.avalanche_bond])
                    gain_hole_charges.append(-my_current.electron_system.charges[i] * gain_rate)
                    gain_electron_charges.append(my_current.electron_system.charges[i] * gain_rate)
                    gain_times.append(last_pos[3])
                    gain_signals.append([])
            else:
                logger.warning("No electron system found for gain calculation in n-layer multiplication.")

        # 创建增益载流子系统
        if gain_electron_charges:
            self.electron_system = VectorizedCarrierSystem(
                gain_positions, gain_electron_charges, gain_times, gain_signals,
                my_d.material, "electron_gain", self.read_out_contact, my_d
            )
        else:
            logger.info("No gain electrons generated.")
        
        if gain_hole_charges:
            self.hole_system = VectorizedCarrierSystem(
                gain_positions, gain_hole_charges, gain_times, gain_signals,
                my_d.material, "hole_gain", self.read_out_contact, my_d
            )
        else:
            logger.info("No gain holes generated.")

        # 执行漂移
        self.drifting_loop(my_d, my_f)

        # 初始化电流
        self.current_define(self.read_ele_num)
        for i in range(self.read_ele_num):
            self.positive_cu[i].Reset()
            self.negative_cu[i].Reset()
        
        # 计算电流
        self.get_current(my_d.x_ele_num, my_d.y_ele_num, self.read_out_contact)

    def current_define(self,read_ele_num):
        """
        @description: 
            Parameter current setting     
        @param:
            positive_cu -- Current from holes move
            negative_cu -- Current from electrons move
            sum_cu -- Current from e-h move
        @Returns:
            None
        @Modify:
            2021/08/31
        """
        self.positive_cu=[]
        self.negative_cu=[]

        for i in range(read_ele_num):
            self.positive_cu.append(ROOT.TH1F("gain_charge_tmp+"+str(i+1)," No."+str(i+1)+"Gain Positive Current",
                                        self.n_bin, self.t_start, self.t_end))
            self.negative_cu.append(ROOT.TH1F("gain_charge_tmp-"+str(i+1)," No."+str(i+1)+"Gain Negative Current",
                                        self.n_bin, self.t_start, self.t_end))

class CalCurrentG4P(CalCurrent):
    def __init__(self, my_d, my_f, my_g4, batch):
        G4P_carrier_list = CarrierListFromG4P(my_d.material, my_g4, batch)
        super().__init__(my_d, my_f, G4P_carrier_list.ionized_pairs, G4P_carrier_list.track_position)
        if self.read_ele_num > 1:
            #self.cross_talk()
            pass


class CalCurrentLaser(CalCurrent):
    def __init__(self, my_d, my_f, my_l):
        super().__init__(my_d, my_f, my_l.ionized_pairs, my_l.track_position)
        
        for i in range(self.read_ele_num):
            
            # convolute the signal with the laser pulse shape in time
            convolved_positive_cu = ROOT.TH1F("convolved_charge+", "Positive Current",
                                        self.n_bin, self.t_start, self.t_end)
            convolved_negative_cu = ROOT.TH1F("convolved_charge-", "Negative Current",
                                        self.n_bin, self.t_start, self.t_end)
            convolved_sum_cu = ROOT.TH1F("convolved_charge","Total Current",
                                        self.n_bin, self.t_start, self.t_end)
            
            convolved_positive_cu.Reset()
            convolved_negative_cu.Reset()
            convolved_sum_cu.Reset()

            signal_convolution(self.positive_cu[i],convolved_positive_cu,[my_l.timePulse])
            signal_convolution(self.negative_cu[i],convolved_negative_cu,[my_l.timePulse])
            signal_convolution(self.sum_cu[i],convolved_sum_cu,[my_l.timePulse])

            self.positive_cu[i] = convolved_positive_cu
            self.negative_cu[i] = convolved_negative_cu
            self.sum_cu[i] = convolved_sum_cu

            if my_d.det_model == "lgad":
                convolved_gain_positive_cu = ROOT.TH1F("convolved_gain_charge+","Gain Positive Current",
                                        self.n_bin, self.t_start, self.t_end)
                convolved_gain_negative_cu = ROOT.TH1F("convolved_gain_charge-","Gain Negative Current",
                                        self.n_bin, self.t_start, self.t_end)
                convolved_gain_positive_cu.Reset()
                convolved_gain_negative_cu.Reset()
                signal_convolution(self.gain_current.positive_cu[i],convolved_gain_positive_cu,[my_l.timePulse])
                signal_convolution(self.gain_current.negative_cu[i],convolved_gain_negative_cu,[my_l.timePulse])
                self.gain_current.positive_cu[i] = convolved_gain_positive_cu
                self.gain_current.negative_cu[i] = convolved_gain_negative_cu