import os
from collections import defaultdict
import re
import ROOT
import numpy as np
from raser.supports.output import output

def main():

    output_folder = output(__file__, "N0_3_4")

    threshold_peak(output_folder, 0)
    threshold_peak(output_folder, 0.05)   
    threshold_peak(output_folder, 0.5)
    threshold_peak(output_folder, 1)
    threshold_peak(output_folder, 3)
    threshold_peak(output_folder, 5)
    
def threshold_peak(output_folder, th):
    
    count = 0

    patternI = r'(\d+)_I.txt'
    patternII = r'(\d+)_II.txt'
    
    for i in range(804):

        c_data = []
        
        event_folder = os.path.join(output_folder, f"event_{i}")
        for filename in os.listdir(event_folder):
    
            match_I = re.match(patternI, filename)
            match_II = re.match(patternII, filename)
            
            if match_I:
               with open(os.path.join(event_folder, filename)) as current_I_file:
                    for line in current_I_file:
                        columns = line.strip().split()
                        if len(columns) == 2:  
                           c_data.append(float(columns[1])) 
            elif match_II:
                with open(os.path.join(event_folder, filename)) as current_II_file:
                    for line in current_II_file:
                        columns = line.strip().split()
                        if len(columns) == 2:  
                           c_data.append(float(columns[1]))

        for ele in c_data:
            if ele>th*1e-6:
               count+=1
               break
        
    print(f"Number of events above the threshold {th}uA:   ", count) 

if __name__ == '__main__':
    main()   
