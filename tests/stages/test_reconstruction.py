import json

import numpy as np
import pytest

from raser.core.current.currents import EventCurrents
from raser.core.current.currents import append_currents
from raser.core.deposit.deposits import Deposits
from raser.core.deposit.deposits import EventDeposits
from raser.core.deposit.deposits import write_deposits
from raser.core.readout.waveforms import EventWaveforms
from raser.core.readout.waveforms import append_waveforms
from raser.core.reconstruction.event_table import read_event_table
from raser.stages import reconstruction
from raser.stages.analysis.timing import event_times

E = 1.602176634e-19
# a negative triangle [V]: 2 mV per bin up to 10 mV in bin 6, then down again
TRIANGLE = 1.0e-3 * np.array([0.0, 0, -2, -4, -6, -8, -10, -8, -6, -4, -2, 0, 0])
DT = 1.0e-9
BEFORE = 200  # bins before the triangle
FRACTIONS = (0.2, 0.5)


def _job(folder, scales, count, seed):
    """Job 0 of `count` events in a seed folder that holds its slices; the
    electrodes carry the triangle times `scales`, and event k collects
    900 + k pairs on the first one."""
    batch = folder / "batch"
    batch.mkdir(parents=True, exist_ok=True)
    held = {"deposit": "", "current": "", "readout": ""}
    (folder / "run.json").write_text(json.dumps({"point": "", "held_in": held}))
    names = [f"strip_{k}" for k in range(len(scales[0]))]
    rng = np.random.default_rng(seed)
    truths = rng.normal(0.0, 1.0e-9, count)
    starts = truths + rng.normal(0.0, 3.0e-11, count)
    deposits = []
    for number in range(count):
        deposits.append(EventDeposits(number, ["Device"], [0.0], [0.0], [1.0], [truths[number]], [0.1], [1000.0]))
        charge = np.zeros(len(names))
        charge[0] = -(900 + number) * E
        append_currents(batch / "current_0.h5", names, 1.0e-11,
                        EventCurrents(number, 0.0, np.zeros((len(names), 2)), charge, 1000.0))
        samples = [np.concatenate([np.zeros(BEFORE), scale * TRIANGLE]) for scale in scales[number % len(scales)]]
        append_waveforms(batch / "readout_0.h5", names, DT,
                         EventWaveforms(number, starts[number] - BEFORE * DT, np.array(samples)))
    write_deposits(str(batch / "deposit_0.h5"), Deposits(count, None, None, deposits))
    return truths


def _run(folder, threshold, amplitude_threshold):
    batch = str(folder / "batch")
    kwargs = {
        "_slice_batch_paths": {name: batch for name in ("deposit", "current", "readout", "reconstruction")},
        "threshold": threshold, "amplitude_threshold": amplitude_threshold, "fractions": FRACTIONS,
    }
    reconstruction.run(kwargs)
    return read_event_table(folder / "batch" / "reconstruction_0.h5")


def test_selected_rows_are_the_events_the_analysis_selects(tmp_path) -> None:
    # 10 mV and 4 mV in turn; 5 mV selects the first ones
    truths = _job(tmp_path, [[1.0], [0.4]], 60, seed=4)

    table = _run(tmp_path, 3, 5)

    count, polarity, times = event_times([(tmp_path, 0)], 3.0e-3, 5.0e-3)
    rows = table.columns
    assert (len(table), table.polarity) == (count, polarity) == (60, -1.0)
    assert list(rows["event"][rows["selected"]]) == list(times["event"]) == list(range(0, 60, 2))
    for name in ("ToA", "ToT", "CoG", "amplitude", "baseline", "noise"):
        assert rows[name][rows["selected"], 0] == pytest.approx(times[name])
    assert rows["CFD"][rows["selected"], 0, 1] == pytest.approx(times["CFD50"])
    # the 4 mV events are above the 3 mV threshold and have times, not selected
    assert rows["above"][:, 0].all()
    assert not np.isnan(rows["ToA"][1::2, 0]).any()
    assert rows["deposit_time"] == pytest.approx(truths)
    assert rows["net_charge"][:, 0] == pytest.approx(-(900 + np.arange(60)) * E)


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
