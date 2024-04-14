import os
import ROOT

def draw_cv(input_dir, output_dir, label):
    com_name = []
    legend_name = []

    for file in os.listdir(input_dir):
        if file.endswith('.root'):
            com_name.append(file)

    c_c = ROOT.TCanvas("c_c", "c_c", 800, 800)
    c_c.SetLeftMargin(0.22)
    c_c.SetBottomMargin(0.16)
    c_c.SetGrid()
    c_c.SetFrameLineWidth(5)
    c_c.SetLogy()
    multigraphs_c = ROOT.TMultiGraph()

    for i in range(len(com_name)):
        name = com_name[i]
        if label == 'sicar1.1.8_cv' and not name.startswith('sicar1.1.8'):
            continue
        elif label == 'sicar1.1.8-1,sicar1.1.8-2_cv' and not (name.startswith('sicar1.1.8-1_')) and not (name.startswith('sicar1.1.8-2_')):
            continue

        name = name.split('.root')[0]

        input_file = os.path.join(input_dir, name + '.root')

        if name.endswith('cv'):
            file = ROOT.TFile(input_file, "READ")
            tree = file.Get("myTree")
            graph = ROOT.TGraph()
            legend_name.append(name.split('_')[0])

            for i, event in enumerate(tree):
                x = event.Voltage
                x = abs(x)
                y = event.Capacitance
                y = abs(y)
                graph.SetPoint(i, x, y)

            graph.SetNameTitle("")
            graph.SetMarkerColor(0+i)
            graph.SetMarkerStyle(24)
            graph.SetMarkerSize(1)
            multigraphs_c.Add(graph)

    multigraphs_c.GetXaxis().SetLimits(0,399.99)
    multigraphs_c.GetXaxis().SetTitle("Reverse Bias Voltage [V]")
    multigraphs_c.GetXaxis().CenterTitle()
    multigraphs_c.GetXaxis().SetTitleOffset(1.4)
    multigraphs_c.GetXaxis().SetTitleSize(0.05)
    multigraphs_c.GetXaxis().SetLabelSize(0.05)
    multigraphs_c.GetXaxis().SetNdivisions(505)
    multigraphs_c.GetYaxis().SetLimits(4,5e2)
    multigraphs_c.GetYaxis().SetRangeUser(4, 5e2)
    multigraphs_c.GetYaxis().SetTitle("Capacitance [pF]")
    multigraphs_c.GetYaxis().CenterTitle()
    multigraphs_c.GetYaxis().SetTitleOffset(1.8)
    multigraphs_c.GetYaxis().SetTitleSize(0.05)
    multigraphs_c.GetYaxis().SetLabelSize(0.05)
    multigraphs_c.Draw("AP")

    max_i = len(legend_name) - 1
    legend_c = ROOT.TLegend(0.52,0.82-0.05*float(max_i),0.87,0.85)
    legend_c.SetTextSize(0.04)

    for i, graph in enumerate(multigraphs_c):
        legend_c.AddEntry(graph, legend_name[i])

    legend_c.Draw()

    file_name_c = label + ".root"
    c_c.SaveAs(os.path.join(output_dir, file_name_c))
    file_name_c = label + ".pdf"
    c_c.SaveAs(os.path.join(output_dir, file_name_c))
    file_name_c = label + ".png"
    c_c.SaveAs(os.path.join(output_dir, file_name_c))


def main(label):
    if label=='itk_md8_compare_dataandsim':
        input_dir = '/publicfs/atlas/atlasnew/silicondet/itk/raser/lizhan/itkmd8/comparison'
        output_dir = '/afs/ihep.ac.cn/users/l/lizhan/disk/scrathfs/raser/output/fig'
    else:
        input_dir = '/publicfs/atlas/atlasnew/silicondet/itk/raser/wangkeqi/sicar1.1.8'
        output_dir = '/afs/ihep.ac.cn/users/w/wangkeqi/raser/output/fig'

    draw_cv(input_dir, output_dir, label)

if __name__ == "__main__":
    main()
