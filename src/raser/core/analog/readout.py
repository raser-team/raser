#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

"""
Description:
    Simulate induced current through Broad_Band or Charge_Sensitive amplifier
@Date       : 2024/09/22 15:24:33
@Author     : Yuhang Tan, Chenxi Fu
@version    : 2.0
"""

import math
import json
import os
import subprocess
import time

import numpy as np
import ROOT

from .ngspice import set_ngspice_input
from .ngspice import set_tmp_cir
from raser.supports.output import output
from raser.supports.output import delete_file
from raser.supports.paths import optional_component_path

ROOT.gROOT.SetBatch(True)


def _new_histogram(name, title, n_bins, t_start, t_end):
    add_directory = ROOT.TH1.AddDirectoryStatus()
    ROOT.TH1.AddDirectory(False)
    try:
        return ROOT.TH1F(name, title, n_bins, t_start, t_end)
    finally:
        ROOT.TH1.AddDirectory(add_directory)


def _hist_contents(hist: ROOT.TH1F) -> np.ndarray:
    n_bins = hist.GetNbinsX()
    return np.array(
        [hist.GetBinContent(bin_idx) for bin_idx in range(1, n_bins + 1)],
        dtype=np.float64,
    )


def _set_hist_contents(hist: ROOT.TH1F, values: np.ndarray):
    n_bins = hist.GetNbinsX()
    if len(values) != n_bins:
        raise ValueError(
            f"Histogram {hist.GetName()} has {n_bins} bins, got {len(values)} values"
        )
    for bin_idx, value in enumerate(values, start=1):
        hist.SetBinContent(bin_idx, float(value))


def _hist_bin_centers(hist: ROOT.TH1F) -> np.ndarray:
    n_bins = hist.GetNbinsX()
    axis = hist.GetXaxis()
    return np.array(
        [axis.GetBinCenter(bin_idx) for bin_idx in range(1, n_bins + 1)],
        dtype=np.float64,
    )


def _convolve_samples(
    values: np.ndarray,
    t_bin: float,
    pulse_responce_function_list: list,
) -> np.ndarray:
    if t_bin <= 0:
        raise ValueError(f"Convolution bin width must be positive, got {t_bin}")
    result = np.asarray(values, dtype=np.float64)
    n_bins = len(result)
    if n_bins == 0:
        return result
    times = np.arange(n_bins, dtype=np.float64) * t_bin
    for response in pulse_responce_function_list:
        kernel = np.array([response(time) for time in times], dtype=np.float64)
        result = np.convolve(result, kernel, mode="full")[:n_bins] * t_bin
    return result


def _convolve_histogram_causal(
    hist: ROOT.TH1F,
    pulse_responce_function_list: list,
) -> np.ndarray:
    return _convolve_samples(
        _hist_contents(hist),
        hist.GetBinWidth(1),
        pulse_responce_function_list,
    )


def _hist_activity_window(
    hist: ROOT.TH1F,
    relative_threshold: float = 0.02,
    absolute_threshold: float = 0.0,
):
    values = np.abs(_hist_contents(hist))
    if len(values) == 0:
        return None

    peak = float(np.max(values))
    if peak <= 0.0:
        return None

    threshold = max(relative_threshold * peak, absolute_threshold)
    active = np.flatnonzero(values >= threshold)
    if len(active) == 0:
        return None

    centers = _hist_bin_centers(hist)
    return float(centers[active[0]]), float(centers[active[-1]])


def _combined_activity_window(histograms, absolute_thresholds=None):
    if absolute_thresholds is None:
        absolute_thresholds = [0.0] * len(histograms)

    axis_min = min(hist.GetXaxis().GetXmin() for hist in histograms)
    axis_max = max(hist.GetXaxis().GetXmax() for hist in histograms)
    windows = []
    for hist, absolute_threshold in zip(histograms, absolute_thresholds):
        window = _hist_activity_window(
            hist,
            absolute_threshold=absolute_threshold,
        )
        if window is not None:
            windows.append(window)

    if not windows:
        return axis_min, axis_max

    xmax = max(window[1] for window in windows)
    standard_ends = [1e-9, 2e-9, 5e-9, 10e-9, 20e-9, 50e-9, 100e-9]
    selected_end = standard_ends[-1]
    for candidate in standard_ends:
        if xmax <= candidate:
            selected_end = candidate
            break

    xmin = -0.25 * selected_end
    return max(axis_min, xmin), min(axis_max, selected_end)


class Amplifier:
    """Get current after amplifier with convolution, for each reading electrode

    Parameters
    ---------
    currents : list[ROOT.TH1F]
        The ROOT.TH1F objects of induced current with time information

    amplifier_name : str
        The name of the amplifier

    CDet : None | float
        The capacitance of the detector

    Attributes
    ---------
    amplified_currents: list[ROOT.TH1F]
        The list of induced current after amplifier

    Methods
    ---------
    amplifier_define
        Define parameters and the responce function of amplifier

    fill_amplifier_output
        Get the induced current after amplifier

    set_scope_output
        Get the scope output after amplifier

    Last Modified
    ---------
        2024/09/14
    """
    def __init__(
        self,
        currents: list[ROOT.TH1F],
        amplifier_name: str,
        seed = 0,
        CDet = None,
        is_cut = False,
    ):
        self.amplified_currents = []
        self.read_ele_num = len(currents)
        self.time_unit = 10e-12
        # TODO: need to set the time unit corresponding to the oscilloscope or the TDC 
        # TODO: and consistent with the time unit in gen_signal_batch.py

        ele_json = optional_component_path(
            "electronics", "analog", amplifier_name + ".json"
        )
        ele_cir = optional_component_path(
            "electronics", "analog", amplifier_name + ".cir"
        )
        if ele_json is not None and os.path.exists(ele_json):
            with open(ele_json) as f:
                self.amplifier_parameters = json.load(f)
                self.name = self.amplifier_parameters['ele_name']

            self.amplifier_define(CDet)
            self.fill_amplifier_output(currents)
            self.set_scope_output(currents)
            self.add_noise(seed)
            if is_cut:
                self.judge_threshold_CFD()

        elif ele_cir is not None and os.path.exists(ele_cir):
            self.name = amplifier_name
            input_current_strs = set_ngspice_input(currents)
            time_stamp = time.time_ns()
            pid = os.getpid()
            # stamp and thread name for avoiding file name conflict
            path = output(__file__, self.name)
            tmp_cirs, raws = set_tmp_cir(self.read_ele_num, path, input_current_strs, ele_cir, str(time_stamp)+"_"+str(pid),)
            for i in range(self.read_ele_num):
                print("Running ngspice for amplifier simulation on electrode No.%d..."%(i+1))
                subprocess.run(['ngspice -b '+tmp_cirs[i]], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,)
            self.read_raw_file(raws)
            # TODO: delete the files properly
            for tmp_cir in tmp_cirs:
                delete_file(tmp_cir)
            for raw in raws:
                delete_file(raw)

        else:
            raise NameError("The amplifier file is not found!")

    def amplifier_define(self, CDet):
        """
        Description:
            The parameters, pulse responce function and scope scaling of the amplifier.
            Details introduction can be got in setting module.
        @Modify:
        ---------
            2021/09/09
        """
        if CDet is None:
            raise ValueError("Detector capacitance must be provided by the detector")

        if self.amplifier_parameters['ele_name'] == 'Charge_Sensitive':
            """ Current Sensitive Amplifier parameter initialization"""

            mode = 0

            def pulse_responce_Charge_Sensitive(t):
                if t < 0: # step function
                    return 0

                t_rise   = self.amplifier_parameters['t_rise']
                t_fall   = self.amplifier_parameters['t_fall']

                tau_rise = t_rise/2.2*1e-9
                tau_fall = t_fall/2.2*1e-9
                if tau_rise == tau_fall:
                    tau_rise *= 0.9

                return ( tau_fall/(tau_fall+tau_rise) * (math.exp(-t/tau_fall)-math.exp(-t/tau_rise))
                )

            def scale_Charge_Sensitive(output_Q_max, input_Q_tot):
                """Current Sensitive Amplifier scale function"""
                trans_imp = self.amplifier_parameters['trans_imp']
                Ci = 3.5e-11  #fF
                Qfrac = 1.0/(1.0+CDet*1e-12/Ci)

                if output_Q_max == 0.0:
                    return 0.0
            
                if mode == 0:
                    scale = trans_imp * 1e15 * input_Q_tot * Qfrac / output_Q_max     
                    # scale = trans_imp/(self.CDet*1e-12) #C_D=3.7pF   
                elif mode == 1:
                    scale = trans_imp * 1e15 * input_Q_tot / output_Q_max

                return scale

            self.pulse_responce_list = [pulse_responce_Charge_Sensitive]
            self.scale = scale_Charge_Sensitive

        elif self.amplifier_parameters['ele_name'] == 'Broad_Band':
            """ Broad Bandwidth Amplifier (Charge Sensitive Amplifier) parameter initialization"""

            mode = "RC"

            def pulse_responce_Broad_Band(t):
                if t < 0: # step function
                    return 0
                
                Broad_Band_Bandwidth = self.amplifier_parameters['Broad_Band_Bandwidth']
                Broad_Band_Imp       = self.amplifier_parameters['Broad_Band_Imp']
                OscBW        = self.amplifier_parameters['OscBW']   
                
                if mode == "scope":
                    tau_C50 = 1.0e-12 * 50.0 * CDet          #Oscil. RC
                    tau_BW = 0.35 / (1.0e9*OscBW) / 2.2      #Oscil. RC
                    tau_scope = math.sqrt(pow(tau_C50,2)+pow(tau_BW,2))

                    return 1/tau_scope * math.exp(-t/tau_scope)

                elif mode == "RC":
                    tau_Broad_Band_RC = 1.0e-12 * Broad_Band_Imp * CDet     #Broad_Band RC
                    tau_Broad_Band_BW = ( 0.35 / (1.0e9*Broad_Band_Bandwidth) / 2.2
                    )    #Broad_Band Tau, Rf*Cf?
                    tau_Broad_Band = math.sqrt(pow(tau_Broad_Band_RC,2)+pow(tau_Broad_Band_BW,2))

                    return 1/tau_Broad_Band * math.exp(-t/tau_Broad_Band)
                
                else:
                    raise NameError(mode,"mode is not defined")
                
            def scale_Broad_Band(output_Q_max, input_Q_tot):
                """Broad Bandwidth Amplifier (Charge Sensitive Amplifier) scale function"""

                if mode == "scope":
                    Broad_Band_Gain = self.amplifier_parameters['Broad_Band_Gain']
                    return Broad_Band_Gain

                elif mode == "RC":
                    Broad_Band_Gain = self.amplifier_parameters['Broad_Band_Gain']
                    R_in = 50
                    return Broad_Band_Gain * R_in
                
            self.pulse_responce_list = [pulse_responce_Broad_Band]
            self.scale = scale_Broad_Band
            

    def fill_amplifier_output(self, currents: list[ROOT.TH1F]):
        for i in range(self.read_ele_num):
            cu = currents[i]
            self.amplified_currents.append(
                _new_histogram(
                    "electronics %s%s"%(self.name, i + 1),
                    "electronics %s"%(self.name),
                    cu.GetNbinsX(),
                    cu.GetXaxis().GetXmin(),
                    cu.GetXaxis().GetXmax(),
                )
            )
            self.amplified_currents[i].Reset()
            values = _convolve_histogram_causal(cu, self.pulse_responce_list)
            _set_hist_contents(self.amplified_currents[i], values)
    
    def set_scope_output(self, currents: list[ROOT.TH1F]):
        for i in range(self.read_ele_num):
            cu = currents[i]
            input_Q_tot = cu.Integral()*cu.GetBinWidth(0)
            output_Q_max = self.amplified_currents[i].GetMaximum()
            self.amplified_currents[i].Scale(self.scale(output_Q_max, input_Q_tot))

    def add_noise(self, seed):
        noise_avg = self.amplifier_parameters["noise_avg"]
        noise_rms = self.amplifier_parameters["noise_rms"]
        ROOT.gRandom.SetSeed(seed)
        for i in range(self.read_ele_num):
            cu = self.amplified_currents[i]
            for j in range(cu.GetNbinsX()):
                noise_height=ROOT.gRandom.Gaus(noise_avg,noise_rms)
                cu.SetBinContent(j,cu.GetBinContent(j)+noise_height)

    def judge_threshold_CFD(self):
        threshold = self.amplifier_parameters["threshold"]
        for i in range(self.read_ele_num):
            cu = self.amplified_currents[i]
            amplitude = max(cu.GetMaximum(), abs(cu.GetMinimum()))
            if amplitude > threshold:
                return
            else:
                self.amplified_currents[i].Reset()

    def read_raw_file(self, raws):
        time_limit = 100e-9
        # TODO: make this match the .tran in the .cir file
        # TODO: the time limit should be consistent with the time limit in gen_signal_scan.py
        for i in range(self.read_ele_num):
            raw = raws[i]
            with open(raw, 'r') as f:
                lines = f.readlines()
                time,volt = [],[]

                for line in lines:
                    time.append(float(line.split()[0]))
                    volt.append(float(line.split()[1])*1e3) # convert V to mV

            self.amplified_currents.append(_new_histogram(
                                "electronics %s"%(self.name)+str(i+1), "electronics %s"%(self.name),
                                int(time_limit/self.time_unit),0,time[-1],))
            # the .raw input is not uniform, so we need to slice the time range
            filled = set()
            for j in range(len(time)):
                k = self.amplified_currents[i].FindBin(time[j])
                self.amplified_currents[i].SetBinContent(k, volt[j])
                filled.add(k)
            # fill the empty bins
            for k in range(1, int(time[-1]/self.time_unit)-1):
                if k not in filled:
                    self.amplified_currents[i].SetBinContent(k, self.amplified_currents[i][k-1])

    def draw_waveform(self, currents, path):
        for i in range(self.read_ele_num):
            fig_name = os.path.join(path, self.name+"No."+str(i+1)+'.pdf')  
            root_name = os.path.join(path, self.name+"No."+str(i+1)+'.root')
            c = ROOT.TCanvas('c','c',1400,1200)
            c.SetMargin(0.2,0.2,0.2,0.1)
            temp_amplified_current = self.amplified_currents[i].Clone()
            temp_current = currents[i].Clone()

            # scale 
            c_min = temp_current.GetMinimum()
            a_min = temp_amplified_current.GetMinimum()
            c_max = temp_current.GetMaximum()
            a_max = temp_amplified_current.GetMaximum()
            c_abs_max = max(abs(c_max), abs(c_min))
            a_abs_max = max(abs(a_max), abs(a_min))
            if c_abs_max == 0 or a_abs_max == 0:
                scale_factor = 1
            else:
                scale_factor = c_abs_max / a_abs_max
            temp_amplified_current.Scale(scale_factor)
            a_min_scaled = temp_amplified_current.GetMinimum()
            a_max_scaled = temp_amplified_current.GetMaximum()

            amplified_noise_floor = 3.0 * self.amplifier_parameters["noise_rms"] * scale_factor
            xmin, xmax = _combined_activity_window(
                [temp_current, temp_amplified_current],
                absolute_thresholds=[0.0, amplified_noise_floor],
            )
            combined_ymin = min(c_min, a_min_scaled)
            combined_ymax = max(c_max, a_max_scaled)

            # 设置直方图显示范围
            frame = ROOT.gPad.DrawFrame(xmin,combined_ymin,xmax,combined_ymax) 
            ROOT.gPad.Modify()
            ROOT.gPad.Update()
            c.Update()

            temp_current.Draw("SAME HIST")

            temp_current.SetLineColor(1)
            temp_current.SetLineWidth(2)
            frame.GetXaxis().SetTitle('Time [s]')
            frame.GetXaxis().CenterTitle()
            frame.GetXaxis().SetTitleSize(0.08)
            frame.GetXaxis().SetLabelSize(0.06)
            frame.GetXaxis().SetNdivisions(5)
            frame.GetXaxis().SetTitleOffset(1)

            frame.GetYaxis().SetTitle('Current [A]')
            frame.GetYaxis().CenterTitle()
            frame.GetYaxis().SetTitleSize(0.08)
            frame.GetYaxis().SetLabelSize(0.06)
            frame.GetYaxis().SetNdivisions(5)
            frame.GetYaxis().SetTitleOffset(1)
            c.Update()

            temp_amplified_current.SetLineWidth(2)   
            temp_amplified_current.SetLineColor(2)
            temp_amplified_current.Draw("SAME HIST")
            c.Update()

            axis = ROOT.TGaxis(
                ROOT.gPad.GetUxmax(), ROOT.gPad.GetUymin(),
                ROOT.gPad.GetUxmax(), ROOT.gPad.GetUymax(),
                combined_ymin/scale_factor, combined_ymax/scale_factor, 505, "+L",)
            axis.SetLineColor(2)
            axis.SetTextColor(2)
            axis.SetLabelColor(2)
            axis.SetTitleColor(2)
            axis.SetLabelFont(42)
            axis.SetTitleFont(42)
            axis.CenterTitle()
            axis.SetTitleSize(0.08)
            axis.SetLabelSize(0.06)
            axis.SetNdivisions(5)
            axis.SetTitleOffset(1)
            axis.SetTitle("Amplitude [mV]")
            axis.Draw("SAME HIST")
            c.Update()
            if temp_amplified_current.GetMaximum() > abs(temp_amplified_current.GetMinimum()):
                legend = ROOT.TLegend(0.45, 0.7, 0.75, 0.85)
            else:
                legend = ROOT.TLegend(0.45, 0.25, 0.75, 0.4)
            legend.AddEntry(temp_current, "original", "l")
            legend.AddEntry(temp_amplified_current, "electronics", "l")
            
            legend.Draw("SAME")
            c.Update()

            c.cd()
            c.SaveAs(fig_name)
            c.SaveAs(root_name)


def main(name):
    '''main function for readout.py to test the output of the given amplifier'''

    my_th1f = ROOT.TH1F("my_th1f", "my_th1f", 1000, 0, 10e-9)
    # input signal: triangle pulse
    for i in range(101, 301):
        my_th1f.SetBinContent(i, -0.05e-6*(300-i)) # A

    ele = Amplifier([my_th1f], name, CDet=30)
    ele.draw_waveform([my_th1f], output(__file__, name))

if __name__ == '__main__':
    import sys
    main(sys.argv[1])
