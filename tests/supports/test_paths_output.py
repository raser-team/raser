from __future__ import annotations

from pathlib import Path

import pytest

from raser.supports.output import create_path
from raser.supports.output import delete_file
from raser.supports.output import owned_path
from raser.supports.io_decorator import io_decorator
from raser.supports.memory_decorator import memory_decorator
from raser.supports.paths import component_file_path
from raser.supports.paths import infer_project_root
from raser.supports.paths import project_root
from raser.supports.paths import project_root_context


def test_project_context_and_component_lookup_use_the_active_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_root = tmp_path / "work"
    application = work_root / "measurement"
    component = application / "components" / "afe" / "selected.json"
    component.parent.mkdir(parents=True)
    component.write_text("{}\n", encoding="utf-8")
    monkeypatch.setenv("RASER_WORK_PATH", str(work_root))
    monkeypatch.delenv("RASER_PROJECT_PATH", raising=False)

    assert infer_project_root("measurement") == application
    with project_root_context(application):
        assert project_root() == application
        assert component_file_path("afe", "selected") == component
    assert "RASER_PROJECT_PATH" not in __import__("os").environ


def test_output_paths_remain_under_the_declared_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path))
    artifact = owned_path("signal", "run-1", "batch")
    assert artifact == tmp_path / "signal" / "run-1" / "batch"
    assert create_path(artifact).is_dir()

    marker = artifact / "marker"
    marker.write_text("value", encoding="utf-8")
    delete_file(marker)
    assert not marker.exists()

    with pytest.raises(ValueError, match="inside the project"):
        owned_path("signal", "../outside")
    with pytest.raises(ValueError, match="inside the project"):
        owned_path("signal", "/outside")
    with pytest.raises(ValueError, match="removal must remain inside"):
        delete_file(tmp_path.parent / "outside")


def test_io_diagnostic_preserves_results_and_failures(
    capsys: pytest.CaptureFixture[str],
) -> None:
    @io_decorator
    def successful() -> int:
        print("payload")
        return 3

    @io_decorator
    def failed() -> None:
        print("before failure")
        raise RuntimeError("visible")

    assert successful() == 3
    assert "payload" in capsys.readouterr().out
    with pytest.raises(RuntimeError, match="visible"):
        failed()
    assert "before failure" in capsys.readouterr().out


def test_memory_diagnostic_preserves_the_wrapped_result(
    capsys: pytest.CaptureFixture[str],
) -> None:
    @memory_decorator
    def measured(value: int) -> int:
        return value + 1

    assert measured(2) == 3
    diagnostic = capsys.readouterr().out
    assert "Memory usage before calling measured" in diagnostic
    assert "Memory usage after calling measured" in diagnostic
