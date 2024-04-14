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

def CreateIrradiation(device, region, label="Xingchen", flux=1e15, custom_defect = {}):

    # if not InEdgeModelList(device, region, "ElectricField"):
    #     CreateEdgeModel(device, region, "ElectricField", "(Potential@n0-Potential@n1)*EdgeInverseLength")
    #     CreateEdgeModelDerivatives(device, region, "ElectricField", "(Potential@n0-Potential@n1)*EdgeInverseLength", "Potential")

    # TODO: change labels into formal names
    if label == 'XingChen':
        defects = CreateIrradiationModel_XingChen(device, region)
    elif label == 'Perugia':
        defects = CreateIrradiationModel_Perugia(device, region)
    elif label == 'Schwandt':
        defects = CreateIrradiationModel_Schwandt(device, region)
    elif label == 'CommonDefect':
        defects = CreateIntrinsicModel_SiCCommonDefect(device, region)
    else:
        defects = custom_defect

    TrappedElectrons="0"
    TrappedHoles="0"
    TrappingRate_n="0"
    TrappingRate_p="0"
    U_r = "0"

    for defect in defects:
        name, E_t_ev, g_int, sigma_n_irr, sigma_p_irr = defect['name'], defect['E_t_ev'], defect['g_int'], defect['sigma_n_irr'], defect['sigma_p_irr']
        e = 1.6*1e-19
        E_t = E_t_ev * e
        N_t_irr = g_int*flux

        devsim.set_parameter(device=device, region=region, name="sigma_n_irr_"+name,   value=sigma_n_irr)
        devsim.set_parameter(device=device, region=region, name="sigma_p_irr_"+name,   value=sigma_p_irr)
        devsim.set_parameter(device=device, region=region, name="N_t_irr_"+name,   value=N_t_irr)
        devsim.set_parameter(device=device, region=region, name="E_t_"+name,   value=E_t)

        r_n = "(vel_mean * sigma_n_irr_{name})".format(name=name)#c_n
        n_1 = "(N_c * exp(-(E_g/2 - E_t_{name})/k_T))".format(name=name)#e_n
        r_p = "(vel_mean * sigma_p_irr_{name})".format(name=name)#c_p
        p_1 = "(N_v * exp(-(E_t_{name} - (-E_g/2))/k_T))".format(name=name)#e_p
        n_t_irr_n = "+(N_t_irr_{name}*(Electrons*{r_n}+{p_1}*{r_p})/({r_n}*(Electrons+{n_1})+{r_p}*(Holes+{p_1})))".format(name=name,r_n=r_n,n_1=n_1,r_p=r_p,p_1=p_1)
        n_t_irr_p = "+(N_t_irr_{name}*(Holes*{r_p}+{n_1}*{r_n})/({r_n}*(Electrons+{n_1})+{r_p}*(Holes+{p_1})))".format(name=name,r_n=r_n,n_1=n_1,r_p=r_p,p_1=p_1)
        trap_n = "+(vel_mean * sigma_n_irr_{name})*(N_t_irr_{name}*(Electrons*{r_n}+{p_1}*{r_p})/({r_n}*(Electrons+{n_1})+{r_p}*(Holes+{p_1})))".format(name=name,r_n=r_n,n_1=n_1,r_p=r_p,p_1=p_1)
        trap_p = "+(vel_mean * sigma_p_irr_{name})*(N_t_irr_{name}*(Holes*{r_p}+{n_1}*{r_n})/({r_n}*(Electrons+{n_1})+{r_p}*(Holes+{p_1})))".format(name=name,r_n=r_n,n_1=n_1,r_p=r_p,p_1=p_1)
        U_r_i="+(N_t_irr_{name}*{r_n}*{r_p}*(Electrons*Holes-n_i^2)/({r_n}*(Electrons+{n_1})+{r_p}*(Holes+{p_1})))".format(name=name,r_n=r_n,n_1=n_1,r_p=r_p,p_1=p_1)

        TrappedElectrons=TrappedElectrons+n_t_irr_n
        TrappedHoles=TrappedHoles+n_t_irr_p
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
    defects.append({"name" : "DA1", "E_t_ev" : 0.56-0.42,  "g_int" : 0.209*0.7, "sigma_n_irr" : 1e-15,     "sigma_p_irr" : 1e-14})#右
    defects.append({"name" : "DA2", "E_t_ev" : 0.56-0.46,  "g_int" : 0.155,  "sigma_n_irr" : 7e-15,     "sigma_p_irr" : 7e-14})#右
    defects.append({"name" : "DD1", "E_t_ev" : -0.56+0.36, "g_int" : 0.025*2.6, "sigma_n_irr" : 3.23e-13,  "sigma_p_irr" : 3.23e-14})#左
    defects.append({"name" : "DD2", "E_t_ev" : -0.56+0.48, "g_int" : 0.321*0.85, "sigma_n_irr" : 4.166e-15, "sigma_p_irr" : 1.965e-16})#左

    return defects


def CreateIrradiationModel_Perugia(device, region):
    """
    Si Irradiation model  
    """

    defects = []
    defects.append({"name" : "DA1", "E_t_ev" : 0.56-0.42, "g_int" : 1.613, "sigma_n_irr" : 1e-15,     "sigma_p_irr" : 1e-14})
    defects.append({"name" : "DA2", "E_t_ev" : 0.56-0.46, "g_int" : 0.9,   "sigma_n_irr" : 7e-15,     "sigma_p_irr" : 7e-14})
    defects.append({"name" : "DD",  "E_t_ev" : -0.56+0.36, "g_int" : 0.9,   "sigma_n_irr" : 3.23e-13,  "sigma_p_irr" : 3.23e-14})

    return defects


def CreateIrradiationModel_Schwandt(device, region):
    """
    Si Irradiation model  
    """

    defects = []
    defects.append({"name" : "E30K", "E_t_ev" : 0.56-0.1,   "g_int" : 0.0497, "sigma_n_irr" : 2.300e-14, "sigma_p_irr" : 2.920e-16})
    defects.append({"name" : "V3",   "E_t_ev" : 0.56-0.458, "g_int" : 0.6447, "sigma_n_irr" : 2.551e-14, "sigma_p_irr" : 1.551e-13})
    defects.append({"name" : "Ip",   "E_t_ev" : 0.56-0.545, "g_int" : 0.4335, "sigma_n_irr" : 4.478e-15, "sigma_p_irr" : 6.709e-15})
    defects.append({"name" : "H220", "E_t_ev" : -0.56+0.48, "g_int" : 0.5978, "sigma_n_irr" : 4.166e-15, "sigma_p_irr" : 1.965e-16})
    defects.append({"name" : "CiOi", "E_t_ev" : -0.56+0.36, "g_int" : 0.3780, "sigma_n_irr" : 3.230e-17, "sigma_p_irr" : 2.036e-14})

    return defects

def CreateIntrinsicModel_SiCCommonDefect(device, region):
    """
    SiC Intrinsic Defect model  
    """
    
    defects = []
    defects.append({"name" : "Z12",  "E_t_ev" : 1.63-0.67, "g_int" : 1, "sigma_n_irr" : 3e-16, "sigma_p_irr" : 2e-12})
    defects.append({"name" : "EH67", "E_t_ev" : 1.63-1.65, "g_int" : 1, "sigma_n_irr" : 2e-17, "sigma_p_irr" : 3e-17})

    return defects
