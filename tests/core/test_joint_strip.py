from __future__ import annotations

import copy
import json

import numpy as np
import pytest

from raser.apps.telescope import joint_strip as workflow
from raser.apps.telescope import strip_dataset
from raser.core.reconstruction.joint_features import JointFeatureConfig, joint_features
from raser.core.reconstruction.joint_strip import JointStripResponse


def pulse_event(q, u, event_id, rng, *, shift=0.0, scale=1.0):
    t = np.linspace(-12, 8, 2001) * 1e-9
    common = scale * (1 + rng.normal(0, 0.04))
    waves = [
        -common
        * fraction
        * np.exp(-0.5 * ((t * 1e9 - 0.8 - shift - delay) / 0.10) ** 2)
        + rng.normal(0, 0.0005, len(t))
        for fraction, delay in [(0.5 + 0.1 * u, 0), (0.5 - 0.1 * u, 0.3 * q)]
    ]
    return {
        "event_id": event_id,
        "times_s": [t, t],
        "signals": waves,
        "waveform_hash": strip_dataset._waveform_hash([t, t], waves),
    }


@pytest.fixture(scope="module")
def calibrated(tmp_path_factory):
    root = tmp_path_factory.mktemp("joint-strip")
    rng = np.random.default_rng(711)
    manifest = {
        "schema": "raser-joint-strip-dataset-v1",
        "kind": "strip",
        "channels": ["1", "2"],
        "positions_um": [[-20.0, 0.0], [0.0, 0.0]],
        "response_id": "a" * 64,
        "waveform_kind": "frontend_mV",
        "entrance_reference_um": 29.0,
        "entrance_z_um": 0.0,
        "manifest_sha256": "b" * 64,
    }
    config = JointFeatureConfig(shape_samples=64)
    targets = [
        np.array(
            [
                (q, u)
                for q in np.linspace(-0.8, 0.8, 5)
                for u in [-2.0, 0.0, 2.0]
                for _ in range(12)
            ]
        ),
        rng.uniform([-0.7, -1.8], [0.7, 1.8], (160, 2)),
    ]
    populations, paths = [], []
    for role, points in zip(["train", "interval"], targets):
        events = [
            pulse_event(q, u, f"{role}-{i}", rng) for i, (q, u) in enumerate(points)
        ]
        path = root / (role + "-labels.json")
        path.write_text(
            json.dumps(
                {
                    "events": {
                        e["event_id"]: {"slopes": [q], "entrance_um": [u]}
                        for e, (q, u) in zip(events, points)
                    }
                }
            )
        )
        populations.append(events)
        paths.append(path)
    model = workflow.calibrate(
        manifest, populations[0], paths[0], manifest, populations[1], paths[1], config
    )
    return manifest, model, populations, config


def test_two_readouts_jointly_recover_off_grid_position_and_slope(calibrated):
    m, model, _, _ = calibrated
    rng = np.random.default_rng(712)
    targets = [(-0.61, 0.7), (0.38, -1.1), (0.63, 1.2)]
    events = [pulse_event(q, u, f"new-{i}", rng) for i, (q, u) in enumerate(targets)]
    rows, _ = workflow.predict(m, events, model)
    for row, (q, u) in zip(rows, targets):
        assert row["best_fit"]["slope"] == pytest.approx(q, abs=0.04)
        assert row["best_fit"]["entrance_um"] == pytest.approx(u, abs=0.15)
        assert row["confidence_sets"]["0.95"]["entrance_intervals_um"]
        assert row["confidence_sets"]["0.95"]["angle_intervals_deg"]


def test_absolute_integrals_survive_common_amplitude_changes():
    config = JointFeatureConfig()
    t = np.linspace(-12, 8, 2001) * 1e-9
    waves = [
        -np.exp(-0.5 * ((t * 1e9 - 0.7) / 0.1) ** 2),
        -0.5 * np.exp(-0.5 * ((t * 1e9 - 0.9) / 0.1) ** 2),
    ]
    first = joint_features(
        [t, t], waves, [[-20, 0], [0, 0]], config=config, waveform_kind="frontend_mV"
    )
    second = joint_features(
        [t, t],
        [2 * w for w in waves],
        [[-20, 0], [0, 0]],
        config=config,
        waveform_kind="frontend_mV",
    )
    assert np.allclose(
        second.diagnostics["signed_integrals"],
        2 * np.array(first.diagnostics["signed_integrals"]),
    )
    assert not np.allclose(first.values[:8], second.values[:8])
    assert np.allclose(first.values[18:], second.values[18:])


def test_current_integral_has_physical_charge_units():
    t = np.linspace(-12, 8, 4001) * 1e-9
    pulse = -2e-6 * np.exp(-0.5 * ((t * 1e9 - 0.8) / 0.1) ** 2)
    f = joint_features(
        [t, t],
        [pulse, pulse],
        [[-20, 0], [0, 0]],
        config=JointFeatureConfig(noise_floor=1e-12),
        waveform_kind="current_A",
    )
    assert f.diagnostics["integral_units"] == "fC"
    assert f.diagnostics["signed_integrals"][0] == pytest.approx(
        -2 * np.sqrt(2 * np.pi) * 0.1, rel=1e-6
    )


def test_common_clock_shift_keeps_relative_shapes_and_charge():
    t = np.linspace(-12, 8, 2001) * 1e-9
    waves = [-np.exp(-0.5 * ((t * 1e9 - 0.7 - d) / 0.1) ** 2) for d in [0, 0.2]]
    cfg = JointFeatureConfig()
    a = joint_features(
        [t, t], waves, [[-20, 0], [0, 0]], config=cfg, waveform_kind="frontend_mV"
    )
    b = joint_features(
        [t + 0.05e-9, t + 0.05e-9],
        waves,
        [[-20, 0], [0, 0]],
        config=cfg,
        waveform_kind="frontend_mV",
    )
    assert np.allclose(a.values, b.values, atol=1e-10)


def test_unobserved_third_waveform_is_not_read_or_hashed(tmp_path):
    t = np.linspace(-12, 8, 1001) * 1e-9
    pulse = -np.exp(-0.5 * ((t * 1e9 - 0.8) / 0.1) ** 2)
    source = tmp_path / "event.npz"
    np.savez(
        source,
        frontend_time_s_1=t,
        frontend_time_s_2=t,
        frontend_mV_1=pulse,
        frontend_mV_2=pulse,
    )
    manifest = {
        "schema": "raser-joint-strip-dataset-v1",
        "kind": "strip",
        "channels": ["1", "2"],
        "positions_um": [[-20, 0], [0, 0]],
        "waveform_kind": "frontend_mV",
        "response_id": "a" * 64,
        "entrance_reference_um": 29.0,
        "entrance_z_um": 0.0,
        "events": [{"event_id": "one", "waveforms": "event.npz"}],
    }
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(manifest))
    _, first = workflow.load_dataset(path)
    np.savez(
        source,
        frontend_time_s_1=t,
        frontend_time_s_2=t,
        frontend_mV_1=pulse,
        frontend_mV_2=pulse,
        frontend_time_s_3=np.array([np.nan]),
        frontend_mV_3=np.array([object()]),
    )
    _, second = workflow.load_dataset(path)
    assert first[0]["waveform_hash"] == second[0]["waveform_hash"]
    assert len(second[0]["signals"]) == 2


def test_identical_observations_retain_joint_position_angle_ambiguity():
    y = np.array(
        [(q, u) for q in [-0.8, 0, 0.8] for u in [-2.0, 0.0, 2.0] for _ in range(12)]
    )
    x = np.zeros((len(y), 18 + 2 * 8))
    metadata = {
        "channels": ["1", "2"],
        "feature_config": {"shape_samples": 8},
        "training_event_ids": [],
    }
    model = JointStripResponse.fit(
        x,
        y,
        floors=np.full(x.shape[1], 0.02),
        metadata=metadata,
        usable=np.ones(len(x), dtype=bool),
    )
    calibration = np.zeros((120, x.shape[1]))
    labels = np.random.default_rng(713).uniform([-0.79, -1.9], [0.79, 1.9], (120, 2))
    model.calibrate(
        calibration, labels, usable=[True] * 120, event_ids=[str(i) for i in range(120)]
    )
    row = model.predict(x[0])
    assert not row["accepted"]
    assert row["confidence_sets"]["0.95"]["entrance_intervals_um"] == [[-2.0, 2.0]]
    assert np.allclose(row["confidence_sets"]["0.95"]["slope_intervals"], [[-0.8, 0.8]])


@pytest.mark.parametrize("role", [0, 1])
def test_relabelled_training_and_interval_replays_are_rejected(calibrated, role):
    m, model, populations, _ = calibrated
    event = copy.deepcopy(populations[role][0])
    event["event_id"] = "relabeled"
    with pytest.raises(ValueError, match="leakage"):
        workflow.predict(m, [event], model)


def test_two_and_three_channel_contracts_are_distinct(calibrated):
    m, model, _, _ = calibrated
    changed = {
        **m,
        "channels": ["1", "2", "3"],
        "positions_um": [[-20.0, 0.0], [0.0, 0.0], [20.0, 0.0]],
    }
    with pytest.raises(ValueError, match="contract differs"):
        workflow.predict(changed, [], model)


def test_entrance_labels_are_explicit_and_not_midplane_impact(tmp_path):
    p = tmp_path / "labels.json"
    p.write_text(json.dumps({"events": {"x": {"slopes": [0.4], "impact_um": [1.0]}}}))
    with pytest.raises(ValueError, match="entrance_um"):
        workflow.labels(p, ["x"])


def test_joint_model_roundtrip_and_immutable_outputs(calibrated, tmp_path):
    m, model, _, _ = calibrated
    path = tmp_path / "joint.npz"
    model.save(path)
    restored = JointStripResponse.load(path)
    event = pulse_event(0.33, 0.7, "roundtrip", np.random.default_rng(714))
    a, _ = workflow.predict(m, [event], model)
    b, _ = workflow.predict(m, [event], restored)
    assert a == b
    with pytest.raises(FileExistsError):
        model.save(path)
    with pytest.raises(ValueError, match="immutable"):
        model.calibrate([], [], usable=[], event_ids=[])


def test_coupled_training_locus_is_rejected():
    y = np.repeat(np.array([[-0.5, -1], [0, 0], [0.5, 1]]), 12, axis=0)
    x = np.zeros((len(y), 18 + 2 * 8))
    with pytest.raises(ValueError, match="independently cross"):
        JointStripResponse.fit(
            x,
            y,
            floors=np.ones(x.shape[1]),
            usable=[True] * len(y),
            metadata={"channels": ["1", "2"], "feature_config": {"shape_samples": 8}},
        )


def test_joint_cli_predict_has_no_truth_input():
    from raser.cli.raser import build_parser

    args = build_parser().parse_args(
        [
            "telescope",
            "joint-strip",
            "predict",
            "--dataset",
            "signals.json",
            "--model",
            "model.npz",
            "--output",
            "prediction.json",
        ]
    )
    assert args.joint_action == "predict"
    assert not hasattr(args, "labels")


def test_public_cli_reloads_template_and_scores_one_new_particle(calibrated, tmp_path):
    from raser.cli.raser import main

    manifest, model, _, _ = calibrated
    model_path = tmp_path / "model.npz"
    model.save(model_path)
    event = pulse_event(0.33, 0.7, "cli-new", np.random.default_rng(716))
    np.savez_compressed(
        tmp_path / "wave.npz",
        frontend_time_s_1=event["times_s"][0],
        frontend_time_s_2=event["times_s"][1],
        frontend_mV_1=event["signals"][0],
        frontend_mV_2=event["signals"][1],
    )
    data_path = tmp_path / "dataset.json"
    data_path.write_text(
        json.dumps(
            {
                **manifest,
                "events": [{"event_id": "cli-new", "waveforms": "wave.npz"}],
            }
        )
    )
    labels_path = tmp_path / "labels.json"
    labels_path.write_text(
        json.dumps(
            {
                "events": {
                    "cli-new": {
                        "slopes": [0.33],
                        "entrance_um": [0.7],
                        "projected_cell_crossings": ["2"],
                    }
                }
            }
        )
    )
    output = tmp_path / "evaluation.json"
    assert (
        main(
            [
                "telescope",
                "joint-strip",
                "evaluate",
                "--dataset",
                str(data_path),
                "--labels",
                str(labels_path),
                "--model",
                str(model_path),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    result = json.loads(output.read_text())
    assert result["events"][0]["best_fit"]["slope"] == pytest.approx(0.33, abs=0.04)
    assert result["evaluation"]["input_events"] == 1
    assert result["evaluation"]["all_candidates"]["events"] == 1
