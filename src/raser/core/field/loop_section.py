#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

'''
@File    :   loop_section.py
@Time    :   2025/05
@Author  :   Sen Zhao
@Version :   1.0
'''

import os
import pickle

import devsim
import numpy as np

from . import initial
from . import physics_drift_diffusion
from .create_parameter import delete_init
from raser.supports.output import output
from raser.supports.memory_decorator import memory_decorator

class loop_section:
    def __init__(self, paras, device, region, solve_model, irradiation):
        self.paras = paras
        self.step_model  = False
        self.solve_model = solve_model
        self.device = device
        self.region = region
        self.irradiation = irradiation
        self.voltage = []
        self.current = []
        self.capacitance = []
        self.noise = []
        self.voltage_milestone = []
        self.positions_mid = []
        self.intensities = []

        self.positions = []
        self.electrons = []
        self.holes = []

    def initial_solver(self, contact, set_contact_type, irradiation_model, irradiation_flux, impact_model,):
        initial.PotentialOnlyInitialSolution(device=self.device, region=self.region, circuit_contacts=contact, paras=self.paras, set_contact_type=set_contact_type,)
        devsim.solve(type="dc", absolute_error=self.paras['absolute_error_Initial'], relative_error=self.paras['relative_error_Initial'], maximum_iterations=self.paras['maximum_iterations_Initial'],)
        print("======================\nFirst initialize successfully\n===============================")
        if self.solve_model == "wf":
            pass
        else:
            print("======RASER info ===========\nradiation\n================info=================")
            initial.DriftDiffusionInitialSolution(device=self.device, region=self.region, circuit_contacts=contact,paras=self.paras,set_contact_type=set_contact_type,
                                                irradiation_model=irradiation_model,irradiation_flux=irradiation_flux,impact_model=impact_model,)
            devsim.solve(type="dc", absolute_error=self.paras['absolute_error_Initial'], relative_error=self.paras['relative_error_Initial'], maximum_iterations=self.paras['maximum_iterations_Initial'],)
            
        # eliminate calculation fatals from intrinsic carrier concentration
        delete_init(device=self.device, region=self.region)

        print("=====================\nDriftDiffusion initialize successfully\n======================")
        print("=========RASER info =========\nAll initialization successfully\n=========info========== ")    

    @memory_decorator
    def loop_solver(self, circuit_contact, v_trial, area_factor):
        devsim.set_parameter(device=self.device, name=physics_drift_diffusion.GetContactBiasName(circuit_contact), value=v_trial,)
        try:
            devsim.solve(type="dc", absolute_error=self.paras['absolute_error_VoltageSteps'], relative_error=self.paras['relative_error_VoltageSteps'], maximum_iterations=self.paras['maximum_iterations_VoltageSteps'],)
            self.voltage.append(v_trial)
        except devsim.error as msg:
            path = output(__file__, self.device)
            devsim.write_devices(file=os.path.join(path, "last_solvable.dd"), type="tecplot")
            raise
        
        if self.solve_model !="wf":     
            physics_drift_diffusion.PrintCurrents(device=self.device, contact=circuit_contact)
            electron_current = devsim.get_contact_current(device=self.device, contact=circuit_contact, equation="ElectronContinuityEquation",)
            hole_current     = devsim.get_contact_current(device=self.device, contact=circuit_contact, equation="HoleContinuityEquation",)
            total_current    = electron_current + hole_current
            self.current.append(total_current*area_factor)
            if self.solve_model == "cv":
                devsim.circuit_alter(name="V1", value=v_trial)
                devsim.solve(type="ac", frequency=self.paras["frequency"])
                cap= (1e12*devsim.get_circuit_node_value(node="V1.I", solution="ssac_imag")/ (-2*np.pi*self.paras["frequency"])) # pF/cm^dim
                self.capacitance.append(cap*area_factor)
            if self.solve_model == "noise":
                devsim.solve(type="noise", frequency=self.paras["frequency"],output_node="V1.I")
                noise=devsim.get_circuit_node_value(node="V1.I")
                self.noise.append(noise)

    def get_voltage_values(self):
        return self.voltage
    def get_current_values(self):
        return self.current
    def get_cap_values(self):
        return self.capacitance
    def get_noise_values(self):
        return self.noise

