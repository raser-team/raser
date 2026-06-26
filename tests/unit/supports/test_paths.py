from pathlib import Path

import pytest

from raser.supports import paths


def test_project_and_work_roots_follow_environment(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    work_root = tmp_path / "work"
    monkeypatch.setenv("RASER_PROJECT_PATH", str(project_root))
    monkeypatch.setenv("RASER_WORK_PATH", str(work_root))

    assert paths.project_root() == project_root
    assert paths.work_root() == work_root
    assert paths.project_path("field", "run") == project_root / "field" / "run"


def test_infer_project_root_maps_bare_name_to_work_project(tmp_path, monkeypatch):
    monkeypatch.setenv("RASER_WORK_PATH", str(tmp_path / "work"))
    monkeypatch.delenv("RASER_PROJECT_PATH", raising=False)

    assert paths.infer_project_root("HPK-Si-PiN") == tmp_path / "work" / "HPK-Si-PiN"


def test_infer_project_root_uses_parent_for_arbitrary_config_path(tmp_path, monkeypatch):
    monkeypatch.delenv("RASER_PROJECT_PATH", raising=False)
    config = tmp_path / "custom-detector.json"

    assert paths.infer_project_root(config) == tmp_path


def test_infer_project_root_uses_components_parent_for_project_config(tmp_path, monkeypatch):
    monkeypatch.delenv("RASER_PROJECT_PATH", raising=False)
    config = tmp_path / "components" / "detector" / "custom.json"

    assert paths.infer_project_root(config) == tmp_path


def test_component_roots_preserve_search_order_and_deduplicate(tmp_path, monkeypatch):
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path))
    extra_root = tmp_path / "extra"
    env_root = tmp_path / "env"
    monkeypatch.setenv(
        "RASER_COMPONENT_PATH",
        str(env_root) + ":" + str(extra_root),
    )

    roots = paths.component_roots([extra_root, extra_root])

    assert roots[:4] == [
        tmp_path / "components",
        extra_root,
        env_root,
        paths.DEFAULT_COMPONENT_ROOT,
    ]
    assert roots.count(extra_root) == 1


def test_component_path_returns_first_existing_candidate(tmp_path):
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_target = first_root / "detector" / "first.json"
    second_target = second_root / "detector" / "first.json"
    second_target.parent.mkdir(parents=True)
    second_target.write_text("{}", encoding="utf-8")

    assert (
        paths.component_path("detector", "first.json", roots=[first_root, second_root])
        == second_target
    )

    first_target.parent.mkdir(parents=True)
    first_target.write_text("{}", encoding="utf-8")

    assert (
        paths.component_path("detector", "first.json", roots=[first_root, second_root])
        == first_target
    )


def test_component_path_reports_all_candidates(tmp_path):
    roots = [tmp_path / "a", tmp_path / "b"]

    with pytest.raises(FileNotFoundError) as excinfo:
        paths.component_path("missing.json", roots=roots)

    message = str(excinfo.value)
    assert "Cannot find RASER component missing.json" in message
    assert str(roots[0] / "missing.json") in message
    assert str(roots[1] / "missing.json") in message


def test_optional_component_path_returns_none_for_missing_file(tmp_path):
    assert paths.optional_component_path("missing.json", roots=[tmp_path]) is None


@pytest.mark.parametrize(
    ("module_file", "expected"),
    [
        (paths.PACKAGE_ROOT / "apps" / "tct" / "tct_signal.py", "tct"),
        (paths.PACKAGE_ROOT / "core" / "field" / "solver_section.py", "field"),
        (paths.PACKAGE_ROOT / "cli" / "raser.py", "cli"),
        (paths.PACKAGE_ROOT / "supports" / "output.py", "output"),
        (Path("/outside/module.py"), "module"),
    ],
)
def test_module_work_name_maps_package_layout(module_file, expected):
    assert paths.module_work_name(module_file) == expected


def test_component_file_path_accepts_explicit_file(tmp_path):
    config = tmp_path / "detector.json"
    config.write_text("{}", encoding="utf-8")

    assert paths.component_file_path("detector", config) == config


def test_module_work_path_uses_project_module_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("RASER_PROJECT_PATH", str(tmp_path))

    result = paths.module_work_path(
        paths.PACKAGE_ROOT / "core" / "current" / "model.py",
        "Si",
        "run-1",
    )

    assert result == tmp_path / "current" / "Si" / "run-1"
