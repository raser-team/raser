from pathlib import Path

import json

import numpy as np
import pytest

from raser.core.digitizer.digital_waveforms import read_digitized
from raser.core.digitizer.quantize import to_volts
from raser.core.readout.waveforms import EventWaveforms
from raser.core.readout.waveforms import append_waveforms
from raser.stages.digitizer import digitized

DT_S = 50e-12
BINS = 200
# pulse of the traces, V: down from the bin 50 on
PULSE_V = -0.010
FLAT_V = 0.0


def _trace(amplitude_V: float) -> np.ndarray:
    volts = np.zeros((1, BINS))
    volts[0, 50:] = amplitude_V
    return volts


def write_readout(path: Path, amplitudes_V: dict[int, float]) -> None:
    """A readout file of the electrode "a", one event of the pulse of each amplitude [V]."""
    for number, amplitude_V in amplitudes_V.items():
        append_waveforms(
            path,
            ["a"],
            DT_S,
            10 * DT_S,
            EventWaveforms(number, 0.0, _trace(amplitude_V)),
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


# Deliberate changes: writing to the readout node, reading another file, the
# plots folder of another node, the plots count ignored.
def test_the_digitized_file_and_pictures_are_written_into_the_node_of_the_slice(
    tmp_path: Path,
) -> None:
    kwargs = make_kwargs(tmp_path)
    write_readout(
        tmp_path / "readout" / "readout.h5", {3: PULSE_V, 5: FLAT_V, 8: PULSE_V}
    )

    assert digitized(kwargs) is None

    assert (tmp_path / "digitizer" / "digitizer.h5").exists()
    pictures = sorted(
        path.name for path in (tmp_path / "digitizer" / "plots").glob("*.png")
    )
    assert pictures == ["codes.png", "samples_3.png", "samples_5.png"]
    assert not (tmp_path / "readout" / "digitizer.h5").exists()


# Deliberate changes: the codes made of the wrong file, the full scale or the
# period of another component, the lsb taken from the wrong bits.
def test_the_codes_are_the_sampled_pulse_of_the_readout_at_the_sampling_period_of_the_component(
    tmp_path: Path,
) -> None:
    kwargs = make_kwargs(tmp_path)
    write_readout(tmp_path / "readout" / "readout.h5", {3: PULSE_V, 5: FLAT_V})

    digitized(kwargs)

    record = read_digitized(tmp_path / "digitizer" / "digitizer.h5")
    # 50 ps of the readout, 20 GSps of toy: one sample for each bin
    assert record.sampling_period == pytest.approx(DT_S, rel=1e-12, abs=0)
    assert [event.event for event in record.events] == [3, 5]
    volts = to_volts(
        record.events[0].code[0], record.bits, record.lsb_V, record.offset_V
    )
    assert volts.shape == (BINS,)
    # the resampling rings for a few tens of bins on both sides of the step
    assert volts[:20] == pytest.approx(0.0, abs=record.lsb_V)
    assert volts[100:] == pytest.approx(PULSE_V, abs=record.lsb_V)


# Deliberate change: the check of the position dropped, so that the missing
# file is opened or written.
def test_a_position_without_a_readout_returns_no_events_and_writes_nothing(
    tmp_path: Path,
) -> None:
    kwargs = make_kwargs(tmp_path, "readout.B", "digitizer.B")

    assert digitized(kwargs, "B") == {"events": 0}
    assert list((tmp_path / "digitizer.B").iterdir()) == []


# Deliberate change: the slice of the position reading readout.h5 or writing
# digitizer.h5.
def test_a_position_reads_and_writes_the_files_named_with_it(tmp_path: Path) -> None:
    kwargs = make_kwargs(tmp_path, "readout.A", "digitizer.A")
    write_readout(tmp_path / "readout.A" / "readout.A.h5", {1: PULSE_V})

    assert digitized(kwargs, "A") is None

    assert (tmp_path / "digitizer.A" / "digitizer.A.h5").exists()
    assert (tmp_path / "digitizer.A" / "plots" / "samples_1.png").exists()
    assert not (tmp_path / "digitizer" / "digitizer.h5").exists()


# Deliberate change: one of the keys read with .get(), or left out of the check.
@pytest.mark.parametrize("key", ["device", "plots", "seed"])
def test_a_missing_key_is_named_in_the_error(tmp_path: Path, key: str) -> None:
    kwargs = make_kwargs(tmp_path)
    write_readout(tmp_path / "readout" / "readout.h5", {1: PULSE_V})
    del kwargs[key]

    with pytest.raises(ValueError, match=key):
        digitized(kwargs)
    assert not (tmp_path / "digitizer" / "digitizer.h5").exists()


def test_a_missing_component_is_named_in_the_error(tmp_path: Path) -> None:
    kwargs = make_kwargs(tmp_path)
    write_readout(tmp_path / "readout" / "readout.h5", {1: -0.01})
    del kwargs["_files"]["digitizer"]

    with pytest.raises(ValueError, match="digitizer.device"):
        digitized(kwargs)
