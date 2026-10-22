import os
import re
from scipy.interpolate import interp1d
import numpy as np
from collections import defaultdict
from raser.supports.output import output

global z_list, y_list
z_list = list(range(2))
y_list = list(range(-3, 3))

def main():

    output_folder = output(__file__, "N0_3_4")
    patternI = r'(\d+)_I\.txt'
    patternII = r'(\d+)_II\.txt'

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
                                ln_post = ln+201
                                fc_10ns=int(10)*1e-9
                                for ele in range(ln_prep, ln_post):
                                    columns = lines[ele].strip().split() 
                                    fc = float(columns[0])+int(ht)*1e-9  
                                    sc = float(columns[1])
                                    dic_II[f'detector_II_{y}_{z}'].append([fc, sc])
                                fc_10ns+=fc
                                dic_II[f'detector_II_{y}_{z}'].append([fc_10ns, 0.0])   
    
    print("Finish saving data and processing....")

    dic_process(dic_I, 'I')
    dic_process(dic_II, 'II')                            

    I_sample_res = sampling(dic_I, 'I')
    II_sample_res = sampling(dic_II, 'II')
    tot_sample_res = I_sample_res+II_sample_res

    print('Total sample value in 1ms at Detector I:      ', sum(I_sample_res))
    print('Total sample value in 1ms at Detector II:     ', sum(II_sample_res))
    print('Total sample value in 1ms at Detector Total:  ', sum(tot_sample_res))

def dic_process(dic, label):
    for p in y_list:
        for q in z_list:
            if len(dic[f'detector_{label}_{p}_{q}'])==0:
               dic[f'detector_{label}_{p}_{q}'].append([0.0, 0.0])
               dic[f'detector_{label}_{p}_{q}'].append([1e-3, 0.0])
            elif [0.0, 0.0] in dic[f'detector_{label}_{p}_{q}']:
                 dic[f'detector_{label}_{p}_{q}'].append([1e-3, 0.0])
                 dic[f'detector_{label}_{p}_{q}'].sort(key=lambda x: x[0])
            else:
                 dic[f'detector_{label}_{p}_{q}'].append([0.0, 0.0])
                 dic[f'detector_{label}_{p}_{q}'].append([1e-3, 0.0])
                 dic[f'detector_{label}_{p}_{q}'].sort(key=lambda x: x[0])
   
def sampling(dic, label):
    sample_res = []
    for p in y_list:
        for q in z_list:
            tmp_t, tmp_c = [], []
            sum_c=0
            for ele in dic[f'detector_{label}_{p}_{q}']:
                tmp_t.append(ele[0])
                tmp_c.append(ele[1])
            f = interp1d(tmp_t, tmp_c)
            sample_point = np.linspace(0, 1e-3, int(1e7))
            sample_c = f(sample_point)
            sum_c = np.sum(sample_c)
            sample_res.append(sum_c)

    return sample_res

if __name__ == '__main__':
    main() 
