"""Train and score single-layer strip regressors on explicit waveform datasets."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

from raser.core.reconstruction.features import FeatureConfig
from raser.core.reconstruction.strip_regression import (
    StripRegressor,
    regression_inputs,
    strip_vector,
)

from . import strip_dataset as dataset


def algorithm_hashes():
    root = Path(__file__).resolve().parents[2]
    names = [
        "core/reconstruction/features.py",
        "core/reconstruction/strip_regression.py",
        "apps/telescope/strip_dataset.py",
        "apps/telescope/strip_regression.py",
    ]
    return {name: dataset._hash(root / name) for name in names}


def features(manifest, events, config):
    result = [
        strip_vector(e["times_s"], e["signals"], manifest["channels"], config=config)
        for e in events
    ]
    return (
        np.asarray([r[0] for r in result]),
        np.asarray([r[1] for r in result]),
        result,
    )


def calibrate(
    manifest, events, labels_path, *, estimator, representation, config, seed, epochs
):
    if estimator.startswith("difference") and manifest["channels"] != ["1", "2", "3"]:
        raise ValueError(
            "Differential calibration requires the declared three-channel readout"
        )
    values, usable, rows = features(manifest, events, config)
    truth = dataset.labels(labels_path, [e["event_id"] for e in events])
    target = np.asarray([truth[e["event_id"]] for e in events])
    if estimator.startswith("difference"):
        target = target[:, :1]
    inputs = regression_inputs(values, estimator, representation, config.shape_samples)
    names = rows[0][3]
    if estimator == "difference-peak":
        input_names = ["signed_extremum_R_minus_L"]
    elif estimator == "difference-waveform":
        input_names = [f"R_minus_L_{i}" for i in range(config.shape_samples)]
    elif representation == "summary":
        input_names = names[:17] + names[-3:]
    else:
        input_names = names
    info = {key: manifest[key] for key in dataset.CONTRACT}
    info.update(
        feature_config=config.as_dict(),
        representation=representation,
        source_feature_names=names,
        model_input_names=input_names,
        numpy_version=np.__version__,
        algorithm_sha256=algorithm_hashes(),
        targets=["signed dx/dz"]
        if target.shape[1] == 1
        else ["signed dx/dz", "entrance um"],
        training_event_ids=[e["event_id"] for e in events],
        training_waveform_hashes=[e["waveform_hash"] for e in events],
        training_particle_ids=[e.get("particle_id", e["event_id"]) for e in events],
        training_manifest_sha256=manifest["manifest_sha256"],
        training_labels_sha256=dataset._hash(labels_path),
        training_input_count=len(events),
        training_usable_count=int(usable.sum()),
        uncertainty_scope="Finite regression candidates with independently uncalibrated acceptance.",
    )
    return StripRegressor.fit(
        estimator,
        inputs[usable],
        target[usable],
        metadata=info,
        seed=seed,
        epochs=epochs,
    )


def predict(manifest, events, model):
    dataset.compatible(manifest, model.metadata)
    if model.metadata["algorithm_sha256"] != algorithm_hashes():
        raise ValueError("Regression code differs from the calibrated source")
    prior = [
        {"event_id": event_id, "waveform_hash": digest, "particle_id": particle_id}
        for event_id, digest, particle_id in zip(
            model.metadata["training_event_ids"],
            model.metadata["training_waveform_hashes"],
            model.metadata["training_particle_ids"],
        )
    ]
    dataset.independent([prior, events])
    config = FeatureConfig(**model.metadata["feature_config"])
    values, usable, records = features(manifest, events, config)
    x = regression_inputs(
        values, model.estimator, model.metadata["representation"], config.shape_samples
    )
    estimates = model.predict(x)
    rows = []
    for event, estimate, valid, record in zip(events, estimates, usable, records):
        candidate = None
        if valid:
            candidate = {
                "slope": float(estimate[0]),
                "angle_deg": float(np.degrees(np.arctan(estimate[0]))),
                "entrance_um": float(estimate[1]) if len(estimate) == 2 else None,
            }
        rows.append(
            {
                "event_id": event["event_id"],
                "waveform_hash": event["waveform_hash"],
                "status": "candidate" if valid else record[2],
                "candidate": candidate,
                "strict_accepted": None,
            }
        )
    return rows


def score(rows, truth, records):
    def metrics(selected):
        available = [r for r in selected if r["candidate"] is not None]
        errors = np.asarray(
            [
                r["candidate"]["angle_deg"]
                - np.degrees(np.arctan(truth[r["event_id"]][0]))
                for r in available
            ]
        )
        positions = [
            r["candidate"]["entrance_um"] - truth[r["event_id"]][1]
            for r in available
            if r["candidate"]["entrance_um"] is not None
        ]
        return {
            "input_events": len(selected),
            "candidate_events": len(available),
            "candidate_fraction": len(available) / len(selected),
            "angle_rmse_deg": float(np.sqrt(np.mean(errors**2)))
            if len(errors)
            else None,
            "angle_bias_deg": float(errors.mean()) if len(errors) else None,
            "angle_std_deg": float(errors.std()) if len(errors) else None,
            "absolute_error_p90_deg": float(np.quantile(abs(errors), 0.9))
            if len(errors)
            else None,
            "entrance_rmse_um": float(np.sqrt(np.mean(np.square(positions))))
            if positions
            else None,
            "strict_accepted_events": None,
            "strict_accepted_fraction": None,
        }

    groups = {}
    for row in rows:
        cells = records[row["event_id"]].get("projected_cell_crossings")
        if cells is not None:
            groups.setdefault(str(len(cells)), []).append(row)
    return dict(
        **metrics(rows),
        statuses=dict(Counter(r["status"] for r in rows)),
        by_geometric_hit_count={
            key: metrics(selected) for key, selected in sorted(groups.items())
        },
        uncertainty_scope="Strict selection and confidence coverage require an independent calibration.",
    )


def main(kwargs):
    manifest, events = dataset.load_dataset(kwargs["dataset"])
    action = kwargs["joint_action"]
    if action in ("features", "calibrate"):
        config = (
            FeatureConfig(**dataset._json(kwargs["feature_config"]))
            if kwargs.get("feature_config")
            else FeatureConfig()
        )
        if manifest["waveform_kind"] != "frontend_mV":
            raise ValueError(
                "Regression inputs use frontend_mV with an explicit front-end response"
            )
        if action == "features":
            _, usable, rows = features(manifest, events, config)
            report = {
                "schema": "raser-strip-regression-feature-table-v1",
                "feature_names": rows[0][3],
                "feature_config": config.as_dict(),
                "events": [
                    {
                        "event_id": e["event_id"],
                        "usable": bool(ok),
                        "reason": r[2],
                        "values": r[0].tolist(),
                    }
                    for e, ok, r in zip(events, usable, rows)
                ],
            }
            dataset._write(kwargs["output"], report)
        else:
            model = calibrate(
                manifest,
                events,
                kwargs["labels"],
                estimator=kwargs["estimator"],
                representation=kwargs["representation"],
                config=config,
                seed=kwargs["seed"],
                epochs=kwargs["epochs"],
            )
            Path(kwargs["output"]).parent.mkdir(parents=True, exist_ok=True)
            model.save(kwargs["output"])
    else:
        model = StripRegressor.load(kwargs["model"])
        rows = predict(manifest, events, model)
        report = {
            "schema": "raser-strip-regression-prediction-v1",
            "estimator": model.estimator,
            "events": rows,
            "channels": manifest["channels"],
            "model_sha256": dataset._hash(kwargs["model"]),
            "dataset_sha256": manifest["manifest_sha256"],
        }
        if action == "evaluate":
            truth = dataset.labels(kwargs["labels"], [e["event_id"] for e in events])
            report["evaluation"] = score(
                rows, truth, dataset._json(kwargs["labels"])["events"]
            )
        dataset._write(kwargs["output"], report)
    print(Path(kwargs["output"]).resolve())
