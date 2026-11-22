"""Generate synthetic Gaussian pulses locally and exercise the public strip CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

import numpy as np


def generate_sample(root: Path):
    """Write an analytic software fixture with separate train and test particles."""
    root.mkdir(parents=True, exist_ok=False)
    (root / "events").mkdir()
    seed = 20261122
    source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    contract = {
        "model": "synthetic-gaussian-strip-v1",
        "source_sha256": source_hash,
        "time_ns": [-12.0, 8.0, 1001],
        "noise_mV": 0.0004,
        "depth_um": 50.0,
        "pitch_um": 20.0,
    }
    response_id = hashlib.sha256(
        json.dumps(contract, sort_keys=True).encode()
    ).hexdigest()
    metadata = {
        "schema": "raser-joint-strip-dataset-v1",
        "kind": "strip",
        "response_id": response_id,
        "waveform_kind": "frontend_mV",
        "channels": ["1", "2", "3"],
        "positions_um": [[-20, 0], [0, 0], [20, 0]],
        "entrance_reference_um": 0,
        "entrance_z_um": 0,
    }
    time_ns = np.linspace(-12, 8, 1001)
    streams = np.random.SeedSequence(seed).spawn(2)
    for role, stream in zip(("train", "test"), streams):
        rng = np.random.default_rng(stream)
        points = (
            [(q, u) for q in (-0.45, 0, 0.45) for u in (-5, 0, 5) for _ in range(4)]
            if role == "train"
            else rng.uniform([-0.4, -4], [0.4, 4], (12, 2))
        )
        events, labels = [], {}
        for index, (slope, entrance) in enumerate(points):
            event_id = f"synthetic-{role}-{index:04d}"
            arrays = {}
            for channel, side, scale in zip(("1", "2", "3"), (-1, 0, 1), (0.3, 1, 0.3)):
                amplitude = scale * (1 + 0.06 * side * entrance)
                delay = 0.9 + 0.5 * side * slope
                voltage = -amplitude * np.exp(-0.5 * ((time_ns - delay) / 0.16) ** 2)
                arrays[f"frontend_time_s_{channel}"] = time_ns * 1e-9
                arrays[f"frontend_mV_{channel}"] = voltage + rng.normal(
                    0, contract["noise_mV"], len(time_ns)
                )
            relative = f"events/{event_id}.npz"
            np.savez_compressed(root / relative, **arrays)
            events.append(
                {"event_id": event_id, "particle_id": event_id, "waveforms": relative}
            )
            endpoints = np.array([entrance, entrance + 50 * slope])
            cells = np.floor((np.sort(endpoints) + 10) / 20).astype(int)
            labels[event_id] = {
                "slopes": [float(slope)],
                "entrance_um": [float(entrance)],
                "projected_cell_crossings": [
                    str(2 + c) for c in range(cells[0], cells[1] + 1)
                ],
            }
        (root / f"{role}.json").write_text(
            json.dumps(dict(metadata, events=events), indent=2) + "\n"
        )
        (root / f"{role}-labels.json").write_text(
            json.dumps({"events": labels}, indent=2) + "\n"
        )
    (root / "generation.json").write_text(
        json.dumps({"seed": seed, "contract": contract}, indent=2) + "\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("work/single-strip-example")
    )
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    root = output / "data"
    generate_sample(root)
    views = {"C": ["2"], "LC": ["1", "2"], "CR": ["2", "3"], "LCR": ["1", "2", "3"]}
    manifests = {}
    for view, channels in views.items():
        for role in ("train", "test"):
            manifest = json.loads((root / f"{role}.json").read_text())
            positions = dict(zip(manifest["channels"], manifest["positions_um"]))
            manifest["channels"] = channels
            manifest["positions_um"] = [positions[c] for c in channels]
            for event in manifest["events"]:
                event["waveforms"] = os.path.relpath(root / event["waveforms"], output)
            path = output / f"{role}-{view}.json"
            path.write_text(json.dumps(manifest, indent=2) + "\n")
            manifests[role, view] = path
    settings = [(view, method) for view in views for method in ("ridge", "mlp")] + [
        ("LCR", "difference-peak"),
        ("LCR", "difference-waveform"),
    ]
    reports = {}
    for view, method in settings:
        name = f"{view}-{method}"
        model, predicted, scored = (
            output / f"{name}{suffix}"
            for suffix in (".npz", "-predicted.json", "-scored.json")
        )
        common = ["raser", "telescope", "joint-strip"]
        commands = [
            common
            + [
                "calibrate",
                "--estimator",
                method,
                "--dataset",
                str(manifests["train", view]),
                "--labels",
                str(root / "train-labels.json"),
                "--output",
                str(model),
            ],
            common
            + [
                "predict",
                "--dataset",
                str(manifests["test", view]),
                "--model",
                str(model),
                "--output",
                str(predicted),
            ],
            common
            + [
                "evaluate",
                "--dataset",
                str(manifests["test", view]),
                "--labels",
                str(root / "test-labels.json"),
                "--model",
                str(model),
                "--output",
                str(scored),
            ],
        ]
        for command in commands:
            subprocess.run(command, check=True)
        report = json.loads(scored.read_text())
        if report["events"] != json.loads(predicted.read_text())["events"]:
            raise ValueError("Prediction differs after evaluation labels are supplied")
        reports[name] = report
    truth = json.loads((root / "test-labels.json").read_text())["events"]
    ids = list(truth)
    lookup = {
        name: {e["event_id"]: e["candidate"] for e in report["events"]}
        for name, report in reports.items()
    }
    common_ids = [
        i for i in ids if all(results[i] is not None for results in lookup.values())
    ]
    summary = {
        "scope": "Synthetic Gaussian software fixture; scores describe the analytic generator.",
        "requested": len(ids),
        "common_candidates": len(common_ids),
        "by_geometric_hit_count": {},
    }
    for count in (1, 2, 3):
        requested = [
            i for i in ids if len(truth[i]["projected_cell_crossings"]) == count
        ]
        selected = [i for i in common_ids if i in requested]
        angles = np.degrees(np.arctan([truth[i]["slopes"][0] for i in selected]))
        scores = {}
        if selected:
            scores["constant_zero"] = float(np.sqrt(np.mean(angles**2)))
            for name, results in lookup.items():
                error = np.array([results[i]["angle_deg"] for i in selected]) - angles
                scores[name] = float(np.sqrt(np.mean(error**2)))
        summary["by_geometric_hit_count"][str(count)] = {
            "requested": len(requested),
            "common_candidates": len(selected),
            "candidate_angle_rmse_deg": scores,
            "strict_accepted_fraction": None,
        }
    (output / "comparison.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
