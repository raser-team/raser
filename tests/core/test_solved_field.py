from __future__ import annotations

import json
from pathlib import Path

import pytest

from raser.core.device.build_device import Detector
from raser.core.device.build_device import device_json
from raser.core.field.reading import Reading
from raser.core.field.solved import solved_field


def _device(change=lambda content: None) -> Detector:
    content = device_json("HPK-Si-PiN")
    change(content)
    return Detector("HPK-Si-PiN", content)


def _field(folder: Path, flux=None, solved=None, read=True) -> None:
    """A field folder as a solve of HPK-Si-PiN leaves it."""
    reading = Reading(_device())
    reading.device_dict["doping"]["Donors"]
    record = {"options": {"irradiation_flux": flux}, "files": {"device": device_json("HPK-Si-PiN")}}
    if read:
        record["read"] = reading.read
    record["solved"] = {"potential": [0.0, 100.0], "weighting": ["any"]} if solved is None else solved
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "run.json").write_text(json.dumps(record))


@pytest.fixture
def fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path))
    return tmp_path / "field"


def test_a_run_takes_the_field_at_its_flux_that_holds_its_bias(fields: Path) -> None:
    _field(fields)
    _field(fields / "irradiation_flux_1e+15", flux=1e15)

    assert solved_field(_device(), 100.0, 0) == fields
    assert solved_field(_device(), 100.0, 1e15) == fields / "irradiation_flux_1e+15"
    unrelated = _device(lambda content: content.update(capacitance_pF=9.9))
    assert solved_field(unrelated, 0.0, 0) == fields


def test_a_field_that_does_not_serve_the_run_is_refused_with_what_is_missing(
    fields: Path,
) -> None:
    with pytest.raises(FileNotFoundError, match="no field of HPK-Si-PiN"):
        solved_field(_device(), 100.0, 0)

    _field(fields)
    with pytest.raises(FileNotFoundError, match=r"flux 1e\+15.*solved at: \[0.0\]"):
        solved_field(_device(), 100.0, 1e15)
    with pytest.raises(FileNotFoundError, match=r"not solved at 150.0 V.*\[0.0, 100.0\]"):
        solved_field(_device(), 150.0, 0)
    other = _device(lambda content: content["doping"].update(Donors="1e18"))
    with pytest.raises(ValueError, match="another device .doping.Donors."):
        solved_field(other, 100.0, 0)

    _field(fields, solved={"potential": [100.0]})
    with pytest.raises(FileNotFoundError, match="no weighting field"):
        solved_field(_device(), 100.0, 0)
    _field(fields, read=False)
    with pytest.raises(ValueError, match="nothing solved yet"):
        solved_field(_device(), 100.0, 0)
