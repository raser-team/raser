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
from raser.supports.memory_decorator import memory_decorator

class loop_section:
    def __init__(self, paras, device, region, solve_model, irradiation, path, with_noise=False):
        self.paras = paras
        self.path = path
        self.with_noise = with_noise
        self.step_model  = False
        self.solve_model = solve_model
        self.device = device
        self.region = region
        self.irradiation = irradiation
        self.voltage = []
        self.solved = []  # the last two solved biases: (bias, {solution name: node values})
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

    def start_from_solved(self, v_trial):
        """Start the step to v_trial from the last solved bias, its potential carried on along the last two."""
        if not self.solved:
            return
        v_last, last = self.solved[-1]
        start = dict(last)
        if len(self.solved) == 2:
            v_before, before = self.solved[0]
            slope = (last["Potential"] - before["Potential"]) / (v_last - v_before)
            start["Potential"] = last["Potential"] + (v_trial - v_last) * slope
        for name, values in start.items():
            devsim.set_node_values(device=self.device, region=self.region, name=name, values=list(values))

    def keep_solved(self, v_trial):
        state = {name: np.array(devsim.get_node_model_values(device=self.device, region=self.region, name=name))
                 for name in ("Potential", "Electrons", "Holes")}
        if self.solved and self.solved[-1][0] == v_trial:
            self.solved[-1] = (v_trial, state)
        else:
            self.solved = self.solved[-1:] + [(v_trial, state)]

    @memory_decorator
    def loop_solver(self, circuit_contact, v_trial, area_factor, on_curve=True):
        if self.solve_model != "wf":
            self.start_from_solved(v_trial)
        devsim.set_parameter(device=self.device, name=physics_drift_diffusion.GetContactBiasName(circuit_contact), value=v_trial,)
        try:
            devsim.solve(type="dc", absolute_error=self.paras['absolute_error_VoltageSteps'], relative_error=self.paras['relative_error_VoltageSteps'], maximum_iterations=self.paras['maximum_iterations_VoltageSteps'],)
            if on_curve:
                self.voltage.append(v_trial)
        except devsim.error as msg:
            devsim.write_devices(file=os.path.join(self.path, "last_solvable.dd"), type="tecplot")
            raise
        
        if self.solve_model !="wf":     
            self.keep_solved(v_trial)
            if not on_curve:  # a step between two points of the IV and CV curves
                return
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
            if self.with_noise:
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
