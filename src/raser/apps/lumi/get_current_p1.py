import os
import array
import time
import re
import multiprocessing
import ROOT
from . import cflm_p1
from raser.core.device import build_device as bdv
from raser.core.field import devsim_field as devfield
from raser.core.current import cal_current as ccrt
from raser.supports.output import output
from raser.supports.paths import component_path
import json

def main(output_path):
    
    geant4_json = component_path('g4experiment', 'cflm_p1.json')
    with open(geant4_json) as f:
         g4_dic = json.load(f)

    detector_json = component_path('detector', g4_dic['DetModule'])
    with open(detector_json) as q:
         det_dic = json.load(q)

    det_name = det_dic['det_name']
    my_d = bdv.Detector(det_name)
    voltage = det_dic['bias']['voltage']

    print(my_d.device)
    print(voltage)

    my_f = devfield.DevsimField(my_d.device, my_d.dimension, voltage, det_dic['read_out_contact'], 0)
    
    def worker_function(queue, lock, i, j, l, output_path):
       
        time, current = [], []

        try:
           result_message = "Execution completed successfully"
           my_g4p = cflm_p1.cflmPixelG4Particles(my_d, i, j, l)
           if my_g4p.HitFlag == 0:
               print("No secondary particles hit the detector")
           else:
                print(f'detector_{l}_{i}_{j}')
                if l=="I":
                   my_current = ccrt.CalCurrentG4P(my_d, my_f, my_g4p, 0)
                   time, current = save_current_single_file(my_current, g4_dic, det_dic['read_out_contact'], i, j, l, output_path)
                   if len(current) != 0:
                      with open(os.path.join(output_path, f"{g4_dic['CurrentName'].split('.')[0]}_I.txt"), 'a') as current_file:                      
                           current_file.write(f"detector_{l}_{i}_{j}:"+'\n')
                           for t, c in zip(time, current):
                               current_file.write(f"{t} {c}\n")
                elif l=="II":
                   my_current = ccrt.CalCurrentG4P(my_d, my_f, my_g4p, 0)
                   time, current = save_current_single_file(my_current, g4_dic, det_dic['read_out_contact'], i, j, l, output_path)
                   if len(current) != 0:
                      with open(os.path.join(output_path, f"{g4_dic['CurrentName'].split('.')[0]}_II.txt"), 'a') as current_file:                      
                           current_file.write(f"detector_{l}_{i}_{j}:"+'\n')
                           for t, c in zip(time, current):
                               current_file.write(f"{t} {c}\n")


        except Exception as e:
           result_message = f"Error: {e}"
        with lock:
           queue.put(result_message)
  
    lock = multiprocessing.Lock()
    queue = multiprocessing.Queue()
    
    dividedAreaZIndex = []
    for k in range(2):
        dividedAreaZIndex.append(k)
    dividedAreaYIndex = []
    for b in range(-3, 3):
        dividedAreaYIndex.append(b)
    
    for l in ('I', 'II'):
        for i in dividedAreaYIndex:  
            for j in dividedAreaZIndex:
                p = multiprocessing.Process(target=worker_function, args=(queue, lock, i, j, l, output_path))
                p.start()
                p.join()
                while not queue.empty():
                    output_info = queue.get() 
                    print("队列输出:", output_info)
                    if output_info is None:
                        print("警告: worker_function 返回了 None,可能发生了错误!")   
    del my_f

def save_current_single_file(my_current, g4_dic, read_ele_num, p, q, n, output_path):
 
    time_pwl, current_pwl = [], []
    
    time = array.array('d', [999.])
    current = array.array('d', [999.])
    print(os.path.join(output_path, g4_dic['CurrentName']))
    fout = ROOT.TFile(os.path.join(output_path, g4_dic['CurrentName']), "RECREATE")
    t_out = ROOT.TTree("tree", "signal")
    t_out.Branch("time", time, "time/D")
    for i in range(len(read_ele_num)):
        t_out.Branch("current"+str(i), current, "current"+str(i)+"/D")
        for j in range(my_current.n_bin):
            current[0]=my_current.sum_cu[i].GetBinContent(j)
            time[0]=j*my_current.t_bin
            t_out.Fill()
    t_out.Write()
    fout.Close()
   
    file = ROOT.TFile(os.path.join(output_path, g4_dic['CurrentName']), "READ")
    tree = file.Get("tree")

    for i in range(tree.GetEntries()):
       tree.GetEntry(i)
       time_pwl.append(tree.time)
       current_pwl.append(tree.current0)

    if not all(x == 0.0 for x in current_pwl):
       return time_pwl, current_pwl
    else:
       return [], []
