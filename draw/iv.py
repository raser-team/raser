import os
import ROOT

def draw_iv(input_dir, output_dir, label):
    com_name = []
    legend_name = []

    for file in os.listdir(input_dir):
        if file.endswith('.root'):
            com_name.append(file)
    
    c_i = ROOT.TCanvas("c_i", "c_i", 800, 800)
    c_i.SetLeftMargin(0.22)
    c_i.SetBottomMargin(0.16)
    c_i.SetGrid()
    c_i.SetFrameLineWidth(5)
    multigraphs_i = ROOT.TMultiGraph()

    for i in range(len(com_name)):
        name = com_name[i]
        if label == 'sicar1.1.8' and not name.startswith('sicar1.1.8'):
            continue
        elif label == 'sicar1.1.8-1,sicar1.1.8-2_iv' and not (name.startswith('sicar1.1.8-1_')) and not (name.startswith('sicar1.1.8-2_')):
            continue

        name = name.split('.root')[0]

        input_file = os.path.join(input_dir, name + '.root')

        if name.endswith('iv'):
            file = ROOT.TFile(input_file, "READ")
            tree = file.Get("myTree")
            graph1 = ROOT.TGraph()
            legend_name.append(name.split('_')[0])   
            for i, event in enumerate(tree):
                x = event.Value
                x = abs(x)
                y = event.Reading
                y = abs(y)
                graph1.SetPoint(i, x, y)

            graph1.SetNameTitle("")
            graph1.SetMarkerColor(0+i)
            graph1.SetMarkerStyle(24)
            graph1.SetMarkerSize(1)
            multigraphs_i.Add(graph1)

    multigraphs_i.GetXaxis().SetTitle("Reverse Bias Voltage [V]")
    multigraphs_i.GetXaxis().SetLimits(0,510)
    multigraphs_i.GetXaxis().CenterTitle()
    multigraphs_i.GetXaxis().SetTitleOffset(1.4)
    multigraphs_i.GetXaxis().SetTitleSize(0.05)
    multigraphs_i.GetXaxis().SetLabelSize(0.05)
    multigraphs_i.GetXaxis().SetNdivisions(505)
    multigraphs_i.GetYaxis().SetLimits(1e-11,1e-5)
    multigraphs_i.GetYaxis().SetTitle("Current [A]")
    multigraphs_i.GetYaxis().CenterTitle()
    multigraphs_i.GetYaxis().SetTitleOffset(1.8)
    multigraphs_i.GetYaxis().SetTitleSize(0.05)
    multigraphs_i.GetYaxis().SetLabelSize(0.05)
    multigraphs_i.Draw("AP")

    max_i = len(legend_name) - 1
    legend_i = ROOT.TLegend(0.52,0.82-0.05*float(max_i),0.87,0.85)
    legend_i.SetTextSize(0.04)

    for i, graph1 in enumerate(multigraphs_i):
        legend_i.AddEntry(graph1, legend_name[i])
  
    legend_i.Draw()

    file_name_i = label + "_iv.root"
    c_i.SaveAs(os.path.join(output_dir, file_name_i))
    file_name_i = label + "_iv.pdf"
    c_i.SaveAs(os.path.join(output_dir, file_name_i))
    file_name_i = label + "_iv.png"
    c_i.SaveAs(os.path.join(output_dir, file_name_i))

def main(label):
    if label=='itk_md8_compare_dataandsim':
        input_dir = '/publicfs/atlas/atlasnew/silicondet/itk/raser/lizhan/itkmd8/comparison'
        output_dir = '/afs/ihep.ac.cn/users/l/lizhan/disk/scrathfs/raser/output/fig'
    else:
        input_dir = '/publicfs/atlas/atlasnew/silicondet/itk/raser/wangkeqi/sicar1.1.8'
        output_dir = '/afs/ihep.ac.cn/users/w/wangkeqi/raser/output/fig'

    draw_iv(input_dir, output_dir, label)

if __name__ == "__main__":
    main()
