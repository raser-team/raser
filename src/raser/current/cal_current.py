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
    2: 50e-9,
    3: 50e-9
}

delta_t = {
    1: 2e-12,  # simulation time step
    2: 20e-12,
    3: 20e-12
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
        if getattr(my_d, "has_avalanche", False):
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

    def _get_active_time_window(self, histograms, padding_bins=10, threshold_ratio=1e-3, max_fraction=0.3):
        active_bins = []
        max_abs_value = 0.0
        nbins = None

        for hist in histograms:
            if hist is None:
                continue
            if nbins is None:
                nbins = hist.GetNbinsX()
            else:
                nbins = min(nbins, hist.GetNbinsX())
            max_abs_value = max(
                max_abs_value,
                abs(hist.GetMaximum()),
                abs(hist.GetMinimum()),
            )

        if nbins is None or max_abs_value <= 0:
            return None

        threshold = max_abs_value * threshold_ratio
        for bin_idx in range(1, nbins + 1):
            for hist in histograms:
                if hist is None:
                    continue
                if abs(hist.GetBinContent(bin_idx)) > threshold:
                    active_bins.append(bin_idx)
                    break

        if not active_bins:
            return None

        first_bin = max(1, active_bins[0] - padding_bins)
        last_bin = min(nbins, active_bins[-1] + padding_bins)
        xmin = histograms[0].GetBinLowEdge(first_bin)
        xmax = histograms[0].GetBinLowEdge(last_bin + 1)
        full_xmin = histograms[0].GetXaxis().GetXmin()
        full_xmax = histograms[0].GetXaxis().GetXmax()
        full_span = full_xmax - full_xmin
        active_span = xmax - xmin

        if full_span <= 0 or active_span >= max_fraction * full_span:
            return None
        return xmin, xmax

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

            if hasattr(self, "gain_current"):
                self.gain_current.positive_cu[read_ele_num].Draw("SAME HIST")
                self.gain_current.negative_cu[read_ele_num].Draw("SAME HIST")
                self.gain_current.positive_cu[read_ele_num].SetLineColor(617)#kMagneta+1
                self.gain_current.negative_cu[read_ele_num].SetLineColor(867)#kAzure+7
                self.gain_current.positive_cu[read_ele_num].SetLineWidth(2)
                self.gain_current.negative_cu[read_ele_num].SetLineWidth(2)

            has_cross_talk = hasattr(self, "cross_talk_cu") and read_ele_num < len(self.cross_talk_cu)

            if ("strip" in self.det_model or "pixel" in self.det_model) and has_cross_talk:
                # make sure you run cross_talk() first and attached cross_talk_cu to self
                self.cross_talk_cu[read_ele_num].Draw("SAME HIST")
                self.cross_talk_cu[read_ele_num].SetLineColor(420)#kGreen+4
                self.cross_talk_cu[read_ele_num].SetLineWidth(2)

            legend = ROOT.TLegend(0.5, 0.2, 0.8, 0.5)
            legend.AddEntry(self.negative_cu[read_ele_num], "electron", "l")
            legend.AddEntry(self.positive_cu[read_ele_num], "hole", "l")

            if hasattr(self, "gain_current"):
                legend.AddEntry(self.gain_current.negative_cu[read_ele_num], "electron gain", "l")
                legend.AddEntry(self.gain_current.positive_cu[read_ele_num], "hole gain", "l")

            if "strip" in self.det_model and has_cross_talk:
                legend.AddEntry(self.cross_talk_cu[read_ele_num], "cross talk", "l")

            legend.AddEntry(self.sum_cu[read_ele_num], "total", "l")
            
            legend.SetBorderSize(0)
            #legend.SetTextFont(43)
            legend.SetTextSize(0.08)
            legend.Draw("same")
            c.Update()

            c.SaveAs(path+'/'+tag+"No_"+str(read_ele_num+1)+"electrode"+"_basic_infor.pdf")
            c.SaveAs(path+'/'+tag+"No_"+str(read_ele_num+1)+"electrode"+"_basic_infor.root")

            active_window = self._get_active_time_window([
                self.negative_cu[read_ele_num],
                self.positive_cu[read_ele_num],
                self.sum_cu[read_ele_num],
            ])
            if active_window is not None:
                xmin, xmax = active_window
                for hist in (self.negative_cu[read_ele_num], self.positive_cu[read_ele_num], self.sum_cu[read_ele_num]):
                    hist.GetXaxis().SetRangeUser(xmin, xmax)
                c.Update()
                c.SaveAs(path+'/'+tag+"No_"+str(read_ele_num+1)+"electrode"+"_basic_infor_zoom.pdf")
                c.SaveAs(path+'/'+tag+"No_"+str(read_ele_num+1)+"electrode"+"_basic_infor_zoom.root")
                for hist in (self.negative_cu[read_ele_num], self.positive_cu[read_ele_num], self.sum_cu[read_ele_num]):
                    hist.GetXaxis().UnZoom()
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
        
        gain_rate = getattr(my_d, "gain_rate", 0.0)
        logger.info("gain_rate=%s", gain_rate)
        
        # 创建增益载流子
        gain_positions = []
        gain_electron_charges = []
        gain_hole_charges = []
        gain_times = []
        gain_signals = []

        gain_algorithm = getattr(my_d, "gain_algorithm", "planar_integral")
        if gain_algorithm == "planar_integral":
            self._build_planar_gain_carriers(
                my_d,
                my_current,
                gain_rate,
                gain_positions,
                gain_electron_charges,
                gain_hole_charges,
                gain_times,
                gain_signals
            )
        else:
            self._build_local_gain_carriers(
                my_d,
                my_f,
                my_current,
                gain_positions,
                gain_electron_charges,
                gain_hole_charges,
                gain_times,
                gain_signals
            )

        logger.info(
            "gain carriers generated: algorithm=%s, pairs=%d",
            gain_algorithm,
            len(gain_positions)
        )

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

    def _build_planar_gain_carriers(self, my_d, my_current, gain_rate, gain_positions,
                                    gain_electron_charges, gain_hole_charges,
                                    gain_times, gain_signals):
        if my_d.avalanche_bond is None:
            raise ValueError("planar_integral gain algorithm requires `avalanche_bond` in detector settings")

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

    def _build_local_gain_carriers(self, my_d, my_f, my_current, gain_positions,
                                   gain_electron_charges, gain_hole_charges,
                                   gain_times, gain_signals):
        material = Material(my_d.material, avalanche_model=my_d.avalanche_model)
        cal_coefficient = material.cal_coefficient
        min_pairs = max(float(getattr(my_d, "gain_pair_threshold", 0.05)), 0.0)
        max_carriers = int(getattr(my_d, "gain_max_carriers", 50000))
        top_n = max(int(getattr(my_d, "gain_diagnostics_top_n", 5)), 0)
        diagnostics = {
            "segments_total": 0,
            "segments_with_alpha": 0,
            "segments_above_threshold": 0,
            "field_eval_errors": 0,
            "max_field": 0.0,
            "max_alpha": 0.0,
            "max_segment_exponent": 0.0,
            "max_substeps": 1,
            "max_raw_gain_pairs": 0.0,
            "max_effective_gain_pairs": 0.0,
            "max_running_parent_pairs": 0.0,
            "total_raw_gain_pairs": 0.0,
            "total_effective_gain_pairs": 0.0,
            "total_emitted_gain_pairs": 0.0,
            "total_below_threshold_pairs": 0.0,
            "carrier_limit_reached": False,
            "top_segments_limit": top_n,
            "top_field_segments": [],
            "top_gain_segments": [],
            "temperature": my_d.temperature,
            "local_gain_max_exponent": max(float(getattr(my_d, "local_gain_max_exponent", 0.5)), 0.0),
            "local_gain_emit_slices": max(1, int(getattr(my_d, "local_gain_emit_slices", 2))),
            "local_gain_field_method": getattr(my_d, "local_gain_field_method", "potential_gradient"),
            "local_gain_field_neighbors": max(8, int(getattr(my_d, "local_gain_field_neighbors", 128))),
            "local_gain_field_max": max(0.0, float(getattr(my_d, "local_gain_field_max", 1.0e6))),
            "local_gain_integration_step_um": max(0.02, float(getattr(my_d, "local_gain_integration_step_um", 0.25))),
            "local_gain_integration_max_steps": max(1, int(getattr(my_d, "local_gain_integration_max_steps", 16))),
            "local_gain_cascade": bool(getattr(my_d, "local_gain_cascade", False))
        }

        self._build_local_gain_carriers_from_system(
            getattr(my_current, "electron_system", None),
            my_d,
            my_f,
            cal_coefficient,
            min_pairs,
            max_carriers,
            diagnostics,
            gain_positions,
            gain_electron_charges,
            gain_hole_charges,
            gain_times,
            gain_signals
        )
        self._build_local_gain_carriers_from_system(
            getattr(my_current, "hole_system", None),
            my_d,
            my_f,
            cal_coefficient,
            min_pairs,
            max_carriers,
            diagnostics,
            gain_positions,
            gain_electron_charges,
            gain_hole_charges,
            gain_times,
            gain_signals
        )
        logger.info(
            "local gain diagnostics: segments=%d, alpha>0=%d, above_threshold=%d, field_errors=%d, "
            "max_field=%.3e V/cm, max_alpha=%.3e cm^-1, max_segment_exponent=%.3e, "
            "max_substeps=%d, max_parent_pairs=%.3e, max_raw_gain_pairs=%.3e, max_gain_pairs=%.3e, "
            "total_raw_gain_pairs=%.3e, total_gain_pairs=%.3e, emitted_gain_pairs=%.3e, "
            "below_threshold_pairs=%.3e, threshold=%.3e, exp_cap=%.3e, cascade=%s, field_method=%s",
            diagnostics["segments_total"],
            diagnostics["segments_with_alpha"],
            diagnostics["segments_above_threshold"],
            diagnostics["field_eval_errors"],
            diagnostics["max_field"],
            diagnostics["max_alpha"],
            diagnostics["max_segment_exponent"],
            diagnostics["max_substeps"],
            diagnostics["max_running_parent_pairs"],
            diagnostics["max_raw_gain_pairs"],
            diagnostics["max_effective_gain_pairs"],
            diagnostics["total_raw_gain_pairs"],
            diagnostics["total_effective_gain_pairs"],
            diagnostics["total_emitted_gain_pairs"],
            diagnostics["total_below_threshold_pairs"],
            min_pairs,
            diagnostics["local_gain_max_exponent"],
            diagnostics["local_gain_cascade"],
            diagnostics["local_gain_field_method"]
        )
        self._log_local_gain_segments(
            diagnostics["top_field_segments"],
            "local gain strongest-field segments",
            top_n
        )
        self._log_local_gain_segments(
            diagnostics["top_gain_segments"],
            "local gain strongest-gain segments",
            top_n
        )
        if hasattr(my_f, "get_cache_stats"):
            cache_stats = my_f.get_cache_stats()
            if cache_stats.get("gain_hits", 0) or cache_stats.get("gain_misses", 0):
                logger.info(
                    "local gain field cache: hits=%d, misses=%d, fallbacks=%d, errors=%d, entries=%d",
                    cache_stats.get("gain_hits", 0),
                    cache_stats.get("gain_misses", 0),
                    cache_stats.get("gain_fallbacks", 0),
                    cache_stats.get("gain_errors", 0),
                    cache_stats.get("gain_entries", 0)
                )

    def _build_local_gain_segment_entry(self, carrier_system, carrier_idx, x_mid, y_mid, z_mid,
                                        segment_length_um, e_norm, alpha, parent_charge, t1):
        return {
            "carrier_type": carrier_system.carrier_type,
            "carrier_idx": int(carrier_idx),
            "x_um": float(x_mid),
            "y_um": float(y_mid),
            "z_um": float(z_mid),
            "length_um": float(segment_length_um),
            "field_v_per_cm": float(e_norm),
            "alpha_cm_inv": float(alpha),
            "parent_pairs": float(parent_charge),
            "running_parent_pairs": float(parent_charge),
            "time_ns": float(t1 * self.delta_t * 1e9),
            "segment_exponent": 0.0,
            "substeps": 1,
            "emit_slices": 1,
            "gain_pairs": 0.0,
            "raw_gain_pairs": 0.0
        }

    def _record_local_gain_segment(self, bucket, limit, score, segment):
        if limit <= 0 or not np.isfinite(score):
            return

        entry = dict(segment)
        entry["score"] = float(score)
        bucket.append(entry)
        bucket.sort(key=lambda item: item["score"], reverse=True)
        if len(bucket) > limit:
            del bucket[limit:]

    def _log_local_gain_segments(self, segments, title, top_n):
        if not segments or top_n <= 0:
            return

        logger.info("%s (top %d):", title, len(segments))
        for idx, segment in enumerate(segments, start=1):
            logger.info(
                "  #%d carrier=%s[%d], pos=(%.2f, %.2f, %.2f) um, len=%.3f um, t=%.3f ns, "
                "field=%.3e V/cm, alpha=%.3e cm^-1, exponent=%.3e, substeps=%d, emit_slices=%d, "
                "gain_pairs=%.3e, raw_gain_pairs=%.3e, parent_pairs=%.3e",
                idx,
                segment["carrier_type"],
                segment["carrier_idx"],
                segment["x_um"],
                segment["y_um"],
                segment["z_um"],
                segment["length_um"],
                segment["time_ns"],
                segment["field_v_per_cm"],
                segment["alpha_cm_inv"],
                segment.get("segment_exponent", 0.0),
                int(segment.get("substeps", 1)),
                int(segment.get("emit_slices", 1)),
                segment["gain_pairs"],
                segment.get("raw_gain_pairs", segment["gain_pairs"]),
                segment["parent_pairs"]
            )

    def _calculate_local_gain_pairs(self, parent_charge, alpha, segment_length_um, max_exponent):
        segment_exponent = max(alpha * segment_length_um * 1e-4, 0.0)
        return self._calculate_local_gain_pairs_from_exponent(parent_charge, segment_exponent, max_exponent)

    def _calculate_local_gain_pairs_from_exponent(self, parent_charge, segment_exponent, max_exponent):
        segment_exponent = max(float(segment_exponent), 0.0)
        if not math.isfinite(segment_exponent):
            return 0.0, 1, 0.0, 0.0
        if segment_exponent <= 0 or parent_charge <= 0:
            return 0.0, 1, 0.0, 0.0

        raw_gain_pairs = parent_charge * math.expm1(min(segment_exponent, 50.0))
        if max_exponent <= 0:
            substeps = 1
        else:
            substeps = max(1, int(math.ceil(segment_exponent / max_exponent)))
        # Splitting is only an emission/discretization control. It must not
        # change the total avalanche charge implied by the integrated exponent.
        stabilized_gain_pairs = raw_gain_pairs
        return segment_exponent, substeps, raw_gain_pairs, stabilized_gain_pairs

    def _get_local_gain_field(self, my_f, x, y, z, diagnostics):
        if hasattr(my_f, "get_gain_e_field_cached"):
            return my_f.get_gain_e_field_cached(
                x,
                y,
                z,
                diagnostics["local_gain_field_method"],
                diagnostics["local_gain_field_neighbors"],
                diagnostics["local_gain_field_max"]
            )
        return my_f.get_e_field_cached(x, y, z)

    def _integrate_local_gain_exponent(self, my_f, cal_coefficient, charge_sign,
                                       x0, y0, z0, x1, y1, z1, segment_length_um,
                                       diagnostics):
        step_um = diagnostics["local_gain_integration_step_um"]
        max_steps = diagnostics["local_gain_integration_max_steps"]
        sample_count = min(max(1, int(math.ceil(segment_length_um / step_um))), max_steps)
        exponent = 0.0
        max_field = 0.0
        max_alpha = 0.0
        weighted_field = 0.0
        weighted_alpha = 0.0

        for sample_idx in range(sample_count):
            fraction = (sample_idx + 0.5) / sample_count
            x_sample = x0 + fraction * (x1 - x0)
            y_sample = y0 + fraction * (y1 - y0)
            z_sample = z0 + fraction * (z1 - z0)
            e_field = self._get_local_gain_field(my_f, x_sample, y_sample, z_sample, diagnostics)
            if e_field is None:
                raise ValueError("local gain field evaluation returned None")
            e_norm = Vector(*e_field).get_length()
            if not math.isfinite(e_norm):
                raise ValueError("local gain field evaluation returned non-finite field")
            alpha = cal_coefficient(e_norm, charge_sign, diagnostics["temperature"])
            if not math.isfinite(alpha):
                alpha = 0.0
            ds_um = segment_length_um / sample_count
            exponent += max(alpha, 0.0) * ds_um * 1e-4
            max_field = max(max_field, e_norm)
            max_alpha = max(max_alpha, alpha)
            weighted_field += e_norm * ds_um
            weighted_alpha += alpha * ds_um

        return {
            "exponent": exponent,
            "max_field": max_field,
            "max_alpha": max_alpha,
            "mean_field": weighted_field / segment_length_um,
            "mean_alpha": weighted_alpha / segment_length_um,
            "samples": sample_count,
        }

    def _clip_gain_position_to_detector(self, x, y, z, my_d):
        margin = 1e-3
        return [
            min(max(float(x), margin), max(float(my_d.l_x) - margin, margin)),
            min(max(float(y), margin), max(float(my_d.l_y) - margin, margin)),
            min(max(float(z), margin), max(float(my_d.l_z) - margin, margin)),
        ]

    def _append_local_gain_carrier_slices(self, x0, y0, z0, t0, x1, y1, z1, t1, gain_pairs,
                                          max_emit_slices, my_d, gain_positions, gain_electron_charges,
                                          gain_hole_charges, gain_times, gain_signals):
        emit_slices = max(1, int(max_emit_slices))
        per_slice_pairs = gain_pairs / emit_slices
        for slice_idx in range(emit_slices):
            fraction = (slice_idx + 0.5) / emit_slices
            x_slice = x0 + fraction * (x1 - x0)
            y_slice = y0 + fraction * (y1 - y0)
            z_slice = z0 + fraction * (z1 - z0)
            t_slice = t0 + fraction * (t1 - t0)
            gain_positions.append(self._clip_gain_position_to_detector(x_slice, y_slice, z_slice, my_d))
            gain_electron_charges.append(-per_slice_pairs)
            gain_hole_charges.append(per_slice_pairs)
            gain_times.append(int(round(t_slice)))
            gain_signals.append([])
        return emit_slices

    def _build_local_gain_carriers_from_system(self, carrier_system, my_d, my_f, cal_coefficient,
                                               min_pairs, max_carriers, diagnostics, gain_positions,
                                               gain_electron_charges, gain_hole_charges,
                                               gain_times, gain_signals):
        if carrier_system is None:
            return

        max_reached = False
        for carrier_idx, path in enumerate(carrier_system.paths):
            if max_reached:
                break

            parent_charge = abs(carrier_system.charges[carrier_idx])
            if parent_charge <= 0 or len(path) < 2:
                continue
            running_parent_charge = parent_charge

            charge_sign = -1 if carrier_system.charges[carrier_idx] < 0 else 1

            for point0, point1 in zip(path[:-1], path[1:]):
                x0, y0, z0, t0 = point0
                x1, y1, z1, t1 = point1
                dx = x1 - x0
                dy = y1 - y0
                dz = z1 - z0
                segment_length_um = np.sqrt(dx * dx + dy * dy + dz * dz)
                if segment_length_um <= 0:
                    continue
                diagnostics["segments_total"] += 1

                x_mid = 0.5 * (x0 + x1)
                y_mid = 0.5 * (y0 + y1)
                z_mid = 0.5 * (z0 + z1)

                try:
                    gain_integral = self._integrate_local_gain_exponent(
                        my_f,
                        cal_coefficient,
                        charge_sign,
                        x0,
                        y0,
                        z0,
                        x1,
                        y1,
                        z1,
                        segment_length_um,
                        diagnostics
                    )
                except Exception:
                    diagnostics["field_eval_errors"] += 1
                    continue

                e_norm = gain_integral["max_field"]
                diagnostics["max_field"] = max(diagnostics["max_field"], e_norm)
                alpha = gain_integral["max_alpha"]
                diagnostics["max_alpha"] = max(diagnostics["max_alpha"], alpha)
                segment_entry = self._build_local_gain_segment_entry(
                    carrier_system,
                    carrier_idx,
                    x_mid,
                    y_mid,
                    z_mid,
                    segment_length_um,
                    e_norm,
                    alpha,
                    running_parent_charge,
                    t1
                )
                if alpha <= 0:
                    self._record_local_gain_segment(
                        diagnostics["top_field_segments"],
                        diagnostics["top_segments_limit"],
                        e_norm,
                        segment_entry
                    )
                    continue
                diagnostics["segments_with_alpha"] += 1

                segment_exponent, substeps, raw_gain_pairs, gain_pairs = self._calculate_local_gain_pairs_from_exponent(
                    running_parent_charge,
                    gain_integral["exponent"],
                    diagnostics["local_gain_max_exponent"]
                )
                diagnostics["max_segment_exponent"] = max(diagnostics["max_segment_exponent"], segment_exponent)
                diagnostics["max_substeps"] = max(diagnostics["max_substeps"], substeps)
                diagnostics["max_running_parent_pairs"] = max(diagnostics["max_running_parent_pairs"], running_parent_charge)
                diagnostics["max_raw_gain_pairs"] = max(diagnostics["max_raw_gain_pairs"], raw_gain_pairs)
                diagnostics["max_effective_gain_pairs"] = max(diagnostics["max_effective_gain_pairs"], gain_pairs)
                diagnostics["total_raw_gain_pairs"] += raw_gain_pairs
                diagnostics["total_effective_gain_pairs"] += gain_pairs
                segment_entry["segment_exponent"] = float(segment_exponent)
                segment_entry["substeps"] = int(substeps)
                segment_entry["raw_gain_pairs"] = float(raw_gain_pairs)
                segment_entry["gain_pairs"] = float(gain_pairs)
                if max_carriers > 0:
                    remaining_capacity = max_carriers - len(gain_positions)
                    if remaining_capacity <= 0:
                        logger.warning(
                            "Gain carrier generation reached configured limit (%d). Truncating local avalanche carriers.",
                            max_carriers
                        )
                        diagnostics["carrier_limit_reached"] = True
                        max_reached = True
                        break
                    emit_slices = min(substeps, diagnostics["local_gain_emit_slices"], remaining_capacity)
                else:
                    emit_slices = min(substeps, diagnostics["local_gain_emit_slices"])
                emit_slices = max(1, emit_slices)
                segment_entry["emit_slices"] = int(emit_slices)
                self._record_local_gain_segment(
                    diagnostics["top_field_segments"],
                    diagnostics["top_segments_limit"],
                    e_norm,
                    segment_entry
                )
                self._record_local_gain_segment(
                    diagnostics["top_gain_segments"],
                    diagnostics["top_segments_limit"],
                    gain_pairs,
                    segment_entry
                )
                if gain_pairs < min_pairs:
                    diagnostics["total_below_threshold_pairs"] += gain_pairs
                    if diagnostics["local_gain_cascade"]:
                        running_parent_charge += gain_pairs
                    continue
                diagnostics["segments_above_threshold"] += 1

                self._append_local_gain_carrier_slices(
                    x0, y0, z0, t0,
                    x1, y1, z1, t1,
                    gain_pairs,
                    emit_slices,
                    my_d,
                    gain_positions,
                    gain_electron_charges,
                    gain_hole_charges,
                    gain_times,
                    gain_signals
                )
                diagnostics["total_emitted_gain_pairs"] += gain_pairs
                if diagnostics["local_gain_cascade"]:
                    running_parent_charge += gain_pairs

                if max_carriers > 0 and len(gain_positions) >= max_carriers:
                    logger.warning(
                        "Gain carrier generation reached configured limit (%d). Truncating local avalanche carriers.",
                        max_carriers
                    )
                    diagnostics["carrier_limit_reached"] = True
                    max_reached = True
                    break

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

            if hasattr(self, "gain_current"):
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
