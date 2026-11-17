from __future__ import annotations

import json
from pathlib import Path

import pytest

from raser.components import loader
from raser.lifecycle import workflow
from raser.lifecycle.workflow import Workflow
from raser.lifecycle.workflow import execute

SCRIPT = """
G4SETUP = {"world": "G4_Galactic", "maxstep": 2, "object": {}}
RUNS.append(1) if "RUNS" in globals() else None


def build(construction):
    return {}
"""


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path))
    monkeypatch.delenv("RASER_COMPONENT_PATH", raising=False)
    (tmp_path / "components" / "g4setup").mkdir(parents=True)
    return tmp_path / "components" / "g4setup"


def test_a_script_g4setup_is_its_dictionary_with_its_name_and_the_hash_of_the_file(project: Path) -> None:
    (project / "world.py").write_text(SCRIPT)

    read = loader.read_g4setup("world")
    given = loader.read_g4setup(str(project / "world.py"))

    assert read["world"] == "G4_Galactic" and read["file"] == "world" and len(read["sha256"]) == 64
    assert given["file"] == str(project / "world.py") and given["sha256"] == read["sha256"]


def test_a_json_g4setup_is_refused_and_told_to_be_a_script(project: Path) -> None:
    (project / "old.json").write_text(json.dumps({"world": "G4_AIR", "maxstep": 1}))
    (project / "world.py").write_text(SCRIPT)
    (project / "world.json").write_text("{}")

    with pytest.raises(ValueError, match="old.py"):
        loader.read_g4setup("old")
    with pytest.raises(ValueError, match="world.py"):
        loader.read_g4setup("world")
    with pytest.raises(ValueError, match="a g4setup is a script now"):
        loader.read_g4setup(str(project / "old.json"))


def test_a_script_of_one_path_and_content_runs_once(project: Path) -> None:
    (project / "count.py").write_text("import builtins\nbuiltins.RASER_COUNT = getattr(builtins, 'RASER_COUNT', 0) + 1\nG4SETUP = {}\n")
    import builtins

    loader.load_python_component("g4setup", "count")
    loader.load_python_component("g4setup", "count")

    assert builtins.RASER_COUNT == 1  # type: ignore[attr-defined]
    del builtins.RASER_COUNT  # type: ignore[attr-defined]


def test_a_change_of_the_script_alone_makes_a_run_out_of_date(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(workflow, "_commit", lambda: "abc")
    (project / "world.py").write_text(SCRIPT)
    toy = Workflow(
        name="toy", job=lambda options: None, keys=("g4setup",), defaults={"g4setup": "world"},
        components={"g4setup": "g4setup"}, readers={"g4setup": loader.read_g4setup}, device=False, seeds=False,
    )
    kwargs = {"batch": False, "mem": 1, "dry_run": False, "scan": [], "_entry_command_prefix": ("toy",)}
    execute(toy, kwargs)

    (project / "world.py").write_text(SCRIPT.replace("return {}", "return {'box': 1}"))  # build alone
    lines: list[str] = []
    monkeypatch.setattr("builtins.print", lambda *a, **k: lines.append(" ".join(map(str, a))))
    execute(toy, kwargs)

    assert any("the old run is replaced" in line and "files" in line for line in lines)
