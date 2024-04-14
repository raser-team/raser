import ROOT
import os
import numpy
import sys
import math

def read_file(file_path,wave_name):

    with open(file_path + '/' + wave_name, 'r') as f:
        
        lines = f.readlines()
        points = lines[6:]
        time, volt = [],[]

        for point in points:
            try:
                time.append(float(point.strip('\n').strip().split(',')[3])*1e9)
                volt.append(float(point.strip('\n').strip().split(',')[4])*1e3)
            except Exception as e:
                pass

    return time,volt

def get_max(time_list,volt_list):

    volt_max = 0.
    time_max = 0.
    index_max = 0
    for i in range(len(volt_list)):
        if(volt_list[i]>volt_max):
            time_max = time_list[i]
            volt_max = volt_list[i]
            index_max = i
    return time_max,volt_max,index_max

def get_baseline(time_list,volt_list,time_win):

    time_start = time_list[0]
    time_end = time_start + time_win
    count = 0.
    total = 0.
    for i in range(len(time_list)):
        if(time_list[i] < time_end):
            total += volt_list[i] 
            count += 1.
    baseline = total/count
    return baseline

def get_charge(time_list,volt_list,baseline):

    volt_cut_baseline_list = []
    for i in range(len(volt_list)):
        volt_cut_baseline_list.append(volt_list[i]-baseline)

    time_max,volt_max,index_max = get_max(time_list,volt_cut_baseline_list)

    time_bin = time_list[1]-time_list[0]
    tmp_integrate = 0.
    
    tmp_index = index_max
    while True:
        if(volt_cut_baseline_list[tmp_index]<0.): break
        tmp_integrate += volt_cut_baseline_list[tmp_index]*time_bin
        tmp_index -= 1
    
    tmp_index = index_max+1
    while True:
        if(volt_cut_baseline_list[tmp_index]<0.): break
        tmp_integrate += volt_cut_baseline_list[tmp_index]*time_bin
        tmp_index += 1

    charge = tmp_integrate*(1e-12)/50/100*(1e15)

    return charge

def main():

    input_name = sys.argv[1]
    path = '/scratchfs/atlas/lizaiyi/data/alpha_readout/' + input_name
    waves = os.listdir(path)
    time,volt = [],[]
    window = 1000

    c = ROOT.TCanvas('c','c',1500,600)
    c.Divide(2,1)
    charge_graph = ROOT.TH1F('charge','charge',100,20,1000)
    volt_graph = ROOT.TH1F('volt',"volt",100,0,1500)

    for wave in waves:

        print(wave)
        time,volt = read_file(path,wave)
        time_max,volt_max,index_max = get_max(time,volt)
        baseline = get_baseline(time,volt,window)
        charge = get_charge(time,volt,baseline)
        if charge > 30 and charge < 1000:
            charge_graph.Fill(charge)
            volt_graph.Fill(volt_max)
    
    charge_graph.GetXaxis().SetTitle('Charge [fC]')
    
    volt_graph.GetXaxis().SetTitle('Volt [mV]')

    c.cd(1)
    charge_graph.Draw()

    c.cd(2)
    volt_graph.Draw()

    c.SaveAs('./output/'+ input_name + '_distribution.pdf')

if __name__ == '__main__':
    main()