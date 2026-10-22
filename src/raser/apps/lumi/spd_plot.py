import os
import re
import ROOT
from raser.supports.output import output

def main():

    folder_path = output(__file__, "spd")

    z_tot_pos_nx, y_tot_pos_nx = [], []
    z_g_pos_nx, y_g_pos_nx = [], []
    z_em_pos_nx, y_em_pos_nx = [], []
    z_oth_pos_nx, y_oth_pos_nx = [], []

    z_tot_pos_px, y_tot_pos_px = [], []
    z_g_pos_px, y_g_pos_px = [], []
    z_em_pos_px, y_em_pos_px = [], []
    z_oth_pos_px, y_oth_pos_px = [], []

    pattern_nx = re.compile(r"SecondaryParticle_\d+_nx\.txt")
    for file_name in os.listdir(folder_path):
        if pattern_nx.match(file_name):
           print(file_name)
           with open(os.path.join(folder_path, file_name), 'r') as file:
                for line in file:
                    z_tot_pos_nx.append(float(line.split(' ')[1])/1000)
                    y_tot_pos_nx.append(float(line.split(' ')[2]))
           with open(os.path.join(folder_path, file_name), 'r') as file:
                for line in file:
                    if str(line.split(' ')[0]) == 'gamma':
                        z_g_pos_nx.append(float(line.split(' ')[1])/1000)
                        y_g_pos_nx.append(float(line.split(' ')[2]))
                    elif str(line.split(' ')[0]) == 'e-':
                        z_em_pos_nx.append(float(line.split(' ')[1])/1000)
                        y_em_pos_nx.append(float(line.split(' ')[2])) 
                    else:
                        z_oth_pos_nx.append(float(line.split(' ')[1])/1000)
                        y_oth_pos_nx.append(float(line.split(' ')[2])) 
   
    pattern_px = re.compile(r"SecondaryParticle_\d+_px\.txt")
    for file_name in os.listdir(folder_path):
        if pattern_px.match(file_name):
            print(file_name)
            with open(os.path.join(folder_path, file_name), 'r') as file:
                for line in file:
                    z_tot_pos_px.append(float(line.split(' ')[1])/1000)
                    y_tot_pos_px.append(float(line.split(' ')[2]))
            with open(os.path.join(folder_path, file_name), 'r') as file:
                for line in file:
                    if str(line.split(' ')[0]) == 'gamma':
                        z_g_pos_px.append(float(line.split(' ')[1])/1000)
                        y_g_pos_px.append(float(line.split(' ')[2]))
                    elif str(line.split(' ')[0]) == 'e-':
                        z_em_pos_px.append(float(line.split(' ')[1])/1000)
                        y_em_pos_px.append(float(line.split(' ')[2])) 
                    else:
                        z_oth_pos_px.append(float(line.split(' ')[1])/1000)
                        y_oth_pos_px.append(float(line.split(' ')[2]))
    
    print("-31mm plane...")
    print("N_gamma/N_tot:   ", len(z_g_pos_nx)/len(z_tot_pos_nx))
    print("N_ele/N_tot:   ", len(z_em_pos_nx)/len(z_tot_pos_nx))
    print("N_oth/N_tot:   ", len(z_oth_pos_nx)/len(z_tot_pos_nx))
    print("31mm plane...")
    print("N_gamma/N_tot:   ", len(z_g_pos_px)/len(z_tot_pos_px))
    print("N_ele/N_tot:   ", len(z_em_pos_px)/len(z_tot_pos_px))
    print("N_oth/N_tot:   ", len(z_oth_pos_px)/len(z_tot_pos_px))
    
    hist1 = ROOT.TH1F("", "", 100, -1, 5)
    hist2 = ROOT.TH1F("", "", 100, -1, 5)
    hist3 = ROOT.TH1F("", "", 100, -200, 200)
    hist4 = ROOT.TH1F("", "", 100, -200, 200)
    hist5 = ROOT.TH1F("", "", 100, -1, 5)
    hist6 = ROOT.TH1F("", "", 100, -1, 5)
    hist7 = ROOT.TH1F("", "", 100, -200, 200)
    hist8 = ROOT.TH1F("", "", 100, -200, 200)

    for val in z_g_pos_nx:
        hist1.Fill(val)
    for val in z_em_pos_nx:
        hist2.Fill(val)
    for val in y_g_pos_nx:
        hist3.Fill(val)
    for val in y_em_pos_nx:
        hist4.Fill(val)
    for val in z_g_pos_px:
        hist5.Fill(val)
    for val in z_em_pos_px:
        hist6.Fill(val)
    for val in y_g_pos_px:
        hist7.Fill(val)
    for val in y_em_pos_px:
        hist8.Fill(val)
    z_g = 0
    for i in z_g_pos_nx:
        if i<=0.235 and i>=0.225:
           z_g += 1
    z_e = 0
    for i in z_em_pos_nx:
        if i<=0.235 and i>=0.225:
           z_e += 1

    print('detector area gamma:   ',   z_g/len(z_g_pos_nx))
    print('detector area electron:',   z_e/len(z_em_pos_nx))

    draw_spd_dis(
        h1=hist1, h2=hist2,
        pdf_name="z_nx",
        X_label="Beam direction (m)",
        styles={'unit': 'm', 'suffix': 'm', 'label1': '#gamma', 'label2': 'e^{-}'},
        ratio_range_bin=0.06
    )

    draw_spd_dis(
        h1=hist3, h2=hist4,
        pdf_name="y_nx",
        X_label="Vertical (mm)",
        styles={'unit': 'mm', 'suffix': 'mm', 'label1': '#gamma', 'label2': 'e^{-}'},
        ratio_range_bin=4
    )

    draw_spd_dis(
        h1=hist5, h2=hist6,
        pdf_name="z_px",
        X_label="Beam drairection (m)",
        styles={'unit': 'm', 'suffix': 'm', 'label1': '#gamma', 'label2': 'e^{-}'},
        ratio_range_bin=0.06
    )

    draw_spd_dis(
        h1=hist7, h2=hist8,
        pdf_name="y_px",
        X_label="Vertical (mm)",
        styles={'unit': 'mm', 'suffix': 'mm', 'label1': '#gamma', 'label2': 'e^{-}'},
        ratio_range_bin=4
    )

def draw_spd_dis(h1, h2, pdf_name, X_label, styles, ratio_range_bin):
    
    c1 = ROOT.TCanvas("c1", "c1", 800, 600)
    c1.SetLeftMargin(0.15)

    h1.SetLineColor(ROOT.kBlue)  
    h1.SetLineWidth(2)
    h2.SetLineColor(ROOT.kRed)  
    h2.SetLineWidth(2)

    h1.Draw()
    h2.Draw("SAME")

    h1.GetXaxis().SetTitle(X_label)
    h1.GetXaxis().SetTitleSize(0.06)
    h1.GetXaxis().SetLabelSize(0.04)
    h1.GetXaxis().SetTitleOffset(0.8)
    h1.GetXaxis().CenterTitle()
    h1.GetYaxis().SetTitleOffset(1.2)
    h1.GetYaxis().SetTitleSize(0.06)
    h1.GetYaxis().SetLabelSize(0.04) 
    h1.GetYaxis().CenterTitle()
    h1.GetYaxis().SetTitle(f"Events / {ratio_range_bin} {styles['unit']}")
    h1.Scale(1.0/172.0)  # averange 1 primary electrons in PEL areas
    h2.Scale(1.0/172.0)
    h1.SetTitle("") 
    h1.SetStats(0) 

    maxbin1 = h1.GetMaximumBin()
    maxbin_center1 = h1.GetBinCenter(maxbin1)
    maxbin2 = h2.GetMaximumBin()
    maxbin_center2 = h2.GetBinCenter(maxbin2)

    latex = ROOT.TLatex()
    latex.SetTextSize(0.03)
    latex.SetTextFont(42)
    latex.SetTextAlign(11)
    latex.SetNDC(True)
    latex.DrawLatex(0.55, 0.55, f"Max bin center of #gamma : {maxbin_center1:.3f} {styles['suffix']}")
    latex.DrawLatex(0.55, 0.5, f"Max bin center of e^{{-}}: {maxbin_center2:.3f} {styles['suffix']}")

    legend = ROOT.TLegend(0.7, 0.75, 0.85, 0.85)
    legend.AddEntry(h1, styles['label1'], "l")
    legend.AddEntry(h2, styles['label2'], "l")
    legend.Draw()

    c1.SaveAs(f"src/raser/apps/lumi/figs/{pdf_name}.pdf")
