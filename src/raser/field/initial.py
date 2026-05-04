'''
Description:  Initial.py
@Date       : 2022/10/25 16:40:46
@Author     : Tao Yang
@version    : 1.0
'''

import json

import devsim

from .model_create import *
from .physics_drift_diffusion import *

def switch_cylindrical_coordinate(device, region):
    devsim.set_parameter(device=device, name="raxis_variable", value="x")
    devsim.set_parameter(device=device, name="raxis_zero",     value=0)
    devsim.cylindrical_node_volume(device=device, region=region)
    devsim.cylindrical_edge_couple(device=device, region=region)
    devsim.cylindrical_surface_area(device=device, region=region)
    devsim.set_parameter(name="node_volume_model",value="CylindricalNodeVolume")
    devsim.set_parameter(name="edge_couple_model",value="CylindricalEdgeCouple")
    devsim.set_parameter(name="edge_node0_volume_model",value="CylindricalEdgeNodeVolume@n0")
    devsim.set_parameter(name="edge_node1_volume_model",value="CylindricalEdgeNodeVolume@n1")
    devsim.set_parameter(name="element_edge_couple_model",value="ElementCylindricalEdgeCouple")
    devsim.set_parameter(name="element_node0_volume_model",value="ElementCylindricalNodeVolume@en0")
    devsim.set_parameter(name="element_node1_volume_model",value="ElementCylindricalNodeVolume@en1")


def PotentialOnlyInitialSolution(device, region, paras, circuit_contacts, set_contact_type=None):
    if paras["Cylindrical_coordinate"]==True:
        switch_cylindrical_coordinate(device,region)
    else:
        pass
    # Create Potential, Potential@n0, Potential@n1
    CreateSolution(device, region, "Potential")
    
    CreateNodeModel(device, region, "InitialElectron", "abs(NetDoping)")
    CreateNodeModel(device, region, "InitialHole", "abs(NetDoping)")
    devsim.edge_from_node_model(device=device,region=region,node_model="InitialElectron")
    devsim.edge_from_node_model(device=device,region=region,node_model="InitialHole")
    CreateSiliconPotentialOnly(device, region)
    CreateDiamondPotentialOnly(device, region)
    if paras["weightfield"]==True:
        try:
            CreateOxidePotentialOnly(device=device, region="SiO2", update_type="default")
            for interface in devsim.get_interface_list(device=device):
                CreateSiliconOxideInterface(device=device, interface=interface)
        except:
            print("================RASER info===============\nThere is no SiO2 layer in your detector\n===========warning============")
            pass 
    else:
        pass
    # Set up the contacts applying a bias
    for i in devsim.get_contact_list(device=device):
        if set_contact_type and i in set_contact_type:
            contact_type = set_contact_type[i]
        else:
            contact_type = {"type" : "Ohmic"}
        devsim.set_parameter(device=device, name=GetContactBiasName(i), value=0)
        if str(circuit_contacts) in i :
            CreateSiliconPotentialOnlyContact(device, region, i, contact_type, True)
            CreateDiamondPotentialOnlyContact(device, region, i, contact_type, True)
            if paras["weightfield"]==True:
                try:
                    CreateOxideContact(device=device, region="SiO2", contact=i)
                except:
                    print("===============RASER info===============\nThere is no SiO2 layer in your detector\n===========warning============")
                    pass 
        else:
            ###print "FIX THIS"
            ### it is more correct for the bias to be 0, and it looks like there is side effects
            devsim.set_parameter(device=device, name=GetContactBiasName(i), value="0.0")
            CreateSiliconPotentialOnlyContact(device, region, i, contact_type)
            CreateDiamondPotentialOnlyContact(device, region, i, contact_type)
            if paras["weightfield"]==True:
                try:
                    CreateOxideContact(device=device, region="SiO2", contact=i)
                except:
                    print("Waring info:++++++++++++++++++++++++++++++++++++++++++/nWarning: There is no SiO2 layer in your detector\n++++++++++++++++++++++++++++++++++++++")
                    pass 

def DriftDiffusionInitialSolution(device, region, paras, irradiation_model=None, irradiation_flux=1e15, impact_model=None, circuit_contacts=None, set_contact_type=None):
    if paras["Cylindrical_coordinate"]==True:
        switch_cylindrical_coordinate(device,region)
    else:
        pass
    ####
    #### drift diffusion solution variables
    ####
    CreateSolution(device, region, "Electrons")
    CreateSolution(device, region, "Holes")

    ####
    #### create initial guess from dc only solution
    ####
    devsim.set_node_values(device=device, region=region, name="Electrons", init_from="IntrinsicElectrons")
    devsim.set_node_values(device=device, region=region, name="Holes",     init_from="IntrinsicHoles")
    #devsim.set_node_values(device=device, region=region, name="Electrons", init_from="InitialElectron")
    #devsim.set_node_values(device=device, region=region, name="Holes",     init_from="InitialHole")

    ###
    ### Set up equations
    ###
    
#    CreateSiliconDriftDiffusion(device, region, irradiation_model=irradiation_model, irradiation_flux=irradiation_flux, impact_model=impact_model)
#    for i in devsim.get_contact_list(device=device):
#        if set_contact_type and i in set_contact_type:
#            contact_type = set_contact_type[i]
#        else:
#            contact_type = {"type" : "Ohmic"}
#
#        if str(circuit_contacts) in i:
#            devsim.set_parameter(device=device, name=GetContactBiasName(i), value="0.0")
#            CreateSiliconDriftDiffusionAtContact(device, region, i, contact_type, True)
#        else:
#            devsim.set_parameter(device=device, name=GetContactBiasName(i), value="0.0")
#            CreateSiliconDriftDiffusionAtContact(device, region, i, contact_type)

    CreateDiamondDriftDiffusion(device, region, irradiation_model=irradiation_model, irradiation_flux=irradiation_flux, impact_model=impact_model)
    for i in devsim.get_contact_list(device=device):
        if set_contact_type and i in set_contact_type:
            contact_type = set_contact_type[i]
        else:
            contact_type = {"type" : "Ohmic"}

        if str(circuit_contacts) in i:
            devsim.set_parameter(device=device, name=GetContactBiasName(i), value="0.0")
            CreateDiamondDriftDiffusionAtContact(device, region, i, contact_type, True)
        else:
            devsim.set_parameter(device=device, name=GetContactBiasName(i), value="0.0")
            CreateDiamondDriftDiffusionAtContact(device, region, i, contact_type)


