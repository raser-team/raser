'''
Description:  wavefrom_stats.py
@Date       : 2025
@Author     : Chenxi Fu
@version    : 1.0
'''


import os
import re
import json
from array import array

import ROOT

from ..device import build_device as bdv
from ..util.output import output
from ..util.math import is_number, fit_data_normal, fit_data_landau

CFD = 0.5 # partition
#TODO: get threshold and CFD from electronics setting

class InputWaveform():
    """
    ToA : time of arrival
    ToT : time over threshold
    amplitude : peak amplitude for charge sensitive preamp
    charge : total charge for current sensitive preamp
    ToR : time of ratio (CFD)
    """
    def __init__(self, input_entry, threshold, amplitude_threshold, read_ele_num, pitch_x, pitch_y, CFD=CFD):
        self.waveforms = [None for _ in range(read_ele_num)]
        self.read_ele_num = read_ele_num
        self.pitch_x = pitch_x
        self.pitch_y = pitch_y
        self.CFD = CFD
        self.peak_time = [0 for i in range(read_ele_num)]
        self.ToA = [0 for i in range(read_ele_num)]
        self.ToT = [0 for i in range(read_ele_num)]
        self.amplitude = [0 for i in range(read_ele_num)] # for charge sensitive pre amp
        self.charge = [0 for i in range(read_ele_num)] # for current sensitive pre amp
        self.ToR = [0 for i in range(read_ele_num)]
        self.threshold = threshold
        self.amplitude_threshold = amplitude_threshold

        par_in = input_entry.par_in
        par_out = input_entry.par_out
        self.original_x = (par_in[0]+par_out[0])/2

        for i in range(read_ele_num):
            # only available for strip detector
            self.waveforms[i] = eval(f"input_entry.amplified_waveform_{i}")
            self.amplitude[i], self.peak_time[i] = get_amplitude(self.waveforms[i])
            if self.amplitude[i] < self.threshold:
                self.amplitude[i] = 0
                self.ToA[i] = None
                self.ToT[i] = 0
                self.charge[i] = 0
                self.ToR[i] = None
            else:
                self.ToA[i] = get_ToA(self.waveforms[i], self.threshold, self.peak_time[i])
                self.ToT[i] = get_ToT(self.waveforms[i], self.threshold, self.peak_time[i])
                self.charge[i] = get_charge(self.waveforms[i])
                self.ToR[i] = get_ToR(self.waveforms[i], CFD, self.peak_time[i])

        self.get_total_data()

    def get_total_data(self):
        self.data = {}
        if max(self.amplitude) < self.amplitude_threshold:
            self.data["ToA"] = None
            self.data["ToT"] = None
            self.data["amplitude"] = None
            self.data["charge"] = None
            self.data["ToR"] = None
            self.data["gravity_center_ToT"] = None
            self.data["gravity_center_amplitude"] = None
            self.data["gravity_center_charge"] = None
            self.data["cluster_size_ToT"] = 0
            self.data["cluster_size_amplitude"] = 0
            self.data["cluster_charge"] = 0
            self.data["gravity_center_ToT_error"] = None
            self.data["gravity_center_amplitude_error"] = None
            self.data["gravity_center_charge_error"] = None
        elif self.read_ele_num == 1:
            self.data["ToA"] = self.ToA[0]
            self.data["ToT"] = self.ToT[0]
            self.data["amplitude"] = self.amplitude[0]
            self.data["charge"] = self.charge[0]
            self.data["ToR"] = self.ToR[0]
            self.data["gravity_center_ToT"] = 0 # No spacial resolution
            self.data["gravity_center_amplitude"] = 0
            self.data["gravity_center_charge"] = 0
            self.data["cluster_size_ToT"] = 1
            self.data["cluster_size_amplitude"] = 1
            self.data["cluster_charge"] = 1
            self.data["gravity_center_ToT_error"] = 0
            self.data["gravity_center_amplitude_error"] = 0
            self.data["gravity_center_charge_error"] = 0
        else:
            # assume strip, one dimensional spacial resolution
            self.data["ToA"] = get_conjoined_time(self.ToA) # TODO: conjoint measurement
            self.data["ToT"] = get_total_amp(self.ToT, 10e-9)
            self.data["amplitude"] = get_total_amp(self.amplitude, self.amplitude_threshold)
            self.data["charge"] = get_total_amp(self.charge, 1e5)
            self.data["ToR"] = get_conjoined_time(self.ToR) # TODO: conjoint measurement
            self.data["gravity_center_ToT"], self.data["cluster_size_ToT"] = get_gravity_center_and_cluster_size(self.ToT, 10e-9) # TODO: assign a proper value for all DAQ systems
            self.data["gravity_center_amplitude"], self.data["cluster_size_amplitude"] = get_gravity_center_and_cluster_size(self.amplitude, self.amplitude_threshold)
            self.data["gravity_center_charge"], self.data["cluster_charge"] = get_gravity_center_and_cluster_size(self.charge, 1e5) # TODO: assign a proper value for all DAQ systems

            if self.data["gravity_center_ToT"] != None:
                self.data["gravity_center_ToT_error"] = self.data["gravity_center_ToT"] - self.original_x/self.pitch_x
            else:
                self.data["gravity_center_ToT_error"] = None
            if self.data["gravity_center_amplitude"] != None:
                self.data["gravity_center_amplitude_error"] = self.data["gravity_center_amplitude"] - self.original_x/self.pitch_x
            else:
                self.data["gravity_center_amplitude_error"] = None
            if self.data["gravity_center_charge"] != None:
                self.data["gravity_center_charge_error"] = self.data["gravity_center_charge"] - self.original_x/self.pitch_x
            else:
                self.data["gravity_center_charge_error"] = None

        self.data["original_x"] = self.original_x

def get_ToA(hist, threshold, peak_time_bin):
    for i in range(peak_time_bin, 0, -1):
        content = hist.GetBinContent(i)
        if abs(content) < threshold:
            return hist.GetBinCenter(i)
    return None

def get_ToT(hist, threshold, peak_time_bin):
    start = None
    for i in range(peak_time_bin, 0, -1):
        content = abs(hist.GetBinContent(i))
        if content < threshold:
            start = hist.GetBinCenter(i)
            break
    if start is None:
        return 0.0
    end = None
    for i in range(peak_time_bin, hist.GetNbinsX() + 1):
        content = abs(hist.GetBinContent(i))
        if content < threshold:
            end = hist.GetBinCenter(i)
            break
    if end is None:
        return 0.0
    return end - start

def get_amplitude(hist):
    max_val = 0.0
    peak_bin = 0
    for i in range(1, hist.GetNbinsX() + 1):
        content = abs(hist.GetBinContent(i))
        if content > max_val:
            max_val = content
            peak_bin = i
    return max_val, peak_bin

def get_charge(hist):
    charge = 0.0
    for i in range(1, hist.GetNbinsX() + 1):
        charge += abs(hist.GetBinContent(i))
    return charge

def get_ToR(hist, CFD, peak_time_bin):
    amplitude = abs(hist.GetBinContent(peak_time_bin))
    target = amplitude * CFD
    for i in range(peak_time_bin, 0, -1):
        content = abs(hist.GetBinContent(i))
        if content > target:
            return hist.GetBinCenter(i)
    return None

def get_conjoined_time(time_list):
    # TODO: conjoint measurement
    new_list = remove_none(time_list)
    if len(new_list) == 0:
        return None
    return min(new_list)

def get_total_amp(amp_list, amp_thres):
    max_amp = max(amp_list)
    i_max = amp_list.index(max_amp)
    if max_amp == 0:
        return None
    seeds = set()
    for i in range(len(amp_list)):
        if amp_list[i] > amp_thres:
            seeds.add(i)
    if len(seeds) == 0:
        return None
    new_seeds = set()
    for i in seeds:
        new_seeds.add(i)
        if i > 0 and amp_list[i-1] > 0:
            new_seeds.add(i-1)
        if i < len(amp_list) - 1 and amp_list[i+1] > 0:
            new_seeds.add(i+1)
    return sum([amp_list[i] for i in new_seeds])

def get_gravity_center_and_cluster_size(amp_list, amp_thres):
    max_amp = max(amp_list)
    i_max = amp_list.index(max_amp)
    if max_amp == 0:
        return None, 0
    seeds = set()
    for i in range(len(amp_list)):
        if amp_list[i] > amp_thres:
            seeds.add(i)
    if len(seeds) == 0:
        return None, 0
    new_seeds = set()
    for i in seeds:
        new_seeds.add(i)
        if i > 0 and amp_list[i-1] > 0:
            new_seeds.add(i-1)
        if i < len(amp_list) - 1 and amp_list[i+1] > 0:
            new_seeds.add(i+1)
    return sum([i * amp_list[i] for i in new_seeds]) / sum(amp_list[i] for i in new_seeds), len(new_seeds)

def remove_none(list):
    new_list = []
    for i in list:
        if i == None:
            continue
        new_list.append(i)
    return new_list

class WaveformStatistics():
    def __init__(self, input_path, my_d, threshold, amplitude_threshold, output_path, vis=False):
        if my_d.det_model == 'planar' or my_d.det_model == 'lgad':
            my_d.read_ele_num = 1
            pitch_x = my_d.l_x
            pitch_y = my_d.l_y
        elif my_d.det_model == 'strip':
            my_d.read_ele_num = my_d.read_ele_num
            pitch_x = my_d.p_x
            pitch_y = my_d.l_y
        elif my_d.det_model == 'pixel':
            my_d.read_ele_num = my_d.x_ele_num * my_d.y_ele_num
            pitch_x = my_d.p_x
            pitch_y = my_d.p_y

        # TODO: establish a better method to get the coordinate of the electrode
        self.data = {}
        self.waveforms = [[] for i in range(my_d.read_ele_num)]

        self.output_path = output_path

        files = os.listdir(input_path)
        files.sort()

        tag = str(my_d.voltage)+str(my_d.irradiation_flux)+str(my_d.g4experiment)+str(my_d.amplifier)

        for file in files:
            #if tag not in file:
            #    continue
            
            path = os.path.join(input_path, file)
            file_pointer = ROOT.TFile(path, "READ")
            tree = file_pointer.Get("tree")
            n = tree.GetEntries()
            for i in range(n):
                tree.GetEntry(i) 
                iw = InputWaveform(tree, threshold, amplitude_threshold, my_d.read_ele_num, pitch_x, pitch_y)
                self.fill_data(iw.data)
                if vis == True:
                    for j in range(my_d.read_ele_num):
                        self.waveforms[j].append(iw.waveforms[j])

            print("read {n} events from {file}".format(n=n, file=file))
            file_pointer.Close()

        if vis == True:
            for j in range(my_d.read_ele_num):
                canvas = ROOT.TCanvas("canvas", "Canvas", 800, 600)
                multigraph = ROOT.TMultiGraph("mg","")
                count = 0
                for waveform in (self.waveforms[j]):
                    if count > 100:
                        break
                    x = [float(i[0]) for i in waveform]
                    y = [float(i[1]) for i in waveform]
                    graph = ROOT.TGraph(len(x), array('f', x), array('f', y))
                    multigraph.Add(graph)
                    count += 1
                multigraph.Draw("APL")
                canvas.SaveAs(os.path.join(output_path, "waveform_electrode_{}.pdf".format(j)))
                canvas.SaveAs(os.path.join(output_path, "waveform_electrode_{}.png".format(j)))

        self.time_resolution_fit(self.data["ToA"], "ToA", tag)
        self.time_resolution_fit(self.data["ToR"], "ToR", tag)
        self.amplitude_fit(self.data["charge"], "charge", tag)
        self.amplitude_fit(self.data["amplitude"], "amplitude", tag)
        self.amplitude_fit(self.data["ToT"], "ToT", tag)
        self.gravity_center_fill(self.data["gravity_center_ToT"], "gravity_center_ToT", tag)
        self.gravity_center_fill(self.data["gravity_center_amplitude"], "gravity_center_amplitude", tag)
        self.gravity_center_fill(self.data["gravity_center_charge"], "gravity_center_charge", tag)
        self.cluster_size_fill(self.data["cluster_size_ToT"], "cluster_size_ToT", tag)
        self.cluster_size_fill(self.data["cluster_size_amplitude"], "cluster_size_amplitude", tag)
        self.cluster_size_fill(self.data["cluster_charge"], "cluster_size_charge", tag)
        self.gravity_center_error_fit(self.data["gravity_center_ToT_error"], "gravity_center_ToT_error", tag)
        self.gravity_center_error_fit(self.data["gravity_center_amplitude_error"], "gravity_center_amplitude_error", tag)
        self.gravity_center_error_fit(self.data["gravity_center_charge_error"], "gravity_center_charge_error", tag)
        self.ita_calibration(self.data["gravity_center_ToT"], self.data["original_x"], pitch_x, "ita_calibration_ToT", tag)
        self.ita_calibration(self.data["gravity_center_amplitude"], self.data["original_x"], pitch_x, "ita_calibration_amplitude", tag)
        self.ita_calibration(self.data["gravity_center_charge"], self.data["original_x"], pitch_x, "ita_calibration_charge", tag)
    
    def fill_data(self, data):
        for key in data:
            try:
                self.data[key].append(data[key])
            except KeyError:
                self.data[key] = []
                self.data[key].append(data[key])

    def time_resolution_fit(self, input_data, model, tag):
        data = remove_none(input_data)
        try:
            x2_min = min(data)
            x2_max = sorted(data)[int(len(data))-1]
        except ValueError:
            print("No valid data for "+model)
            x2_min = 0
            x2_max = 0
        n2_bin = 100
        histo=ROOT.TH1F("","",n2_bin,x2_min,x2_max)
        for i in range(0,len(data)):
            histo.Fill(data[i])
        fit_func_1,_,_,sigma,sigma_error=fit_data_normal(histo,x2_min,x2_max)# in nanosecond
        sigma=sigma*1e12 # in picosecond
        sigma_error=sigma_error*1e12

        c1 = ROOT.TCanvas("c1","c1",200,10,800,600)
        ROOT.gStyle.SetOptStat(0)
        c1.SetGrid()
        c1.SetLeftMargin(0.2)
        c1.SetTopMargin(0.12)
        c1.SetBottomMargin(0.2)

        histo.GetXaxis().SetTitle(model+" [s]")
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

        # Legend setting
        leg = ROOT.TLegend(0.75, 0.6, 0.85, 0.8)
        leg.AddEntry(fit_func_1,"Fit","L")
        leg.AddEntry(histo,"Sim","L")
        # Draw
        histo.Draw()
        fit_func_1.Draw("same")
        leg.Draw("same")
        # Text set
        tex = ROOT.TLatex()
        tex.SetNDC(1)
        tex.SetTextFont(43)
        tex.SetTextSize(25)
        #tex.DrawLatexNDC(0.65, 0.7, "CFD=0.5")
        tex.DrawLatexNDC(0.65, 0.6, "#sigma = %.3f #pm %.3f ps"%(sigma,sigma_error))
        # Save
        c1.SaveAs(self.output_path+'/'+tag+"_"+model+".pdf")
        c1.SaveAs(self.output_path+'/'+tag+"_"+model+".C")

    def amplitude_fit(self, input_data, model, tag):
        data = remove_none(input_data)
        try:
            x2_min = min(data)
            x2_max = sorted(data)[int(len(data))-1]
        except ValueError:
            print("No valid data for "+model)
            x2_min = 0
            x2_max = 0
        n2_bin = 100
        histo=ROOT.TH1F("","",n2_bin,x2_min,x2_max)
        for i in range(0,len(data)):
            histo.Fill(data[i])
        fit_func_1,mean,mean_error,sigma,sigma_error=fit_data_landau(histo,x2_min,x2_max)

        c1 = ROOT.TCanvas("c1","c1",200,10,800,600)
        ROOT.gStyle.SetOptStat(0)
        c1.SetGrid()
        c1.SetLeftMargin(0.2)
        c1.SetTopMargin(0.12)
        c1.SetBottomMargin(0.2)

        histo.GetXaxis().SetTitle(model+" [a.u.]")
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
        histo.SetLineWidth(2)

        # Legend setting
        leg = ROOT.TLegend(0.75, 0.6, 0.85, 0.8)
        leg.AddEntry(fit_func_1,"Fit","L")
        leg.AddEntry(histo,"Sim","L")
        # Draw
        histo.Draw()
        fit_func_1.Draw("same")
        leg.Draw("same")
        # Text set
        tex = ROOT.TLatex()
        tex.SetNDC(1)
        tex.SetTextFont(43)
        tex.SetTextSize(25)
        tex.DrawLatexNDC(0.65, 0.6, "%.3g #pm %.3g a.u."%(mean,sigma))
        # Save
        c1.SaveAs(self.output_path+'/'+tag+"_"+model+".pdf")
        c1.SaveAs(self.output_path+'/'+tag+"_"+model+".C")

    def gravity_center_fill(self, input_data, model, tag):
        data = remove_none(input_data)
        try:
            x2_min = min(data)
            x2_max = max(data)
        except IndexError:
            print("No valid data for "+model)
            return
        
        n2_bin = 10*40 # TODO: temp hard code for strip
        histo=ROOT.TH1F("","",n2_bin,x2_min,x2_max)
        for i in range(0,len(data)):
            histo.Fill(data[i])

        c1 = ROOT.TCanvas("c1","c1",200,10,800,600)
        ROOT.gStyle.SetOptStat(0)
        c1.SetGrid()
        c1.SetLeftMargin(0.2)
        c1.SetTopMargin(0.12)
        c1.SetBottomMargin(0.2)

        histo.GetXaxis().SetTitle(model)
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

        # Legend setting
        leg = ROOT.TLegend(0.75, 0.6, 0.85, 0.8)
        leg.AddEntry(histo,"Sim","L")
        
        histo.Draw()
        leg.Draw("same")
        # Save
        c1.SaveAs(self.output_path+'/'+tag+"_"+model+".pdf")
        c1.SaveAs(self.output_path+'/'+tag+"_"+model+".C")

    def cluster_size_fill(self, input_data, model, tag):
        data = remove_none(input_data)
        histo=ROOT.TH1I("","",11,0,11)
        for i in range(0,len(data)):
            histo.Fill(data[i])

        c1 = ROOT.TCanvas("c1","c1",200,10,800,600)
        ROOT.gStyle.SetOptStat(0)
        c1.SetGrid()
        c1.SetLeftMargin(0.2)
        c1.SetTopMargin(0.12)
        c1.SetBottomMargin(0.2)

        histo.GetXaxis().SetTitle(model)
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

        # Legend setting
        leg = ROOT.TLegend(0.75, 0.6, 0.85, 0.8)
        leg.AddEntry(histo,"Sim","L")
        
        histo.Draw()
        leg.Draw("same")
        # Save
        c1.SaveAs(self.output_path+'/'+tag+"_"+model+".pdf")
        c1.SaveAs(self.output_path+'/'+tag+"_"+model+".C")

    def gravity_center_error_fit(self, input_data, model, tag):
        data = remove_none(input_data)
        try:
            mid = sorted(data)[int(len(data)/2)]
        except IndexError:
            print("No valid data for "+model)
            return
        x2_min = mid-1
        x2_max = mid+1
        n2_bin = 100
        histo=ROOT.TH1F("","",n2_bin,x2_min,x2_max)
        for i in range(0,len(data)):
            histo.Fill(data[i])
        fit_func_1,_,_,sigma,sigma_error=fit_data_normal(histo,x2_min,x2_max)
        sigma=sigma
        sigma_error=sigma_error

        c1 = ROOT.TCanvas("c1","c1",200,10,800,600)
        ROOT.gStyle.SetOptStat(0)
        c1.SetGrid()
        c1.SetLeftMargin(0.2)
        c1.SetTopMargin(0.12)
        c1.SetBottomMargin(0.2)

        histo.GetXaxis().SetTitle(model)
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

        # Legend setting
        leg = ROOT.TLegend(0.75, 0.6, 0.85, 0.8)
        leg.AddEntry(fit_func_1,"Fit","L")
        leg.AddEntry(histo,"Sim","L")
        # Draw
        histo.Draw()
        fit_func_1.Draw("same")
        leg.Draw("same")
        # Text set
        tex = ROOT.TLatex()
        tex.SetNDC(1)
        tex.SetTextFont(43)
        tex.SetTextSize(25)
        #tex.DrawLatexNDC(0.65, 0.7, "CFD=0.5")
        tex.DrawLatexNDC(0.65, 0.6, "#sigma = %.3f #pm %.3f"%(sigma,sigma_error))
        # Save
        c1.SaveAs(self.output_path+'/'+tag+"_"+model+".pdf")
        c1.SaveAs(self.output_path+'/'+tag+"_"+model+".C")

    def ita_calibration(self, data, original_x, pitch_x, model, tag):
        print(len(data),len(original_x))
        new_data = []
        new_original_x = []
        for i in range(len(data)):
            if data[i] == None:
                continue
            new_data.append(data[i])
            new_original_x.append(original_x[i])

        print(len(new_data),len(new_original_x))

        x_min = -0.5
        x_max = 0.5
        y_min = 0.5
        y_max = -0.5
        n_x = 20
        n_y = 20
        histo=ROOT.TH2F("","",n_x,x_min,x_max,n_y,y_min,y_max)
        for i in range(0,len(new_data)):
            histo.Fill(new_original_x[i]/pitch_x - round(new_original_x[i]/pitch_x), new_data[i]- round(new_data[i]))

        histo.GetXaxis().SetTitle("Original x")
        histo.GetYaxis().SetTitle("Reconstructed x")
        histo.GetXaxis().SetTitleOffset(1.2)
        histo.GetXaxis().SetTitleSize(0.07)
        histo.GetXaxis().SetLabelSize(0.05)
        histo.GetXaxis().SetNdivisions(505)
        histo.GetYaxis().SetTitleOffset(1.1)
        histo.GetYaxis().SetTitleSize(0.07)
        histo.GetYaxis().SetLabelSize(0.05)
        histo.GetYaxis().SetNdivisions(505)
        histo.GetXaxis().CenterTitle()
        histo.GetYaxis().CenterTitle()

        c1 = ROOT.TCanvas("c1","c1",200,10,800,1000)
        ROOT.gStyle.SetOptStat(0)
        c1.SetGrid()
        c1.SetLeftMargin(0.2)
        c1.SetTopMargin(0.12)
        c1.SetBottomMargin(0.2)

        histo.Draw("COLZ")
        # Save
        c1.SaveAs(self.output_path+'/'+tag+"_"+model+".pdf")
        c1.SaveAs(self.output_path+'/'+tag+"_"+model+".C")


def main(kwargs):
    det_name = kwargs['det_name']
    my_d = bdv.Detector(det_name)
    if kwargs['voltage'] != None:
        my_d.voltage = kwargs['voltage']
    if kwargs['irradiation'] != None:
        my_d.irradiation_flux = float(kwargs['irradiation'])
    if kwargs['g4experiment'] != None:
        my_d.g4experiment = kwargs['g4experiment']
    if kwargs['amplifier'] != None:
        my_d.amplifier = kwargs['amplifier']
    if kwargs['daq'] != None:
        my_d.daq = kwargs['daq']
   
    daq_json = os.getenv("RASER_SETTING_PATH")+"/daq/" + my_d.daq + ".json"
    with open(daq_json) as f:
        daq_dict = json.load(f)
        threshold = daq_dict['threshold']
        amplitude_threshold = daq_dict['amplitude_threshold']

    tct = kwargs['tct']
    if tct != None:
        input_path = "output/tct/" + det_name + "/" + tct
    else:
        input_path = "output/signal/" + det_name + "/batch"

    output_path = output(__file__, det_name)
    WaveformStatistics(input_path, my_d, threshold, amplitude_threshold, output_path)
