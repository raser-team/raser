import h5py
import numpy as np
import pytest

from raser.core.digitizer.digital_waveforms import DigitizerFileSettings
from raser.core.digitizer.digital_waveforms import EventDigitized
from raser.core.digitizer.digital_waveforms import append_digitized
from raser.core.readout.waveforms import EventWaveforms
from raser.core.readout.waveforms import append_waveforms
from raser.core.readout.waveforms import read_waveforms
from raser.core.reconstruction.event_table import read_event_table
from raser.stages import reconstruction

# a negative triangle [V]: 2 mV per bin up to 10 mV in bin 6, then down again
TRIANGLE = 1.0e-3 * np.array([0.0, 0, -2, -4, -6, -8, -10, -8, -6, -4, -2, 0, 0])
DT = 1.0e-9
BEFORE = 200  # bins before the triangle
FRACTIONS = (0.2, 0.5)


def _job(folder, scales, count, seed):
    """The readout of job 0 of `count` events in a seed folder; the
    electrodes carry the triangle times `scales`, whose sign gives the edge
    the readout derives for each. Returns the start of the triangle of each
    event."""
    node = folder / "node"
    node.mkdir(parents=True, exist_ok=True)
    names = [f"strip_{k}" for k in range(len(scales[0]))]
    starts = np.random.default_rng(seed).normal(0.0, 1.0e-9, count)
    for number in range(count):
        samples = [
            np.concatenate([np.zeros(BEFORE), scale * TRIANGLE])
            for scale in scales[number % len(scales)]
        ]
        append_waveforms(
            node / "readout.h5",
            names,
            DT,
            BEFORE * DT,
            EventWaveforms(number, starts[number] - BEFORE * DT, np.array(samples)),
            pulse_edge=["falling" if scale > 0 else "rising" for scale in scales[0]],
        )
    return starts


def _run(folder, threshold, amplitude_threshold, edge="falling", fractions=FRACTIONS):
    """The table of the waveforms of the node, as the slice writes it of the
    digitized ones."""
    node = folder / "node"
    reconstruction.tabulate(
        read_waveforms(node / "readout.h5"), node / "readout.h5", node / "reconstruction.h5",
        threshold, amplitude_threshold, fractions, edge,
    )
    return read_event_table(node / "reconstruction.h5")


BITS = 12
LSB = 1.0e-4  # V
PERIOD = 0.5e-9  # s


def _digitized(path, events):
    """A digitizer file of the electrodes left and right: for each event
    number the start [s] and the scale of the triangle of each electrode it
    stored, sampled every PERIOD and quantized as the digitizer does."""
    settings = DigitizerFileSettings(PERIOD, LSB, 0.0, BITS, 4, "toy", BEFORE * PERIOD)
    volts = np.concatenate([np.zeros(BEFORE), TRIANGLE])
    for number, traces in events.items():
        codes = [np.floor(scale * volts / LSB).astype(int) + 2 ** (BITS - 1) for _, scale in traces.values()]
        record = EventDigitized(
            number, np.array(codes), np.zeros(len(traces), dtype=int), np.array([start for start, _ in traces.values()]),
            list(traces), np.zeros(len(traces), dtype=bool),
        )
        append_digitized(path, ["left", "right"], settings, record, ["falling", "falling"])


def _triggered(path, events, seen):
    with h5py.File(path, "w") as file:
        file["event"] = np.array(events, dtype="int64")
        file["trigger_time"] = np.zeros(len(events), dtype="float64")
        file.attrs["events_seen"] = seen


# Deliberate changes: every digitized event given a row, the codes taken as
# volts without the lsb, one start taken for all the electrodes of an event,
# the samples placed half a period late.
def test_the_slice_tabulates_the_digitized_waveforms_of_the_events_the_trigger_recorded(tmp_path) -> None:
    node = tmp_path / "node"
    node.mkdir()
    # the right electrode is of another device, whose clock starts 0.2 ns later
    _digitized(node / "digitizer.h5", {
        3: {"left": (1.0e-9, 1.0), "right": (1.2e-9, 0.5)},
        5: {"left": (0.0, 1.0)},
        8: {"left": (2.0e-9, 1.0), "right": (2.2e-9, 0.5)},
    })
    _triggered(node / "trigger.h5", [3, 8], 3)
    kwargs = {
        "_node_paths": {name: str(node) for name in ("digitizer", "trigger", "reconstruction")},
        "threshold": 3, "amplitude_threshold": 5, "fractions": FRACTIONS, "edge": None,
    }

    assert reconstruction.run(kwargs) is None

    rows = read_event_table(node / "reconstruction.h5").columns
    assert list(rows["event"]) == [3, 8]
    # codes back to volts: the baseline and the peak are both half an lsb
    # above the floor of their step, 10 mV and 5 mV apart
    assert rows["amplitude"] == pytest.approx(np.tile([10.0e-3, 5.0e-3], (2, 1)), rel=1e-9, abs=0)
    # the triangle is symmetric about its sample 6: at t0 + (BEFORE + 6) periods of each electrode
    peak = (BEFORE + 6) * PERIOD
    assert rows["CoG"] == pytest.approx(np.array([[1.0e-9, 1.2e-9], [2.0e-9, 2.2e-9]]) + peak, rel=1e-9, abs=0)


def test_every_event_has_a_row_and_the_large_ones_are_selected(tmp_path) -> None:
    # 10 mV and 4 mV in turn; 5 mV selects the first ones
    starts = _job(tmp_path, [[1.0], [0.4]], 60, seed=4)

    table = _run(tmp_path, 3, 5)

    rows = table.columns
    assert (len(table), table.edges) == (60, ["falling"])
    assert list(rows["event"]) == list(range(60))
    assert list(np.flatnonzero(rows["selected"])) == list(range(0, 60, 2))
    assert rows["amplitude"][:, 0] == pytest.approx(np.tile([10.0e-3, 4.0e-3], 30))
    # bin i of the triangle is centred (i + 0.5) ns after its start; 3 mV is
    # crossed midway from bin 2 to 3 and from 9 to 10 on the 10 mV ones, and
    # three quarters of the way from bin 4 (2.4 mV) to 5 (3.2 mV) on the 4 mV ones
    assert rows["ToA"][:, 0] == pytest.approx(starts + np.tile([3.0e-9, 5.25e-9], 30))
    assert rows["ToT"][0::2, 0] == pytest.approx(np.full(30, 7.0e-9))
    # symmetric about bin 6; 20 % of 10 mV is bin 2 itself, 50 % midway from bin 3 to 4
    assert rows["CoG"][:, 0] == pytest.approx(starts + 6.5e-9)
    assert rows["CFD"][0::2, 0, 0] == pytest.approx(starts[0::2] + 2.5e-9)
    assert rows["CFD"][:, 0, 1] == pytest.approx(starts + 4.0e-9)
    assert rows["area"][0::2, 0] == pytest.approx(np.full(30, 50.0e-3 * DT))


def test_cluster_of_three_strips_weighs_the_strips_above_the_threshold(tmp_path) -> None:
    # strip 0 has 1 mV, below the 3 mV threshold; strips 1 and 2 have 10 and 5
    _job(tmp_path, [[0.1, 1.0, 0.5]], 4, seed=5)

    rows = _run(tmp_path, 3, 4).columns

    assert list(rows["cluster_size"]) == [2] * 4
    assert rows["cluster_center"] == pytest.approx(np.full(4, (1 * 10 + 2 * 5) / 15))
    assert not rows["above"][:, 0].any() and rows["above"][:, 1:].all()
    assert np.isnan(rows["ToA"][:, 0]).all() and np.isnan(rows["CFD"][:, 0]).all()
    # the half of 10 mV and of 5 mV lie at the same time of the triangle
    assert rows["CFD"][:, 1, 1] == pytest.approx(rows["CFD"][:, 2, 1])


def test_event_below_both_thresholds_has_no_cluster(tmp_path) -> None:
    _job(tmp_path, [[0.2]], 3, seed=6)  # 2 mV

    rows = _run(tmp_path, 3, 5).columns

    assert not rows["selected"].any()
    assert list(rows["cluster_size"]) == [0] * 3
    assert np.isnan(rows["cluster_center"]).all()
    assert rows["amplitude"][:, 0] == pytest.approx(np.full(3, 2.0e-3))


def test_thresholds_on_the_other_edge_see_no_pulse(tmp_path) -> None:
    _job(tmp_path, [[1.0]], 3, seed=7)  # 10 mV, falling

    rising = _run(tmp_path, 3, 5, "rising").columns

    assert not rising["above"].any() and not rising["selected"].any()
    # turned over the falling pulse is a dip: nothing rises above the baseline
    assert rising["amplitude"][:, 0] == pytest.approx(np.zeros(3))
    with pytest.raises(ValueError, match="edge 'down': .* rising .* or a falling"):
        _run(tmp_path, 3, 5, "down")


def test_position_reads_and_writes_the_files_of_its_own_slices(tmp_path) -> None:
    node = tmp_path / "node"
    node.mkdir()
    names = {
        f"{name}.{position}": str(node)
        for name in ("digitizer", "trigger", "reconstruction") for position in ("left", "right")
    }
    _digitized(node / "digitizer.left.h5", {7: {"left": (0.0, 1.0)}})
    _triggered(node / "trigger.left.h5", [7], 1)
    kwargs = {"_node_paths": names, "threshold": 3, "amplitude_threshold": 5, "fractions": FRACTIONS, "edge": "falling"}

    assert reconstruction.run(kwargs, "left") is None
    assert reconstruction.run(kwargs, "right") == {"events": 0}  # no currents, nothing digitized or triggered there

    assert list(read_event_table(node / "reconstruction.left.h5").columns["event"]) == [7]
    assert not (node / "reconstruction.right.h5").exists()


def test_event_at_the_amplitude_threshold_is_selected_with_its_cluster(tmp_path) -> None:
    # 10 mV exactly at the amplitude threshold
    _job(tmp_path, [[1.0]], 2, seed=8)

    rows = _run(tmp_path, 3, 10).columns

    assert rows["selected"].all()
    assert list(rows["cluster_size"]) == [1, 1]
    assert rows["cluster_center"] == pytest.approx(np.zeros(2))


def test_event_above_the_amplitude_cut_but_below_the_timing_threshold_is_selected_without_times(tmp_path) -> None:
    # 10 mV: no amplitude cut, a timing threshold of 15 mV
    _job(tmp_path, [[1.0]], 2, seed=9)

    rows = _run(tmp_path, 15, 0).columns

    assert rows["selected"].all()
    assert rows["amplitude"][:, 0] == pytest.approx(np.full(2, 10.0e-3))
    assert not rows["above"].any() and np.isnan(rows["ToA"]).all()


def test_area_is_of_the_lobe_that_holds_the_peak(tmp_path) -> None:
    # -120 mV for one ns, then an undershoot of +120 mV for one ns, on noise
    # far below them; the undershoot of a falling pulse is not its area
    node = tmp_path / "node"
    node.mkdir()
    rng = np.random.default_rng(10)
    samples = np.concatenate(
        [
            rng.normal(0.0, 1.0e-4, BEFORE),
            [0.0, -120.0e-3, 120.0e-3, 0.0],
            rng.normal(0.0, 1.0e-4, 50),
        ]
    )
    samples[BEFORE] = samples[BEFORE + 3] = (
        1.0e-3  # above the baseline on the far sides
    )
    append_waveforms(
        node / "readout.h5",
        ["top"],
        DT,
        BEFORE * DT,
        EventWaveforms(0, 0.0, np.array([samples])),
        pulse_edge=["falling"],
    )

    rows = _run(tmp_path, 50, 100).columns

    assert rows["area"][0, 0] == pytest.approx(120.0e-3 * DT, rel=0.01)


def test_fraction_outside_zero_to_one_is_refused(tmp_path) -> None:
    _job(tmp_path, [[1.0]], 1, seed=11)

    with pytest.raises(ValueError, match=r"fractions \[1.2\]: a constant fraction lies between 0 and 1"):
        _run(tmp_path, 3, 5, fractions=(0.5, 1.2))
    assert not (tmp_path / "node" / "reconstruction.h5").exists()


def test_rising_edge_takes_a_positive_pulse(tmp_path) -> None:
    starts = _job(tmp_path, [[-1.0]], 3, seed=12)  # the triangle upside up: +10 mV

    rows = _run(tmp_path, 3, 5, "rising").columns

    assert rows["selected"].all()
    assert rows["amplitude"][:, 0] == pytest.approx(np.full(3, 10.0e-3))
    assert rows["ToA"][:, 0] == pytest.approx(starts + 3.0e-9)


def test_centre_of_gravity_of_a_lopsided_pulse_is_not_its_peak(tmp_path) -> None:
    node = tmp_path / "node"
    node.mkdir()
    # 4, 10, 6, 4 mV above the 3 mV threshold in bins 1 ... 4 after the 200 before
    samples = np.concatenate(
        [np.zeros(BEFORE), -1.0e-3 * np.array([0.0, 4, 10, 6, 4, 2, 0, 0])]
    )
    append_waveforms(
        node / "readout.h5",
        ["top"],
        DT,
        BEFORE * DT,
        EventWaveforms(0, 0.0, np.array([samples])),
        pulse_edge=["falling"],
    )

    rows = _run(tmp_path, 3, 5).columns

    centres = (BEFORE + np.arange(1, 5) + 0.5) * DT
    assert rows["CoG"][0, 0] == pytest.approx(np.dot(centres, [4, 10, 6, 4]) / 24)
    assert rows["CoG"][0, 0] > (BEFORE + 2.5) * DT  # later than the peak


def test_without_an_edge_each_electrode_takes_the_one_the_readout_derives(tmp_path, capsys) -> None:
    # strip 0 falls by 10 mV, strip 1 rises by 5 mV
    _job(tmp_path, [[1.0, -0.5]], 2, seed=13)

    rows = _run(tmp_path, 3, 4, None).columns

    assert rows["amplitude"] == pytest.approx(np.tile([10.0e-3, 5.0e-3], (2, 1)))
    assert list(rows["cluster_size"]) == [2, 2]
    assert capsys.readouterr().out == ""


def test_given_edge_that_is_not_the_pulse_is_told_and_taken(tmp_path, capsys) -> None:
    _job(tmp_path, [[1.0, -0.5]], 2, seed=13)

    rows = _run(tmp_path, 3, 4, "falling").columns

    assert rows["amplitude"][:, 0] == pytest.approx(np.full(2, 10.0e-3))
    assert not rows["above"][:, 1].any()
    told = capsys.readouterr().out
    assert "edge falling given for strip_1, whose pulse is rising" in told and "strip_0" not in told


def test_event_holds_only_the_strips_it_has_a_signal_on(tmp_path) -> None:
    node = tmp_path / "node"
    node.mkdir()
    names = ["strip_0", "strip_1", "strip_2"]
    samples = np.concatenate([np.zeros(BEFORE), TRIANGLE])
    events = [
        EventWaveforms(0, 0.0, np.array([samples, 0.5 * samples]), ["strip_1", "strip_2"]),
        EventWaveforms(1, 0.0, np.zeros((0, len(samples))), []),  # no current, no waveform
    ]
    for event in events:
        append_waveforms(
            node / "readout.h5",
            names,
            DT,
            BEFORE * DT,
            event,
            pulse_edge=["falling"] * 3,
        )

    rows = _run(tmp_path, 3, 4, None).columns

    assert list(rows["event"]) == [0, 1]
    assert rows["traced"].tolist() == [[False, True, True], [False, False, False]]
    assert rows["amplitude"][0, 1:] == pytest.approx([10.0e-3, 5.0e-3])
    assert np.isnan(rows["amplitude"][0, 0]) and np.isnan(rows["amplitude"][1]).all()
    assert rows["selected"].tolist() == [True, False]
    assert list(rows["cluster_size"]) == [2, 0]
    assert rows["cluster_center"][0] == pytest.approx((1 * 10 + 2 * 5) / 15)
