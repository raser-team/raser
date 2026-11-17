"""Material and polarization parameters for the exploratory AlGaN/GaN HEMT.

Values are recovered from the project's 2026-10-26 working integration
snapshot.  They are model inputs, not independently calibrated constants.
This module is intentionally isolated from legacy Si/SiC parameter setup.
"""

from __future__ import annotations

import math

import devsim

def _hemt_ambacher_values(x, pseudomorphic=True, ga_face=True):
    if not 0.0 <= x <= 1.0:
        raise ValueError("hemt_physics.al_mole_fraction must be between 0 and 1")
    a_gan = 3.189
    a_algan = 3.189 - 0.077 * x
    strain = (a_gan - a_algan) / a_algan if pseudomorphic else 0.0
    e31 = -0.49 - 0.11 * x
    e33 = 0.73 + 0.73 * x
    c13 = 103.0 + 5.0 * x
    c33 = 405.0 - 32.0 * x
    psp_gan = -0.029
    psp_algan = -0.029 - 0.052 * x
    ppz_algan = 2 * strain * (e31 - e33 * c13 / c33)
    sigma = (psp_gan - psp_algan - ppz_algan) * (1 if ga_face else -1)
    eg_gan = 3.42
    eg_algan = (1 - x) * eg_gan + x * 6.13 - x * (1 - x)
    return {
        "x": x, "Psp_GaN_C_m2": psp_gan, "Psp_AlGaN_C_m2": psp_algan,
        "Ppz_AlGaN_C_m2": ppz_algan, "SigmaPol_C_m2": sigma,
        "SigmaPol_C_cm2": sigma / 1e4, "Eg_GaN_eV": eg_gan,
        "Eg_AlGaN_eV": eg_algan, "DeltaEc_eV": 0.7 * (eg_algan - eg_gan),
        "eps_GaN": 9.5, "eps_AlGaN": 9.5 - 0.5 * x,
        "PhiBn_eV": 0.84 + 1.3 * x,
    }

def _hemt_literature_values(v, cfg):
    """Literature-based material sets; never fit intrinsic P to Hall ns."""
    x = v["x"]
    pol = cfg.get("polarization_parameter_set", "ambacher_1999")
    band = cfg.get("band_parameter_set", "ambacher_1999")

    if pol not in ("ambacher_1999", "lee_2002"):
        raise ValueError("Unknown polarization model: " + str(pol))
    if band not in ("ambacher_1999", "lee_2002",
                    "ibbetson_2000_x034"):
        raise ValueError("Unknown band model: " + str(band))

    if pol == "lee_2002":
        # Lee 2002, ETRI Journal 24(4), Table 1
        a0 = 3.189
        a1 = 3.189 - 0.077*x
        strain = ((a0-a1)/a1
                  if cfg.get("pseudomorphic_barrier", True)
                  else 0.0)

        e31 = -0.22 - 0.36*x
        e33 = 0.44 + 1.11*x
        c13 = 114.0 + 6.0*x
        c33 = 209.0 + 186.0*x

        ppz = 2*strain*(e31-e33*c13/c33)
        psp_ga = -0.029
        psp_al = -0.029-0.052*x

        sigma = (psp_ga-psp_al-ppz)*(
            1 if cfg.get("ga_face", True) else -1
        )

        v.update(
            Psp_GaN_C_m2=psp_ga,
            Psp_AlGaN_C_m2=psp_al,
            Ppz_AlGaN_C_m2=ppz,
            SigmaPol_C_m2=sigma,
            SigmaPol_C_cm2=sigma/1e4,
            eps_GaN=10.0,
            eps_AlGaN=10.0-1.5*x
        )

    if band == "lee_2002":
        # Lee Table 1: DeltaEc = 0.7*(2.12*x+0.6*x*x)
        gap = 2.12*x + 0.6*x*x
        v["DeltaEc_eV"] = 0.7*gap
        v["Eg_AlGaN_eV"] = v["Eg_GaN_eV"]+gap
        v["ElectronMassAlGaN_m0"] = 0.22+0.11*x

    elif band == "ibbetson_2000_x034":
        # Sample-specific published approximations, not general Eg(x)
        if abs(x-0.34) > 0.002:
            raise ValueError("Ibbetson sample option requires x=0.34")
        v["DeltaEc_eV"] = 0.69
        v["Eg_AlGaN_eV"] = 4.3

    return v

def _hemt_nc(T):
    kb = 1.380649e-23
    h = 6.62607015e-34
    me = 9.1093837139e-31
    return 2.0 * (2.0 * math.pi * (0.22 * me) * kb * T / h**2)**1.5 / 1e6

def _hemt_material_constants(T, device, region, material, values):
    x = values["x"]
    q = 1.602176634e-19
    eps0 = 8.8541878128e-14
    kb = 1.380649e-23
    nc = _hemt_nc(T)
    if material == "AlGaN" and "ElectronMassAlGaN_m0" in values:
        nc *= (values["ElectronMassAlGaN_m0"]/0.22)**1.5
    nv = 4.6e19
    is_algan = material == "AlGaN"
    eg_ev = values["Eg_AlGaN_eV"] if is_algan else values["Eg_GaN_eV"]
    epsr = values["eps_AlGaN"] if is_algan else values["eps_GaN"]
    eg_j = eg_ev * q
    ni = math.sqrt(nc * nv) * math.exp(-eg_j / (2 * kb * T))
    params = {
        "N_c": nc, "N_v": nv, "E_g": eg_j, "eps": epsr,
        "Permittivity": epsr * eps0, "n_i": ni,
        "n1": ni, "p1": ni, "E_g_eV": eg_ev,
        "EcOffset_eV": values["DeltaEc_eV"] if is_algan else 0.0,
        "AlMoleFraction": x if is_algan else 0.0,
        "PolarizationSp_C_m2": values["Psp_AlGaN_C_m2"] if is_algan else values["Psp_GaN_C_m2"],
        "PolarizationPz_C_m2": values["Ppz_AlGaN_C_m2"] if is_algan else 0.0,
        "SigmaPol_C_m2": values["SigmaPol_C_m2"],
        "SigmaPol_C_cm2": values["SigmaPol_C_cm2"],
        "SchottkyPhiBn_eV": values["PhiBn_eV"],
    }
    for name, value in params.items():
        devsim.set_parameter(device=device, region=region, name=name, value=value)
    devsim.set_parameter(device=device, region=region, name="T", value=T)
    devsim.set_parameter(device=device, region=region, name="k_T", value=kb * T)
    devsim.set_parameter(device=device, region=region, name="Volt_thermal", value=kb * T / q)

def initialize_hemt_materials(detector, device, create_global_constant, create_node_model):
    """Initialize all HEMT semiconductor regions, not the detector-name pseudo-region.

    Legacy create_parameter() receives ``detector.region``, which is the
    device name, while actual DEVSIM HEMT regions have different names.
    """
    hp = detector.device_dict["hemt_physics"]
    if hp.get("transport_model") != "drift_diffusion_v1":
        raise ValueError("HEMT material initialization requires drift_diffusion_v1")
    temperature = float(detector.device_dict["temperature"])
    if abs(temperature - 300.0) > 1e-8:
        raise ValueError("Initial HEMT parameterization is restricted to 300 K")

    values = _hemt_ambacher_values(
        float(hp["al_mole_fraction"]),
        pseudomorphic=bool(hp.get("pseudomorphic_barrier", True)),
        ga_face=bool(hp.get("ga_face", True)),
    )
    values = _hemt_literature_values(values, hp)
    regions = devsim.get_region_list(device=device)
    materials = {r: devsim.get_material(device=device, region=r) for r in regions}
    expected = {"AlGaN_barrier": "AlGaN", "GaN_buffer": "GaN"}
    for region, material in expected.items():
        if materials.get(region) != material:
            raise ValueError(
                f"HEMT region {region!r} must use material {material!r}; "
                f"got {materials.get(region)!r}"
            )

    for region, material in expected.items():
        create_global_constant(temperature, device, region)
        _hemt_material_constants(temperature, device, region, material, values)
        # Preserve the generic U_const contract for these semiconductor regions.
        create_node_model(
            device, region, "U_const", detector.device_dict.get("U_const", 0)
        )

    sigma = values["SigmaPol_C_cm2"]
    if not math.isfinite(sigma):
        raise ValueError("Non-finite HEMT polarization charge")
    return values
