#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

'''
Description:  physics_irradiation.py
@Date       : 2023/10/20
@Author     : XingChen Li, Chenxi Fu, Zhan Li
@version    : 3.0
'''
import math
import devsim
from .model_create import *



# def CreateIrradiation(device, region, label="XingChen", flux=1e15, custom_defect = {}):

#     # if not InEdgeModelList(device, region, "ElectricField"):
#     #     CreateEdgeModel(device, region, "ElectricField", "(Potential@n0-Potential@n1)*EdgeInverseLength")
#     #     CreateEdgeModelDerivatives(device, region, "ElectricField", "(Potential@n0-Potential@n1)*EdgeInverseLength", "Potential")

#     # TODO: change labels into formal names
#     if label == 'XingChen':
#         defects = CreateIrradiationModel_XingChen(device, region)
#     elif label == 'Perugia':
#         defects = CreateIrradiationModel_Perugia(device, region)
#     elif label == 'Schwandt':
#         defects = CreateIrradiationModel_Schwandt(device, region)
#     elif label == 'CommonDefect':
#         defects = CreateIntrinsicModel_SiCCommonDefect(device, region)
#     elif label in ("Diamond","Diamond3Level",):
#         defects = CreateIrradiationModel_Diamond3Level(device,region)    
#     else:
#         defects = custom_defect

#     TrappedElectrons="0"
#     TrappedHoles="0"
#     TrappingRate_n="0"
#     TrappingRate_p="0"
#     U_r = "0"
#     # 辐照缺陷渐进加载参数：
#     # flux=0 时直接使用本征缺陷；
#     # flux>0 时先从 N_t0 开始，再由 loop_section 渐进加载到目标浓度。
#     initial_irradiation_scale = (
#         1.0 if float(flux) <= 0.0 else 0.0
#     )

#     devsim.set_parameter(
#         device=device,
#         region=region,
#         name="IrradiationScale",
#         value=initial_irradiation_scale,
#     )
#     for defect in defects:
#         name, E_t_ev, g_int, sigma_n_irr, sigma_p_irr = ( defect['name'], defect['E_t_ev'], defect['g_int'], defect['sigma_n_irr'], defect['sigma_p_irr'],
#         )
#         e = 1.6*1e-19
#         E_t = E_t_ev * e
#         #N_t_irr = g_int*flux
#         N_t0 = float(defect.get("N_t0", 0.0))
#         N_t_sat = float(
#             defect.get(
#                 "N_t_sat",
#                 float("inf"),
#             )
#         )
#         fluence_scale = float(
#             defect.get(
#                 "fluence_scale",
#                 1.0,
#             )
#         )

#         effective_fluence = max(
#             float(flux),
#             0.0,
#         ) * fluence_scale

#         N_t_irr = N_t0 + g_int * effective_fluence

#         if math.isfinite(N_t_sat):
#             N_t_irr = min(
#                 N_t_irr,
#                 N_t_sat,
#             )        
#         devsim.set_parameter(device=device, region=region, name="sigma_n_irr_"+name,   value=sigma_n_irr)
#         devsim.set_parameter(device=device, region=region, name="sigma_p_irr_"+name,   value=sigma_p_irr)
#         #devsim.set_parameter(device=device, region=region, name="N_t_irr_"+name,   value=N_t_irr)
#         devsim.set_parameter(device=device,region=region,name="N_t0_" + name,value=N_t0,)
#         devsim.set_parameter(device=device,region=region,name="N_t_target_" + name,value=N_t_irr,)
#         # 实际参与计算的缺陷浓度：
#         # scale=0 → N_t0
#         # scale=1 → N_t_target
#         CreateNodeModel(device,region,"N_t_irr_" + name,("N_t0_{name}""+IrradiationScale""*(N_t_target_{name}-N_t0_{name})").format(name=name),)
#         print("[Irradiation] {}: N_t0={:.6e}, target={:.6e}, flux={:.6e}".format(name,N_t0,N_t_irr,float(flux),))
#         devsim.set_parameter(device=device, region=region, name="E_t_"+name,   value=E_t)

#         r_n = "(vel_mean * sigma_n_irr_{name})".format(name=name)#c_n
#         n_1 = "(N_c * exp(-(E_g/2 - E_t_{name})/k_T))".format(name=name)#e_n
#         r_p = "(vel_mean * sigma_p_irr_{name})".format(name=name)#c_p
#         p_1 = "(N_v * exp(-(E_t_{name} - (-E_g/2))/k_T))".format(name=name)#e_p
#         denominator = ("({r_n}*(Electrons+{n_1})""+{r_p}*(Holes+{p_1})""+1e-20)").format(r_n=r_n,n_1=n_1,r_p=r_p,p_1=p_1,)
#         occupancy_n = ("(N_t_irr_{name}*""(Electrons*{r_n}+{p_1}*{r_p})""/{denominator})").format(name=name,r_n=r_n,r_p=r_p,n_1=n_1,p_1=p_1,denominator=denominator,)
#         occupancy_p = ("(N_t_irr_{name}*""(Holes*{r_p}+{n_1}*{r_n})""/{denominator})").format(name=name,r_n=r_n,r_p=r_p,n_1=n_1,p_1=p_1,denominator=denominator,)
#         n_t_irr_n = "+" + occupancy_n
#         n_t_irr_p = "+" + occupancy_p
#         trap_n = ("+(vel_mean*sigma_n_irr_{name})*{occupancy}").format(name=name,occupancy=occupancy_n,)
#         trap_p = ("+(vel_mean*sigma_p_irr_{name})*{occupancy}").format(name=name,occupancy=occupancy_p,)
#         U_r_i = ("+(N_t_irr_{name}*{r_n}*{r_p}""*(Electrons*Holes-n_i^2)""/{denominator})").format(name=name,r_n=r_n,r_p=r_p,denominator=denominator,)
#         # n_t_irr_n = "+(N_t_irr_{name}*(Electrons*{r_n}+{p_1}*{r_p})/({r_n}*(Electrons+{n_1})+{r_p}*(Holes+{p_1})))".format(name=name,r_n=r_n,n_1=n_1,r_p=r_p,p_1=p_1)
#         # n_t_irr_p = "+(N_t_irr_{name}*(Holes*{r_p}+{n_1}*{r_n})/({r_n}*(Electrons+{n_1})+{r_p}*(Holes+{p_1})))".format(name=name,r_n=r_n,n_1=n_1,r_p=r_p,p_1=p_1)
#         # trap_n = "+(vel_mean * sigma_n_irr_{name})*(N_t_irr_{name}*(Electrons*{r_n}+{p_1}*{r_p})/({r_n}*(Electrons+{n_1})+{r_p}*(Holes+{p_1})))".format(name=name,r_n=r_n,n_1=n_1,r_p=r_p,p_1=p_1)
#         # trap_p = "+(vel_mean * sigma_p_irr_{name})*(N_t_irr_{name}*(Holes*{r_p}+{n_1}*{r_n})/({r_n}*(Electrons+{n_1})+{r_p}*(Holes+{p_1})))".format(name=name,r_n=r_n,n_1=n_1,r_p=r_p,p_1=p_1)
#         # U_r_i="+(N_t_irr_{name}*{r_n}*{r_p}*(Electrons*Holes-n_i^2)/({r_n}*(Electrons+{n_1})+{r_p}*(Holes+{p_1})))".format(name=name,r_n=r_n,n_1=n_1,r_p=r_p,p_1=p_1)

#         TrappedElectrons=TrappedElectrons+n_t_irr_n
#         TrappedHoles=TrappedHoles+n_t_irr_p
#         TrappingRate_n=TrappingRate_n+trap_n
#         TrappingRate_p=TrappingRate_p+trap_p
#         U_r = U_r+U_r_i
    

#     CreateNodeModel(device, region, "TrappedElectrons", TrappedElectrons)
#     CreateNodeModel(device, region, "TrappedHoles", TrappedHoles)
#     for i in ("Electrons", "Holes", "Potential"):
#         CreateNodeModelDerivative(device, region, "TrappedElectrons", TrappedElectrons, i)
#         CreateNodeModelDerivative(device, region, "TrappedHoles", TrappedHoles, i)
    
#     CreateNodeModel(device, region, "U_r", U_r)
#     for i in ("Electrons", "Holes"):
#         CreateNodeModelDerivative(device, region, "U_r", U_r, i)

#     CreateNodeModel(device, region, "TrappingRate_n", TrappingRate_n)
#     CreateNodeModel(device, region, "TrappingRate_p", TrappingRate_p)
def CreateIrradiation(
    device,
    region,
    label="XingChen",
    flux=1e15,
    custom_defect=None,
):
    model_map = {
        "XingChen": CreateIrradiationModel_XingChen,
        "Perugia": CreateIrradiationModel_Perugia,
        "Schwandt": CreateIrradiationModel_Schwandt,
        "CommonDefect": CreateIntrinsicModel_SiCCommonDefect,
        "Diamond": CreateIrradiationModel_Diamond3Level,
        "Diamond3Level": CreateIrradiationModel_Diamond3Level,
    }

    if label in model_map:
        defects = model_map[label](device, region)
    elif custom_defect is not None:
        defects = custom_defect
    else:
        raise ValueError(
            f"Unknown irradiation model: {label}"
        )

    flux = max(float(flux), 0.0)
    is_diamond = label in ("Diamond", "Diamond3Level")

    if is_diamond:
        devsim.set_parameter(
            device=device,
            region=region,
            name="CarrierFloor",
            value=1.0,
        )

        # flux=0 时直接使用 N_t0；
        # flux>0 时从 N_t0 开始逐步增加到目标浓度。
        devsim.set_parameter(
            device=device,
            region=region,
            name="IrradiationScale",
            value=1.0 if flux <= 0.0 else 0.0,
        )

    TrappedElectrons = "0"
    TrappedHoles = "0"
    TrappingRate_n = "0"
    TrappingRate_p = "0"
    U_r = "0"

    q = 1.602176634e-19

    for defect in defects:
        name = defect["name"]

        E_t_ev = float(defect["E_t_ev"])
        sigma_n_irr = float(defect["sigma_n_irr"])
        sigma_p_irr = float(defect["sigma_p_irr"])

        if (
            "N_t0" in defect
            and "g_int" in defect
        ):
            N_t0 = float(defect["N_t0"])
            g_int = float(defect["g_int"])
            fluence_scale = float(
                defect.get("fluence_scale", 1.0)
            )

            N_t_target = (
                N_t0
                + g_int
                * flux
                * fluence_scale
            )

            if "N_t_sat" in defect:
                N_t_target = min(
                    N_t_target,
                    float(defect["N_t_sat"]),
                )

            if is_diamond:
                devsim.set_parameter(
                    device=device,
                    region=region,
                    name="N_t0_" + name,
                    value=N_t0,
                )

                devsim.set_parameter(
                    device=device,
                    region=region,
                    name="N_t_target_" + name,
                    value=N_t_target,
                )

                CreateNodeModel(
                    device,
                    region,
                    "N_t_irr_" + name,
                    "N_t0_{0} + "
                    "IrradiationScale * "
                    "(N_t_target_{0} - N_t0_{0})"
                    .format(name),
                )

                print(
                    "[Irradiation] {0}: "
                    "N_t0={1:.6e}, "
                    "target={2:.6e}, "
                    "flux={3:.6e}".format(
                        name,
                        N_t0,
                        N_t_target,
                        flux,
                    )
                )
            else:
                devsim.set_parameter(
                    device=device,
                    region=region,
                    name="N_t_irr_" + name,
                    value=N_t_target,
                )
        else:
            N_t_irr = float(
                defect.get("N_t", 0.0)
            )

            devsim.set_parameter(
                device=device,
                region=region,
                name="N_t_irr_" + name,
                value=N_t_irr,
            )

        E_t = E_t_ev * q

        devsim.set_parameter(
            device=device,
            region=region,
            name="sigma_n_irr_" + name,
            value=sigma_n_irr,
        )

        devsim.set_parameter(
            device=device,
            region=region,
            name="sigma_p_irr_" + name,
            value=sigma_p_irr,
        )

        devsim.set_parameter(
            device=device,
            region=region,
            name="E_t_" + name,
            value=E_t,
        )

        r_n = (
            "(vel_mean * sigma_n_irr_{0})"
            .format(name)
        )

        r_p = (
            "(vel_mean * sigma_p_irr_{0})"
            .format(name)
        )

        n_1 = (
            "(N_c * exp("
            "-(E_g/2 - E_t_{0})/k_T))"
            .format(name)
        )

        p_1 = (
            "(N_v * exp("
            "-(E_t_{0} - (-E_g/2))/k_T))"
            .format(name)
        )

        # 在 Newton 迭代中保护电子、空穴浓度。
        # 防止负值、零值进入陷阱占据率分母。
        n_safe = (
            "(ifelse("
            "Electrons > CarrierFloor, "
            "Electrons, CarrierFloor))"
        )

        p_safe = (
            "(ifelse("
            "Holes > CarrierFloor, "
            "Holes, CarrierFloor))"
        )

        denominator = (
            "({r_n}*({n}+{n_1})"
            "+{r_p}*({p}+{p_1})"
            "+1e-30)"
        ).format(
            r_n=r_n,
            n=n_safe,
            n_1=n_1,
            r_p=r_p,
            p=p_safe,
            p_1=p_1,
        )

        trapped_electrons = (
            "+(N_t_irr_{name}*"
            "({n}*{r_n}+{p_1}*{r_p})"
            "/({denominator}))"
        ).format(
            name=name,
            n=n_safe,
            r_n=r_n,
            p_1=p_1,
            r_p=r_p,
            denominator=denominator,
        )

        trapped_holes = (
            "+(N_t_irr_{name}*"
            "({p}*{r_p}+{n_1}*{r_n})"
            "/({denominator}))"
        ).format(
            name=name,
            p=p_safe,
            r_p=r_p,
            n_1=n_1,
            r_n=r_n,
            denominator=denominator,
        )

        trapping_rate_n = (
            "+(vel_mean*sigma_n_irr_{name})*"
            "(N_t_irr_{name}*"
            "({n}*{r_n}+{p_1}*{r_p})"
            "/({denominator}))"
        ).format(
            name=name,
            n=n_safe,
            r_n=r_n,
            p_1=p_1,
            r_p=r_p,
            denominator=denominator,
        )

        trapping_rate_p = (
            "+(vel_mean*sigma_p_irr_{name})*"
            "(N_t_irr_{name}*"
            "({p}*{r_p}+{n_1}*{r_n})"
            "/({denominator}))"
        ).format(
            name=name,
            p=p_safe,
            r_p=r_p,
            n_1=n_1,
            r_n=r_n,
            denominator=denominator,
        )

        irradiation_recombination = (
            "+(N_t_irr_{name}*"
            "{r_n}*{r_p}*"
            "({n}*{p}-n_i^2)"
            "/({denominator}))"
        ).format(
            name=name,
            n=n_safe,
            p=p_safe,
            r_n=r_n,
            r_p=r_p,
            denominator=denominator,
        )

        TrappedElectrons += trapped_electrons
        TrappedHoles += trapped_holes
        TrappingRate_n += trapping_rate_n
        TrappingRate_p += trapping_rate_p
        U_r += irradiation_recombination

    CreateNodeModel(
        device,
        region,
        "TrappedElectrons",
        TrappedElectrons,
    )

    CreateNodeModel(
        device,
        region,
        "TrappedHoles",
        TrappedHoles,
    )

    for variable in (
        "Electrons",
        "Holes",
        "Potential",
    ):
        CreateNodeModelDerivative(
            device,
            region,
            "TrappedElectrons",
            TrappedElectrons,
            variable,
        )

        CreateNodeModelDerivative(
            device,
            region,
            "TrappedHoles",
            TrappedHoles,
            variable,
        )

    CreateNodeModel(
        device,
        region,
        "U_r",
        U_r,
    )

    for variable in (
        "Electrons",
        "Holes",
    ):
        CreateNodeModelDerivative(
            device,
            region,
            "U_r",
            U_r,
            variable,
        )

    CreateNodeModel(
        device,
        region,
        "TrappingRate_n",
        TrappingRate_n,
    )

    CreateNodeModel(
        device,
        region,
        "TrappingRate_p",
        TrappingRate_p,
    )

def CreateIrradiationModel_Diamond3Level(
    device,
    region,
):
    """
    Diamond three-level irradiation model.

    Energy reference:
        E_v = -Eg / 2
        E_c = +Eg / 2
        E_t is measured from mid-gap.

    N_t = min(
        N_t0 + g_int * fluence * fluence_scale,
        N_t_sat,
    )
    """

    Eg = 5.47

    defects = [
        {
            "name": "H1_Ev0p75",

            # E_v + 0.75 eV
            "E_t_ev": -Eg / 2.0 + 0.75,

            "N_t0": 1.0e10,
            "g_int": 5.0e-2,
            "N_t_sat": 5.0e13,
            "fluence_scale": 1.0,

            "sigma_n_irr": 1.0e-15,
            "sigma_p_irr": 1.0e-13,
        },
        {
            "name": "E1_Ec0p95",

            # E_c - 0.95 eV
            "E_t_ev": Eg / 2.0 - 0.95,

            "N_t0": 1.0e10,
            "g_int": 4.0e-2,
            "N_t_sat": 4.0e13,
            "fluence_scale": 1.0,

            "sigma_n_irr": 1.0e-13,
            "sigma_p_irr": 1.0e-15,
        },
        {
            "name": "RC_Mid",

            # mid-gap defect
            "E_t_ev": 0.0,

            "N_t0": 5.0e9,
            "g_int": 2.0e-2,
            "N_t_sat": 2.0e13,
            "fluence_scale": 1.0,

            "sigma_n_irr": 1.0e-15,
            "sigma_p_irr": 1.0e-15,
        },
    ]

    return defects

# def CreateIrradiationModel_Diamond3Level(device, region):
#     """
#     Diamond 3-level irradiation model

#     说明：
#     1) 能级位置参考文献：
#        - hole trap: Ev + 0.75 eV
#        - electron trap: Ec - 0.95 eV
#     2) 初始本征陷阱浓度 N_t0 取 ~1e13 cm^-3 量级
#     3) 辐照后采用 N_t = N_t0 + g_int * Phi_eff
#     4) 高注量下加入 N_t_sat，反映文献中的饱和趋势
#     5) g_int 这里是“工程起始值”，需要你后续结合 TCT/CCE/IV 再拟合
#     """

#     Eg = 5.47  # eV
#     defects = [
#         {
#             "name": "H1_Ev0p75",
#             "E_t_ev": -Eg / 2 + 0.75,
#             "N_t0": 1.0e13,
#             "g_int": 5.0e-2,      # cm^-1，起始拟合值
#             "N_t_sat": 5.0e13,    # cm^-3，反映高注量饱和
#             "fluence_scale": 1.0,
#             "sigma_n_irr": 1.0e-15,
#             "sigma_p_irr": 1.0e-13,
#         },
#         {
#             "name": "E1_Ec0p95",
#             "E_t_ev": Eg / 2 - 0.95,
#             "N_t0": 1.0e13,
#             "g_int": 4.0e-2,      # cm^-1，起始拟合值
#             "N_t_sat": 4.0e13,
#             "fluence_scale": 1.0,
#             "sigma_n_irr": 1.0e-13,
#             "sigma_p_irr": 1.0e-15,
#         },
#         {
#             "name": "RC_Mid",
#             "E_t_ev": 0.0,
#             "N_t0": 5.0e12,
#             "g_int": 2.0e-2,      # cm^-1，起始拟合值
#             "N_t_sat": 2.0e13,
#             "fluence_scale": 1.0,
#             "sigma_n_irr": 1.0e-15,
#             "sigma_p_irr": 1.0e-15,
#         },
#     ]
#     return defects




def CreateIrradiationModel_XingChen(device, region):
    """
    Si Irradiation model
    """
    
    defects = []
    defects.append({"name" : "E30K", "E_t_ev" : 0.56-0.1,   "g_int" : 2.0810, "sigma_n_irr" : 2.300e-14, "sigma_p_irr" : 2.920e-16,})
    defects.append({"name" : "V3",   "E_t_ev" : 0.56-0.458, "g_int" : 1.6504, "sigma_n_irr" : 2.551e-14, "sigma_p_irr" : 1.551e-13,})
    defects.append({"name" : "Ip",   "E_t_ev" : 0.56-0.545, "g_int" : 0.6936, "sigma_n_irr" : 4.478e-15, "sigma_p_irr" : 6.709e-15,})
    defects.append({"name" : "H220", "E_t_ev" : -0.56+0.48, "g_int" : 2.6112, "sigma_n_irr" : 4.166e-15, "sigma_p_irr" : 1.965e-16,})
    defects.append({"name" : "CiOi", "E_t_ev" : -0.56+0.36, "g_int" : 1.6511, "sigma_n_irr" : 3.230e-17, "sigma_p_irr" : 2.036e-14,})

    return defects


def CreateIrradiationModel_Perugia(device, region):
    """
    Si Irradiation model
    """

    defects = []
    defects.append({"name" : "DA1", "E_t_ev" : 0.56-0.42, "g_int" : 1.613, "sigma_n_irr" : 1e-15,     "sigma_p_irr" : 1e-14,})
    defects.append({"name" : "DA2", "E_t_ev" : 0.56-0.46, "g_int" : 0.9,   "sigma_n_irr" : 7e-15,     "sigma_p_irr" : 7e-14,})
    defects.append({"name" : "DD",  "E_t_ev" : -0.56+0.36, "g_int" : 0.9,   "sigma_n_irr" : 3.23e-13,  "sigma_p_irr" : 3.23e-14,})

    return defects


def CreateIrradiationModel_Schwandt(device, region):
    """
    Si Irradiation model
    """

    defects = []
    defects.append({"name" : "E30K", "E_t_ev" : 0.56-0.1,   "g_int" : 0.0497, "sigma_n_irr" : 2.300e-14, "sigma_p_irr" : 2.920e-16,})
    defects.append({"name" : "V3",   "E_t_ev" : 0.56-0.458, "g_int" : 0.6447, "sigma_n_irr" : 2.551e-14, "sigma_p_irr" : 1.551e-13,})
    defects.append({"name" : "Ip",   "E_t_ev" : 0.56-0.545, "g_int" : 0.4335, "sigma_n_irr" : 4.478e-15, "sigma_p_irr" : 6.709e-15,})
    defects.append({"name" : "H220", "E_t_ev" : -0.56+0.48, "g_int" : 0.5978, "sigma_n_irr" : 4.166e-15, "sigma_p_irr" : 1.965e-16,})
    defects.append({"name" : "CiOi", "E_t_ev" : -0.56+0.36, "g_int" : 0.3780, "sigma_n_irr" : 3.230e-17, "sigma_p_irr" : 2.036e-14,})

    return defects

def CreateIntrinsicModel_SiCCommonDefect(device, region):
    """
    SiC Intrinsic Defect model
    """
    
    defects = []
    defects.append({"name" : "Z12",  "E_t_ev" : 1.63-0.67, "g_int" : 1, "sigma_n_irr" : 3e-16, "sigma_p_irr" : 2e-12,})
    defects.append({"name" : "EH67", "E_t_ev" : 1.63-1.65, "g_int" : 1, "sigma_n_irr" : 2e-17, "sigma_p_irr" : 3e-17,})

    return defects
