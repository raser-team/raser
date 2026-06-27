'''
Description:  action_initialization.py
@Date       : 2025
@Author     : Yuhang Tan, Chenxi Fu (Original: Geant4)
@version    : 2.0
'''

import numpy as np
import g4ppyy as g4b

g4b.include("G4VUserActionInitialization.hh")

from .run_action import GeneralRunAction
from .event_action import GeneralEventAction
from .stepping_action import GeneralSteppingAction
from .primary_generator_action import GeneralPrimaryGeneratorAction

class GeneralActionInitialization(g4b.G4VUserActionInitialization):
    def __init__(self, par_in, par_out, par_randx, par_randy, par_type, par_energy,
                 eventIDs, edep_devices, p_steps, energy_steps, events_angles, geant4_model,):
        super().__init__()
        self.par_in = par_in
        self.par_out = par_out
        self.par_type = par_type
        self.par_energy = par_energy
        self.par_randx = par_randx
        self.par_randy = par_randy

        self.eventIDs = eventIDs
        self.edep_devices = edep_devices
        self.p_steps = p_steps
        self.energy_steps = energy_steps
        self.events_angles = events_angles

        self.geant4_model=geant4_model
        self.actions = []

    def Build(self):
        primary_action = GeneralPrimaryGeneratorAction(self.par_in,
                                                    self.par_out,
                                                    self.par_randx, 
                                                    self.par_randy,
                                                    self.par_type,
                                                    self.par_energy,
                                                    self.geant4_model,)
        self.actions.append(primary_action)
        self.SetUserAction(primary_action)
        # global myRA_action
        myRA_action = GeneralRunAction()
        self.actions.append(myRA_action)
        self.SetUserAction(myRA_action)
        myEA = GeneralEventAction(myRA_action, self.par_in, self.par_out, 
                                  self.eventIDs, self.edep_devices, self.p_steps, self.energy_steps, self.events_angles,)
        self.actions.append(myEA)
        self.SetUserAction(myEA)
        stepping_action = GeneralSteppingAction(myEA)
        self.actions.append(stepping_action)
        self.SetUserAction(stepping_action)
