"""Interpolation and potential-gradient calculations for Field data."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

import numpy as np
from scipy.interpolate import RegularGridInterpolator
from scipy.interpolate import griddata
from scipy.interpolate import interp1d
from scipy.spatial import cKDTree


def interpolate_1d(data: Mapping[str, Any]):
    return interp1d(data["points"], data["values"])


def interpolate_2d(data: Mapping[str, Any]):
    points = np.asarray(data["points"], dtype=np.float64)
    values = np.asarray(data["values"], dtype=np.float64)
    return lambda x, y: float(griddata(points, values, (x, y), method="linear"))


def _interpolation_bins_3d(
    bins: Mapping[str, int] | None,
) -> tuple[int, int, int]:
    values = {"x": 30, "y": 30, "z": 30}
    if bins is not None:
        unknown = set(bins) - set(values)
        if unknown:
            raise ValueError(
                f"Unknown interpolation axes: {', '.join(sorted(unknown))}"
            )
        values.update({axis: int(count) for axis, count in bins.items()})
    if any(count < 2 for count in values.values()):
        raise ValueError("3D interpolation requires at least two bins per axis")
    return values["x"], values["y"], values["z"]


def _idw_grid_3d(
    points: np.ndarray,
    values: np.ndarray,
    axes: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> np.ndarray:
    mesh = np.meshgrid(*axes, indexing="ij")
    queries = np.column_stack([coordinate.ravel() for coordinate in mesh])
    neighbors = min(8, len(points))
    distances, indices = cKDTree(points).query(queries, k=neighbors)
    distances = np.asarray(distances, dtype=np.float64)
    indices = np.asarray(indices)
    if distances.ndim == 1:
        distances = distances[:, np.newaxis]
        indices = indices[:, np.newaxis]
    weights = 1.0 / np.square(np.maximum(distances, 1.0e-15))
    interpolated = np.sum(weights * values[indices], axis=1) / np.sum(weights, axis=1)
    exact = distances[:, 0] <= 1.0e-15
    interpolated[exact] = values[indices[exact, 0]]
    return interpolated.reshape(tuple(len(axis) for axis in axes))


def interpolate_3d(
    data: Mapping[str, Any],
    *,
    bins: Mapping[str, int] | None = None,
):
    points = np.asarray(data["points"], dtype=np.float64)
    values = np.asarray(data["values"], dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError("3D interpolation points must have shape N x 3")
    if values.ndim != 1 or len(values) != len(points):
        raise ValueError("3D interpolation values must match the point count")
    if (
        len(points) < 2
        or not np.all(np.isfinite(points))
        or not np.all(np.isfinite(values))
    ):
        raise ValueError("3D interpolation requires finite points and values")
    if np.all(values == values[0]):
        constant = float(values[0])
        return lambda x, y, z: constant
    axes = tuple(np.unique(points[:, axis]) for axis in range(3))
    expected = np.prod([len(axis) for axis in axes])
    if len(points) == expected and len(np.unique(points, axis=0)) == len(points):
        indices = tuple(
            np.searchsorted(axes[axis], points[:, axis]) for axis in range(3)
        )
        grid = np.empty(tuple(len(axis) for axis in axes), dtype=np.float64)
        grid[indices] = values
    else:
        counts = _interpolation_bins_3d(bins)
        axes = tuple(
            np.linspace(np.min(points[:, axis]), np.max(points[:, axis]), counts[axis])
            for axis in range(3)
        )
        if any(axis_values[0] == axis_values[-1] for axis_values in axes):
            raise ValueError("3D interpolation point cloud must span every axis")
        grid = _idw_grid_3d(points, values, axes)
    interpolator = RegularGridInterpolator(
        axes,
        grid,
        method="linear",
        bounds_error=True,
    )
    return lambda x, y, z: float(interpolator((x, y, z)))


def calculate_gradient(
    function: Callable[..., float],
    coordinates: Sequence[float],
    *,
    step: float = 1.0e-5,
) -> tuple[float, ...]:
    if step <= 0:
        raise ValueError("Gradient step must be positive")
    point = tuple(map(float, coordinates))
    gradient = []
    for axis in range(len(point)):
        upper = list(point)
        lower = list(point)
        upper[axis] += step / 2.0
        lower[axis] -= step / 2.0
        gradient.append((float(function(*upper)) - float(function(*lower))) / step)
    return tuple(gradient)
