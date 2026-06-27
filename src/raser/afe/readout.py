#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

'''
Description: 
    Simulate induced current through Broad_Band or Charge_Sensitive amplifier 
@Date       : 2024/09/22 15:24:33
@Author     : Yuhang Tan, Chenxi Fu
@version    : 2.0
'''

import math
import json
import os
import subprocess
import time

import ROOT
ROOT.gROOT.SetBatch(True)

from .ngspice import circuit_has_noise_spectrum
from .ngspice import set_ngspice_input
from .ngspice import set_tmp_cir
from .ngspice import set_tmp_noise_cir
from .noise import load_noise_spectrum
from .noise import resolve_noise_spectrum_path
from .noise import synthesize_noise_from_spectrum
from ..util.math import signal_convolution
from ..util.output import output
from ..util.output import delete_file

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
    _ngspice_noise_spectrum_cache = {}

    def __init__(self, currents: list[ROOT.TH1F], amplifier_name: str, seed = None, CDet = None, is_cut = False):
        self.amplified_currents = []
        self.read_ele_num = len(currents)
        self.time_unit = 10e-12
        # TODO: need to set the time unit corresponding to the oscilloscope or the TDC 
        # TODO: and consistent with the time unit in gen_signal_batch.py

        ele_json = os.getenv("RASER_SETTING_PATH")+"/electronics/" + amplifier_name + ".json"
        ele_cir = os.getenv("RASER_SETTING_PATH")+"/electronics/" + amplifier_name + ".cir"
        self.electronics_dir = os.path.dirname(ele_json)
        use_spice_amplifier = os.getenv("RASER_USE_SPICE_AMPLIFIER", "").lower()
        use_spice_amplifier = use_spice_amplifier in ("1", "true", "yes", amplifier_name.lower())
        if os.path.exists(ele_json) and not use_spice_amplifier:
            with open(ele_json) as f:
                self.amplifier_parameters = json.load(f)
                if self.amplifier_parameters.get("noise_spectrum") is None:
                    sidecar_noise = self.load_sidecar_noise_config(ele_json)
                    if sidecar_noise is not None:
                        self.amplifier_parameters["noise_spectrum"] = sidecar_noise
                self.name = self.amplifier_parameters['ele_name']

            self.amplifier_define(CDet)
            self.fill_amplifier_output(currents)
            self.set_scope_output(currents)
            self.add_noise(seed)
            if is_cut:
                self.judge_threshold_CFD()

        elif os.path.exists(ele_cir):
            self.name = amplifier_name
            input_current_strs = set_ngspice_input(currents)
            time_stamp = time.time_ns()
            pid = os.getpid()
            # stamp and thread name for avoiding file name conflict
            path = output(__file__, self.name)
            use_spectrum_noise = circuit_has_noise_spectrum(ele_cir)
            keep_trnoise = os.getenv("RASER_SPICE_KEEP_TRNOISE", "").lower()
            keep_trnoise = keep_trnoise in ("1", "true", "yes", amplifier_name.lower())
            tmp_cirs, raws = set_tmp_cir(
                self.read_ele_num,
                path,
                input_current_strs,
                ele_cir,
                str(time_stamp)+"_"+str(pid),
                disable_trnoise=use_spectrum_noise and not keep_trnoise,
            )
            for i in range(self.read_ele_num):
                print("Running ngspice for amplifier simulation on electrode No.%d..."%(i+1))
                subprocess.run(
                    ["ngspice", "-b", tmp_cirs[i]],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            self.read_raw_file(raws)
            if use_spectrum_noise:
                self.add_ngspice_noise(ele_cir, path, str(time_stamp)+"_"+str(pid), seed)
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
            CDet = self.amplifier_parameters['CDet']

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
                if (tau_rise == tau_fall):
                    tau_rise *= 0.9

                return tau_fall/(tau_fall+tau_rise) * (math.exp(-t/tau_fall)-math.exp(-t/tau_rise))

            def scale_Charge_Sensitive(output_Q_max, input_Q_tot):
                """ Current Sensitive Amplifier scale function"""
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
                    tau_C50 = 1.0e-12 * 50. * CDet          #Oscil. RC
                    tau_BW = 0.35 / (1.0e9*OscBW) / 2.2      #Oscil. RC
                    tau_scope = math.sqrt(pow(tau_C50,2)+pow(tau_BW,2))

                    return 1/tau_scope * math.exp(-t/tau_scope)

                elif mode == "RC":
                    tau_Broad_Band_RC = 1.0e-12 * Broad_Band_Imp * CDet     #Broad_Band RC
                    tau_Broad_Band_BW = 0.35 / (1.0e9*Broad_Band_Bandwidth) / 2.2    #Broad_Band Tau, Rf*Cf?
                    tau_Broad_Band = math.sqrt(pow(tau_Broad_Band_RC,2)+pow(tau_Broad_Band_BW,2))

                    return 1/tau_Broad_Band * math.exp(-t/tau_Broad_Band)
                
                else:
                    raise NameError(mode,"mode is not defined")
                
            def scale_Broad_Band(output_Q_max, input_Q_tot):
                """ Broad Bandwidth Amplifier (Charge Sensitive Amplifier) scale function"""

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
            self.amplified_currents.append(ROOT.TH1F("electronics %s"%(self.name)+str(i+1), "electronics %s"%(self.name),
                                cu.GetNbinsX(),cu.GetXaxis().GetXmin(),cu.GetXaxis().GetXmax()))
            self.amplified_currents[i].Reset()
            signal_convolution(cu, self.amplified_currents[i], self.pulse_responce_list)
    
    def set_scope_output(self, currents: list[ROOT.TH1F]):
        for i in range(self.read_ele_num):
            cu = currents[i]
            input_Q_tot = cu.Integral()*cu.GetBinWidth(0)
            output_Q_max = self.amplified_currents[i].GetMaximum()
            self.amplified_currents[i].Scale(self.scale(output_Q_max, input_Q_tot))

    def add_noise(self, seed):
        noise_avg = self.amplifier_parameters["noise_avg"]
        noise_rms = self.amplifier_parameters["noise_rms"]
        noise_spectrum = self.amplifier_parameters.get("noise_spectrum")
        if noise_spectrum is not None:
            try:
                self.add_spectrum_noise(noise_spectrum, seed, noise_avg, noise_rms)
                return
            except Exception as exc:
                required = (
                    isinstance(noise_spectrum, dict)
                    and noise_spectrum.get("required", False)
                )
                if required:
                    raise
                print(
                    "Warning: spectral noise generation failed ({}). "
                    "Falling back to Gaussian bin noise.".format(exc)
                )

        ROOT.gRandom.SetSeed(0 if seed is None else int(seed))
        for i in range(self.read_ele_num):
            cu = self.amplified_currents[i]
            for j in range(1, cu.GetNbinsX() + 1):
                noise_height = ROOT.gRandom.Gaus(noise_avg, noise_rms)
                cu.SetBinContent(j, cu.GetBinContent(j) + noise_height)

    def add_spectrum_noise(self, noise_spectrum, seed, noise_avg, noise_rms):
        if isinstance(noise_spectrum, str):
            spectrum_config = {"file": noise_spectrum}
        elif isinstance(noise_spectrum, dict):
            spectrum_config = noise_spectrum
        else:
            raise TypeError("noise_spectrum must be a file path or a dict")

        spectrum_file = spectrum_config.get("file", spectrum_config.get("path"))
        if spectrum_file is None:
            raise ValueError("noise_spectrum requires a file/path field")

        spectrum_file = resolve_noise_spectrum_path(spectrum_file, self.electronics_dir)
        frequencies, density = load_noise_spectrum(
            spectrum_file,
            frequency_column=int(spectrum_config.get("frequency_column", 0)),
            density_column=int(spectrum_config.get("density_column", 1)),
        )
        self.add_spectrum_density_noise(
            frequencies,
            density,
            spectrum_config,
            seed,
            noise_avg,
            noise_rms,
        )

    def add_spectrum_density_noise(
            self,
            frequencies,
            density,
            spectrum_config,
            seed,
            noise_avg,
            noise_rms):

        target_rms = spectrum_config.get("target_rms")
        if spectrum_config.get("normalize_to_noise_rms", False):
            target_rms = noise_rms

        density_type = spectrum_config.get(
            "density_type",
            spectrum_config.get("type", "amplitude"),
        )
        unit_scale = float(spectrum_config.get("unit_scale", 1.0))
        randomize_amplitude = bool(spectrum_config.get("randomize_amplitude", True))
        mean = float(spectrum_config.get("mean", noise_avg))

        base_seed = None if seed is None else int(seed)
        for i in range(self.read_ele_num):
            cu = self.amplified_currents[i]
            channel_seed = None if base_seed is None else base_seed + i
            noise = synthesize_noise_from_spectrum(
                frequencies,
                density,
                cu.GetNbinsX(),
                cu.GetBinWidth(1),
                seed=channel_seed,
                density_type=density_type,
                unit_scale=unit_scale,
                mean=mean,
                target_rms=target_rms,
                min_frequency_hz=_config_float(
                    spectrum_config,
                    "min_frequency_hz",
                    "minimum_frequency_hz",
                    "high_pass_hz",
                    "low_frequency_cutoff_hz",
                ),
                max_frequency_hz=_config_float(
                    spectrum_config,
                    "max_frequency_hz",
                    "maximum_frequency_hz",
                    "low_pass_hz",
                    "high_frequency_cutoff_hz",
                ),
                randomize_amplitude=randomize_amplitude,
            )
            for j, noise_height in enumerate(noise, start=1):
                cu.SetBinContent(j, cu.GetBinContent(j) + float(noise_height))

    def add_ngspice_noise(self, ele_cir, path, label, seed):
        cache_key = (os.path.abspath(ele_cir), os.path.getmtime(ele_cir))
        if cache_key in Amplifier._ngspice_noise_spectrum_cache:
            frequencies, density = Amplifier._ngspice_noise_spectrum_cache[cache_key]
        else:
            noise_tmp_cir, noise_raw = set_tmp_noise_cir(path, ele_cir, label)
            if noise_tmp_cir is None:
                return

            completed = subprocess.run(
                ["ngspice", "-b", noise_tmp_cir],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                if not os.path.exists(noise_raw) or os.path.getsize(noise_raw) == 0:
                    print(
                        "Warning: ngspice noise analysis exited with code {} "
                        "and did not produce {}. No spectral noise was added.".format(
                            completed.returncode,
                            noise_raw,
                        )
                    )
                    return

                frequencies, density = load_noise_spectrum(noise_raw)
                if completed.returncode != 0:
                    print(
                        "Warning: ngspice noise analysis exited with code {} "
                        "but produced a usable noise spectrum. Using {}.".format(
                            completed.returncode,
                            noise_raw,
                        )
                    )
                Amplifier._ngspice_noise_spectrum_cache[cache_key] = (frequencies, density)
            finally:
                delete_file(noise_tmp_cir)
                delete_file(noise_raw)

        self.add_spectrum_density_noise(
            frequencies,
            density,
            self.load_ngspice_noise_config(ele_cir),
            seed,
            0.0,
            0.0,
        )

    def load_ngspice_noise_config(self, ele_cir):
        spectrum_config = {
            "density_type": "amplitude",
            "unit_scale": 1e3,
            "randomize_amplitude": True,
        }

        config_file = os.path.splitext(ele_cir)[0] + ".noise.json"
        if os.path.exists(config_file):
            with open(config_file) as handle:
                spectrum_config.update(json.load(handle))

        return spectrum_config

    def load_sidecar_noise_config(self, ele_json):
        config_file = os.path.splitext(ele_json)[0] + ".noise.json"
        if not os.path.exists(config_file):
            return None
        with open(config_file) as handle:
            spectrum_config = json.load(handle)
        if spectrum_config.get("file") is None and spectrum_config.get("path") is None:
            return None
        return spectrum_config

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
        for i in range(self.read_ele_num):
            raw = raws[i]
            with open(raw, 'r') as f:
                lines = f.readlines()
                time,volt = [],[]

                for line in lines:
                    time.append(float(line.split()[0]))
                    volt.append(float(line.split()[1])*1e3) # convert V to mV

            if not time:
                raise ValueError("No data returned from ngspice raw file: {}".format(raw))

            time_min = time[0]
            time_max = time[-1]
            if time_max <= time_min:
                time_max = time_min + self.time_unit

            n_bins = max(1, int(round((time_max - time_min) / self.time_unit)))
            self.amplified_currents.append(ROOT.TH1F("electronics %s"%(self.name)+str(i+1), "electronics %s"%(self.name),
                                n_bins, time_min, time_max))
            # the .raw input is not uniform, so we need to slice the time range
            filled = set()
            for j in range(len(time)):
                k = self.amplified_currents[i].FindBin(time[j])
                if 1 <= k <= n_bins:
                    self.amplified_currents[i].SetBinContent(k, volt[j])
                    filled.add(k)
            # fill the empty bins
            last_value = 0.0
            for k in range(1, n_bins + 1):
                if k not in filled:
                    self.amplified_currents[i].SetBinContent(k, last_value)
                else:
                    last_value = self.amplified_currents[i].GetBinContent(k)

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

            xmin = min(temp_current.GetXaxis().GetXmin(), temp_amplified_current.GetXaxis().GetXmin())
            xmax = max(temp_current.GetXaxis().GetXmax(), temp_amplified_current.GetXaxis().GetXmax())
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
                combined_ymin/scale_factor, combined_ymax/scale_factor, 505, "+L")
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

    ele = Amplifier([my_th1f], name)
    ele.draw_waveform([my_th1f], output(__file__, name))


def _config_float(config, *keys):
    for key in keys:
        if key in config:
            return float(config[key])
    return None

if __name__ == '__main__':
    import sys
    main(sys.argv[1])
