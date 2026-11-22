"""Clipping counts, short events, empty readouts and the codes figure of write_digitized."""

import re

import h5py
import numpy as np
import pytest

from raser.core.digitizer import draw
from raser.core.digitizer.digital_waveforms import read_digitized
from raser.core.digitizer.job import write_digitized
from raser.core.digitizer.sampling import sample_count
from raser.core.digitizer.settings import DigitizerSettings
from raser.core.readout.waveforms import EventWaveforms, append_waveforms

DT = 50e-12
PULSE_EDGE = ["falling"]


def _settings():
    # range [-0.02 V, +0.02 V), period 62.5 ps
    return DigitizerSettings.from_component(
        "test",
        {
            "channels": 4,
            "bits": 8,
            "max_sampling_rate_GSps": 16,
            "response": "none",
            "aperture_jitter_ps": 0,
            "sampling_rate_GSps": 16,
            "full_scale_V": 0.04,
            "offset_V": 0.0,
        },
    )


def _append(path, electrodes, number, volts):
    append_waveforms(
        path,
        electrodes,
        DT,
        10 * DT,
        EventWaveforms(number, 0.0, np.asarray(volts, dtype=float)),
        pulse_edge=["falling"] * len(electrodes),
    )


def _digitize(readout, output, plots=0, plot_path=None, seed=0):
    write_digitized(
        readout,
        output,
        _settings(),
        "test",
        seed,
        plots,
        plot_path,
        lambda event: [],
    )


# Deliberate change: in quantize(), the clipped count of samples above the
# range only (the samples below the range are not counted).
def test_clipped_counts_the_samples_beyond_the_full_scale_range(tmp_path):
    settings = _settings()
    bins = 400
    centres = (np.arange(bins) + 0.5) * DT
    periods = 10
    amplitude = 0.05
    frequency = periods / (bins * DT)
    cosine = amplitude * np.cos(2 * np.pi * frequency * centres)
    inside = np.full(bins, 0.001)
    above = np.full(bins, 1.0)
    below = np.full(bins, -1.0)
    readout = tmp_path / "readout.h5"
    names = ["inside", "above", "below", "cosine"]
    _append(readout, names, 1, [inside, above, below, cosine])
    output = tmp_path / "digitizer.h5"
    _digitize(readout, output)
    event = read_digitized(output).events[0]
    clipped = dict(zip(event.electrodes, event.clipped, strict=True))
    count = sample_count(bins, DT, settings.period_s)
    # a constant waveform is reproduced exactly at any instant: the plateau
    # outside the range clips every sample, the one inside none
    assert clipped["inside"] == 0
    assert clipped["above"] == count
    assert clipped["below"] == count
    # the cosine has whole periods in the record, so the interpolation returns
    # it exactly; the instants are the clock phase of device 0 plus k periods
    phase = np.random.default_rng([0, 1, 0, 0]).uniform(0.0, settings.period_s)
    instants = phase + np.arange(count) * settings.period_s
    exact = amplitude * np.cos(2 * np.pi * frequency * instants)
    low, high = -settings.full_scale_V / 2, settings.full_scale_V / 2
    margin = np.min(np.minimum(np.abs(exact - low), np.abs(exact - high)))
    assert margin > 1e-6
    expected = int(np.sum((exact < low) | (exact >= high)))
    assert 0 < expected < count
    assert clipped["cosine"] == expected
    codes = dict(zip(event.electrodes, event.code, strict=True))
    assert np.all(codes["above"] == 255)
    assert np.all(codes["below"] == 0)
    assert np.sum((codes["cosine"] == 0) | (codes["cosine"] == 255)) == expected


# Deliberate change: the check of the sampling-point count removed, or its
# threshold lowered to count < 1.
@pytest.mark.parametrize("bins", [1, 2])
def test_an_event_shorter_than_two_sampling_periods_is_refused(tmp_path, bins):
    settings = _settings()
    readout = tmp_path / "readout.h5"
    _append(readout, ["a"], 3, np.zeros((1, 64)))
    _append(readout, ["a"], 5, np.zeros((1, bins)))
    count = sample_count(bins, DT, settings.period_s)
    assert count < 2
    message = (
        rf"event 5 .*{re.escape(str(bins * DT))} s.*"
        rf"period {re.escape(str(settings.period_s))} s"
    )
    with pytest.raises(ValueError, match=message):
        _digitize(readout, tmp_path / "digitizer.h5")


def test_an_event_of_two_sampling_periods_is_digitized(tmp_path):
    readout = tmp_path / "readout.h5"
    _append(readout, ["a"], 5, np.zeros((1, 3)))
    assert sample_count(3, DT, _settings().period_s) == 2
    _digitize(readout, tmp_path / "digitizer.h5")
    assert read_digitized(tmp_path / "digitizer.h5").events[0].code.shape == (1, 2)


def make_empty_readout(path, electrodes):
    with h5py.File(path, "w") as file:
        file.attrs.create("electrodes", electrodes, dtype=h5py.string_dtype())
        file.attrs["dt"] = DT
        file.attrs["pre_window"] = 10 * DT
        file.attrs.create(
            "pulse_edge", ["falling"] * len(electrodes), dtype=h5py.string_dtype()
        )
        for name, kind in (
            ("event", "int64"),
            ("t0", "float64"),
            ("count", "int64"),
            ("stored", "int64"),
            ("index", "int64"),
            ("voltage", "float64"),
        ):
            file.create_dataset(name, shape=(0,), maxshape=(None,), dtype=kind)


# Deliberate change: create_digitized skipped when the readout has no events
# (the file is then only created by the first appended event).
def test_a_readout_without_events_gives_an_empty_digitizer_file(tmp_path):
    readout = tmp_path / "readout.h5"
    make_empty_readout(readout, ["a", "b"])
    output = tmp_path / "digitizer.h5"
    plots = tmp_path / "plots"
    _digitize(readout, output, plots=2, plot_path=plots)
    settings = _settings()
    with h5py.File(output, "r") as file:
        assert file.attrs["electrodes"].tolist() == ["a", "b"]
        assert file.attrs["sampling_period"] == settings.period_s
        assert file.attrs["lsb_V"] == settings.lsb_V
        assert file.attrs["offset_V"] == settings.offset_V
        assert file.attrs["bits"] == 8
        assert file.attrs["channels"] == 4
        assert file.attrs["device"] == "test"
        assert file.attrs["pulse_edge"].tolist() == ["falling", "falling"]
        assert set(file) == {
            "event",
            "count",
            "stored",
            "index",
            "t0",
            "clipped",
            "noise_only",
            "code",
        }
        assert all(file[name].shape == (0,) for name in file)
    assert read_digitized(output).events == []


# Deliberate change: the y-axis label "Events" of the codes histogram changed.
def test_the_codes_histogram_counts_events_on_its_y_axis(tmp_path, monkeypatch):
    labels = []

    def intercept(figure, folder, name, *suffixes):
        labels.append((name, figure.axes[0].get_xlabel(), figure.axes[0].get_ylabel()))

    monkeypatch.setattr(draw.figures, "save", intercept)
    readout = tmp_path / "readout.h5"
    _append(readout, ["a"], 1, np.zeros((1, 64)))
    _digitize(readout, tmp_path / "digitizer.h5", plots=1, plot_path=tmp_path / "p")
    assert ("codes", "Code", "Events") in labels
