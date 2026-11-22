import dataclasses
import math

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.optimize import brentq
from scipy.special import erf

from raser.core.current.currents import EventCurrents, append_currents
from raser.core.field.device_circuit import DeviceCircuit
from raser.core.readout.cable import (
    SPEED_OF_LIGHT,
    Cable,
    attenuation_db_per_m,
    read_cable,
    through_cable,
    transfer_factor,
)
from raser.core.readout.job import LOWEST_NOISE_HZ, noise_spectra, write_waveforms
from raser.core.readout.spectral_noise import noise_from_spectrum
from raser.core.readout.spice import solve
from raser.core.readout.waveforms import read_waveforms
from raser.stages.readout import cable_of

BELDEN = read_cable("Belden8259")
# one metre of Belden 8259: 1 / (c * 0.66)
ONE_METRE_S = 1.0 / (SPEED_OF_LIGHT * 0.66)
DT_S = 5e-12
# a wire and a 50 Ohm load behind a device that is a current source on 50 Ohm
WIRE = {
    "ports": {"in": "a", "out": "b"},
    "elements": {"R1": {"between": ["a", "b"], "ohm": 1e-6}},
}
LOAD = {
    "ports": {"in": "a"},
    "elements": {"R1": {"between": ["a", "0"], "ohm": 50.0}},
}
CHAIN = {"stages": {"wire": WIRE}, "load": LOAD}
SOURCE_ON_50_OHM = DeviceCircuit(
    lines=("R1 pad 0 50",), sources={"top": ("pad", "0")}, outputs={"top": "pad"}
)


def _crossing(times, voltage, level):
    """Time the voltage first reaches the level, by a line between bins."""
    after = int(np.argmax(voltage >= level))
    before = after - 1
    fraction = (level - voltage[before]) / (voltage[after] - voltage[before])
    return times[before] + fraction * (times[after] - times[before])


def test_loss_coefficients_of_the_data_sheet_give_back_400_mhz():
    # the data sheet has 0.407 dB/m at 400 MHz; the two points it is solved
    # from are 100 MHz and 1000 MHz, and the model between them is a fit
    assert BELDEN.skin == pytest.approx(1.72e-6, rel=1e-3)
    assert BELDEN.dielectric == pytest.approx(3.17e-11, rel=1e-3)
    assert attenuation_db_per_m(BELDEN, 400e6) == pytest.approx(0.409, abs=0.001)
    assert attenuation_db_per_m(BELDEN, 400e6) == pytest.approx(0.407, abs=0.003)
    # the points themselves are exact
    assert attenuation_db_per_m(BELDEN, 100e6) == pytest.approx(0.177, abs=1e-9)
    assert attenuation_db_per_m(BELDEN, 1000e6) == pytest.approx(0.748, abs=1e-9)
    # and the transfer factor loses that many dB in a metre
    modulus = abs(transfer_factor(BELDEN, 1.0, 400e6))
    assert -20 * math.log10(modulus) == pytest.approx(0.409, abs=0.001)


def test_velocity_of_the_component_is_the_speed_of_light_times_the_factor():
    assert BELDEN.velocity == pytest.approx(299792458.0 * 0.66, rel=1e-12)
    assert ONE_METRE_S == pytest.approx(5.05e-9, abs=0.01e-9)


def test_cable_of_length_zero_leaves_the_waveform_and_its_reference_as_they_are():
    times = np.arange(2000) * 2e-12
    pulse = np.where(times >= 1e-9, np.exp(-(times - 1e-9) / 1e-9), 0.0)

    assert through_cable(BELDEN, 0.0, pulse, 2e-12) == pytest.approx(pulse, abs=1e-12)

    # the level before the pulse is a direct current: a cable passes it whole
    # and moves the pulse the same as without it
    on_a_level = through_cable(BELDEN, 1.0, 0.3 + pulse, 2e-12)
    assert on_a_level == pytest.approx(
        0.3 + through_cable(BELDEN, 1.0, pulse, 2e-12), abs=1e-12
    )
    assert through_cable(BELDEN, 1.0, np.full(2000, 0.3), 2e-12) == pytest.approx(
        0.3, abs=1e-12
    )


def _skin_delay_s(skin, length_m, decay_s, edge_s, at_s):
    """Delay of the 50 % crossing of an edge (error function of width edge_s
    at at_s, then an exponential decay) on a line that has the skin loss alone:
    the pulse folded with the impulse response of the line, whose step response
    is erfc(kappa / (2 sqrt(t))), kappa = length * skin / sqrt(pi)."""
    kappa = length_m * skin / np.sqrt(np.pi)

    def impulse(s):
        return kappa / (2 * np.sqrt(np.pi)) * s**-1.5 * np.exp(-(kappa**2) / (4 * s))

    def pulse(t):
        edge = 0.5 * (1 + erf((t - at_s) / (np.sqrt(2) * edge_s)))
        return edge * np.exp(-np.clip(t - at_s, 0, None) / decay_s)

    def through(t):
        last = t - at_s + 8 * edge_s
        cuts = [0, kappa**2, 10 * kappa**2, 1e-11, 1e-10, last / 4, last / 2, last]
        cuts = sorted({cut for cut in cuts if 0 <= cut <= last})
        return sum(
            quad(lambda s: pulse(t - s) * impulse(s), a, b, limit=400, epsabs=1e-13)[0]
            for a, b in zip(cuts[:-1], cuts[1:])
        )

    window = (at_s - 100e-12, at_s + 300e-12)
    return brentq(lambda t: through(t) - 0.5, *window, xtol=1e-16) - brentq(
        lambda t: pulse(t) - 0.5, *window, xtol=1e-16
    )


def test_a_cable_of_one_metre_moves_the_edge_of_a_pulse_by_its_dispersion():
    # the line with the skin loss of the Belden cable and no dielectric loss,
    # whose dielectric part reaches far before the edge; 3 m is in
    # as well, where the shift is three times larger
    skin_only = dataclasses.replace(BELDEN, dielectric=0.0)
    dt, bins, at, edge, decay = 2e-12, 4000, 1e-9, 50e-12, 1e-9
    times = np.arange(bins) * dt
    pulse = 0.5 * (1 + erf((times - at) / (np.sqrt(2) * edge)))
    pulse = pulse * np.exp(-np.clip(times - at, 0, None) / decay)

    for length in (1.0, 3.0):
        filtered = through_cable(skin_only, length, pulse, dt)
        shift = _crossing(times, filtered, 0.5) - _crossing(times, pulse, 0.5)
        expected = _skin_delay_s(skin_only.skin, length, decay, edge, at)
        # 9 ps for 1 m; what is left is the end of the window, where the
        # record the transform is made on is cut
        assert shift == pytest.approx(expected, abs=0.15e-12 * length)
        assert shift > 8e-12 * length


@pytest.mark.ngspice
def test_lossless_line_matched_on_both_ends_delays_by_its_delay():
    cable = Cable(BELDEN, {"top": 1.0})
    bins = 2400
    times = (np.arange(bins) + 0.5) * DT_S
    step = np.where(times > 1e-9, 1e-6, 0.0)

    bare = solve(CHAIN, ["top"], DT_S, [step], SOURCE_ON_50_OHM)[0]
    delayed = solve(CHAIN, ["top"], DT_S, [step], SOURCE_ON_50_OHM, cable)[0]

    # 1 uA on the 50 Ohm of the source and the line is 25 uV on the load
    assert bare[-1] == pytest.approx(-25e-6, rel=1e-3)
    assert delayed[-1] == pytest.approx(-25e-6, rel=1e-3)
    delay = _crossing(times, -delayed, 12.5e-6) - _crossing(times, -bare, 12.5e-6)
    assert delay == pytest.approx(ONE_METRE_S, abs=DT_S)


def _pulse_events(path, bins):
    """One event: 1 uA from 1 ns on that decays in 1 ns."""
    times = (np.arange(bins) + 0.5) * DT_S
    current = np.where(times > 1e-9, 1e-6 * np.exp(-(times - 1e-9) / 1e-9), 0.0)
    append_currents(
        path, ["top"], DT_S, EventCurrents(7, -1e-9, current[None, :], np.zeros(1), 0.0)
    )


@pytest.mark.ngspice
def test_waveforms_of_a_cable_are_longer_by_its_delay_and_come_later_by_it(tmp_path):
    bins = 1000
    currents = tmp_path / "currents.h5"
    _pulse_events(currents, bins)
    cable = Cable(BELDEN, {"top": 1.0})
    for name, given in (("bare", None), ("cable", cable)):
        write_waveforms(
            currents,
            tmp_path / f"{name}.h5",
            CHAIN,
            SOURCE_ON_50_OHM,
            None,
            given,
            pulse_edge=["falling"],
            pre_window_s=0.0,
            post_window_s=0.0,
        )
    bare = read_waveforms(tmp_path / "bare.h5").events[0]
    delayed = read_waveforms(tmp_path / "cable.h5").events[0]

    extra = math.ceil(ONE_METRE_S / DT_S)
    assert bare.voltage.shape == (1, bins)
    assert delayed.voltage.shape == (1, bins + extra)
    assert delayed.t0 == bare.t0
    level = 0.5 * np.abs(bare.voltage).max()
    times = np.arange(bins + extra) * DT_S
    shift = _crossing(times, -delayed.voltage[0], level) - _crossing(
        times[:bins], -bare.voltage[0], level
    )
    # the delay and, on top of it, the dispersion of a metre: a few ps
    assert shift - ONE_METRE_S == pytest.approx(0.0, abs=20e-12)
    assert shift > ONE_METRE_S


@pytest.mark.ngspice
def test_noise_of_a_cable_is_that_of_the_circuit_times_its_loss(tmp_path):
    bins = 1000
    currents = tmp_path / "currents.h5"
    _pulse_events(currents, bins)
    cable = Cable(BELDEN, {"top": 30.0})
    for name, seed in (("quiet", None), ("noisy", 5)):
        write_waveforms(
            currents,
            tmp_path / f"{name}.h5",
            CHAIN,
            SOURCE_ON_50_OHM,
            seed,
            cable,
            pulse_edge=["falling"],
            pre_window_s=0.0,
            post_window_s=0.0,
        )
    quiet = read_waveforms(tmp_path / "quiet.h5").events[0].voltage[0]
    noisy = read_waveforms(tmp_path / "noisy.h5").events[0].voltage[0]

    count = len(quiet)
    assert count == bins + math.ceil(30.0 * ONE_METRE_S / DT_S)
    frequencies, densities = noise_spectra(
        CHAIN, SOURCE_ON_50_OHM, LOWEST_NOISE_HZ, 0.5 / DT_S
    )
    expected = noise_from_spectrum(
        frequencies,
        densities[0] * np.abs(cable.transfer("top", frequencies)),
        count,
        DT_S,
        np.random.default_rng([5, 7, 0]),
    )
    assert noisy - quiet == pytest.approx(expected, abs=1e-12)
    # the cable takes much of the noise: more than the 50 Ohm alone has
    without = noise_from_spectrum(
        frequencies, densities[0], count, DT_S, np.random.default_rng([5, 7, 0])
    )
    assert np.std(expected) < 0.9 * np.std(without)


def _kwargs(length_m):
    return {"cable": {"name": "Belden8259", "length_m": length_m}}


def test_no_cable_setting_is_a_read_out_without_cable():
    assert cable_of({}, "det", ["top"]) is None
    assert cable_of({"cable": None}, "det", ["top"]) is None


def test_lengths_of_the_cable_are_one_for_each_output():
    cable = cable_of(_kwargs({"a": 1, "b": 0.0}), "det", ["a", "b"])
    assert cable.length_m == {"a": 1.0, "b": 0.0}
    assert cable.delay_s("a") == pytest.approx(ONE_METRE_S, rel=1e-12)
    assert cable.delay_s("b") == 0.0


def test_a_length_missing_for_an_output_is_named():
    with pytest.raises(
        ValueError,
        match=r"^readout\.cable\.length_m\.b is missing: give a cable length in m for each output of det \(.*'a', 'b'.*\)$",
    ):
        cable_of(_kwargs({"a": 1.0}), "det", ["a", "b"])
    # a name of a cable alone has no length for any output
    with pytest.raises(ValueError, match=r"length_m\.a is missing"):
        cable_of({"cable": "Belden8259"}, "det", ["a", "b"])


def test_a_length_for_a_channel_the_circuit_has_not_is_refused():
    with pytest.raises(
        ValueError,
        match=r"^readout\.cable\.length_m has unknown channels \['c'\]; the outputs of det are .*'a'.*$",
    ):
        cable_of(_kwargs({"a": 1.0, "c": 1.0}), "det", ["a"])


@pytest.mark.parametrize("value", [-1.0, float("nan"), float("inf"), "long", True])
def test_a_length_that_is_not_a_finite_non_negative_number_is_refused(value):
    with pytest.raises(
        ValueError,
        match=r"^readout\.cable\.length_m\.a must be a finite non-negative number in m, not ",
    ):
        cable_of(_kwargs({"a": value}), "det", ["a"])
