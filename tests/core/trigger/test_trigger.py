import h5py
import numpy as np
import pytest

from raser.core.digitizer.digital_waveforms import (
    DigitizerFileSettings,
    EventDigitized,
    append_digitized,
)
from raser.core.digitizer.digital_waveforms import read_digitized
from raser.core.digitizer.job import write_digitized
from raser.core.digitizer.quantize import quantize, to_volts
from raser.core.digitizer.settings import DigitizerSettings
from raser.core.readout.waveforms import EventWaveforms, append_waveforms
from raser.core.trigger.conditions import TriggerConditions
from raser.core.trigger.crossing import first_crossing
from raser.core.trigger import job
from raser.core.trigger.draw import amplitude
from raser.core.trigger.job import read_triggered, write_triggered


def _settings(channels=3):
    return DigitizerSettings.from_component(
        "test",
        {
            "channels": channels,
            "bits": 12,
            "max_sampling_rate_GSps": 20,
            "response": "none",
            "aperture_jitter_ps": 0,
            "sampling_rate_GSps": 1,
            "full_scale_V": 2,
            "offset_V": 0,
        },
    )


def _write(path, values, t0=None, electrodes=None, file_electrodes=None):
    """Write one event; ``file_electrodes`` are all electrodes of the file, if more than stored."""
    config = _settings(max(3, len(values)))
    codes, clipped = quantize(np.asarray(values, dtype=float), config)
    names = ["a", "b", "c"][: len(values)] if electrodes is None else electrodes
    all_names = names if file_electrodes is None else file_electrodes
    starts = np.zeros(len(names)) if t0 is None else np.asarray(t0, dtype=float)
    append_digitized(
        path,
        all_names,
        DigitizerFileSettings.from_settings(config, "test"),
        EventDigitized(
            1, codes, clipped, starts, names, np.zeros(len(names), dtype=bool)
        ),
        ["falling"] * len(all_names),
    )


def test_first_crossing_interpolates_both_directions():
    assert first_crossing([1.0, 0.0], 0.25, "falling", 2.0, 4.0) == 5.0
    assert first_crossing([-1.0, 1.0], 0.25, "rising", 2.0, 4.0) == 4.5


# Page behaviour (edge trigger): a record whose first point is already beyond
# the level, on the side the signal moves to, counts only the crossing after the
# signal has returned to the near side. Deliberate changes that break these
# tests: the crossing test ignoring the direction, or accepting previous == L
# at the start (previous >= L >= current for a falling slope).
@pytest.mark.parametrize(
    "volts, slope",
    [
        ([-0.5, 0.5, -0.5], "falling"),
        ([0.5, -0.5, 0.5], "rising"),
    ],
)
def test_a_record_starting_beyond_the_level_counts_only_the_return_crossing(
    volts, slope
):
    # the second step crosses 0 half-way between the second and third point,
    # at t = 1 + 0.5 in units of the period; the first step is the wrong way
    assert first_crossing(volts, 0.0, slope, 0.0, 1.0) == 1.5


@pytest.mark.parametrize(
    "volts, slope", [([-0.5, -0.4, -0.6], "falling"), ([0.5, 0.4, 0.6], "rising")]
)
def test_a_record_that_never_returns_to_the_near_side_does_not_cross(volts, slope):
    assert first_crossing(volts, 0.0, slope, 0.0, 1.0) is None


@pytest.mark.parametrize(
    "volts, slope",
    [
        ([0.0, -0.5, 0.5, -0.5], "falling"),
        ([0.0, 0.5, -0.5, 0.5], "rising"),
    ],
)
def test_a_record_starting_on_the_level_has_no_crossing_at_its_start(volts, slope):
    # previous == L is not previous > L, so the first step is not a crossing;
    # the step from the third to the fourth point crosses at 2 + 0.5
    assert first_crossing(volts, 0.0, slope, 0.0, 1.0) == 2.5


def test_edge_trigger_records_both_directions(tmp_path):
    path = tmp_path / "digitizer.h5"
    falling = tmp_path / "falling.h5"
    rising = tmp_path / "rising.h5"
    _write(path, [[1.0, -1.0, -1.0], [-1.0, 1.0, 1.0]])
    write_triggered(
        path,
        falling,
        TriggerConditions.from_component(
            {"mode": "edge", "source": "CH1", "level_V": 0.0, "slope": "falling"}
        ),
        plot_path=tmp_path / "plots",
    )
    write_triggered(
        path,
        rising,
        TriggerConditions.from_component(
            {"mode": "edge", "source": "CH2", "level_V": 0.0, "slope": "rising"}
        ),
        plot_path=tmp_path / "plots",
    )
    np.testing.assert_allclose(read_triggered(falling).trigger_time, [0.5e-9])
    np.testing.assert_allclose(read_triggered(rising).trigger_time, [0.5e-9])


def test_edge_trigger_of_a_record_starting_on_the_far_side_records_the_return_crossing(
    tmp_path,
):
    path = tmp_path / "digitizer.h5"
    output = tmp_path / "trigger.h5"
    _write(path, [[-1.0, 1.0, -1.0]])
    conditions = TriggerConditions.from_component(
        {"mode": "edge", "source": "CH1", "level_V": 0.0, "slope": "falling"}
    )
    write_triggered(path, output, conditions, plot_path=tmp_path / "plots")
    np.testing.assert_allclose(read_triggered(output).trigger_time, [1.5e-9])


def test_pattern_requires_all_channels_and_uses_intersection_start(tmp_path):
    path = tmp_path / "digitizer.h5"
    output = tmp_path / "trigger.h5"
    _write(path, [[1.0, -1.0, -1.0], [1.0, 1.0, -1.0]])
    conditions = TriggerConditions.from_component(
        {
            "mode": "pattern",
            "channels": {
                "CH1": {"level_V": 0.0, "state": "low"},
                "CH2": {"level_V": 0.0, "state": "low"},
            },
        }
    )
    write_triggered(path, output, conditions, plot_path=tmp_path / "plots")
    np.testing.assert_allclose(read_triggered(output).trigger_time, [1.5e-9])


def test_pattern_missing_channel_does_not_record(tmp_path):
    path = tmp_path / "digitizer.h5"
    output = tmp_path / "trigger.h5"
    _write(path, [[1.0, -1.0, -1.0]], electrodes=["a"], file_electrodes=["a", "b"])
    conditions = TriggerConditions.from_component(
        {
            "mode": "pattern",
            "channels": {
                "CH1": {"level_V": 0.0, "state": "low"},
                "CH2": {"level_V": 0.0, "state": "low"},
            },
        }
    )
    write_triggered(path, output, conditions, plot_path=tmp_path / "plots")
    assert read_triggered(output).event.size == 0


def test_pattern_uses_different_electrode_t0_values(tmp_path):
    path = tmp_path / "digitizer.h5"
    output = tmp_path / "trigger.h5"
    _write(path, [[1.0, -1.0], [1.0, -1.0]], t0=[0.0, 0.2e-9])
    conditions = TriggerConditions.from_component(
        {
            "mode": "pattern",
            "channels": {
                "CH1": {"level_V": 0.0, "state": "low"},
                "CH2": {"level_V": 0.0, "state": "low"},
            },
        }
    )
    write_triggered(path, output, conditions, plot_path=tmp_path / "plots")
    np.testing.assert_allclose(read_triggered(output).trigger_time, [0.7e-9])


def test_pattern_starting_already_valid_must_leave_and_reenter(tmp_path):
    path = tmp_path / "digitizer.h5"
    output = tmp_path / "trigger.h5"
    _write(path, [[-1.0, -1.0, 1.0], [-1.0, -1.0, 1.0]])
    conditions = TriggerConditions.from_component(
        {
            "mode": "pattern",
            "channels": {
                "CH1": {"level_V": 0.0, "state": "low"},
                "CH2": {"level_V": 0.0, "state": "low"},
            },
        }
    )
    write_triggered(path, output, conditions, plot_path=tmp_path / "plots")
    assert read_triggered(output).event.size == 0


def test_trigger_file_contains_only_documented_content(tmp_path):
    path = tmp_path / "digitizer.h5"
    output = tmp_path / "trigger.h5"
    _write(path, [[1.0, -1.0, -1.0]])
    write_triggered(
        path,
        output,
        TriggerConditions.from_component(
            {"mode": "edge", "source": "CH1", "level_V": 0.0, "slope": "falling"}
        ),
        plot_path=tmp_path / "plots",
    )
    with h5py.File(output, "r") as file:
        assert set(file) == {"event", "trigger_time"}
        assert file["event"].dtype == np.dtype("int64")
        assert file["trigger_time"].dtype == np.dtype("float64")
        assert file.attrs["events_seen"] == 1


def test_pattern_valid_from_the_start_of_the_later_channel_does_not_trigger(tmp_path):
    # both channels are low throughout; the second starts 0.2 ns later, so the
    # pattern holds from the first moment both are seen and never becomes valid
    path = tmp_path / "digitizer.h5"
    output = tmp_path / "trigger.h5"
    _write(path, [[-1.0, -1.0, -1.0], [-1.0, -1.0, -1.0]], t0=[0.0, 0.2e-9])
    conditions = TriggerConditions.from_component(
        {
            "mode": "pattern",
            "channels": {
                "CH1": {"level_V": 0.0, "state": "low"},
                "CH2": {"level_V": 0.0, "state": "low"},
            },
        }
    )
    write_triggered(path, output, conditions, plot_path=tmp_path / "plots")
    assert read_triggered(output).event.size == 0


def test_amplitude_is_the_extreme_towards_the_trigger_direction():
    volts = [0.2, -0.5, 0.7, 0.1]
    assert amplitude(volts, "falling") == -0.5
    assert amplitude(volts, "low") == -0.5
    assert amplitude(volts, "rising") == 0.7
    assert amplitude(volts, "high") == 0.7


def _write_events(path, traces):
    config = _settings(3)
    for number, values in traces.items():
        codes, clipped = quantize(np.asarray([values], dtype=float), config)
        append_digitized(
            path,
            ["a"],
            DigitizerFileSettings.from_settings(config, "test"),
            EventDigitized(
                number, codes, clipped, np.zeros(1), ["a"], np.zeros(1, dtype=bool)
            ),
            ["falling"],
        )


def test_write_triggered_hands_recorded_and_discarded_amplitudes_to_the_plot(
    tmp_path, monkeypatch
):
    path = tmp_path / "digitizer.h5"
    _write_events(
        path,
        {
            1: [1.0, -0.5, 0.0],
            2: [1.0, -0.8, 0.5],
            3: [1.0, 0.25, 0.5],
        },
    )
    captured = []
    monkeypatch.setattr(
        job, "draw_trigger_amplitude", lambda folder, panels: captured.append(panels)
    )
    write_triggered(
        path,
        tmp_path / "trigger.h5",
        TriggerConditions.from_component(
            {"mode": "edge", "source": "CH1", "level_V": -0.25, "slope": "falling"}
        ),
        plot_path=tmp_path / "plots",
    )
    ((panel,),) = captured
    title, recorded, discarded, level = panel
    lsb = _settings(3).lsb_V
    assert title == "CH1"
    np.testing.assert_allclose(recorded, [-0.5, -0.8], atol=lsb)
    np.testing.assert_allclose(discarded, [0.25], atol=lsb)
    assert level == -0.25


def _midpoint_level(code=2048):
    """Voltage a sample of ``code`` is read back at: exactly a level that sample sits on."""
    config = _settings(3)
    return float(to_volts(code, config.bits, config.lsb_V, config.offset_V))


def _edge(level, slope, source="CH1"):
    return TriggerConditions.from_component(
        {"mode": "edge", "source": source, "level_V": level, "slope": slope}
    )


# Deliberate change that breaks the attribution tests: the crossing test of
# first_crossing read as previous >= L > current (falling) or previous <= L <
# current (rising), so that a sample sitting on the level belongs to the next step.
@pytest.mark.parametrize(
    "slope, volts, expected_step",
    [
        ("falling", [1.0, "L", 1.0, -1.0], 1.0),
        ("rising", [-1.0, "L", -1.0, 1.0], 1.0),
    ],
)
def test_a_sample_on_the_level_is_the_crossing_for_the_step_that_reaches_it(
    slope, volts, expected_step
):
    level = 0.0
    values = [level if value == "L" else value for value in volts]
    # falling: previous > L >= current, rising: previous < L <= current; the
    # step into the sample on the level crosses exactly at that sample
    assert first_crossing(values, level, slope, 0.0, 1.0) == expected_step


@pytest.mark.parametrize(
    "slope, volts",
    [("falling", [0.0, 1.0, 0.0]), ("rising", [0.0, -1.0, 0.0])],
)
def test_starting_on_the_level_and_coming_back_onto_it_crosses_at_the_return(
    slope, volts
):
    # no crossing at the start (previous == L); the step from 1 (or -1) down
    # onto the level is previous > L >= current: it crosses at the third point
    assert first_crossing(volts, 0.0, slope, 0.0, 1.0) == 2.0


@pytest.mark.parametrize(
    "slope, volts",
    [
        ("falling", [0.5, None, 0.5, -0.5]),
        ("rising", [-0.5, None, -0.5, 0.5]),
    ],
)
def test_the_written_file_attributes_a_sample_on_the_level_to_the_step_into_it(
    tmp_path, slope, volts
):
    level = _midpoint_level()
    path = tmp_path / "digitizer.h5"
    output = tmp_path / "trigger.h5"
    _write(path, [[level if value is None else value for value in volts]])
    # the stored code of the middle sample reads back at exactly the level
    assert quantize(np.array([[level]]), _settings(3))[0][0, 0] == 2048
    write_triggered(path, output, _edge(level, slope), plot_path=tmp_path / "plots")
    np.testing.assert_allclose(read_triggered(output).trigger_time, [1e-9], rtol=1e-12)


@pytest.mark.parametrize(
    "slope, volts, expected_ns",
    [
        ("falling", [None, -0.5, 0.5, -0.5], 2.5),
        ("rising", [None, 0.5, -0.5, 0.5], 2.5),
    ],
)
def test_a_record_starting_on_the_level_triggers_on_the_next_real_crossing(
    tmp_path, slope, volts, expected_ns
):
    level = _midpoint_level()
    path = tmp_path / "digitizer.h5"
    output = tmp_path / "trigger.h5"
    _write(path, [[level if value is None else value for value in volts]])
    write_triggered(path, output, _edge(level, slope), plot_path=tmp_path / "plots")
    np.testing.assert_allclose(
        read_triggered(output).trigger_time, [expected_ns * 1e-9], atol=2e-12
    )


# Deliberate change that breaks the "high" tests: the state test of
# state_intervals for "high" made the same as for "low".
def _pattern(states):
    return TriggerConditions.from_component(
        {
            "mode": "pattern",
            "channels": {
                channel: {"level_V": 0.0, "state": state}
                for channel, state in states.items()
            },
        }
    )


def test_pattern_state_high_starts_when_every_channel_is_above_its_level(tmp_path):
    path = tmp_path / "digitizer.h5"
    output = tmp_path / "trigger.h5"
    # CH1 is above 0 from 0.5 ns, CH2 from 1.5 ns: both from 1.5 ns
    _write(path, [[-1.0, 1.0, 1.0], [-1.0, -1.0, 1.0]])
    write_triggered(
        path, output, _pattern({"CH1": "high", "CH2": "high"}), tmp_path / "plots"
    )
    np.testing.assert_allclose(
        read_triggered(output).trigger_time, [1.5e-9], atol=1e-12
    )


def test_pattern_state_high_does_not_trigger_on_a_channel_that_stays_low(tmp_path):
    path = tmp_path / "digitizer.h5"
    output = tmp_path / "trigger.h5"
    _write(path, [[-1.0, 1.0, 1.0], [1.0, -1.0, -1.0]])
    write_triggered(
        path, output, _pattern({"CH1": "high", "CH2": "high"}), tmp_path / "plots"
    )
    assert read_triggered(output).event.size == 0


def test_pattern_may_mix_high_and_low_states(tmp_path):
    path = tmp_path / "digitizer.h5"
    output = tmp_path / "trigger.h5"
    # CH1 high from 0.5 ns; CH2 low from 1.5 ns
    _write(path, [[-1.0, 1.0, 1.0], [1.0, 1.0, -1.0]])
    write_triggered(
        path, output, _pattern({"CH1": "high", "CH2": "low"}), tmp_path / "plots"
    )
    np.testing.assert_allclose(
        read_triggered(output).trigger_time, [1.5e-9], atol=1e-12
    )


# Deliberate change that breaks the CH9 test: device_of returning
# place % channels (CH9 would land on the first device), or the channel-to-place
# map of TriggerCondition.place shifted.
def test_channel_nine_of_eight_channel_devices_is_on_the_second_device_and_triggers(
    tmp_path,
):
    config = DigitizerSettings.from_component(
        "test",
        {
            "channels": 8,
            "bits": 12,
            "max_sampling_rate_GSps": 20,
            "response": "none",
            "aperture_jitter_ps": 0,
            "sampling_rate_GSps": 16,
            "full_scale_V": 2,
            "offset_V": 0,
        },
    )
    dt, bins = 50e-12, 80
    electrodes = [f"e{number}" for number in range(1, 10)]
    centres = (np.arange(bins) + 0.5) * dt
    # CH9 falls linearly from +0.5 V to -0.5 V in 4 ns and crosses 0 V at 2 ns;
    # the others stay at 0 V
    voltage = np.zeros((9, bins))
    voltage[8] = 0.5 - 0.25e9 * centres
    readout = tmp_path / "readout.h5"
    append_waveforms(
        readout,
        electrodes,
        dt,
        EventWaveforms(1, 0.0, voltage, electrodes),
        pulse_edge=["falling"] * 9,
    )
    digitizer = tmp_path / "digitizer.h5"
    write_digitized(
        readout, digitizer, config, "test", 0, 0, tmp_path / "p", lambda event: []
    )
    event = read_digitized(digitizer).events[0]
    assert len(set(event.t0[:8])) == 1
    assert event.t0[8] != event.t0[0]
    output = tmp_path / "trigger.h5"
    write_triggered(
        digitizer, output, _edge(0.0, "falling", "CH9"), plot_path=tmp_path / "plots"
    )
    triggered = read_triggered(output)
    np.testing.assert_array_equal(triggered.event, [1])
    # the ramp is reproduced exactly; the code step of 0.49 mV on a slope of
    # 0.25 V/ns moves the crossing by at most 2 ps
    np.testing.assert_allclose(triggered.trigger_time, [2e-9], atol=5e-12)
    other = tmp_path / "other.h5"
    write_triggered(
        digitizer, other, _edge(0.0, "falling", "CH1"), plot_path=tmp_path / "plots"
    )
    assert read_triggered(other).event.size == 0


# Deliberate change: the first line of the number() check in
# TriggerConditions replaced so that a bool or a string level is accepted.
@pytest.mark.parametrize("level", ["0.1", True, False, None])
def test_edge_and_pattern_levels_reject_strings_and_bools(level):
    with pytest.raises(ValueError, match="level_V"):
        TriggerConditions.from_component(
            {"mode": "edge", "source": "CH1", "level_V": level, "slope": "falling"}
        )
    with pytest.raises(ValueError, match="level_V"):
        TriggerConditions.from_component(
            {
                "mode": "pattern",
                "channels": {"CH1": {"level_V": level, "state": "low"}},
            }
        )


# Deliberate change: "slope" taken out of the keys an edge condition requires.
def test_a_missing_slope_is_named():
    with pytest.raises(ValueError, match="'slope'"):
        TriggerConditions.from_component(
            {"mode": "edge", "source": "CH1", "level_V": 0.0}
        )


def test_a_missing_state_is_named():
    with pytest.raises(ValueError, match="'state'"):
        TriggerConditions.from_component(
            {"mode": "pattern", "channels": {"CH1": {"level_V": 0.0}}}
        )


# Deliberate change: the check of the condition channels against the number of
# electrodes removed from write_triggered.
@pytest.mark.parametrize("plots_exists", [False, True])
@pytest.mark.parametrize("mode", ["edge", "pattern"])
def test_a_channel_beyond_the_electrodes_is_refused_before_any_event(
    tmp_path, plots_exists, mode
):
    path = tmp_path / "digitizer.h5"
    names = [f"e{number}" for number in range(1, 9)]
    _write(path, [[1.0, -1.0, -1.0]] * 8, electrodes=names)
    plots = tmp_path / "plots"
    if plots_exists:
        plots.mkdir()
    conditions = (
        _edge(0.0, "falling", "CH9")
        if mode == "edge"
        else _pattern({"CH1": "low", "CH9": "low"})
    )
    output = tmp_path / "trigger.h5"
    with pytest.raises(ValueError, match=r"CH9.*8 electrodes"):
        write_triggered(path, output, conditions, plot_path=plots)
    assert not output.exists()
    assert not plots.exists() or not list(plots.iterdir())


def _make_empty_readout(path, electrodes, dt):
    with h5py.File(path, "w") as file:
        file.attrs.create("electrodes", electrodes, dtype=h5py.string_dtype())
        file.attrs["dt"] = dt
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


# Deliberate change: create_digitized skipped when the readout has no events.
def test_a_readout_without_events_gives_zero_events_seen_and_empty_datasets(tmp_path):
    readout = tmp_path / "readout.h5"
    _make_empty_readout(readout, ["a", "b"], 50e-12)
    digitizer = tmp_path / "digitizer.h5"
    plots = tmp_path / "plots"
    write_digitized(
        readout, digitizer, _settings(), "test", 0, 2, plots, lambda event: []
    )
    assert read_digitized(digitizer).events == []
    output = tmp_path / "trigger.h5"
    write_triggered(digitizer, output, _edge(0.0, "falling"), plot_path=plots)
    with h5py.File(output, "r") as file:
        assert file.attrs["events_seen"] == 0
        assert file["event"].shape == (0,)
        assert file["trigger_time"].shape == (0,)
    triggered = read_triggered(output)
    assert triggered.events_seen == 0
    assert triggered.event.size == 0
    assert not (plots / "trigger_amplitude.png").exists()


# Deliberate changes: the draw call of write_triggered skipped, and its guard
# "some event has a waveform" removed (so that an empty figure is drawn).
def test_write_triggered_always_draws_the_trigger_amplitude(tmp_path):
    path = tmp_path / "digitizer.h5"
    _write(path, [[1.0, -1.0, -1.0]])
    plots = tmp_path / "plots"
    write_triggered(path, tmp_path / "trigger.h5", _edge(0.0, "falling"), plots)
    assert (plots / "trigger_amplitude.png").exists()


def test_write_triggered_draws_nothing_when_no_event_has_a_waveform(tmp_path):
    path = tmp_path / "digitizer.h5"
    _write(
        path,
        np.zeros((0, 3)),
        electrodes=[],
        file_electrodes=["a", "b", "c"],
    )
    plots = tmp_path / "plots"
    output = tmp_path / "trigger.h5"
    write_triggered(path, output, _edge(0.0, "falling"), plots)
    assert read_triggered(output).events_seen == 1
    assert not plots.exists()
