import os
import re
from scipy.interpolate import interp1d
import numpy as np
from collections import defaultdict
import ROOT
from raser.supports.output import create_path
from raser.supports.paths import project_path

def main(output_folder, fig_name):

    patternI = r'(\d+)_I\.txt'
    patternII = r'(\d+)_II\.txt'
    
    global z_list, y_list
    z_list = list(range(2))
    y_list = list(range(-3, 3))
    
    
    dic_I = defaultdict(list)
    dic_II = defaultdict(list)
    
    for j in y_list:
        for k in z_list:
            key_I = f"detector_I_{j}_{k}"
            key_II = f"detector_II_{j}_{k}"
            _ = dic_I[key_I]
            _ = dic_II[key_II]
    
    for i in range(804):
        event_folder = os.path.join(output_folder, f"event_{i}")
        print(i)
        for filename in os.listdir(event_folder):
            match_I = re.match(patternI, filename)
            match_II = re.match(patternII, filename)
            
            if match_I:
                ht = match_I.group(1)
                with open(os.path.join(event_folder, filename), 'r') as I_file:
                    lines = I_file.readlines()           
                for y in y_list:
                    for z in z_list:
                        for ln, line in enumerate(lines):                         
                            if f'detector_I_{y}_{z}:\n' == line:  
                                ln_prep = ln+1
                                ln_post = ln+1001
                                fc_10ns=int(10)*1e-9
                                for ele in range(ln_prep, ln_post):
                                    columns = lines[ele].strip().split() 
                                    fc = float(columns[0])+int(ht)*1e-9  
                                    sc = float(columns[1])
                                    dic_I[f'detector_I_{y}_{z}'].append([fc, sc])
                                fc_10ns+=fc
                                dic_I[f'detector_I_{y}_{z}'].append([fc_10ns, 0.0])   
     
            elif match_II:   
                    ht = match_II.group(1)  
                    with open(os.path.join(event_folder, filename), 'r') as II_file:
                        lines = II_file.readlines()
                    for y in y_list:
                        for z in z_list:
                            for ln, line in enumerate(lines):
                                if f'detector_II_{y}_{z}:\n' == line:
                                    ln_prep = ln+1
                                    ln_post = ln+1001
                                    fc_10ns=int(10)*1e-9
                                    for ele in range(ln_prep, ln_post):
                                        columns = lines[ele].strip().split() 
                                        fc = float(columns[0])+int(ht)*1e-9  
                                        sc = float(columns[1])
                                    fc_10ns+=fc
                                    dic_II[f'detector_II_{y}_{z}'].append([fc_10ns, 0.0])
    
    
    figure_data_file = project_path("lumi", f"{fig_name}.txt")
    create_path(figure_data_file.parent)
    with open(figure_data_file, 'w') as file:
        file.write("0.0 0.0\n")
        for l in range(len(dic_I['detector_I_0_1'])):
            file.write(f"{float(dic_I['detector_I_0_1'][l][0])*1e3} {float(dic_I['detector_I_0_1'][l][1])*1e6}\n")
        file.write("1 0.0\n")       
    
    t,c = [], []
    with open(figure_data_file, 'r') as file:
         for line in file:
             columns = line.strip().split()
             t.append(float(columns[0]))
             c.append(float(columns[1]))
    
    t_np = np.array(t, dtype='float64')  
    c_np = np.array(c, dtype='float64')
    
    c1 = ROOT.TCanvas('c1','c1', 1600, 600)
    c1.SetLeftMargin(0.15)
    f1 = ROOT.TGraph(len(t_np), t_np, c_np)
    f1.SetTitle(' ')
    f1.SetLineColor(4)
    f1.SetLineWidth(1)
    f1.GetXaxis().SetTitle('Time (ms)')
    f1.GetXaxis().SetLimits(0.0, 0.1)
    f1.GetXaxis().CenterTitle()
    f1.GetXaxis().SetTitleSize(0.06)
    f1.GetXaxis().SetLabelSize(0.04)
    f1.GetXaxis().SetTitleOffset(0.8)
    f1.GetYaxis().SetTitle('Current (uA)')
    f1.GetYaxis().CenterTitle()
    f1.GetYaxis().SetTitleSize(0.06)
    f1.GetYaxis().SetLabelSize(0.04) 
    f1.GetYaxis().SetTitleOffset(0.4)
    f1.Draw('AL')
    c1.SaveAs(f'src/raser/apps/lumi/figs/{fig_name}.pdf')
