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
import copy
from pathlib import Path

import numpy as np
import g4ppyy as g4b

g4b.include("G4RunManager.hh")

from .detector_construction import GeneralDetectorConstruction
from .action_initialization import GeneralActionInitialization
from raser.supports.paths import component_path

verbose = 0
world_size = 25000

def _get_or_create_vis_manager():
    existing = g4b.cppyy.gbl.G4VVisManager.GetConcreteInstance()
    if existing:
        return existing
    vis_manager = g4b.G4VisExecutive()
    vis_manager.Initialize()
    return vis_manager


def _resolve_vis_driver(g4_dic):
    driver = g4_dic.get("g4_vis_driver") or os.environ.get("G4VIS_DEFAULT_DRIVER")
    if not driver:
        raise ValueError(
            "Geant4 visualization driver must be explicit: use "
            "--g4-vis-driver or set G4VIS_DEFAULT_DRIVER"
        )
    return driver


def _vis_driver_needs_ui_session(driver):
    batch_drivers = {
        "DAWNFILE",
        "HEPREPFILE",
        "K3DJUPYTER",
        "MPLJUPYTER",
        "VRML2FILE",
    }
    return driver.upper() not in batch_drivers


class GeneralG4Interaction:
    def __init__(self, my_d, g4experiment, 
                 g4_seed = random.randint(0, 1e7), g4_vis = False, 
                 MyDetectorConstruction=GeneralDetectorConstruction, MyActionInitialization=GeneralActionInitialization,):
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
        if isinstance(g4experiment, dict):
            g4_dic = copy.deepcopy(g4experiment)
        else:
            geant4_json = Path(g4experiment)
            if not geant4_json.exists():
                raise FileNotFoundError(
                    "Geant4 geometry must be passed as a config dict or JSON path: "
                    f"{g4experiment}"
                )
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

        self.my_g4d = MyDetectorConstruction(my_d,g4_dic,detector_material,g4_dic['maxstep'])

        g4_vis = g4_vis or g4_dic['g4_vis']
        vis_driver = _resolve_vis_driver(g4_dic) if g4_vis else None
        vis_needs_ui = bool(vis_driver and _vis_driver_needs_ui_session(vis_driver))
        if g4_vis: 
            ui = None
            if vis_needs_ui:
                ui = g4b.G4UIExecutive(1, [os.getcwd()]) # make sure the UI is created in the current working directory

        self.g4RunManager = g4b.G4RunManager.GetRunManager() or g4b.G4RunManager()
        self.rand_engine= g4b.cppyy.gbl.CLHEP.RanecuEngine()
        g4b.cppyy.gbl.CLHEP.HepRandom.setTheEngine(self.rand_engine)
        g4b.cppyy.gbl.CLHEP.HepRandom.setTheSeed(g4_seed)
        self.g4RunManager.SetUserInitialization(self.my_g4d)

        # set physics list
        self.physics_list =  g4b.FTFP_BERT()
        self.step_limiter_physics = g4b.G4StepLimiterPhysics()
        self.physics_list.RegisterPhysics(self.step_limiter_physics)
        self.g4RunManager.SetUserInitialization(self.physics_list)

        (

        self.eventIDs, self.edep_devices, self.p_steps, self.energy_steps, self.events_angles,
        ) = [],[],[],[],[]

        #define action
        self.action_initialization = MyActionInitialization(
                                          g4_dic['par_in'], g4_dic['par_out'], g4_dic['par_randx'], g4_dic['par_randy'], g4_dic['par_type'], g4_dic['par_energy'],
                                          self.eventIDs, self.edep_devices, self.p_steps, self.energy_steps, self.events_angles,
                                          self.geant4_model,)
        self.g4RunManager.SetUserInitialization(self.action_initialization)
        
        if g4_vis:  
            self.visManager = _get_or_create_vis_manager()
            UImanager = g4b.G4UImanager.GetUIpointer()
            UImanager.ApplyCommand("/vis/open {}".format(vis_driver))
            
            if self.geant4_model == 'gdml_import':
                UImanager.ApplyCommand(
                    "/control/execute {}".format(
                        component_path("g4macro", "vis_pcb.mac")
                    ))
            else:
                UImanager.ApplyCommand(
                    "/control/execute {}".format(
                        component_path("g4macro", "init_vis.mac")
                    ))
                UImanager.ApplyCommand(
                    "/control/execute {}".format(
                        component_path("g4macro", "vis.mac")
                    ))
            if g4_dic.get("g4_vis_output"):
                UImanager.ApplyCommand("/vis/viewer/set/background 1 1 1")
                UImanager.ApplyCommand("/vis/ogl/set/printMode vectored")
                UImanager.ApplyCommand("/vis/ogl/set/printSize 2000 2000")
                UImanager.ApplyCommand(
                    "/vis/ogl/set/printFilename {}".format(
                        g4_dic["g4_vis_output"]
                    )
                )
        else:
            UImanager = g4b.G4UImanager.GetUIpointer()
            # reduce verbose from physics list
            UImanager.ApplyCommand('/process/em/verbose %d'%(verbose))
            UImanager.ApplyCommand('/process/had/verbose %d'%(verbose))
            UImanager.ApplyCommand('/run/initialize')
            
        self.g4RunManager.BeamOn(int(g4_dic['total_events']))
        if g4_vis:
            UImanager.ApplyCommand("/vis/viewer/flush")
        if g4_vis and g4_dic.get("g4_vis_output"):
            UImanager.ApplyCommand("/vis/ogl/export")
        if g4_vis and vis_needs_ui:
            ui.SessionStart()
            del ui

        self.init_tz_device = 0    
        self.p_steps_current=[[[single_step[0]+my_d.l_x/2,
                                single_step[1]+my_d.l_y/2,
                                single_step[2]-self.init_tz_device,]\
            for single_step in p_step] for p_step in self.p_steps]
        # change the coordinate system from Geant4 to device

        
    def __del__(self):
        pass
