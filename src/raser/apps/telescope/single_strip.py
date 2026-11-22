"""Dispatch the single-layer strip workflow to its selected estimator."""

import json

import numpy as np

from . import joint_strip, strip_regression


def main(kwargs):
    estimator = kwargs.get("estimator", "template")
    if kwargs["joint_action"] in ("predict", "evaluate"):
        with np.load(kwargs["model"], allow_pickle=False) as model:
            schema = json.loads(str(model["metadata"]))["schema"]
        if schema not in ("raser-joint-strip-v1", "raser-strip-regressor-v1"):
            raise ValueError("Unsupported single-layer strip model schema")
        estimator = "template" if schema == "raser-joint-strip-v1" else "regression"
    if estimator == "template":
        if kwargs["joint_action"] == "calibrate" and (
            not kwargs.get("interval_dataset") or not kwargs.get("interval_labels")
        ):
            raise ValueError(
                "Template calibration requires independent interval data and labels"
            )
        return joint_strip.main(kwargs)
    return strip_regression.main(kwargs)
