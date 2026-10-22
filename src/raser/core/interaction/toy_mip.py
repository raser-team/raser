"""toyMIP-like carrier sources for algorithm tests."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import ROOT

from .energy_loss import sample_fano_pairs
from .energy_loss import sample_landau_energy_loss

IONIZATION_ENERGY_EV = {
    "Si": 3.6,
    "SiC": 8.4,
    "Diamond": 13.1,
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
        landau_sampling: bool = False,
        landau_width_mev_per_um: float | None = None,
        fano_sampling: bool = False,
        fano_factor: float = 0.0,
        rng=None,
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
        else:
            if energy_deposition_mev_per_um is None:
                raise RuntimeError("toyMIP energy-loss resolution failed")
            if energy_deposition_mev_per_um < 0:
                raise ValueError("energy_deposition_mev_per_um must be non-negative")
            pairs_per_um = energy_deposition_mev_per_um * 1e6 / energy_loss_ev
        if energy_deposition_mev_per_um is None or pairs_per_um is None:
            raise RuntimeError("toyMIP energy-loss resolution failed")

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

        mean_energy_deposition_per_packet = (
            energy_deposition_mev_per_um * length_um / packets
        )
        landau_width_per_packet = 0.0
        if landau_sampling:
            if landau_width_mev_per_um is None:
                landau_width_mev_per_um = 0.1 * energy_deposition_mev_per_um
            landau_width_per_packet = landau_width_mev_per_um * length_um / packets
        track_position = [[float(x), float(y), float(z), float(time)] for x, y, z in points]
        energy_deposition_mev = []
        ionized_pairs = []
        for _ in range(packets):
            energy_deposition_per_packet = sample_landau_energy_loss(
                mean_energy_deposition_per_packet,
                landau_width_per_packet,
                rng,
            )
            mean_pairs = energy_deposition_per_packet * 1e6 / energy_loss_ev
            pairs = (
                sample_fano_pairs(mean_pairs, fano_factor, rng)
                if fano_sampling
                else mean_pairs
            )
            energy_deposition_mev.append(float(energy_deposition_per_packet))
            ionized_pairs.append(float(pairs))
        return cls(
            track_position=track_position,
            ionized_pairs=ionized_pairs,
            energy_deposition_mev=energy_deposition_mev,
            energy_loss_ev=float(energy_loss_ev),
            pairs_per_um=float(pairs_per_um),
        )


class ToyMIPInteraction:
    """Toy MIP source with the runtime data exposed by Geant4 Interaction."""

    geant4_model = "toy_mip"

    def __init__(self, sensor, config, seed):
        self.config = dict(config)
        self.total_events = int(self.config.get("total_events", 1))
        self.packets = (
            int(self.config["packets"])
            if "packets" in self.config
            else self._packets_from_step_limit(sensor, self.config)
        )
        self.landau_sampling = bool(self.config.get("landau_sampling", False))
        self.fano_sampling = bool(self.config.get("fano_sampling", False))
        self.fano_factor = float(
            self.config.get("fano_factor", getattr(sensor, "fano_factor", 0.0))
        )
        self.pairs_per_um = self.config.get("pairs_per_um")
        self.energy_deposition_mev_per_um = self.config.get(
            "energy_deposition_mev_per_um"
        )
        self.landau_width_mev_per_um = self.config.get("landau_width_mev_per_um")
        self.start = self.config.get("start")
        self.end = self.config.get("end")
        self.position_range_um = self.config.get("position_range_um")
        self.direction_sigma_mrad = self.config.get("direction_sigma_mrad", 0.0)

        ROOT.gRandom.SetSeed(int(seed))
        self.sources = []
        self.eventIDs = []
        self.edep_devices = []
        self.energy_steps = []
        self.events_angles = []
        self.p_steps = []
        self.p_steps_current = []
        for event in range(self.total_events):
            start, end, angle = self._sample_track(sensor)
            source = ToyMIPLineSource.through_sensor(
                sensor,
                packets=self.packets,
                pairs_per_um=self.pairs_per_um,
                energy_deposition_mev_per_um=self.energy_deposition_mev_per_um,
                landau_sampling=self.landau_sampling,
                landau_width_mev_per_um=self.landau_width_mev_per_um,
                start=start,
                end=end,
                fano_sampling=self.fano_sampling,
                fano_factor=self.fano_factor,
            )
            self.sources.append(source)
            self.eventIDs.append(event)
            self.edep_devices.append(sum(source.energy_deposition_mev))
            self.energy_steps.append(list(source.energy_deposition_mev))
            self.events_angles.append(angle)
            steps = [[point[0], point[1], point[2]] for point in source.track_position]
            self.p_steps.append(steps)
            self.p_steps_current.append(steps)

    def _sample_track(self, sensor):
        start = self.start or [
            float(sensor.l_x) / 2.0,
            float(sensor.l_y) / 2.0,
            0.0,
        ]
        end = self.end or [
            float(sensor.l_x) / 2.0,
            float(sensor.l_y) / 2.0,
            float(sensor.l_z),
        ]
        start = [float(value) for value in start]
        end = [float(value) for value in end]

        if self.position_range_um is not None:
            x_range = self.position_range_um.get("x", [start[0], start[0]])
            y_range = self.position_range_um.get("y", [start[1], start[1]])
            start[0] = float(ROOT.gRandom.Uniform(*map(float, x_range)))
            start[1] = float(ROOT.gRandom.Uniform(*map(float, y_range)))

        sigma_x_mrad, sigma_y_mrad = self._direction_sigmas()
        dz = end[2] - start[2]
        slope_x = (
            float(ROOT.gRandom.Gaus(0.0, sigma_x_mrad * 1.0e-3))
            if sigma_x_mrad > 0.0
            else 0.0
        )
        slope_y = (
            float(ROOT.gRandom.Gaus(0.0, sigma_y_mrad * 1.0e-3))
            if sigma_y_mrad > 0.0
            else 0.0
        )
        if self.position_range_um is not None or slope_x or slope_y:
            end[0] = start[0] + slope_x * dz
            end[1] = start[1] + slope_y * dz
        return start, end, math.atan(math.hypot(slope_x, slope_y))

    def _direction_sigmas(self):
        value = self.direction_sigma_mrad
        if isinstance(value, dict):
            return float(value.get("x", 0.0)), float(value.get("y", 0.0))
        if isinstance(value, (list, tuple)):
            if not value:
                return 0.0, 0.0
            if len(value) == 1:
                return float(value[0]), float(value[0])
            return float(value[0]), float(value[1])
        value = float(value)
        return value, value

    @staticmethod
    def _packets_from_step_limit(sensor, config):
        maxstep = config.get("maxstep")
        if maxstep is None:
            raise ValueError("Toy MIP packets require maxstep when not configured")
        maxstep = float(maxstep)
        if not math.isfinite(maxstep) or maxstep <= 0:
            raise ValueError("maxstep must be positive")
        return max(1, math.ceil(float(sensor.l_z) / maxstep))

    def source(self, batch):
        self.selected_batch_number = int(batch)
        return self.sources[self.selected_batch_number]

    def close(self):
        return None
