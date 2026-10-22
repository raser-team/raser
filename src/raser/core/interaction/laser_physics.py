"""Laser energy-deposition expressions."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike
from numpy.typing import NDArray


PLANCK_CONSTANT_J_S = 6.626e-34
SPEED_OF_LIGHT_M_PER_S = 2.998e8


def gaussian_square_integral(temporal_fwhm_s: float) -> float:
    """Return the integral factor for a unit-area Gaussian pulse squared."""
    if temporal_fwhm_s <= 0.0:
        raise ValueError("Laser temporal FWHM must be positive")
    return math.sqrt(2.0 * math.log(2.0)) / (math.sqrt(math.pi) * temporal_fwhm_s)


def tpa_carrier_density(
    *,
    beta_2: float,
    wavelength_um: float,
    pulse_fluence_W_s_per_m2: ArrayLike,
    temporal_fwhm_s: float,
) -> float | NDArray[np.float64]:
    """Calculate two-photon carrier density from pulse fluence."""
    pulse_fluence = np.asarray(pulse_fluence_W_s_per_m2, dtype=float)
    if beta_2 < 0.0 or wavelength_um <= 0.0 or np.any(pulse_fluence < 0.0):
        raise ValueError(
            "TPA inputs require positive wavelength and non-negative values"
        )
    density = (
        beta_2
        * wavelength_um
        * 1.0e-6
        * pulse_fluence**2
        * gaussian_square_integral(temporal_fwhm_s)
        / (2.0 * PLANCK_CONSTANT_J_S * SPEED_OF_LIGHT_M_PER_S)
    )
    return float(density) if density.ndim == 0 else density
