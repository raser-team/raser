#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

'''
Description:  physics_avalanche.py
@Date       : 2022/10/25 16:40:46
@Author     : Tao Yang, Zaiyi Li
@version    : 2.0
'''

import devsim
from .model_create import *
import math


def CreateImpactGeneration(device, region, impact_label,custom_ion_n='0', custom_ion_p='0' ):   
    
    material = devsim.get_material(device=device, region=region)
    #create impact ionization model
    if impact_label == "NoAvalanche":
        Ion_coeff_rate = '0'
    else:
        
        if material == 'Silicon' and impact_label != "CustomAvalanche":
            Ion_coeff_n, Ion_coeff_p = CreateImpactModel_vanOvenstraeten(device, region)
        elif material=='SiliconCarbide' and impact_label != "CustomAvalanche":
            Ion_coeff_n, Ion_coeff_p = CreateImpactModel_Hatakeyama(device, region)#default SiC model
            #changebale models
            if impact_label=="Hatakeyama":
                pass
            if impact_label=="Tunnel":
                pass
            if impact_label=="sze":
                Ion_coeff_n, Ion_coeff_p = CreateImpactModel_sze(device, region)
            if impact_label=="chynoweth":
                Ion_coeff_n, Ion_coeff_p = CreateImpactModel_chynoweth(device, region)
            if impact_label=="bologna":
                Ion_coeff_n, Ion_coeff_p = CreateImpactModel_bologna(device, region)
            if impact_label=="sic_custom":
                Ion_coeff_n, Ion_coeff_p = CreateImpactModel_sic_custom(device, region)
            elif impact_label=="CustomAvalanche":
                Ion_coeff_n, Ion_coeff_p = custom_ion_n, custom_ion_p
        else:
            Ion_coeff_n, Ion_coeff_p = custom_ion_n, custom_ion_p

        CreateEdgeModel(device, region, "Ion_coeff_n", Ion_coeff_n)
        CreateEdgeModelDerivatives(device, region, "Ion_coeff_n", Ion_coeff_n, "Potential")
        #CreateEdgeModelDerivatives(device, region, "Ion_coeff_n", Ion_coeff_n, "Electrons")
        #CreateEdgeModelDerivatives(device, region, "Ion_coeff_n", Ion_coeff_n, "Holes")
        CreateEdgeModel(device, region, "Ion_coeff_p", Ion_coeff_p)
        CreateEdgeModelDerivatives(device, region, "Ion_coeff_p", Ion_coeff_p, "Potential")
        #CreateEdgeModelDerivatives(device, region, "Ion_coeff_p", Ion_coeff_p, "Electrons")
        #CreateEdgeModelDerivatives(device, region, "Ion_coeff_p", Ion_coeff_p, "Holes")
        #CreateEdgeModel(device, region, "Ion_coeff_rate", Ion_coeff_rate)
        #CreateEdgeModelDerivatives(device, region, "Ion_coeff_rate", Ion_coeff_rate, "Potential")
    
        Ion_coeff_rate = "(Ion_coeff_n*(abs(ElectronCurrent))+Ion_coeff_p*(abs(HoleCurrent)))/ElectronCharge"
    
    #Create other field related models 
    if material=='SiliconCarbide':
        CreateFESRH(device,region)
        Ion_coeff_rate +="+R_TAT" #default create trap assisted tunneling in SiC
    
    if impact_label == 'Tunnel':
        print("creating tunnel")
        Ion_coeff_rate += CreateTunnelModel_Zaiyi(device, region)#tunneling model in P5
    
    ImpactGen_n = "+ElectronCharge*(%s)"%(Ion_coeff_rate)
    ImpactGen_p = "-ElectronCharge*(%s)"%(Ion_coeff_rate)
    

#for all material
    CreateEdgeModel(device, region, "ImpactGen_n", ImpactGen_n)
    CreateEdgeModelDerivatives(device, region, "ImpactGen_n", ImpactGen_n, "Potential")
    CreateEdgeModelDerivatives(device, region, "ImpactGen_n", ImpactGen_n, "Electrons")
    CreateEdgeModelDerivatives(device, region, "ImpactGen_n", ImpactGen_n, "Holes")
    
    CreateEdgeModel(device, region, "ImpactGen_p", ImpactGen_p)
    CreateEdgeModelDerivatives(device, region, "ImpactGen_p", ImpactGen_p, "Potential")
    CreateEdgeModelDerivatives(device, region, "ImpactGen_p", ImpactGen_p, "Electrons")
    CreateEdgeModelDerivatives(device, region, "ImpactGen_p", ImpactGen_p, "Holes")
    #devsim.edge_model(device=device,region=region,name="ImpactGen_p:Potential",equation="-ImpactGen_n:Potential")

def CreateImpactModel_vanOvenstraeten(device, region):
    """
    van Ovenstraeten Model
    """
    # constants in gen_devsim_db.py

    Ion_coeff_n  = "ifelse(abs(ElectricField)>1.75e4, (ifelse(abs(ElectricField)>4e5, gamma * n_a_high * exp( - gamma * n_b_high / (abs(ElectricField)+1)),  gamma * n_a_low * exp( - gamma * n_b_low / (abs(ElectricField)+1)))), 1)"
    Ion_coeff_p  = "ifelse(abs(ElectricField)>1.75e4, (ifelse(abs(ElectricField)>4e5, gamma * p_a_high * exp( - gamma * p_b_high / (abs(ElectricField)+1)),  gamma * p_a_low * exp( - gamma * p_b_low / (abs(ElectricField)+1)))), 1)"

    return Ion_coeff_n, Ion_coeff_p

def CreateImpactModel_Hatakeyama(device, region, cutoff_angle = 4):
    """
    Hatakeyama Model for cutoff angle of 4°
    """

    sin_cutoff_angle = math.sin(math.radians(cutoff_angle))
    cos_cutoff_angle = math.cos(math.radians(cutoff_angle))

    if not InEdgeModelList(device, region, "ElectricField_0001"):
        CreateEdgeModel(device, region, "ElectricField_0001", "abs(ElectricField+1)*{0}".format(cos_cutoff_angle))

    if not InEdgeModelList(device, region, "ElectricField_1120"):
        CreateEdgeModel(device, region, "ElectricField_1120", "abs(ElectricField+1)*{0}".format(sin_cutoff_angle))

    if not InEdgeModelList(device, region, "n_B"):
        CreateEdgeModel(device, region, "n_B", "abs(ElectricField+1) / pow( pow( ElectricField_1120/n_b_1120 , 2) + pow( ElectricField_0001/n_b_0001 , 2) , 0.5)")

    if not InEdgeModelList(device, region, "p_B"):
        CreateEdgeModel(device, region, "p_B", "abs(ElectricField+1) / pow( pow( ElectricField_1120/p_b_1120 , 2) + pow( ElectricField_0001/p_b_0001 , 2) , 0.5)")


    if not InEdgeModelList(device, region, "n_a_aniso"):
        CreateEdgeModel(device, region, "n_a_aniso", "pow( n_a_1120, pow( n_B*ElectricField_1120/n_b_1120/abs(ElectricField+1), 2) ) * pow( n_a_0001, pow( n_B*ElectricField_0001/n_b_0001/abs(ElectricField+1), 2) )")

    if not InEdgeModelList(device, region, "p_a_aniso"):
        CreateEdgeModel(device, region, "p_a_aniso", "pow( p_a_1120, pow( p_B*ElectricField_1120/p_b_1120/abs(ElectricField+1), 2) ) * pow( p_a_0001, pow( p_B*ElectricField_0001/p_b_0001/abs(ElectricField+1), 2) )")



    if not InEdgeModelList(device, region, "n_A"):
        CreateEdgeModel(device, region, "n_A", "log(n_a_0001/n_b_1120)")

    if not InEdgeModelList(device, region, "p_A"):
        CreateEdgeModel(device, region, "p_A", "log(p_a_0001/p_b_1120)")

    if not InEdgeModelList(device, region, "n_b_aniso"):
        CreateEdgeModel(device, region, "n_b_aniso", "n_B * pow( 1-pow(n_A,2)* pow( (n_B*ElectricField_1120*ElectricField_0001)/(abs(ElectricField+1)*n_b_1120*n_b_0001), 2), 0.5)")

    if not InEdgeModelList(device, region, "p_b_aniso"):
        CreateEdgeModel(device, region, "p_b_aniso", "p_B * pow( 1-pow(p_A,2)* pow( (p_B*ElectricField_1120*ElectricField_0001)/(abs(ElectricField+1)*p_b_1120*p_b_0001), 2), 0.5)")

    gamma_str = "tanh(0.19/(2*0.0257))/tanh(0.19/(2*0.0257*T/T0))"
    Ion_coeff_n  = "ifelse(abs(ElectricField)>1e4, {0} * n_a_aniso * exp( - {1} * n_b_aniso / (abs(ElectricField)+1)), 1)".format(gamma_str,gamma_str)
    Ion_coeff_p  = "ifelse(abs(ElectricField)>1e4, {0} * p_a_aniso * exp( - {1} * p_b_aniso / (abs(ElectricField)+1)), 1)".format(gamma_str,gamma_str)

    return Ion_coeff_n, Ion_coeff_p


def CreateTunnelModel_Zaiyi(device, region):

    R_improved="3.11*abs(ElectricField)^2.5*exp(abs(ElectricField)/3e4)"
    CreateEdgeModel(device,region,"R_improved",R_improved)
    CreateEdgeModelDerivatives(device,region,"R_improved",R_improved,"Potential")

    R_BTBT="1e21*abs(ElectricField)^2.5*exp(-0.8e7/(1+abs(ElectricField)))"
    CreateEdgeModel(device,region,"R_BTBT",R_BTBT)
    CreateEdgeModelDerivatives(device,region,"R_BTBT",R_BTBT,"Potential")
    devsim.edge_from_node_model(device=device,region=region,node_model="USRH")

    R_TAT="2*(3*3.14159)^0.5*abs(ElectricField)/3.9e4*exp((abs(ElectricField)/3.9e4)^2)*USRH@n1"
    CreateEdgeModel(device,region,"R_TAT",R_TAT)
    CreateEdgeModelDerivatives(device,region,"R_TAT",R_TAT,"Potential")
    CreateEdgeModelDerivatives(device,region,"R_TAT",R_TAT,"Electrons")
    CreateEdgeModelDerivatives(device,region,"R_TAT",R_TAT,"Holes")

    return "+R_improved"

def CreateImpactModel_sze(device,region):
    Ion_coeff_n  = "ifelse(abs(ElectricField)>1e4, a*abs(ElectricField)*exp(-b/abs(ElectricField)),1)"
    Ion_coeff_p  = "ifelse(abs(ElectricField)>1e4, a*abs(ElectricField)*exp(-b/abs(ElectricField)),1)"

    return Ion_coeff_n, Ion_coeff_p
    
def CreateImpactModel_chynoweth(device,region):
    Ion_coeff_n  = "ifelse(abs(ElectricField)>1e4, a*exp(-b/abs(ElectricField)),1)"
    Ion_coeff_p  = "ifelse(abs(ElectricField)>1e4, a*exp(-b/abs(ElectricField)),1)"

    return Ion_coeff_n, Ion_coeff_p

def CreateImpactModel_bologna(device,region):
    Ion_coeff_n  = "ifelse(abs(ElectricField)>1e4, abs(ElectricField)/(a+b*exp(d/(abs(ElectricField)+c))),1)"
    Ion_coeff_p  = "ifelse(abs(ElectricField)>1e4, abs(ElectricField)/(a+b*exp(d/(abs(ElectricField)+c))),1)"

    return Ion_coeff_n, Ion_coeff_p
    
def CreateImpactModel_sic_custom(device,region):
    Ion_coeff_n  = "ifelse(abs(ElectricField)>1e4, 1.96e6*exp(-(9.96e6/abs(ElectricField))^1.6), 1)"
    Ion_coeff_p  = "ifelse(abs(ElectricField)>1e4, 3.32e6*exp(-(1.07e7/abs(ElectricField))^1.1), 1)"

    return Ion_coeff_n, Ion_coeff_p
    
def CreateFESRH(device,region):
    R_TAT="ifelse(abs(ElectricField)<F_sat,2*(3*3.14159)^0.5*abs(ElectricField)/3.9e4*exp((abs(ElectricField)/3.9e4)^2)*(U_const@n1),2*(3*3.14159)^0.5*abs(F_sat)/3.9e4*exp((F_sat/3.9e4)^2)*(U_const@n1))"
    CreateEdgeModel(device,region,"R_TAT",R_TAT)
    CreateEdgeModelDerivatives(device,region,"R_TAT",R_TAT,"Potential")
    CreateEdgeModelDerivatives(device,region,"R_TAT",R_TAT,"Electrons")
    CreateEdgeModelDerivatives(device,region,"R_TAT",R_TAT,"Holes")
