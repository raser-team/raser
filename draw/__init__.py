import os
import ROOT
from . import iv
from . import cv
from . import compare_iv
from . import compare_cv
def main(kwargs):
    label = kwargs['label']

    if label == 'sicar1.1.8':
        input_dir = '/publicfs/atlas/atlasnew/silicondet/itk/raser/wangkeqi/sicar1.1.8'
        output_dir = '/afs/ihep.ac.cn/users/w/wangkeqi/raser/output/fig'
        draw_figure(input_dir, output_dir, label)
    elif label == 'compare_sicar1.1.8_iv':
        iv.main(label)
    elif label == 'compare_sicar1.1.8_cv':
        cv.main(label)
    elif label == 'sicar1.1.8-1':
        input_dir = '/publicfs/atlas/atlasnew/silicondet/itk/raser/wangkeqi/sicar1.1.8'
        output_dir = '/afs/ihep.ac.cn/users/w/wangkeqi/raser/output/fig'
        draw_figure(input_dir, output_dir, label)
    elif label == 'sicar1.1.8-2':
        input_dir = '/publicfs/atlas/atlasnew/silicondet/itk/raser/wangkeqi/sicar1.1.8'
        output_dir = '/afs/ihep.ac.cn/users/w/wangkeqi/raser/output/fig'
        draw_figure(input_dir, output_dir, label)  
    elif label == 'itk_md8_data_v1':
        input_dir = '/publicfs/atlas/atlasnew/silicondet/itk/raser/lizhan/itkmd8/itkmd8data'
        output_dir = '/afs/ihep.ac.cn/users/l/lizhan/disk/scrathfs/raser/output/fig'
        draw_figure(input_dir, output_dir, label,xtitle_iv="Reverse Bias Voltage [V]",ytitle_iv="Current [nA]",
                xtitle_cv="Reverse Bias Voltage [V]",ytitle_cv="Capacitance [pF]",
                    xlowerlimit_iv=0,xupperlimit_iv=700,ylowerlimit_iv=1e-11,yupperlimit_iv=1e-5,ylogscale_iv=0,
                    xlowerlimit_cv=0,xupperlimit_cv=400,ylowerlimit_cv=0,yupperlimit_cv=1e2,ylogscale_cv=0)  
    elif label == 'itk_md8_sim_v1':
        input_dir = '/publicfs/atlas/atlasnew/silicondet/itk/raser/lizhan/itkmd8/itkmd8sim'
        output_dir = '/afs/ihep.ac.cn/users/l/lizhan/disk/scrathfs/raser/output/fig'
        draw_figure(input_dir, output_dir, label,xtitle_iv="Reverse Bias Voltage [V]",ytitle_iv="Current [nA]",
                xtitle_cv="Reverse Bias Voltage [V]",ytitle_cv="Capacitance [pF]",
                    xlowerlimit_iv=0,xupperlimit_iv=700,ylowerlimit_iv=1e-11,yupperlimit_iv=1e-5,ylogscale_iv=0,
                    xlowerlimit_cv=0,xupperlimit_cv=400,ylowerlimit_cv=0,yupperlimit_cv=1e2,ylogscale_cv=0)  
    elif label == 'itk_md8_compare_dataandsim_v1':
        input_dir = '/publicfs/atlas/atlasnew/silicondet/itk/raser/lizhan/itkmd8/comparison'
        output_dir = '/afs/ihep.ac.cn/users/l/lizhan/disk/scrathfs/raser/output/fig'
        cv.main(label)
        iv.main(label)
    elif label == 'itk_atlas18_sim_v1':
        input_dir = '/publicfs/atlas/atlasnew/silicondet/itk/raser/lizhan/atlas18/sim'
        output_dir = '/afs/ihep.ac.cn/users/l/lizhan/disk/scrathfs/raser/output/fig'
        draw_figure(input_dir, output_dir, label,xtitle_iv="Reverse Bias Voltage [V]",ytitle_iv="Current [A]",
            xtitle_cv="Reverse Bias Voltage [V]",ytitle_cv="Capacitance [pF]",
                xlowerlimit_iv=0,xupperlimit_iv=700,ylowerlimit_iv=1e-11,yupperlimit_iv=1e-5,ylogscale_iv=0,
                xlowerlimit_cv=0,xupperlimit_cv=400,ylowerlimit_cv=0,yupperlimit_cv=1e2,ylogscale_cv=0)
    elif label == 'itk_atlas18_data_v1':
        input_dir = '/publicfs/atlas/atlasnew/silicondet/itk/raser/lizhan/atlas18/data'
        output_dir = '/afs/ihep.ac.cn/users/l/lizhan/disk/scrathfs/raser/output/fig'
        draw_figure(input_dir, output_dir, label,xtitle_iv="Reverse Bias Voltage [V]",ytitle_iv="Current [nA]",
                xtitle_cv="Reverse Bias Voltage [V]",ytitle_cv="Capacitance [pF]",
                    xlowerlimit_iv=0,xupperlimit_iv=700,ylowerlimit_iv=1e-11,yupperlimit_iv=1e-5,ylogscale_iv=0,
                    xlowerlimit_cv=0,xupperlimit_cv=400,ylowerlimit_cv=0,yupperlimit_cv=1e2,ylogscale_cv=0) 
    elif label == 'sicar1.1.8-1,sicar1.1.8-2_iv':
        iv.main(label)  
    elif label == 'sicar1.1.8-1,sicar1.1.8-2_cv':
        cv.main(label) 
    elif label == "compare_nju_iv":
        path1="/publicfs/atlas/atlasnew/silicondet/itk/raser/zhaosen/njupin_iv/nju_pin_iv.root"
        path2="./output/2Dresult/simNJUPIN/simIV800.0to800.0.root"
        compare_iv.main(label,path1,path2)
    elif label == "compare_nju_cv":
        path1="/publicfs/atlas/atlasnew/silicondet/itk/raser/zhaosen/njupin_cv/4H-SiC-PIN-cv.root"
        path2="./output/2Dresult/simNJUPIN/simCV500.0to500.0.root"
        compare_cv.main(label,path1,path2)
    elif label == "compare_sim_sicar1.1.8_cv":
        path1="/publicfs/atlas/atlasnew/silicondet/itk/raser/wangkeqi/sicar1.1.8/sicar1.1.8-11_cv.root"
        path2="./output/2Dresult/simsicar1.1.6/simCV500.0to500.0.root"
        compare_cv.main(label,path1,path2)
    elif label == "compare_sicar_cv_1d":
        path1="/publicfs/atlas/atlasnew/silicondet/itk/raser/wangkeqi/sicar1.1.8/iv_cv/sicar1.1.8-8_cv.root"
        path2="./output/field/SICAR-1.1.8/simCV-500.0to0.0.root"
        compare_cv.main(label,path1,path2)
    elif label == "compare_sim_sicar1.1.8_iv":
        path1="/publicfs/atlas/atlasnew/silicondet/itk/raser/wangkeqi/sicar1.1.8/sicar1.1.8-11_iv.root"
        path2="./output/2Dresult/simsicar1.1.6/simIV650.0to650.0.root"
        compare_iv.main(label,path1,path2)
    else: 
        raise NameError(label)
    
def draw_figure(input_dir, output_dir, label,xtitle_iv="Reverse Bias Voltage [V]",ytitle_iv="Current [A]",
                xtitle_cv="Reverse Bias Voltage [V]",ytitle_cv="Capacitance [pF]",
                    xlowerlimit_iv=0,xupperlimit_iv=510,ylowerlimit_iv=1e-11,yupperlimit_iv=1e-5,ylogscale_iv=0,
                    xlowerlimit_cv=0,xupperlimit_cv=399.99,ylowerlimit_cv=0,yupperlimit_cv=1e2,ylogscale_cv=0):

    com_name = []
    for file in os.listdir(input_dir):
        if file.endswith('.root'):
            com_name.append(file)
    for name in com_name:
        if label == 'sicar1.1.8' and not name.startswith('sicar1.1.8'):
            continue
        elif label == 'sicar1.1.8-1' and not name.startswith('sicar1.1.8-1_'):
            continue
        elif label == 'sicar1.1.8-2' and not name.startswith('sicar1.1.8-2_'):
            continue
        name = name.split('.root')[0]

        input_file = os.path.join(input_dir, name + '.root')
        output_file = os.path.join(output_dir, name + '.root')
        pdf_file = os.path.join(output_dir, name + '.pdf')
        png_file = os.path.join(output_dir, name + '.png')

        if name.endswith('iv'):  
            file = ROOT.TFile(input_file, "READ")
            tree = file.Get("myTree")
            graph = ROOT.TGraph()
            
            for i, event in enumerate(tree):
                if label in ['itk_md8_data','itk_atlas18_data']:
                    x = event.Voltage_V
                    x = abs(x)
                    y = event.Current_nA
                    y = abs(y)*1e-9
                elif label == 'itk_atlas18_sim':
                    x = event.Voltage
                    x = abs(x)
                    y = event.Current
                    y = abs(y)*1e-9
                else:
                    x = event.Value
                    x = abs(x)
                    y = event.Reading
                    y = abs(y)
                graph.SetPoint(i, x, y)

            draw_with_options(graph,name,output_file,pdf_file,png_file,xtitle_iv,ytitle_iv,
                              xlowerlimit_iv,xupperlimit_iv,ylowerlimit_iv,yupperlimit_iv,ylogscale_iv)
            #problem: unable to change y limits
            
        if name.endswith('cv'):  
            file = ROOT.TFile(input_file, "READ")
            tree = file.Get("myTree")
            graph = ROOT.TGraph()
            for i, event in enumerate(tree):
                x = event.Voltage
                x = abs(x)
                y = event.Capacitance
                y = abs(y)
                graph.SetPoint(i, x, y)
            
            draw_with_options(graph,name,output_file,pdf_file,png_file,xtitle_cv,ytitle_cv,
                              xlowerlimit_cv,xupperlimit_cv,ylowerlimit_cv,yupperlimit_cv,ylogscale_cv)


def draw_with_options(graph,name,output_file,pdf_file,png_file,xtitle,ytitle,
                      xlowerlimit,xupperlimit,ylowerlimit,yupperlimit,ylogscale):
            graph.SetNameTitle("")
            graph.SetLineWidth(1)
            graph.SetMarkerColor(ROOT.kBlack)
            graph.SetMarkerStyle(24)
            graph.SetMarkerSize(1)

            graph.GetXaxis().SetTitle(xtitle)
            graph.GetXaxis().SetLimits(xlowerlimit,xupperlimit)
            graph.GetXaxis().CenterTitle()
            graph.GetXaxis().SetTitleOffset(1.4)
            graph.GetXaxis().SetTitleSize(0.05)
            graph.GetXaxis().SetLabelSize(0.05)
            graph.GetXaxis().SetNdivisions(505)
            
            graph.GetYaxis().SetLimits(ylowerlimit,yupperlimit)
            graph.GetYaxis().SetTitle(ytitle)
            graph.GetYaxis().CenterTitle()
            graph.GetYaxis().SetTitleOffset(1.8)
            graph.GetYaxis().SetTitleSize(0.05)
            graph.GetYaxis().SetLabelSize(0.05)
            graph.Draw("AP")

            c = ROOT.TCanvas("c","c",500,500)
            c.SetLeftMargin(0.22)
            c.SetBottomMargin(0.16)
            legend = ROOT.TLegend(0.27,0.67,0.62,0.80)
            c.SetGrid()
            c.SetFrameLineWidth(5)

            legend.SetTextSize(0.04)
            legend.AddEntry(graph,name.split('_')[0])

            c.cd()
            c.SetLogy(ylogscale)
            graph.Draw()
            legend.Draw()

            c.SaveAs(output_file)
            c.SaveAs(pdf_file)
            c.SaveAs(png_file)
            del c