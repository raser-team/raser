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
from .physics_irradiation import irradiation_defects, set_fluence
from raser.supports.memory_decorator import memory_decorator

# The smallest step in fluence, as a fraction of the target fluence.
SMALLEST_FLUX_STEP = 1e-7


def raise_fluence(target, first_share, increase, decrease, solve, restore):
    """Raise the fluence from 0 to `target` [cm^-2] in steps.

    The first step is `target * first_share`. A step that `solve(flux)` solves
    (returns True) is kept and the next step is `increase` times larger; the
    last step is cut to end at `target`. A step it does not solve (returns
    False) is undone by `restore()` and tried again with `decrease` times the
    failed step. A step below `SMALLEST_FLUX_STEP * target` raises RuntimeError.

    Returns the list of fluences [cm^-2] that were solved, in order.
    """
    reached = 0.0
    step = target * first_share
    solved = []
    while reached < target:
        trial = min(reached + step, target)
        if solve(trial):
            reached = trial
            step *= increase
            solved.append(trial)
        else:
            restore()
            step = (trial - reached) * decrease
            if step < SMALLEST_FLUX_STEP * target:
                raise RuntimeError(
                    "Fluence step too small: stopped at {:.6g} cm^-2 of the target {:.6g} cm^-2".format(reached, target)
                )
    return solved


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

    def _raise_initial_fluence(self, irradiation_model, irradiation_flux):
        """Raise the fluence of the initial solution from 0 to `irradiation_flux` [cm^-2]."""
        defects = irradiation_defects(self.device, self.region, irradiation_model)
        names = ("Potential", "Electrons", "Holes")
        kept = {}

        def keep():
            for name in names:
                kept[name] = np.array(devsim.get_node_model_values(device=self.device, region=self.region, name=name))

        def solve(flux):
            set_fluence(self.device, self.region, defects, flux)
            try:
                devsim.solve(type="dc", absolute_error=self.paras['absolute_error_Initial'], relative_error=self.paras['relative_error_Initial'], maximum_iterations=self.paras['maximum_iterations_Initial'],)
            except devsim.error as error:
                if "Convergence failure" in str(error):
                    return False
                raise
            keep()
            print(f"{self.device}: the initial solution at a fluence of {flux:.3g} cm^-2 of {irradiation_flux:.3g}")
            return True

        def restore():
            for name in names:
                devsim.set_node_values(device=self.device, region=self.region, name=name, values=list(kept[name]))

        keep()
        try:
            raise_fluence(irradiation_flux, self.paras["flux_step_initial"], self.paras["flux_step_increase"], self.paras["flux_step_decrease"], solve, restore)
        except RuntimeError as error:
            raise RuntimeError(f"{self.device}: {error}") from error

    def initial_solver(self, contact, set_contact_type, irradiation_model, irradiation_flux, impact_model,):
        initial.PotentialOnlyInitialSolution(device=self.device, region=self.region, circuit_contacts=contact, paras=self.paras, set_contact_type=set_contact_type,)
        devsim.solve(type="dc", absolute_error=self.paras['absolute_error_Initial'], relative_error=self.paras['relative_error_Initial'], maximum_iterations=self.paras['maximum_iterations_Initial'],)
        print("======================\nFirst initialize successfully\n===============================")
        if self.solve_model == "wf":
            pass
        else:
            print("======RASER info ===========\nradiation\n================info=================")
            raised = irradiation_model is not None and irradiation_flux > 0
            initial.DriftDiffusionInitialSolution(device=self.device, region=self.region, circuit_contacts=contact,paras=self.paras,set_contact_type=set_contact_type,
                                                irradiation_model=irradiation_model,irradiation_flux=0 if raised else irradiation_flux,impact_model=impact_model,)
            devsim.solve(type="dc", absolute_error=self.paras['absolute_error_Initial'], relative_error=self.paras['relative_error_Initial'], maximum_iterations=self.paras['maximum_iterations_Initial'],)
            if raised:
                self._raise_initial_fluence(irradiation_model, irradiation_flux)

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
            if name != "Potential":
                # a density that went down to zero would stop the next solve
                values = np.maximum(values, np.finfo(float).tiny)
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
