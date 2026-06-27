import pandas as pd
import random
import ROOT
import math
import array
import os

def main():

    input_path = 'src/raser/apps/lumi/input/'
    '''
    df = pd.read_excel(os.path.join(input_path, 'lossposition_CEPC.xlsx'))
    df.to_csv(os.path.join(input_path, 'lossposition_CEPC.txt'), sep='\t', index=False)
    
    pos_x, pos_y, pos_z = array.array('d',[999.]), array.array('d',[999.]), array.array('d',[999.])
    px, py, pz = array.array('d',[999.]), array.array('d',[999.]), array.array('d',[999.])
    s_energy = array.array('d',[999.])
    nCount = 0
    
    data_file_root = ROOT.TFile(os.path.join(input_path, 'datafile_p1.root'), "RECREATE")
    tree = ROOT.TTree("electrons", "electrons")

    tree.Branch("pos_x", pos_x, 'pos_x/D')
    tree.Branch("pos_y", pos_y, 'pos_y/D')
    tree.Branch("pos_z", pos_z, 'pos_z/D')
    tree.Branch("px", px, 'px/D')
    tree.Branch("py", py, 'py/D')
    tree.Branch("pz", pz, 'pz/D')
    tree.Branch("s_energy", s_energy, 's_energy/D')

    pos_x_tmp, pos_y_tmp, pos_z_tmp, px_tmp, py_tmp, pz_tmp, s_energy_tmp = [], [], [], [], [], [], []

    with open(os.path.join(input_path, 'lossposition_CEPC.txt'), 'r') as input_file:
         next(input_file)  # Skip the header line
         for line in input_file:
             columns = line.strip().split('\t')
             s = float(columns[0])
             x = float(columns[3])
             y = float(columns[5])
             if s >= 10 and s <= 10.2 and abs(x*1000)>=28*math.cos(51/180*math.pi):
                nCount += 1
                pos_x_tmp.append(round(float(columns[3])*1000, 4))  # mm
                pos_y_tmp.append(round(float(columns[5])*1000, 4))  # mm
                pos_z_tmp.append(round((s-10)*1000, 4))             # mm

                s_energy_tmp.append(round(float(columns[2]), 4))    # GeV

                px_tmp.append(round(float(columns[2]) * float(columns[4]), 4))  # GeV
                py_tmp.append(round(float(columns[2]) * float(columns[6]), 4))  # GeV
                pz_tmp.append(round(math.sqrt(1-float(columns[4])**2-float(columns[6])**2) * float(columns[2]), 4))  # GeV

    print(nCount)

    os.remove(os.path.join(input_path, 'lossposition_CEPC.txt'))

    for i in range(len(s_energy_tmp)):

        pos_x[0] = float(pos_x_tmp[i])
        pos_y[0] = float(pos_y_tmp[i])
        pos_z[0] = float(pos_z_tmp[i])
        s_energy[0] = float(s_energy_tmp[i])
        px[0] = float(px_tmp[i])
        py[0] = float(py_tmp[i])
        pz[0] = float(pz_tmp[i])
        tree.Fill()
    
    data_file_root.Write()
    data_file_root.Close()
    '''
    file = ROOT.TFile(os.path.join(input_path, 'datafile_p1.root'), "READ")
    t = file.Get("electrons")
    
    h2 = ROOT.TH2F("h2", "", 100, -50, 50, 100, -50, 50)
    h1 = ROOT.TH1F("h1", "", 100, -20, 230)
    
    for event in t:
        h2.Fill(event.pos_x, event.pos_y)        
        h1.Fill(event.pos_z)

    c1 = ROOT.TCanvas("c1", "c1", 800, 600)
    c1.SetLeftMargin(0.15)
    c2 = ROOT.TCanvas("c2", "c2", 800, 600)
    c2.SetLeftMargin(0.15)
    
    c1.cd()
    h2.Draw("COLZ")
    h2.GetXaxis().CenterTitle()
    h2.GetXaxis().SetTitleSize(0.06)
    h2.GetXaxis().SetLabelSize(0.04)
    h2.GetXaxis().SetTitleOffset(0.8)
    h2.GetXaxis().SetTitle("Horizontal (mm)")
    h2.GetYaxis().CenterTitle()
    h2.GetYaxis().SetTitleOffset(0.8)
    h2.GetYaxis().SetTitleSize(0.06)
    h2.GetYaxis().SetLabelSize(0.04) 
    h2.GetYaxis().SetTitle("Vertical (mm)")
    h2.SetStats(0)
    
    c2.cd()
    h1.Draw()
    h1.GetXaxis().CenterTitle()
    h1.GetXaxis().SetTitleSize(0.06)
    h1.GetXaxis().SetLabelSize(0.04)
    h1.GetXaxis().SetTitleOffset(0.8)
    h1.GetXaxis().SetTitle("Beam direction (mm)")
    h1.GetYaxis().CenterTitle()
    h1.GetYaxis().SetTitleOffset(0.8)
    h1.GetYaxis().SetTitleSize(0.06)
    h1.GetYaxis().SetLabelSize(0.04) 
    h1.GetYaxis().SetTitle(f"Events / 2.5 mm")
    h1.SetStats(0)
    
    c1.Draw()
    c2.Draw()
    c1.SaveAs('src/raser/apps/lumi/figs/primary_hit_position_XoY.pdf')
    c2.SaveAs('src/raser/apps/lumi/figs/primary_hit_position_z.pdf')