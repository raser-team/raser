"""Plots of induced currents and collected charges."""

from array import array
import logging

import ROOT
ROOT.gROOT.SetBatch(True)

logger = logging.getLogger(__name__)

ELECTRON_CHARGE = 1.6e-19  # C


def _histogram(name, values, t0, dt):
    histogram = ROOT.TH1F(name, "", len(values), t0, t0 + len(values) * dt)
    for index, value in enumerate(values, start=1):
        histogram.SetBinContent(index, float(value))
    return histogram


def draw_currents(path, t0, dt, current, hole_current, electron_current,
                  gain_hole_current=None, gain_electron_current=None, tag=""):
    """Draw the currents of every electrode, one pdf and one root file each.

    The currents are arrays (electrodes, bins) in A on the time axis that
    starts at `t0` with bins of `dt` [s]; the two of the gain are drawn
    where given.
    """
    for electrode in range(len(current)):
        c=ROOT.TCanvas("c","canvas1",1600,1300)
        c.cd()
        c.Update()
        c.SetLeftMargin(0.25)
        c.SetRightMargin(0.15)
        c.SetBottomMargin(0.17)
        ROOT.gStyle.SetOptStat(ROOT.kFALSE)
        ROOT.gStyle.SetOptStat(0)

        sum_cu = _histogram("charge"+str(electrode+1), current[electrode], t0, dt)
        positive_cu = _histogram("charge+"+str(electrode+1), hole_current[electrode], t0, dt)
        negative_cu = _histogram("charge-"+str(electrode+1), electron_current[electrode], t0, dt)

        sum_cu.GetXaxis().SetNdivisions(510)
        sum_cu.GetYaxis().SetNdivisions(505)
        sum_cu.GetXaxis().SetTitle("Time [s]")
        sum_cu.GetYaxis().SetTitle("Current [A]")
        sum_cu.GetXaxis().SetLabelSize(0.08)
        sum_cu.GetXaxis().SetTitleSize(0.08)
        sum_cu.GetYaxis().SetLabelSize(0.08)
        sum_cu.GetYaxis().SetTitleSize(0.08)
        sum_cu.GetYaxis().SetTitleOffset(1.2)
        sum_cu.SetTitle("")
        sum_cu.SetNdivisions(5)
        sum_cu.Draw("HIST")
        positive_cu.Draw("SAME HIST")
        negative_cu.Draw("SAME HIST")
        sum_cu.Draw("SAME HIST")

        positive_cu.SetLineColor(877)#kViolet-3
        negative_cu.SetLineColor(600)#kBlue
        sum_cu.SetLineColor(418)#kGreen+2

        positive_cu.SetLineWidth(2)
        negative_cu.SetLineWidth(2)
        sum_cu.SetLineWidth(2)
        c.Update()

        if gain_hole_current is not None:
            gain_positive_cu = _histogram(
                "gain_charge+"+str(electrode+1), gain_hole_current[electrode], t0, dt)
            gain_negative_cu = _histogram(
                "gain_charge-"+str(electrode+1), gain_electron_current[electrode], t0, dt)
            gain_positive_cu.Draw("SAME HIST")
            gain_negative_cu.Draw("SAME HIST")
            gain_positive_cu.SetLineColor(617)#kMagneta+1
            gain_negative_cu.SetLineColor(867)#kAzure+7
            gain_positive_cu.SetLineWidth(2)
            gain_negative_cu.SetLineWidth(2)

        legend = ROOT.TLegend(0.5, 0.2, 0.8, 0.5)
        legend.AddEntry(negative_cu, "electron", "l")
        legend.AddEntry(positive_cu, "hole", "l")

        if gain_hole_current is not None:
            legend.AddEntry(gain_negative_cu, "electron gain", "l")
            legend.AddEntry(gain_positive_cu, "hole gain", "l")

        legend.AddEntry(sum_cu, "total", "l")

        legend.SetBorderSize(0)
        legend.SetTextSize(0.08)
        legend.Draw("same")
        c.Update()

        c.SaveAs(path+'/'+tag+"No_"+str(electrode+1)+"electrode"+"_basic_infor.pdf")
        c.SaveAs(path+'/'+tag+"No_"+str(electrode+1)+"electrode"+"_basic_infor.root")
        del c


def charge_collection_strip(path, charge):
    """Draw the net charge [C] of every strip, in electrons, against its number."""
    electrons = array('d', [value / ELECTRON_CHARGE for value in charge])
    x = array('d', range(1, len(electrons) + 1))
    logger.info("Collected charge per electrode (e): %s", list(electrons))
    c1=ROOT.TCanvas("c1","canvas1",1000,1000)
    cce=ROOT.TGraph(len(electrons),x,electrons)
    cce.SetMarkerStyle(3)
    cce.Draw()
    cce.SetTitle("Charge Collection Efficiency")
    cce.GetXaxis().SetTitle("elenumber")
    cce.GetYaxis().SetTitle("charge[Coulomb]")
    c1.SaveAs(path+"/cce.pdf")
    c1.SaveAs(path+"/cce.root")


def charge_collection_pixel(path, charge, x_ele_num, y_ele_num):
    """Draw the net charge [C] of every pixel, in electrons, as a map."""
    electrons = [value / ELECTRON_CHARGE for value in charge]
    c1=ROOT.TCanvas("c1","canvas1",1000,1000)
    cce=ROOT.TH2I("cce", "Charge Collection Efficiency", x_ele_num, 0, x_ele_num, y_ele_num, 0, y_ele_num)
    for i in range(x_ele_num*y_ele_num):
        cce.Fill(i%x_ele_num, i//x_ele_num, electrons[i])
    logger.info("Collected charge per electrode (e): %s", electrons)
    cce.Draw("COLZ")
    cce.SetTitle("Charge Collection Efficiency")
    cce.GetXaxis().SetTitle("x_elenumber")
    cce.GetYaxis().SetTitle("y_elenumber")
    cce.GetZaxis().SetTitle("charge[Coulomb]")
    c1.SaveAs(path+"/cce.pdf")
    c1.SaveAs(path+"/cce.root")
