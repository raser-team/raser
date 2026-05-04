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

def CreateDiamondPotentialOnly(device, region):
    '''
      Creates the physical models for a Diamond region (Poisson equation only)
      为金刚石区域创建仅电势的物理模型（泊松方程）
    '''
    # 检查并创建电势解
    if not InNodeModelList(device, region, "Potential"):
        print("Creating Node Solution Potential for Diamond")
        CreateSolution(device, region, "Potential")
    
    # 使用玻尔兹曼统计的本征载流子浓度模型
    # 由于金刚石禁带很宽(5.47 eV)，本征载流子浓度极低(~10^-27 cm^-3)
    # 使用精确计算避免数值问题
    elec_i = "n_i*exp(Potential/Volt_thermal)"
    hole_i = "n_i^2/IntrinsicElectrons"
    
    # 总电荷密度：空穴 - 电子 + 净掺杂
    # 金刚石通常掺杂浓度较低，注意数值稳定性
    charge_i = "kahan3(IntrinsicHoles, -IntrinsicElectrons, NetDoping)"
    
    # 乘以电子电荷得到电荷密度
    pcharge_i = "-ElectronCharge * IntrinsicCharge"

    # 创建节点模型及其对电势的导数
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

    # 创建边缘模型：电场和电位移通量
    for i in (
        ("ElectricField", "(Potential@n0-Potential@n1)*EdgeInverseLength"),
        ("PotentialEdgeFlux", "Permittivity * ElectricField")
    ):
        n = i[0]
        e = i[1]
        CreateEdgeModel(device, region, n, e)
        CreateEdgeModelDerivatives(device, region, n, e, "Potential")

        equation(device=device, region=region, name="PotentialEquation", variable_name="Potential",
             node_model="PotentialIntrinsicCharge", edge_model="PotentialEdgeFlux", variable_update="log_damp")
    # 创建电势方程（泊松方程）
    # 金刚石的高介电常数和宽禁带需要特殊处理
    #equation(device=device, region=region, name="PotentialEquation", 
    #         variable_name="Potential",
    #         node_model="PotentialIntrinsicCharge", 
    #         edge_model="PotentialEdgeFlux", 
    #         variable_update="log_damp",
    #         time_node_model="",  # 静态分析
    #         enabled=True)


def CreateSiliconPotentialOnlyContact(device, region, contact, contact_type, is_circuit=False):
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

    if contact_type["type"] == "Schottky":
        workfun = contact_type["workfun"]
        affinity = contact_type["affinity"]
        # gamma=1: Schottky, gamma=0: Bardeen, else: Sze
        if "gamma" in contact_type:
            gamma = contact_type["gamma"]
        else:
            if "delta" in contact_type and "D_s" in contact_type:
                gamma = "Permittivity / (Permittivity + ElectronCharge*ElectronCharge*{0}*{1})".format(contact_type["delta"], contact_type["D_s"])
            else:
                gamma = 1
        phi_0 = "E_g/(3*ElectronCharge)"
        contact_model = "Potential - {0} + {3}*({1} - {2}) - {3}*E_g/ElectronCharge + ({3}-1)*{4} + Volt_thermal*log(N_v/n_i)".format(GetContactBiasName(contact), workfun, affinity, gamma, phi_0)
        # The units of affinity and workfun are eV, assume q=1e to get the V
    else:
        contact_model = "Potential -{0} + ifelse(NetDoping >0, \
                        -Volt_thermal*log({1}/n_i), \
                        Volt_thermal*log({2}/n_i))".format(GetContactBiasName(contact), celec_model, chole_model)

    contact_model_name = GetContactNodeModelName(contact)
    CreateContactNodeModel(device, contact, contact_model_name, contact_model)
    # Simplify it too complicated
    CreateContactNodeModel(device, contact, "{0}:{1}".format(contact_model_name,"Potential"), "1")
    if is_circuit:
       # add_circuit_node(name=str(GetContactBiasName(contact)),value=0)
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

def CreateDiamondPotentialOnlyContact(device, region, contact, contact_type, is_circuit=False):
    '''
      Creates the potential equation at the contact for Diamond
      为金刚石创建接触边界条件
      
      Args:
        device: 设备对象
        region: 区域名称
        contact: 接触名称
        contact_type: 接触类型字典，包含类型和参数
        is_circuit: 是否连接电路
    '''
    # 接触电荷计算模型（与硅相同）
    if not InEdgeModelList(device, region, "contactcharge_edge"):
        CreateEdgeModel(device, region, "contactcharge_edge", "Permittivity*ElectricField")
        CreateEdgeModelDerivatives(device, region, "contactcharge_edge", 
                                   "Permittivity*ElectricField", "Potential")

    # 根据接触类型创建不同的边界条件
    #if contact_type["type"] == "Schottky":
        # 肖特基接触 - 金刚石功函数较高(~4.8-5.0 eV)
    #    workfun = contact_type.get("workfun", 4.8)  # 金属功函数，默认4.8 eV
    #    affinity = contact_type.get("affinity", 0.38)  # 金刚石电子亲和能，默认0.38 eV
        
        # γ参数：肖特基模型修正因子
        # 金刚石的界面态密度可能较低
    #    if "gamma" in contact_type:
    #        gamma = contact_type["gamma"]
    #    else:
            # 默认使用标准肖特基模型(γ=1)
    #        gamma = 1.0
        
        # 中带电势（金刚石可能需要调整）
    #    phi_0 = "E_g/(3*ElectronCharge)"
        
        # 肖特基接触模型公式
    #    contact_model = """
    #        Potential - {0} + {3}*({1} - {2}) - {3}*E_g/ElectronCharge 
    #        + ({3}-1)*{4} + Volt_thermal*log(N_v/n_i)
    #    """.format(GetContactBiasName(contact), workfun, affinity, gamma, phi_0)
        
    if contact_type["type"] == "Ohmic":
        # 欧姆接触 - 金刚石的欧姆接触制备较困难
        # 通常需要重掺杂或特殊处理
        celec_model = contact_type.get("celec_model", "n_i*exp(({0}-Potential)/Volt_thermal)".format(GetContactBiasName(contact)))
        chole_model = contact_type.get("chole_model", "n_i*exp((Potential-{0})/Volt_thermal)".format(GetContactBiasName(contact)))
        contact_model = """
            Potential -{0} + ifelse(NetDoping > 0, \
                        -Volt_thermal*log({1}/n_i), \
                        Volt_thermal*log({2}/n_i))
        """.format(GetContactBiasName(contact), celec_model, chole_model)
        
    #elif contact_type["type"] == "HydrogenTerminated":
        # 金刚石特有的氢终端接触
        # 氢终端金刚石表面形成2D空穴气，具有独特的能带结构
    #    surface_dipole = contact_type.get("surface_dipole", 1.7)  # 表面偶极层电势降
        
    #    contact_model = """
    #        Potential - {0} + {1} - E_g/(2*ElectronCharge) 
    #        + Volt_thermal*log(N_v/n_i)
    #    """.format(GetContactBiasName(contact), surface_dipole)
        
    #elif contact_type["type"] == "OxygenTerminated":
        # 氧终端金刚石表面
    #    surface_affinity = contact_type.get("surface_affinity", 1.7)  # 表面电子亲和能
        
    #    contact_model = """
    #        Potential - {0} + ({1} - affinity) - E_g/(2*ElectronCharge)
    #        + Volt_thermal*log(N_v/n_i)
    #    """.format(GetContactBiasName(contact), surface_affinity)
        
    #else:
    #    contact_model = "Potential - {0}".format(GetContactBiasName(contact))
        # 默认欧姆接触
    #    celec_model = "n_i*exp(({0}-Potential)/Volt_thermal)".format(GetContactBiasName(contact))
    #    chole_model = "n_i*exp((Potential-{0})/Volt_thermal)".format(GetContactBiasName(contact))
        
    #    contact_model = """
    #        Potential -{0} + ifelse(NetDoping > 0, \
    #                    -Volt_thermal*log({1}/n_i), \
    #                    Volt_thermal*log({2}/n_i))
    #    """.format(GetContactBiasName(contact), celec_model, chole_model)

    # 创建接触节点模型
    contact_model_name = GetContactNodeModelName(contact)
    CreateContactNodeModel(device, contact, contact_model_name, contact_model)
    
    # 创建对电势的导数（通常为1）
    CreateContactNodeModel(device, contact, "{0}:{1}".format(contact_model_name, "Potential"), "1")
    
    # 如果连接电路，创建对电路节点的导数
    if is_circuit:
        CreateContactNodeModel(device, contact, 
                               "{0}:{1}".format(contact_model_name, GetContactBiasName(contact)), 
                               "-1")

    # 创建接触方程
    if is_circuit:
        contact_equation(device=device, contact=contact, name="PotentialEquation",
                         node_model=contact_model_name, edge_model="",
                         node_charge_model="", edge_charge_model="contactcharge_edge",
                         node_current_model="", edge_current_model="", 
                         circuit_node=GetContactBiasName(contact))
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


def CreateSRH(device, region, irradiation_model):
    USRH="(Electrons*Holes - n_i^2)/(taup*(Electrons + n1) + taun*(Holes + p1))"
    Gn = "-ElectronCharge * (USRH+U_const)"
    Gp = "+ElectronCharge * (USRH+U_const)"

    if irradiation_model != None:
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
    

def CreateECE(device, region, mu_n, impact_model):
    CreateElectronCurrent(device, region, mu_n)

    NCharge = "-ElectronCharge * Electrons"
    CreateNodeModel(device, region, "NCharge", NCharge)
    CreateNodeModelDerivative(device, region, "NCharge", NCharge, "Electrons")
    if impact_model != None:
        CreateImpactGeneration(device, region, impact_model)
        equation(device=device, region=region, name="ElectronContinuityEquation", variable_name="Electrons",
                time_node_model = "NCharge",
                edge_model="ElectronCurrent", variable_update="positive", node_model="ElectronGeneration",
                edge_volume_model="ImpactGen_n")
    else:
        equation(device=device, region=region, name="ElectronContinuityEquation", variable_name="Electrons",
                time_node_model = "NCharge",
                edge_model="ElectronCurrent", variable_update="positive", node_model="ElectronGeneration")
    

def CreateHCE(device, region, mu_p, impact_model):
    CreateHoleCurrent(device, region, mu_p)
    PCharge = "ElectronCharge * Holes"
    CreateNodeModel(device, region, "PCharge", PCharge)
    CreateNodeModelDerivative(device, region, "PCharge", PCharge, "Holes")
    if impact_model != None:
        CreateImpactGeneration(device, region, impact_model)
        equation(device=device, region=region, name="HoleContinuityEquation", variable_name="Holes",
                time_node_model = "PCharge",
                edge_model="HoleCurrent", variable_update="positive", node_model="HoleGeneration",
                edge_volume_model="ImpactGen_p")
    else:
        equation(device=device, region=region, name="HoleContinuityEquation", variable_name="Holes",
                time_node_model = "PCharge",
                edge_model="HoleCurrent", variable_update="positive", node_model="HoleGeneration")
    

def CreatePE(device, region, irradiation_model):
    pne = "-ElectronCharge*kahan3(Holes, -Electrons, NetDoping)"
    if irradiation_model != None:
        pne = "-ElectronCharge*kahan3(Holes, -Electrons, kahan3(NetDoping, TrappedHoles, -TrappedElectrons))"

    CreateNodeModel(device, region, "PotentialNodeCharge", pne)
    CreateNodeModelDerivative(device, region, "PotentialNodeCharge", pne, "Electrons")
    CreateNodeModelDerivative(device, region, "PotentialNodeCharge", pne, "Holes")

    equation(device=device, region=region, name="PotentialEquation", variable_name="Potential",
             node_model="PotentialNodeCharge", edge_model="PotentialEdgeFlux",
             time_node_model="", variable_update="log_damp")


def CreateSiliconDriftDiffusion(device, region, mu_n="mu_n", mu_p="mu_p", irradiation_model=None, irradiation_flux=1e15, impact_model=None):
    if irradiation_model != None:
        CreateIrradiation(device, region, label=irradiation_model, flux=irradiation_flux)
    else:
        CreateNodeModel(device, region, "TrappingRate_n", "0")
        CreateNodeModel(device, region, "TrappingRate_p", "0")
        # For carrier lifetime

    CreatePE(device, region, irradiation_model)
    CreateBernoulli(device, region)
    CreateSRH(device, region, irradiation_model)
    CreateECE(device, region, mu_n, impact_model=impact_model)
    CreateHCE(device, region, mu_p, impact_model=impact_model)

def CreateDiamondDriftDiffusion(device, region, mu_n="mu_n", mu_p="mu_p", 
                                irradiation_model=None, irradiation_flux=1e15, 
                                impact_model=None, incomplete_ionization=True):
    """
    金刚石漂移扩散模型 - 简洁版
    参数:
    - incomplete_ionization: 金刚石需要考虑不完全电离效应（默认True）
    """
    
    # 1. 辐照模型（与硅类似）
    if irradiation_model != None:
        CreateIrradiation(device, region, label=irradiation_model, flux=irradiation_flux)
    else:
        CreateNodeModel(device, region, "TrappingRate_n", "0")
        CreateNodeModel(device, region, "TrappingRate_p", "0")
    
    # 2. 如果不完全电离，创建金刚石特有的不完全电离模型
    #if incomplete_ionization:
    #    CreateDiamondIncompleteIonization(device, region)
    
    # 3. 调用物理模型
    CreatePE(device, region, irradiation_model)
    CreateBernoulli(device, region)
    CreateSRH(device, region, irradiation_model)
    CreateECE(device, region, mu_n, impact_model=impact_model)
    CreateHCE(device, region, mu_p, impact_model=impact_model)


def CreateSiliconDriftDiffusionAtContact(device, region, contact, contact_type, is_circuit=False): 
    '''
      Restrict electrons and holes to their equilibrium values
      Integrates current into circuit
    '''
    if contact_type["type"] == "Schottky":
        workfun = contact_type["workfun"]
        affinity = contact_type["affinity"]
        # gamma=1: Schottky, gamma=0: Bardeen, else: Sze
        if "gamma" in contact_type:
            gamma = contact_type["gamma"]
        else:
            if "delta" in contact_type and "D_s" in contact_type:
                gamma = "Permittivity / (Permittivity + ElectronCharge*ElectronCharge*{0}*{1})".format(contact_type["delta"], contact_type["D_s"])
            else:
                gamma = 1
        phi_0 = "E_g/(3*ElectronCharge)"
        Phi_Bn = "{2}*({0}-{1})+(1-{2})*(E_g/ElectronCharge-{3})".format(workfun, affinity, gamma, phi_0)
        Equi_Electrons = "N_c * exp(-({0}) / Volt_thermal)".format(Phi_Bn)
        Equi_Holes = "N_v * exp((-E_g/ElectronCharge + {0}) / Volt_thermal)".format(Phi_Bn)
        # The units of affinity and workfun are eV, assume q=1e to get the V
        contact_electrons_model = "Electrons - {0}".format(Equi_Electrons)
        contact_holes_model = "Holes - {0}".format(Equi_Holes)
    else:
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

def CreateDiamondDriftDiffusionAtContact(device, region, contact, contact_type, is_circuit=False): 
    '''
      Creates contact boundary conditions for Diamond drift-diffusion model
      为金刚石漂移-扩散模型创建接触边界条件
      
      Args:
        device: 设备对象
        region: 区域名称
        contact: 接触名称
        contact_type: 接触类型字典
        is_circuit: 是否连接到电路
    '''
    # 获取接触偏置名称
    contact_bias = GetContactBiasName(contact)
    
    # 根据接触类型创建不同的边界条件
    #if contact_type["type"] == "Schottky":
        # 金刚石肖特基接触（金刚石功函数较高，势垒大）
    #    workfun = contact_type.get("workfun", 4.8)  # 金属功函数，默认4.8 eV（常用金属）
    #    affinity = contact_type.get("affinity", 0.38)  # 金刚石电子亲和能，默认0.38 eV
        
        # γ参数：考虑界面态影响的修正因子
        # 金刚石表面态密度较低，通常γ接近1
    #    if "gamma" in contact_type:
    #        gamma = contact_type["gamma"]
    #    else:
    #        if "delta" in contact_type and "D_s" in contact_type:
                # Sze模型，考虑界面态
    #            gamma = ("Permittivity / (Permittivity + "
    #                    "ElectronCharge*ElectronCharge*{0}*{1})".format(
    #                    contact_type["delta"], contact_type["D_s"]))
    #        else:
    #            gamma = 1.0  # 默认理想肖特基模型
        
        # 中带电势（金刚石禁带宽，可能需要调整）
    #    phi_0 = "E_g/(2*ElectronCharge)"  # 对于金刚石，可能更适合用E_g/2
        
        # 肖特基势垒高度计算
    #    Phi_Bn = ("{2}*({0}-{1}) + (1-{2})*(E_g/ElectronCharge - {3})".format(
    #             workfun, affinity, gamma, phi_0))
        
        # 平衡电子浓度（热电子发射理论）
        # 金刚石导带有效态密度N_c相对较低
    #    Equi_Electrons = ("N_c * exp(-({0}) / Volt_thermal)".format(Phi_Bn))
        
        # 平衡空穴浓度
   #     Equi_Holes = ("N_v * exp((-E_g/ElectronCharge + {0}) / Volt_thermal)".format(Phi_Bn))
        
        # 边界条件模型
    #    contact_electrons_model = "Electrons - {0}".format(Equi_Electrons)
    #    contact_holes_model = "Holes - {0}".format(Equi_Holes)
        
    #elif contact_type["type"] == "HydrogenTerminated":
        # 氢终端金刚石接触（形成欧姆接触或低势垒接触）
        # 氢终端表面形成2D空穴气，具有独特性质
        
        # 表面偶极层电势降（约1.7 eV）
    #    surface_dipole = contact_type.get("surface_dipole", 1.7)
        
        # 氢终端表面电子亲和能变为负值
    #    surface_affinity = contact_type.get("surface_affinity", -0.38)
        
        # 有效势垒高度（通常较低）
    #    effective_barrier = contact_type.get("effective_barrier", 0.5)
        
        # 氢终端接触载流子浓度
    #    Equi_Electrons = ("N_c * exp(-{0} / Volt_thermal)".format(effective_barrier))
    #    Equi_Holes = ("N_v * exp(-(E_g/ElectronCharge - {0}) / Volt_thermal)".format(effective_barrier))
        
    #    contact_electrons_model = "Electrons - {0}".format(Equi_Electrons)
    #    contact_holes_model = "Holes - {0}".format(Equi_Holes)
        
    if contact_type["type"] == "Ohmic":
        # 金刚石欧姆接触（通常需要重掺杂或特殊处理）
        # 假设celecmodel和cholemodel已定义（通常是费米统计）
        celec_model = contact_type.get("celec_model", 
                                      "n_i*exp(({0}-Potential)/Volt_thermal)".format(contact_bias))
        chole_model = contact_type.get("chole_model", 
                                      "n_i*exp((Potential-{0})/Volt_thermal)".format(contact_bias))
        
        # 欧姆接触边界条件
        contact_electrons_model = "Electrons - ifelse(NetDoping > 0, {0}, n_i^2/{1})".format(celec_model, chole_model)
        
        contact_holes_model =  "Holes - ifelse(NetDoping < 0, +{1}, +n_i^2/{0})".format(celec_model, chole_model)
        
    #else:
        # 默认欧姆接触
    #    celec_model = "n_i*exp(({0}-Potential)/Volt_thermal)".format(contact_bias)
    #    chole_model = "n_i*exp((Potential-{0})/Volt_thermal)".format(contact_bias)
 
  
    #    contact_electrons_model = (
    #        "Electrons - ifelse(NetDoping > 0, "
    #        "{0}, n_i^2/{1})".format(celec_model, chole_model))
       
    #    contact_holes_model = (
    #        "Holes - ifelse(NetDoping < 0, "
    #        "+{1}, +n_i^2/{0})".format(celec_model, chole_model))
        # 创建接触节点模型
    contact_electrons_name = "{0}nodeelectrons".format(contact)
    contact_holes_name = "{0}nodeholes".format(contact)
    
    CreateContactNodeModel(device, contact, contact_electrons_name, contact_electrons_model)
    # 创建导数模型（对Electrons的导数为1）
    CreateContactNodeModel(device, contact, 
                          "{0}:{1}".format(contact_electrons_name, "Electrons"), "1")
    
    CreateContactNodeModel(device, contact, contact_holes_name, contact_holes_model)
    CreateContactNodeModel(device, contact, 
                          "{0}:{1}".format(contact_holes_name, "Holes"), "1")
    
    # 创建接触边界方程
    if is_circuit:
        # 连接到电路的情况
        contact_equation(device=device, contact=contact, 
                         name="ElectronContinuityEquation",
                         node_model=contact_electrons_name,
                         edge_current_model="ElectronCurrent", 
                         circuit_node=contact_bias)
        
        contact_equation(device=device, contact=contact, 
                         name="HoleContinuityEquation",
                         node_model=contact_holes_name,
                         edge_current_model="HoleCurrent", 
                         circuit_node=contact_bias)
    else:
        # 不连接电路的情况
        contact_equation(device=device, contact=contact, 
                         name="ElectronContinuityEquation",
                         node_model=contact_electrons_name,
                         edge_current_model="ElectronCurrent")
        
        contact_equation(device=device, contact=contact, 
                         name="HoleContinuityEquation",
                         node_model=contact_holes_name,
                         edge_current_model="HoleCurrent")
    
    # 金刚石特有的接触效应：场发射（高场下）
    if contact_type.get("enable_field_emission", False):
        CreateDiamondFieldEmissionContact(device, region, contact, contact_type) 


def CreateOxidePotentialOnly(device, region, update_type="default"):
    '''
      Create electric field model in oxide
      Creates Potential solution variable if not available
    '''
    if not InNodeModelList(device, region, "Potential"):
        print("Creating Node Solution Potential")
        CreateSolution(device, region, "Potential")

    # this needs to remove derivatives w.r.t. independents
    CreateEdgeModel(device, region, "ElectricField", "(Potential@n0 - Potential@n1)*EdgeInverseLength")
    CreateEdgeModelDerivatives(device, region, "ElectricField", "(Potential@n0 - Potential@n1)*EdgeInverseLength", "Potential")
    CreateEdgeModel(device, region, "PotentialEdgeFlux", "Permittivity * ElectricField")
    CreateEdgeModelDerivatives(device, region, "PotentialEdgeFlux", "Permittivity * ElectricField", "Potential")
    equation(device=device, region=region, name="PotentialEquation", variable_name="Potential",
             edge_model="PotentialEdgeFlux", variable_update=update_type)

def CreateOxidePotentialOnly(device, region, update_type="default"):
    '''
      Create electric field model in oxide
      Creates Potential solution variable if not available
    '''
    if not InNodeModelList(device, region, "Potential"):
        print("Creating Node Solution Potential")
        CreateSolution(device, region, "Potential")

    # this needs to remove derivatives w.r.t. independents
    CreateEdgeModel(device, region, "ElectricField", "(Potential@n0 - Potential@n1)*EdgeInverseLength")
    CreateEdgeModelDerivatives(device, region, "ElectricField", "(Potential@n0 - Potential@n1)*EdgeInverseLength", "Potential")
    CreateEdgeModel(device, region, "PotentialEdgeFlux", "Permittivity * ElectricField")
    CreateEdgeModelDerivatives(device, region, "PotentialEdgeFlux", "Permittivity * ElectricField", "Potential")
    equation(device=device, region=region, name="PotentialEquation", variable_name="Potential",
             edge_model="PotentialEdgeFlux", variable_update=update_type)

#in the future, worry about workfunction
def CreateOxideContact(device, region, contact):
    set_parameter(name = "Permittivity", value=9.76*8.85e-14)
    conteq="Permittivity *ElectricField"
    contact_bias_name  = GetContactBiasName(contact)
    contact_model_name = GetContactNodeModelName(contact)
    eq = "Potential - {0}".format(contact_bias_name)
    CreateContactNodeModel(device, contact, contact_model_name, eq)
    CreateContactNodeModelDerivative(device, contact, contact_model_name, eq, "Potential")

    #TODO: make everyone use dfield
    if not InEdgeModelList(device, region, contactcharge_edge):
        CreateEdgeModel(device, region, contactcharge_edge, "Permittivity * ElectricField")
        CreateEdgeModelDerivatives(device, region, contactcharge_edge, "Permittivity * ElectricField", "Potential")

    contact_equation(device=device, contact=contact, name="PotentialEquation",
                     node_model=contact_model_name, edge_charge_model= contactcharge_edge)


def CreateSiliconOxideInterface(device, interface):
    '''
      continuous potential at interface
    '''
    model_name = CreateContinuousInterfaceModel(device, interface, "Potential")
    interface_equation(device=device, interface=interface, name="PotentialEquation", interface_model=model_name, type="continuous")

def CreateDiamondOxideInterface(device, interface):
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

def CreateDiamondDiamondInterface(device, interface):
    '''
      Enforces potential, electron, and hole continuity across the interface
    '''
    CreateDiamondOxideInterface(device, interface)
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

