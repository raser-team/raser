import json
from pathlib import Path

import numpy as np
import pytest

from raser.core.trigger.job import read_triggered
from raser.stages.digitizer import digitized
from raser.stages.trigger import coincident
from raser.stages.trigger import triggered
from raser.core.readout.waveforms import EventWaveforms
from raser.core.readout.waveforms import append_waveforms

DT_S = 50e-12
BINS = 200
# the pulse begins at the bin 50, in V
PULSE_V = -0.010
FLAT_V = 0.0


def write_readout(path: Path, amplitudes_V: dict[int, float]) -> None:
    """A readout file of the electrode "a", one event of the pulse of each amplitude [V]."""
    for number, amplitude_V in amplitudes_V.items():
        volts = np.zeros((1, BINS))
        volts[0, 50:] = amplitude_V
        append_waveforms(
            path,
            ["a"],
            DT_S,
            EventWaveforms(number, 0.0, volts),
            pulse_edge=["falling"],
        )


def make_kwargs(tmp_path: Path, *names: str) -> dict:
    """The arguments of a slice whose nodes are the folders of tmp_path, one per name."""
    paths = {}
    for name in ("readout", "digitizer", "trigger", *names):
        folder = tmp_path / name
        folder.mkdir(exist_ok=True)
        paths[name] = str(folder)
    return {
        "_node_paths": paths,
        "_files": {
            "digitizer": json.loads(
                Path("src/raser/components/digitizer/toy.json").read_text(
                    encoding="utf-8"
                )
            )
        },
        "device": "toy",
        "plots": 2,
        "seed": 7,
        "job_index": 0,
    }


def _digitize(
    tmp_path: Path, kwargs: dict, amplitudes_V: dict[int, float], position: str | None
) -> None:
    suffix = "" if position is None else f".{position}"
    write_readout(tmp_path / f"readout{suffix}" / f"readout{suffix}.h5", amplitudes_V)
    digitized(kwargs, position)


# Deliberate changes: the level of the condition ignored so that every event is
# recorded, the event index recorded instead of the event number, the trigger
# of another channel read.
def test_the_events_whose_pulse_crosses_the_level_are_recorded(tmp_path: Path) -> None:
    kwargs = make_kwargs(tmp_path)
    _digitize(tmp_path, kwargs, {3: PULSE_V, 5: FLAT_V, 8: PULSE_V}, None)

    assert triggered(kwargs) == {"events": 2}

    record = read_triggered(tmp_path / "trigger" / "trigger.h5")
    # the level of toy is -2 mV, falling; the pulse of 10 mV begins at bin 50
    assert record.event.tolist() == [3, 8]
    assert record.events_seen == 3
    assert record.trigger_time == pytest.approx([50 * DT_S, 50 * DT_S], abs=DT_S)
    assert (tmp_path / "trigger" / "plots" / "trigger_amplitude.png").exists()
    assert not (tmp_path / "digitizer" / "trigger.h5").exists()


# Deliberate change: the missing "trigger" key of the component answered with a
# default condition.
def test_a_component_without_a_trigger_is_refused(tmp_path: Path) -> None:
    kwargs = make_kwargs(tmp_path)
    _digitize(tmp_path, kwargs, {1: PULSE_V}, None)
    del kwargs["_files"]["digitizer"]["trigger"]

    with pytest.raises(ValueError, match="trigger"):
        triggered(kwargs)
    assert not (tmp_path / "trigger" / "trigger.h5").exists()


# Deliberate change: the check of the position dropped.
def test_a_position_without_digitized_waveforms_returns_no_events_and_writes_nothing(
    tmp_path: Path,
) -> None:
    kwargs = make_kwargs(tmp_path, "digitizer.B", "trigger.B")

    assert triggered(kwargs, "B") == {"events": 0}
    assert list((tmp_path / "trigger.B").iterdir()) == []


# Deliberate change: the slice of the position reading digitizer.h5 or writing trigger.h5.
def test_a_position_reads_and_writes_the_files_named_with_it(tmp_path: Path) -> None:
    kwargs = make_kwargs(tmp_path, "readout.A", "digitizer.A", "trigger.A")
    _digitize(tmp_path, kwargs, {1: PULSE_V, 2: FLAT_V}, "A")

    assert triggered(kwargs, "A") == {"events": 1}

    assert read_triggered(tmp_path / "trigger.A" / "trigger.A.h5").event.tolist() == [1]


def _two_positions(
    tmp_path: Path, a: dict[int, float], b: dict[int, float] | None
) -> dict:
    kwargs = make_kwargs(
        tmp_path,
        "readout.A",
        "readout.B",
        "digitizer.A",
        "digitizer.B",
        "trigger.A",
        "trigger.B",
    )
    kwargs["_files"]["trigger"] = json.loads(
        Path("src/raser/components/trigger/coincidence.json").read_text(
            encoding="utf-8"
        )
    )
    _digitize(tmp_path, kwargs, a, "A")
    if b is not None:
        _digitize(tmp_path, kwargs, b, "B")
    return kwargs


# Deliberate changes: "all" evaluated as "any", only one position read, the
# trigger file written for one position only.
def test_only_the_events_over_the_level_in_both_positions_are_recorded(
    tmp_path: Path,
) -> None:
    kwargs = _two_positions(
        tmp_path,
        {1: PULSE_V, 2: PULSE_V, 3: FLAT_V},
        {1: PULSE_V, 2: FLAT_V, 3: PULSE_V},
    )

    assert coincident(kwargs, ["A", "B"]) == {"events": 1}

    for position in ("A", "B"):
        record = read_triggered(
            tmp_path / f"trigger.{position}" / f"trigger.{position}.h5"
        )
        assert record.event.tolist() == [1]
        assert record.events_seen == 3
    assert (tmp_path / "trigger" / "plots" / "trigger_amplitude.png").exists()


# Deliberate change: the slot of a position without a file counted as hit, or
# the missing file opened.
def test_a_position_without_a_file_is_hit_in_no_event(tmp_path: Path) -> None:
    kwargs = _two_positions(tmp_path, {1: PULSE_V, 2: PULSE_V}, None)

    assert coincident(kwargs, ["A", "B"]) == {"events": 0}

    assert read_triggered(tmp_path / "trigger.A" / "trigger.A.h5").events_seen == 2

    # the same events with any of the slots enough
    kwargs["_files"]["trigger"]["require"] = "any"

    assert coincident(kwargs, ["A", "B"]) == {"events": 2}


# Deliberate change: the component of trigger.device read with .get() and a default.
def test_a_missing_trigger_key_is_named_in_the_error(tmp_path: Path) -> None:
    kwargs = _two_positions(tmp_path, {1: PULSE_V}, {1: PULSE_V})
    del kwargs["_files"]["trigger"]

    with pytest.raises(ValueError, match="trigger"):
        coincident(kwargs, ["A", "B"])
