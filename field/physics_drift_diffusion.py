#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

'''
Description:  physics_drift_diffusion.py
@Date       : 2023/12/05 13:10:36
@Author     : Chenxi Fu
@Original   : DEVSIM LLC
@version    : 1.0
'''

from devsim import *
from .model_create import *
from .physics_avalanche import CreateImpactGeneration
from .physics_irradiation import CreateIrradiation

contactcharge_edge="contactcharge_edge"
ece_name="ElectronContinuityEquation"
hce_name="HoleContinuityEquation"
celec_model = "(1e-10 + 0.5*abs(NetDoping+(NetDoping^2 + 4 * n_i^2)^(0.5)))"
chole_model = "(1e-10 + 0.5*abs(-NetDoping+(NetDoping^2 + 4 * n_i^2)^(0.5)))"

def GetContactBiasName(contact):
    return "{0}_bias".format(contact)

def GetContactNodeModelName(contact):
    return "{0}nodemodel".format(contact)

def CreateSiliconPotentialOnly(device, region):
    '''
      Creates the physical models for a Silicon region
    '''
    if not InNodeModelList(device, region, "Potential"):
        print("Creating Node Solution Potential")
        CreateSolution(device, region, "Potential")
    elec_i = "n_i*exp(Potential/Volt_thermal)"
    hole_i = "n_i^2/IntrinsicElectrons"
    charge_i = "kahan3(IntrinsicHoles, -IntrinsicElectrons, NetDoping)"
    pcharge_i = "-ElectronCharge * IntrinsicCharge"

    # require NetDoping
    for i in (
        ("IntrinsicElectrons", elec_i),
        ("IntrinsicHoles", hole_i),
        ("IntrinsicCharge", charge_i),
        ("PotentialIntrinsicCharge", pcharge_i)
    ):
        n = i[0]
        e = i[1]
        CreateNodeModel(device, region, n, e)
        CreateNodeModelDerivative(device, region, n, e, "Potential")

    ### TODO: Edge Average Model
    for i in (
        ("ElectricField",     "(Potential@n0-Potential@n1)*EdgeInverseLength"),
        ("PotentialEdgeFlux", "Permittivity * ElectricField")
    ):
        n = i[0]
        e = i[1]
        CreateEdgeModel(device, region, n, e)
        CreateEdgeModelDerivatives(device, region, n, e, "Potential")

    equation(device=device, region=region, name="PotentialEquation", variable_name="Potential",
             node_model="PotentialIntrinsicCharge", edge_model="PotentialEdgeFlux", variable_update="log_damp")


def CreateSiliconPotentialOnlyContact(device, region, contact, is_circuit=False):
    '''
      Creates the potential equation at the contact
      if is_circuit is true, than use node given by GetContactBiasName
    '''
    # Means of determining contact charge
    # Same for all contacts
    #### TODO: This is the same as D-Field
    if not InEdgeModelList(device, region, "contactcharge_edge"):
        CreateEdgeModel(device, region, "contactcharge_edge", "Permittivity*ElectricField")
        CreateEdgeModelDerivatives(device, region, "contactcharge_edge", "Permittivity*ElectricField", "Potential")

    # set_parameter(device=device, region=region, name=GetContactBiasName(contact), value=0.0)

    contact_model = "Potential -{0} + ifelse(NetDoping > 0, \
                    -Volt_thermal*log({1}/n_i), \
                    Volt_thermal*log({2}/n_i))".format(GetContactBiasName(contact), celec_model, chole_model)

    contact_model_name = GetContactNodeModelName(contact)
    CreateContactNodeModel(device, contact, contact_model_name, contact_model)
    # Simplify it too complicated
    CreateContactNodeModel(device, contact, "{0}:{1}".format(contact_model_name,"Potential"), "1")
    if is_circuit:
        CreateContactNodeModel(device, contact, "{0}:{1}".format(contact_model_name,GetContactBiasName(contact)), "-1")

    if is_circuit:
        contact_equation(device=device, contact=contact, name="PotentialEquation",
                         node_model=contact_model_name, edge_model="",
                         node_charge_model="", edge_charge_model="contactcharge_edge",
                         node_current_model="", edge_current_model="", circuit_node=GetContactBiasName(contact))
    else:
        contact_equation(device=device, contact=contact, name="PotentialEquation",
                         node_model=contact_model_name, edge_model="",
                         node_charge_model="", edge_charge_model="contactcharge_edge",
                         node_current_model="", edge_current_model="")


def CreateBernoulli (device, region):
    '''
    Creates the Bernoulli function for Scharfetter Gummel
    '''
    #### test for requisite models here
    EnsureEdgeFromNodeModelExists(device, region, "Potential")
    vdiffstr="(Potential@n0 - Potential@n1)/Volt_thermal"
    CreateEdgeModel(device, region, "vdiff", vdiffstr)
    CreateEdgeModel(device, region, "vdiff:Potential@n0",  "Volt_thermal^(-1)")
    CreateEdgeModel(device, region, "vdiff:Potential@n1",  "-vdiff:Potential@n0")
    CreateEdgeModel(device, region, "Bern01",              "B(vdiff)")
    CreateEdgeModel(device, region, "Bern01:Potential@n0", "dBdx(vdiff) * vdiff:Potential@n0")
    CreateEdgeModel(device, region, "Bern01:Potential@n1", "-Bern01:Potential@n0")
    #identity of Bernoulli functions
    # CreateEdgeModel(device, region, "Bern10",              "Bern01 + vdiff")
    # CreateEdgeModel(device, region, "Bern10:Potential@n0", "Bern01:Potential@n0 + vdiff:Potential@n0")
    # CreateEdgeModel(device, region, "Bern10:Potential@n1", "Bern01:Potential@n1 + vdiff:Potential@n1")


def CreateElectronCurrent(device, region, mu_n):
    '''
    Electron current
    '''
    EnsureEdgeFromNodeModelExists(device, region, "Potential")
    EnsureEdgeFromNodeModelExists(device, region, "Electrons")
    EnsureEdgeFromNodeModelExists(device, region, "Holes")
    # Make sure the bernoulli functions exist
    if not InEdgeModelList(device, region, "Bern01"):
        CreateBernoulli(device, region)
    #### test for requisite models here
    # Jn = "ElectronCharge*{0}*EdgeInverseLength*Volt_thermal*(Electrons@n1*Bern10 - Electrons@n0*Bern01)".format(mu_n)
    Jn = "ElectronCharge*{0}*EdgeInverseLength*Volt_thermal*kahan3(Electrons@n1*Bern01,  Electrons@n1*vdiff,  -Electrons@n0*Bern01)".format(mu_n)
    # Jn = "ElectronCharge*{0}*EdgeInverseLength*Volt_thermal*((Electrons@n1-Electrons@n0)*Bern01 +  Electrons@n1*vdiff)".format(mu_n)

    CreateEdgeModel(device, region, "ElectronCurrent", Jn)
    for i in ("Electrons", "Potential", "Holes"):
        CreateEdgeModelDerivatives(device, region, "ElectronCurrent", Jn, i)


def CreateHoleCurrent(device, region, mu_p):
    '''
    Hole current
    '''
    EnsureEdgeFromNodeModelExists(device, region, "Potential")
    EnsureEdgeFromNodeModelExists(device, region, "Holes")
    # Make sure the bernoulli functions exist
    if not InEdgeModelList(device, region, "Bern01"):
        CreateBernoulli(device, region)
    ##### test for requisite models here
    # Jp ="-ElectronCharge*{0}*EdgeInverseLength*Volt_thermal*(Holes@n1*Bern01 - Holes@n0*Bern10)".format(mu_p)
    Jp ="-ElectronCharge*{0}*EdgeInverseLength*Volt_thermal*kahan3(Holes@n1*Bern01, -Holes@n0*Bern01, -Holes@n0*vdiff)".format(mu_p)
    # Jp ="-ElectronCharge*{0}*EdgeInverseLength*Volt_thermal*((Holes@n1 - Holes@n0)*Bern01 - Holes@n0*vdiff)".format(mu_p)
    CreateEdgeModel(device, region, "HoleCurrent", Jp)
    for i in ("Holes", "Potential", "Electrons"):
        CreateEdgeModelDerivatives(device, region, "HoleCurrent", Jp, i)


def PrintCurrents(device, contact):
    '''
       print out contact currents
    '''
    # TODO add charge
    contact_bias_name = GetContactBiasName(contact)
    electron_current= get_contact_current(device=device, contact=contact, equation=ece_name)
    hole_current    = get_contact_current(device=device, contact=contact, equation=hce_name)
    total_current   = electron_current + hole_current                                        
    voltage         = get_parameter(device=device, name=GetContactBiasName(contact))
    print("{0}\t{1}\t{2}\t{3}\t{4}".format(contact, voltage, electron_current, hole_current, total_current))


def CreateSRH(device, region, irradiation_label):
    USRH="(Electrons*Holes - n_i^2)/(taup*(Electrons + n1) + taun*(Holes + p1))"
    Gn = "-ElectronCharge * (USRH+U_const)"
    Gp = "+ElectronCharge * (USRH+U_const)"

    if irradiation_label != None:
        Gn = Gn + "-ElectronCharge * U_r"
        Gp = Gp + "+ElectronCharge * U_r"

    CreateNodeModel(device, region, "USRH", USRH)
    CreateNodeModel(device, region, "ElectronGeneration", Gn)
    CreateNodeModel(device, region, "HoleGeneration", Gp)
    for i in ("Electrons", "Holes"):
        CreateNodeModelDerivative(device, region, "USRH", USRH, i)
        CreateNodeModelDerivative(device, region, "ElectronGeneration", Gn, i)
        CreateNodeModelDerivative(device, region, "HoleGeneration", Gp, i)
    edge_from_node_model(device=device,region=region,node_model="USRH")
    edge_from_node_model(device=device,region=region,node_model="ElectronGeneration")
    edge_from_node_model(device=device,region=region,node_model="HoleGeneration")
    edge_from_node_model(device=device,region=region,node_model="U_const")
    #CreateEdgeModelDerivatives(device,region,)
    

def CreateECE(device, region, mu_n, impact_label):
    CreateElectronCurrent(device, region, mu_n)

    NCharge = "-ElectronCharge * Electrons"
    CreateNodeModel(device, region, "NCharge", NCharge)
    CreateNodeModelDerivative(device, region, "NCharge", NCharge, "Electrons")
    if impact_label != None:
        CreateImpactGeneration(device, region, impact_label)
        equation(device=device, region=region, name="ElectronContinuityEquation", variable_name="Electrons",
                time_node_model = "NCharge",
                edge_model="ElectronCurrent", variable_update="positive", node_model="ElectronGeneration",
                edge_volume_model="ImpactGen_n")
    else:
        equation(device=device, region=region, name="ElectronContinuityEquation", variable_name="Electrons",
                time_node_model = "NCharge",
                edge_model="ElectronCurrent", variable_update="positive", node_model="ElectronGeneration")
    

def CreateHCE(device, region, mu_p, impact_label):
    CreateHoleCurrent(device, region, mu_p)
    PCharge = "ElectronCharge * Holes"
    CreateNodeModel(device, region, "PCharge", PCharge)
    CreateNodeModelDerivative(device, region, "PCharge", PCharge, "Holes")
    if impact_label != None:
        CreateImpactGeneration(device, region, impact_label)
        equation(device=device, region=region, name="HoleContinuityEquation", variable_name="Holes",
                time_node_model = "PCharge",
                edge_model="HoleCurrent", variable_update="positive", node_model="HoleGeneration",
                edge_volume_model="ImpactGen_p")
    else:
        equation(device=device, region=region, name="HoleContinuityEquation", variable_name="Holes",
                time_node_model = "PCharge",
                edge_model="HoleCurrent", variable_update="positive", node_model="HoleGeneration")
    

def CreatePE(device, region, irradiation_label):
    pne = "-ElectronCharge*kahan3(Holes, -Electrons, NetDoping)"
    if irradiation_label != None:
        pne = "-ElectronCharge*kahan3(Holes, -Electrons, kahan3(NetDoping, TrappedHoles, -TrappedElectrons))"

    CreateNodeModel(device, region, "PotentialNodeCharge", pne)
    CreateNodeModelDerivative(device, region, "PotentialNodeCharge", pne, "Electrons")
    CreateNodeModelDerivative(device, region, "PotentialNodeCharge", pne, "Holes")

    equation(device=device, region=region, name="PotentialEquation", variable_name="Potential",
             node_model="PotentialNodeCharge", edge_model="PotentialEdgeFlux",
             time_node_model="", variable_update="log_damp")


def CreateSiliconDriftDiffusion(device, region, mu_n="mu_n", mu_p="mu_p", irradiation_label=None, irradiation_flux=1e15, impact_label=None):
    if irradiation_label != None:
        CreateIrradiation(device, region, label=irradiation_label, flux=irradiation_flux)
    else:
        CreateNodeModel(device, region, "TrappingRate_n", "0")
        CreateNodeModel(device, region, "TrappingRate_p", "0")
        # For carrier lifetime

    CreatePE(device, region, irradiation_label)
    CreateBernoulli(device, region)
    CreateSRH(device, region, irradiation_label)
    CreateECE(device, region, mu_n, impact_label=impact_label)
    CreateHCE(device, region, mu_p, impact_label=impact_label)


def CreateSiliconDriftDiffusionAtContact(device, region, contact, is_circuit=False): 
    '''
      Restrict electrons and holes to their equilibrium values
      Integrates current into circuit
    '''
    contact_electrons_model = "Electrons - ifelse(NetDoping > 0, {0}, n_i^2/{1})".format(celec_model, chole_model)
    contact_holes_model = "Holes - ifelse(NetDoping < 0, +{1}, +n_i^2/{0})".format(celec_model, chole_model)
    contact_electrons_name = "{0}nodeelectrons".format(contact)
    contact_holes_name = "{0}nodeholes".format(contact)

    CreateContactNodeModel(device, contact, contact_electrons_name, contact_electrons_model)
    #TODO: The simplification of the ifelse statement is time consuming
    # CreateContactNodeModelDerivative(device, contact, contact_electrons_name, contact_electrons_model, "Electrons")
    CreateContactNodeModel(device, contact, "{0}:{1}".format(contact_electrons_name, "Electrons"), "1")

    CreateContactNodeModel(device, contact, contact_holes_name, contact_holes_model)
    CreateContactNodeModel(device, contact, "{0}:{1}".format(contact_holes_name, "Holes"), "1")

    #TODO: keyword args
    if is_circuit:
        contact_equation(device=device, contact=contact, name="ElectronContinuityEquation",
                         node_model=contact_electrons_name,
                         edge_current_model="ElectronCurrent", circuit_node=GetContactBiasName(contact))

        contact_equation(device=device, contact=contact, name="HoleContinuityEquation",
                         node_model=contact_holes_name,
                         edge_current_model="HoleCurrent", circuit_node=GetContactBiasName(contact))

    else:
        contact_equation(device=device, contact=contact, name="ElectronContinuityEquation",
                         node_model=contact_electrons_name,
                         edge_current_model="ElectronCurrent")

        contact_equation(device=device, contact=contact, name="HoleContinuityEquation",
                         node_model=contact_holes_name,
                         edge_current_model="HoleCurrent")


def CreateOxidePotentialOnly(device, region, update_type="default"):
    '''
      Create electric field model in oxide
      Creates Potential solution variable if not available
    '''
    if not InNodeModelList(device, region, "Potential"):
        print("Creating Node Solution Potential")
        CreateSolution(device, region, "Potential")

    efield="(Potential@n0 - Potential@n1)*EdgeInverseLength"
    # this needs to remove derivatives w.r.t. independents
    CreateEdgeModel(device, region, "ElectricField", efield)
    CreateEdgeModelDerivatives(device, region, "ElectricField", efield, "Potential")
    dfield="Permittivity*ElectricField"
    CreateEdgeModel(device, region, "PotentialEdgeFlux", dfield)
    CreateEdgeModelDerivatives(device, region, "PotentialEdgeFlux", dfield, "Potential")
    equation(device=device, region=region, name="PotentialEquation", variable_name="Potential",
             edge_model="PotentialEdgeFlux", variable_update=update_type)


#in the future, worry about workfunction
def CreateOxideContact(device, region, contact):
    conteq="Permittivity*ElectricField"
    contact_bias_name  = GetContactBiasName(contact)
    contact_model_name = GetContactNodeModelName(contact)
    eq = "Potential - {0}".format(contact_bias_name)
    CreateContactNodeModel(device, contact, contact_model_name, eq)
    CreateContactNodeModelDerivative(device, contact, contact_model_name, eq, "Potential")

    #TODO: make everyone use dfield
    if not InEdgeModelList(device, region, contactcharge_edge):
        CreateEdgeModel(device, region, contactcharge_edge, "Permittivity*ElectricField")
        CreateEdgeModelDerivatives(device, region, contactcharge_edge, "Permittivity*ElectricField", "Potential")

    contact_equation(device=device, contact=contact, name="PotentialEquation",
                     node_model=contact_model_name, edge_charge_model= contactcharge_edge)


def CreateSiliconOxideInterface(device, interface):
    '''
      continuous potential at interface
    '''
    model_name = CreateContinuousInterfaceModel(device, interface, "Potential")
    interface_equation(device=device, interface=interface, name="PotentialEquation", interface_model=model_name, type="continuous")

#
##TODO: similar model for silicon/silicon interface
## should use quasi-fermi potential
def CreateSiliconSiliconInterface(device, interface):
    '''
      Enforces potential, electron, and hole continuity across the interface
    '''
    CreateSiliconOxideInterface(device, interface)
    ename = CreateContinuousInterfaceModel(device, interface, "Electrons")
    interface_equation(device=device, interface=interface, name="ElectronContinuityEquation", interface_model=ename, type="continuous")
    hname = CreateContinuousInterfaceModel(device, interface, "Holes")
    interface_equation(device=device, interface=interface, name="HoleContinuityEquation", interface_model=hname, type="continuous")

'''
def CreateMobility(device, region):

    if not InEdgeModelList(device, region, "ElectricField"):
        
        CreateEdgeModel(device, region, "ElectricField", "(Potential@n0-Potential@n1)*EdgeInverseLength")
        CreateEdgeModelDerivatives(device, region, "ElectricField", "(Potential@n0-Potential@n1)*EdgeInverseLength", "Potential")

    # debugE = devsim.get_edge_model_values(device, region, "Eparallel")
    # print("\n\n*********************************\n")
    # print(debugE)
    # print("\n*********************************\n\n")

    #mu_n = "{0} / (pow(1.0 + pow({1} * ElectricField /{2}, {3}), 1.0 / {4}))".format( str(n_lfm), str(n_lfm), str(n_vsatp), str(n_betap), str(n_betap))
    mu_n = "n_lfm / (pow(1.0 + pow(n_lfm * 40.0 / n_vsatp, n_betap), 1.0 / n_betap))"

    #mu_p = "{0} / (pow(1.0 + pow({1} * ElectricField /{2}, {3}), 1.0 / {4}))".format( str(p_lfm), str(p_lfm), str(p_vsatp), str(p_betap), str(p_betap))
    mu_p = "p_lfm / (pow(1.0 + pow(p_lfm * 40.0 / p_vsatp, p_betap), 1.0/p_betap))"

    CreateEdgeModel(device, region, "ElectronMobility", mu_n)
    CreateEdgeModel(device, region, "HoleMobility", mu_p)

    CreateEdgeModelDerivatives(device, region,"ElectronMobility", mu_n, "Potential")
    CreateEdgeModelDerivatives(device, region, "HoleMobility", mu_p, "Potential")
'''

