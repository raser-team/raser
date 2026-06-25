from pathlib import Path

from raser.util.output import create_path, delete_file, output


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


def test_output_maps_src_raser_module_to_output_directory(tmp_path):
    module_file = tmp_path / "src" / "raser" / "field" / "solver.py"
    module_file.parent.mkdir(parents=True)
    module_file.write_text("# placeholder\n", encoding="utf-8")

    result = Path(output(str(module_file), "HPK-Si-PiN", "run-1"))

    assert result == tmp_path / "output" / "field" / "HPK-Si-PiN" / "run-1"
    assert result.is_dir()
