#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import devsim 
from .build_device import Detector
from . import model_create
from . import physics_drift_diffusion
from . import initial

import sys
import json
import pickle
import csv
import os
from util.output import output
from .devsim_draw import *

import numpy as np
import time
import math

paras = {
    "absolute_error" : 1e10, 
    "relative_error" : 1e-5, 
    "maximum_iterations" : 1000,

    "milestone_mode" : True,
    "milestone_step" : 100,

    "voltage_step" : 1,
    "acreal" : 1.0, 
    "acimag" : 0.0,
    "frequency" : 1.0
}

def main(kwargs):
    simname = kwargs['label']
    is_cv = kwargs['cv']

    with open('setting/devsim_general.json') as file:
        paras.update(json.load(file))

    devsim.open_db(filename="./output/field/SICARDB.db", permission="readonly")
    device = simname
    region = simname
    MyDetector = Detector(device)
    MyDetector.mesh_define()

    T = MyDetector.device_dict['temperature']
    k = 1.3806503e-23  # J/K
    q = 1.60217646e-19 # coul
    devsim.add_db_entry(material="global",   parameter="T",    value=T,     unit="K",   description="T")
    devsim.add_db_entry(material="global",   parameter="k_T",    value=k*T,       unit="J",        description="k*T")
    devsim.add_db_entry(material="global",   parameter="Volt_thermal",    value=k*T/q,     unit="J/coul",   description="k*T/q")
    N_c=2.82e19*pow(T/300,1.5)
    N_v=1.83e19*pow(T/300,1.5)
    devsim.add_db_entry(material="Silicon",parameter="N_c",value=N_c, unit="/cm^3", description="effective density of states in conduction band")
    devsim.add_db_entry(material="Silicon",parameter="N_v",value=N_v, unit="/cm^3", description="effective density of states in valence band")
    E_g=1.12*1.6e-19
    N_i=pow(N_c*N_v,0.5)*math.exp(-E_g/(2*k*T))
    devsim.add_db_entry(material="Silicon",   parameter="n_i",    value=N_i,   unit="/cm^3",     description="Intrinsic Electron Concentration")
    devsim.add_db_entry(material="Silicon",   parameter="n1",     value=N_i,   unit="/cm^3",     description="n1")
    devsim.add_db_entry(material="Silicon",   parameter="p1",     value=N_i,   unit="/cm^3",     description="p1")

    if "parameter_alter" in MyDetector.device_dict:
        for material in MyDetector.device_dict["parameter_alter"]:
            print (material)
            for parameter in MyDetector.device_dict["parameter_alter"][material]:
                print (parameter)
                devsim.add_db_entry(material=material,
                                    parameter=parameter['name'],
                                    value=parameter['value'],
                                    unit=parameter['unit'],
                                    description=parameter['name'])
    
    if "parameter" in MyDetector.device_dict:
        devsim.add_db_entry(material=MyDetector.device_dict['parameter']['material'],parameter=MyDetector.device_dict['parameter']['name'],value=MyDetector.device_dict['parameter']['value'],unit=MyDetector.device_dict['parameter']['unit'],description=MyDetector.device_dict['parameter']['description'])
    if "U_const" in MyDetector.device_dict:
        U_const=MyDetector.device_dict["U_const"]
        model_create.CreateNodeModel(device,region,"U_const",U_const)
    else:
        model_create.CreateNodeModel(device,region,"U_const",0)
      
    circuit_contacts = MyDetector.device_dict['bias']['electrode']

    T1 = time.time()

    devsim.set_parameter(name = "extended_solver", value=True)
    devsim.set_parameter(name = "extended_model", value=True)
    devsim.set_parameter(name = "extended_equation", value=True)
    devsim.circuit_element(name="V1", n1=physics_drift_diffusion.GetContactBiasName(circuit_contacts), n2=0,
                           value=0.0, acreal=paras['acreal'], acimag=paras['acimag'])
    
    initial.InitialSolution(device, region, circuit_contacts=circuit_contacts)
    devsim.solve(type="dc", absolute_error=paras['absolute_error_Initial'], relative_error=paras['relative_error_Initial'], maximum_iterations=paras['maximum_iterations_Initial'])

    if "irradiation" in MyDetector.device_dict:
        irradiation_label=MyDetector.device_dict['irradiation']['irradiation_label']
        irradiation_flux=MyDetector.device_dict['irradiation']['irradiation_flux']
    else:
        irradiation_label=None
        irradiation_flux=None

    if 'avalanche_model' in MyDetector.device_dict:
        impact_label=MyDetector.device_dict['avalanche_model']
    else:
        impact_label=None

    initial.DriftDiffusionInitialSolution(device, region, irradiation_label=irradiation_label, irradiation_flux=irradiation_flux, impact_label=impact_label, circuit_contacts=circuit_contacts)
        
    devsim.solve(type="dc", absolute_error=paras['absolute_error_DriftDiffusion'], relative_error=paras['relative_error_DriftDiffusion'], maximum_iterations=paras['maximum_iterations_DriftDiffusion'])
    devsim.delete_node_model(device=device, region=region, name="IntrinsicElectrons")
    devsim.delete_node_model(device=device, region=region, name="IntrinsicHoles")
    devsim.delete_node_model(device=device, region=region, name="IntrinsicElectrons:Potential")
    devsim.delete_node_model(device=device, region=region, name="IntrinsicHoles:Potential")

    voltage = []
    current = []
    capacitance = []

    voltage_milestone = []
    positions_mid = []
    intensities = []

    positions = []
    electrons = []
    holes = []
    
    path = output(__file__, device)
    
    if "irradiation" in MyDetector.device_dict:
        path = output(__file__, str(device)+"/"+str(MyDetector.device_dict['irradiation']['irradiation_flux']))
        
    iv_path = os.path.join(path,"iv.csv")
    f_iv = open(iv_path, "w")
    header_iv = ["Voltage","Current"]
    writer_iv = csv.writer(f_iv)
    writer_iv.writerow(header_iv)

    if is_cv == True:
        cv_path = os.path.join(path,"cv.csv")
        f_cv = open(cv_path, "w")
        header_cv = ["Voltage","Capacitance"]
        writer_cv = csv.writer(f_cv)
        writer_cv.writerow(header_cv)

    v_max = MyDetector.device_dict['bias']['voltage']
    area_factor = MyDetector.device_dict['area_factor']
    frequency = paras['frequency']

    v = 0.0
    if v_max > 0:
        voltage_step = paras['voltage_step']
    else: 
        voltage_step = -1 * paras['voltage_step']

    while abs(v) <= abs(v_max):
        voltage.append(v)
        devsim.set_parameter(device=device, name=physics_drift_diffusion.GetContactBiasName(circuit_contacts), value=v)
        devsim.solve(type="dc", absolute_error=paras['absolute_error_VoltageSteps'], relative_error=paras['relative_error_VoltageSteps'], maximum_iterations=paras['maximum_iterations_VoltageSteps'])
        physics_drift_diffusion.PrintCurrents(device, circuit_contacts)
        electron_current= devsim.get_contact_current(device=device, contact=circuit_contacts, equation="ElectronContinuityEquation")
        hole_current    = devsim.get_contact_current(device=device, contact=circuit_contacts, equation="HoleContinuityEquation")
        total_current   = electron_current + hole_current
        
        if(abs(total_current/area_factor)>105e-6): break
        
        current.append(abs(total_current/area_factor))
        writer_iv.writerow([v,abs(total_current/area_factor)])

        if is_cv == True:
            devsim.circuit_alter(name="V1", value=v)
            #devsim.solve(type="dc", absolute_error=paras['absolute_error'], relative_error=paras['relative_error'], maximum_iterations=paras['maximum_iterations'])
            devsim.solve(type="ac", frequency=frequency)
            cap=1e12*devsim.get_circuit_node_value(node="V1.I", solution="ssac_imag")/ (-2*np.pi*frequency)

            capacitance.append(abs(cap/area_factor))
            writer_cv.writerow([v,abs(cap/area_factor)])
        
        if(paras['milestone_mode']==True and v%paras['milestone_step']==0.0):
            if MyDetector.dimension == 1:
                milestone_save_1D(device, region, v, path)
            elif MyDetector.dimension == 2:
                milestone_save_2D(device, region, v, path)
            elif MyDetector.dimension == 3:
                milestone_save_3D(device, region, v, path)
            else:
                raise ValueError(MyDetector.dimension)
            
            devsim.edge_average_model(device=device, region=region, node_model="x", edge_model="xmid")
            x_mid = devsim.get_edge_model_values(device=device, region=region, name="xmid") # get x-node values 
            E = devsim.get_edge_model_values(device=device, region=region, name="ElectricField") # get y-node values
            V = v

            x = devsim.get_node_model_values(device=device, region=region, name="x") # get x-node values 
            n = devsim.get_node_model_values(device=device, region=region, name="Electrons")
            p = devsim.get_node_model_values(device=device, region=region, name="Holes")

            positions_mid.append(x_mid)
            intensities.append(E)
            voltage_milestone.append(V)

            positions.append(x)
            electrons.append(n)
            holes.append(p)

        v += voltage_step

    draw_iv(device, voltage, current,path)
    if is_cv == True:
        draw_cv(device, voltage, capacitance,path)
    draw_field(device, positions_mid, intensities, voltage_milestone,path)
    save_field(device, positions_mid, intensities, voltage_milestone,path)
    draw_electrons(device, positions, electrons, voltage_milestone,path)
    draw_holes(device, positions, holes, voltage_milestone,path)
    T2 =time.time()
    print('程序运行时间:%s秒' % ((T2 - T1)))

def milestone_save_1D(device, region, v, path):
    x = np.array(devsim.get_node_model_values(device=device, region=region, name="x"))
    Potential = np.array(devsim.get_node_model_values(device=device, region=region, name="Potential")) # get the potential dat
    NetDoping= np.array(devsim.get_node_model_values(device=device, region=region, name="NetDoping"))
    PotentialNodeCharge = np.array(devsim.get_node_model_values(device=device, region=region, name="PotentialNodeCharge"))
    Electrons = np.array(devsim.get_node_model_values(device=device, region=region, name="Electrons"))
    Holes = np.array(devsim.get_node_model_values(device=device, region=region, name="Holes"))
    devsim.edge_average_model(device=device, region=region, node_model="x", edge_model="xmid")
    x_mid = devsim.get_edge_model_values(device=device, region=region, name="xmid") # get x-node values 
    ElectricField = devsim.get_edge_model_values(device=device, region=region, name="ElectricField") # get y-node values
    TrappingRate_n = np.array(devsim.get_node_model_values(device=device, region=region, name="TrappingRate_n"))
    TrappingRate_p = np.array(devsim.get_node_model_values(device=device, region=region, name="TrappingRate_p"))

    draw1D(x,Potential,"Potential","Depth[cm]","Potential[V]", v, path)
    draw1D(x_mid,ElectricField,"ElectricField","Depth[cm]","ElectricField[V/cm]",v, path)
    draw1D(x,TrappingRate_n,"TrappingRate_n","Depth[cm]","TrappingRate_n[s]",v, path)
    draw1D(x,TrappingRate_p,"TrappingRate_p","Depth[cm]","TrappingRate_p[s]",v, path)

    dd = os.path.join(path, str(v)+'V.dd')
    devsim.write_devices(file=dd, type="tecplot")

    metadata = {}
    metadata['voltage'] = v
    metadata['dimension'] = 1

    for name in ['Potential', 'TrappingRate_p', 'TrappingRate_n']: # scalar field on mesh point (instead of on edge)
        with open(os.path.join(path, "{}_{}V.pkl".format(name,v)),'wb') as file:
            data = {}
            data['values'] = eval(name) # refer to the object with given name
            data['points'] = x
            data['metadata'] = metadata
            pickle.dump(data, file)

def milestone_save_2D(device, region, v, path):
    x = np.array(devsim.get_node_model_values(device=device, region=region, name="x")) # get x-node values
    y = np.array(devsim.get_node_model_values(device=device, region=region, name="y")) # get y-node values
    Potential = np.array(devsim.get_node_model_values(device=device, region=region, name="Potential")) # get the potential data
    TrappingRate_n = np.array(devsim.get_node_model_values(device=device, region=region, name="TrappingRate_n"))
    TrappingRate_p = np.array(devsim.get_node_model_values(device=device, region=region, name="TrappingRate_p"))

    devsim.element_from_edge_model(edge_model="ElectricField",   device=device, region=region)
    devsim.edge_average_model(device=device, region=region, node_model="x", edge_model="xmid")
    devsim.edge_average_model(device=device, region=region, node_model="y", edge_model="ymid")
    ElectricField=np.array(devsim.get_edge_model_values(device=device, region=region, name="ElectricField"))
    x_mid = np.array(devsim.get_edge_model_values(device=device, region=region, name="xmid")) 
    y_mid = np.array(devsim.get_edge_model_values(device=device, region=region, name="ymid")) 

    draw2D(x,y,Potential,"Potential",v, path)
    draw2D(x_mid,y_mid,ElectricField,"ElectricField",v, path)
    draw2D(x,y,TrappingRate_n,"TrappingRate_n",v, path)
    draw2D(x,y,TrappingRate_p,"TrappingRate_p",v, path)

    dd = os.path.join(path, str(v)+'V.dd')
    devsim.write_devices(file=dd, type="tecplot")

    metadata = {}
    metadata['voltage'] = v
    metadata['dimension'] = 2

    for name in ['Potential', 'TrappingRate_p', 'TrappingRate_n']: # scalar field on mesh point (instead of on edge)
        with open(os.path.join(path, "{}_{}V.pkl".format(name,v)),'wb') as file:
            data = {}
            data['values'] = eval(name) # refer to the object with given name
            merged_list = [x, y]
            transposed_list = list(map(list, zip(*merged_list)))
            data['points'] = transposed_list
            data['metadata'] = metadata
            pickle.dump(data, file)

def milestone_save_3D(device, region, v, path):
    x=devsim.get_node_model_values(device=device,region=region,name="x")
    y=devsim.get_node_model_values(device=device,region=region,name="y")
    z=devsim.get_node_model_values(device=device,region=region,name="z")
    Potential=devsim.get_node_model_values(device=device,region=region,name="Potential")

    metadata = {}
    metadata['voltage'] = v
    metadata['dimension'] = 3

    for name in ['Potential']: # scalar field on mesh point (instead of on edge)
        with open(os.path.join(path, "{}_{}V.pkl".format(name,v)),'wb') as file:
            data = {}
            data['values'] = eval(name) # refer to the object with given name
            merged_list = [x, y, z]
            transposed_list = list(map(list, zip(*merged_list)))
            data['points'] = transposed_list
            data['metadata'] = metadata
            pickle.dump(data, file)

if __name__ == "__main__":
    args = sys.argv[1:]
    kwargs = {}
    for arg in args:
        key, value = arg.split('=')
        kwargs[key] = value
    main(kwargs)
