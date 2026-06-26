"""Runtime path helpers for package components."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]
DEFAULT_COMPONENT_ROOT = PACKAGE_ROOT / "components"
DEFAULT_WORK_ROOT = REPO_ROOT / "work"


def work_root():
    return Path(os.environ.get("RASER_WORK_PATH", DEFAULT_WORK_ROOT))


def project_root():
    return Path(os.environ.get("RASER_PROJECT_PATH", Path.cwd()))


def project_path(*parts: str):
    return project_root().joinpath(*parts)


def _is_path_input(value: str | os.PathLike):
    path = Path(value)
    return path.is_absolute() or len(path.parts) > 1 or bool(path.suffix)


def _project_root_from_path(path: Path):
    parts = path.parts
    if "components" in parts:
        index = parts.index("components")
        if index > 0:
            return Path(*parts[:index])
    return path if path.is_dir() else path.parent


def infer_project_root(input_value: str | os.PathLike | None):
    if os.environ.get("RASER_PROJECT_PATH"):
        return project_root()
    if input_value is None:
        return project_root()
    if _is_path_input(input_value):
        return _project_root_from_path(Path(input_value).expanduser())
    return work_root() / str(input_value)


@contextmanager
def project_root_context(project_path_value: str | os.PathLike | None):
    if project_path_value is None:
        yield
        return

    previous = os.environ.get("RASER_PROJECT_PATH")
    os.environ["RASER_PROJECT_PATH"] = str(project_path_value)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("RASER_PROJECT_PATH", None)
        else:
            os.environ["RASER_PROJECT_PATH"] = previous


def _as_path_list(paths: str | os.PathLike | list[str | os.PathLike] | None):
    if paths is None:
        return []
    if isinstance(paths, (str, os.PathLike)):
        return [Path(paths)]
    return [Path(path) for path in paths]


def component_roots(
    extra_roots: str | os.PathLike | list[str | os.PathLike] | None = None,
):
    roots = [project_path("components")]
    roots.extend(_as_path_list(extra_roots))
    env_paths = os.environ.get("RASER_COMPONENT_PATH", "")
    roots.extend(Path(path) for path in env_paths.split(os.pathsep) if path)
    roots.append(DEFAULT_COMPONENT_ROOT)

    deduped = []
    seen = set()
    for root in roots:
        key = str(root)
        if key not in seen:
            deduped.append(root)
            seen.add(key)
    return deduped


def app_component_root(app_name: str):
    return PACKAGE_ROOT / "apps" / app_name / "components"


def app_file_path(app_name: str, filename: str):
    path = PACKAGE_ROOT / "apps" / app_name / filename
    if path.exists():
        return path
    raise FileNotFoundError(f"Cannot find RASER app file: {path}")


def app_component_roots(app_name: str, *app_names: str):
    roots = [app_component_root(app_name)]
    roots.extend(app_component_root(name) for name in app_names)
    return component_roots(roots)


def component_candidates(*parts: str, roots=None):
    search_roots = component_roots() if roots is None else list(roots)
    return [root.joinpath(*parts) for root in search_roots]


def component_path(*parts: str, roots=None):
    candidates = component_candidates(*parts, roots=roots)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    searched = "\n  - ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(
        f"Cannot find RASER component {'/'.join(parts)}:\n  - {searched}"
    )


def optional_component_path(*parts: str, roots=None):
    for candidate in component_candidates(*parts, roots=roots):
        if candidate.exists():
            return candidate
    return None


def component_file_path(
    kind: str,
    name_or_path: str | os.PathLike,
    suffix: str = ".json",
):
    if _is_path_input(name_or_path):
        path = Path(name_or_path).expanduser()
        if path.exists():
            return path
        raise FileNotFoundError(f"Cannot find RASER {kind} file: {path}")
    return component_path(kind, str(name_or_path) + suffix)


def module_work_name(current_file_path: str | os.PathLike):
    path = Path(current_file_path).resolve()
    try:
        relative = path.relative_to(PACKAGE_ROOT)
    except ValueError:
        return path.stem

    parts = relative.parts
    if len(parts) >= 2 and parts[0] in {"apps", "core"}:
        return parts[1]
    if parts and parts[0] == "cli":
        return "cli"
    return path.stem


def module_work_path(current_file_path: str | os.PathLike, *labels: str):
    return project_path(module_work_name(current_file_path), *labels)
