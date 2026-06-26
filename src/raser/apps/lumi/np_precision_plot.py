import ROOT
from math import sqrt
import numpy as np
import math

def main():
    
    y_length  = [1, 2, 3, 4, 5]
    bunch_0   = [674, 731, 746, 750, 753]
    bunch_005 = [673, 731, 745, 750, 753]
    bunch_05  = [672, 731, 743, 750, 753]
    bunch_1   = [653, 717, 738, 743, 750]
    bunch_3   = [549, 654, 675, 698, 713]
    bunch_5   = [484, 600, 619, 638, 673]

    c1 = ROOT.TCanvas("c1", "NP", 800, 600)
    c2 = ROOT.TCanvas("c2", "Precision", 800, 600)

    styles = [
               {"color": ROOT.kRed,    "marker": 20, "label": "0 uA"},
               {"color": ROOT.kBlue,   "marker": 21, "label": "0.05 uA"},
               {"color": ROOT.kGreen,  "marker": 22, "label": "0.5 uA"},
               {"color": ROOT.kMagenta,"marker": 23, "label": "1 uA"},
               {"color": ROOT.kRed,    "marker": 24, "label": "3 uA"},
               {"color": ROOT.kBlack,  "marker": 25, "label": "5 uA"}
             ]
 
    c1.cd()
    c1.SetLeftMargin(0.2)
    np_plot = c1.DrawFrame(0, 1600, 6, 2800, "")
    np_plot.GetXaxis().CenterTitle()
    np_plot.GetXaxis().SetTitleOffset(0.8)
    np_plot.GetXaxis().SetTitle("Vertical length (cm)")
    np_plot.GetXaxis().SetTitleSize(0.06)
    np_plot.GetXaxis().SetLabelSize(0.04)
    np_plot.GetYaxis().CenterTitle()
    np_plot.GetYaxis().SetTitle("#it{N}_{#it{d}}")
    np_plot.GetYaxis().SetTitleOffset(1.2)
    np_plot.GetYaxis().SetTitleSize(0.05)
    np_plot.GetYaxis().SetLabelSize(0.04) 
    line_np = ROOT.TLine(0, 2500, 6, 2500)
    line_np.SetLineColor(ROOT.kBlack) 
    line_np.SetLineStyle(2)            
    line_np.SetLineWidth(2)            
    line_np.Draw()

    graphs_np = []
    for idx, data in enumerate([bunch_0, bunch_005, bunch_05, bunch_1, bunch_3, bunch_5]):
        np_list, _ = np_precision_list(data)
        gr = ROOT.TGraph(len(y_length), np.array(y_length, dtype='d'), np.array(np_list, dtype='d'))
        gr.SetMarkerColor(styles[idx]["color"])
        gr.SetMarkerStyle(styles[idx]["marker"])
        gr.SetMarkerSize(1.5)
        gr.SetLineColor(styles[idx]["color"])
        gr.Draw("LP SAME")
        graphs_np.append(gr)
    
    leg_np = ROOT.TLegend(0.6, 0.2, 0.9, 0.5)
    leg_np.SetTextSize(0.04)
    leg_np.SetTextFont(42) 
    for idx, style in enumerate(styles):
        leg_np.AddEntry(graphs_np[idx], style["label"], "lp")
    leg_np.Draw()
    
    c1.Update()
    c1.SaveAs("src/raser/apps/lumi/figs/np_plot.pdf")

    c2.cd()
    c2.SetLeftMargin(0.15)
    precision_plot = c2.DrawFrame(0, 1.8, 6, 2.5, "")
    precision_plot.GetXaxis().CenterTitle()
    precision_plot.GetXaxis().SetTitleOffset(0.8)
    precision_plot.GetXaxis().SetTitle(" Vertical length(cm)")
    precision_plot.GetXaxis().SetTitleSize(0.06)
    precision_plot.GetXaxis().SetLabelSize(0.04)
    precision_plot.GetYaxis().CenterTitle()
    precision_plot.GetYaxis().SetTitle("#nu #times %")
    precision_plot.GetYaxis().SetTitleOffset(1.2)
    precision_plot.GetYaxis().SetTitleSize(0.06)
    precision_plot.GetYaxis().SetLabelSize(0.04) 
    line = ROOT.TLine(0, 2, 6, 2)
    line.SetLineColor(ROOT.kBlack) 
    line.SetLineStyle(2)            
    line.SetLineWidth(2)            
    line.Draw()
    graphs_precision = []

    for idx, data in enumerate([bunch_0, bunch_005, bunch_05, bunch_1, bunch_3, bunch_5]):
        _, precision_list = np_precision_list(data)
        gr = ROOT.TGraph(len(y_length), np.array(y_length, dtype='d'), np.array(precision_list, dtype='d'))
        gr.SetMarkerColor(styles[idx]["color"])
        gr.SetMarkerStyle(styles[idx]["marker"])
        gr.SetMarkerSize(1.5)
        gr.SetLineColor(styles[idx]["color"])
        gr.Draw("LP SAME")
        graphs_precision.append(gr)

    leg_precision = ROOT.TLegend(0.6, 0.6, 0.9, 0.9)
    leg_precision.SetTextSize(0.04)
    leg_precision.SetTextFont(42) 
    for idx, style in enumerate(styles):
        leg_precision.AddEntry(graphs_np[idx], style["label"], "lp")
    leg_precision.Draw()
    
    c2.Update()
    c2.SaveAs("src/raser/apps/lumi/figs/precision_plot.pdf")

def np_precision_list(bunch_list):
    np_list, precision_list = [], []
    for val in bunch_list:
        np = 3.4 * val / (1 - math.exp(-3.4))
        precision = 1 / sqrt(np)*100
        np_list.append(np)
        precision_list.append(precision)
    return np_list, precision_list

if __name__ == "__main__":
    main()
