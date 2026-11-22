"""ADC quantisation and conversion of codes back to bin-centre voltages."""

import numpy as np

from .settings import DigitizerSettings


def quantize(samples, settings: DigitizerSettings):
    """Return clipped ``int16`` codes and one ``int64`` count per electrode."""
    values = np.asarray(samples, dtype=np.float64)
    if values.ndim != 2:
        raise ValueError(
            f"samples has shape {values.shape}, expected (electrodes, bins)"
        )
    raw = np.floor((values - settings.offset_V) / settings.lsb_V).astype(np.int64) + (
        1 << (settings.bits - 1)
    )
    clipped = np.sum(
        (raw < 0) | (raw > (1 << settings.bits) - 1), axis=1, dtype=np.int64
    )
    codes = np.clip(raw, 0, (1 << settings.bits) - 1).astype(np.int16)
    return codes, clipped


def to_volts(codes, bits, lsb_V, offset_V):
    """Convert ADC codes to the midpoint voltage of their quantisation bin."""
    return (np.asarray(codes) - (1 << (int(bits) - 1)) + 0.5) * float(lsb_V) + float(
        offset_V
    )
