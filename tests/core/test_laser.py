import json
from types import SimpleNamespace

import pytest

from raser.core.interaction.laser import LaserInjection
from raser.supports.paths import component_path


def _tpa_laser(temporal_fwhm: float, rayleigh: float | None = 15.7) -> LaserInjection:
    with open(component_path("laser", "TPA_edge_Si.json")) as file:
        laser = json.load(file)
    laser["temporal_FWHM"] = temporal_fwhm
    del laser["l_Rayleigh"]
    if rayleigh is not None:
        laser["l_Rayleigh"] = rayleigh
    return LaserInjection(SimpleNamespace(l_x=50.0, l_y=50.0, l_z=50.0), laser)


def test_tpa_density_at_the_focus_of_a_50_pJ_60_fs_pulse() -> None:
    # 50 pJ in a spot of 1 um FWHM: fluence 4 E / (π w0²) = 88.25 J/m² with
    # w0² = 1 um² / (2 ln2); β_2 = 1.5e-11 m/W, 1550 nm, 60 fs:
    # 1.5e-11 * 1.55e-6 * 88.25² / (2 h c) * sqrt(2 ln2) / (sqrt(π) 60 fs)
    density = _tpa_laser(60e-15).getCarrierDensity(0.0, 0.0, 0.0)

    assert density == pytest.approx(5.045e24, rel=2e-3)  # pairs per m³


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
