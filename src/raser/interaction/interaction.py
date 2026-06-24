'''
Description:  interaction.py
@Date       : 2025
@Author     : Chenxi Fu (Original: Geant4)
@version    : 1.0
'''

import sys
import random
import math
import json
import os

import numpy as np
import g4ppyy as g4b

g4b.include("G4RunManager.hh")

from .detector_construction import GeneralDetectorConstruction
from .action_initialization import GeneralActionInitialization

verbose = 0
world_size = 25000

class GeneralG4Interaction:
    def __init__(self, my_d, g4experiment, 
                 g4_seed = random.randint(0, 1e7), g4_vis = False, 
                 MyDetectorConstruction=GeneralDetectorConstruction, MyActionInitialization=GeneralActionInitialization):
        """
        Description:
            General Geant4 main process
            Simulate s_num particles through device
            Record the energy depositon in the device
        Parameters:
            energy_steps : list
                Energy deposition of each step in simulation
            edep_devices : list
                Total energy deposition in device          
        @Modify:
            2025/05/15
        """	
        geant4_json = os.getenv("RASER_SETTING_PATH")+"/g4experiment/" + g4experiment + ".json"
        with open(geant4_json) as f:
            g4_dic = json.load(f)

        if 'par_randx' not in g4_dic:
            g4_dic['par_randx'] = 0
        if 'par_randy' not in g4_dic:
            g4_dic['par_randy'] = 0

        self.geant4_model = g4_dic['geant4_model']
        detector_material=my_d.device_dict['material']

        if (self.geant4_model == 'gdml_import'
                and MyDetectorConstruction is GeneralDetectorConstruction):
            from .g4_gdml_import import GDMLDetectorConstruction
            MyDetectorConstruction = GDMLDetectorConstruction

        my_g4d = MyDetectorConstruction(my_d,g4_dic,detector_material,g4_dic['maxstep'])

        g4_vis = g4_vis or g4_dic['g4_vis']
        if g4_vis: 
            ui = None
            ui = g4b.G4UIExecutive(1, [os.getcwd()]) # make sure the UI is created in the current working directory

        g4RunManager = g4b.G4RunManager.GetRunManager() or g4b.G4RunManager()
        rand_engine= g4b.cppyy.gbl.CLHEP.RanecuEngine()
        g4b.cppyy.gbl.CLHEP.HepRandom.setTheEngine(rand_engine)
        g4b.cppyy.gbl.CLHEP.HepRandom.setTheSeed(g4_seed)
        g4RunManager.SetUserInitialization(my_g4d)

        # set physics list
        physics_list =  g4b.FTFP_BERT()
        physics_list.RegisterPhysics(g4b.G4StepLimiterPhysics())
        g4RunManager.SetUserInitialization(physics_list)

        self.eventIDs, self.edep_devices, self.p_steps, self.energy_steps, self.events_angles = [],[],[],[],[]

        #define action
        g4RunManager.SetUserInitialization(MyActionInitialization(
                                          g4_dic['par_in'], g4_dic['par_out'], g4_dic['par_randx'], g4_dic['par_randy'], g4_dic['par_type'], g4_dic['par_energy'],
                                          self.eventIDs, self.edep_devices, self.p_steps, self.energy_steps, self.events_angles,
                                          self.geant4_model))
        
        if g4_vis:  
            visManager = g4b.G4VisExecutive()
            visManager.Initialize()
            UImanager = g4b.G4UImanager.GetUIpointer()
            
            if self.geant4_model == 'gdml_import':
                UImanager.ApplyCommand('/control/execute setting/g4macro/vis_pcb.mac')
            else:
                UImanager.ApplyCommand('/control/execute setting/g4macro/init_vis.mac')
        else:
            UImanager = g4b.G4UImanager.GetUIpointer()
            # reduce verbose from physics list
            UImanager.ApplyCommand('/process/em/verbose %d'%(verbose))
            UImanager.ApplyCommand('/process/had/verbose %d'%(verbose))
            UImanager.ApplyCommand('/run/initialize')
            
        g4RunManager.BeamOn(int(g4_dic['total_events']))
        if g4_vis:  
            ui.SessionStart()
            del ui

        self.init_tz_device = 0    
        self.p_steps_current=[[[single_step[0]+my_d.l_x/2,
                                single_step[1]+my_d.l_y/2,
                                single_step[2]-self.init_tz_device]\
            for single_step in p_step] for p_step in self.p_steps]
        # change the coordinate system from Geant4 to device

        
    def __del__(self):
        pass
