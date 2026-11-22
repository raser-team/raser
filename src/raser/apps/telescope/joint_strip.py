"""Explicit two/three-readout joint entrance-position and angle workflow."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

from raser.core.reconstruction.joint_features import JointFeatureConfig, joint_features
from raser.core.reconstruction.joint_strip import JOINT_LEVELS, JointStripResponse

from . import strip_dataset
from .strip_dataset import CONTRACT, compatible, independent, labels, load_dataset


def algorithm_hashes():
    root = Path(__file__).resolve().parents[2]
    files = [
        "core/reconstruction/joint_features.py",
        "core/reconstruction/joint_strip.py",
        "core/reconstruction/features.py",
        "core/reconstruction/response.py",
        "apps/telescope/joint_strip.py",
        "apps/telescope/strip_dataset.py",
    ]
    return {name: strip_dataset._hash(root / name) for name in files}


def features(manifest, events, config):
    return [
        joint_features(
            e["times_s"],
            e["signals"],
            manifest["positions_um"],
            config=config,
            waveform_kind=manifest["waveform_kind"],
        )
        for e in events
    ]


def calibrate(
    manifest,
    events,
    labels_path,
    interval_manifest,
    interval_events,
    interval_labels,
    config,
):
    compatible(manifest, interval_manifest)
    independent([events, interval_events])
    fs = features(manifest, events, config)
    truth = labels(labels_path, [e["event_id"] for e in events])
    metadata = {k: manifest[k] for k in CONTRACT}
    metadata.update(
        feature_config=config.as_dict(),
        algorithm_sha256=algorithm_hashes(),
        training_event_ids=[e["event_id"] for e in events],
        training_waveform_hashes=[e["waveform_hash"] for e in events],
        training_particle_ids=[e.get("particle_id", e["event_id"]) for e in events],
        interval_event_ids=[e["event_id"] for e in interval_events],
        interval_waveform_hashes=[e["waveform_hash"] for e in interval_events],
        interval_particle_ids=[
            e.get("particle_id", e["event_id"]) for e in interval_events
        ],
        training_manifest_sha256=manifest["manifest_sha256"],
        interval_manifest_sha256=interval_manifest["manifest_sha256"],
        training_labels_sha256=strip_dataset._hash(labels_path),
        interval_labels_sha256=strip_dataset._hash(interval_labels),
        position_scope="transverse entrance x relative to entrance_reference_um at entrance_z_um",
        integral_units="fC"
        if manifest["waveform_kind"] == "current_A"
        else "mV ns (frontend charge proxy)",
    )
    model = JointStripResponse.fit(
        [f.values for f in fs],
        [truth[e["event_id"]] for e in events],
        floors=fs[0].floors,
        metadata=metadata,
        usable=[f.usable for f in fs],
    )
    calibration = features(interval_manifest, interval_events, config)
    target = labels(interval_labels, [e["event_id"] for e in interval_events])
    model.calibrate(
        [f.values for f in calibration],
        [target[e["event_id"]] for e in interval_events],
        usable=[f.usable for f in calibration],
        event_ids=[e["event_id"] for e in interval_events],
    )
    return model


def predict(manifest, events, model):
    compatible(manifest, model.metadata)
    if model.metadata["algorithm_sha256"] != algorithm_hashes():
        raise ValueError("Joint algorithm differs from calibrated source")
    prior = [
        {"event_id": i, "waveform_hash": h, "particle_id": p}
        for role in ["training", "interval"]
        for i, h, p in zip(
            model.metadata[role + "_event_ids"],
            model.metadata[role + "_waveform_hashes"],
            model.metadata.get(
                role + "_particle_ids", model.metadata[role + "_event_ids"]
            ),
        )
    ]
    independent([prior, events])
    fs = features(
        manifest, events, JointFeatureConfig(**model.metadata["feature_config"])
    )
    rows = []
    for event, f in zip(events, fs):
        result = model.predict(f.values, usable=f.usable, reason=f.reason)
        rows.append(
            dict(
                event_id=event["event_id"],
                **result,
                waveform_hash=event["waveform_hash"],
                feature_diagnostics=f.diagnostics,
            )
        )
    return rows, fs


def _metrics(rows, truth, *, accepted_only=False):
    chosen = [
        r
        for r in rows
        if r.get("best_fit") is not None and (r["accepted"] or not accepted_only)
    ]
    if not chosen:
        return {
            "events": 0,
            "angle": None,
            "entrance": None,
            "wrong_sign": None,
            "angle_tail10": None,
        }
    predicted = np.array(
        [[r["best_fit"]["slope"], r["best_fit"]["entrance_um"]] for r in chosen]
    )
    actual = np.array([truth[r["event_id"]] for r in chosen])
    error = predicted - actual
    error[:, 0] = np.degrees(np.arctan(predicted[:, 0]) - np.arctan(actual[:, 0]))

    def summary(v):
        return {
            "bias": float(v.mean()),
            "rms": float(np.sqrt(np.mean(v * v))),
            "median_absolute": float(np.median(abs(v))),
            "absolute_p95": float(np.quantile(abs(v), 0.95)),
        }

    directional = abs(actual[:, 0]) > 1e-10
    return {
        "events": len(chosen),
        "angle": summary(error[:, 0]),
        "entrance": summary(error[:, 1]),
        "wrong_sign": int(
            np.sum(directional & (np.sign(predicted[:, 0]) != np.sign(actual[:, 0])))
        ),
        "directional_events": int(directional.sum()),
        "angle_tail10": int(np.sum(abs(error[:, 0]) > 10)),
    }


def evaluate(manifest, rows, fs, truth_records, truth, model):
    regions = {}
    for level in JOINT_LEVELS:
        available = covered = accepted_covered = 0
        widths = []
        for r, f in zip(rows, fs):
            region = r["confidence_sets"].get(str(level))
            if region is None:
                continue
            available += 1
            loss = model.loss_at(f.values, truth[r["event_id"]])
            ok = loss is not None and loss <= region["joint_loss_limit"] + 1e-9
            covered += int(ok)
            accepted_covered += int(ok and r["accepted"])
            widths.append(
                [region["total_angle_width_deg"], region["total_entrance_width_um"]]
            )
        regions[str(level)] = {
            "input_events": len(rows),
            "with_region": available,
            "joint_covered": covered,
            "joint_coverage_on_inputs": covered / len(rows),
            "joint_coverage_with_region": covered / available if available else None,
            "accepted_joint_covered": accepted_covered,
            "mean_angle_width_deg": float(np.mean(np.array(widths)[:, 0]))
            if widths
            else None,
            "mean_entrance_width_um": float(np.mean(np.array(widths)[:, 1]))
            if widths
            else None,
        }
    strata = {}
    groups: dict[str, list[dict]] = {}
    for r in rows:
        cells = truth_records[r["event_id"]].get("projected_cell_crossings")
        if cells is not None:
            key = "projected_cells_" + "".join(cells)
            groups.setdefault(key, []).append(r)
    for key, subset in groups.items():
        strata[key] = {
            "input_events": len(subset),
            "accepted_events": sum(r["accepted"] for r in subset),
            "all_candidates": _metrics(subset, truth),
            "accepted": _metrics(subset, truth, accepted_only=True),
        }
    return {
        "input_events": len(rows),
        "accepted_events": sum(r["accepted"] for r in rows),
        "accepted_fraction": sum(r["accepted"] for r in rows) / len(rows),
        "rejection_reasons": dict(Counter(r["status"] for r in rows)),
        "all_candidates": _metrics(rows, truth),
        "accepted": _metrics(rows, truth, accepted_only=True),
        "joint_uncertainty": regions,
        "truth_only_evaluation_strata": strata,
        "units": {"angle": "deg", "entrance": "um at declared entrance plane"},
        "projected_cell_scope": "Straight-line crossings of pitch cells; distinct from collected charge and above-threshold signal counts.",
    }


def main(kwargs):
    action = kwargs["joint_action"]
    manifest, events = load_dataset(kwargs["dataset"])
    if action in {"features", "calibrate"}:
        config = (
            JointFeatureConfig(**strip_dataset._json(kwargs["feature_config"]))
            if kwargs.get("feature_config")
            else JointFeatureConfig(
                noise_floor=0.001
                if manifest["waveform_kind"] == "frontend_mV"
                else 1e-12
            )
        )
        if action == "features":
            fs = features(manifest, events, config)
            report = {
                "schema": "raser-joint-strip-features-v1",
                "channels": manifest["channels"],
                "events": [
                    {
                        "event_id": e["event_id"],
                        "values": f.values.tolist(),
                        "usable": f.usable,
                        "reason": f.reason,
                        "diagnostics": f.diagnostics,
                    }
                    for e, f in zip(events, fs)
                ],
            }
            strip_dataset._write(kwargs["output"], report)
        else:
            im, ie = load_dataset(kwargs["interval_dataset"])
            model = calibrate(
                manifest,
                events,
                kwargs["labels"],
                im,
                ie,
                kwargs["interval_labels"],
                config,
            )
            Path(kwargs["output"]).parent.mkdir(parents=True, exist_ok=True)
            model.save(kwargs["output"])
    else:
        model = JointStripResponse.load(kwargs["model"])
        rows, fs = predict(manifest, events, model)
        report = {
            "schema": "raser-joint-strip-prediction-v1",
            "channels": manifest["channels"],
            "waveform_kind": manifest["waveform_kind"],
            "events": rows,
            "model_sha256": strip_dataset._hash(kwargs["model"]),
            "dataset_sha256": manifest["manifest_sha256"],
            "algorithm_sha256": algorithm_hashes(),
            "uncertainty_scope": model.metadata["uncertainty_scope"],
        }
        if action == "evaluate":
            truth = labels(kwargs["labels"], [e["event_id"] for e in events])
            report["evaluation"] = evaluate(
                manifest,
                rows,
                fs,
                strip_dataset._json(kwargs["labels"])["events"],
                truth,
                model,
            )
        strip_dataset._write(kwargs["output"], report)
    print(Path(kwargs["output"]).resolve())
