
# -*- encoding: utf-8 -*-
'''
Description:  NIEL calculator   
@Date       : 2021/11/23 18:46:00
@Author     : yangtao
@version    : 1.0
'''

import ROOT
import math
import sys
from array import array


def usage():
    sys.stdout.write('''
NAME
    NIEL_calculator.py

SYNOPSIS

    ./NIEL_calculator.py  [particle_type] [particle_energy (MeV)]

AUTHOR
    Tao Yang  <yangtao@ihep.ac.cn>

DATE
    Nov 2021
\n''')


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        return usage()
    particle_type = args[0]
    particle_energy = float(args[1])
    NIEL_calculator(particle_type,particle_energy)


def NIEL_calculator(particle_type, particle_energy):
 
    n = 7
    x_proton_energy = array( 'd',[55,65,76,85,95,105,115])
    y_D = array( 'd',[1.7147368421,1.5800000000,1.4684210526,1.3789473684,1.3073684211,1.2442105263,1.2021052632])

    g_proton_Huhtinen = ROOT.TGraph(n,x_proton_energy,y_D)
    
    g_proton_Huhtinen.SetTitle("")
    g_proton_Huhtinen.SetMarkerSize(3)
    g_proton_Huhtinen.SetMarkerStyle(29)
    g_proton_Huhtinen.SetMarkerColor(4)

    f = ROOT.TF1("f","pol4",50.0,120.0)
    g_proton_Huhtinen.Fit(f,"NR+")
    f.SetNpx(7000)

    target_D = f.Eval(particle_energy)

    f.SetLineColor(1)
    f.SetLineStyle(2)

    print("\n************************************\n")
    print("\nProton Energy: "+str(particle_energy)+" MeV")
    print("NIEL facotr:" +str(target_D)+" 95 MeV mb")
    print("\n************************************\n")

    g_proton_target = ROOT.TGraph(1,array("d",[particle_energy]),array("d",[target_D]))
    g_proton_target.SetTitle("")
    g_proton_target.SetMarkerSize(3)
    g_proton_target.SetMarkerStyle(3)
    g_proton_target.SetMarkerColor(2)

    mg = ROOT.TMultiGraph()
    mg.Add(g_proton_Huhtinen)
    mg.Add(g_proton_target)

    mg.GetXaxis().SetTitle("Energy [MeV]")
    mg.GetYaxis().SetTitle("D(E) [95 MeV mb]")
    mg.GetXaxis().SetTitleOffset(1.2)
    mg.GetXaxis().SetTitleSize(0.05)
    mg.GetXaxis().SetLabelSize(0.05)
    mg.GetXaxis().SetNdivisions(510)
    mg.GetYaxis().SetTitleOffset(1.1)
    mg.GetYaxis().SetTitleSize(0.05)
    mg.GetYaxis().SetLabelSize(0.05)
    mg.GetYaxis().SetNdivisions(505)
    mg.GetXaxis().CenterTitle()
    mg.GetYaxis().CenterTitle()
    mg.GetXaxis().SetRangeUser(50,120.0)

    latex = ROOT.TLatex()
    latex.SetNDC(1)
    latex.SetTextSize(0.038)

    c = ROOT.TCanvas( '', '', 700, 500 )
    c.SetTopMargin(0.10)
    c.SetBottomMargin(0.14)
    c.SetLeftMargin(0.12)
    c.SetGrid()
    c.cd()
    mg.Draw("AP")
    f.Draw("SAME")
    latex.DrawLatex(0.5,0.6,"Target energy: "+str(particle_energy)+ "MeV")
    latex.DrawLatex(0.5,0.55,"Target NIEL: "+str(target_D))
    c.SaveAs("proton_Huhtinen.pdf")


if __name__ == '__main__':
    main()
