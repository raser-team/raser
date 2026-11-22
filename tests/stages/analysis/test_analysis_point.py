import hashlib
import json

import h5py
import numpy as np
import pytest

from raser.stages import analysis as ana
from raser.lifecycle import workflow
from raser.stages.analysis.point import write_point
from raser.stages.reconstruction import reconstruct
from raser.core.current.currents import EventCurrents
from raser.core.current.currents import append_currents
from raser.core.readout.waveforms import EventWaveforms
from raser.core.readout.waveforms import append_waveforms
from raser.core.deposit.deposits import Deposits
from raser.core.deposit.deposits import EventDeposits
from raser.core.deposit.deposits import write_deposits

E = 1.602176634e-19
# a negative triangle [V]: 2 mV per bin up to 10 mV in bin 6, then down again;
# its half height is 4 ns after its start
TRIANGLE = 1.0e-3 * np.array([0.0, 0, -2, -4, -6, -8, -10, -8, -6, -4, -2, 0, 0])
DT = 1.0e-9
BEFORE = 200  # bins before the triangle


def _nodes(folder, index):
    """The node of each slice of job `index` of the experiment folder
    `folder`: twelve hex digits, a different one for each file."""
    return {
        name: hashlib.sha1(f"{folder}/{index}/{name}".encode()).hexdigest()[:12]
        for name in ("deposit", "current", "readout", "reconstruction")
    }


def _of(folder, index):
    """Job `index` of the experiment folder `folder`, as lifecycle hands it
    out: the experiment folder and the node of each of its slices."""
    return (folder, _nodes(folder, index))


def _slice(folder, index, name):
    """The file of the slice `name` of job `index` of the experiment folder
    `folder`: in the node of the slice."""
    path = folder / "nodes" / name / _nodes(folder, index)[name] / f"{name}.h5"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _job(folder, index, scale, count, seed, amplitude_threshold=5, jitter=3.0e-11, spread=1.0e-9):
    """A job of `count` events in a seed folder that holds its slices. Each
    event has 1000 pairs, collects 90 % of them and gives the triangle times
    `scale`; the pulse starts within 30 ps of the deposit, and the deposits
    are spread over 1 ns. Its reconstruction has the thresholds 3 mV and
    `amplitude_threshold` mV, on the falling edge."""
    folder.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    truths = rng.normal(0.0, spread, count)
    starts = truths + rng.normal(0.0, jitter, count)
    deposits = []
    for number in range(count):
        deposits.append(
            EventDeposits(number, ["Device"], [0.0], [0.0], [1.0], [truths[number]], [0.1], [1000.0])
        )
        append_currents(
            _slice(folder, index, "current"),
            ["top"],
            1.0e-11,
            EventCurrents(number, 0.0, np.zeros((1, 2)), np.array([-900 * E]), 1000.0),
        )
        samples = np.concatenate([np.zeros(BEFORE), scale * TRIANGLE])
        append_waveforms(
            _slice(folder, index, "readout"),
            ["top"],
            DT,
            EventWaveforms(number, starts[number] - BEFORE * DT, np.array([samples])),
            pulse_edge=["falling"],
        )
    write_deposits(str(_slice(folder, index, "deposit")), Deposits(50, None, None, deposits))
    if count:
        reconstruct(
            _slice(folder, index, "readout"), _slice(folder, index, "reconstruction"), 3, amplitude_threshold, (0.2, 0.5, 0.8), "falling"
        )


def test_point_takes_its_events_from_the_reconstruction_tables(tmp_path) -> None:
    seed = tmp_path / "seed_1"
    _job(seed, 0, 1.0, 300, seed=4)  # 10 mV
    _job(seed, 1, 0.4, 300, seed=5)  # 4 mV, below the amplitude threshold
    # the waveforms are not read again: only the tables hold the times
    for index in (0, 1):
        _slice(seed, index, "readout").unlink()

    error = write_point([_of(seed, 0), _of(seed, 1)], tmp_path / "out")

    assert error is None
    result = json.loads((tmp_path / "out" / "result.json").read_text())
    assert result["reconstruction"] == {"threshold": 3.0, "amplitude_threshold": 5.0, "fractions": [0.2, 0.5, 0.8], "edge": ["falling"]}
    assert set(result["timing"]["times"]) == {"ToA", "CoG", "CFD20", "CFD50", "CFD80"}
    assert result["collection"]["events"] == 600
    assert result["collection"]["mean"] == pytest.approx(0.9)
    timing = result["timing"]
    assert (timing["events"], timing["selected"], timing["polarity"]) == (600, 300, -1.0)
    half = timing["times"]["CFD50"]
    assert half["mean"] == pytest.approx(4.0e-9, abs=5 * half["mean_error"])
    assert half["sigma"] == pytest.approx(3.0e-11, abs=5 * half["sigma_error"])
    assert half["sigma_error"] < 5.0e-12
    # one row per selected event: those of the first job
    with h5py.File(tmp_path / "out" / "events.h5", "r") as file:
        assert list(file["job"][:]) == [0] * 300
        assert list(file["event"][:]) == list(range(300))
        assert file["amplitude"][:] == pytest.approx(np.full(300, 10.0e-3))


def test_point_with_too_few_selected_events_keeps_its_efficiency_and_tells_why(tmp_path) -> None:
    seed = tmp_path / "seed_1"
    _job(seed, 0, 1.0, 10, seed=4)
    _job(seed, 1, 0.4, 300, seed=5)

    error = write_point([_of(seed, 0), _of(seed, 1)], tmp_path / "out")

    assert error == "no time resolution: 10 values, fewer than 20"
    result = json.loads((tmp_path / "out" / "result.json").read_text())
    assert result["collection"]["events"] == 310
    assert result["timing"] == {"events": 310, "selected": 10, "polarity": -1.0, "error": "10 values, fewer than 20"}
    assert not (tmp_path / "out" / "time_difference.png").exists()


def test_point_without_selected_events_is_a_result_not_a_failure(tmp_path, monkeypatch, capsys) -> None:
    root = tmp_path / "work" / "device" / "signal"
    _job(root / "seed_1", 0, 0.4, 100, seed=5)  # 4 mV, below the amplitude threshold
    monkeypatch.setattr(ana, "batches", lambda jobs: "seed 1: 1 jobs")
    monkeypatch.setattr(ana, "jobs_of_points", lambda folder: [("", {}, [_of(root / "seed_1", 0)])])
    options = {"experiment": str(root), "_run_path": str(tmp_path / "out")}

    ana.collect(options)

    timing = json.loads((tmp_path / "out" / "result.json").read_text())["timing"]
    assert timing == {"events": 100, "selected": 0, "polarity": -1.0, "error": "0 values, fewer than 20"}
    assert "no time resolution: 0 values, fewer than 20" in capsys.readouterr().out


@pytest.mark.parametrize(("count", "why"), [(0, "the jobs recorded no event"), (1, "1 values, fewer than 20")])
def test_point_with_fewer_than_two_events_is_a_result_not_a_failure(tmp_path, monkeypatch, capsys, count, why) -> None:
    root = tmp_path / "work" / "device" / "timeres"
    _job(root / "seed_1", 0, 1.0, count, seed=4)
    monkeypatch.setattr(ana, "batches", lambda jobs: "seed 1: 1 jobs")
    monkeypatch.setattr(ana, "jobs_of_points", lambda folder: [("", {}, [_of(root / "seed_1", 0)])])
    options = {"experiment": str(root), "_run_path": str(tmp_path / "out")}

    ana.collect(options)

    result = json.loads((tmp_path / "out" / "result.json").read_text())
    assert result["collection"] == {"events": count, "error": f"{count} events in the point, a mean and a spread need at least 2"}
    assert (result["timing"]["events"], result["timing"]["selected"], result["timing"]["error"]) == (count, count, why)
    printed = capsys.readouterr().out
    assert f"no efficiency: {count} events in the point" in printed and f"no time resolution: {why}" in printed


def test_enough_events_whose_fit_fails_are_an_error(tmp_path) -> None:
    # every deposit at 0 and every pulse starting there: time - truth is one value
    seed = tmp_path / "seed_1"
    _job(seed, 0, 1.0, 30, seed=4, jitter=0.0, spread=0.0)

    with pytest.raises(ValueError, match=r"the window \[.*\] is empty"):
        write_point([_of(seed, 0)], tmp_path / "out")


def test_currents_and_reconstruction_of_other_events_are_refused(tmp_path) -> None:
    seed = tmp_path / "seed_1"
    _job(seed, 0, 1.0, 30, seed=4)
    other = tmp_path / "other"
    _job(other, 0, 1.0, 31, seed=4)
    # the currents of events 0 ... 30 next to the reconstruction of 0 ... 29
    _slice(seed, 0, "current").write_bytes(_slice(other, 0, "current").read_bytes())

    with pytest.raises(ValueError, match=r"events \[30\] are in the currents or in the reconstruction of the job, not in both"):
        write_point([_of(seed, 0)], tmp_path / "out")


def test_jobs_reconstructed_with_other_thresholds_are_refused(tmp_path) -> None:
    seed = tmp_path / "seed_1"
    _job(seed, 0, 1.0, 30, seed=4)
    _job(seed, 1, 1.0, 30, seed=5, amplitude_threshold=6)

    with pytest.raises(ValueError, match="reconstructed with different settings"):
        write_point([_of(seed, 0), _of(seed, 1)], tmp_path / "out")


def test_analysis_holds_the_results_of_the_points_it_analyses(tmp_path, monkeypatch) -> None:
    root = tmp_path / "work" / "device" / "timeres"
    _job(root / "seed_1", 0, 1.0, 100, seed=4)
    _job(root / "voltage_100" / "seed_1", 0, 0.4, 100, seed=5, amplitude_threshold=2)  # 4 mV
    (root / "config.json").write_text(json.dumps({"workflow": "timeres", "device": "device"}))
    points: list[tuple[str, dict, list]] = [
        ("", {"voltage": 300.0, "plots": 0}, [_of(root / "seed_1", 0)]),
        ("voltage_100", {"voltage": 100.0, "plots": 0}, [_of(root / "voltage_100" / "seed_1", 0)]),
        ("voltage_200", {"voltage": 200.0, "plots": 0}, []),
    ]
    monkeypatch.setattr(ana, "batches", lambda jobs: "seed 1: 1 jobs")
    monkeypatch.setattr(ana, "jobs_of_points", lambda folder: points if folder == root.resolve() else None)

    def own_process(flow, kwargs, words):
        try:
            workflow._run_job(flow, {**kwargs, "job_dir": words[-1]})
        except SystemExit as stopped:  # as the command of a job that stops
            raise RuntimeError(str(stopped)) from stopped

    monkeypatch.setattr(workflow, "_own_process", own_process)
    kwargs: dict = {"experiment": str(root), "scan": []}
    kwargs.update(jobs=None, batch=False, mem=1, dry_run=False, _entry_command_prefix=("raser",))
    kwargs["_components_of"] = {"timeres": ()}  # the component roots the commands register

    with pytest.raises(SystemExit, match="1 of 3 points are not complete"):
        ana.run(kwargs)

    place = root / "analysis"
    results = {upstream: json.loads((place / upstream / "result.json").read_text()) for upstream in ("", "voltage_100")}
    assert {upstream: result["timing"]["selected"] for upstream, result in results.items()} == {"": 100, "voltage_100": 100}
    assert results["voltage_100"]["reconstruction"]["amplitude_threshold"] == 2.0
    assert not (place / "voltage_200").exists()
    # one row per point that ran, with the option that differs between them
    rows = json.loads((place / "points.json").read_text())
    assert [(row["point"], row["voltage"], row["events"]) for row in rows] == [("", 300.0, 100), ("voltage_100", 100.0, 100)]
    assert "plots" not in rows[0]
    half = results["voltage_100"]["timing"]["times"]["CFD50"]
    assert rows[1]["CFD50"] == {key: half[key] for key in ("sigma68", "sigma", "sigma_error")}
    assert rows[1]["efficiency"] == pytest.approx(0.9)
