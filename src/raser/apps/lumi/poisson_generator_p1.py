import ROOT
import os
from array import array
import json
from . import cflm_p1
from . import get_current_p1
import glob
from raser.supports.paths import app_file_path
from raser.supports.output import output

def main(hitEvents, pos_mom_energy, hitTime):

    if int(hitEvents) == 0:
       
        print("No particle hits the detect area and no detector response")

    else:    
        output_path = output(__file__, "N0_3_4")
                                                            
        pos, mom, energy = [], [], []
        pos_mom_energy_list = pos_mom_energy

        for ele in pos_mom_energy_list:
            pos.append(ele[0])
            mom.append(ele[1])
            energy.append(ele[2])
                    
        geant4_json = app_file_path("lumi", "cflm_p1.json")
        with open(geant4_json, 'r') as file:
        
            g4_dic = json.load(file)    
            g4_dic['NumofGun']    = int(hitEvents)
            g4_dic['par_in']      = pos
            g4_dic['par_direct']  = mom
            g4_dic['par_energy']  = energy
            g4_dic['CurrentName'] = f"{hitTime}.root"   
            updated_g4_dic = json.dumps(g4_dic, indent=4)

        with open(geant4_json, 'w') as file:
            file.write(updated_g4_dic)

        cflm_p1.main()
        get_current_p1.main(output_path)
        os.remove(os.path.join(output_path, "s_p_steps.json"))
        os.remove(os.path.join(output_path, "s_energy_steps.json"))
        os.remove(os.path.join(output_path, "s_edep_devices.json"))

        root_files = glob.glob(os.path.join(output_path, '*.root'))
        for file in root_files:
            os.remove(file)      
