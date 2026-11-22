from __future__ import annotations

import json

import numpy as np
import pytest

from raser.apps.telescope import strip_dataset, strip_regression
from raser.cli.raser import build_parser, main
from raser.core.reconstruction.features import FeatureConfig
from raser.core.reconstruction.strip_regression import (
    StripRegressor,
    regression_inputs,
    strip_vector,
)


def pulses(slope, entrance, event_id, rng, channels=("1", "2", "3")):
    time = np.linspace(-12, 8, 2001) * 1e-9
    shapes = []
    for index in range(3):
        fraction = (0.3, 1.0, 0.3)[index] * (1 + 0.06 * (index - 1) * entrance)
        delay = 0.9 + 0.5 * (index - 1) * slope
        voltage = -fraction * np.exp(-0.5 * ((time * 1e9 - delay) / 0.16) ** 2)
        shapes.append(voltage + rng.normal(0, 0.0004, len(time)))
    selected = [shapes[int(c) - 1] for c in channels]
    return {
        "event_id": event_id,
        "times_s": [time] * len(channels),
        "signals": selected,
        "waveform_hash": strip_dataset._waveform_hash([time] * len(channels), selected),
    }


def test_features_keep_relative_timing_and_exclude_missing_channels():
    event = pulses(0.3, -1.0, "x", np.random.default_rng(81))
    cfg = FeatureConfig()
    a, valid, _, names = strip_vector(
        event["times_s"], event["signals"], ["1", "2", "3"], config=cfg
    )
    b, *_ = strip_vector(
        [t + 0.04e-9 for t in event["times_s"]],
        event["signals"],
        ["1", "2", "3"],
        config=cfg,
    )
    assert valid and len(names) == len(set(names)) == len(a) == 120
    np.testing.assert_allclose(a, b, atol=2e-3)
    two, *_ = strip_vector(
        event["times_s"][:2], event["signals"][:2], ["1", "2"], config=cfg
    )
    assert np.all(two[21:117].reshape(3, 32)[2] == 0)
    assert regression_inputs(a[None], "ridge", "summary", 32).shape == (1, 20)
    assert regression_inputs(a[None], "difference-waveform", "waveform", 32).shape == (
        1,
        32,
    )


def test_left_right_mirror_reverses_difference():
    cfg = FeatureConfig()
    event = pulses(0.31, 0, "x", np.random.default_rng(82))
    a, *_ = strip_vector(
        event["times_s"], event["signals"], ["1", "2", "3"], config=cfg
    )
    b, *_ = strip_vector(
        event["times_s"], event["signals"][::-1], ["1", "2", "3"], config=cfg
    )
    da = regression_inputs(a[None], "difference-waveform", "waveform", 32)
    db = regression_inputs(b[None], "difference-waveform", "waveform", 32)
    np.testing.assert_allclose(da, -db, atol=1e-12)
    assert a[9] == pytest.approx(-b[10], abs=2e-3)


@pytest.mark.parametrize(
    "estimator", ["ridge", "mlp", "difference-peak", "difference-waveform"]
)
def test_training_and_reloading_recover_held_out_signed_slopes(estimator, tmp_path):
    rng = np.random.default_rng(83)
    x = rng.normal(0, 1, (200, 3))
    y = np.c_[0.12 * x[:, 0] - 0.08 * x[:, 1], x[:, 2]]
    model = StripRegressor.fit(estimator, x, y, metadata={}, epochs=220)
    new_x = rng.normal(0, 0.6, (24, 3))
    expected = np.c_[0.12 * new_x[:, 0] - 0.08 * new_x[:, 1], new_x[:, 2]]
    predicted = model.predict(new_x)
    assert np.sqrt(np.mean((predicted[:, 0] - expected[:, 0]) ** 2)) < 0.025
    assert np.sqrt(np.mean((predicted[:, 1] - expected[:, 1]) ** 2)) < 0.15
    path = tmp_path / "model.npz"
    model.save(path)
    np.testing.assert_array_equal(predicted, StripRegressor.load(path).predict(new_x))
    with pytest.raises(FileExistsError):
        model.save(path)


def test_ridge_matches_explicit_normal_equations():
    rng = np.random.default_rng(84)
    x = rng.normal(size=(80, 5))
    target = x[:, :2]
    model = StripRegressor.fit("ridge", x, target, metadata={})
    a = model.arrays
    z = np.clip((x - a["xmean"]) / a["xstd"], -8, 8) - a["xoffset"]
    weights = np.linalg.solve(
        z.T @ z / len(z) + 0.1 * np.eye(5),
        z.T @ ((target - a["ymean"]) / a["ystd"] - a["intercept"]) / len(z),
    )
    np.testing.assert_allclose(a["weights"], weights)


def test_candidates_keep_failed_waveforms_in_denominator():
    rows = [
        {
            "event_id": "one",
            "status": "candidate",
            "candidate": {"angle_deg": 5.0, "entrance_um": 0.0},
        },
        {"event_id": "failed", "status": "no_significant_pulse", "candidate": None},
    ]
    truth = {"one": [np.tan(np.deg2rad(3)), 1.0], "failed": [0.0, 0.0]}
    records = {key: {"projected_cell_crossings": ["2"]} for key in truth}
    score = strip_regression.score(rows, truth, records)
    assert score["input_events"] == 2 and score["candidate_events"] == 1
    assert score["angle_rmse_deg"] == pytest.approx(2.0)
    assert score["candidate_fraction"] == 0.5
    assert score["strict_accepted_fraction"] is None
    assert score["by_geometric_hit_count"]["1"]["input_events"] == 2


def test_duplicate_waveforms_with_different_labels_are_rejected():
    event = pulses(0.1, 0.0, "a", np.random.default_rng(85))
    duplicate = dict(event, event_id="b")
    with pytest.raises(ValueError, match="leakage"):
        strip_dataset.independent([[event], [duplicate]])


def test_noisy_variants_of_one_particle_stay_in_one_split():
    first = pulses(0.1, 0, "one", np.random.default_rng(99))
    second = pulses(0.1, 0, "two", np.random.default_rng(100))
    first["particle_id"] = second["particle_id"] = "physical-track"
    strip_dataset.independent([[first, second]])
    with pytest.raises(ValueError, match="leakage"):
        strip_dataset.independent([[first], [second]])


def test_loader_reads_only_declared_channels_and_rejects_embedded_truth(tmp_path):
    t = np.linspace(-12, 8, 401) * 1e-9
    np.savez(
        tmp_path / "event.npz", frontend_time_s_2=t, frontend_mV_2=np.zeros_like(t)
    )
    record = {"event_id": "x", "waveforms": "event.npz"}
    manifest = {
        "schema": "raser-joint-strip-dataset-v1",
        "kind": "strip",
        "channels": ["2"],
        "positions_um": [[0, 0]],
        "response_id": "a" * 64,
        "waveform_kind": "frontend_mV",
        "entrance_reference_um": 29,
        "entrance_z_um": 0,
        "events": [record],
    }
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(manifest))
    _, events = strip_dataset.load_dataset(path)
    assert len(events[0]["signals"]) == 1
    record["true_angle_deg"] = "0"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="labels are separate"):
        strip_dataset.load_dataset(path)


def test_cli_prediction_has_no_truth_argument():
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
    assert not hasattr(args, "labels")


def test_cli_train_predict_and_evaluate(tmp_path):
    rng = np.random.default_rng(86)
    metadata = {
        "schema": "raser-joint-strip-dataset-v1",
        "kind": "strip",
        "channels": ["1", "2", "3"],
        "positions_um": [[-20, 0], [0, 0], [20, 0]],
        "response_id": "a" * 64,
        "waveform_kind": "frontend_mV",
        "entrance_reference_um": 29,
        "entrance_z_um": 0,
    }
    for role, count in [("train", 40), ("test", 8)]:
        events, truth = [], {}
        for i in range(count):
            slope, entrance = rng.uniform(-0.3, 0.3), rng.uniform(-2, 2)
            event_id = f"{role}-{i}"
            e = pulses(slope, entrance, event_id, rng)
            filename = f"{event_id}.npz"
            np.savez_compressed(
                tmp_path / filename,
                **{
                    key: value
                    for c, t, v in zip(("1", "2", "3"), e["times_s"], e["signals"])
                    for key, value in [
                        (f"frontend_time_s_{c}", t),
                        (f"frontend_mV_{c}", v),
                    ]
                },
            )
            events.append({"event_id": event_id, "waveforms": filename})
            truth[event_id] = {
                "slopes": [slope],
                "entrance_um": [entrance],
                "projected_cell_crossings": ["2"],
            }
        (tmp_path / f"{role}.json").write_text(
            json.dumps(dict(metadata, events=events))
        )
        (tmp_path / f"{role}-labels.json").write_text(json.dumps({"events": truth}))
    prefix = ["telescope", "joint-strip"]
    model = tmp_path / "model.npz"
    assert (
        main(
            prefix
            + [
                "calibrate",
                "--estimator",
                "ridge",
                "--dataset",
                str(tmp_path / "train.json"),
                "--labels",
                str(tmp_path / "train-labels.json"),
                "--output",
                str(model),
            ]
        )
        == 0
    )
    output = tmp_path / "predicted.json"
    assert (
        main(
            prefix
            + [
                "predict",
                "--dataset",
                str(tmp_path / "test.json"),
                "--model",
                str(model),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    evaluation = tmp_path / "evaluation.json"
    assert (
        main(
            prefix
            + [
                "evaluate",
                "--dataset",
                str(tmp_path / "test.json"),
                "--labels",
                str(tmp_path / "test-labels.json"),
                "--model",
                str(model),
                "--output",
                str(evaluation),
            ]
        )
        == 0
    )
    a, b = json.loads(output.read_text()), json.loads(evaluation.read_text())
    assert a["events"] == b["events"]
    assert b["evaluation"]["candidate_events"] == 8
    assert b["evaluation"]["angle_rmse_deg"] < 4.0
