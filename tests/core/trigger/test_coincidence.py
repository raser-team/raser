from itertools import product

import h5py
import numpy as np
import pytest

from raser.core.digitizer.digital_waveforms import (
    DigitizerFileSettings,
    EventDigitized,
    append_digitized,
)
from raser.core.digitizer.quantize import quantize
from raser.core.digitizer.settings import DigitizerSettings
from raser.core.trigger.coincidence import (
    CoincidenceSettings,
    coincidence_time,
    evaluate,
    parse_require,
)
from raser.core.trigger import job
from raser.core.trigger.job import read_triggered, write_coincidence

NS = 1e-9


def _truth_table(text, slots):
    expression = parse_require(text, slots)
    table = {}
    for flags in product([False, True], repeat=len(slots)):
        hits = {slot for slot, flag in zip(slots, flags, strict=True) if flag}
        table[frozenset(hits)] = evaluate(expression, hits)
    return table


def test_and_binds_tighter_than_or():
    slots = ["a", "b", "c"]
    plain = _truth_table("a AND b OR c", slots)
    assert plain == _truth_table("(a AND b) OR c", slots)
    other = _truth_table("a AND (b OR c)", slots)
    assert plain[frozenset({"c"})] is True
    assert other[frozenset({"c"})] is False


def test_all_and_any_join_every_slot():
    slots = ["a", "b", "c"]
    everything = _truth_table("all", slots)
    anything = _truth_table("any", slots)
    for hits in everything:
        assert everything[hits] is (len(hits) == 3)
        assert anything[hits] is (len(hits) >= 1)


def test_at_least_two_of_three_for_all_eight_hit_combinations():
    table = _truth_table("AT_LEAST(2: a, b, c)", ["a", "b", "c"])
    assert len(table) == 8
    for hits, value in table.items():
        assert value is (len(hits) >= 2)


def test_at_least_mixes_with_and():
    slots = ["l1", "l2", "l3", "dut"]
    table = _truth_table("AT_LEAST(2: l1, l2, l3) AND dut", slots)
    assert table[frozenset({"l1", "l3", "dut"})] is True
    assert table[frozenset({"l1", "l3"})] is False
    assert table[frozenset({"l1", "dut"})] is False


@pytest.mark.parametrize(
    "text, match",
    [
        ("a AND d", "'d'"),
        ("a AND b", "'c'"),
        ("(a AND b OR c", "ends|expected"),
        ("a AND b) OR c", "unexpected"),
        ("a AND OR b OR c", "unexpected"),
        ("a AND b OR", "ends"),
        ("AT_LEAST(0: a, b, c)", "from 1 through 3"),
        ("AT_LEAST(4: a, b, c)", "from 1 through 3"),
        ("AT_LEAST(1.5: a, b, c)", "unexpected character"),
        ("AT_LEAST(x: a, b, c)", "integer"),
        ("a & b | c", "unexpected character"),
    ],
)
def test_wrong_expressions_raise_value_error_with_the_reason(text, match):
    with pytest.raises(ValueError, match=match):
        parse_require(text, ["a", "b", "c"])


def test_a_hit_slot_outside_the_expression_is_an_error():
    expression = parse_require("a AND b", ["a", "b"])
    with pytest.raises(ValueError, match="'z'"):
        evaluate(expression, {"a", "z"})


@pytest.mark.parametrize(
    "text, slots, window_ns, expected_ns",
    [
        ("a AND b", ["a", "b"], 5.0, 3.0),
        ("a AND c", ["a", "c"], 5.0, None),
        ("a AND c", ["a", "c"], None, 10.0),
        ("a OR c", ["a", "c"], 5.0, 0.0),
        ("AT_LEAST(2: a, b, c)", ["a", "b", "c"], 5.0, 3.0),
    ],
)
def test_coincidence_time_follows_the_window(text, slots, window_ns, expected_ns):
    all_times = {"a": 0.0, "b": 3.0 * NS, "c": 10.0 * NS}
    hit_times = {slot: all_times[slot] for slot in slots}
    window = None if window_ns is None else window_ns * NS
    result = coincidence_time(parse_require(text, slots), hit_times, window)
    if expected_ns is None:
        assert result is None
    else:
        assert result == expected_ns * NS


def test_coincidence_time_without_hits_is_none():
    assert coincidence_time(parse_require("any", ["a", "b"]), {}, None) is None


def test_coincidence_settings_resolve_levels_and_window():
    values = {
        "level_V": {"dut": -0.002, "ref": -0.005},
        "slope": "falling",
        "require": "dut AND ref",
        "coincidence_window_ns": 5,
    }
    settings = CoincidenceSettings.from_component(values, ["dut", "ref"])
    assert settings.level_V == {"dut": -0.002, "ref": -0.005}
    assert settings.coincidence_window_s == pytest.approx(5e-9, rel=1e-12)
    shared = CoincidenceSettings.from_component(
        {**values, "level_V": -0.003, "coincidence_window_ns": None}, ["dut", "ref"]
    )
    assert shared.level_V == {"dut": -0.003, "ref": -0.003}
    assert shared.coincidence_window_s is None


@pytest.mark.parametrize(
    "change, match",
    [
        ({"level_V": {"dut": -0.002}}, "level_V"),
        ({"level_V": {"dut": 0, "ref": 0, "x": 0}}, "level_V"),
        ({"slope": "up"}, "slope"),
        ({"coincidence_window_ns": -1}, "coincidence_window_ns"),
        ({"coincidence_window_ns": "5"}, "coincidence_window_ns"),
        ({"require": "dut"}, "'ref'"),
        ({"extra": 1}, "unknown"),
    ],
)
def test_coincidence_settings_reject_wrong_values(change, match):
    values = {
        "level_V": -0.002,
        "slope": "falling",
        "require": "all",
        "coincidence_window_ns": None,
        **change,
    }
    with pytest.raises(ValueError, match=match):
        CoincidenceSettings.from_component(values, ["dut", "ref"])


def test_coincidence_settings_need_every_key():
    values = {"level_V": -0.002, "slope": "falling", "require": "all"}
    with pytest.raises(ValueError, match="coincidence_window_ns"):
        CoincidenceSettings.from_component(values, ["dut", "ref"])


def _digitizer_config():
    return DigitizerSettings.from_component(
        "test",
        {
            "channels": 8,
            "bits": 12,
            "max_sampling_rate_GSps": 20,
            "response": "none",
            "aperture_jitter_ps": 0,
            "sampling_rate_GSps": 1,
            "full_scale_V": 2,
            "offset_V": 0,
        },
    )


def _write_events(path, electrodes, events):
    """``events`` maps an event number to ``{electrode: (volts, t0_s)}``."""
    config = _digitizer_config()
    for number, traces in events.items():
        names = [name for name in electrodes if name in traces]
        volts = np.array([traces[name][0] for name in names], dtype=float).reshape(
            len(names), 4
        )
        codes, clipped = quantize(volts, config)
        append_digitized(
            path,
            electrodes,
            DigitizerFileSettings.from_settings(config, "test"),
            EventDigitized(
                number,
                codes,
                clipped,
                np.array([traces[name][1] for name in names], dtype=float),
                names,
                np.zeros(len(names), dtype=bool),
            ),
            ["falling"] * len(electrodes),
        )


FALL_AT_0 = [1.0, -1.0, -1.0, -1.0]
FALL_AT_1 = [1.0, 1.0, -1.0, -1.0]
FLAT = [1.0, 1.0, 1.0, 1.0]
FALL_TO_HALF = [1.0, -0.5, -0.5, -0.5]
FALL_TO_THREE_QUARTERS = [1.0, -0.75, -0.75, -0.75]
FALL_TO_QUARTER = [1.0, -0.25, -0.25, -0.25]


def _two_slot_files(tmp_path):
    dut = tmp_path / "dut.h5"
    ref = tmp_path / "ref.h5"
    _write_events(
        dut,
        ["a"],
        {
            1: {"a": (FALL_AT_0, 0.0)},
            2: {"a": (FALL_AT_0, 0.0)},
            3: {"a": (FALL_AT_0, 0.0)},
        },
    )
    _write_events(
        ref,
        ["c"],
        {
            1: {"c": (FALL_AT_1, 0.2 * NS)},
            2: {"c": (FLAT, 0.2 * NS)},
            3: {},
            4: {"c": (FALL_AT_0, 0.2 * NS)},
        },
    )
    return {"dut": dut, "ref": ref}


def _run(tmp_path, digitizer_paths, **change):
    values = {
        "level_V": 0.0,
        "slope": "falling",
        "require": "all",
        "coincidence_window_ns": None,
        **change,
    }
    settings = CoincidenceSettings.from_component(values, list(digitizer_paths))
    outputs = {slot: tmp_path / f"trigger_{slot}.h5" for slot in digitizer_paths}
    write_coincidence(digitizer_paths, outputs, settings, plot_path=tmp_path / "plots")
    return {slot: read_triggered(path) for slot, path in outputs.items()}, outputs


def test_all_records_only_events_hit_in_every_slot_at_the_later_hit_time(tmp_path):
    result, _ = _run(tmp_path, _two_slot_files(tmp_path))
    dut_hit, ref_hit = 0.5 * NS, 0.2 * NS + 1.5 * NS
    np.testing.assert_array_equal(result["dut"].event, [1])
    assert result["dut"].trigger_time[0] == pytest.approx(ref_hit, rel=1e-9, abs=0)
    assert result["dut"].trigger_time[0] > dut_hit


def test_any_records_events_hit_in_one_slot_at_its_hit_time(tmp_path):
    result, _ = _run(tmp_path, _two_slot_files(tmp_path), require="any")
    np.testing.assert_array_equal(result["dut"].event, [1, 2, 3, 4])
    expected = [0.5 * NS, 0.5 * NS, 0.5 * NS, 0.2 * NS + 0.5 * NS]
    np.testing.assert_allclose(result["dut"].trigger_time, expected, rtol=1e-9, atol=0)


def test_events_seen_counts_the_union_of_the_event_numbers(tmp_path):
    result, _ = _run(tmp_path, _two_slot_files(tmp_path))
    assert result["dut"].events_seen == 4
    assert result["ref"].events_seen == 4


def test_the_trigger_files_of_all_slots_are_identical(tmp_path):
    result, outputs = _run(tmp_path, _two_slot_files(tmp_path), require="any")
    np.testing.assert_array_equal(result["dut"].event, result["ref"].event)
    np.testing.assert_array_equal(
        result["dut"].trigger_time, result["ref"].trigger_time
    )
    with (
        h5py.File(outputs["dut"], "r") as first,
        h5py.File(outputs["ref"], "r") as second,
    ):
        assert set(first) == set(second) == {"event", "trigger_time"}
        assert first.attrs["events_seen"] == second.attrs["events_seen"]


def test_a_stricter_level_in_one_slot_removes_the_event(tmp_path):
    paths = _two_slot_files(tmp_path)
    loose, _ = _run(tmp_path, paths, level_V={"dut": 0.0, "ref": 0.0})
    strict, _ = _run(tmp_path, paths, level_V={"dut": 0.0, "ref": -1.5})
    np.testing.assert_array_equal(loose["dut"].event, [1])
    assert strict["dut"].event.size == 0


def test_the_time_window_separates_events_hit_too_far_apart(tmp_path):
    paths = _two_slot_files(tmp_path)
    narrow, _ = _run(tmp_path, paths, coincidence_window_ns=1.0)
    wide, _ = _run(tmp_path, paths, coincidence_window_ns=2.0)
    assert narrow["dut"].event.size == 0
    np.testing.assert_array_equal(wide["dut"].event, [1])


def test_the_earliest_crossing_electrode_sets_the_slot_hit_time(tmp_path):
    path = tmp_path / "dut.h5"
    _write_events(
        path,
        ["a", "b"],
        {1: {"a": (FALL_AT_1, 0.0), "b": (FALL_AT_0, 0.2 * NS)}},
    )
    result, _ = _run(tmp_path, {"dut": path})
    np.testing.assert_allclose(
        result["dut"].trigger_time, [0.2 * NS + 0.5 * NS], rtol=1e-9, atol=0
    )


def test_write_coincidence_needs_a_path_for_every_slot(tmp_path):
    paths = _two_slot_files(tmp_path)
    settings = CoincidenceSettings.from_component(
        {
            "level_V": 0.0,
            "slope": "falling",
            "require": "all",
            "coincidence_window_ns": None,
        },
        ["dut", "ref"],
    )
    with pytest.raises(ValueError, match="slots"):
        write_coincidence(
            paths,
            {"dut": tmp_path / "x.h5"},
            settings,
            plot_path=tmp_path / "plots",
        )


def test_write_coincidence_hands_slot_amplitudes_to_the_plot(tmp_path, monkeypatch):
    dut = tmp_path / "dut.h5"
    ref = tmp_path / "ref.h5"
    _write_events(
        dut,
        ["a", "b"],
        {
            1: {"a": (FALL_TO_HALF, 0.0), "b": (FALL_TO_THREE_QUARTERS, 0.0)},
            2: {"a": (FLAT, 0.0), "b": (FALL_TO_QUARTER, 0.0)},
        },
    )
    _write_events(ref, ["c"], {1: {"c": (FALL_TO_QUARTER, 0.0)}, 2: {"c": (FLAT, 0.0)}})
    settings = CoincidenceSettings.from_component(
        {
            "level_V": -0.125,
            "slope": "falling",
            "require": "all",
            "coincidence_window_ns": None,
        },
        ["dut", "ref"],
    )
    captured = []
    monkeypatch.setattr(
        job, "draw_trigger_amplitude", lambda folder, panels: captured.append(panels)
    )
    outputs = {slot: tmp_path / f"trigger_{slot}.h5" for slot in ("dut", "ref")}
    write_coincidence(
        {"dut": dut, "ref": ref},
        outputs,
        settings,
        plot_path=tmp_path / "plots",
    )
    ((dut_panel, ref_panel),) = captured
    tolerance = 2 * _digitizer_config().lsb_V
    assert dut_panel[0] == "dut"
    np.testing.assert_allclose(dut_panel[1], [-0.75], atol=tolerance)
    np.testing.assert_allclose(dut_panel[2], [-0.25], atol=tolerance)
    assert dut_panel[3] == -0.125
    assert ref_panel[0] == "ref"
    np.testing.assert_allclose(ref_panel[1], [-0.25], atol=tolerance)
    np.testing.assert_allclose(ref_panel[2], [1.0], atol=tolerance)


# Deliberate change: the lower bound of the window in coincidence_time, `>=`
# changed to `>` (a hit exactly one window before the trigger time is outside).
def test_two_hits_exactly_one_window_apart_are_in_one_window():
    expression = parse_require("a AND b", ["a", "b"])
    # binary-exact times, so that the difference is exactly the window
    hit_times = {"a": 0.25, "b": 0.75}
    assert coincidence_time(expression, hit_times, 0.5) == 0.75
    assert coincidence_time(expression, hit_times, 0.25) is None


def test_equal_hit_times_coincide_in_any_window():
    expression = parse_require("a AND b", ["a", "b"])
    for window in (0.0, 1e-9, None):
        assert coincidence_time(expression, {"a": 0.5, "b": 0.5}, window) == 0.5


# Deliberate change: `window_s < 0` in CoincidenceSettings.from_component
# changed to `window_s <= 0`.
def test_a_coincidence_window_of_zero_is_accepted_and_only_equal_hits_coincide():
    values = {
        "level_V": 0.0,
        "slope": "falling",
        "require": "all",
        "coincidence_window_ns": 0,
    }
    settings = CoincidenceSettings.from_component(values, ["dut", "ref"])
    assert settings.coincidence_window_s == 0.0
    expression = settings.require
    assert coincidence_time(expression, {"dut": 1.0, "ref": 1.0}, 0.0) == 1.0
    assert coincidence_time(expression, {"dut": 1.0, "ref": 1.0 + 1e-9}, 0.0) is None


def test_a_zero_window_records_the_event_whose_slots_hit_at_the_same_instant(
    tmp_path,
):
    paths = {}
    for slot in ("dut", "ref"):
        paths[slot] = tmp_path / f"{slot}.h5"
        _write_events(paths[slot], ["a"], {1: {"a": (FALL_AT_1, 0.0)}})
    same, _ = _run(tmp_path, paths, coincidence_window_ns=0)
    np.testing.assert_allclose(same["dut"].trigger_time, [1.5 * NS], rtol=1e-9)
    shifted = tmp_path / "shifted.h5"
    _write_events(shifted, ["a"], {1: {"a": (FALL_AT_1, 0.2 * NS)}})
    apart, _ = _run(
        tmp_path, {"dut": paths["dut"], "ref": shifted}, coincidence_window_ns=0
    )
    assert apart["dut"].event.size == 0


@pytest.mark.parametrize("window", [-1e-9, -0.5, "0", True, False, [0]])
def test_the_coincidence_window_rejects_negative_and_non_numeric_values(window):
    values = {
        "level_V": 0.0,
        "slope": "falling",
        "require": "all",
        "coincidence_window_ns": window,
    }
    with pytest.raises(ValueError, match="coincidence_window_ns"):
        CoincidenceSettings.from_component(values, ["dut", "ref"])


# Deliberate change: number() accepting a bool or a string for level_V.
@pytest.mark.parametrize("wrong", ["0.1", True, False, None])
@pytest.mark.parametrize("shape", ["shared", "per slot"])
def test_coincidence_levels_reject_strings_and_bools(wrong, shape):
    level = wrong if shape == "shared" else {"dut": -0.1, "ref": wrong}
    values = {
        "level_V": level,
        "slope": "falling",
        "require": "all",
        "coincidence_window_ns": None,
    }
    with pytest.raises(ValueError, match="level_V"):
        CoincidenceSettings.from_component(values, ["dut", "ref"])


# Deliberate changes: the draw call of write_coincidence skipped, and its guard
# "some slot has an event with a waveform" removed.
def test_write_coincidence_always_draws_the_trigger_amplitude(tmp_path):
    _run(tmp_path, _two_slot_files(tmp_path))
    assert (tmp_path / "plots" / "trigger_amplitude.png").exists()


def test_write_coincidence_draws_nothing_when_no_event_has_a_waveform(tmp_path):
    paths = {}
    for slot, electrode in (("dut", "a"), ("ref", "c")):
        paths[slot] = tmp_path / f"{slot}.h5"
        _write_events(paths[slot], [electrode], {1: {}, 2: {}})
    result, _ = _run(tmp_path, paths)
    assert result["dut"].events_seen == 2
    assert result["dut"].event.size == 0
    assert not (tmp_path / "plots").exists()
