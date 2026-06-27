"""toyMIP-like carrier sources for algorithm tests."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

IONIZATION_ENERGY_EV = {
    "Si": 3.6,
    "SiC": 8.4,
}

TOY_MIP_PAIRS_PER_UM = {
    "Si": 80.0,
    "SiC": 80.0,
}


@dataclass(frozen=True)
class ToyMIPLineSource:
    """A straight toyMIP track represented as weighted carrier packets."""

    track_position: list[list[float]]
    ionized_pairs: list[float]
    energy_deposition_mev: list[float]
    energy_loss_ev: float
    pairs_per_um: float

    @classmethod
    def through_sensor(
        cls,
        sensor,
        *,
        packets: int = 32,
        energy_deposition_mev_per_um: float | None = None,
        pairs_per_um: float | None = None,
        time: float = 0.0,
        start: tuple[float, float, float] | None = None,
        end: tuple[float, float, float] | None = None,
    ):
        if packets <= 0:
            raise ValueError("packets must be positive")
        if energy_deposition_mev_per_um is not None and pairs_per_um is not None:
            raise ValueError("use energy_deposition_mev_per_um or pairs_per_um, not both")

        material = getattr(sensor, "material", "Si")
        if material not in IONIZATION_ENERGY_EV:
            raise ValueError(f"unsupported toyMIP material: {material}")
        energy_loss_ev = IONIZATION_ENERGY_EV[material]
        if pairs_per_um is None and energy_deposition_mev_per_um is None:
            pairs_per_um = TOY_MIP_PAIRS_PER_UM[material]
        if pairs_per_um is not None:
            if pairs_per_um < 0:
                raise ValueError("pairs_per_um must be non-negative")
            energy_deposition_mev_per_um = pairs_per_um * energy_loss_ev * 1e-6
        elif energy_deposition_mev_per_um < 0:
            raise ValueError("energy_deposition_mev_per_um must be non-negative")
        else:
            pairs_per_um = energy_deposition_mev_per_um * 1e6 / energy_loss_ev

        if start is None:
            start = (float(sensor.l_x) / 2.0, float(sensor.l_y) / 2.0, 0.0)
        if end is None:
            end = (float(sensor.l_x) / 2.0, float(sensor.l_y) / 2.0, float(sensor.l_z))

        start_array = np.asarray(start, dtype=np.float64)
        end_array = np.asarray(end, dtype=np.float64)
        length_um = float(np.linalg.norm(end_array - start_array))
        if not math.isfinite(length_um) or length_um <= 0:
            raise ValueError("toyMIP track length must be positive")

        if packets == 1:
            points = np.array([(start_array + end_array) / 2.0])
        else:
            fractions = (np.arange(packets, dtype=np.float64) + 0.5) / packets
            points = start_array + fractions[:, None] * (end_array - start_array)

        energy_deposition_per_packet = energy_deposition_mev_per_um * length_um / packets
        pairs_per_packet = energy_deposition_per_packet * 1e6 / energy_loss_ev
        track_position = [[float(x), float(y), float(z), float(time)] for x, y, z in points]
        energy_deposition_mev = [float(energy_deposition_per_packet)] * packets
        ionized_pairs = [float(pairs_per_packet)] * packets
        return cls(
            track_position=track_position,
            ionized_pairs=ionized_pairs,
            energy_deposition_mev=energy_deposition_mev,
            energy_loss_ev=float(energy_loss_ev),
            pairs_per_um=float(pairs_per_um),
        )
