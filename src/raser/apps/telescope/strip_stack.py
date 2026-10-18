"""Two stereo strip layers sharing a global track and independent sensor fields."""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from dataclasses import replace
from pathlib import Path

from raser.components import load_component, load_source
from raser.core.device import resolve_device
from raser.core.device.stack import StraightTrack, combine_projected_slopes, stereo_pair
from raser.core.field import FieldConfiguration
from raser.core.field.assets import resolve_field_pickle
from raser.supports import runs
from raser.supports.paths import project_root_context, work_root


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, values: dict) -> None:
    path.write_text(
        json.dumps(values, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def build_plan(kwargs: dict) -> tuple[dict, tuple, StraightTrack]:
    setup = kwargs.get("setup") or "strip_ayyouby_stack"
    supplied = Path(setup).expanduser()
    path = supplied if supplied.suffix else Path(__file__).with_name(setup + ".json")
    config = json.loads(path.read_text(encoding="utf-8"))
    for option, key in (
        ("stereo_angle_deg", "stereo_angle_deg"),
        ("gap_um", "silicon_gap_um"),
        ("slope_x", "slope_x"),
        ("slope_y", "slope_y"),
    ):
        if kwargs.get(option) is not None:
            config[key] = float(kwargs[option])
    if re.fullmatch(r"[A-Za-z0-9_-]+", config["name"]) is None:
        raise ValueError("Stack name must be a safe project directory name")
    device = resolve_device(config["device"])
    if (
        "strip" not in device.definition.model.lower()
        or device.definition.readout.y_count != 1
    ):
        raise ValueError("Stereo stack requires a single-row strip device")
    if device.name != "strip_ayyouby" or device.definition.readout.contacts != (
        "top1",
        "top2",
        "top3",
    ):
        raise ValueError(
            "This stack workflow requires the three-channel strip_ayyouby sensor"
        )
    if config["name"] == device.name:
        raise ValueError("Stack output project must differ from its sensor project")
    field = FieldConfiguration.resolve(device)
    directory = field.directory(device)
    field_json = directory / "config.json"
    if json.loads(field_json.read_text()) != field.as_dict():
        raise ValueError("Stored field configuration differs from the sensor state")
    contacts = device.definition.readout.contacts
    assets = [device.definition.source_path, field_json]
    for prefix in ("Potential", "TrappingRate_n", "TrappingRate_p"):
        assets.append(
            resolve_field_pickle(directory, prefix, device.state.bias_voltage)
        )
    assets.append(resolve_field_pickle(directory, "NetDoping", 0))
    assets.extend(
        directory / "weightingfield" / name / "Potential_1V.pkl" for name in contacts
    )
    source_path, source = load_source(config["source"])
    if source.get("kind") != "toy_mip":
        raise ValueError("Stereo stack validation requires a toy_mip source")
    afe_path, afe = load_component("afe", config["amplifier"])
    assets.extend((source_path, afe_path))
    layers = stereo_pair(
        device.definition.dimensions_um,
        stereo_angle_deg=config["stereo_angle_deg"],
        gap_um=config["silicon_gap_um"],
    )
    reference = tuple(float(x) for x in config["reference_um"])
    track = StraightTrack(
        reference, config["slope_x"], config["slope_y"], beta=config["beta"]
    )
    crossings = [layer.crossing(track) for layer in layers]
    if any(crossing is None for crossing in crossings):
        raise ValueError(
            "Requested global track misses at least one active silicon slab"
        )
    seed = int(kwargs.get("seed", 7))
    if seed < 0:
        raise ValueError("Seed must be non-negative")
    if int(config["packets_per_layer"]) <= 0:
        raise ValueError("Packets per layer must be positive")
    projections = [layer.projected_slope(track) for layer in layers]
    plan = {
        "workflow": "strip_stack",
        "configuration": config,
        "setup_source": str(path.resolve()),
        "device": device.as_dict(),
        "field": {
            "configuration": field.as_dict(),
            "hash": field.digest,
            "directory": str(directory),
        },
        "source": {"path": str(source_path), "values": source},
        "afe": {"path": str(afe_path), "values": afe},
        "layers": [
            {
                **layer.as_dict(),
                "crossing": crossing.as_dict(),
                "channels": [f"{layer.name}/{contact}" for contact in contacts],
            }
            for layer, crossing in zip(layers, crossings)
        ],
        "geometry": {
            "stereo_angle_deg": config["stereo_angle_deg"],
            "silicon_gap_um": config["silicon_gap_um"],
            "center_separation_um": device.definition.dimensions_um[2]
            + config["silicon_gap_um"],
        },
        "truth": {
            "reference_um": reference,
            "slope_x": track.slope_x,
            "slope_y": track.slope_y,
            "projected_slopes": projections,
            "angles": combine_projected_slopes(
                projections, [layer.rotation_z_deg for layer in layers]
            ),
        },
        "work": {"events": 1, "seed": seed, "channels": 2 * len(contacts)},
        "input_sha256": {str(item.resolve()): _hash(item) for item in assets},
        "source_code_sha256": {
            str(item.resolve()): _hash(item)
            for item in (
                Path(__file__),
                Path(__file__).with_name("strip_stack_plot.py"),
                Path(__file__).resolve().parents[2] / "core/device/stack.py",
                Path(__file__).resolve().parents[2] / "core/current/cal_current.py",
                path,
            )
        },
        "scope": {
            "field_model": config["field_scope"],
            "same_global_straight_track": True,
            "independent_layer_ionization_and_frontend_rng": True,
            "truth_separate_from_waveforms": True,
            "angular_calibration": "Required before projected slopes can be measured from waveforms",
            "resolution_statistics": "Pending",
        },
    }
    return plan, layers, track


def _samples(histogram):
    import numpy as np

    count = histogram.GetNbinsX()
    times = np.array([histogram.GetBinCenter(i) for i in range(1, count + 1)])
    values = np.array([histogram.GetBinContent(i) for i in range(1, count + 1)])
    widths = np.array([histogram.GetBinWidth(i) for i in range(1, count + 1)])
    if count == 0 or not np.isfinite(times).all() or not np.isfinite(values).all():
        raise ValueError("Waveform must have finite samples and timestamps")
    if float(np.max(np.abs(values))) == 0:
        raise ValueError("Waveform is identically zero")
    return times, values, widths


def simulate(plan: dict, layers: tuple, track: StraightTrack, root: Path) -> dict:
    # Native ROOT and array dependencies are only needed for signal execution.
    import numpy as np
    import ROOT

    from raser.core.current.cal_current import CalCurrentToyMIP
    from raser.core.device.build_device import Detector
    from raser.core.field.devsim_field import DevsimField
    from raser.core.frontend.legacy_readout import Amplifier
    from raser.core.interaction.toy_mip import ToyMIPLineSource

    ROOT.gROOT.SetBatch(True)
    ROOT.TH1.AddDirectory(False)
    detector = Detector(plan["device"]["definition"])
    field = DevsimField(
        detector.device,
        detector.dimension,
        detector.voltage,
        detector.read_out_contact,
        detector.mesher,
        is_plugin=detector.is_plugin(),
        bounds=detector.bound,
        field_set=plan["field"]["hash"],
        field_directory=plan["field"]["directory"],
    )
    detector.gain_rate_cal(field)
    for x in (9.0, 29.0, 49.0):
        for z in (0.0, 25.0, 50.0):
            if not np.isfinite(field._get_e_field(x, detector.l_y / 2, z)).all():
                raise ValueError("Nonfinite local electric field")
    for electrode, x in enumerate((9.0, 29.0, 49.0)):
        for index in range(3):
            actual = field._get_w_p(x, detector.l_y / 2, 0.0, index)
            if not math.isclose(actual, float(index == electrode), abs_tol=1e-6):
                raise ValueError("Weighting field electrode boundary mismatch")
            back = field._get_w_p(x, detector.l_y / 2, detector.l_z, index)
            if not math.isclose(back, 0.0, abs_tol=1e-6):
                raise ValueError("Weighting field backplane boundary mismatch")
    arrays, channels, truth_layers = {}, [], []
    source_options = dict(plan["source"]["values"])
    source_options = {
        key: value
        for key, value in source_options.items()
        if key not in {"name", "kind", "description"}
    }
    for layer_index, layer in enumerate(layers):
        crossing = layer.crossing(track)
        if crossing is None:
            raise ValueError("Validation track misses a layer")
        rng_seed = (plan["work"]["seed"] + (layer_index + 1) * 1_000_003) % (
            2**32 - 1
        ) + 1
        source = ToyMIPLineSource.through_sensor(
            detector,
            packets=int(plan["configuration"]["packets_per_layer"]),
            start=crossing.entry_local_um,
            end=crossing.exit_local_um,
            rng=ROOT.TRandom3(rng_seed),
            **source_options,
        )
        positions = []
        for index, point in enumerate(source.track_position):
            fraction = (index + 0.5) / len(source.track_position)
            time_s = crossing.entry_time_s + fraction * (
                crossing.exit_time_s - crossing.entry_time_s
            )
            positions.append([*point[:3], time_s])
        source = replace(source, track_position=positions)
        global_positions = [layer.to_global(point[:3]) for point in positions]
        if any(
            np.linalg.norm(np.array(point) - track.at_z(point[2])) > 1e-8
            for point in global_positions
        ):
            raise ValueError(
                "Local ionization packets do not belong to the shared global track"
            )
        layer_root = root / layer.name
        layer_root.mkdir()
        transport_seed = (rng_seed + 200_003) % (2**32 - 1) + 1
        transport_random_state = random.getstate()
        try:
            random.seed(transport_seed)
            current = CalCurrentToyMIP(detector, field, source, keep_drift_paths=False)
        finally:
            random.setstate(transport_random_state)
        frontend_seed = (rng_seed + 100_003) % (2**32 - 1) + 1
        frontend = Amplifier(
            current.sum_cu,
            plan["configuration"]["amplifier"],
            seed=frontend_seed,
            CDet=detector.capacitance,
        )
        if len(current.sum_cu) != 3 or len(frontend.amplified_currents) != 3:
            raise ValueError(
                "Each layer must produce exactly three current and frontend waveforms"
            )
        for index, (raw, amplified) in enumerate(
            zip(current.sum_cu, frontend.amplified_currents), 1
        ):
            time_s, values, widths = _samples(raw)
            frontend_time, front, _ = _samples(amplified)
            label = f"{layer.name}_{index}"
            arrays[f"time_s_{label}"] = time_s
            arrays[f"current_A_{label}"] = values
            arrays[f"frontend_time_s_{label}"] = frontend_time
            arrays[f"frontend_mV_{label}"] = front
            charge = float(np.sum(values * widths))
            channels.append(
                {
                    "event_id": 0,
                    "layer": layer.name,
                    "contact": f"top{index}",
                    "peak_current_A": float(np.max(np.abs(values))),
                    "signed_charge_C": charge,
                    "signed_charge_e": charge / 1.602176634e-19,
                    "frontend_peak_mV": float(np.max(np.abs(front))),
                    "frontend_unit": "RASER AFE mV convention",
                }
            )
        current.draw_currents(str(layer_root))
        frontend.draw_waveform(current.sum_cu, str(layer_root))
        truth_layers.append(
            {
                "event_id": 0,
                "layer": layer.name,
                "rng_seed": rng_seed,
                "frontend_seed": frontend_seed,
                "transport_seed": transport_seed,
                "crossing": crossing.as_dict(),
                "global_packets_um": global_positions,
                "local_packets_um_and_time_s": positions,
                "ionized_pairs": source.ionized_pairs,
                "generated_pairs": sum(source.ionized_pairs),
                "deposited_energy_MeV": sum(source.energy_deposition_mev),
            }
        )
        del current, frontend
    for layer in layers:
        charge = sum(
            abs(channel["signed_charge_e"])
            for channel in channels
            if channel["layer"] == layer.name
        )
        if not math.isfinite(charge) or charge <= 0:
            raise ValueError("Layer has no finite integrated induced charge")
    np.savez_compressed(root / "waveforms.npz", **arrays)
    _write_json(
        root / "truth.json",
        {"event_id": 0, "track": plan["truth"], "layers": truth_layers},
    )
    for path, expected in plan["input_sha256"].items():
        if _hash(Path(path)) != expected:
            raise ValueError("Input changed during stack validation: " + path)
    return {
        "stage": "complete",
        "events": 1,
        "channels": channels,
        "same_track_packet_coordinates_verified": True,
        "input_hashes_unchanged": True,
        "local_electric_field_samples_finite": True,
        "weighting_contact_boundaries_verified": True,
        "scope": plan["scope"],
    }


def main(kwargs: dict):
    plan, layers, track = build_plan(kwargs)
    if kwargs.get("dry_run"):
        print(json.dumps(plan, indent=2, allow_nan=False))
        return plan
    from raser.apps.telescope.strip_stack_plot import draw_geometry, draw_waveforms

    run_id = runs.ensure_run_id(kwargs)
    project = work_root() / plan["configuration"]["name"]
    with project_root_context(project):
        root, _ = runs.write_run_record(plan, workflow="signal", run_id=run_id)
    _write_json(root / "stack.json", plan)
    draw_geometry(plan, root / "geometry.png")
    if kwargs.get("geometry_only"):
        _write_json(
            root / "validation.json",
            {"stage": "geometry_complete", "scope": plan["scope"]},
        )
    else:
        try:
            result = simulate(plan, layers, track, root)
            draw_waveforms(plan, root)
            _write_json(root / "validation.json", result)
        except Exception as exc:
            _write_json(
                root / "validation.json", {"stage": "failed", "error": repr(exc)}
            )
            raise
    print(root)
    return plan
