"""Runtime path helpers for package components."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
# The folder raser, raser_bench and raser_app are installed in, side by side.
PACKAGES_ROOT = PACKAGE_ROOT.parent


def source_tree(package_root=PACKAGE_ROOT):
    """The source tree raser runs from, <tree>/src/raser beside <tree>/pyproject.toml,
    as from a checkout or after pip install -e; None when it is installed as a package."""
    tree = package_root.parents[1]
    return (
        tree
        if package_root.parent.name == "src" and (tree / "pyproject.toml").is_file()
        else None
    )


REPO_ROOT = source_tree()
DEFAULT_COMPONENT_ROOT = PACKAGE_ROOT / "components"


def default_work_root(tree=REPO_ROOT, cwd=None):
    """work/ of the source tree; installed as a package, work/ of the current
    folder: never the folder the package is installed in."""
    return tree / "work" if tree is not None else Path(cwd or Path.cwd()) / "work"


def work_root():
    given = os.environ.get("RASER_WORK_PATH")
    return Path(given) if given is not None else default_work_root()


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
def _environment(name: str, value: str | None):
    if value is None:
        yield
        return

    previous = os.environ.get(name)
    os.environ[name] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


@contextmanager
def project_root_context(
    project_path_value: str | os.PathLike | None,
    component_apps: tuple[str, ...] = (),
):
    project = None if project_path_value is None else str(project_path_value)
    components = None
    if component_apps:
        roots = [str(app_component_root(app)) for app in component_apps]
        previous = os.environ.get("RASER_COMPONENT_PATH")
        if previous:
            roots.append(previous)
        components = os.pathsep.join(roots)
    with _environment("RASER_PROJECT_PATH", project):
        with _environment("RASER_COMPONENT_PATH", components):
            yield


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
    """The components of an app; `app_name` is its folder beside raser, "raser_bench/signal"."""
    return PACKAGES_ROOT / app_name / "components"


def app_file_path(app_name: str, filename: str):
    path = PACKAGES_ROOT / app_name / filename
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
        if path.is_file():
            return path
        if path.exists():
            raise IsADirectoryError(f"RASER {kind} input must be a file: {path}")
        raise FileNotFoundError(f"Cannot find RASER {kind} file: {path}")
    return component_path(kind, str(name_or_path) + suffix)


def module_work_name(current_file_path: str | os.PathLike):
    path = Path(current_file_path).resolve()
    try:
        relative = path.relative_to(PACKAGES_ROOT)
    except ValueError:
        return path.stem

    parts = relative.parts
    if len(parts) >= 2 and parts[0] in {"raser_app", "raser_bench"}:
        return parts[1]
    if len(parts) >= 3 and parts[:2] == ("raser", "core"):
        return parts[2]
    if parts[:2] == ("raser", "cli"):
        return "cli"
    return path.stem


def module_work_path(current_file_path: str | os.PathLike, *labels: str):
    return project_path(module_work_name(current_file_path), *labels)
