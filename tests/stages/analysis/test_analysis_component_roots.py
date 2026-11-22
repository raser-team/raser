from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from raser.cli.raser import main
from raser.stages import analysis as ana
from raser.supports.paths import app_component_root


def test_ana_finds_the_components_as_the_command_of_the_experiment_does(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RASER_WORK_PATH", str(tmp_path))
    monkeypatch.delenv("RASER_PROJECT_PATH", raising=False)
    monkeypatch.delenv("RASER_COMPONENT_PATH", raising=False)
    experiment = tmp_path / "HPK-Si-PiN" / "signal"
    experiment.mkdir(parents=True)
    config = {"workflow": "signal", "device": "HPK-Si-PiN", "set": {}, "scan": {}}
    (experiment / "config.json").write_text(json.dumps(config))
    roots: list[list[str]] = []
    monkeypatch.setattr(
        ana,
        "execute",
        lambda workflow, kwargs: roots.append(os.environ["RASER_COMPONENT_PATH"].split(os.pathsep)),
    )

    main(["ana", str(experiment)])

    assert roots == [[str(app_component_root("raser_bench/signal"))]]
