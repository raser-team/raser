from pathlib import Path

from raser.supports.output import create_path, delete_file, output
from raser.supports.paths import PACKAGE_ROOT


def test_create_path_creates_nested_directory(tmp_path):
    target = tmp_path / "nested" / "output"

    create_path(target)

    assert target.is_dir()


def test_delete_file_removes_existing_file_and_ignores_missing_file(tmp_path):
    target = tmp_path / "old.txt"
    target.write_text("old", encoding="utf-8")

    delete_file(target)
    delete_file(target)

    assert not target.exists()


def test_output_maps_src_raser_module_to_project_module_directory(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path))
    module_file = PACKAGE_ROOT / "core" / "field" / "solver.py"

    result = Path(output(str(module_file), "HPK-Si-PiN", "run-1"))

    assert result == tmp_path / "field" / "HPK-Si-PiN" / "run-1"
    assert result.is_dir()
