#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
'''
Description: 
    geat4_pybind simulation   
@Date       : 2021/09/02 12:46:27
@Author     : Yuhang Tan
@version    : 1.0
   
@Date       : 2023/04/18
@Author     : xingchenli
@version    : 2.0
'''

import sys
import random
import math
import json
import os

import numpy as np
import g4ppyy as g4b

from .interaction import GeneralG4Interaction
from .detector_construction import GeneralDetectorConstruction
from .action_initialization import GeneralActionInitialization
from .primary_generator_action import GeneralPrimaryGeneratorAction
from .event_action import GeneralEventAction
from .stepping_action import GeneralSteppingAction
from .run_action import GeneralRunAction
# TODO: tagged orphan file

verbose = 0
world_size = 25000

# Geant4 main process
class BeamMonitorG4Interaction(GeneralG4Interaction):
    def __init__(self, my_d, g4experiment, g4_seed = random.randint(0, 1e7), g4_vis = False):
        """
        Description:
            Geant4 main process
            Simulate s_num particles through device
            Record the energy depositon in the device
        Parameters:
        ---------
        energy_steps : list
            Energy deposition of each step in simulation
        edep_devices : list
            Total energy deposition in device          
        @Modify:
        ---------
            2023/04/18
        """	
        super().__init__(my_d, g4experiment, g4_seed, g4_vis)
        hittotal=0
        for particleenergy in self.edep_devices:
            if(particleenergy>0):
                hittotal=hittotal+1
        self.hittotal=hittotal      #count the numver of hit particles

        number=0
        total_steps=0
        for step in self.p_steps:
            total_steps=len(step)+total_steps
        average_steps=total_steps/len(self.p_steps)
        for step in self.p_steps:
            if(len(step)>=average_steps*0.9):
                break
            number=number+1
        newtype_step=self.p_steps[number]      #new particle's step
        self.p_steps_current=[[[single_step[0]+my_d.l_x/2,
                                single_step[1]+my_d.l_y/2,
                                single_step[2]-self.init_tz_device]\
            for single_step in newtype_step]]
    
        newtype_energy=[0 for i in range(len(newtype_step))]
        for energy in self.energy_steps:
            for i in range(len(newtype_step)):
                if(len(energy)>i):
                    newtype_energy[i]+=energy[i]
        self.energy_steps=[newtype_energy]      #new particle's every step energy
