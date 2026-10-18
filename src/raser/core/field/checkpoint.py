"""Validate saved DEVSIM states for a continued bias sweep."""

from __future__ import annotations

import math
from pathlib import Path


def require_checkpoint(directory: str | Path, voltage: float, goal: float) -> Path:
    voltage = float(voltage)
    goal = float(goal)
    if not math.isfinite(voltage) or not math.isfinite(goal):
        raise ValueError("Field resume voltages must be finite")
    if voltage * goal < 0 or abs(voltage) >= abs(goal):
        raise ValueError("Field resume bias must precede the goal with the same sign")
    label = "0" if voltage == 0 else str(voltage)
    path = Path(directory) / f"{label}V.devsim"
    if not path.is_file():
        raise FileNotFoundError(f"No field checkpoint for this configuration: {path}")
    return path
