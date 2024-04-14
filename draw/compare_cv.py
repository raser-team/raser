
import ROOT
import os
def compare_cv(label,path1,path2):    
    folder_path="./output/draw"
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    
    file1 = ROOT.TFile(path1)
    tree1 = file1.Get("myTree")

    # 创建第一个图形
    canvas = ROOT.TCanvas("canvas", "Canvas", 1600, 1200)

    # 创建一个TGraph对象来存储第一个ROOT文件中的数据
    graph1 = ROOT.TGraph(tree1.GetEntries())

    # 从树中获取变量数据并添加到TGraph对象中
    for i, event in enumerate(tree1):
        graph1.SetPoint(i, event.Voltage, event.Capacitance)

    # 设置第一个数据点的标记样式和颜色
    graph1.SetMarkerStyle(20)
    graph1.SetMarkerColor(ROOT.kBlue)
    graph1.SetMarkerSize(0.5)
    graph1.GetXaxis().SetTitle("Voltage/v")
    graph1.GetYaxis().SetTitle("CAP/pF")
    # 打开第二个ROOT文件
    file2 = ROOT.TFile(path2)
    tree2 = file2.Get("SicarTestCV")

    # 创建一个TGraph对象来存储第二个ROOT文件中的数据
    graph2 = ROOT.TGraph(tree2.GetEntries())

    # 从树中获取变量数据并添加到TGraph对象中
    for i, event in enumerate(tree2):
        graph2.SetPoint(i, event.voltage, event.CAP)

    # 设置第二个数据点的标记样式和颜色
    graph2.SetMarkerStyle(21)
    graph2.SetMarkerColor(ROOT.kRed)
    graph2.SetMarkerSize(0.5)
    
    graph2.GetXaxis().SetTitle("Voltage/v")
    graph2.GetYaxis().SetTitle("CAP/pF")
    
    canvas = ROOT.TCanvas("canvas", "Canvas", 1600, 1200)
    graph1.SetTitle("{}_SimulateVSexperiment".format(label))
    graph1.Draw("AP")
    graph2.Draw("P")

    # 创建图例
    legend = ROOT.TLegend(0.7, 0.7, 0.9, 0.9)
    legend.AddEntry(graph1, "experiment", "p")
    legend.AddEntry(graph2, "simulate", "p")
    legend.Draw()
    
    # 显示图形
    
    canvas.Update()
    canvas.SaveAs("./output/draw/compare_{}_ex.root".format(label))
def main(label,path1,path2):
    compare_cv(label,path1,path2)

if __name__ == "__main__":
    main(label,path1,path2)