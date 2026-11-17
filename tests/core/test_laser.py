import json
from types import SimpleNamespace

import pytest

from raser.core.interaction.laser import LaserInjection, absorption_coefficient
from raser.supports.paths import component_path


def _tpa_laser(
    temporal_fwhm: float, rayleigh: float | None = 15.7, **changes
) -> LaserInjection:
    with open(component_path("laser", "TPA_edge_Si.json")) as file:
        laser = json.load(file)
    laser["temporal_FWHM"] = temporal_fwhm
    del laser["l_Rayleigh"]
    if rayleigh is not None:
        laser["l_Rayleigh"] = rayleigh
    laser.update(changes)
    detector = SimpleNamespace(l_x=50.0, l_y=50.0, l_z=50.0, material="Si")
    return LaserInjection(detector, laser)


def test_tpa_density_at_the_focus_of_a_50_pJ_60_fs_pulse() -> None:
    # 50 pJ in a spot of 1 um FWHM: fluence 2 E / (π w0²) = 44.13 J/m² with
    # w0² = 1 um² / (2 ln2); β_2 = 1.5e-11 m/W, 1550 nm, 60 fs:
    # 1.5e-11 * 1.55e-6 * 44.13² / (2 h c) * sqrt(2 ln2) / (sqrt(π) 60 fs)
    density = _tpa_laser(60e-15).getCarrierDensity(0.0, 0.0, 0.0)

    assert density == pytest.approx(1.261e24, rel=2e-3)  # pairs per m³


def test_pairs_of_a_fully_absorbed_pulse_are_its_photons() -> None:
    # 1 pJ at 660 nm is 3.32e6 photons; with 1/α = 1 um all of them are
    # absorbed in a sensor 50 um thick, one pair each
    with open(component_path("laser", "SPA_top_Si.json")) as file:
        laser = json.load(file)
    laser.update(alpha=1e6, pulse_energy=1e-12, fz_rel=0.0, r_step=0.5, h_step=0.1)
    injection = LaserInjection(SimpleNamespace(l_x=100.0, l_y=100.0, l_z=50.0), laser)

    assert sum(injection.ionized_pairs) == pytest.approx(3.32e6, rel=2e-2)


def test_tpa_density_doubles_when_the_pulse_is_half_as_long() -> None:
    long = _tpa_laser(60e-15).getCarrierDensity(0.0, 0.0, 0.0)
    short = _tpa_laser(30e-15).getCarrierDensity(0.0, 0.0, 0.0)

    assert short == pytest.approx(2.0 * long)


def test_beam_widens_over_the_rayleigh_length_of_the_laser_file() -> None:
    # one Rayleigh length from the focus the beam area has doubled, so the
    # fluence is halved and the two-photon density quartered
    laser = _tpa_laser(60e-15, rayleigh=15.7)

    focus = laser.getCarrierDensity(0.0, 0.0, 0.0)
    assert laser.getCarrierDensity(15.7, 0.0, 0.0) == pytest.approx(focus / 4)


def test_rayleigh_length_follows_from_the_spot_when_the_file_gives_none() -> None:
    # π w0² n / λ with w0² = 1 um² / (2 ln2), n = 3.51, λ = 1.55 um
    laser = _tpa_laser(60e-15, rayleigh=None)

    assert laser.l_Rayleigh == pytest.approx(5.132, rel=1e-3)


def _spa_laser(material: str, **changes) -> LaserInjection:
    with open(component_path("laser", "SPA_top_Si_IR.json")) as file:
        laser = json.load(file)
    laser.update(changes)
    detector = SimpleNamespace(l_x=50.0, l_y=50.0, l_z=50.0, material=material)
    return LaserInjection(detector, laser)


def test_absorption_of_silicon_between_two_rows_of_the_table() -> None:
    # Green 2008: 11.1 /cm at 1060 nm and 8.00 /cm at 1070 nm; at 1064 nm
    # 11.1 * (8.00 / 11.1)^0.4 = 9.74 /cm
    assert absorption_coefficient("Si", 1.064) == pytest.approx(974.0, rel=1e-3)  # 1/m


def test_silicon_does_not_absorb_band_to_band_beyond_the_table() -> None:
    assert absorption_coefficient("Si", 1.55) == 0.0


def test_laser_without_alpha_takes_the_absorption_of_the_material() -> None:
    assert _spa_laser("Si").alpha == pytest.approx(974.0, rel=1e-3)


def test_alpha_of_the_laser_file_replaces_the_table() -> None:
    assert _spa_laser("Si", alpha=5000.0).alpha == 5000.0


def test_material_without_a_table_needs_alpha_in_the_laser_file() -> None:
    with pytest.raises(ValueError, match="give alpha"):
        _spa_laser("Diamond")


def test_defect_absorption_adds_pairs_linear_in_the_pulse_energy() -> None:
    # at the entrance (focus at the surface) α F / (h ν) with α = 100 /m,
    # F = 44.13 J/m², 1550 nm: 100 * 44.13 * 1.55e-6 / (h c) = 3.443e22 /m³
    pure = _tpa_laser(60e-15, fx_rel=0.0).getCarrierDensity(0.0, 0.0, 0.0)
    mixed = _tpa_laser(60e-15, fx_rel=0.0, alpha=100.0).getCarrierDensity(0.0, 0.0, 0.0)

    assert mixed - pure == pytest.approx(3.443e22, rel=2e-3)


def test_single_photon_share_grows_when_the_pulse_energy_falls() -> None:
    # two-photon pairs go with E², single-photon pairs with E
    def parts(energy: float) -> tuple[float, float]:
        pure = _tpa_laser(60e-15, fx_rel=0.0, pulse_energy=energy)
        mixed = _tpa_laser(60e-15, fx_rel=0.0, pulse_energy=energy, alpha=100.0)
        two = pure.getCarrierDensity(0.0, 0.0, 0.0)
        return mixed.getCarrierDensity(0.0, 0.0, 0.0) - two, two

    one_high, two_high = parts(50e-12)
    one_low, two_low = parts(5e-12)

    assert one_low / two_low == pytest.approx(10.0 * one_high / two_high)


def test_defects_absorb_their_share_of_the_photons_along_the_whole_beam() -> None:
    # 50 pJ at 1550 nm is 3.90e8 photons; α = 100 /m over the 50 um of the
    # sensor absorbs 0.5 % of them, wherever the focus is. The pulse is long,
    # so that two photons make no pairs.
    laser = _tpa_laser(1e-3, alpha=100.0, fx_rel=0.5, r_step=0.25, h_step=1.0)

    assert sum(laser.ionized_pairs) == pytest.approx(0.005 * 3.90e8, rel=2e-2)


def test_weak_pulse_keeps_the_pairs_of_cells_with_less_than_one_pair() -> None:
    # 1 fJ at 1064 nm is 5356 photons; silicon 50 um thick absorbs
    # 1 - exp(-974 /m * 50 um) = 4.75 % of them: 255 pairs over 28800 cells
    laser = _spa_laser("Si", pulse_energy=1e-15, fz_rel=0.0)

    assert sum(laser.ionized_pairs) == pytest.approx(255.0, rel=1e-2)
