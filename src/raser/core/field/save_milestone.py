'''
@File       : save_milestone.py
@Date       : 2024
@Author     : Sen Zhao
@version    : 1.0
'''

import json
import os
import pickle
import re

import devsim
import numpy as np

from .assets import field_pickle_path
from . import devsim_draw
from .create_parameter import create_parameter, delete_init
from .conductive import conductive
from .conductive import undepleted_bulk
from .conductive import undepleted_layer_of_mesh
from raser.supports import figures
from raser.supports.output import create_path

def _depth_um(x_cm):
    """Positions [cm] of the field solver in um, the unit of the depth axis."""
    return np.asarray(x_cm) * 1e-2 / figures.UNIT["um"]


def _electric_field_kv_per_cm(field):
    """Electric field [V/cm] in kV/cm."""
    return np.asarray(field) * 1e2 / figures.UNIT["kV/cm"]


def conductive_of_region(device, region):
    """Which nodes of a solved region are conductive at its bias, 1.0 or 0.0 each,
    judged with the mobilities the solve used there."""

    def values(name):
        return devsim.get_node_model_values(device=device, region=region, name=name)

    def mobility(name):
        return float(devsim.get_parameter(device=device, region=region, name=name))

    return conductive(
        values("Electrons"), values("Holes"), values("NetDoping"), mobility("mu_n"), mobility("mu_p")
    ).astype(float)


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
    Conductive = []

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
        if not is_tcad:
            Conductive.extend(conductive_of_region(device, region))
            mu_n, mu_p, permittivity = (
                float(devsim.get_parameter(device=device, region=region, name=name))
                for name in ("mu_n", "mu_p", "Permittivity")
            )

    if not is_tcad:
        # The undepleted bulk at this bias, per area: its resistance and its
        # capacitance, which a run takes with the area factor of the device.
        width, resistance = undepleted_bulk(x, Electrons, Holes, NetDoping, mu_n, mu_p)
        layer = {
            "voltage_V": float(v),
            "undepleted_width_um": width * 1e4,
            "specific_resistance_ohm_cm2": resistance,
            "specific_capacitance_pF": 1e12 * permittivity / width if width else None,
            "per": "cm^2",
        }
        with open(os.path.join(path, f"{float(v)}V.undepleted.json"), "w") as file:
            json.dump(layer, file, indent=2)
        save_solved(path, "undepleted", float(v))

    x = geometry_scale*np.array(x) # get x-node values
    Potential = np.array(Potential) # get the potential data
    NetDoping= np.array(NetDoping)
    PotentialNodeCharge = np.array(PotentialNodeCharge)
    Electrons = np.array(Electrons)
    Holes = np.array(Holes)
    TrappingRate_n = np.array(TrappingRate_n)
    TrappingRate_p = np.array(TrappingRate_p)

    devsim_draw.draw_profile(
        _depth_um(x), [(Potential, figures.TOTAL, None)],
        figures.label("Potential", "V"), path, "potential", (v, "V"))
    if TrappingRate_n.any() or TrappingRate_p.any():
        devsim_draw.draw_profile(
            _depth_um(x),
            [(TrappingRate_n / figures.UNIT["s-1"], figures.ELECTRON, "electrons"),
             (TrappingRate_p / figures.UNIT["s-1"], figures.HOLE, "holes")],
            figures.label("Trapping rate", "s-1"), path, "trapping_rate", (v, "V"), log=True)

    if is_tcad:
        ElectricField = []
        for region in devsim.get_region_list(device=device):
            if ( devsim.get_material(device=device, region=region) == "Aluminum" or devsim.get_material(device=device, region=region) == "air"
            ):
                continue
            ElectricField.extend(devsim.get_node_model_values(device=device, region=region, name=E))
        ElectricField = np.array(ElectricField)
        devsim_draw.draw_profile(
            _depth_um(x), [(_electric_field_kv_per_cm(ElectricField), figures.TOTAL, None)],
            figures.label("Electric field", "kV/cm"), path, "electric_field", (v, "V"))
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
        devsim_draw.draw_profile(
            _depth_um(x_mid), [(_electric_field_kv_per_cm(ElectricField), figures.TOTAL, None)],
            figures.label("Electric field", "kV/cm"), path, "electric_field", (v, "V"))

    metadata = {}
    metadata['voltage'] = v
    metadata['dimension'] = 1

    names = ['Potential', 'TrappingRate_p', 'TrappingRate_n', 'Electrons', 'Holes']
    if not is_tcad:
        names.append('Conductive')
    if v == 0 or is_tcad:
        names.append('NetDoping')

    for name in names: # scalar field on mesh point (instead of on edge)
        with open(field_pickle_path(path, name, v),'wb') as file:
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

    # `path` is the weightingfield folder of the field folder, which holds the plots
    field_path = os.path.dirname(os.path.normpath(path))
    electrode = re.sub(r"[^a-z0-9_]", "_", contact_name.lower())
    devsim_draw.draw_profile(
        _depth_um(x), [(Potential, figures.TOTAL, None)],
        "Weighting potential", field_path, "weighting_potential", electrode, (v, "V"))
    devsim_draw.draw_profile(
        _depth_um(x_mid), [(ElectricField * 1e2 / figures.UNIT["cm-1"], figures.TOTAL, None)],
        figures.label("Weighting field", "cm-1"), field_path, "weighting_field", electrode, (v, "V"))

    metadata = {}
    metadata['voltage'] = v
    metadata['dimension'] = 1
    
    for name in ['Potential']: # scalar field on mesh point (instead of on edge)
        with open(field_pickle_path(save_wf_path, name, v),'wb') as file:
            data = {}
            data['values'] = eval(name) # refer to the object with given name
            data['points'] = x
            data['metadata'] = metadata
            pickle.dump(data, file)

def milestone_save_2D(device, v, path, is_tcad, is_flip=False, axes=None):
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
    Conductive = []
    volumes = []

    # TODO: TCAD imports can contain dielectric/metal regions that do not carry
    # semiconductor node models; filter by available node models before saving.
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
        if not is_tcad:
            Conductive.extend(conductive_of_region(device, region))
            volumes.extend(devsim.get_node_model_values(device=device, region=region, name="NodeVolume"))
            mu_n, mu_p, permittivity = (
                float(devsim.get_parameter(device=device, region=region, name=name))
                for name in ("mu_n", "mu_p", "Permittivity")
            )

    if not is_tcad and axes is not None and "z" in axes:
        # The undepleted bulk at this bias, per area: its mean width over the
        # span of the mesh across the depth, and its resistance times its
        # area, which a run takes with the area of the device.
        coordinates = dict(zip(axes, (x, y)))
        span = 1.0
        for axis in axes:
            if axis != "z":
                span *= float(np.max(coordinates[axis]) - np.min(coordinates[axis]))
        width, resistance = undepleted_layer_of_mesh(volumes, span, Electrons, Holes, NetDoping, mu_n, mu_p)
        layer = {
            "voltage_V": float(v),
            "undepleted_width_um": width * 1e4,
            "specific_resistance_ohm_cm2": resistance,
            "specific_capacitance_pF": 1e12 * permittivity / width if width else None,
            "per": "cm^2",
        }
        with open(os.path.join(path, f"{float(v)}V.undepleted.json"), "w") as file:
            json.dump(layer, file, indent=2)
        save_solved(path, "undepleted", float(v))

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

    names = ['Potential', 'TrappingRate_p', 'TrappingRate_n', 'Electrons', 'Holes']
    if not is_tcad:
        names.append('Conductive')
    if v == 0 or is_tcad:
        names.append('NetDoping')

    for name in names: # scalar field on mesh point (instead of on edge)
        with open(field_pickle_path(path, name, v),'wb') as file:
            data = {}
            data['values'] = eval(name) # refer to the object with given name
            merged_list = [x, y]
            transposed_list = list(map(list, zip(*merged_list)))
            data['points'] = transposed_list
            data['metadata'] = metadata
            pickle.dump(data, file)


def milestone_save_wf_2D(device, v, path, contact_name, is_tcad, is_flip=False, cells_either_side=None):
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
    if cells_either_side is not None:
        # the potential is on a row of cells, the electrode in the middle one
        metadata['cells_either_side'] = cells_either_side

    for name in ['Potential']: # scalar field on mesh point (instead of on edge)
        with open(field_pickle_path(save_wf_path, name, v),'wb') as file:
            data = {}
            data['values'] = eval(name) # refer to the object with given name
            merged_list = [x, y]
            transposed_list = list(map(list, zip(*merged_list)))
            data['points'] = transposed_list
            data['metadata'] = metadata
            pickle.dump(data, file)

def milestone_save_3D(device, v, path, is_tcad, axes=None):
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
    Conductive = []
    volumes = []

    
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
        if not is_tcad:
            Conductive.extend(conductive_of_region(device, region))
            volumes.extend(devsim.get_node_model_values(device=device, region=region, name="NodeVolume"))
            mu_n, mu_p, permittivity = (
                float(devsim.get_parameter(device=device, region=region, name=name))
                for name in ("mu_n", "mu_p", "Permittivity")
            )

  
    if not is_tcad and axes is not None and "z" in axes:
        # The undepleted bulk at this bias, per area: its mean width over the
        # span of the mesh across the depth, and its resistance times its
        # area, which a run takes with the area of the device.
        coordinates = dict(zip(axes, (x, y, z)))
        span = 1.0
        for axis in axes:
            if axis != "z":
                span *= float(np.max(coordinates[axis]) - np.min(coordinates[axis]))
        width, resistance = undepleted_layer_of_mesh(volumes, span, Electrons, Holes, NetDoping, mu_n, mu_p)
        layer = {
            "voltage_V": float(v),
            "undepleted_width_um": width * 1e4,
            "specific_resistance_ohm_cm2": resistance,
            "specific_capacitance_pF": 1e12 * permittivity / width if width else None,
            "per": "cm^2",
        }
        with open(os.path.join(path, f"{float(v)}V.undepleted.json"), "w") as file:
            json.dump(layer, file, indent=2)
        save_solved(path, "undepleted", float(v))

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
            # A TDR file holds the field of a 3D solution as its three components.
            components = [
                np.array(devsim.get_node_model_values(device=device, region=region, name=f"{E}_{axis}"))
                for axis in range(3)
            ]
            ElectricField.extend(np.sqrt(sum(component**2 for component in components)))
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

    names = ["Potential", "TrappingRate_p", "TrappingRate_n", "Electrons", "Holes"]
    if not is_tcad:
        names.append('Conductive')
    if v == 0 or is_tcad:
        names.append("NetDoping")

    for name in names:
        save_path = field_pickle_path(path, name, v)
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

    with open(field_pickle_path(save_wf_path, "Potential", v), 'wb') as file:
        data = {}
        data['values'] = Potential
        merged_list = [x, y, z]
        transposed_list = list(map(list, zip(*merged_list)))
        data['points'] = transposed_list
        data['metadata'] = metadata
        pickle.dump(data, file)

def save_record(path, **entries):
    """Write what a solve records about its field into the run.json of the
    field folder, beside what is recorded there already."""
    record = {}
    if os.path.exists(os.path.join(path, "run.json")):
        with open(os.path.join(path, "run.json")) as file:
            record = json.load(file)
    record.update(entries)
    with open(os.path.join(path, "run.json"), "w") as file:
        json.dump(record, file, indent=2)


def save_solved(path, asset, at):
    """Add to the "solved" entry of run.json that the folder now holds `asset`
    at `at`: {"potential": [0, 100.0, 200.0], "weighting": [200.0], ...}."""
    record = {}
    if os.path.exists(os.path.join(path, "run.json")):
        with open(os.path.join(path, "run.json")) as file:
            record = json.load(file)
    solved = record.get("solved", {})
    if at not in solved.setdefault(asset, []):
        solved[asset].append(at)
    save_record(path, solved=solved)


def save_milestone(device, v, path, dimension, contact_name, is_wf, is_tcad = False, is_flip=False, cells_either_side=None, axes=None):
    if dimension == 1:
        if is_wf == True:
            milestone_save_wf_1D(device, v, path, contact_name, is_tcad)
        elif is_wf == False:
            milestone_save_1D(device, v, path, is_tcad)
        else:
            print("==========RASER info ==========\nis_wf only has 2 values, True or False\n==========Error=========")
    if dimension == 2:
        if is_wf == True:
            milestone_save_wf_2D(device, v, path, contact_name, is_tcad, is_flip, cells_either_side)
        elif is_wf == False:
            milestone_save_2D(device, v, path, is_tcad, is_flip, axes=axes)
        else:
            print("==========RASER info ==========\nis_wf only has 2 values, True or False\n==========Error=========")
    if dimension == 3:
        if is_wf == True:
            milestone_save_wf_3D(device, v, path, contact_name, is_tcad)
        elif is_wf == False:
            milestone_save_3D(device, v, path, is_tcad, axes=axes)
        else:
            print("==========RASER info ==========\nis_wf only has 2 values, True or False\n==========Error=========")
