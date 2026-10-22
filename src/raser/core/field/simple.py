"""Analytic 1D field models for controlled algorithm tests."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
import math

import numpy as np


ELEMENTARY_CHARGE_C = 1.602176634e-19
EPSILON_0_F_PER_M = 8.8541878128e-12
DEFAULT_RELATIVE_PERMITTIVITY = 11.7


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


@dataclass(frozen=True)
class AnalyticPlanarField:
    """Planar weighting potential paired with a one-dimensional drift field."""

    thickness_um: float
    bias_voltage: float
    depletion_voltage: float
    sensor_x_um: float | None = None
    sensor_y_um: float | None = None
    doping_cm3: float = 1.0e12
    deplete_from_implants: bool = True
    _drift_field: LinearDepletionField1D = field(init=False, repr=False)

    def __post_init__(self):
        object.__setattr__(
            self,
            "_drift_field",
            LinearDepletionField1D(
                self.thickness_um,
                self.bias_voltage,
                self.depletion_voltage,
                self.doping_cm3,
                self.deplete_from_implants,
            ),
        )

    @property
    def drift_field(self):
        return self._drift_field

    def get_e_field_cached(self, x, y, z):
        z_clamped = min(float(self.thickness_um), max(0.0, float(z)))
        return 0.0, 0.0, float(self.drift_field.get_e_field_z_many([z_clamped])[0])

    def get_doping_cached(self, x, y, z):
        return float(self.doping_cm3)

    def get_w_p_cached(self, x, y, z, electrode_idx):
        if not self._inside_xy(x, y):
            raise ValueError(f"position outside analytic field bounds: {(x, y, z)}")
        z_clamped = min(float(self.thickness_um), max(0.0, float(z)))
        return z_clamped / float(self.thickness_um)

    def get_trap_h_cached(self, x, y, z):
        return 0.0

    def get_trap_e_cached(self, x, y, z):
        return 0.0

    def get_cache_stats(self):
        return {"hits": 0, "misses": 0, "errors": 0, "fallbacks": 0, "hit_rate": 0.0}

    def _inside_xy(self, x, y):
        if self.sensor_x_um is not None and not 0.0 <= float(x) <= self.sensor_x_um:
            return False
        if self.sensor_y_um is not None and not 0.0 <= float(y) <= self.sensor_y_um:
            return False
        return True


@dataclass(frozen=True)
class AnalyticStripPixelField:
    """Rectangular-electrode weighting potential with a 1D drift field."""

    thickness_um: float
    bias_voltage: float
    depletion_voltage: float
    pitch_x_um: float
    pitch_y_um: float | None = None
    sensor_x_um: float | None = None
    sensor_y_um: float | None = None
    dimension: int = 2
    doping_cm3: float = 1.0e12
    deplete_from_implants: bool = True
    central_electrode: bool = True
    weighting_series_terms: int = 100
    _drift_field: LinearDepletionField1D = field(init=False, repr=False)

    def __post_init__(self):
        if self.dimension not in (2, 3):
            raise ValueError("dimension must be 2 for strips or 3 for pixels")
        if self.pitch_x_um <= 0:
            raise ValueError("pitch_x_um must be positive")
        if self.dimension == 3 and (self.pitch_y_um is None or self.pitch_y_um <= 0):
            raise ValueError("pitch_y_um must be positive for pixel weighting fields")
        if self.sensor_x_um is not None and self.sensor_x_um <= 0:
            raise ValueError("sensor_x_um must be positive")
        if self.sensor_y_um is not None and self.sensor_y_um <= 0:
            raise ValueError("sensor_y_um must be positive")
        if self.weighting_series_terms < 1:
            raise ValueError("weighting_series_terms must be positive")
        object.__setattr__(
            self,
            "_drift_field",
            LinearDepletionField1D(
                self.thickness_um,
                self.bias_voltage,
                self.depletion_voltage,
                self.doping_cm3,
                self.deplete_from_implants,
            ),
        )

    @property
    def drift_field(self):
        return self._drift_field

    def get_e_field_cached(self, x, y, z):
        z_clamped = min(float(self.thickness_um), max(0.0, float(z)))
        return 0.0, 0.0, float(self.drift_field.get_e_field_z_many([z_clamped])[0])

    def get_doping_cached(self, x, y, z):
        return float(self.doping_cm3)

    def get_w_p_cached(self, x, y, z, electrode_idx):
        x_local = float(x) - self._electrode_center_x(electrode_idx)
        y_local = float(y) - self._electrode_center_y(electrode_idx)
        z_clamped = min(float(self.thickness_um), max(0.0, float(z)))
        z_from_implant = float(self.thickness_um) - z_clamped
        potential = self._pad_weighting_potential(x_local, y_local, z_from_implant)
        return float(min(1.0, max(0.0, potential)))

    def get_trap_h_cached(self, x, y, z):
        return 0.0

    def get_trap_e_cached(self, x, y, z):
        return 0.0

    def get_cache_stats(self):
        return {"hits": 0, "misses": 0, "errors": 0, "fallbacks": 0, "hit_rate": 0.0}

    def _pad_weighting_potential(self, x, y, z):
        thickness = float(self.thickness_um)
        value = self._pad_f(x, y, z)
        for n in range(1, self.weighting_series_terms + 1):
            mirror = 2.0 * n * thickness
            value -= self._pad_f(x, y, mirror - z) - self._pad_f(x, y, mirror + z)
        return value / (2.0 * math.pi)

    def _pad_f(self, x, y, u):
        half_x = 0.5 * float(self.pitch_x_um)
        half_y = 0.5 * self._electrode_size_y()
        x1, x2 = float(x) + half_x, float(x) - half_x
        y1, y2 = float(y) + half_y, float(y) - half_y
        return (
            self._pad_angle(x1, y1, u)
            + self._pad_angle(x2, y2, u)
            - self._pad_angle(x1, y2, u)
            - self._pad_angle(x2, y1, u)
        )

    @staticmethod
    def _pad_angle(x, y, u):
        radius = math.sqrt(x * x + y * y + u * u)
        return math.atan2(x * y, u * radius)

    def _electrode_size_y(self):
        if self.dimension == 3:
            if self.pitch_y_um is None:
                raise ValueError("pitch_y_um is required for pixel weighting fields")
            return float(self.pitch_y_um)
        if self.sensor_y_um is not None:
            return float(self.sensor_y_um)
        if self.pitch_y_um is not None:
            return float(self.pitch_y_um)
        return float(self.pitch_x_um)

    def _electrode_center_x(self, electrode_idx):
        if self.sensor_x_um is None:
            return 0.5 * float(self.pitch_x_um)
        if self.central_electrode:
            return 0.5 * float(self.sensor_x_um)
        columns = max(1, round(float(self.sensor_x_um) / float(self.pitch_x_um)))
        return (int(electrode_idx) % columns + 0.5) * float(self.pitch_x_um)

    def _electrode_center_y(self, electrode_idx):
        if self.dimension == 2:
            return 0.0 if self.sensor_y_um is None else 0.5 * float(self.sensor_y_um)
        if self.sensor_y_um is None:
            return 0.0
        if self.central_electrode:
            return 0.5 * float(self.sensor_y_um)
        if self.pitch_y_um is None:
            raise ValueError("pitch_y_um is required for pixel weighting fields")
        columns = max(
            1,
            round(float(self.sensor_x_um or self.pitch_x_um) / float(self.pitch_x_um)),
        )
        return (int(electrode_idx) // columns + 0.5) * float(self.pitch_y_um)


@dataclass(frozen=True)
class _RectangularSeries2D:
    width_um: float
    height_um: float
    terms: int

    def __post_init__(self):
        if self.width_um <= 0 or self.height_um <= 0:
            raise ValueError("series dimensions must be positive")
        if self.terms < 1:
            raise ValueError("series terms must be positive")

    def poisson_unit(self, x, y):
        value = 0.0
        gradient_x = 0.0
        gradient_y = 0.0
        for m in range(1, self.terms + 1, 2):
            kx = m * math.pi / float(self.width_um)
            sin_x = math.sin(kx * x)
            cos_x = math.cos(kx * x)
            for n in range(1, self.terms + 1, 2):
                ky = n * math.pi / float(self.height_um)
                sin_y = math.sin(ky * y)
                cos_y = math.cos(ky * y)
                coefficient = 16.0 / (math.pi * math.pi * m * n)
                amplitude = coefficient / (kx * kx + ky * ky)
                value += amplitude * sin_x * sin_y
                gradient_x += amplitude * kx * cos_x * sin_y
                gradient_y += amplitude * ky * sin_x * cos_y
        return value, gradient_x, gradient_y

    def source_modes(self, sources):
        if not sources:
            raise ValueError("source_modes requires at least one source")
        scale = 4.0 / (float(self.width_um) * float(self.height_um))
        modes = []
        for m in range(1, self.terms + 1):
            kx = m * math.pi / float(self.width_um)
            for n in range(1, self.terms + 1):
                ky = n * math.pi / float(self.height_um)
                source_factor = sum(
                    math.sin(kx * source_x) * math.sin(ky * source_y)
                    for source_x, source_y in sources
                ) / len(sources)
                modes.append((kx, ky, scale * source_factor / (kx * kx + ky * ky)))
        return tuple(modes)

    @staticmethod
    def evaluate_modes(x, y, modes):
        value = 0.0
        gradient_x = 0.0
        gradient_y = 0.0
        for kx, ky, amplitude in modes:
            sin_x = math.sin(kx * x)
            cos_x = math.cos(kx * x)
            sin_y = math.sin(ky * y)
            cos_y = math.cos(ky * y)
            value += amplitude * sin_x * sin_y
            gradient_x += amplitude * kx * cos_x * sin_y
            gradient_y += amplitude * ky * sin_x * cos_y
        return value, gradient_x, gradient_y


@dataclass(frozen=True)
class AnalyticColumn3DField:
    """Column-detector approximation from a rectangular Fourier series."""

    thickness_um: float
    bias_voltage: float
    cell_x_um: float
    cell_y_um: float
    column_radius_um: float
    sensor_x_um: float | None = None
    sensor_y_um: float | None = None
    doping_cm3: float = 1.0e12
    relative_permittivity: float = DEFAULT_RELATIVE_PERMITTIVITY
    readout_column_x_um: float | None = None
    readout_column_y_um: float | None = None
    ground_columns_um: tuple[tuple[float, float], ...] | None = None
    series_terms: int = 51
    central_electrode: bool = True
    _series: _RectangularSeries2D = field(init=False, repr=False)
    _poisson_readout_scale: float = field(init=False, repr=False)
    _green_norm: float = field(init=False, repr=False)
    _readout_modes: tuple[tuple[float, float, float], ...] = field(
        init=False, repr=False
    )

    def __post_init__(self):
        if self.thickness_um <= 0:
            raise ValueError("thickness_um must be positive")
        if self.cell_x_um <= 0 or self.cell_y_um <= 0:
            raise ValueError("column cell dimensions must be positive")
        if self.column_radius_um <= 0:
            raise ValueError("column_radius_um must be positive")
        if self.column_radius_um >= 0.25 * min(self.cell_x_um, self.cell_y_um):
            raise ValueError("column_radius_um must be smaller than half pitch")
        if self.relative_permittivity <= 0 or self.series_terms < 1:
            raise ValueError("permittivity and series terms must be positive")

        series = _RectangularSeries2D(self.cell_x_um, self.cell_y_um, self.series_terms)
        readout_x = self._configured_readout_x()
        readout_y = self._configured_readout_y()
        self._validate_readout_position(readout_x, readout_y)
        for ground_x, ground_y in self._configured_ground_columns():
            if not 0.0 <= ground_x <= self.cell_x_um:
                raise ValueError("ground column x position is outside the cell")
            if not 0.0 <= ground_y <= self.cell_y_um:
                raise ValueError("ground column y position is outside the cell")

        readout_modes = series.source_modes(self._readout_source_points())
        surface = readout_x + float(self.column_radius_um), readout_y
        green_norm = series.evaluate_modes(surface[0], surface[1], readout_modes)[0]
        if green_norm <= 0.0:
            raise ValueError("column series normalization failed")
        poisson_surface = series.poisson_unit(*surface)[0]
        object.__setattr__(self, "_series", series)
        object.__setattr__(self, "_poisson_readout_scale", poisson_surface / green_norm)
        object.__setattr__(self, "_green_norm", green_norm)
        object.__setattr__(self, "_readout_modes", readout_modes)

    def get_e_field_cached(self, x, y, z):
        local_x, local_y = self._local_cell_xy(x, y, 0)
        _, weighting_x, weighting_y = self._weighting(local_x, local_y)
        _, poisson_x, poisson_y = self._poisson(local_x, local_y)
        poisson_scale = self._poisson_voltage_scale()
        return (
            (float(self.bias_voltage) * weighting_x - poisson_scale * poisson_x) * 1e4,
            (float(self.bias_voltage) * weighting_y - poisson_scale * poisson_y) * 1e4,
            0.0,
        )

    def get_potential_cached(self, x, y, z):
        local_x, local_y = self._local_cell_xy(x, y, 0)
        return (
            -float(self.bias_voltage) * self._weighting(local_x, local_y)[0]
            + self._poisson_voltage_scale() * self._poisson(local_x, local_y)[0]
        )

    def get_doping_cached(self, x, y, z):
        return float(self.doping_cm3)

    def get_w_p_cached(self, x, y, z, electrode_idx):
        local_x, local_y = self._local_cell_xy(x, y, electrode_idx)
        radius = math.hypot(
            local_x - self._configured_readout_x(),
            local_y - self._configured_readout_y(),
        )
        if radius <= float(self.column_radius_um):
            return 1.0
        if self._inside_ground_column(local_x, local_y):
            return 0.0
        return float(min(1.0, max(0.0, self._weighting(local_x, local_y)[0])))

    def get_trap_h_cached(self, x, y, z):
        return 0.0

    def get_trap_e_cached(self, x, y, z):
        return 0.0

    def get_cache_stats(self):
        return {"hits": 0, "misses": 0, "errors": 0, "fallbacks": 0, "hit_rate": 0.0}

    def _local_cell_xy(self, x, y, electrode_idx):
        local_x = float(x) - self._electrode_center_x(electrode_idx)
        local_x += self._configured_readout_x()
        local_y = float(y) - self._electrode_center_y(electrode_idx)
        local_y += self._configured_readout_y()
        return (
            min(float(self.cell_x_um), max(0.0, local_x)),
            min(float(self.cell_y_um), max(0.0, local_y)),
        )

    def _electrode_center_x(self, electrode_idx):
        if self.sensor_x_um is None or self.central_electrode:
            return 0.5 * float(self.sensor_x_um or self.cell_x_um)
        columns = max(1, round(float(self.sensor_x_um) / float(self.cell_x_um)))
        return (
            int(electrode_idx) % columns * float(self.cell_x_um)
            + self._configured_readout_x()
        )

    def _electrode_center_y(self, electrode_idx):
        if self.sensor_y_um is None or self.central_electrode:
            return 0.5 * float(self.sensor_y_um or self.cell_y_um)
        columns = max(
            1,
            round(float(self.sensor_x_um or self.cell_x_um) / float(self.cell_x_um)),
        )
        return (
            int(electrode_idx) // columns * float(self.cell_y_um)
            + self._configured_readout_y()
        )

    def _weighting(self, x, y):
        value = self._series.evaluate_modes(x, y, self._readout_modes)
        return tuple(component / self._green_norm for component in value)

    def _poisson(self, x, y):
        poisson = self._series.poisson_unit(x, y)
        readout = self._series.evaluate_modes(x, y, self._readout_modes)
        return tuple(
            base - self._poisson_readout_scale * correction
            for base, correction in zip(poisson, readout)
        )

    def _configured_readout_x(self):
        return (
            float(self.readout_column_x_um)
            if self.readout_column_x_um is not None
            else 0.5 * float(self.cell_x_um)
        )

    def _configured_readout_y(self):
        return (
            float(self.readout_column_y_um)
            if self.readout_column_y_um is not None
            else 0.5 * float(self.cell_y_um)
        )

    def _configured_ground_columns(self):
        if self.ground_columns_um is not None:
            return tuple((float(x), float(y)) for x, y in self.ground_columns_um)
        return (
            (0.0, 0.0),
            (0.0, float(self.cell_y_um)),
            (float(self.cell_x_um), 0.0),
            (float(self.cell_x_um), float(self.cell_y_um)),
        )

    def _validate_readout_position(self, x, y):
        radius = float(self.column_radius_um)
        if not radius < x < float(self.cell_x_um) - radius:
            raise ValueError("readout column x position is outside the cell")
        if not radius < y < float(self.cell_y_um) - radius:
            raise ValueError("readout column y position is outside the cell")

    def _inside_ground_column(self, x, y):
        return any(
            math.hypot(float(x) - ground_x, float(y) - ground_y)
            <= float(self.column_radius_um)
            for ground_x, ground_y in self._configured_ground_columns()
        )

    def _poisson_voltage_scale(self):
        charge_density = ELEMENTARY_CHARGE_C * float(self.doping_cm3) * 1.0e6
        return (
            charge_density
            / (EPSILON_0_F_PER_M * float(self.relative_permittivity))
            * 1.0e-12
        )

    def _readout_source_points(self):
        center_x = self._configured_readout_x()
        center_y = self._configured_readout_y()
        points = [(center_x, center_y)]
        for radius_fraction, count in ((0.35, 8), (0.65, 16), (0.9, 24)):
            radius = radius_fraction * float(self.column_radius_um)
            for index in range(count):
                angle = 2.0 * math.pi * index / count
                points.append(
                    (
                        center_x + radius * math.cos(angle),
                        center_y + radius * math.sin(angle),
                    )
                )
        return tuple(points)


def strip_pixel_field_from_detector(detector):
    """Construct an analytic field from a runtime detector."""
    det_model = str(getattr(detector, "det_model", "")).lower()
    depletion_voltage = getattr(detector, "depletion_voltage", None)
    if depletion_voltage is None:
        depletion_voltage = abs(float(detector.voltage))

    if "3d" in det_model:
        if not hasattr(detector, "column_radius_um"):
            raise ValueError("3D analytic column field requires column_radius_um")
        cell_x_um = getattr(detector, "column_cell_x_um", None)
        cell_y_um = getattr(detector, "column_cell_y_um", None)
        return AnalyticColumn3DField(
            thickness_um=float(detector.l_z),
            bias_voltage=float(detector.voltage),
            cell_x_um=float(
                cell_x_um if cell_x_um is not None else 2.0 * detector.p_x
            ),
            cell_y_um=float(
                cell_y_um if cell_y_um is not None else 2.0 * detector.p_y
            ),
            column_radius_um=float(detector.column_radius_um),
            sensor_x_um=float(detector.l_x),
            sensor_y_um=float(detector.l_y),
            doping_cm3=float(getattr(detector, "input_doping", 1.0e12)),
            relative_permittivity=float(
                getattr(
                    detector, "relative_permittivity", DEFAULT_RELATIVE_PERMITTIVITY
                )
            ),
            readout_column_x_um=getattr(detector, "readout_column_x_um", None),
            readout_column_y_um=getattr(detector, "readout_column_y_um", None),
            ground_columns_um=getattr(detector, "ground_columns_um", None),
            series_terms=int(getattr(detector, "weighting_series_terms", 51)),
            central_electrode=len(getattr(detector, "read_out_contact", [])) == 1,
        )

    if "planar" in det_model or det_model == "lgad":
        return AnalyticPlanarField(
            thickness_um=float(detector.l_z),
            bias_voltage=float(detector.voltage),
            depletion_voltage=float(depletion_voltage),
            sensor_x_um=float(detector.l_x),
            sensor_y_um=float(detector.l_y),
            doping_cm3=float(getattr(detector, "input_doping", 1.0e12)),
        )

    if "strip" not in det_model and "pixel" not in det_model:
        raise ValueError("analytic field requires a planar, strip, or pixel detector")
    dimension = 3 if "pixel" in det_model else 2
    return AnalyticStripPixelField(
        thickness_um=float(detector.l_z),
        bias_voltage=float(detector.voltage),
        depletion_voltage=float(depletion_voltage),
        pitch_x_um=float(detector.p_x),
        pitch_y_um=float(detector.p_y) if dimension == 3 else None,
        sensor_x_um=float(detector.l_x),
        sensor_y_um=float(detector.l_y),
        dimension=dimension,
        doping_cm3=float(getattr(detector, "input_doping", 1.0e12)),
        central_electrode=len(getattr(detector, "read_out_contact", [])) == 1,
        weighting_series_terms=int(getattr(detector, "weighting_series_terms", 100)),
    )
