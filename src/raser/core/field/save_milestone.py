'''
@File       : save_milestone.py
@Date       : 2024
@Author     : Sen Zhao
@version    : 1.0
'''

import os
import pickle

import devsim
import numpy as np

from . import devsim_draw
from .create_parameter import create_parameter, delete_init
from raser.supports.output import create_path

def milestone_save_1D(device, v, path, is_tcad):
    if is_tcad:
        U = "ElectrostaticPotential"
        # TODO: replace E with (ElectricField_0**2 + ElectricField_1**2)**0.5
        E = "ElectricField_0"
        Doping = "DopingConcentration"
        PNC = "SpaceCharge"
        e = "eDensity"
        h = "hDensity"
        # TODO: add irradiation defect assisted recombination
        trap_n = "eGapStatesRecombination"
        trap_p = "hGapStatesRecombination"
        geometry_scale = 1e-4 # TCAD uses um
    else:
        U = "Potential"
        E = "ElectricField"
        Doping = "NetDoping"
        PNC = "PotentialNodeCharge"
        e = "Electrons"
        h = "Holes"
        trap_n = "TrappingRate_n"
        trap_p = "TrappingRate_p"  
        geometry_scale = 1 # Devsim uses cm

    x = []
    Potential = [] # get the potential dat
    NetDoping= []
    PotentialNodeCharge = []
    Electrons = []
    Holes = []
    TrappingRate_n = []
    TrappingRate_p = []

    for region in devsim.get_region_list(device=device):
        if ( devsim.get_material(device=device, region=region) == "Aluminum" or devsim.get_material(device=device, region=region) == "air"
        ):
            continue
        x.extend(devsim.get_node_model_values(device=device, region=region, name="x"))
        Potential.extend(devsim.get_node_model_values(device=device, region=region, name=U)) # get the potential dat
        NetDoping.extend(devsim.get_node_model_values(device=device, region=region, name=Doping))
        PotentialNodeCharge.extend(devsim.get_node_model_values(device=device, region=region, name=PNC))
        Electrons.extend(devsim.get_node_model_values(device=device, region=region, name=e))
        Holes.extend(devsim.get_node_model_values(device=device, region=region, name=h))
        TrappingRate_n.extend(devsim.get_node_model_values(device=device, region=region, name=trap_n))
        TrappingRate_p.extend(devsim.get_node_model_values(device=device, region=region, name=trap_p))

    x = geometry_scale*np.array(x) # get x-node values
    Potential = np.array(Potential) # get the potential data
    NetDoping= np.array(NetDoping)
    PotentialNodeCharge = np.array(PotentialNodeCharge)
    Electrons = np.array(Electrons)
    Holes = np.array(Holes)
    TrappingRate_n = np.array(TrappingRate_n)
    TrappingRate_p = np.array(TrappingRate_p)

    devsim_draw.draw1D(x,Potential,"Potential","Depth[cm]","Potential[V]", v, path)
    devsim_draw.draw1D(x,TrappingRate_n,"Electron Trapping Rate","Depth[cm]","Trapping Rate[s]", v, path,)
    devsim_draw.draw1D(x,TrappingRate_p,"Hole Trapping Rate","Depth[cm]","Trapping Rate[s]", v, path,)

    if is_tcad:
        ElectricField = []
        for region in devsim.get_region_list(device=device):
            if ( devsim.get_material(device=device, region=region) == "Aluminum" or devsim.get_material(device=device, region=region) == "air"
            ):
                continue
            ElectricField.extend(devsim.get_node_model_values(device=device, region=region, name=E))
        ElectricField = np.array(ElectricField)
        devsim_draw.draw1D(x,ElectricField,"Electric Field","Depth[cm]","Electric Field[V/cm]", v, path,)
    else:
        x_mid = []
        ElectricField = []
        for region in devsim.get_region_list(device=device): 
            if ( devsim.get_material(device=device, region=region) == "Aluminum" or devsim.get_material(device=device, region=region) == "air"
            ):
                continue
            devsim.edge_average_model(device=device, region=region, node_model="x", edge_model="xmid")
            x_mid.extend(devsim.get_edge_model_values(device=device, region=region, name="xmid")) # get x-node values 
            ElectricField.extend(devsim.get_edge_model_values(device=device, region=region, name=E)) # get y-node values
        x_mid = np.array(x_mid) # get x-node values
        ElectricField = np.array(ElectricField) # get y-node values
        devsim_draw.draw1D(x_mid,ElectricField,"Electric Field","Depth[cm]","Electric Field[V/cm]", v, path,)

    metadata = {}
    metadata['voltage'] = v
    metadata['dimension'] = 1

    names = ['Potential', 'TrappingRate_p', 'TrappingRate_n']
    if v == 0 or is_tcad:
        names.append('NetDoping')

    for name in names: # scalar field on mesh point (instead of on edge)
        with open(os.path.join(path, "{}_{}V.pkl".format(name,v)),'wb') as file:
            data = {}
            data['values'] = eval(name) # refer to the object with given name
            data['points'] = x
            data['metadata'] = metadata
            pickle.dump(data, file)

def milestone_save_wf_1D(device, v, path, contact_name, is_tcad):
    save_wf_path = os.path.join(path, contact_name)
    create_path(save_wf_path)

    x = []
    Potential = [] # get the potential dat
    ElectricField = []
    x_mid = []

    for region in devsim.get_region_list(device=device):
        if ( devsim.get_material(device=device, region=region) == "Aluminum" or devsim.get_material(device=device, region=region) == "air"
        ):
            continue
        x.extend(devsim.get_node_model_values(device=device, region=region, name="x"))
        Potential.extend(devsim.get_node_model_values(device=device, region=region, name="Potential")) # get the potential data
        devsim.edge_average_model(device=device, region=region, node_model="x", edge_model="xmid")
        ElectricField.extend(devsim.get_edge_model_values(device=device, region=region, name="ElectricField"))
        x_mid.extend(devsim.get_edge_model_values(device=device, region=region, name="xmid")) 
    
    x = np.array(x) # get x-node values
    Potential = np.array(Potential) # get the potential data
    x_mid = np.array(x_mid) # get x-node values
    ElectricField = np.array(ElectricField) # get y-node values

    devsim_draw.draw1D(x,Potential,"Weighting Potential","Depth[um]","Weighting Potential", v, save_wf_path,)
    devsim_draw.draw1D(x_mid,ElectricField,"Weighting Field","Depth[um]","Weighting Field[1/cm]",v, save_wf_path,)

    metadata = {}
    metadata['voltage'] = v
    metadata['dimension'] = 1
    
    for name in ['Potential']: # scalar field on mesh point (instead of on edge)
        with open(os.path.join(save_wf_path, "{}_{}V.pkl".format(name,v)),'wb') as file:
            data = {}
            data['values'] = eval(name) # refer to the object with given name
            data['points'] = x
            data['metadata'] = metadata
            pickle.dump(data, file)

def milestone_save_2D(device, v, path, is_tcad, is_flip=False):
    if is_tcad:
        U = "ElectrostaticPotential"
        # TODO: replace E with (ElectricField_0**2 + ElectricField_1**2)**0.5
        E = "ElectricField_0"
        Doping = "DopingConcentration"
        PNC = "SpaceCharge"
        e = "eDensity"
        h = "hDensity"
        # TODO: add irradiation defect assisted recombination
        trap_n = "eGapStatesRecombination"
        trap_p = "hGapStatesRecombination"
        geometry_scale = 1e-4 # TCAD uses um
    else:
        U = "Potential"
        E = "ElectricField"
        Doping = "NetDoping"
        PNC = "PotentialNodeCharge"
        e = "Electrons"
        h = "Holes"
        trap_n = "TrappingRate_n"
        trap_p = "TrappingRate_p"  
        geometry_scale = 1 # Devsim uses cm

    x = []
    y = []
    Potential = [] # get the potential dat
    NetDoping= []
    PotentialNodeCharge = []
    Electrons = []
    Holes = []
    TrappingRate_n = []
    TrappingRate_p = []

    for region in devsim.get_region_list(device=device):
        if ( devsim.get_material(device=device, region=region) == "Aluminum" or devsim.get_material(device=device, region=region) == "air"
        ):
            continue
        x.extend(devsim.get_node_model_values(device=device, region=region, name="x"))
        y.extend(devsim.get_node_model_values(device=device, region=region, name="y"))
        Potential.extend(devsim.get_node_model_values(device=device, region=region, name=U)) # get the potential dat
        NetDoping.extend(devsim.get_node_model_values(device=device, region=region, name=Doping))
        PotentialNodeCharge.extend(devsim.get_node_model_values(device=device, region=region, name=PNC))
        Electrons.extend(devsim.get_node_model_values(device=device, region=region, name=e))
        Holes.extend(devsim.get_node_model_values(device=device, region=region, name=h))
        TrappingRate_n.extend(devsim.get_node_model_values(device=device, region=region, name=trap_n))
        TrappingRate_p.extend(devsim.get_node_model_values(device=device, region=region, name=trap_p))

    x = geometry_scale*np.array(x) # get x-node values
    y = geometry_scale*np.array(y) # get y-node values
    Potential = np.array(Potential) # get the potential data
    NetDoping= np.array(NetDoping)
    PotentialNodeCharge = np.array(PotentialNodeCharge)
    Electrons = np.array(Electrons)
    Holes = np.array(Holes)
    TrappingRate_n = np.array(TrappingRate_n)
    TrappingRate_p = np.array(TrappingRate_p)

    if is_flip:
        x, y = y, x

    devsim_draw.draw2D(x,y,Potential,"Potential", v, path)
    devsim_draw.draw2D(x,y,TrappingRate_n,"Electron Trapping Rate", v, path)
    devsim_draw.draw2D(x,y,TrappingRate_p,"Hole Trapping Rate", v, path)

    if is_tcad:
        ElectricField = []
        for region in devsim.get_region_list(device=device):
            if ( devsim.get_material(device=device, region=region) == "Aluminum" or devsim.get_material(device=device, region=region) == "air"
            ):
                continue
            ElectricField.extend(devsim.get_node_model_values(device=device, region=region, name=E))
        ElectricField = np.array(ElectricField)
        devsim_draw.draw2D(x,y,ElectricField,"Electric Field", v, path)
    else:
        x_mid = []
        y_mid = []
        ElectricField = []
        for region in devsim.get_region_list(device=device):
            if ( devsim.get_material(device=device, region=region) == "Aluminum" or devsim.get_material(device=device, region=region) == "air"
            ):
                continue 
            devsim.element_from_edge_model(edge_model=E,   device=device, region=region)
            devsim.edge_average_model(device=device, region=region, node_model="x", edge_model="xmid")
            devsim.edge_average_model(device=device, region=region, node_model="y", edge_model="ymid")
            x_mid.extend(devsim.get_edge_model_values(device=device, region=region, name="xmid")) 
            y_mid.extend(devsim.get_edge_model_values(device=device, region=region, name="ymid")) 
            ElectricField.extend(devsim.get_edge_model_values(device=device, region=region, name=E))
        x_mid = np.array(x_mid) # get x-node values
        y_mid = np.array(y_mid) # get y-node values
        ElectricField = np.array(ElectricField) # get y-node values
        if is_flip:
            x_mid, y_mid = y_mid, x_mid
        devsim_draw.draw2D(x_mid,y_mid,ElectricField,"Electric Field", v, path)

    metadata = {}
    metadata['voltage'] = v
    metadata['dimension'] = 2

    names = ['Potential', 'TrappingRate_p', 'TrappingRate_n']
    if v == 0 or is_tcad:
        names.append('NetDoping')

    for name in names: # scalar field on mesh point (instead of on edge)
        with open(os.path.join(path, "{}_{}V.pkl".format(name,v)),'wb') as file:
            data = {}
            data['values'] = eval(name) # refer to the object with given name
            merged_list = [x, y]
            transposed_list = list(map(list, zip(*merged_list)))
            data['points'] = transposed_list
            data['metadata'] = metadata
            pickle.dump(data, file)


def milestone_save_wf_2D(device, v, path, contact_name, is_tcad, is_flip=False):
    save_wf_path = os.path.join(path,contact_name)
    create_path(save_wf_path)

    x = []
    y = []
    Potential = [] # get the potential dat
    ElectricField = []
    x_mid = []
    y_mid = []

    for region in devsim.get_region_list(device=device):
        print(devsim.get_material(device=device, region=region))
        if ( devsim.get_material(device=device, region=region) == "Aluminum" or devsim.get_material(device=device, region=region) == "air"
        ):
            continue    
        x.extend(devsim.get_node_model_values(device=device, region=region, name="x"))
        y.extend(devsim.get_node_model_values(device=device, region=region, name="y"))
        Potential.extend(devsim.get_node_model_values(device=device, region=region, name="Potential")) # get the potential data
        devsim.element_from_edge_model(edge_model="ElectricField",   device=device, region=region)
        devsim.edge_average_model(device=device, region=region, node_model="x", edge_model="xmid")
        devsim.edge_average_model(device=device, region=region, node_model="y", edge_model="ymid")
        ElectricField.extend(devsim.get_edge_model_values(device=device, region=region, name="ElectricField"))
        x_mid.extend(devsim.get_edge_model_values(device=device, region=region, name="xmid")) 
        y_mid.extend(devsim.get_edge_model_values(device=device, region=region, name="ymid"))
    
    x = np.array(x) # get x-node values
    y = np.array(y) # get y-node values
    Potential = np.array(Potential) # get the potential data
    x_mid = np.array(x_mid) # get x-node values
    y_mid = np.array(y_mid) # get y-node values
    ElectricField = np.array(ElectricField) # get y-node values

    if is_flip:
        x, y = y, x
        x_mid, y_mid = y_mid, x_mid

    devsim_draw.draw2D(x,y,Potential,"Weighting Potential", v, save_wf_path)
    devsim_draw.draw2D(x_mid,y_mid,ElectricField,"Weighting Field", v, save_wf_path)

    metadata = {}
    metadata['voltage'] = v
    metadata['dimension'] = 2

    for name in ['Potential']: # scalar field on mesh point (instead of on edge)
        with open(os.path.join(save_wf_path, "{}_{}V.pkl".format(name,v)),'wb') as file:
            data = {}
            data['values'] = eval(name) # refer to the object with given name
            merged_list = [x, y]
            transposed_list = list(map(list, zip(*merged_list)))
            data['points'] = transposed_list
            data['metadata'] = metadata
            pickle.dump(data, file)

def milestone_save_3D(device, v, path, is_tcad):
    if is_tcad:
        U = "ElectrostaticPotential"       
        E = "ElectricField"           
        Doping = "DopingConcentration"   
        PNC = "SpaceCharge"               
        e = "eDensity"                     
        h = "hDensity"                    
        trap_n = "eGapStatesRecombination"
        trap_p = "hGapStatesRecombination" 
        geometry_scale = 1e-4             
    else:
        U = "Potential"                    
        E = "ElectricField"           
        Doping = "NetDoping"              
        PNC = "PotentialNodeCharge"        
        e = "Electrons"                   
        h = "Holes"                       
        trap_n = "TrappingRate_n"         
        trap_p = "TrappingRate_p"          
        geometry_scale = 1               

   
    x = []  
    y = []  
    z = []  
    Potential = []          
    NetDoping = []          
    PotentialNodeCharge = []
    Electrons = []
    ElectricField = []        
    Holes = []              
    TrappingRate_n = []     
    TrappingRate_p = []    

    
    for region in devsim.get_region_list(device=device):
        if ( devsim.get_material(device=device, region=region) == "Aluminum" or devsim.get_material(device=device, region=region) == "air"
        ): 
            continue  
        x.extend(devsim.get_node_model_values(device=device, region=region, name="x"))
        y.extend(devsim.get_node_model_values(device=device, region=region, name="y"))
        z.extend(devsim.get_node_model_values(device=device, region=region, name="z"))
        Potential.extend(devsim.get_node_model_values(device=device, region=region, name=U))
        NetDoping.extend(devsim.get_node_model_values(device=device, region=region, name=Doping))
        PotentialNodeCharge.extend(devsim.get_node_model_values(device=device, region=region, name=PNC))
        Electrons.extend(devsim.get_node_model_values(device=device, region=region, name=e))
        Holes.extend(devsim.get_node_model_values(device=device, region=region, name=h))
        TrappingRate_n.extend(devsim.get_node_model_values(device=device, region=region, name=trap_n))
        TrappingRate_p.extend(devsim.get_node_model_values(device=device, region=region, name=trap_p))

  
    x = geometry_scale * np.array(x)
    y = geometry_scale * np.array(y)
    z = geometry_scale * np.array(z)
    Potential = np.array(Potential)
    NetDoping = np.array(NetDoping)
    PotentialNodeCharge = np.array(PotentialNodeCharge)
    Electrons = np.array(Electrons)
    Holes = np.array(Holes)
    TrappingRate_n = np.array(TrappingRate_n)
    TrappingRate_p = np.array(TrappingRate_p)

    devsim_draw.draw3D(x, y, z, Potential, "Potential Distribution ", v, path)
    devsim_draw.draw3D(x, y, z, TrappingRate_n, "Electron Trapping Rate ", v, path)
    devsim_draw.draw3D(x, y, z, TrappingRate_p, "Hole Trapping Rate ", v, path)

   
    if is_tcad:
        for region in devsim.get_region_list(device=device):
            if ( devsim.get_material(device=device, region=region) == "Aluminum" or devsim.get_material(device=device, region=region) == "air"
            ):
                continue 
            ElectricField.extend(devsim.get_node_model_values(device=device, region=region, name=E))
        ElectricField = np.array(ElectricField)     
        devsim_draw.draw3D(x, y, z, ElectricField, "Electric Field", v, path)
    else:    
        x_mid = [] 
        y_mid = []
        z_mid = []
        for region in devsim.get_region_list(device=device):
            if ( devsim.get_material(device=device, region=region) == "Aluminum" or devsim.get_material(device=device, region=region) == "air"
            ):
                continue      
            devsim.element_from_edge_model(edge_model=E, device=device, region=region)
            devsim.edge_average_model(device=device, region=region, node_model="x", edge_model="xmid")
            devsim.edge_average_model(device=device, region=region, node_model="y", edge_model="ymid")
            devsim.edge_average_model(device=device, region=region, node_model="z", edge_model="zmid")
            x_mid.extend(devsim.get_edge_model_values(device=device, region=region, name="xmid"))
            y_mid.extend(devsim.get_edge_model_values(device=device, region=region, name="ymid"))
            z_mid.extend(devsim.get_edge_model_values(device=device, region=region, name="zmid"))    
            ElectricField.extend(devsim.get_edge_model_values(device=device, region=region, name=E))
        x_mid = np.array(x_mid)
        y_mid = np.array(y_mid)
        z_mid = np.array(z_mid)
        ElectricField = np.array(ElectricField)
        devsim_draw.draw3D(x_mid, y_mid, z_mid, ElectricField, "Electric Field", v, path)

    metadata = {
        "voltage": v,        
        "dimension": 3       
    }

    names = ["Potential", "TrappingRate_p", "TrappingRate_n"]
    if v == 0 or is_tcad:
        names.append("NetDoping")

    for name in names:
        save_path = os.path.join(path, f"{name}_{v}V.pkl")
        with open(save_path, "wb") as file:
            data = {
                "values": eval(name),
                "points": list(map(list, zip(x, y, z))),
                "metadata": metadata,
            }
            pickle.dump(data, file)

def milestone_save_wf_3D(device, v, path, contact_name, is_tcad):
    save_wf_path = os.path.join(path, contact_name)
    create_path(save_wf_path)

    x = []
    y = []
    z = []
    Potential = []
    ElectricField = []
    x_mid = []
    y_mid = []
    z_mid = []

    for region in devsim.get_region_list(device=device):
        if ( devsim.get_material(device=device, region=region) == "Aluminum" or devsim.get_material(device=device, region=region) == "air"
        ):
            continue
        x.extend(devsim.get_node_model_values(device=device, region=region, name="x"))
        y.extend(devsim.get_node_model_values(device=device, region=region, name="y"))
        z.extend(devsim.get_node_model_values(device=device, region=region, name="z"))
        Potential.extend(devsim.get_node_model_values(device=device, region=region, name="Potential"))
        devsim.element_from_edge_model(edge_model="ElectricField", device=device, region=region)
        devsim.edge_average_model(device=device, region=region, node_model="x", edge_model="xmid")
        devsim.edge_average_model(device=device, region=region, node_model="y", edge_model="ymid")
        devsim.edge_average_model(device=device, region=region, node_model="z", edge_model="zmid")
        ElectricField.extend(devsim.get_edge_model_values(device=device, region=region, name="ElectricField"))
        x_mid.extend(devsim.get_edge_model_values(device=device, region=region, name="xmid"))
        y_mid.extend(devsim.get_edge_model_values(device=device, region=region, name="ymid"))
        z_mid.extend(devsim.get_edge_model_values(device=device, region=region, name="zmid"))

    x = np.array(x)
    y = np.array(y)
    z = np.array(z)
    Potential = np.array(Potential)
    x_mid = np.array(x_mid)
    y_mid = np.array(y_mid)
    z_mid = np.array(z_mid)
    ElectricField = np.array(ElectricField)

    devsim_draw.draw3D(x, y, z, Potential, "Weighting Potential", v, save_wf_path)
    devsim_draw.draw3D(x_mid, y_mid, z_mid, ElectricField, "Weighting Field", v, save_wf_path)

    metadata = {}
    metadata['voltage'] = v
    metadata['dimension'] = 3
    metadata['contact_name'] = contact_name

    with open(os.path.join(save_wf_path, f"Potential_{v}V.pkl"), 'wb') as file:
        data = {}
        data['values'] = Potential
        merged_list = [x, y, z]
        transposed_list = list(map(list, zip(*merged_list)))
        data['points'] = transposed_list
        data['metadata'] = metadata
        pickle.dump(data, file)

def save_milestone(device, v, path, dimension, contact_name, is_wf, is_tcad = False, is_flip=False):
    if dimension == 1:
        if is_wf == True:
            milestone_save_wf_1D(device, v, path, contact_name, is_tcad)
        elif is_wf == False:
            milestone_save_1D(device, v, path, is_tcad)
        else:
            print("==========RASER info ==========\nis_wf only has 2 values, True or False\n==========Error=========")
    if dimension == 2:
        if is_wf == True:
            milestone_save_wf_2D(device, v, path, contact_name, is_tcad, is_flip)
        elif is_wf == False:
            milestone_save_2D(device, v, path, is_tcad, is_flip)
        else:
            print("==========RASER info ==========\nis_wf only has 2 values, True or False\n==========Error=========")
    if dimension == 3:
        if is_wf == True:
            milestone_save_wf_3D(device, v, path, contact_name, is_tcad)
        elif is_wf == False:
            milestone_save_3D(device, v, path, is_tcad)
        else:
            print("==========RASER info ==========\nis_wf only has 2 values, True or False\n==========Error=========")

