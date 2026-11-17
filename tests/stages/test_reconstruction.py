import numpy as np
import pytest

from raser.core.readout.waveforms import EventWaveforms
from raser.core.readout.waveforms import append_waveforms
from raser.core.reconstruction.event_table import read_event_table
from raser.stages import reconstruction

# a negative triangle [V]: 2 mV per bin up to 10 mV in bin 6, then down again
TRIANGLE = 1.0e-3 * np.array([0.0, 0, -2, -4, -6, -8, -10, -8, -6, -4, -2, 0, 0])
DT = 1.0e-9
BEFORE = 200  # bins before the triangle
FRACTIONS = (0.2, 0.5)


def _job(folder, scales, count, seed):
    """The readout of job 0 of `count` events in a seed folder; the
    electrodes carry the triangle times `scales`. Returns the start of the
    triangle of each event."""
    batch = folder / "batch"
    batch.mkdir(parents=True, exist_ok=True)
    names = [f"strip_{k}" for k in range(len(scales[0]))]
    starts = np.random.default_rng(seed).normal(0.0, 1.0e-9, count)
    for number in range(count):
        samples = [np.concatenate([np.zeros(BEFORE), scale * TRIANGLE]) for scale in scales[number % len(scales)]]
        append_waveforms(batch / "readout_0.h5", names, DT,
                         EventWaveforms(number, starts[number] - BEFORE * DT, np.array(samples)))
    return starts


def _run(folder, threshold, amplitude_threshold, edge="falling"):
    batch = str(folder / "batch")
    kwargs = {
        "_slice_batch_paths": {name: batch for name in ("readout", "reconstruction")},
        "threshold": threshold, "amplitude_threshold": amplitude_threshold, "fractions": FRACTIONS, "edge": edge,
    }
    reconstruction.run(kwargs)
    return read_event_table(folder / "batch" / "reconstruction_0.h5")


def test_every_event_has_a_row_and_the_large_ones_are_selected(tmp_path) -> None:
    # 10 mV and 4 mV in turn; 5 mV selects the first ones
    starts = _job(tmp_path, [[1.0], [0.4]], 60, seed=4)

    table = _run(tmp_path, 3, 5)

    rows = table.columns
    assert (len(table), table.edge) == (60, "falling")
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
    assert rows["charge"][0::2, 0] == pytest.approx(np.full(30, 50.0e-3 * DT))


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
    with pytest.raises(ValueError, match="edge 'down'"):
        _run(tmp_path, 3, 5, "down")
