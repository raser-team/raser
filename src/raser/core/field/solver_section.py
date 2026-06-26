#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

'''
@File    :   solver_section.py
@Time    :   2024
@Author  :   Sen Zhao
@Version :   1.0
'''

import sys
import os
import subprocess
import time
import math

import devsim 
import numpy as np

if __name__ == "__main__":
    __package__ = "raser.core.field"

from ..device.build_device import Detector
from .create_mesh import DevsimMesh
from .create_parameter import create_parameter, delete_init
from . import save_milestone
from . import loop_section
from . import physics_drift_diffusion
from raser.supports.output import output
from .devsim_draw import *

paras = {
    "absolute_error_Initial" : 1e10, 
    "relative_error_Initial" : 1e-4, 
    "maximum_iterations_Initial" : 100,

    "absolute_error_VoltageSteps" : 1e20, 
    "relative_error_VoltageSteps" : 1e-4, 
    "maximum_iterations_VoltageSteps" : 100,

    "milestone_mode" : True,
    "milestone_step" : 100.0,

    "max_voltage_step" :8.0,
    "increase_factor": 2.0,
    "decrease_factor":0.5,

    "voltage_step" : 1.0,
    "acreal" : 1.0, 
    "acimag" : 0.0,
    "frequency" : 1000.0,
    "Cylindrical_coordinate": False,

    "ac-weightfield" : False,

    "Voltage-step-model" : False,
    "step":1,
}

os.environ["OMP_NUM_THREADS"] = "1"

def main (kwargs):
    simname = kwargs['label']
    is_cv = kwargs['cv']
    is_wf = kwargs["wf"]
    is_noise = kwargs["noise"]
    irradiation_flux = kwargs["irradiation_flux"]
    v_goal = kwargs["bias"]
    
    if is_wf:
        paras.update({"weightfield": True})
    else:
        paras.update({"weightfield": False})

    device = simname
    region = simname
    MyDetector = Detector(device)
    MyDevsimMesh = DevsimMesh(MyDetector, devsim_solve_paras=paras)
    MyDevsimMesh.mesh_define()

    if "frequency" in MyDetector.device_dict:
        paras.update({"frequency": MyDetector.device_dict['frequency']})
    if "area_factor" in MyDetector.device_dict:
        paras.update({"area_factor": MyDetector.device_dict['area_factor']})
    if "default_dimension" in MyDetector.device_dict:
        default_dimension =MyDetector.device_dict["default_dimension"]
    if "irradiation" in MyDetector.device_dict and not is_wf:
        irradiation = True
    else:
        irradiation = False

    create_parameter(MyDetector, device, region)

    if "irradiation" in MyDetector.device_dict:
        irradiation_model=MyDetector.device_dict['irradiation']['irradiation_model']
        if irradiation_flux == None:
            irradiation_flux=MyDetector.device_dict['irradiation']['irradiation_flux']
    else:
        irradiation_model=None
        irradiation_flux=0
    if 'avalanche_model' in MyDetector.device_dict:
        impact_model=MyDetector.device_dict['avalanche_model']
    else:
        impact_model=None
        
    if is_wf == True:
        readout_contacts=[]
        if MyDetector.device_dict.get("mesh", {}).get("2D_mesh", {}).get("ac_contact"):
            print("=========RASER info===================\nACLGAD is simulating\n=============info====================")
            for read_out_electrode in MyDetector.device_dict["mesh"]["2D_mesh"]["ac_contact"]:
                readout_contacts.append(read_out_electrode["name"])
            for i,c in enumerate(readout_contacts):
                devsim.circuit_element(name="V{}".format(i+1), n1=physics_drift_diffusion.GetContactBiasName(c), n2=0,
                        value=0.0, acreal=paras['acreal'], acimag=paras['acimag'],)
        else:
            print("===============RASER info===================\nNot AC detector\n===========info=============")
            for read_out_electrode in MyDetector.device_dict["read_out_contact"]:
                readout_contacts.append(read_out_electrode["name"])
            for i,c in enumerate(readout_contacts):
                devsim.circuit_element(name="V{}".format(i+1), n1=physics_drift_diffusion.GetContactBiasName(c), n2=0,
                        value=0.0, acreal=paras['acreal'], acimag=paras['acimag'],)
            
    else:
        bias_contact = MyDetector.device_dict['bias']['electrode']
        devsim.circuit_element(name="V1", n1=physics_drift_diffusion.GetContactBiasName(bias_contact), n2=0,
                           value=0.0, acreal=paras['acreal'], acimag=paras['acimag'],)
    T1 = time.time()
    print("================RASER info============\nWelcome to RASER TCAD PART, mesh load successfully\n=============info===============")
    devsim.set_parameter(name = "debug_level", value="info")
    devsim.set_parameter(name = "extended_solver", value=True)
    devsim.set_parameter(name = "extended_model", value=True)
    devsim.set_parameter(name = "extended_equation", value=True)
    
    if is_wf == True: # top priority
        solve_model = "wf"
    elif is_cv == True:
        solve_model = "cv"
    elif is_noise == True:
        solve_model = "noise"
    else:
        solve_model = None

    path = output(__file__, device)
    if irradiation:
        path = output(__file__, device, str(irradiation_flux))

    loop=loop_section.loop_section(paras=paras,device=device,region=region,solve_model=solve_model,irradiation=irradiation,)
   
    if is_wf == True:
        v_trial=1
        print("=======RASER info========\nBegin simulation WeightingField\n======================")
        for contact in readout_contacts:
            print(path)
            folder_path = os.path.join(path, "weightingfield")
            print(folder_path)
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            
            paras["milestone_step"] == 1
            paras.update({"milestone_step":paras["milestone_step"]})

            loop.initial_solver(contact=contact,set_contact_type=None,impact_model=impact_model,irradiation_model=irradiation_model,irradiation_flux=irradiation_flux,)
            loop.loop_solver(circuit_contact=contact,v_trial=v_trial,area_factor=paras["area_factor"],)

            save_milestone.save_milestone(device=device, v=v_trial, path=folder_path,dimension=default_dimension,contact_name=contact,is_wf=is_wf,)
            devsim.write_devices(file=os.path.join(folder_path,"weightingfield.dat"), type="tecplot")
            
    elif is_wf == False:
        loop.initial_solver(contact=bias_contact, set_contact_type=None, impact_model=impact_model, irradiation_model=irradiation_model, irradiation_flux=irradiation_flux,)
        v_current = 0
        loop.loop_solver(circuit_contact=bias_contact, v_trial=0, area_factor=paras["area_factor"])
        save_milestone.save_milestone(device=device, v=0, path=path, dimension=default_dimension, contact_name=bias_contact, is_wf=is_wf,)
        dd = os.path.join(path, '0V.dd')
        devsim_device = os.path.join(path, '0V.devsim')
        devsim.write_devices(file=dd, type="tecplot")
        devsim.write_devices(file=devsim_device, type="devsim")
        # solve and save at 0V
        if v_goal is None:
            v_goal = float(MyDetector.device_dict['bias']['voltage'])
        if v_goal > 0:
            milestone_step = paras['milestone_step']
            voltage_step = 1.0 
        else:
            milestone_step = -1 * paras['milestone_step']
            voltage_step = -1.0 
        max_voltage_step = paras['max_voltage_step']

        step_too_small = False
        milestone_flag = False
        goal_flag = False
        voltage_milestones = [n*milestone_step for n in range(1, int(abs(v_goal)/abs(milestone_step)) + 1)]
        while abs(v_current) <= abs(v_goal):
            v_trial = v_current + voltage_step
            if abs(v_trial) > abs(v_goal):
                v_trial = v_goal
                goal_flag = True
            elif abs(v_trial) > abs(voltage_milestones[0]):
                v_trial = voltage_milestones[0]
                milestone_flag = True
            try:
                loop.loop_solver(circuit_contact=bias_contact, v_trial=v_trial, area_factor=paras["area_factor"],)
                if abs(voltage_step) < max_voltage_step:
                    voltage_step = voltage_step * paras['increase_factor']
                else:
                    pass
                print("=========RASER info===========\nConvergence success, voltage = {}, increased voltage step = {}\n================".format(v_trial, voltage_step))
                if (paras['milestone_mode']) and (milestone_flag or goal_flag):
                    save_milestone.save_milestone(device=device, v=v_trial, path=path, dimension=default_dimension, contact_name=bias_contact, is_wf=is_wf,)
                    dd = os.path.join(path, str(v_trial) + 'V.dd')
                    devsim_device = os.path.join(path, str(v_trial) + 'V.devsim')
                    devsim.write_devices(file=dd, type="tecplot")
                    devsim.write_devices(file=devsim_device, type="devsim")
                    if goal_flag:
                        break
                    if milestone_flag:
                        voltage_milestones.pop(0)
                        milestone_flag = False

            except devsim.error as msg:
                milestone_flag = False
                if str(msg).find("Convergence failure") == -1:
                    raise
                voltage_step *= paras['decrease_factor'] 

                print("=========RASER info===========\nConvergence failure, voltage = {}, decreased voltage step = {}\n================".format(v_trial, voltage_step))
  
                if abs(voltage_step) < 1e-7:
                    step_too_small = True
                    break  
                continue  

            v_current = v_trial 

        else:
            print("Loop completed successfully.")
        if step_too_small:
            raise RuntimeError("Step size too small (less than 1e-7). Exiting loop.")
        else:
            print("Loop completed successfully.")

    if is_wf != True:
    
        draw_iv(device, V=loop.get_voltage_values(), I=loop.get_current_values(),path=path)
        if is_cv == True:
            draw_cv(device, V=loop.get_voltage_values(), C=loop.get_cap_values(),path=path)
        if is_noise == True:
            draw_noise(device, V=loop.get_voltage_values(), noise=loop.get_noise_values(),path=path,)
    T2 =time.time()
    print("=========RASER info===========\nSimulation finish ,total used time: {}s !^w^!\n================".format(T2-T1))

if __name__ == "__main__":
    import sys
    args = sys.argv[1] # str(kwargs)
    print(args)
    main(eval(args))