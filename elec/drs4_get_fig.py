#!/usr/bin/env python3

import ROOT
import numpy

def read_file(file_path,file_name):
    with open(file_path + '/' + file_name) as f:
        lines = f.readlines()
        time,volt = [],[]

        for line in lines:
            time.append(float(line.split()[0])*1e9)
            volt.append(float(line.split()[1]))

    time = numpy.array(time,dtype='float64')
    volt = numpy.array(volt,dtype='float64')

    return time,volt

def main():
    file_path = 'fig/'
    file_name = 'drs4_analog.raw'
    com_name=file_name.split('.')[0]
    fig_name=file_path + com_name + '.pdf'
    time,volt = [],[]

    time,volt = read_file(file_path,file_name)
    length = len(time)

    ROOT.gROOT.SetBatch()    
    c = ROOT.TCanvas('c','c',700,600)
    f1 = ROOT.TGraph(length,time,volt)
    f1.SetTitle(' ')

    f1.SetLineColor(2)
    f1.SetLineWidth(2)

    f1.GetXaxis().SetTitle('Time [ns]')
    f1.GetXaxis().SetLimits(0,5)
    f1.GetXaxis().CenterTitle()
    f1.GetXaxis().SetTitleSize(0.05)
    f1.GetXaxis().SetTitleOffset(0.8)

    f1.GetYaxis().SetTitle('Voltage [V]')
    f1.GetYaxis().SetLimits(0,-1)
    f1.GetYaxis().CenterTitle()
    f1.GetYaxis().SetTitleSize(0.05)
    f1.GetYaxis().SetTitleOffset(0.93)

    c.cd()
    f1.Draw('AL')
    c.SaveAs(fig_name)
    print("figure  has been saved in " , fig_name)

if __name__ == '__main__':
    main()
    
