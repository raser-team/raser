"""Differential baselines, ridge regression and a small strip waveform network."""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np

from .features import FeatureConfig, extract_features

ESTIMATORS = ("difference-peak", "difference-waveform", "ridge", "mlp")
FEATURE_SCHEMA = "raser-strip-regression-features-v1"
CHANNEL_NAMES = ("L", "C", "R")


def strip_vector(times_s, signals, channels, *, config: FeatureConfig):
    """Encode supplied readouts in fixed L, C, R slots and retain pulse polarity."""
    if (
        len(channels) != len(signals)
        or len(times_s) != len(signals)
        or not channels
        or len(set(channels)) != len(channels)
        or any(c not in ("1", "2", "3") for c in channels)
        or list(channels) != [c for c in ("1", "2", "3") if c in channels]
    ):
        raise ValueError("Regression readouts must be an ordered subset of 1, 2, 3")
    slots = {channel: index for index, channel in enumerate(channels)}
    times = [times_s[slots.get(c, 0)] for c in ("1", "2", "3")]
    waves = [
        signals[slots[c]] if c in slots else np.zeros_like(times_s[0], dtype=float)
        for c in ("1", "2", "3")
    ]
    result = extract_features(
        times, waves, [[-1, 0], [0, 0], [1, 0]], mode="joint", config=config
    )
    d = result.diagnostics
    active = np.asarray(d["active_channels"], dtype=bool)
    cfds = d["cfd_ns"]
    relative = [
        cfds[i + 1] - cfds[i] if active[i] and active[i + 1] else 0.0 for i in (0, 1)
    ]
    shape = result.values[18:].reshape(3, config.shape_samples)
    odd, even = shape[2] - shape[0], shape[2] + shape[0] - 2 * shape[1]
    coordinate = np.linspace(-1, 1, config.shape_samples)
    moments = [
        odd.mean(),
        np.mean(odd * coordinate),
        even.mean(),
        np.mean(even * coordinate),
    ]
    amplitude, noise = np.asarray(d["amplitude"]), np.asarray(d["baseline_noise"])
    minimum_snr = (
        float(np.min(amplitude[active] / noise[active])) if active.any() else 1.0
    )
    vector = np.r_[
        result.values[:9],
        relative,
        d["leading_rise_ns"],
        active.astype(float),
        moments,
        shape.ravel(),
        np.log(max(float(amplitude.sum()), 1e-12)),
        np.log(max(minimum_snr, 1.0)),
        active.sum(),
    ]
    summary_names = (
        [
            f"{lobe}_area_fraction_{c}"
            for lobe in ("negative", "positive")
            for c in CHANNEL_NAMES
        ]
        + [f"peak_fraction_{c}" for c in CHANNEL_NAMES]
        + ["time_C_minus_L_ns", "time_R_minus_C_ns"]
        + [f"rise_20_80_ns_{c}" for c in CHANNEL_NAMES]
        + [f"timing_valid_{c}" for c in CHANNEL_NAMES]
    )
    names = (
        summary_names
        + ["odd_mean", "odd_first_moment", "even_mean", "even_first_moment"]
        + [
            f"waveform_{c}_{i}"
            for c in CHANNEL_NAMES
            for i in range(config.shape_samples)
        ]
        + ["log_total_peak", "log_minimum_timing_snr", "active_channel_count"]
    )
    return vector, result.usable, result.reason, names


def regression_inputs(values, estimator, representation, shape_samples):
    """Select the archived feature ordering or the signed R-minus-L trace."""
    x = np.asarray(values, dtype=float)
    if x.ndim != 2 or x.shape[1] != 24 + 3 * shape_samples or not np.isfinite(x).all():
        raise ValueError("Finite complete strip regression feature rows required")
    if estimator not in ESTIMATORS or representation not in ("summary", "waveform"):
        raise ValueError("Unsupported strip estimator or representation")
    shapes = x[:, 21:-3].reshape(len(x), 3, shape_samples)
    difference = shapes[:, 2] - shapes[:, 0]
    if estimator == "difference-peak":
        peak = np.argmax(abs(difference), axis=1)
        return difference[np.arange(len(x)), peak, None]
    if estimator == "difference-waveform":
        return difference
    if representation == "summary":
        return np.c_[x[:, :17], x[:, -3:]]
    return x


@dataclass
class StripRegressor:
    estimator: str
    arrays: dict
    metadata: dict

    @classmethod
    def fit(cls, estimator, features, targets, *, metadata, seed=20261120, epochs=220):
        x, y = np.asarray(features, dtype=float), np.asarray(targets, dtype=float)
        if (
            estimator not in ESTIMATORS
            or x.ndim != 2
            or y.ndim != 2
            or len(x) < 3
            or len(x) != len(y)
            or not x.shape[1]
            or y.shape[1] not in (1, 2)
            or not np.isfinite(x).all()
            or not np.isfinite(y).all()
            or type(seed) is not int
            or seed < 0
            or type(epochs) is not int
            or epochs < 1
        ):
            raise ValueError(
                "Finite training rows, targets and positive training settings required"
            )
        xmean, xstd = x.mean(0), np.maximum(x.std(0), 1e-6)
        ymean, ystd = y.mean(0), np.maximum(y.std(0), 1e-6)
        if estimator == "difference-peak":
            xmean, xstd = np.zeros(x.shape[1]), np.ones(x.shape[1])
        scaled_x = (x - xmean) / xstd
        if estimator != "difference-peak":
            scaled_x = np.clip(scaled_x, -8, 8)
        scaled_y = (y - ymean) / ystd
        arrays = {"xmean": xmean, "xstd": xstd, "ymean": ymean, "ystd": ystd}
        info = dict(
            metadata,
            schema="raser-strip-regressor-v1",
            estimator=estimator,
            seed=seed,
            training_rows=len(x),
            feature_schema=FEATURE_SCHEMA,
        )
        if estimator != "mlp":
            arrays.update(xoffset=scaled_x.mean(0), intercept=scaled_y.mean(0))
            centered = scaled_x - arrays["xoffset"]
            if estimator == "difference-peak":
                weights = np.linalg.lstsq(
                    centered, scaled_y - arrays["intercept"], rcond=None
                )[0]
            else:
                weights = np.linalg.solve(
                    centered.T @ centered / len(x) + 0.1 * np.eye(x.shape[1]),
                    centered.T @ (scaled_y - arrays["intercept"]) / len(x),
                )
            arrays["weights"] = weights
            info["ridge_penalty"] = 0.0 if estimator == "difference-peak" else 0.1
        else:
            rng = np.random.default_rng(seed)
            w1 = rng.normal(0, 1 / np.sqrt(x.shape[1]), (x.shape[1], 24))
            w2 = rng.normal(0, 1 / np.sqrt(24), (24, y.shape[1]))
            b1, b2 = np.zeros(24), np.zeros(y.shape[1])
            params = (w1, b1, w2, b2)
            first, second = (
                [np.zeros_like(p) for p in params],
                [np.zeros_like(p) for p in params],
            )
            losses, step = [], 0
            for _ in range(epochs):
                permutation = rng.permutation(len(x))
                for start in range(0, len(x), 64):
                    indices = permutation[start : start + 64]
                    bx, by = scaled_x[indices], scaled_y[indices]
                    hidden = np.tanh(bx @ w1 + b1)
                    residual = (hidden @ w2 + b2 - by) * (2 / by.size)
                    upstream = (residual @ w2.T) * (1 - hidden**2)
                    grads = (
                        bx.T @ upstream,
                        upstream.sum(0),
                        hidden.T @ residual,
                        residual.sum(0),
                    )
                    step += 1
                    for p, m, v, gradient in zip(params, first, second, grads):
                        m *= 0.9
                        m += 0.1 * gradient
                        v *= 0.999
                        v += 0.001 * gradient**2
                        p -= (
                            0.003
                            * (m / (1 - 0.9**step))
                            / (np.sqrt(v / (1 - 0.999**step)) + 1e-8)
                        )
                losses.append(
                    float(
                        np.mean((np.tanh(scaled_x @ w1 + b1) @ w2 + b2 - scaled_y) ** 2)
                    )
                )
            arrays.update(w1=w1, b1=b1, w2=w2, b2=b2, loss=np.asarray(losses))
            info.update(
                hidden_units=24, epochs=epochs, batch_size=64, learning_rate=0.003
            )
        model = cls(estimator, arrays, info)
        model.validate()
        return model

    def validate(self):
        a = self.arrays
        required = {"xmean", "xstd", "ymean", "ystd"}
        required.update(
            ("w1", "b1", "w2", "b2", "loss")
            if self.estimator == "mlp"
            else ("xoffset", "intercept", "weights")
        )
        if (
            self.estimator not in ESTIMATORS
            or not required <= a.keys()
            or self.metadata.get("schema") != "raser-strip-regressor-v1"
            or self.metadata.get("estimator") != self.estimator
            or self.metadata.get("feature_schema") != FEATURE_SCHEMA
            or any(not np.isfinite(v).all() for v in a.values())
        ):
            raise ValueError("Invalid strip model schema or numerical parameters")
        if a["xmean"].ndim != 1 or a["ymean"].ndim != 1:
            raise ValueError("Model normalization vectors must be one-dimensional")
        width, targets = len(a["xmean"]), len(a["ymean"])
        expected = {
            "xmean": (width,),
            "xstd": (width,),
            "ymean": (targets,),
            "ystd": (targets,),
        }
        if self.estimator == "mlp":
            expected.update(w1=(width, 24), b1=(24,), w2=(24, targets), b2=(targets,))
        else:
            expected.update(
                xoffset=(width,), intercept=(targets,), weights=(width, targets)
            )
        if (
            width < 1
            or targets not in (1, 2)
            or any(a[k].shape != shape for k, shape in expected.items())
            or np.any(a["xstd"] <= 0)
            or np.any(a["ystd"] <= 0)
        ):
            raise ValueError("Invalid strip model dimensions or normalization")

    def predict(self, features):
        x = np.asarray(features, dtype=float)
        if (
            x.ndim != 2
            or x.shape[1] != len(self.arrays["xmean"])
            or not np.isfinite(x).all()
        ):
            raise ValueError("Prediction features must match the calibrated model")
        a = self.arrays
        x = (x - a["xmean"]) / a["xstd"]
        if self.estimator != "difference-peak":
            x = np.clip(x, -8, 8)
        if self.estimator == "mlp":
            y = np.tanh(x @ a["w1"] + a["b1"]) @ a["w2"] + a["b2"]
        else:
            y = (x - a["xoffset"]) @ a["weights"] + a["intercept"]
        result = a["ymean"] + a["ystd"] * y
        if not np.isfinite(result).all():
            raise ArithmeticError("Regression produced a nonfinite candidate")
        return result

    def save(self, path):
        self.validate()
        metadata = np.array(json.dumps(self.metadata, allow_nan=False))
        with open(path, "xb") as stream:
            np.savez_compressed(stream, **self.arrays, metadata=metadata)

    @classmethod
    def load(cls, path):
        with np.load(path, allow_pickle=False) as source:
            metadata = json.loads(str(source["metadata"]))
            arrays = {key: source[key] for key in source.files if key != "metadata"}
        model = cls(metadata["estimator"], arrays, metadata)
        model.validate()
        return model
