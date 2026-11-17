'''
Description:  wavefrom_stats.py
@Date       : 2025
@Author     : Chenxi Fu
@version    : 1.0
'''


import os
from array import array
from pathlib import Path

import ROOT

from raser.core.reconstruction.event import CFD_LABEL
from raser.core.reconstruction.event import remove_none


def fit_data_normal(histo,x_min,x_max):
    """ Fit data distribution """
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
    """ Fit data distribution """
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

class WaveformStatistics:
    def __init__(
        self,
        my_d,
        threshold,
        amplitude_threshold,
    ):
        det_model = my_d.det_model.lower()
        if det_model == 'planar' or det_model == 'lgad':
            my_d.read_ele_num = 1
            self.pitch_x = my_d.l_x
            self.pitch_y = my_d.l_y
        elif 'strip' in det_model:
            my_d.read_ele_num = my_d.read_ele_num
            self.pitch_x = my_d.p_x
            self.pitch_y = my_d.l_y
        elif 'pixel' in det_model:
            my_d.read_ele_num = my_d.x_ele_num * my_d.y_ele_num
            self.pitch_x = my_d.p_x
            self.pitch_y = my_d.p_y
        else:
            raise ValueError("Unsupported detector model for waveform statistics: {}".format(my_d.det_model))

        # TODO: establish a better method to get the coordinate of the electrode
        self.detector = my_d
        self.threshold = threshold
        self.amplitude_threshold = amplitude_threshold
        self.data = {}
        self.waveforms = [[] for i in range(my_d.read_ele_num)]

    def draw(self, output_path, tag, vis=False):
        if tag is None:
            raise ValueError("Waveform statistics output tag must be explicit")
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)
        self.output_path = str(output_path)

        if vis == True:
            for j in range(self.detector.read_ele_num):
                canvas = ROOT.TCanvas("canvas", "Canvas", 800, 600)
                multigraph = ROOT.TMultiGraph("mg","")
                count = 0
                for waveform in self.waveforms[j]:
                    if count > 100:
                        break
                    x = [float(i[0]) for i in waveform]
                    y = [float(i[1]) for i in waveform]
                    graph = ROOT.TGraph(len(x), array('f', x), array('f', y))
                    multigraph.Add(graph)
                    count += 1
                multigraph.Draw("APL")
                canvas.SaveAs(os.path.join(self.output_path, "waveform_electrode_{}.pdf".format(j)))
                canvas.SaveAs(os.path.join(self.output_path, "waveform_electrode_{}.png".format(j)))

        self.time_resolution_fit(self.data["ToA"], "ToA", tag)
        self.time_resolution_fit(self.data[CFD_LABEL], CFD_LABEL, tag)
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
        self.gravity_center_error_fit(self.data["gravity_center_amplitude_error"], "gravity_center_amplitude_error", tag,)
        self.gravity_center_error_fit(self.data["gravity_center_charge_error"], "gravity_center_charge_error", tag)
        self.ita_calibration(self.data["gravity_center_ToT"], self.data["original_x"], self.pitch_x, "ita_calibration_ToT", tag,)
        self.ita_calibration(self.data["gravity_center_amplitude"], self.data["original_x"], self.pitch_x, "ita_calibration_amplitude", tag,)
        self.ita_calibration(self.data["gravity_center_charge"], self.data["original_x"], self.pitch_x, "ita_calibration_charge", tag,)
    
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
        if model == CFD_LABEL and len(data) >= 20:
            sorted_data = sorted(data)
            x2_min = sorted_data[int(0.02 * (len(sorted_data) - 1))]
            x2_max = sorted_data[int(0.98 * (len(sorted_data) - 1))]
            n2_bin = 30
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
        except (IndexError, ValueError):
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
            histo.Fill(new_original_x[i]/pitch_x - round(new_original_x[i]/pitch_x), new_data[i]- round(new_data[i]),)

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

