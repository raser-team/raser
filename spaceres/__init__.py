import sys
import os
#sys.path.insert(0, sys.path[0]+"/../")

import ROOT
import time
import subprocess

from . import telescope as tlcp
#from . import test
from particle.g4simulation import Particles
from particle.geometry import R3dDetector
from current.cal_current import CalCurrentPixel

def main(kwargs):
    label = kwargs['label']
    if label == "-h":
        print("taichu_v1:   ","first version of telescope simulation")
        print("taichu_v2:   ","second version of telescope simulation")
    elif label.startswith("taichu_v1"):
        #paths = ['det_name=Taichu3', 'parfile=readjson/detector.json', 'geant4_model=pixel_detector', 'geant4_parfile=readjson/absorber.json', 'pixel_detector']
        dset = Setting() #read label.json instead of inputting path
        my_d = R3dDetector(dset) #remain the same
        my_f = 0
        my_g4p = Particles(my_d, dset) #remove my_f
        my_charge = CalCurrentPixel(my_d,my_f,my_g4p)
        if label.endswith("draw_charge"):
            draw_charge(my_charge)
        my_telescope = tlcp.telescope(my_d,my_charge) 
        #tlcp.main(my_d)  
    elif label.startswith("taichu_v2"):
        #virtual object
        class MyObject:
            pass
        #output 
        res = []
        psize = []
        N = 25
        MaxSize = 25.
        for i in range(N):
            t_my_d = MyObject()
            t_my_d.seedcharge = 100
            t_my_d.p_x = MaxSize*(i+1)/N
            t_my_d.p_y = MaxSize*(i+1)/N
            t_my_d.p_z = 200.
            t_my_d.lt_z = [20000.,60000.,100000.,140000.,180000.,220000.]
            psize.append(t_my_d.p_x)
            res.append(tlcp.main(t_my_d))
        
        graph = ROOT.TGraph()
        for i in range(len(psize)):
            graph.SetPoint(i,psize[i],res[i])
        
        canvas = ROOT.TCanvas("canvas", "TGraph", 800, 600)
        graph.SetMarkerStyle(ROOT.kFullCircle)
        graph.GetYaxis().SetTitle("Resolution [um]")
        graph.GetYaxis().CenterTitle()  
        graph.GetXaxis().SetTitle("Pixel Size [um]")
        graph.GetXaxis().CenterTitle()  
        
        legend = ROOT.TLegend(0.27,0.67,0.62,0.80)
        legend.SetTextSize(0.04)
        legend.AddEntry(graph,label)
        
        canvas.SetGrid() 
        
        graph.Draw("APL")
        legend.Draw()

        canvas.Draw()
        Name = "Res vs size"
        now = time.strftime("%Y_%m%d_%H%M")
        path = os.path.join("output/fig", str(now),'' )
        """ If the path does not exit, create the path"""
        if not os.access(path, os.F_OK):
            os.makedirs(path) 
        canvas.SaveAs(path+Name+".png")
    elif label.startswith("acts_v1"):
        python_script = "raser/spaceres/telescope_simulation.py"  

        result = subprocess.run(["python3", python_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if result.returncode == 0:
            print(f"Script '{python_script}' executed successfully.")
        else:
            print(f"Script '{python_script}' failed with return code:", result.returncode)

        stdout_output = result.stdout
        stderr_output = result.stderr

        print("Standard Output:")
        print(stdout_output)

        print("Standard Error:")
        print(stderr_output)
    else:
        raise NameError(label)
    
def draw_charge(my_charge):
    path = os.path.join("output", "pixel",)
    create_path(path) 
    c=ROOT.TCanvas("c","canvas1",1000,1000)
    c.cd()
    c.Update()
    c.SetLeftMargin(0.12)
    # c.SetTopMargin(0.12)
    c.SetRightMargin(0.12)
    c.SetBottomMargin(0.14)
    ROOT.gStyle.SetOptStat(ROOT.kFALSE)
    ROOT.gStyle.SetOptStat(0)

    my_charge.sum_charge.GetXaxis().SetNdivisions(510)
    my_charge.sum_charge.GetYaxis().SetNdivisions(505)
    my_charge.sum_charge.GetXaxis().SetTitle("X")
    my_charge.sum_charge.GetYaxis().SetTitle("Y")

    my_charge.sum_charge.Draw("lego")
    c.Update()
    c.SaveAs(path+"/Pixel_charge.pdf")
    c.SaveAs(path+"/Pixel_charge.root")
