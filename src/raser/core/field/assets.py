"""Field asset file naming helpers."""

from __future__ import annotations

import math
import re
from pathlib import Path


def voltage_label(voltage):
    value = float(voltage)
    if math.isfinite(value) and value.is_integer():
        return str(int(value))
    return format(value, ".12g")


def field_pickle_name(prefix, voltage):
    return f"{prefix}_{voltage_label(voltage)}V.pkl"


def field_pickle_path(directory, prefix, voltage):
    return Path(directory) / field_pickle_name(prefix, voltage)


def resolve_field_pickle(directory, prefix, voltage):
    path = Path(directory)
    exact_path = field_pickle_path(path, prefix, voltage)
    if exact_path.exists():
        return exact_path

    try:
        target_voltage = float(voltage)
    except (TypeError, ValueError):
        return exact_path

    pattern = re.compile(rf"^{re.escape(prefix)}_(-?\d+(?:\.\d+)?)V\.pkl$")
    for candidate in path.iterdir():
        match = pattern.match(candidate.name)
        if match and math.isclose(
            float(match.group(1)),
            target_voltage,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            return candidate
    return exact_path
