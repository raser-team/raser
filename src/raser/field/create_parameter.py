import math

import devsim

from . import model_create

'''  
Description:  This module creates various physical and material parameters.
@Date       : 2023
@Author     : Tao Yang, Xingchen Li, Zaiyi Li, Chenxi Fu (Copied and modified from devsim examples)
@version    : 2.0
'''

def CreateGlobalConstant(T, device, region):
    # define global constant
    q = 1.60217646e-19 # coul
    k = 1.3806503e-23  # J/K
    eps_0 = 8.85e-14   # F/cm^2
    T0 = 300.0         # K

    devsim.set_parameter(device=device, region=region, name="ElectronCharge", value=q)
    devsim.set_parameter(device=device, region=region, name="k", value=k)
    devsim.set_parameter(device=device, region=region, name="eps_0", value=eps_0)
    devsim.set_parameter(device=device, region=region, name="T0", value=T0)

    vel_mean = 1e7
    devsim.set_parameter(device=device, region=region, name="vel_mean", value=vel_mean)

    T = 300.0  # K
    devsim.set_parameter(device=device, region=region, name="T", value=T)
    devsim.set_parameter(device=device, region=region, name="k_T", value=k * T)
    devsim.set_parameter(device=device, region=region, name="Volt_thermal", value=k * T / q)

def CreateGasConstant(T, device, region):
    # define gas parameters
    eps_0 = 8.85e-14
    devsim.set_parameter(device=device, region=region, name="n_i", value="1e-9")
    devsim.set_parameter(device=device, region=region, name="Permittivity", value=eps_0)

def CreateSiliconCarbideConstant(T, device, region):
    # define SiliconCarbide parameters
    N_c = 3.25e15
    N_v = 4.8e15
    devsim.set_parameter(device=device, region=region, name="N_c", value=N_c)
    devsim.set_parameter(device=device, region=region, name="N_v", value=N_v)

    E_g = 3.26 * 1.6 * 1e-19
    devsim.set_parameter(device=device, region=region, name="E_g", value=E_g)

    devsim.set_parameter(device=device, region=region, name="eps", value=9.76)
    eps_0 = 8.85e-14
    devsim.set_parameter(device=device, region=region, name="Permittivity", value=9.76 * eps_0)
    N_i = 3.89e-9
    devsim.set_parameter(device=device, region=region, name="n_i", value=N_i)

    devsim.set_parameter(device=device, region=region, name="mu_n", value=1100)
    devsim.set_parameter(device=device, region=region, name="mu_p", value=114)

    devsim.set_parameter(device=device, region=region, name="n1", value=N_i)
    devsim.set_parameter(device=device, region=region, name="p1", value=N_i)
    devsim.set_parameter(device=device, region=region, name="taun", value=2.5e-6)
    devsim.set_parameter(device=device, region=region, name="taup", value=0.5e-6)

def CreateSiliconConstant(T, device, region):
    # define Silicon parameters
    N_c = 2.82e19 * pow(T / 300, 1.5)
    N_v = 1.83e19 * pow(T / 300, 1.5)
    devsim.set_parameter(device=device, region=region, name="N_c", value=N_c)
    devsim.set_parameter(device=device, region=region, name="N_v", value=N_v)

    E_g = 1.12 * 1.6e-19
    devsim.set_parameter(device=device, region=region, name="E_g", value=E_g)

    devsim.set_parameter(device=device, region=region, name="eps", value=11.9)
    eps_0 = 8.85e-14
    devsim.set_parameter(device=device, region=region, name="Permittivity", value=11.9 * eps_0)
    k = 1.3806503e-23  # J/K
    N_i = pow(N_c * N_v, 0.5) * math.exp(-E_g / (2 * k * T))
    devsim.set_parameter(device=device, region=region, name="n_i", value=N_i)

    devsim.set_parameter(device=device, region=region, name="mu_n", value=1450)
    devsim.set_parameter(device=device, region=region, name="mu_p", value=500)

    devsim.set_parameter(device=device, region=region, name="n1", value=N_i)
    devsim.set_parameter(device=device, region=region, name="p1", value=N_i)
    devsim.set_parameter(device=device, region=region, name="taun", value=7e-3)
    devsim.set_parameter(device=device, region=region, name="taup", value=7e-3)
def CreateDiamondConstant(T, device, region):
    # define SiliconCarbide parameters
    N_c = 1.8e19 * pow(T / 300, 1.5)  # cm^-3
    N_v = 1.5e19 * pow(T / 300, 1.5)  # cm^-3
    devsim.set_parameter(device=device, region=region, name="N_c", value=N_c)
    devsim.set_parameter(device=device, region=region, name="N_v", value=N_v)

    E_g = 5.47 * 1.6e-19  # J
    devsim.set_parameter(device=device, region=region, name="E_g", value=E_g)

    epsilon_r = 5.7  # 相对介电常数
    eps_0 = 8.85e-14  # F/cm^2
    devsim.set_parameter(device=device, region=region, name="eps", value=epsilon_r)
    devsim.set_parameter(device=device, region=region, name="Permittivity", value=epsilon_r * eps_0)

    k = 1.3806503e-23  # J/K
    N_i = pow(N_c * N_v, 0.5) * math.exp(-E_g / (2 * k * T))
    devsim.set_parameter(device=device, region=region, name="n_i", value=N_i)

    devsim.set_parameter(device=device, region=region, name="mu_n", value=110)
    devsim.set_parameter(device=device, region=region, name="mu_p", value=1100)

    devsim.set_parameter(device=device, region=region, name="n1", value=N_i)
    devsim.set_parameter(device=device, region=region, name="p1", value=N_i)
    devsim.set_parameter(device=device, region=region, name="taun", value=5e-6)
    devsim.set_parameter(device=device, region=region, name="taup", value=10e-6)
    
def CreateFineExponentialModels(T, device, region):
    epsilon_model_in = 10 * 1.6 * 1e-19  # J
    epsilon_model_ip = 7 * 1.6 * 1e-19
    epsilon_model_0 = 0.36 * 1.6 * 1e-19
    lambda_model_n = 2.99 * 1e-7
    lambda_model_p = 3.25 * 1e-7
    devsim.set_parameter(device=device, region=region, name="epsilon_model_in", value=epsilon_model_in)
    devsim.set_parameter(device=device, region=region, name="epsilon_model_ip", value=epsilon_model_ip)
    devsim.set_parameter(device=device, region=region, name="epsilon_model_0", value=epsilon_model_0)
    devsim.set_parameter(device=device, region=region, name="lambda_model_n", value=lambda_model_n)
    devsim.set_parameter(device=device, region=region, name="lambda_model_p", value=lambda_model_p)

def CreateHatakeyamaImpact(T, device, region):
    T = 300  # K

    hbarOmega = 0.19  # eV
    _theta = 1  # 1
    T0 = 300.0  # K
    k_T0_ev = 0.0257  # eV

    n_a_0001 = 1.76e8  # cm-1
    n_a_1120 = 2.10e7  # cm-1
    n_b_0001 = 3.30e7  # V/cm
    n_b_1120 = 1.70e7  # V/cm

    p_a_0001 = 3.41e8  # cm-1
    p_a_1120 = 2.96e7  # cm-1
    p_b_0001 = 2.50e7  # V/cm
    p_b_1120 = 1.60e7  # V/cm

    gamma = 1

    n_a = n_a_0001
    n_b = n_b_0001
    p_a = p_a_0001
    p_b = p_b_0001

    devsim.set_parameter(device=device, region=region, name="gamma", value=gamma)
    devsim.set_parameter(device=device, region=region, name="cutoff_angle", value=4)
    devsim.set_parameter(device=device, region=region, name="n_a_0001", value=n_a_0001)
    devsim.set_parameter(device=device, region=region, name="n_b_0001", value=n_b_0001)
    devsim.set_parameter(device=device, region=region, name="p_a_0001", value=p_a_0001)
    devsim.set_parameter(device=device, region=region, name="p_b_0001", value=p_b_0001)

    devsim.set_parameter(device=device, region=region, name="n_a_1120", value=n_a_1120)
    devsim.set_parameter(device=device, region=region, name="n_b_1120", value=n_b_1120)
    devsim.set_parameter(device=device, region=region, name="p_a_1120", value=p_a_1120)
    devsim.set_parameter(device=device, region=region, name="p_b_1120", value=p_b_1120)

def CreateVanOvenstraetenImpact(T, device, region):
    T = 300  # K

    hbarOmega = 0.063  # eV
    E0 = 4.0e5  # V/cm
    T0 = 293.0  # K
    k_T0 = 0.0257  # eV
    gamma = math.tanh(hbarOmega / (2 * k_T0)) / math.tanh(hbarOmega / (2 * k_T0 * T / T0))

    n_a_low = 7.03e5  # cm-1
    n_a_high = 7.03e5  # cm-1

    n_b_low = 1.232e6  # cm-1
    n_b_high = 1.232e6  # cm-1

    p_a_low = 1.582e6  # cm-1
    p_a_high = 6.71e5  # cm-1

    p_b_low = 2.036e6  # cm-1
    p_b_high = 1.693e6  # cm-1

    devsim.set_parameter(device=device, region=region, name="gamma", value=gamma)
    devsim.set_parameter(device=device, region=region, name="n_a_high", value=n_a_high)
    devsim.set_parameter(device=device, region=region, name="n_b_high", value=n_b_high)
    devsim.set_parameter(device=device, region=region, name="p_a_high", value=p_a_high)
    devsim.set_parameter(device=device, region=region, name="p_b_high", value=p_b_high)

    devsim.set_parameter(device=device, region=region, name="n_a_low", value=n_a_low)
    devsim.set_parameter(device=device, region=region, name="n_b_low", value=n_b_low)
    devsim.set_parameter(device=device, region=region, name="p_a_low", value=p_a_low)
    devsim.set_parameter(device=device, region=region, name="p_b_low", value=p_b_low)

def CreateTAT(T, device, region):
    '''trap assisted tunneling model for SiC'''
    devsim.set_parameter(device=device, region=region, name="U_TAT", value=-1.9e11)
    devsim.set_parameter(device=device, region=region, name="F_gamma", value=4.9e4)
    devsim.set_parameter(device=device, region=region, name="F_sat", value=1e5)

def delete_init(device, region):
    devsim.delete_node_model(device=device, region=region, name="IntrinsicElectrons")
    devsim.delete_node_model(device=device, region=region, name="IntrinsicHoles")
    devsim.delete_node_model(device=device, region=region, name="IntrinsicElectrons:Potential")
    devsim.delete_node_model(device=device, region=region, name="IntrinsicHoles:Potential")
    devsim.delete_node_model(device=device, region=region, name="IntrinsicCharge")
    devsim.delete_node_model(device=device, region=region, name="IntrinsicCharge:Potential")

def create_parameter(MyDetector, device, region):
    T = MyDetector.device_dict['temperature']
    CreateGlobalConstant(T, device, region)
    if devsim.get_material(device=device, region=region) == "SiliconCarbide":
        CreateSiliconCarbideConstant(T, device, region)
        CreateHatakeyamaImpact(T, device, region)
        CreateFineExponentialModels(T, device, region)
        CreateTAT(T, device, region)
    elif devsim.get_material(device=device, region=region) == "Silicon":
        CreateSiliconConstant(T, device, region)
        CreateVanOvenstraetenImpact(T, device, region)
    elif devsim.get_material(device=device, region=region) == "gas":
        CreateGasConstant(T, device, region)
    elif devsim.get_material(device=device, region=region) == "Diamond":
        CreateDiamondConstant(T, device, region)
        
    if "parameter" in MyDetector.device_dict:
        devsim.set_parameter(device=device, region=region,
                             name=MyDetector.device_dict['parameter']['name'],
                             value=MyDetector.device_dict['parameter']['value'])
        
    if "U_const" in MyDetector.device_dict:
        U_const = MyDetector.device_dict["U_const"]
        model_create.CreateNodeModel(device, region, "U_const", U_const)
    else:
        model_create.CreateNodeModel(device, region, "U_const", 0)
