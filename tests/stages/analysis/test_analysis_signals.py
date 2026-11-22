import hashlib

import numpy as np
import pytest

from raser.core.current.currents import EventCurrents
from raser.core.current.currents import append_currents
from raser.core.deposit.deposits import Deposits
from raser.core.deposit.deposits import EventDeposits
from raser.core.deposit.deposits import write_deposits
from raser.stages.analysis import across_points
from raser.stages.analysis.across_points import write_signals
from raser.stages.analysis.signals import energy_spread
from raser.stages.analysis.signals import event_energies
from raser.stages.analysis.signals import mean_current

DT = 1.0e-10


def _nodes(folder, index):
    """The node of each slice of job `index` of the experiment folder `folder`."""
    return {
        name: hashlib.sha1(f"{folder}/{index}/{name}".encode()).hexdigest()[:12]
        for name in ("deposit", "current", "readout", "reconstruction")
    }


def _slice(folder, index, name):
    """The file of the slice `name` of job `index`, in the node of the slice."""
    path = folder / "nodes" / name / _nodes(folder, index)[name] / f"{name}.h5"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _job(folder, index, events, dt=DT):
    """A job whose events are (t0 [s], current [A] of shape (2 electrodes,
    bins), energies [MeV] of its deposits)."""
    folder.mkdir(parents=True, exist_ok=True)
    deposits = []
    for number, (t0, current, energies) in enumerate(events):
        append_currents(
            _slice(folder, index, "current"), ["top", "bottom"], dt,
            EventCurrents(number, t0, np.asarray(current, dtype=float), np.zeros(2), 1000.0),
        )
        count = len(energies)
        deposits.append(
            EventDeposits(number, ["Device"] * count, [0.0] * count, [0.0] * count, [1.0] * count, [t0] * count, list(energies), [1.0] * count)
        )
    write_deposits(str(_slice(folder, index, "deposit")), Deposits(50, {}, "any", None, deposits))
    return (folder, _nodes(folder, index) if events else {"deposit": _nodes(folder, index)["deposit"]})


def test_mean_current_is_the_mean_over_events_of_the_sum_over_electrodes(tmp_path) -> None:
    folder = tmp_path / "seed_1"
    first = _job(folder, 0, [(0.0, [[1.0, 2.0, 3.0], [1.0, 0.0, 0.0]], [0.1])])
    second = _job(folder, 1, [(0.0, [[3.0, 2.0, 1.0], [0.0, 0.0, 2.0]], [0.1])])
    empty = _job(folder, 2, [])

    times, current, events = mean_current([first, empty, second])

    assert events == 2
    np.testing.assert_allclose(current, [(2 + 3) / 2, 2.0, (3 + 3) / 2])
    np.testing.assert_allclose(times, (np.arange(3) + 0.5) * DT)


def test_event_without_a_bin_where_another_has_one_counts_with_zero_current(tmp_path) -> None:
    jobs = [_job(tmp_path / "seed_1", 0, [(0.0, [[2.0, 4.0], [0.0, 0.0]], [0.1]), (0.0, [[6.0, 6.0, 8.0, 8.0], [0.0] * 4], [0.1])])]

    _, current, events = mean_current(jobs)

    assert events == 2
    np.testing.assert_allclose(current, [4.0, 5.0, 4.0, 4.0])


def test_events_that_start_between_bins_share_them_and_keep_their_charge(tmp_path) -> None:
    folder = tmp_path / "seed_1"
    jobs = [_job(folder, 0, [(0.0, [[4.0, 0.0], [0.0, 0.0]], [0.1]), (0.25 * DT, [[4.0], [0.0]], [0.1])])]

    times, current, _ = mean_current(jobs)

    np.testing.assert_allclose(current, [(4 + 3) / 2, (0 + 1) / 2])
    # charge of the mean: the mean of the charges of the events, 4 A per bin each
    assert np.sum(current) * DT == pytest.approx(4.0 * DT)
    np.testing.assert_allclose(times[0], 0.5 * DT)


def test_event_that_starts_later_is_placed_at_its_time(tmp_path) -> None:
    jobs = [_job(tmp_path / "seed_1", 0, [(0.0, [[2.0], [0.0]], [0.1]), (3 * DT, [[2.0], [0.0]], [0.1])])]

    _, current, _ = mean_current(jobs)

    np.testing.assert_allclose(current, [1.0, 0.0, 0.0, 1.0])


def test_point_without_events_has_no_mean_current(tmp_path) -> None:
    assert mean_current([_job(tmp_path / "seed_1", 0, [])]) is None


def test_jobs_with_other_time_bins_are_refused(tmp_path) -> None:
    first = _job(tmp_path / "seed_1", 0, [(0.0, [[1.0], [0.0]], [0.1])])
    second = _job(tmp_path / "seed_2", 0, [(0.0, [[1.0], [0.0]], [0.1])], dt=2 * DT)

    with pytest.raises(ValueError, match="time bins"):
        mean_current([first, second])


def test_event_energy_is_the_sum_of_its_deposits_and_the_spread_is_of_the_events(tmp_path) -> None:
    folder = tmp_path / "seed_1"
    zero = [[0.0], [0.0]]
    jobs = [
        _job(folder, 0, [(0.0, zero, [0.1, 0.2]), (0.0, zero, [0.4])]),
        _job(folder, 1, [(0.0, zero, [0.05, 0.05, 0.2])]),
        _job(folder, 2, []),
    ]

    energies = event_energies(jobs)

    np.testing.assert_allclose(energies, [0.3, 0.4, 0.3])
    spread = energy_spread(energies)
    assert spread["events"] == 3
    assert spread["mean"] == pytest.approx(1.0 / 3.0)
    assert spread["std"] == pytest.approx(0.05773502691896258)


@pytest.mark.parametrize("energies", [[], [0.3]])
def test_fewer_than_two_events_have_no_spread(energies) -> None:
    result = energy_spread(np.array(energies))

    assert result["events"] == len(energies)
    assert "error" in result and "std" not in result and "mean" not in result


def test_signals_draw_one_curve_per_point_with_its_own_events(tmp_path, monkeypatch) -> None:
    zero = [[0.0], [0.0]]
    low = [_job(tmp_path / "low" / "seed_1", 0, [(0.0, [[1.0, 3.0], [0.0, 0.0]], [0.1]), (0.0, [[3.0, 1.0], [0.0, 0.0]], [0.3])])]
    high = [_job(tmp_path / "high" / "seed_1", 0, [(0.0, [[10.0, 10.0], [0.0, 0.0]], [0.5, 0.5, 0.5]), (0.0, zero, [2.0]), (0.0, zero, [2.0])])]
    none = [_job(tmp_path / "none" / "seed_1", 0, [])]
    points = [("voltage_200", {"field.voltage": 200}), ("voltage_100", {"field.voltage": 100}), ("voltage_300", {"field.voltage": 300})]
    drawn = {}
    save = across_points.figures.save

    def keep(figure, folder, name, *suffixes):
        axis = figure.axes[0]
        drawn[name] = {
            "labels": [text.get_text() for text in axis.get_legend().get_texts()],
            "lines": [line.get_ydata() for line in axis.lines],
            "heights": [patch.get_xy()[1 : 2 * 60 : 2, 1] for patch in axis.patches],
        }
        return save(figure, folder, name, *suffixes)

    monkeypatch.setattr(across_points.figures, "save", keep)

    write_signals(points, [high, low, none], tmp_path / "out")

    for name in ("currents", "deposited_energy"):
        assert (tmp_path / "out" / f"{name}.png").exists()
        assert (tmp_path / "out" / f"{name}.pdf").exists()
    # in ascending order of the voltage; the point without events has no curve
    currents = drawn["currents"]
    assert currents["labels"] == ["field.voltage = 100", "field.voltage = 200"]
    np.testing.assert_allclose(currents["lines"][0] * 1e-6, [2.0, 2.0])  # the axis is in uA
    np.testing.assert_allclose(currents["lines"][1] * 1e-6, [10.0 / 3, 10.0 / 3])
    energy = drawn["deposited_energy"]
    assert energy["labels"] == ["field.voltage = 100: 2 events", "field.voltage = 200: 3 events"]
    assert [heights.sum() for heights in energy["heights"]] == [2, 3]
    assert (tmp_path / "out" / "currents.png").stat().st_size > 0


def test_no_curve_is_drawn_when_no_point_recorded_an_event(tmp_path) -> None:
    jobs = [[_job(tmp_path / "a" / "seed_1", 0, [])], [_job(tmp_path / "b" / "seed_1", 0, [])]]

    write_signals([("a", {"x": 1}), ("b", {"x": 2})], jobs, tmp_path / "out")

    assert not (tmp_path / "out" / "currents.png").exists()
    assert not (tmp_path / "out" / "deposited_energy.png").exists()


def test_time_axis_starts_at_the_first_bin_of_the_earliest_event(tmp_path) -> None:
    jobs = [_job(tmp_path / "seed_1", 0, [(5 * DT, [[1.0], [0.0]], [0.1]), (7 * DT, [[1.0], [0.0]], [0.1])])]

    times, current, _ = mean_current(jobs)

    np.testing.assert_allclose(times, (5.5 + np.arange(3)) * DT)
    np.testing.assert_allclose(current, [0.5, 0.0, 0.5])
