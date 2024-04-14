#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import os
import devsim
import math
from util.output import output

def CreateDataBase(filename):
    devsim.create_db(filename=filename)
    print("The SICAR database is created.")


def CreateGlobalConstant():

    # define global constant

    q = 1.60217646e-19 # coul
    k = 1.3806503e-23  # J/K
    eps_0 = 8.85e-14   # F/cm^2
    T0 = 300.0         # K

    devsim.add_db_entry(material="global",   parameter="ElectronCharge",       value=q,          unit="coul",     description="Unit Charge")
    devsim.add_db_entry(material="global",   parameter="k",       value=k,          unit="J/K",      description="Boltzmann Constant")
    devsim.add_db_entry(material="global",   parameter="eps_0",   value=eps_0,      unit="F/cm^2",   description="Absolute Dielectric Constant")
    devsim.add_db_entry(material="global",   parameter="T0",      value=T0,         unit="K",        description="T0")

    vel_mean = 1e7
    devsim.add_db_entry(material="global",   parameter="vel_mean",     value=vel_mean,   unit="cm/s",     description="Thermal average velocity")

    T = 300.0         # K
    devsim.add_db_entry(material="global",   parameter="T",    value=T,     unit="K",   description="T")
    devsim.add_db_entry(material="global",   parameter="k_T",    value=k*T,       unit="J",        description="k*T")
    devsim.add_db_entry(material="global",   parameter="Volt_thermal",    value=k*T/q,     unit="J/coul",   description="k*T/q")


def CreateSiliconCarbideConstant():

    # define SiliconCarbide parameters

    N_c=3.25e15
    N_v=4.8e15
    devsim.add_db_entry(material="SiliconCarbide",parameter="N_c",value=N_c, unit="/cm^3", description="effective density of states in conduction band")
    devsim.add_db_entry(material="SiliconCarbide",parameter="N_v",value=N_v, unit="/cm^3", description="effective density of states in valence band")

    E_g=3.26*1.6*1e-19
    devsim.add_db_entry(material="SiliconCarbide",   parameter="E_g",    value=E_g,       unit="J",         description="E_g")

    # material
    devsim.add_db_entry(material="SiliconCarbide",   parameter="eps",    value=9.76,      unit="1",         description="Dielectric Constant")
    eps_0 = 8.85e-14
    devsim.add_db_entry(material="SiliconCarbide",   parameter="Permittivity",    value=9.76*eps_0,      unit="F/cm^2",         description="Dielectric Constant")
    devsim.add_db_entry(material="SiliconCarbide",   parameter="n_i",    value=3.89e-9,   unit="/cm^3",     description="Intrinsic Electron Concentration")

    # mobility
    devsim.add_db_entry(material="SiliconCarbide",   parameter="mu_n",   value=1100,      unit="cm^2/Vs",   description="Constant Mobility of Electron")
    devsim.add_db_entry(material="SiliconCarbide",   parameter="mu_p",   value=114,       unit="cm^2/Vs",   description="Constant Mobility of Hole")

    # SRH
    devsim.add_db_entry(material="SiliconCarbide",   parameter="n1",     value=3.89e-9,   unit="/cm^3",     description="n1")
    devsim.add_db_entry(material="SiliconCarbide",   parameter="p1",     value=3.89e-9,   unit="/cm^3",     description="p1")
    devsim.add_db_entry(material="SiliconCarbide",   parameter="taun",  value=2.5e-6,    unit="s",         description="Constant SRH Lifetime of Electron")
    devsim.add_db_entry(material="SiliconCarbide",   parameter="taup",  value=0.5e-6,    unit="s",         description="Constant SRH Lifetime of Hole")


def CreateSiliconConstant():

    # define Silicon parameters

    #N_c=2.8e19
    #N_v=1.1e19
    N_c=2.82e19
    N_v=1.83e19
    #N_c=2.86e19
    #N_v=2.66e19
    devsim.add_db_entry(material="Silicon",parameter="N_c",value=N_c, unit="/cm^3", description="effective density of states in conduction band")
    devsim.add_db_entry(material="Silicon",parameter="N_v",value=N_v, unit="/cm^3", description="effective density of states in valence band")

    E_g=1.12*1.6*1e-19
    devsim.add_db_entry(material="Silicon",   parameter="E_g",    value=E_g,       unit="J",         description="E_g")

    # material
    devsim.add_db_entry(material="Silicon",   parameter="eps",    value=11.9,      unit="1",         description="Dielectric Constant")
    eps_0 = 8.85e-14
    devsim.add_db_entry(material="Silicon",   parameter="Permittivity",    value=11.9*eps_0,      unit="F/cm^2",         description="Dielectric Constant")
    devsim.add_db_entry(material="Silicon",   parameter="n_i",    value=1.02e10,   unit="/cm^3",     description="Intrinsic Electron Concentration")

    # mobility
    devsim.add_db_entry(material="Silicon",   parameter="mu_n",   value=1450,      unit="cm^2/Vs",   description="Constant Mobility of Electron")
    devsim.add_db_entry(material="Silicon",   parameter="mu_p",   value=500,       unit="cm^2/Vs",   description="Constant Mobility of Hole")

    # SRH
    devsim.add_db_entry(material="Silicon",   parameter="n1",     value=1.02e10,   unit="/cm^3",     description="n1")
    devsim.add_db_entry(material="Silicon",   parameter="p1",     value=1.02e10,   unit="/cm^3",     description="p1")
    """devsim.add_db_entry(material="Silicon",   parameter="taun",  value=5e-6,    unit="s",         description="Constant SRH Lifetime of Electron")
    devsim.add_db_entry(material="Silicon",   parameter="taup",  value=5e-6,    unit="s",         description="Constant SRH Lifetime of Hole")"""
    devsim.add_db_entry(material="Silicon",   parameter="taun",  value=7e-3,    unit="s",         description="Constant SRH Lifetime of Electron")
    devsim.add_db_entry(material="Silicon",   parameter="taup",  value=7e-3,    unit="s",         description="Constant SRH Lifetime of Hole")


def CreateHatakeyamaImpact():
    '''
    The Hatakeyama avalanche model describes the anisotropic behavior in 4H-SiC power devices. The impact ionization coefficient is obtainedaccording to the Chynoweth law.
    Ref : https://onlinelibrary.wiley.com/doi/abs/10.1002/pssa.200925213
    '''
    T = 300 #K

    hbarOmega = 0.19 # eV
    _theta =1 # 1
    T0 = 300.0 # K
    k_T0_ev = 0.0257 # eV
    
    n_a_0001 = 1.76e8 # cm-1
    n_a_1120 = 2.10e7 # cm-1
    n_b_0001 = 3.30e7 # V/cm 
    n_b_1120 = 1.70e7 # V/cm

    p_a_0001 = 3.41e8 # cm-1
    p_a_1120 = 2.96e7 # cm-1
    p_b_0001 = 2.50e7 # V/cm 
    p_b_1120 = 1.60e7 # V/cm 

    #gamma = math.tanh(hbarOmega/(2*k_T0_ev))/math.tanh(hbarOmega/(2*k_T0_ev*T/T0))
    gamma = 1

    n_a = n_a_0001
    n_b = n_b_0001
    p_a = p_a_0001
    p_b = p_b_0001

    devsim.add_db_entry(material="SiliconCarbide",   parameter="gamma",        value=gamma,   unit="1",        description="gamma for Hatakeyama Avalanche Model")
    devsim.add_db_entry(material="SiliconCarbide",   parameter="cutoff_angle",     value=4,   unit="degree",   description="cutoff_angle for Hatakeyama Avalanche Model")
    devsim.add_db_entry(material="SiliconCarbide",   parameter="n_a_0001",  value=n_a_0001,   unit="cm-1",     description="n_a for Hatakeyama Avalanche Model")
    devsim.add_db_entry(material="SiliconCarbide",   parameter="n_b_0001",  value=n_b_0001,   unit="V/cm",     description="n_b for Hatakeyama Avalanche Model")
    devsim.add_db_entry(material="SiliconCarbide",   parameter="p_a_0001",  value=p_a_0001,   unit="cm-1",     description="p_a for Hatakeyama Avalanche Model")
    devsim.add_db_entry(material="SiliconCarbide",   parameter="p_b_0001",  value=p_b_0001,   unit="V/cm",     description="p_b for Hatakeyama Avalanche Model")

    devsim.add_db_entry(material="SiliconCarbide",   parameter="n_a_1120",  value=n_a_1120,   unit="cm-1",     description="n_a for Hatakeyama Avalanche Model")
    devsim.add_db_entry(material="SiliconCarbide",   parameter="n_b_1120",  value=n_b_1120,   unit="V/cm",     description="n_b for Hatakeyama Avalanche Model")
    devsim.add_db_entry(material="SiliconCarbide",   parameter="p_a_1120",  value=p_a_1120,   unit="cm-1",     description="p_a for Hatakeyama Avalanche Model")
    devsim.add_db_entry(material="SiliconCarbide",   parameter="p_b_1120",  value=p_b_1120,   unit="V/cm",     description="p_b for Hatakeyama Avalanche Model")

def CreateVanOvenstraetenImpact():
    T = 300 #K

    hbarOmega = 0.063 # eV
    E0 = 4.0e5 # V/cm
    T0 = 293.0 # K
    k_T0 = 0.0257 # eV
    gamma = math.tanh(hbarOmega/(2*k_T0))/math.tanh(hbarOmega/(2*k_T0*T/T0))

    n_a_low = 7.03e5 # cm-1
    n_a_high = 7.03e5 # cm-1

    n_b_low = 1.232e6 # cm-1
    n_b_high = 1.232e6 # cm-1

    p_a_low = 1.582e6 # cm-1
    p_a_high = 6.71e5 # cm-1

    p_b_low = 2.036e6 # cm-1
    p_b_high = 1.693e6 # cm-1

    devsim.add_db_entry(material="Silicon",   parameter="gamma",  value=gamma,   unit="1",     description="gamma for van Ovenstraeten Avalanche Model")
    devsim.add_db_entry(material="Silicon",   parameter="n_a_high",  value=n_a_high,   unit="cm-1",     description="n_a for van Ovenstraeten Avalanche Model")
    devsim.add_db_entry(material="Silicon",   parameter="n_b_high",  value=n_b_high,   unit="V/cm",     description="n_b for van Ovenstraeten Avalanche Model")
    devsim.add_db_entry(material="Silicon",   parameter="p_a_high",  value=p_a_high,   unit="cm-1",     description="p_a for van Ovenstraeten Avalanche Model")
    devsim.add_db_entry(material="Silicon",   parameter="p_b_high",  value=p_b_high,   unit="V/cm",     description="p_b for van Ovenstraeten Avalanche Model")

    devsim.add_db_entry(material="Silicon",   parameter="n_a_low",  value=n_a_low,   unit="cm-1",     description="n_a for van Ovenstraeten Avalanche Model")
    devsim.add_db_entry(material="Silicon",   parameter="n_b_low",  value=n_b_low,   unit="V/cm",     description="n_b for van Ovenstraeten Avalanche Model")
    devsim.add_db_entry(material="Silicon",   parameter="p_a_low",  value=p_a_low,   unit="cm-1",     description="p_a for van Ovenstraeten Avalanche Model")
    devsim.add_db_entry(material="Silicon",   parameter="p_b_low",  value=p_b_low,   unit="V/cm",     description="p_b for van Ovenstraeten Avalanche Model")

def CreateTAT():
    '''trap assisted tunneling model for SiC'''
    devsim.add_db_entry(material="SiliconCarbide",   parameter="U_TAT",        value=-1.9e11,   unit="cm-3s-1",        description="recombination rate for TAT model")
    devsim.add_db_entry(material="SiliconCarbide",   parameter="F_gamma",        value=4.9e4,   unit="V/cm",        description="F_gamma in TAT model")
    devsim.add_db_entry(material="SiliconCarbide",   parameter="F_sat",        value=1e5,   unit="V/cm",        description="F_gamma in TAT model")

def SaveDataBase():
    devsim.save_db()
    print("The SICAR database is saved.")


def main():
    path = output(__file__, "")
    CreateDataBase(os.path.join(path, "SICARDB.db"))
    CreateGlobalConstant()
    CreateSiliconCarbideConstant()
    CreateSiliconConstant()
    CreateHatakeyamaImpact()
    CreateVanOvenstraetenImpact()
    CreateTAT()
    
    SaveDataBase()

if __name__ == "__main__":
    main()
