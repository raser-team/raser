'''
Description:  Initial.py
@Date       : 2022/10/25 16:40:46
@Author     : Tao Yang
@version    : 1.0
'''

import devsim
from .model_create import *
from .physics_drift_diffusion import *

def InitialSolution(device, region, circuit_contacts=None):
    # Create Potential, Potential@n0, Potential@n1
    CreateSolution(device, region, "Potential")
    
    CreateNodeModel(device, region, "InitialElectron", "abs(NetDoping)")
    CreateNodeModel(device, region, "InitialHole", "abs(NetDoping)")
    devsim.edge_from_node_model(device=device,region=region,node_model="InitialElectron")
    devsim.edge_from_node_model(device=device,region=region,node_model="InitialHole")
    
    # Create potential only physical models
    CreateSiliconPotentialOnly(device, region)


    # Set up the contacts applying a bias
    for i in devsim.get_contact_list(device=device):
        if circuit_contacts and i in circuit_contacts:
            CreateSiliconPotentialOnlyContact(device, region, i, True)
        else:
            ###print "FIX THIS"
            ### it is more correct for the bias to be 0, and it looks like there is side effects
            devsim.set_parameter(device=device, name=GetContactBiasName(i), value=0.0)
            CreateSiliconPotentialOnlyContact(device, region, i)


def DriftDiffusionInitialSolution(device, region, irradiation_label=None, irradiation_flux=1e15, impact_label=None, circuit_contacts=None):
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
    CreateSiliconDriftDiffusion(device, region, irradiation_label=irradiation_label, irradiation_flux=irradiation_flux, impact_label=impact_label)
    for i in devsim.get_contact_list(device=device):
        if circuit_contacts and i in circuit_contacts:
            CreateSiliconDriftDiffusionAtContact(device, region, i, True)
        else:
            CreateSiliconDriftDiffusionAtContact(device, region, i)

