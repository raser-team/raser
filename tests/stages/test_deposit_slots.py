from __future__ import annotations

from typing import Any

import pytest

from raser.stages import chain
from raser.stages import deposit as stage


class _Detector:
    def __init__(self, name: str, device: dict[str, Any]) -> None:
        self.name, self.device = name, device


def test_slots_are_built_from_the_device_table_in_its_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stage.bdv, "Detector", _Detector)
    files = {
        "dut": {"device": {"det_name": "PiN"}},
        "ref": {"device": {"det_name": "LGAD"}},
    }
    built = stage.detectors({"_files": files}, ("ref", "dut"))
    assert list(built) == ["ref", "dut"]
    assert [d.name for d in built.values()] == ["LGAD", "PiN"]


def test_a_single_device_keeps_its_one_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stage.bdv, "Detector", _Detector)
    built = stage.detectors({"det_name": "PiN", "_files": {"device": {"det_name": "PiN"}}})
    assert list(built) == ["Device"]


def test_the_deposit_slice_of_several_devices_carries_their_names_in_table_order() -> None:
    table = {"ref": ("LGAD", ["ref"]), "dut": (None, ["dut"])}
    run = chain.expand(table)[0].run
    assert run.keywords["slots"] == ("ref", "dut")


def test_the_field_of_a_device_of_several_is_found_in_its_own_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    import os

    monkeypatch.setenv("RASER_WORK_PATH", str(tmp_path))
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path / "PiN"))
    seen: list[str] = []

    def ready(options: dict[str, Any], files: dict[str, Any]) -> str:
        seen.append(os.environ["RASER_PROJECT_PATH"])
        return "folder"

    monkeypatch.setattr(chain.field, "ready", ready)
    kwargs = {"det_name": "PiN", "_files": {"ref": {"device": {"det_name": "LGAD"}}}}
    assert chain._field(kwargs, device="ref") == {"field": "folder"}
    assert seen == [str(tmp_path / "LGAD")]


def test_only_the_field_lookup_of_a_device_of_several_leaves_the_project_of_the_experiment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    import os

    from raser.stages import current
    from raser.stages import files

    monkeypatch.setenv("RASER_WORK_PATH", str(tmp_path))
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path / "PiN"))
    seen: dict[str, str] = {}

    def solved_field(my_d: Any, voltage: float, flux: float) -> str:
        seen["field"] = os.environ["RASER_PROJECT_PATH"]
        return "folder"

    def devsim_field(*args: Any, **kwargs: Any) -> str:
        seen["drift"] = os.environ["RASER_PROJECT_PATH"]
        return kwargs["field_directory"]

    monkeypatch.setattr(current, "solved_field", solved_field)
    monkeypatch.setattr(current.devfield, "DevsimField", devsim_field)
    kwargs = chain._of({"det_name": "PiN", "_files": {"ref": {"device": {"det_name": "LGAD"}}}}, "ref")

    class Device:
        irradiation_flux, voltage, device, bound, p_x, p_y = 0, -200, "LGAD", None, 0, 0
        read_out_contact: list[dict[str, Any]] = []
        device_dict: dict[str, Any] = {}

    assert current.solved(Device(), kwargs) == "folder"
    assert seen == {"field": str(tmp_path / "LGAD"), "drift": str(tmp_path / "PiN")}
    with files.field_project({"det_name": "PiN"}):
        assert os.environ["RASER_PROJECT_PATH"] == str(tmp_path / "PiN")


def _recorded(monkeypatch: pytest.MonkeyPatch, kwargs: dict[str, Any], slots: tuple[str, ...]) -> tuple[Any, ...]:
    """The arguments the deposits stage hands to write_simulated_deposits."""
    seen: list[tuple[Any, ...]] = []
    monkeypatch.setattr(stage, "detectors", lambda kwargs, slots=None: dict.fromkeys(slots or ()))
    monkeypatch.setattr(stage, "output", lambda kwargs, name: "deposit.h5")

    def record(*args: Any) -> int:
        seen.append(args)
        return 1

    monkeypatch.setattr(stage, "write_simulated_deposits", record)
    base = {"_files": {"source": {}}, "seed": 1, "fano": False, "events_per_job": 5}
    stage.deposits({**base, **kwargs}, slots)
    return seen[0]


def test_the_logic_and_the_time_window_reach_the_recording(monkeypatch: pytest.MonkeyPatch) -> None:
    args = _recorded(monkeypatch, {"require": "ref AND dut", "coincidence_window_ns": 2.5}, ("ref", "dut"))
    assert args[6:9] == (
        {"ref": (None, None), "dut": (None, None)},
        "ref AND dut",
        2.5,
    )


def test_the_energy_window_of_a_slot_replaces_only_its_own_side(monkeypatch: pytest.MonkeyPatch) -> None:
    kwargs = {"require": "any", "edep_min": 0.01, "edep_max": 0.5, "dut.edep_min": 0.03, "ref.edep_max": 0.2}
    windows = _recorded(monkeypatch, kwargs, ("ref", "dut"))[6]
    assert windows == {"ref": (0.01, 0.2), "dut": (0.03, 0.5)}
