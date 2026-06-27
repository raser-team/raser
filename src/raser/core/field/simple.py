"""Analytic 1D field models for controlled algorithm tests."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class LinearDepletionField1D:
    """Allpix-Squared-style linear depletion field in sensor z coordinates."""

    thickness_um: float
    bias_voltage: float
    depletion_voltage: float
    doping_cm3: float = 1.0e12
    deplete_from_implants: bool = True

    def __post_init__(self):
        if self.thickness_um <= 0:
            raise ValueError("thickness_um must be positive")
        if self.depletion_voltage == 0:
            raise ValueError("depletion_voltage must be non-zero")

    @property
    def effective_thickness_um(self) -> float:
        bias = abs(float(self.bias_voltage))
        depletion = abs(float(self.depletion_voltage))
        if bias < depletion:
            return float(self.thickness_um) * math.sqrt(bias / depletion)
        return float(self.thickness_um)

    def get_e_field_z_many(self, z_values):
        z_values = np.asarray(z_values, dtype=np.float64)
        thickness = float(self.thickness_um)
        effective = self.effective_thickness_um
        bias = abs(float(self.bias_voltage))
        depletion = min(abs(float(self.depletion_voltage)), bias)

        distance = thickness - z_values if self.deplete_from_implants else z_values
        field_v_per_um = np.maximum(
            0.0,
            (bias - depletion) / effective
            + 2.0 * depletion / effective * (1.0 - distance / effective),
        )
        direction = -1.0 if math.copysign(1.0, self.bias_voltage) < 0 else 1.0
        return direction * field_v_per_um * 1e4

    def get_doping_many(self, z_values):
        return np.full_like(np.asarray(z_values, dtype=np.float64), self.doping_cm3)
