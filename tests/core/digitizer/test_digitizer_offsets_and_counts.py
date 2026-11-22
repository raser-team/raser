"""Offsets, sample counts and independence of stored electrodes."""

import numpy as np
import pytest

from raser.core.digitizer.digital_waveforms import read_digitized
from raser.core.digitizer.job import write_digitized
from raser.core.digitizer.quantize import quantize, to_volts
from raser.core.digitizer.sampling import sample
from raser.core.digitizer.settings import DigitizerSettings
from raser.core.readout.waveforms import EventWaveforms, append_waveforms


def _settings(offset_V=0.0, channels=2):
    return DigitizerSettings.from_component(
        "test",
        {
            "channels": channels,
            "bits": 8,
            "max_sampling_rate_GSps": 16,
            "response": "none",
            "aperture_jitter_ps": 0,
            "sampling_rate_GSps": 16,
            "full_scale_V": 0.04,
            "offset_V": offset_V,
        },
    )


def test_codes_read_back_at_the_voltage_they_came_from_with_an_offset():
    settings = _settings(offset_V=-0.01)
    volts = np.random.default_rng(3).uniform(-0.0299, 0.0099, (1, 100000))
    codes, clipped = quantize(volts, settings)
    error = volts - to_volts(codes, settings.bits, settings.lsb_V, settings.offset_V)
    assert clipped[0] == 0
    assert abs(error.mean()) < 0.01 * settings.lsb_V
    assert np.abs(error).max() <= settings.lsb_V / 2 * (1 + 1e-9)
    middle, _ = quantize(np.array([[-0.01 - 1e-9, -0.01 + 1e-9]]), settings)
    assert middle.tolist() == [[2**settings.bits // 2 - 1, 2**settings.bits // 2]]


class _PhaseZero:
    """Generator whose clock phase is the lower bound: sampling starts at the first bin edge."""

    def uniform(self, low, high):
        return low


def test_samples_are_taken_between_the_bin_centres_of_the_readout():
    settings = _settings()
    dt = 50e-12
    centres = (np.arange(64) + 0.5) * dt
    phase, samples = sample(
        centres[None, :], dt, [0], settings, lambda device: _PhaseZero(), None
    )
    assert phase[0] == 0.0
    times = np.arange(samples.shape[1]) * settings.period_s
    inside = times >= centres[0]
    np.testing.assert_allclose(samples[0, inside], times[inside], rtol=0, atol=1e-15)


@pytest.mark.parametrize("bins", [64, 65, 100])
def test_every_sample_of_any_phase_lies_on_the_waveform(bins):
    settings = _settings()
    dt = 50e-12
    record = bins * dt
    phase, samples = sample(
        np.zeros((1, bins)),
        dt,
        [0],
        settings,
        lambda device: np.random.default_rng(0),
        None,
    )
    count = samples.shape[1]
    assert phase[0] + (count - 1) * settings.period_s < record
    assert count * settings.period_s <= record < (count + 1) * settings.period_s


def test_an_electrode_gives_the_same_codes_whatever_else_the_event_stores(tmp_path):
    settings = _settings(channels=8)
    rng = np.random.default_rng(5)
    waveform = {name: rng.normal(0.0, 0.003, 80) for name in ("a", "b", "c")}
    results = {}
    for stored in (["a", "b", "c"], ["c"]):
        readout = tmp_path / f"readout_{len(stored)}.h5"
        append_waveforms(
            readout,
            ["a", "b", "c"],
            50e-12,
            500e-12,
            EventWaveforms(
                3, 0.0, np.array([waveform[name] for name in stored]), stored
            ),
            pulse_edge=["falling"] * 3,
        )
        out = tmp_path / f"digitizer_{len(stored)}.h5"
        write_digitized(
            readout,
            out,
            settings,
            "test",
            11,
            0,
            tmp_path / "plots",
            lambda event: [],
        )
        assert read_digitized(out).pre_window == 500e-12  # the readout file's
        event = read_digitized(out).events[0]
        results[len(stored)] = dict(zip(event.electrodes, event.code, strict=True))
    np.testing.assert_array_equal(results[3]["c"], results[1]["c"])


def _write_readout(tmp_path):
    readout = tmp_path / "readout.h5"
    time = np.arange(64) * 50e-12
    pulse = -0.01 * np.exp(-time / 0.5e-9)[None, :]
    for number, names in ((4, []), (7, ["a"]), (9, ["a", "b"]), (12, ["b"])):
        append_waveforms(
            readout,
            ["a", "b"],
            50e-12,
            500e-12,
            EventWaveforms(
                number,
                0.0,
                np.repeat(pulse, len(names), axis=0).reshape(len(names), 64),
                names,
            ),
            pulse_edge=["falling"] * 2,
        )
    return readout


# Deliberate change: the condition `and places` removed from the samples figure
# of write_digitized (the empty event 4 would then take one of the two figures).
def test_write_digitized_draws_the_first_stored_events_and_the_codes(tmp_path):
    plots = tmp_path / "plots"
    write_digitized(
        _write_readout(tmp_path),
        tmp_path / "digitizer.h5",
        _settings(),
        "test",
        0,
        2,
        plots,
        lambda event: [],
    )
    assert sorted(path.name for path in plots.glob("*.png")) == [
        "codes.png",
        "samples_7.png",
        "samples_9.png",
    ]


# Deliberate change: the codes figure drawn whatever plots is.
def test_write_digitized_without_plots_creates_no_folder(tmp_path):
    plots = tmp_path / "plots"
    write_digitized(
        _write_readout(tmp_path),
        tmp_path / "digitizer.h5",
        _settings(),
        "test",
        0,
        0,
        plots,
        lambda event: [],
    )
    assert not plots.exists()
