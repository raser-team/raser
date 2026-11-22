#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

'''
Description:  physics_irradiation.py
@Date       : 2023/10/20
@Author     : XingChen Li, Chenxi Fu, Zhan Li
@version    : 3.0
'''

import devsim
from .model_create import *

CARRIER_FLOOR = 1.0  # cm^-3


def floored(expression):
    """`expression` with the densities Electrons and Holes held at CarrierFloor or above."""
    return (expression.replace("Electrons", "ifelse(Electrons > CarrierFloor, Electrons, CarrierFloor)")
            .replace("Holes", "ifelse(Holes > CarrierFloor, Holes, CarrierFloor)"))


def irradiation_defects(device, region, label, custom_defect=None):
    """The defects of the irradiation model `label`, as a list of dicts.

    A label that names no built-in model takes `custom_defect` as the list.
    """
    if label == 'XingChen':
        return CreateIrradiationModel_XingChen(device, region)
    elif label == 'Perugia':
        return CreateIrradiationModel_Perugia(device, region)
    elif label == 'Schwandt':
        return CreateIrradiationModel_Schwandt(device, region)
    elif label == 'CommonDefect':
        if devsim.get_material(device=device, region=region) == "Diamond":
            return CreateIntrinsicModel_DiamondCommonDefect(device, region)
        return CreateIntrinsicModel_SiCCommonDefect(device, region)
    return custom_defect


def set_fluence(device, region, defects, flux):
    """Set the trap concentration N_t_irr_<name> [cm^-3] of every defect to
    its background N_t0 [cm^-3] plus g_int [cm^-1] times the fluence `flux` [cm^-2]."""
    for defect in defects:
        devsim.set_parameter(device=device, region=region, name="N_t_irr_" + defect["name"], value=defect.get("N_t0", 0.0) + defect["g_int"] * flux)


def set_defect_parameters(device, region, defects, flux):
    """Set the parameters the defect terms read: the capture cross sections
    sigma_n_irr_<name>, sigma_p_irr_<name> [cm^2], the trap concentration
    N_t_irr_<name> [cm^-3] at the fluence `flux` [cm^-2], the level E_t_<name>
    [J], and CarrierFloor [cm^-3] in a diamond region."""
    if devsim.get_material(device=device, region=region) == "Diamond":
        devsim.set_parameter(device=device, region=region, name="CarrierFloor", value=CARRIER_FLOOR)
    for defect in defects:
        name = defect["name"]
        devsim.set_parameter(device=device, region=region, name="sigma_n_irr_"+name, value=defect["sigma_n_irr"])
        devsim.set_parameter(device=device, region=region, name="sigma_p_irr_"+name, value=defect["sigma_p_irr"])
        devsim.set_parameter(device=device, region=region, name="E_t_"+name, value=defect["E_t_ev"] * 1.6*1e-19)
    set_fluence(device, region, defects, flux)


def CreateIrradiation(device, region, label="XingChen", flux=1e15, custom_defect = {}):

    # if not InEdgeModelList(device, region, "ElectricField"):
    #     CreateEdgeModel(device, region, "ElectricField", "(Potential@n0-Potential@n1)*EdgeInverseLength")
    #     CreateEdgeModelDerivatives(device, region, "ElectricField", "(Potential@n0-Potential@n1)*EdgeInverseLength", "Potential")

    # TODO: change labels into formal names
    defects = irradiation_defects(device, region, label, custom_defect)

    # In a diamond region the carrier densities in the defect terms are held
    # at CARRIER_FLOOR or above.
    diamond = devsim.get_material(device=device, region=region) == "Diamond"
    set_defect_parameters(device, region, defects, flux)

    TrappedElectrons="0"
    TrappedHoles="0"
    TrappingRate_n="0"
    TrappingRate_p="0"
    U_r = "0"

    for defect in defects:
        name, E_t_ev, g_int, sigma_n_irr, sigma_p_irr = ( defect['name'], defect['E_t_ev'], defect['g_int'], defect['sigma_n_irr'], defect['sigma_p_irr'],
        )
        e = 1.6*1e-19
        E_t = E_t_ev * e

        r_n = "(vel_mean * sigma_n_irr_{name})".format(name=name)#c_n
        n_1 = "(N_c * exp(-(E_g/2 - E_t_{name})/k_T))".format(name=name)#e_n
        r_p = "(vel_mean * sigma_p_irr_{name})".format(name=name)#c_p
        p_1 = "(N_v * exp(-(E_t_{name} - (-E_g/2))/k_T))".format(name=name)#e_p
        n_t_irr_n = "+(N_t_irr_{name}*(Electrons*{r_n}+{p_1}*{r_p})/({r_n}*(Electrons+{n_1})+{r_p}*(Holes+{p_1})))".format(name=name,r_n=r_n,n_1=n_1,r_p=r_p,p_1=p_1)
        n_t_irr_p = "+(N_t_irr_{name}*(Holes*{r_p}+{n_1}*{r_n})/({r_n}*(Electrons+{n_1})+{r_p}*(Holes+{p_1})))".format(name=name,r_n=r_n,n_1=n_1,r_p=r_p,p_1=p_1)
        # An electron is captured by a defect that holds none, a hole by one that holds an electron.
        trap_n = "+(vel_mean * sigma_n_irr_{name})*(N_t_irr_{name}*(Holes*{r_p}+{n_1}*{r_n})/({r_n}*(Electrons+{n_1})+{r_p}*(Holes+{p_1})))".format(name=name,r_n=r_n,n_1=n_1,r_p=r_p,p_1=p_1)
        trap_p = "+(vel_mean * sigma_p_irr_{name})*(N_t_irr_{name}*(Electrons*{r_n}+{p_1}*{r_p})/({r_n}*(Electrons+{n_1})+{r_p}*(Holes+{p_1})))".format(name=name,r_n=r_n,n_1=n_1,r_p=r_p,p_1=p_1)
        U_r_i="+(N_t_irr_{name}*{r_n}*{r_p}*(Electrons*Holes-n_i^2)/({r_n}*(Electrons+{n_1})+{r_p}*(Holes+{p_1})))".format(name=name,r_n=r_n,n_1=n_1,r_p=r_p,p_1=p_1)
        if diamond:
            n_t_irr_n, n_t_irr_p, trap_n, trap_p, U_r_i = (
                floored(expression)
                for expression in (n_t_irr_n, n_t_irr_p, trap_n, trap_p, U_r_i)
            )

        # The charge a defect carries: an acceptor is negative while it holds
        # an electron, a donor positive while it holds none.
        if diamond:
            # peiyao's charge: every defect adds N f to TrappedElectrons and N (1 - f) to TrappedHoles
            TrappedElectrons=TrappedElectrons+n_t_irr_n
            TrappedHoles=TrappedHoles+n_t_irr_p
        elif defect.get("type") == "acceptor":
            TrappedElectrons=TrappedElectrons+n_t_irr_n
        elif defect.get("type") == "donor":
            TrappedHoles=TrappedHoles+n_t_irr_p
        else:
            raise ValueError('the defect {} must have "type": "donor" or "acceptor", it has {}'.format(name, defect.get("type")))
        TrappingRate_n=TrappingRate_n+trap_n
        TrappingRate_p=TrappingRate_p+trap_p
        U_r = U_r+U_r_i
    

    CreateNodeModel(device, region, "TrappedElectrons", TrappedElectrons)
    CreateNodeModel(device, region, "TrappedHoles", TrappedHoles)
    for i in ("Electrons", "Holes", "Potential"):
        CreateNodeModelDerivative(device, region, "TrappedElectrons", TrappedElectrons, i)
        CreateNodeModelDerivative(device, region, "TrappedHoles", TrappedHoles, i)
    
    CreateNodeModel(device, region, "U_r", U_r)
    for i in ("Electrons", "Holes"):
        CreateNodeModelDerivative(device, region, "U_r", U_r, i)

    CreateNodeModel(device, region, "TrappingRate_n", TrappingRate_n)
    CreateNodeModel(device, region, "TrappingRate_p", TrappingRate_p)


def CreateIrradiationModel_XingChen(device, region):
    """
    Si Irradiation model
    """
    
    defects = []
    defects.append({"name" : "E30K", "type" : "donor", "E_t_ev" : 0.56-0.1,   "g_int" : 2.0810, "sigma_n_irr" : 2.300e-14, "sigma_p_irr" : 2.920e-16,})
    defects.append({"name" : "V3", "type" : "acceptor",   "E_t_ev" : 0.56-0.458, "g_int" : 1.6504, "sigma_n_irr" : 2.551e-14, "sigma_p_irr" : 1.551e-13,})
    defects.append({"name" : "Ip", "type" : "acceptor",   "E_t_ev" : 0.56-0.545, "g_int" : 0.6936, "sigma_n_irr" : 4.478e-15, "sigma_p_irr" : 6.709e-15,})
    defects.append({"name" : "H220", "type" : "donor", "E_t_ev" : -0.56+0.48, "g_int" : 2.6112, "sigma_n_irr" : 4.166e-15, "sigma_p_irr" : 1.965e-16,})
    defects.append({"name" : "CiOi", "type" : "donor", "E_t_ev" : -0.56+0.36, "g_int" : 1.6511, "sigma_n_irr" : 3.230e-17, "sigma_p_irr" : 2.036e-14,})

    return defects


def CreateIrradiationModel_Perugia(device, region):
    """
    Si Irradiation model
    """

    defects = []
    defects.append({"name" : "DA1", "type" : "acceptor", "E_t_ev" : 0.56-0.42, "g_int" : 1.613, "sigma_n_irr" : 1e-15,     "sigma_p_irr" : 1e-14,})
    defects.append({"name" : "DA2", "type" : "acceptor", "E_t_ev" : 0.56-0.46, "g_int" : 0.9,   "sigma_n_irr" : 7e-15,     "sigma_p_irr" : 7e-14,})
    defects.append({"name" : "DD", "type" : "donor",  "E_t_ev" : -0.56+0.36, "g_int" : 0.9,   "sigma_n_irr" : 3.23e-13,  "sigma_p_irr" : 3.23e-14,})

    return defects


def CreateIrradiationModel_Schwandt(device, region):
    """
    Si Irradiation model
    """

    defects = []
    defects.append({"name" : "E30K", "type" : "donor", "E_t_ev" : 0.56-0.1,   "g_int" : 0.0497, "sigma_n_irr" : 2.300e-14, "sigma_p_irr" : 2.920e-16,})
    defects.append({"name" : "V3", "type" : "acceptor",   "E_t_ev" : 0.56-0.458, "g_int" : 0.6447, "sigma_n_irr" : 2.551e-14, "sigma_p_irr" : 1.511e-13,})
    defects.append({"name" : "Ip", "type" : "acceptor",   "E_t_ev" : 0.56-0.545, "g_int" : 0.4335, "sigma_n_irr" : 4.478e-15, "sigma_p_irr" : 6.709e-15,})
    defects.append({"name" : "H220", "type" : "donor", "E_t_ev" : -0.56+0.48, "g_int" : 0.5978, "sigma_n_irr" : 4.166e-15, "sigma_p_irr" : 1.965e-16,})
    defects.append({"name" : "CiOi", "type" : "donor", "E_t_ev" : -0.56+0.36, "g_int" : 0.3780, "sigma_n_irr" : 3.230e-17, "sigma_p_irr" : 2.036e-14,})

    return defects

def CreateIntrinsicModel_SiCCommonDefect(device, region):
    """
    SiC Intrinsic Defect model
    """
    
    defects = []
    defects.append({"name" : "Z12", "type" : "acceptor",  "E_t_ev" : 1.63-0.67, "g_int" : 1, "sigma_n_irr" : 3e-16, "sigma_p_irr" : 2e-12,})
    defects.append({"name" : "EH67", "type" : "donor", "E_t_ev" : 1.63-1.65, "g_int" : 1, "sigma_n_irr" : 2e-17, "sigma_p_irr" : 3e-17,})

    return defects


def CreateIntrinsicModel_DiamondCommonDefect(device, region):
    """
    Diamond background defects
    """

    defects = []
    defects.append({"name" : "BoronAcceptor", "type" : "acceptor", "E_t_ev" : -5.47/2+0.37, "g_int" : 0, "N_t0" : 2.0e14, "sigma_n_irr" : 1.0e-15, "sigma_p_irr" : 2.0e-14,})
    defects.append({"name" : "SubstitutionalNitrogen_P1", "type" : "donor", "E_t_ev" : 5.47/2-1.70, "g_int" : 0, "N_t0" : 5.0e14, "sigma_n_irr" : 2.0e-14, "sigma_p_irr" : 1.0e-15,})
    defects.append({"name" : "VacancyRelated", "type" : "acceptor", "E_t_ev" : -5.47/2+2.00, "g_int" : 0, "N_t0" : 1.0e14, "sigma_n_irr" : 1.0e-14, "sigma_p_irr" : 1.0e-14,})

    return defects
