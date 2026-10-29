#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exploratory 2D AlGaN/GaN HEMT drift-diffusion branch for RASER/DEVSIM.

This is an isolated electron-only DC transport branch. It preserves the existing
RASER material/mesh creation and HEMT polarization parameterization, but it does
NOT claim full quantitative validation: no hole transport, SRH recombination,
self-heating, impact ionization, gate leakage, or Schrödinger quantum confinement.
The electron density uses DEVSIM's built-in 3D Fermi-Dirac approximation and the
current is driven by the electron quasi-Fermi potential. Polarization is spread
as a normalized half-Gaussian on the GaN side of the heterointerface.

The new device config places source/drain contacts on the lateral GaN edges and
the gate on the AlGaN top surface. This is a deliberate simplified test geometry,
not a claim to reproduce a real recessed/annealed ohmic contact profile.
"""

import csv
import json
import math
from pathlib import Path

import devsim

from . import model_create
from .create_mesh import DevsimMesh
from .create_parameter import create_parameter

Q = 1.602176634e-19
KB = 1.380649e-23
ALGAN = "AlGaN_barrier"
GAN = "GaN_buffer"
IFACE = "AlGaN_GaN_interface"


def _node(device, region, name, expression):
    model_create.CreateNodeModel(device, region, name, expression)


def _edge(device, region, name, expression):
    model_create.CreateEdgeModel(device, region, name, expression)


def _solve(device, cfg, stage):
    opts = cfg.get("solver", {})
    args = {
        "type": "dc",
        "absolute_error": float(opts.get("absolute_error", 1e-12)),
        "relative_error": float(opts.get("relative_error", 1e-7)),
        "maximum_iterations": int(opts.get("maximum_iterations", 100)),
    }
    try:
        devsim.solve(**args)
    except Exception as exc:
        raise RuntimeError(
            f"HEMT_TRANSPORT_V1 solve failed during {stage}; "
            f"solver options={args}"
        ) from exc


def _set_device_parameter(device, name, value):
    devsim.set_parameter(device=device, name=name, value=float(value))


def _create_potential_contact(device, contact, bias_parameter):
    model = f"HT1_{contact}_PotentialBC"
    model_create.CreateContactNodeModel(
        device, contact, model, f"Potential-{bias_parameter}"
    )
    model_create.CreateContactNodeModel(device, contact, f"{model}:Potential", "1")
    devsim.contact_equation(
        device=device,
        contact=contact,
        name="PotentialEquation",
        node_model=model,
        edge_charge_model="PotentialEdgeFlux",
    )


def _create_fn_contact(device, contact, bias_parameter):
    model = f"HT1_{contact}_FnBC"
    model_create.CreateContactNodeModel(
        device, contact, model, f"HEMT_Fn-{bias_parameter}"
    )
    model_create.CreateContactNodeModel(device, contact, f"{model}:HEMT_Fn", "1")
    devsim.contact_equation(
        device=device,
        contact=contact,
        name="ElectronContinuityEquation",
        node_model=model,
        edge_current_model="ElectronCurrent",
    )


def _create_region_models(device, region, material, ef, mobility, cfg, interface_y_cm):
    """Create a coupled Potential / electron quasi-Fermi system for one region."""
    devsim.set_parameter(device=device, region=region, name="HEMT_mu_n", value=float(mobility))
    devsim.set_parameter(device=device, region=region, name="HEMT_Ef_initial", value=float(ef))

    model_create.CreateSolution(device, region, "Potential")
    model_create.CreateSolution(device, region, "HEMT_Fn")
    devsim.node_model(device=device, region=region, name="PotentialInitialZero", equation="0.0")
    devsim.set_node_values(device=device, region=region, name="Potential", init_from="PotentialInitialZero")
    devsim.node_model(device=device, region=region, name="HEMT_FnInitial", equation=f"{float(ef):.16g}")
    devsim.set_node_values(
        device=device, region=region, name="HEMT_Fn", init_from="HEMT_FnInitial"
    )

    eta = "(HEMT_Fn+Potential-EcOffset_eV)/Volt_thermal"
    _node(device, region, "HEMT_Eta", eta)
    _node(device, region, "HEMT_EtaSafe", "max(HEMT_Eta, -10)")
    _node(device, region, "Electrons", "N_c*Fermi(HEMT_EtaSafe)*exp(HEMT_Eta-HEMT_EtaSafe)")
    # DEVSIM's built-in Fermi approximation requires dFermidx in the Jacobian;
    # using n/Vt would be incorrect in the degenerate regime.
    _node(device, region, "HEMT_dndF", "N_c*ifelse(HEMT_Eta < -10, Fermi(HEMT_EtaSafe)*exp(HEMT_Eta-HEMT_EtaSafe), dFermidx(HEMT_EtaSafe))/Volt_thermal")
    _node(device, region, "Electrons:Potential", "HEMT_dndF")
    _node(device, region, "Electrons:HEMT_Fn", "HEMT_dndF")
    devsim.edge_from_node_model(device=device, region=region, node_model="Electrons")
    devsim.edge_from_node_model(device=device, region=region, node_model="HEMT_dndF")

    if material == "GaN":
        hp = cfg["hemt_physics"]
        spread_nm = float(hp.get("polarization_spread_nm", 5.0))
        if spread_nm < 1.0:
            raise ValueError("polarization_spread_nm must be >= 1 nm for this preliminary mesh model")
        sigma = float(devsim.get_parameter(device=device, region=region, name="SigmaPol_C_cm2"))
        devsim.set_parameter(device=device, region=region, name="HEMT_PolSigma", value=sigma)
        devsim.set_parameter(device=device, region=region, name="HEMT_PolWidth", value=spread_nm * 1e-7)
        devsim.set_parameter(device=device, region=region, name="HEMT_InterfaceY", value=float(interface_y_cm))
        devsim.set_parameter(device=device, region=region, name="HEMT_PolScale", value=0.0)
        pol = (
            "HEMT_PolScale*HEMT_PolSigma*0.7978845608028654/HEMT_PolWidth*"
            "exp(-0.5*((y-HEMT_InterfaceY)/HEMT_PolWidth)^2)"
        )
        _node(device, region, "PolarizationVolume", pol)
    else:
        _node(device, region, "PolarizationVolume", "0")

    _node(
        device, region, "PotentialNodeCharge",
        "ElectronCharge*(Electrons-NetDoping)-PolarizationVolume",
    )
    _node(device, region, "PotentialNodeCharge:Potential", "ElectronCharge*HEMT_dndF")
    _node(device, region, "PotentialNodeCharge:HEMT_Fn", "ElectronCharge*HEMT_dndF")

    field = "(Potential@n0-Potential@n1)*EdgeInverseLength"
    _edge(device, region, "ElectricField", field)
    model_create.CreateEdgeModelDerivatives(device, region, "ElectricField", field, "Potential")
    flux = "Permittivity*ElectricField"
    _edge(device, region, "PotentialEdgeFlux", flux)
    model_create.CreateEdgeModelDerivatives(device, region, "PotentialEdgeFlux", flux, "Potential")

    # Electron current: J_n = q * mu_n * n * grad(Fn), with Fn in volts.
    # This quasi-Fermi form is compatible with the chosen Fermi-Dirac density
    # relation when mobility is interpreted as conductivity mobility.
    avg_n = "0.5*(Electrons@n0+Electrons@n1)"
    grad_fn = "(HEMT_Fn@n1-HEMT_Fn@n0)*EdgeInverseLength"
    jn = f"ElectronCharge*HEMT_mu_n*{avg_n}*{grad_fn}"
    _edge(device, region, "ElectronCurrent", jn)

    # Explicit Jacobian terms: the density derivative is dFermidx, not n/Vt.
    _edge(
        device, region, "ElectronCurrent:HEMT_Fn@n0",
        "ElectronCharge*HEMT_mu_n*(0.5*HEMT_dndF@n0*"
        "(HEMT_Fn@n1-HEMT_Fn@n0)*EdgeInverseLength-"
        "0.5*(Electrons@n0+Electrons@n1)*EdgeInverseLength)",
    )
    _edge(
        device, region, "ElectronCurrent:HEMT_Fn@n1",
        "ElectronCharge*HEMT_mu_n*(0.5*HEMT_dndF@n1*"
        "(HEMT_Fn@n1-HEMT_Fn@n0)*EdgeInverseLength+"
        "0.5*(Electrons@n0+Electrons@n1)*EdgeInverseLength)",
    )
    _edge(
        device, region, "ElectronCurrent:Potential@n0",
        "ElectronCharge*HEMT_mu_n*0.5*HEMT_dndF@n0*"
        "(HEMT_Fn@n1-HEMT_Fn@n0)*EdgeInverseLength",
    )
    _edge(
        device, region, "ElectronCurrent:Potential@n1",
        "ElectronCharge*HEMT_mu_n*0.5*HEMT_dndF@n1*"
        "(HEMT_Fn@n1-HEMT_Fn@n0)*EdgeInverseLength",
    )

    _node(device, region, "ElectronGeneration", "0")
    devsim.equation(
        device=device, region=region, name="PotentialEquation",
        variable_name="Potential", node_model="PotentialNodeCharge",
        edge_model="PotentialEdgeFlux", variable_update="log_damp",
    )
    devsim.equation(
        device=device, region=region, name="ElectronContinuityEquation",
        variable_name="HEMT_Fn", node_model="ElectronGeneration",
        edge_model="ElectronCurrent", variable_update="default",
    )


def _inclusive_range(start, stop, step):
    start, stop, step = float(start), float(stop), abs(float(step))
    if step <= 0 or stop < start:
        raise ValueError("Invalid gate sweep range/step")
    count = int(math.floor((stop - start) / step + 1e-10))
    values = [round(start + i * step, 10) for i in range(count + 1)]
    if not values or abs(values[-1] - stop) > 1e-8:
        values.append(stop)
    return values


def _contact_current(device, contact):
    return float(devsim.get_contact_current(
        device=device, contact=contact, equation="ElectronContinuityEquation"
    ))


def _current_balance(source_current, drain_current):
    a, b = abs(float(source_current)), abs(float(drain_current))
    if max(a, b) < 1e-18:
        return 0.0
    return abs(a - b) / max(a, b, 1e-30)


def _save_csv(path, rows):
    if not rows:
        return
    with Path(path).open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _snapshot(device):
    rows = []
    for region in (ALGAN, GAN):
        fields = ("x", "y", "Potential", "HEMT_Fn", "Electrons", "PolarizationVolume")
        values = {
            key: list(map(float, devsim.get_node_model_values(
                device=device, region=region, name=key
            ))) for key in fields
        }
        lengths = {len(v) for v in values.values()}
        if len(lengths) != 1:
            raise RuntimeError(f"Mismatched node-model lengths in {region}: {lengths}")
        for x, y, phi, fn, n, rho_pol in zip(*(values[k] for k in fields)):
            if not all(math.isfinite(v) for v in (x, y, phi, fn, n, rho_pol)):
                raise RuntimeError(f"Non-finite output value in {region}")
            if n < 0:
                raise RuntimeError(f"Negative electron density in {region}")
            rows.append({
                "region": region, "x_um": x * 1e4, "y_nm": y * 1e7,
                "potential_V": phi, "electron_quasi_fermi_V": fn,
                "electrons_cm3": n, "polarization_C_cm3": rho_pol,
            })
    return rows


def _extract_metrics(rows):
    rows = sorted(rows, key=lambda r: r["Vg_V"])
    if len(rows) < 2:
        return {"threshold_constant_current_1mA_per_mm_V": None,
                "peak_gm_mS_per_mm": None}
    vg = [r["Vg_V"] for r in rows]
    ids = [r["Id_mA_per_mm"] for r in rows]
    gm = []
    for i in range(len(rows)):
        if i == 0:
            slope = (ids[1] - ids[0]) / (vg[1] - vg[0])
        elif i == len(rows) - 1:
            slope = (ids[-1] - ids[-2]) / (vg[-1] - vg[-2])
        else:
            slope = (ids[i + 1] - ids[i - 1]) / (vg[i + 1] - vg[i - 1])
        gm.append(slope)
    vth = None
    target = 1.0  # constant-current criterion, 1 mA/mm
    for i in range(len(rows) - 1):
        y0, y1 = ids[i] - target, ids[i + 1] - target
        if y0 == 0:
            vth = vg[i]
            break
        if y0 * y1 < 0 or y1 == 0:
            if ids[i + 1] != ids[i]:
                vth = vg[i] + (target - ids[i]) * (vg[i + 1] - vg[i]) / (ids[i + 1] - ids[i])
            else:
                vth = vg[i]
            break
    return {
        "threshold_constant_current_1mA_per_mm_V": vth,
        "peak_gm_mS_per_mm": max(gm) if gm else None,
    }


def _plot_transfer(path, rows):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:
        print(f"[HEMT-TRANSPORT] matplotlib unavailable; CSV is saved ({exc})", flush=True)
        return
    data = sorted(rows, key=lambda r: r["Vg_V"])
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    ax.plot([r["Vg_V"] for r in data], [r["Id_mA_per_mm"] for r in data], "o-", ms=3)
    ax.set_xlabel("Gate voltage Vg (V)")
    ax.set_ylabel("Drain current |Id| (mA/mm)")
    ax.set_title("AlGaN/GaN HEMT: exploratory DC transfer curve")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(Path(path) / "HEMT_TRANSPORT_IdVg.png", dpi=180)
    fig.savefig(Path(path) / "HEMT_TRANSPORT_IdVg.pdf")
    plt.close(fig)


def run_hemt_transport(detector, kwargs, paras):
    """Entry point selected only by hemt_physics.transport_model."""
    raw = detector.device_dict
    hp = raw.get("hemt_physics", {})
    cfg = hp.get("transport_v1", {})
    device = detector.device

    if int(detector.dimension) != 2:
        raise ValueError("HEMT_TRANSPORT_V1 requires a 2D device")
    if any(bool(kwargs.get(k)) for k in ("cv", "wf", "noise")):
        raise NotImplementedError("HEMT_TRANSPORT_V1 supports DC transfer sweeps only")
    if not hp.get("ga_face", True) or not hp.get("pseudomorphic_barrier", True):
        raise NotImplementedError("HEMT_TRANSPORT_V1 currently assumes a Ga-face pseudomorphic barrier")
    if abs(float(detector.temperature) - 300.0) > 1e-8:
        raise ValueError("Initial HEMT_TRANSPORT_V1 calibration is restricted to 300 K")
    if "2D_mesh" not in raw.get("mesh", {}):
        raise ValueError("HEMT_TRANSPORT_V1 requires mesh.2D_mesh")
    if hp.get("transport_model") != "drift_diffusion_v1":
        raise ValueError("Select hemt_physics.transport_model='drift_diffusion_v1'")
    if kwargs.get("bias") not in (None, 0, 0.0):
        raise ValueError("Use bias=0 for the RASER launcher; drain bias is set in hemt_physics.transport_v1")

    folder = kwargs.get("_field_directory")
    if not folder:
        raise RuntimeError("RASER did not provide _field_directory")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    mesh_cfg = raw["mesh"]["2D_mesh"]
    regions_cfg = {r["region"]: r for r in mesh_cfg.get("region", [])}
    if ALGAN not in regions_cfg or GAN not in regions_cfg:
        raise ValueError("Transport config must contain AlGaN_barrier and GaN_buffer")
    contacts = {c["name"]: c for c in mesh_cfg.get("contact", [])}
    for name in ("source", "gate", "drain"):
        if name not in contacts:
            raise ValueError(f"Transport config is missing contact {name}")
    if contacts["source"].get("region") != GAN or contacts["drain"].get("region") != GAN:
        raise ValueError("For this simplified branch, source and drain must contact GaN_buffer")
    if contacts["gate"].get("region") != ALGAN:
        raise ValueError("Gate must contact AlGaN_barrier")

    mesh = DevsimMesh(detector, devsim_solve_paras=paras, output_directory=str(folder))
    mesh.mesh_define()
    actual_regions = set(devsim.get_region_list(device=device))
    if not {ALGAN, GAN}.issubset(actual_regions):
        raise ValueError(f"Missing semiconductor regions; got {sorted(actual_regions)}")
    actual_contacts = set(devsim.get_contact_list(device=device))
    if not {"source", "gate", "drain"}.issubset(actual_contacts):
        raise ValueError(f"Missing required contacts after mesh generation: {sorted(actual_contacts)}")
    actual_interfaces = set(devsim.get_interface_list(device=device))
    if IFACE not in actual_interfaces:
        raise ValueError(f"Missing heterointerface {IFACE}; found {sorted(actual_interfaces)}")

    create_parameter(detector, device, detector.region)
    T = float(detector.temperature)
    vt = KB * T / Q
    nc_gan = float(devsim.get_parameter(device=device, region=GAN, name="N_c"))
    doping = raw.get("doping", {})
    local = doping.get("by_region", {}).get(GAN, {})
    nd = float(local.get("Donors", doping.get("Donors", 0.0)))
    na = float(local.get("Acceptors", doping.get("Acceptors", 0.0)))
    if nd <= na or nc_gan <= 0:
        raise ValueError("Initial model requires n-type GaN with Donors > Acceptors and Nc > 0")
    # Non-degenerate bulk estimate is a stable initial guess; the solved density
    # itself uses DEVSIM's Fermi-Dirac approximation.
    ef = vt * math.log((nd - na) / nc_gan)
    sigma_cm2 = float(devsim.get_parameter(device=device, region=GAN, name="SigmaPol_C_cm2"))
    delta_ec = float(devsim.get_parameter(device=device, region=ALGAN, name="EcOffset_eV"))
    phi_bn = float(devsim.get_parameter(device=device, region=ALGAN, name="SchottkyPhiBn_eV"))
    interface_y_cm = float(regions_cfg[ALGAN]["yh"])

    mu_gan = float(cfg.get("mu_n_gan_cm2_Vs", 1000.0))
    mu_algan = float(cfg.get("mu_n_algan_cm2_Vs", 300.0))
    if min(mu_gan, mu_algan) <= 0:
        raise ValueError("Electron mobilities must be positive")
    _create_region_models(device, ALGAN, "AlGaN", ef, mu_algan, raw, interface_y_cm)
    _create_region_models(device, GAN, "GaN", ef, mu_gan, raw, interface_y_cm)

    # The interface equation combines the regional finite-volume residuals and
    # enforces continuity of the potential across the heterointerface.
    continuity = model_create.CreateContinuousInterfaceModel(device, IFACE, "Potential")
    devsim.interface_equation(
        device=device, interface=IFACE, name="PotentialEquation",
        interface_model=continuity, type="continuous",
    )
    fn_continuity = model_create.CreateContinuousInterfaceModel(device, IFACE, "HEMT_Fn")
    devsim.interface_equation(
        device=device, interface=IFACE, name="ElectronContinuityEquation",
        interface_model=fn_continuity, type="continuous",
    )

    # Contact bias parameters. Source/drain electrostatic potentials are Vt; the
    # electron quasi-Fermi potential shifts oppositely so contact density stays at
    # its equilibrium value when an ideal terminal voltage is applied.
    for contact in ("source", "gate", "drain"):
        _set_device_parameter(device, f"HT1_{contact}_PotentialBias", 0.0)
    for contact in ("source", "drain"):
        _set_device_parameter(device, f"HT1_{contact}_FnBias", ef)
    for contact in ("source", "gate", "drain"):
        _create_potential_contact(device, contact, f"HT1_{contact}_PotentialBias")
    for contact in ("source", "drain"):
        _create_fn_contact(device, contact, f"HT1_{contact}_FnBias")

    gate_base = delta_ec - ef - phi_bn
    _set_device_parameter(device, "HT1_gate_PotentialBias", 0.0)
    for region in (ALGAN, GAN):
        # Explicitly set initial polarization to zero before the first solve.
        if region == GAN:
            devsim.set_parameter(device=device, region=region, name="HEMT_PolScale", value=0.0)

    solve_cfg = {
        "solver": {
            "absolute_error": float(cfg.get("absolute_error", 1e-12)),
            "relative_error": float(cfg.get("relative_error", 1e-7)),
            "maximum_iterations": int(cfg.get("maximum_iterations", 100)),
        }
    }
    print("[HEMT-TRANSPORT] branch=electron-only 2D DD; stats=DEVSIM Fermi approximation", flush=True)
    print(f"[HEMT-TRANSPORT] x_Al={float(hp['al_mole_fraction']):.4f}, T={T:.1f} K, "
          f"sigma_pol={sigma_cm2:.6e} C/cm^2, Ef_initial={ef:.6f} V", flush=True)
    print(f"[HEMT-TRANSPORT] mobility: GaN={mu_gan:g}, AlGaN={mu_algan:g} cm^2/(V s); "
          f"gate baseline={gate_base:.6f} V", flush=True)

    # Step 1: stable zero-field/no-polarization seed.
    _set_device_parameter(device, "HT1_source_PotentialBias", 0.0)
    _set_device_parameter(device, "HT1_drain_PotentialBias", 0.0)
    _set_device_parameter(device, "HT1_source_FnBias", ef)
    _set_device_parameter(device, "HT1_drain_FnBias", ef)
    _set_device_parameter(device, "HT1_gate_PotentialBias", 0.0)
    _solve(device, solve_cfg, "initial equilibrium (gate=0, polarization=off)")

    gate_ramp_steps = max(1, int(cfg.get("gate_ramp_steps", 20)))
    for i in range(1, gate_ramp_steps + 1):
        val = gate_base * i / gate_ramp_steps
        _set_device_parameter(device, "HT1_gate_PotentialBias", val)
        _solve(device, solve_cfg, f"gate baseline ramp {i}/{gate_ramp_steps}")

    pol_steps = max(1, int(cfg.get("polarization_ramp_steps", 20)))
    for i in range(1, pol_steps + 1):
        devsim.set_parameter(device=device, region=GAN, name="HEMT_PolScale", value=i / pol_steps)
        _solve(device, solve_cfg, f"polarization ramp {i}/{pol_steps}")

    vds_target = float(cfg.get("drain_bias_V", 0.05))
    if vds_target < 0 or vds_target > 0.2:
        raise ValueError("Initial transport branch restricts drain_bias_V to 0..0.2 V")
    vds_steps = max(1, int(cfg.get("drain_ramp_steps", 5)))
    for i in range(1, vds_steps + 1):
        vds = vds_target * i / vds_steps
        _set_device_parameter(device, "HT1_source_PotentialBias", 0.0)
        _set_device_parameter(device, "HT1_drain_PotentialBias", vds)
        _set_device_parameter(device, "HT1_source_FnBias", ef)
        _set_device_parameter(device, "HT1_drain_FnBias", ef - vds)
        _solve(device, solve_cfg, f"drain bias ramp {i}/{vds_steps}, Vds={vds:.6g} V")

    vg_start = float(cfg.get("gate_start_V", -3.0))
    vg_stop = float(cfg.get("gate_stop_V", 1.0))
    vg_step = float(cfg.get("gate_step_V", 0.25))
    vg_grid = _inclusive_range(vg_start, vg_stop, vg_step)
    if vg_start > 0 or vg_stop < 0 or not any(abs(v) < 1e-8 for v in vg_grid):
        raise ValueError("Gate sweep must include Vg=0 and span from a non-positive to a non-negative value")
    # Ramp from Vg=0 to the negative sweep start first.
    # Then sweep monotonically from Vg_start to Vg_stop.
    # This avoids jumping directly from -3 V to +0.25 V.
    pre_steps = max(1, int(math.ceil(abs(vg_start) / vg_step)))
    for j in range(1, pre_steps + 1):
        vg_pre = vg_start * j / pre_steps
        _set_device_parameter(
            device, "HT1_gate_PotentialBias", gate_base + vg_pre
        )
        _solve(
            device, solve_cfg,
            f"gate pre-ramp {j}/{pre_steps}, Vg={vg_pre:.6g} V"
        )

    sequence = sorted(vg_grid)

    area_factor = float(raw.get("area_factor", 1.0))
    transfer_rows = []
    max_balance = 0.0
    for idx, vg in enumerate(sequence, 1):
        _set_device_parameter(device, "HT1_gate_PotentialBias", gate_base + vg)
        _solve(device, solve_cfg, f"Id-Vg point {idx}/{len(sequence)}, Vg={vg:.6g} V")
        isrc = _contact_current(device, "source")
        idrn = _contact_current(device, "drain")
        balance = _current_balance(isrc, idrn)
        max_balance = max(max_balance, balance)
        row = {
            "Vg_V": float(vg),
            "Vds_V": float(vds_target),
            "Is_signed_A_per_cm": float(isrc),
            "Id_signed_A_per_cm": float(idrn),
            "Id_mA_per_mm": abs(float(idrn)) * 100.0 * area_factor,
            "source_drain_current_mismatch_relative": float(balance),
        }
        transfer_rows.append(row)
        print(f"[HEMT-TRANSPORT] Vg={vg:+.3f} V, Vds={vds_target:.3f} V, "
              f"|Id|={row['Id_mA_per_mm']:.6g} mA/mm, balance={balance:.3e}", flush=True)

    transfer_sorted = sorted(transfer_rows, key=lambda r: r["Vg_V"])
    _save_csv(folder / "HEMT_TRANSPORT_IdVg.csv", transfer_sorted)
    profiles = _snapshot(device)
    _save_csv(folder / "HEMT_TRANSPORT_final_profile.csv", profiles)
    devsim.write_devices(file=str(folder / "HEMT_TRANSPORT_final.devsim"), type="devsim")
    _plot_transfer(folder, transfer_sorted)
    metrics = _extract_metrics(transfer_sorted)

    limitations = [
        "Exploratory 2D electron-only drift-diffusion; no hole continuity or SRH recombination.",
        "No gate leakage, self-heating, impact ionization, or radiation/trap dynamics.",
        "No Schrödinger-Poisson or density-gradient quantum confinement; 2DEG is not quantum-corrected in 2D.",
        "Polarization sheet is represented by a normalized half-Gaussian in GaN; width is a numerical regularization.",
        "Source/drain use simplified lateral GaN side contacts; this is not a calibrated fabricated-contact geometry.",
        "Electron mobility is constant and user-configured; Id-Vg magnitudes require calibration before quantitative claims.",
    ]
    max_id_mA_mm = max((r["Id_mA_per_mm"] for r in transfer_sorted), default=0.0)
    run_status = (
        "COMPLETED_EXPLORATORY_TRANSPORT_SWEEP"
        if max_balance <= 1e-3 and max_id_mA_mm >= 1e-12
        else "COMPLETED_WITH_NUMERICAL_WARNINGS"
    )
    summary = {
        "status": run_status,
        "device": device,
        "temperature_K": T,
        "al_mole_fraction": float(hp["al_mole_fraction"]),
        "polarization_sigma_C_cm2": sigma_cm2,
        "fermi_initial_V": ef,
        "gate_baseline_V": gate_base,
        "drain_bias_V": vds_target,
        "gate_sweep_V": [vg_start, vg_stop, vg_step],
        "mobility_GaN_cm2_Vs": mu_gan,
        "mobility_AlGaN_cm2_Vs": mu_algan,
        "number_of_gate_points": len(transfer_sorted),
        "maximum_source_drain_current_mismatch_relative": max_balance,
        **metrics,
        "limitations": limitations,
        "interpretation": "Successful numerical output is a transport-framework smoke test, not by itself a literature or experimental validation.",
    }
    with (folder / "HEMT_TRANSPORT_summary.json").open("w", encoding="utf-8") as fp:
        json.dump(summary, fp, indent=2, ensure_ascii=False, allow_nan=False)
    print("[HEMT-TRANSPORT] outputs saved to", folder, flush=True)
    print("[HEMT-TRANSPORT] summary:", json.dumps(summary, ensure_ascii=False), flush=True)
    if max_balance > 1e-3:
        print("[HEMT-TRANSPORT][WARNING] source/drain current mismatch exceeds 0.1%; inspect interface and boundary fluxes before using the curve.", flush=True)
    if max_id_mA_mm < 1e-12:
        print("[HEMT-TRANSPORT][WARNING] All drain currents are effectively zero; do not interpret this as a physical transfer curve.", flush=True)
    return summary
