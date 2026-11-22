#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

'''
@File    :   solver_section.py
@Time    :   2024
@Author  :   Sen Zhao
@Version :   1.0
'''

import json
import math
import os
import time

import devsim 
import numpy as np

if __name__ == "__main__":
    __package__ = "raser.core.field"

from ..model.material import Material
from ..device.build_device import Detector
from .create_mesh import DevsimMesh
from .create_mesh import mesh_axes
from .reading import Reading
from .create_parameter import create_parameter
from . import save_milestone
from . import loop_section
from . import physics_drift_diffusion
from .assets import field_pickle_path
from .weighting import take_conductors_into_electrodes
from raser.supports.output import create_path
from .devsim_draw import *

os.environ["OMP_NUM_THREADS"] = "1"


# The settings of the solver, unless the run gives others.
SOLVER = {
    "initial": {"absolute_error": 1e10, "relative_error": 1e-4, "maximum_iterations": 100},
    "voltage_step": {
        "absolute_error": 1e20,
        "relative_error": 1e-4,
        "maximum_iterations": 100,
        "initial": 1.0,
        "increase_factor": 2.0,
        "decrease_factor": 0.5,
    },
    # Raising the fluence in the initial solution; "initial" is the first step as a fraction of the target fluence.
    "flux_step": {"initial": 0.01, "increase_factor": 2.0, "decrease_factor": 0.5},
    "saved_voltage_interval": 100.0,
    "curve_voltage_interval": 10.0,  # between two points of the IV and CV curves
    "ac": {"real": 1.0, "imaginary": 0.0, "frequency": 1000.0},
    # What may be left of the weighting potential of an electrode at the ends
    # of the row of cells it is solved on.
    "weighting_tolerance": 5e-2,
    # The part of the capacitance of an electrode that the neighbours a
    # distance away must hold for a signal to be carried over to them.
    "crosstalk_tolerance": 5e-2,
}


def _resolve_impact_model(detector):
    return detector.avalanche_model if detector.has_avalanche else None


def _voltage_milestones(v_goal, milestone_step):
    if v_goal == 0:
        return []
    if milestone_step == 0:
        raise ValueError("Field milestone step must be non-zero")
    direction = 1.0 if v_goal > 0 else -1.0
    interval = abs(float(milestone_step))
    milestones = [
        direction * index * interval
        for index in range(1, int(abs(v_goal) / interval) + 1)
    ]
    if not milestones or abs(milestones[-1]) < abs(v_goal):
        milestones.append(float(v_goal))
    return milestones


def _legacy_solver_parameters(configuration, *, weightfield):
    solver = configuration["solver"]
    initial = solver["initial"]
    voltage_step = solver["voltage_step"]
    flux_step = solver["flux_step"]
    ac = solver["ac"]
    return {
        "absolute_error_Initial": float(initial["absolute_error"]),
        "relative_error_Initial": float(initial["relative_error"]),
        "maximum_iterations_Initial": int(initial["maximum_iterations"]),
        "absolute_error_VoltageSteps": float(voltage_step["absolute_error"]),
        "relative_error_VoltageSteps": float(voltage_step["relative_error"]),
        "maximum_iterations_VoltageSteps": int(
            voltage_step["maximum_iterations"]
        ),
        "milestone_mode": True,
        "milestone_step": float(solver["saved_voltage_interval"]),
        "curve_step": float(solver["curve_voltage_interval"]),
        "increase_factor": float(voltage_step["increase_factor"]),
        "decrease_factor": float(voltage_step["decrease_factor"]),
        "voltage_step": float(voltage_step["initial"]),
        "flux_step_initial": float(flux_step["initial"]),
        "flux_step_increase": float(flux_step["increase_factor"]),
        "flux_step_decrease": float(flux_step["decrease_factor"]),
        "acreal": float(ac["real"]),
        "acimag": float(ac["imaginary"]),
        "frequency": float(ac["frequency"]),
        "area_factor": float(configuration["area_factor"]),
        "Cylindrical_coordinate": False,
        "ac-weightfield": False,
        "weightfield": bool(weightfield),
    }

def cells_to_fall_off(depth, pitch, tolerance):
    """Cells on either side of an electrode for its weighting potential to
    fall to `tolerance` in a fully depleted device.

    Far from the electrode the potential falls as exp(-pi * distance / depth)
    between the plane of the electrodes and the back. A device that is not
    fully depleted is thinner than that. The end of the row reflects what
    reaches it, which doubles it there.
    """
    return math.ceil(depth / (math.pi * pitch) * math.log(2 / tolerance))


def left_at_the_ends(device, region, pitch):
    """The largest weighting potential in the two end cells of a row, whose
    cells are `pitch` cm wide."""
    across = np.array(devsim.get_node_model_values(device=device, region=region, name="y"))
    potential = np.array(devsim.get_node_model_values(device=device, region=region, name="Potential"))
    ends = (across < across.min() + pitch) | (across > across.max() - pitch)
    return float(np.abs(potential[ends]).max())


def capacitances(device, electrode, relative_permittivity):
    """Capacitance in F/cm from `electrode` to every other one, in a solved
    weighting field: `electrode` is at 1 V, the others at 0 V and the charge
    on each is what it holds. The weighting field is solved in a dielectric
    of the permittivity of vacuum, so that of the material is put back.
    """
    return {
        name: abs(devsim.get_contact_charge(device=device, contact=name, equation="PotentialEquation"))
        * relative_permittivity
        for name in devsim.get_contact_list(device=device)
        if name != electrode
    }


def neighbours_coupled(to_others, tolerance):
    """How far along the row an electrode carries a signal over: the number
    of "neighbour<n>" electrodes, from the nearest, each of which holds at
    least `tolerance` of the capacitance `to_others` adds up to."""
    total = sum(to_others.values())
    coupled = 0
    while to_others.get("neighbour{}".format(coupled + 1), 0.0) >= tolerance * total:
        coupled += 1
    return coupled


def _empty_devsim():
    """devsim emptied for another solve, with the linear solver it chose when
    it was loaded, which emptying forgets."""
    kept = {
        name: devsim.get_parameter(name=name)
        for name in ("direct_solver", "solver_callback")
        if name in devsim.get_parameter_list()
    }
    devsim.reset_devsim()
    for name, value in kept.items():
        devsim.set_parameter(name=name, value=value)


def main (kwargs):
    simname = kwargs['target']
    is_cv = kwargs['cv']
    is_wf = kwargs["wf"]
    is_noise = kwargs["noise"]
    irradiation_flux = kwargs["irradiation_flux"]
    v_goal = kwargs["bias"]
    
    configuration = {"solver": kwargs.get("solver", SOLVER), "area_factor": 1.0}
    paras = _legacy_solver_parameters(configuration, weightfield=is_wf)

    # Everything the solve takes from the device goes through this, and is noted.
    MyDetector = Reading(Detector(simname, kwargs.get("_files", {}).get("device")))
    # What the device file says about the solve is read here, so that it is noted.
    if "frequency" in MyDetector.device_dict:
        paras["frequency"] = float(MyDetector.device_dict["frequency"])
    paras["area_factor"] = float(MyDetector.device_dict.get("area_factor", 1.0))
    # HEMT_TRANSPORT_V1_DISPATCH
    if MyDetector.device_dict.get("hemt_physics", {}).get("transport_model") == "drift_diffusion_v1":
        from .hemt_solver_2d_transport_v1 import run_hemt_transport
        return run_hemt_transport(MyDetector, kwargs, paras)
    device = MyDetector.device
    region = MyDetector.region
    field_directory = kwargs.get("_field_directory")
    # A device that lists one electrode for a row of them has the mesh of one
    # cell. Its electric field repeats from cell to cell. The weighting
    # potential of an electrode does not, but it is the same for every
    # electrode: it is solved once, on the cell with cells on either side.
    listed = MyDetector.device_dict["read_out_contact"]
    cells_either_side = 0
    weighting_tolerance = float(configuration["solver"]["weighting_tolerance"])
    crosstalk_tolerance = float(configuration["solver"]["crosstalk_tolerance"])
    if is_wf and len(listed) == 1 and MyDetector.read_ele_num > 1:
        cells_either_side = kwargs.get("_cells_either_side") or cells_to_fall_off(
            MyDetector.l_z, MyDetector.p_x, weighting_tolerance
        )
    MyDevsimMesh = DevsimMesh(
        MyDetector,
        devsim_solve_paras=paras,
        output_directory=field_directory,
        cells_either_side=cells_either_side,
    )
    MyDevsimMesh.mesh_define()

    default_dimension = MyDetector.dimension
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
    impact_model = _resolve_impact_model(MyDetector)
        
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
    else:
        solve_model = None

    if field_directory is None:
        raise ValueError("Field execution requires a configuration directory")
    path = str(create_path(field_directory))
    save_milestone.save_record(path, axes=mesh_axes(MyDetector))

    loop=loop_section.loop_section(paras=paras,device=device,region=region,solve_model=solve_model,irradiation=irradiation,path=path,with_noise=is_noise,)
   
    if is_wf == True:
        v_trial=1
        print("=======RASER info========\nBegin simulation WeightingField\n======================")
        conductive_file = field_pickle_path(path, "Conductive", v_goal)
        if not conductive_file.exists():
            raise FileNotFoundError(
                f"the weighting field at {v_goal} V needs the field solved at that bias: "
                f"{conductive_file} is missing; solve it with `raser field {simname} -bias {v_goal}`"
            )
        for contact in readout_contacts:
            print(path)
            folder_path = os.path.join(path, "weightingfield")
            print(folder_path)
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            
            loop.initial_solver(contact=contact,set_contact_type=None,impact_model=impact_model,irradiation_model=irradiation_model,irradiation_flux=irradiation_flux,)
            take_conductors_into_electrodes(
                device, region, conductive_file, bias=v_goal,
                cell_width=float(MyDetector.p_x) * 1e-4 if cells_either_side else None,
            )
            loop.loop_solver(circuit_contact=contact,v_trial=v_trial,area_factor=paras["area_factor"],)

            if cells_either_side:
                left = left_at_the_ends(device, region, float(MyDetector.p_x) * 1e-4)
                to_others = capacitances(device, contact, Material(MyDetector.material).permittivity)
                # The neighbours at the ends of the row hold what would have
                # gone further: one that is still coupled is not the last.
                coupled = neighbours_coupled(to_others, crosstalk_tolerance)
                if left > weighting_tolerance or coupled == cells_either_side:
                    more = math.ceil(1.5 * cells_either_side)
                    if more > 2 * cells_to_fall_off(MyDetector.l_z, MyDetector.p_x, weighting_tolerance):
                        raise ValueError(
                            f"the weighting potential of {contact} of {simname} at {v_goal} V does not fall off "
                            f"along the row: {left:.3g} is left {cells_either_side} cells away, where "
                            f"{to_others['neighbour{}'.format(cells_either_side)] / sum(to_others.values()):.3g} "
                            "of its capacitance is. "
                            "A conductive part of the device that touches the electrodes of the row does this"
                        )
                    _empty_devsim()
                    return main({**kwargs, "_cells_either_side": more})

            # Stored as the weighting field of the bias, as Potential_<bias>V.pkl.
            save_milestone.save_milestone(device=device, v=float(v_goal), path=folder_path,dimension=default_dimension,contact_name=contact,is_wf=is_wf,cells_either_side=cells_either_side or None,axes=mesh_axes(MyDetector),)
            if cells_either_side:
                stored = {
                    "unit": "F/cm",
                    "of": contact,
                    "total": sum(to_others.values()),
                    "to": to_others,
                    "neighbours_coupled": neighbours_coupled(to_others, crosstalk_tolerance),
                }
                with open(
                    field_pickle_path(os.path.join(folder_path, contact), "Capacitance", float(v_goal)).with_suffix(".json"), "w"
                ) as stream:
                    json.dump(stored, stream, indent=1)
            save_milestone.save_solved(path, "weighting", float(v_goal))
            devsim.write_devices(file=os.path.join(folder_path,"weightingfield.dat"), type="tecplot")
            
    elif is_wf == False:
        loop.initial_solver(contact=bias_contact, set_contact_type=None, impact_model=impact_model, irradiation_model=irradiation_model, irradiation_flux=irradiation_flux,)
        v_current = 0
        loop.loop_solver(circuit_contact=bias_contact, v_trial=0, area_factor=paras["area_factor"])
        save_milestone.save_milestone(device=device, v=0, path=path, dimension=default_dimension, contact_name=bias_contact, is_wf=is_wf, axes=mesh_axes(MyDetector),)
        save_milestone.save_solved(path, "potential", 0.0)
        dd = os.path.join(path, '0V.dd')
        devsim_device = os.path.join(path, '0V.devsim')
        devsim.write_devices(file=dd, type="tecplot")
        devsim.write_devices(file=devsim_device, type="devsim")
        # solve and save at 0V
        if v_goal is None:
            v_goal = float(MyDetector.device_dict['bias']['voltage'])
        if v_goal > 0:
            milestone_step = paras['milestone_step']
            voltage_step = abs(paras['voltage_step'])
        else:
            milestone_step = -1 * paras['milestone_step']
            voltage_step = -abs(paras['voltage_step'])

        step_too_small = False
        milestone_flag = False
        goal_flag = False
        voltage_milestones = _voltage_milestones(v_goal, milestone_step)
        curve_points = _voltage_milestones(v_goal, paras['curve_step'] if v_goal > 0 else -paras['curve_step'])
        while abs(v_current) <= abs(v_goal):
            v_trial = v_current + voltage_step
            # The step ends at the nearest bias it has to stop at, if it would pass it.
            next_stop = min([v_goal] + voltage_milestones[:1] + curve_points[:1], key=abs)
            if abs(v_trial) > abs(next_stop):
                v_trial = next_stop
            goal_flag = v_trial == v_goal
            milestone_flag = bool(voltage_milestones) and v_trial == voltage_milestones[0]
            on_curve = bool(curve_points) and v_trial == curve_points[0]
            try:
                loop.loop_solver(circuit_contact=bias_contact, v_trial=v_trial, area_factor=paras["area_factor"], on_curve=on_curve,)
                voltage_step = voltage_step * paras['increase_factor']
                if on_curve:
                    curve_points.pop(0)
                print("=========RASER info===========\nConvergence success, voltage = {}, increased voltage step = {}\n================".format(v_trial, voltage_step))
                if (paras['milestone_mode']) and (milestone_flag or goal_flag):
                    save_milestone.save_milestone(device=device, v=v_trial, path=path, dimension=default_dimension, contact_name=bias_contact, is_wf=is_wf, axes=mesh_axes(MyDetector),)
                    save_milestone.save_solved(path, "potential", float(v_trial))
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
                goal_flag = False
                if str(msg).find("Convergence failure") == -1:
                    raise
                # of the step that was tried, which a stop may have cut short
                voltage_step = (v_trial - v_current) * paras['decrease_factor']

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
        save_milestone.save_record(path, read=MyDetector.read)

        draw_iv(V=loop.get_voltage_values(), I=loop.get_current_values(),path=path)
        if is_cv == True:
            draw_cv(V=loop.get_voltage_values(), C=loop.get_cap_values(),path=path)
        if is_noise == True:
            draw_noise(V=loop.get_voltage_values(), noise=loop.get_noise_values(),path=path,)
    T2 =time.time()
    print("=========RASER info===========\nSimulation finish ,total used time: {}s !^w^!\n================".format(T2-T1))

if __name__ == "__main__":
    import sys
    args = sys.argv[1] # str(kwargs)
    print(args)
    main(eval(args))
