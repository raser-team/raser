from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from raser.apps._planning import activate_plan
from raser.apps._planning import execution_seed
from raser.apps.cce.workflow import build_plan as build_cce_plan
from raser.apps.signal.runtime import apply_signal_plan
from raser.apps.signal.workflow import build_plan
from raser.apps.tct.workflow import build_plan as build_tct_plan
from raser.apps.tct.workflow import runtime_components
from raser.cli.raser import main


@pytest.mark.parametrize(
    ("arguments", "workflow", "component_kinds", "stages"),
    [
        (
            ["signal", "HPK-Si-PiN", "--dry-run"],
            "signal",
            ["Source", "AFE"],
            ["Interaction", "Current", "Frontend"],
        ),
        (
            ["cce", "HPK-Si-PiN", "--dry-run"],
            "cce",
            ["Source", "AFE", "G4Setup", "ADC"],
            [
                "Interaction",
                "Current",
                "Frontend",
                "ADC",
                "Metrics",
                "Charge-collection analysis",
            ],
        ),
        (
            ["tct", "signal", "HPK-Si-PiN", "SPA_top_Si", "--dry-run"],
            "tct",
            ["Laser", "AFE"],
            ["Interaction", "Current", "Frontend"],
        ),
        (
            ["timeres", "HPK-Si-PiN", "--dry-run"],
            "timeres",
            ["Source", "AFE", "G4Setup", "ADC"],
            [
                "Interaction",
                "Current",
                "Frontend",
                "ADC",
                "Metrics",
                "Time-resolution analysis",
            ],
        ),
    ],
)
def test_application_dry_run_resolves_the_complete_plan_without_execution(
    arguments: list[str],
    workflow: str,
    component_kinds: list[str],
    stages: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    work_root = tmp_path / "work"
    monkeypatch.setenv("RASER_WORK_PATH", str(work_root))
    monkeypatch.delenv("RASER_PROJECT_PATH", raising=False)
    monkeypatch.delenv("RASER_COMPONENT_PATH", raising=False)
    external_modules = {
        name: name in sys.modules for name in ("ROOT", "devsim", "g4ppyy")
    }

    assert main(arguments) == 0
    plan = json.loads(capsys.readouterr().out)

    assert plan["workflow"] == workflow
    assert [component["kind"] for component in plan["components"]] == component_kinds
    assert plan["stages"] == stages
    assert len(plan["device"]["revision"]) == 64
    assert len(plan["field"]["hash"]) == 64
    assert {name: name in sys.modules for name in external_modules} == external_modules
    assert not work_root.exists()


def test_field_dry_run_resolves_hash_and_destination_without_writing(
    device_project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("RASER_WORK_PATH", str(tmp_path / "work"))
    assert main(["field", str(device_project), "-bias", "-250", "--dry-run"]) == 0
    plan = json.loads(capsys.readouterr().out)

    assert plan["action"] == "solve"
    assert plan["field_configuration"]["bias_voltage"] == -250.0
    assert plan["directory"] == str(device_project / "field" / plan["field_hash"])
    assert not (device_project / "field").exists()


def test_execution_activates_one_immutable_plan_before_worker_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "work" / "HPK-Si-PiN"
    monkeypatch.setenv("RASER_WORK_PATH", str(tmp_path / "work"))
    monkeypatch.setenv("RASER_PROJECT_PATH", str(project))
    kwargs: dict[str, Any] = {
        "det_name": "HPK-Si-PiN",
        "source": "decay/Sr90",
        "amplifier": "Broad_Band_UCSC",
        "voltage": None,
        "irradiation": None,
        "events_per_job": 4,
        "scan": 2,
        "seed": 7,
        "run": "run-1",
    }
    plan = build_plan(kwargs)
    record = activate_plan(plan, kwargs)

    run_root = project / "signal" / "run-1"
    assert kwargs["_run_path"] == str(run_root)
    assert kwargs["_field_directory"] == plan.field["directory"]
    assert record["work"] == {"events_per_job": 4, "jobs": 2, "seed": 7}
    assert json.loads((run_root / "run.json").read_text(encoding="utf-8")) == record

    activate_plan(plan, kwargs)
    changed = dict(kwargs)
    changed["voltage"] = 250.0
    with pytest.raises(ValueError, match="different device specification"):
        activate_plan(build_plan(changed), changed)


def test_signal_runtime_uses_the_components_recorded_in_the_active_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "work" / "HPK-Si-PiN"
    monkeypatch.setenv("RASER_WORK_PATH", str(tmp_path / "work"))
    monkeypatch.setenv("RASER_PROJECT_PATH", str(project))
    kwargs: dict[str, Any] = {
        "det_name": "HPK-Si-PiN",
        "source": "decay/Sr90",
        "amplifier": None,
        "adc": None,
        "voltage": None,
        "irradiation": None,
        "events_per_job": 4,
        "scan": None,
        "seed": 7,
        "run": "run-1",
    }
    plan = build_cce_plan(kwargs)
    activate_plan(plan, kwargs)
    detector = SimpleNamespace(daq=None)

    apply_signal_plan(detector, kwargs)

    assert detector.g4experiment == "charge_collection"
    assert detector.g4_config["geant4_model"] == "charge_collection"
    assert detector.g4_config["source_kind"] == "decay_source"
    assert detector.amplifier == "Broad_Band_UCSC"
    assert detector.daq == "Alibava"
    assert detector.signal_source == "Sr90"
    assert detector.signal_output_label == "cce"


def test_tct_runtime_uses_the_components_recorded_in_the_active_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "work" / "HPK-Si-PiN"
    monkeypatch.setenv("RASER_WORK_PATH", str(tmp_path / "work"))
    monkeypatch.setenv("RASER_PROJECT_PATH", str(project))
    kwargs: dict[str, Any] = {
        "det_name": "HPK-Si-PiN",
        "laser": "SPA_top_Si_IR",
        "amplifier": None,
        "voltage": 200.0,
        "scan": None,
        "seed": 7,
        "run": "run-1",
    }
    plan = build_tct_plan(kwargs)
    activate_plan(plan, kwargs)
    kwargs["laser"] = "changed-after-activation"
    kwargs["amplifier"] = "changed-after-activation"

    laser, amplifier = runtime_components(kwargs)

    assert laser["laser_model"] == "SPA_top_Si_IR"
    assert amplifier == "Broad_Band_UCSC"


def test_execution_seed_uses_the_recorded_seed_and_worker_offset() -> None:
    assert execution_seed({"seed": 7}) == 7
    assert execution_seed({"seed": 7}, offset=20) == 27
    with pytest.raises(ValueError, match="non-negative"):
        execution_seed({"seed": -1})


def test_global_batch_test_keeps_commands_structured_and_scheduler_idle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    work_root = tmp_path / "work"
    monkeypatch.setenv("RASER_WORK_PATH", str(work_root))
    monkeypatch.delenv("RASER_PROJECT_PATH", raising=False)

    assert main(["-t", "-b", "signal", "HPK-Si-PiN"]) == 0
    assert "hep_sub" in capsys.readouterr().out
    assert not work_root.exists()
