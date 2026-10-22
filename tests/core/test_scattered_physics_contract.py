from __future__ import annotations

import pickle
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from raser.core.field.interpolation import interpolate_3d
from raser.core.field.devsim_field import DevsimField
from raser.core.field.physics_avalanche import CreateImpactModel_vanOvenstraeten
from raser.core.field.solver_section import _resolve_impact_model
from raser.core.field.solver_section import _voltage_milestones
from raser.core.interaction.laser_physics import gaussian_square_integral
from raser.core.interaction.laser_physics import tpa_carrier_density


def test_van_overstraeten_has_zero_ionization_below_its_field_threshold() -> None:
    electron, hole = CreateImpactModel_vanOvenstraeten("device", "region")

    assert "abs(ElectricField)>1.75e5" in electron
    assert "abs(ElectricField)>1.75e5" in hole
    assert electron.endswith(", 0)")
    assert hole.endswith(", 0)")


def test_field_solver_uses_enabled_avalanche_and_includes_final_bias() -> None:
    disabled = SimpleNamespace(has_avalanche=False, avalanche_model="vanOverstraeten")
    enabled = SimpleNamespace(has_avalanche=True, avalanche_model="vanOverstraeten")

    assert _resolve_impact_model(disabled) is None
    assert _resolve_impact_model(enabled) == "vanOverstraeten"
    assert _voltage_milestones(350.0, 100.0) == [100.0, 200.0, 300.0, 350.0]
    assert _voltage_milestones(-250.0, 100.0) == [-100.0, -200.0, -250.0]


def test_tpa_density_contains_the_gaussian_square_integral() -> None:
    first = tpa_carrier_density(
        beta_2=1.5e-11,
        wavelength_um=1.55,
        pulse_fluence_W_s_per_m2=2.0,
        temporal_fwhm_s=600.0e-15,
    )
    second = tpa_carrier_density(
        beta_2=1.5e-11,
        wavelength_um=1.55,
        pulse_fluence_W_s_per_m2=2.0,
        temporal_fwhm_s=300.0e-15,
    )

    assert gaussian_square_integral(300.0e-15) == pytest.approx(
        2.0 * gaussian_square_integral(600.0e-15)
    )
    assert second == pytest.approx(2.0 * first)

    array_density = tpa_carrier_density(
        beta_2=1.5e-11,
        wavelength_um=1.55,
        pulse_fluence_W_s_per_m2=np.asarray([1.0, 2.0]),
        temporal_fwhm_s=600.0e-15,
    )
    assert array_density[1] == pytest.approx(4.0 * array_density[0])


def test_unstructured_3d_field_is_regularized_with_explicit_bins() -> None:
    points = np.asarray(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
            (1.0, 1.0, 1.0),
        ]
    )
    values = np.sum(points, axis=1)
    interpolation = interpolate_3d(
        {"points": points, "values": values},
        bins={"x": 5, "y": 5, "z": 5},
    )

    assert interpolation(0.0, 0.0, 0.0) == pytest.approx(0.0)
    assert interpolation(1.0, 1.0, 1.0) == pytest.approx(3.0)
    assert 0.0 < interpolation(0.5, 0.5, 0.5) < 3.0


def test_repeated_3d_points_do_not_leave_an_uninitialized_grid_cell() -> None:
    points = np.asarray(
        [
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
            (0.0, 1.0, 1.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (1.0, 0.0, 1.0),
        ]
    )
    interpolation = interpolate_3d(
        {"points": points, "values": np.sum(points, axis=1)},
        bins={"x": 3, "y": 3, "z": 3},
    )

    assert np.isfinite(interpolation(1.0, 1.0, 1.0))


def _write_field_pickle(path: Path, points, values, *, voltage: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        pickle.dump(
            {
                "points": np.asarray(points, dtype=float),
                "values": np.asarray(values, dtype=float),
                "metadata": {"voltage": voltage, "dimension": 3},
            },
            stream,
        )


def test_devsim_field_loads_unstructured_3d_assets(tmp_path: Path) -> None:
    points = np.asarray(
        [
            (0.0, 0.0, 0.0),
            (0.01, 0.0, 0.0),
            (0.0, 0.01, 0.0),
            (0.0, 0.0, 0.01),
            (0.01, 0.01, 0.01),
        ]
    )
    potential = np.sum(points, axis=1)
    _write_field_pickle(tmp_path / "Potential_57V.pkl", points, potential, voltage=57)
    _write_field_pickle(
        tmp_path / "NetDoping_0V.pkl", points, np.full(5, 1.0e12), voltage=0
    )
    _write_field_pickle(
        tmp_path / "TrappingRate_p_57V.pkl", points, np.zeros(5), voltage=57
    )
    _write_field_pickle(
        tmp_path / "TrappingRate_n_57V.pkl", points, np.zeros(5), voltage=57
    )
    _write_field_pickle(
        tmp_path / "weightingfield" / "center" / "Potential_1V.pkl",
        points,
        potential / 0.03,
        voltage=1,
    )

    field = DevsimField(
        "synthetic-3d",
        3,
        57,
        [{"name": "center"}],
        "sde",
        bounds={"x": (0.0, 100.0), "y": (0.0, 100.0), "z": (0.0, 100.0)},
        field_directory=tmp_path,
    )

    assert field._get_potential(0.0, 0.0, 0.0) == pytest.approx(0.0)
    assert field._get_potential(100.0, 100.0, 100.0) == pytest.approx(0.03)
    assert field._get_w_p(100.0, 100.0, 100.0, 0) == pytest.approx(1.0)
    assert np.all(np.isfinite(field._get_e_field(50.0, 50.0, 50.0)))
