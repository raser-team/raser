import json
import math
from types import SimpleNamespace

import numpy as np
import pytest

from raser.core.deposit.laser import LaserInjection, absorption_coefficient
from raser.supports.paths import component_path

H_C = 6.626e-34 * 2.998e8  # J m


def _laser(name: str, size: tuple[float, float, float] = (50.0, 50.0, 50.0), **changes):
    with open(component_path("laser", name + ".json")) as file:
        laser = json.load(file)
    for key, value in changes.items():
        if value is None:
            del laser[key]
        else:
            laser[key] = value
    detector = SimpleNamespace(l_x=size[0], l_y=size[1], l_z=size[2], material="Si")
    return LaserInjection(detector, laser)


# the two-photon beam the numbers below are worked out for, whatever the laser file says
TPA = {"pulse_energy": 50e-12, "temporal_FWHM": 60e-15, "spacial_FWHM": 1.0, "l_Rayleigh": 15.7}


def _tpa(size: tuple[float, float, float] = (50.0, 50.0, 50.0), **changes):
    return _laser("TPA1550_edge_Si", size, **{**TPA, **changes})


def _tpa_pairs_without_end(energy: float, fwhm: float) -> float:
    # β_2 E² z_R sqrt(2 ln2) / (2 hν w0² sqrt(π) τ) for a beam in a medium
    # without end: 50 pJ, 60 fs, 1 um FWHM, z_R = 15.7 um at 1550 nm give 3.53e7
    w0_squared = 1e-12 / (2 * math.log(2))
    pulse_squared = math.sqrt(2 * math.log(2)) / (math.sqrt(math.pi) * fwhm)
    return 1.5e-11 * energy**2 * 15.7e-6 * pulse_squared / (2 * H_C / 1.55e-6 * w0_squared)


def test_two_photon_pairs_of_a_beam_through_300_um() -> None:
    # the path from -150 um to +150 um around the focus holds
    # 2 atan(150 / 15.7) / π = 93.4 % of the pairs of a medium without end
    laser = _tpa(size=(300.0, 300.0, 300.0))

    assert _tpa_pairs_without_end(50e-12, 60e-15) == pytest.approx(3.53e7, rel=2e-3)
    assert sum(laser.ionized_pairs) == pytest.approx(0.934 * 3.53e7, rel=3e-3)


def test_two_photon_pairs_double_when_the_pulse_is_half_as_long() -> None:
    long = sum(_tpa().ionized_pairs)
    short = sum(_tpa(temporal_FWHM=30e-15).ionized_pairs)

    assert short == pytest.approx(2.0 * long)


def test_half_of_the_two_photon_pairs_lie_within_one_rayleigh_length() -> None:
    # atan(1) / atan(150 / 15.7) = 53.5 % of the pairs made on the path
    laser = _tpa(size=(300.0, 300.0, 300.0))
    along = np.array(laser.track_position)[:, 0]

    assert np.mean(np.abs(along - 150.0) < 15.7) == pytest.approx(0.535, abs=0.01)


def test_two_photon_pairs_are_narrower_than_the_beam() -> None:
    # across the beam the pairs follow exp(-4 r² / w²): half of them inside
    # r = w sqrt(ln2) / 2, which is 0.354 um at the focus of a 1 um FWHM spot
    laser = _tpa(size=(300.0, 300.0, 300.0), l_Rayleigh=1e6)
    places = np.array(laser.track_position)
    radius = np.hypot(places[:, 1] - 150.0, places[:, 2] - 150.0)

    assert np.mean(radius < 0.354) == pytest.approx(0.5, abs=0.01)


def test_rayleigh_length_follows_from_the_spot_when_the_file_gives_none() -> None:
    # π w0² n / λ with w0² = 1 um² / (2 ln2), n = 3.51, λ = 1.55 um
    assert _tpa(l_Rayleigh=None).l_Rayleigh == pytest.approx(5.132, rel=1e-3)


def test_pairs_of_a_fully_absorbed_pulse_are_its_photons() -> None:
    # 1 pJ at 660 nm is 3.32e6 photons; with 1/α = 1 um all of them are
    # absorbed in a sensor 50 um thick, one pair each
    laser = _laser("LA01R_top_Si", size=(100.0, 100.0, 50.0), alpha=1e6, pulse_energy=1e-12)

    assert sum(laser.ionized_pairs) == pytest.approx(3.32e6, rel=2e-3)


def test_weak_pulse_keeps_its_pairs() -> None:
    # 1 fJ at 1064 nm is 5356 photons; silicon 50 um thick absorbs
    # 1 - exp(-974 /m * 50 um) = 4.75 % of them
    laser = _laser("LA01IR_top_Si", pulse_energy=1e-15)

    assert sum(laser.ionized_pairs) == pytest.approx(255.0, rel=2e-3)


def test_absorbed_light_makes_its_pairs_near_the_face_it_enters() -> None:
    # 1/α = 5 um: 1 - exp(-1) = 63.2 % of the pairs within 5 um of the face,
    # which is z = 0 from the top and z = 50 um from the bottom
    top = np.array(_laser("LA01R_top_Si", alpha=2e5).track_position)[:, 2]
    bottom = np.array(_laser("LA01R_bottom_Si", alpha=2e5).track_position)[:, 2]

    assert np.mean(top < 5.0) == pytest.approx(0.632, abs=0.01)
    assert np.mean(bottom > 45.0) == pytest.approx(0.632, abs=0.01)


def test_light_beside_the_detector_makes_no_pairs() -> None:
    # the focus on the edge x = 0 of the detector: half of the spot is outside
    whole = sum(_laser("LA01IR_top_Si").ionized_pairs)
    half = sum(_laser("LA01IR_top_Si", fx_rel=0.0).ionized_pairs)

    assert half == pytest.approx(whole / 2)


def test_no_group_holds_more_pairs_than_the_laser_file_allows() -> None:
    laser = _laser("LA01R_top_Si", pairs_per_group=200, pulse_energy=1e-12)

    assert max(laser.ionized_pairs) <= 200
    assert sum(laser.ionized_pairs) == pytest.approx(3.31e6, rel=2e-2)


def test_absorption_of_silicon_between_two_rows_of_the_table() -> None:
    # Green 2008: 11.1 /cm at 1060 nm and 8.00 /cm at 1070 nm; at 1064 nm
    # 11.1 * (8.00 / 11.1)^0.4 = 9.74 /cm
    assert absorption_coefficient("Si", 1.064) == pytest.approx(974.0, rel=1e-3)  # 1/m


def test_silicon_does_not_absorb_band_to_band_beyond_the_table() -> None:
    assert absorption_coefficient("Si", 1.55) == 0.0


def test_laser_without_alpha_takes_the_absorption_of_the_material() -> None:
    assert _laser("LA01IR_top_Si").alpha == pytest.approx(974.0, rel=1e-3)


def test_alpha_of_the_laser_file_replaces_the_table() -> None:
    assert _laser("LA01IR_top_Si", alpha=5000.0).alpha == 5000.0


def test_material_without_a_table_needs_alpha_in_the_laser_file() -> None:
    with open(component_path("laser", "LA01IR_top_Si.json")) as file:
        laser = json.load(file)
    detector = SimpleNamespace(l_x=50.0, l_y=50.0, l_z=50.0, material="Diamond")

    with pytest.raises(ValueError, match="give alpha"):
        LaserInjection(detector, laser)


def test_defects_absorb_their_share_of_the_photons_along_the_whole_beam() -> None:
    # 50 pJ at 1550 nm is 3.90e8 photons; α = 100 /m over the 50 um of the
    # sensor absorbs 0.5 % of them, wherever the focus is. The pulse is long,
    # so that two photons make no pairs.
    laser = _tpa(alpha=100.0, temporal_FWHM=1e-3)

    assert sum(laser.ionized_pairs) == pytest.approx(0.005 * 3.90e8, rel=5e-3)


def test_single_photon_share_grows_when_the_pulse_energy_falls() -> None:
    # two-photon pairs go with E², single-photon pairs with E; the pairs of
    # one photon alone are those of a long pulse
    def share(energy: float) -> float:
        one = sum(_tpa(pulse_energy=energy, alpha=1.0, temporal_FWHM=1e-3).ionized_pairs)
        both = sum(_tpa(pulse_energy=energy, alpha=1.0).ionized_pairs)
        return one / (both - one)

    assert share(5e-12) == pytest.approx(10.0 * share(50e-12), rel=1e-3)


def test_two_photon_pairs_are_made_over_a_shorter_time_than_the_pulse() -> None:
    # one photon follows the Gaussian pulse I(t), two follow I(t)², whose FWHM
    # is that of the pulse divided by sqrt(2)
    laser = _tpa(alpha=100.0)
    widths = np.array(laser.time_FWHM)
    pairs = np.array(laser.ionized_pairs)
    one = sum(_tpa(alpha=100.0, temporal_FWHM=1e-3).ionized_pairs)  # the single-photon pairs alone

    assert set(np.round(widths / 60e-15, 6)) == {1.0, round(1 / math.sqrt(2), 6)}
    assert pairs[np.isclose(widths, 60e-15, rtol=1e-6, atol=0)].sum() == pytest.approx(one, rel=1e-6)


def test_laser_pulse_is_one_event_of_deposits_with_the_spread_of_its_times(tmp_path) -> None:
    from raser.core.deposit.deposits import read_deposits, write_deposits
    from raser.core.deposit.laser import laser_deposits

    with open(component_path("laser", "TPA1550_edge_Si.json")) as file:
        laser = {**json.load(file), **TPA, "alpha": 100.0}
    detector = SimpleNamespace(l_x=50.0, l_y=50.0, l_z=50.0, material="Si")
    deposits = laser_deposits(detector, laser)
    path = tmp_path / "deposit_0.h5"
    write_deposits(path, deposits)
    event = read_deposits(path).events[0]

    groups = LaserInjection(detector, laser)
    assert deposits.generated_events == 1 and len(read_deposits(path).events) == 1
    assert sum(event.pairs) == pytest.approx(sum(groups.ionized_pairs))
    # 3.6 eV a pair in silicon
    assert sum(event.e) == pytest.approx(sum(groups.ionized_pairs) * 3.6e-6)
    assert sorted(set(np.round(np.array(event.t_fwhm) / 60e-15, 6))) == [round(1 / math.sqrt(2), 6), 1.0]
    assert event.z_start == event.z
    # group by group, in the order of LaserInjection: one photon or two
    assert event.t_fwhm == [float(w) for w in groups.time_FWHM]
    assert event.pairs == pytest.approx(groups.ionized_pairs)


@pytest.mark.parametrize("name", ["TPA1550_top_Si", "TPA1550_edge_Si"])
def test_two_photon_presets_make_a_signal_and_absorb_little(name: str) -> None:
    # a waist w0 and a Rayleigh length in silicon belong together:
    # z_R = π w0² n / λ (w0 = FWHM / sqrt(2 ln2)); and the pulse of the preset
    # makes more than 100 pairs in 50 um of silicon while two-photon
    # absorption takes a small share of its photons (the weak-absorption
    # range the formula holds in)
    with open(component_path("laser", name + ".json")) as file:
        preset = json.load(file)
    w0 = preset["spacial_FWHM"] / math.sqrt(2 * math.log(2))
    assert preset["l_Rayleigh"] == pytest.approx(math.pi * w0**2 * preset["refractionIndex"] / 1.55, rel=0.01)
    laser = LaserInjection(SimpleNamespace(l_x=50.0, l_y=50.0, l_z=50.0, material="Si"), preset)
    photons = preset["pulse_energy"] * 1.55e-6 / H_C
    assert 100 < sum(laser.ionized_pairs) < 0.1 * photons


def test_sic_absorption_matches_the_measured_coefficients_at_room_temperature() -> None:
    # Sridhara et al. 1998, Table I: 290, 230, 210, 180 /cm at 351.1, 354.0,
    # 355.0, 356.4 nm and room temperature
    for nm, per_cm in ((351.1, 290.0), (354.0, 230.0), (355.0, 210.0), (356.4, 180.0)):
        assert absorption_coefficient("SiC", nm * 1e-3, 300.0) == pytest.approx(100.0 * per_cm, rel=0.15)


def test_sic_absorption_follows_the_measured_edge_at_75_K() -> None:
    # Grivickas et al. 2007, Fig. 4: sqrt(α[/cm] ħω[eV]) = 1.7, 2.6, 7.5 at
    # 3.32, 3.34, 3.38 eV and 75 K
    for photon, root in ((3.32, 1.7), (3.34, 2.6), (3.38, 7.5)):
        alpha = absorption_coefficient("SiC", 1.23984198 / photon, 75.0)
        assert math.sqrt(alpha / 100.0 * photon) == pytest.approx(root, rel=0.10)


def test_sic_does_not_absorb_band_to_band_below_the_lowest_phonon_threshold() -> None:
    # at 300 K the gap is 3.2326 eV; with the 106.2 meV phonon absorbed the
    # threshold is 3.126 eV (397 nm)
    assert absorption_coefficient("SiC", 0.401, 300.0) == 0.0
    assert absorption_coefficient("SiC", 0.395, 300.0) > 0.0


def test_warmer_sic_absorbs_more_at_the_edge() -> None:
    # the gap narrows with the temperature (Grivickas et al. 2007, Eq. (5))
    assert absorption_coefficient("SiC", 0.375, 350.0) > 1.5 * absorption_coefficient("SiC", 0.375, 300.0)


def test_sic_absorption_needs_the_temperature_and_stops_at_its_fitted_range() -> None:
    # the model of Grivickas et al. 2007 is fitted up to 3.8 eV (326 nm)
    with pytest.raises(ValueError, match="temperature"):
        absorption_coefficient("SiC", 0.375)
    with pytest.raises(ValueError, match="give alpha"):
        absorption_coefficient("SiC", 0.320, 300.0)


def test_sic_laser_takes_the_absorption_of_its_device_temperature() -> None:
    # Grivickas et al. 2007, Table I and Eq. (5): 9.05 /cm at 375 nm and 300 K
    with open(component_path("laser", "PIL037_top_SiC.json")) as file:
        laser = json.load(file)
    detector = SimpleNamespace(l_x=50.0, l_y=50.0, l_z=50.0, material="SiC", temperature=300.0)
    alpha = LaserInjection(detector, laser).alpha

    assert alpha == absorption_coefficient("SiC", 0.375, 300.0)
    assert 900.0 < alpha < 910.0
