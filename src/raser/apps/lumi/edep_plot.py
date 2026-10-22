import ROOT
import re
import os
import numpy as np
from raser.supports.output import output

def main():

    output_folder = output(__file__, "N0_3_4")
    current_name = os.path.join(output_folder, "event_0", "0_I.txt")
   
    patternI = r'detector_I_pixelEdep.root'
    patternII = r'detector_II_pixelEdep.root'
   
    edep_I, edep_II= [],[]
    t,c = [], []
    
    for i in range(804):
       
        flag = 0
        event_folder = os.path.join(output_folder, f"event_{i}")
       
        for filename in os.listdir(event_folder):
           
            match_I = re.match(patternI, filename)
            match_II = re.match(patternII, filename)

            if match_I:
  
               df = ROOT.RDataFrame("DetectorID", os.path.join(event_folder, filename))
               edep_np_I = df.AsNumpy(["Edep"])["Edep"]
               edep_list_I = edep_np_I.tolist()
               edep_I.append(sum(edep_list_I))
               flag = 1
              
            elif match_II:
  
               df = ROOT.RDataFrame("DetectorID", os.path.join(event_folder, filename))
               edep_np_II = df.AsNumpy(["Edep"])["Edep"]
               edep_list_II = edep_np_II.tolist()
               edep_II.append(sum(edep_list_II))
               flag = 1
               
        if flag == 0:
       
           edep_I.append(0)
           edep_II.append(0)
    
    print(max(edep_I))
    print(max(edep_II))

    with open(current_name, "r") as f:
         lines = f.readlines()
    
         for line in lines[1:1001]:
             
             data = line.strip().split() 
             
             if len(data) >= 2:
            
                 t.append(float(data[0])*1e9)   #ns
                 c.append(float(data[1])*1e6)   #uA

    h1 = ROOT.TH1F("", "", 100, 0, 20)
    h2 = ROOT.TH1F("", "", 100, 0, 20)
    
    for val in edep_I:
        h1.Fill(val)
    for val in edep_II:
        h2.Fill(val)
    
    c1 = ROOT.TCanvas("c1", "C1", 800, 600)
    c2 = ROOT.TCanvas("c2", "C2", 800, 600)
    c1.SetLeftMargin(0.15)
    c2.SetLeftMargin(0.15)
    
    c1.cd()
    h1.Draw()

    subpad = ROOT.TPad("sp", "sp", 0.25, 0.25, 0.75, 0.75)
    subpad.Draw()
    subpad.cd()

    subpad.SetLeftMargin(0.15)
    subpad.SetRightMargin(0.05)
    subpad.SetTopMargin(0.1)
    subpad.SetBottomMargin(0.1)

    f1 = ROOT.TGraph(len(t), np.array(t, 'd'), np.array(c, 'd'))
    f1.SetTitle("")
    f1.SetLineColor(2)
    f1.SetLineWidth(1)
    f1.GetXaxis().SetTitle("Time (ns)")
    f1.GetYaxis().SetTitle("Current (uA)")
    f1.GetXaxis().SetLimits(0.0, 10.0)

    for axis in [f1.GetXaxis(), f1.GetYaxis()]:
        axis.SetTitleSize(0.06)
        axis.SetLabelSize(0.05)
        axis.SetTitleOffset(0.8)
        axis.CenterTitle(True)

    f1.Draw("AL")

    latex = ROOT.TLatex()
    latex.SetTextSize(0.045)
    latex.SetTextFont(42)
    latex.SetNDC(True)
    latex.DrawLatex(0.35, 0.65, "Deposited Energy: 133 keV")

    c1.cd()
    h1.GetXaxis().SetTitle('Deposited Energy (MeV)')
    h1.GetXaxis().SetTitleSize(0.06)
    h1.GetXaxis().SetLabelSize(0.04)
    h1.GetXaxis().SetTitleOffset(0.8)
    h1.GetXaxis().CenterTitle()
    h1.GetYaxis().SetTitle('Events / 0.2 MeV')
    h1.GetYaxis().SetTitleOffset(1.2)
    h1.GetYaxis().SetTitleSize(0.06)
    h1.GetYaxis().SetLabelSize(0.04) 
    h1.GetYaxis().CenterTitle()
    c1.SaveAs(f"src/raser/apps/lumi/figs/Edep_I.pdf")
    
    c2.cd()
    h2.Draw()
    h2.GetXaxis().SetTitle('Deposited Energy (MeV)')
    h2.GetXaxis().SetTitleSize(0.06)
    h2.GetXaxis().SetLabelSize(0.04)
    h2.GetXaxis().SetTitleOffset(0.8)
    h2.GetXaxis().CenterTitle()
    h2.GetYaxis().SetTitle('Events / 0.2 MeV')
    h2.GetYaxis().SetTitleOffset(1.2)
    h2.GetYaxis().SetTitleSize(0.06)
    h2.GetYaxis().SetLabelSize(0.04) 
    h2.GetYaxis().CenterTitle()
    c2.SaveAs("src/raser/apps/lumi/figs/Edep_II.pdf")   

if __name__ == '__main__':
    main()      
