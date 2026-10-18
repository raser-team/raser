"""Rigid strip placements and straight-track crossings; lengths in micrometres."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Sequence


Vector3 = tuple[float, float, float]
LIGHT_SPEED_UM_PER_S = 299_792_458_000_000.0


def _vector(values: Sequence[float]) -> Vector3:
    if len(values) != 3 or not all(math.isfinite(float(x)) for x in values):
        raise ValueError("Coordinates require three finite values in um")
    return float(values[0]), float(values[1]), float(values[2])


@dataclass(frozen=True)
class StraightTrack:
    """Forward track at a reference z, with slopes dx/dz and dy/dz."""

    reference_um: Vector3 = (0.0, 0.0, 0.0)
    slope_x: float = 0.0
    slope_y: float = 0.0
    reference_time_s: float = 0.0
    beta: float = 1.0

    def __post_init__(self) -> None:
        _vector(self.reference_um)
        if not all(
            math.isfinite(value)
            for value in (self.slope_x, self.slope_y, self.reference_time_s, self.beta)
        ):
            raise ValueError("Track parameters must be finite")
        if not 0.0 < self.beta <= 1.0:
            raise ValueError("Track beta must be in (0, 1]")

    def at_z(self, z_um: float) -> Vector3:
        dz = z_um - self.reference_um[2]
        return (
            self.reference_um[0] + self.slope_x * dz,
            self.reference_um[1] + self.slope_y * dz,
            z_um,
        )

    def time_at_z(self, z_um: float) -> float:
        distance = (z_um - self.reference_um[2]) * math.sqrt(
            1.0 + self.slope_x**2 + self.slope_y**2
        )
        return self.reference_time_s + distance / (self.beta * LIGHT_SPEED_UM_PER_S)


@dataclass(frozen=True)
class Crossing:
    entry_local_um: Vector3
    exit_local_um: Vector3
    entry_global_um: Vector3
    exit_global_um: Vector3
    entry_time_s: float
    exit_time_s: float
    path_length_um: float

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class StripPlacement:
    """Local x crosses strips, local y follows strips, local z is depth."""

    name: str
    dimensions_um: Vector3
    center_um: Vector3
    rotation_z_deg: float

    def __post_init__(self) -> None:
        if not self.name or any(x in self.name for x in ("/", "\\")):
            raise ValueError("Layer name must be a nonempty path component")
        _vector(self.center_um)
        if any(x <= 0 for x in _vector(self.dimensions_um)):
            raise ValueError("Sensor dimensions must be positive")
        if not math.isfinite(self.rotation_z_deg):
            raise ValueError("Layer rotation must be finite")

    @property
    def readout_axis(self) -> tuple[float, float]:
        angle = math.radians(self.rotation_z_deg)
        return math.cos(angle), math.sin(angle)

    def to_global(self, local_um: Sequence[float]) -> Vector3:
        local = _vector(local_um)
        x, y, z = tuple(a - length / 2 for a, length in zip(local, self.dimensions_um))
        c, s = self.readout_axis
        return (
            c * x - s * y + self.center_um[0],
            s * x + c * y + self.center_um[1],
            z + self.center_um[2],
        )

    def to_local(self, global_um: Sequence[float]) -> Vector3:
        point = _vector(global_um)
        x, y, z = tuple(a - center for a, center in zip(point, self.center_um))
        c, s = self.readout_axis
        return (
            c * x + s * y + self.dimensions_um[0] / 2,
            -s * x + c * y + self.dimensions_um[1] / 2,
            z + self.dimensions_um[2] / 2,
        )

    def projected_slope(self, track: StraightTrack) -> float:
        c, s = self.readout_axis
        return c * track.slope_x + s * track.slope_y

    def crossing(self, track: StraightTrack) -> Crossing | None:
        origin = self.to_local(track.reference_um)
        c, s = self.readout_axis
        direction = (
            c * track.slope_x + s * track.slope_y,
            -s * track.slope_x + c * track.slope_y,
            1.0,
        )
        lower, upper = -math.inf, math.inf
        for position, slope, length in zip(origin, direction, self.dimensions_um):
            if slope == 0.0:
                if position < 0.0 or position > length:
                    return None
                continue
            first, last = sorted((-position / slope, (length - position) / slope))
            lower, upper = max(lower, first), min(upper, last)
        if upper <= lower:
            return None
        entry = track.at_z(track.reference_um[2] + lower)
        exit_point = track.at_z(track.reference_um[2] + upper)

        def bounded_local(point: Vector3) -> Vector3:
            local = self.to_local(point)
            if any(
                x < -1e-8 or x > length + 1e-8
                for x, length in zip(local, self.dimensions_um)
            ):
                raise ArithmeticError("Ray-box crossing escaped the sensor")
            # Remove only floating-point roundoff at an analytically intersected face.
            return _vector(
                tuple(
                    min(length, max(0.0, x))
                    for x, length in zip(local, self.dimensions_um)
                )
            )

        return Crossing(
            bounded_local(entry),
            bounded_local(exit_point),
            entry,
            exit_point,
            track.time_at_z(entry[2]),
            track.time_at_z(exit_point[2]),
            (upper - lower) * math.sqrt(1 + track.slope_x**2 + track.slope_y**2),
        )

    def as_dict(self) -> dict:
        return {**asdict(self), "readout_axis_global_xy": self.readout_axis}


def stereo_pair(
    dimensions_um: Vector3, *, stereo_angle_deg: float, gap_um: float
) -> tuple[StripPlacement, StripPlacement]:
    """Two parallel silicon slabs rotated symmetrically about their normals."""
    if not math.isfinite(gap_um) or gap_um < 0:
        raise ValueError("Silicon-to-silicon gap must be finite and non-negative")
    if not math.isfinite(stereo_angle_deg) or not 0 < stereo_angle_deg < 180:
        raise ValueError("Stereo angle must be strictly between 0 and 180 degrees")
    separation = float(dimensions_um[2]) + gap_um
    return (
        StripPlacement(
            "U", dimensions_um, (0.0, 0.0, -separation / 2), -stereo_angle_deg / 2
        ),
        StripPlacement(
            "V", dimensions_um, (0.0, 0.0, separation / 2), stereo_angle_deg / 2
        ),
    )


def combine_projected_slopes(
    projected_slopes: Sequence[float], rotations_deg: Sequence[float]
) -> dict[str, float | None]:
    """Convert two measured projected slopes to global slopes and angles."""
    if len(projected_slopes) != 2 or len(rotations_deg) != 2:
        raise ValueError("Two projected slopes and two rotations are required")
    if not all(math.isfinite(x) for x in (*projected_slopes, *rotations_deg)):
        raise ValueError("Projection inputs must be finite")
    a, b = map(math.radians, rotations_deg)
    determinant = math.sin(b - a)
    if abs(determinant) < 1e-12:
        raise ValueError("Parallel readout axes cannot determine two slopes")
    q_u, q_v = projected_slopes
    slope_x = (q_u * math.sin(b) - q_v * math.sin(a)) / determinant
    slope_y = (-q_u * math.cos(b) + q_v * math.cos(a)) / determinant
    radius = math.hypot(slope_x, slope_y)
    half_sine, half_cosine = abs(math.sin((b - a) / 2)), abs(math.cos((b - a) / 2))
    condition = max(half_sine, half_cosine) / min(half_sine, half_cosine)
    return {
        "slope_x": slope_x,
        "slope_y": slope_y,
        "theta_deg": math.degrees(math.atan(radius)),
        "phi_deg": math.degrees(math.atan2(slope_y, slope_x)) if radius > 0 else None,
        "projection_condition_number": condition,
    }
