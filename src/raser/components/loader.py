"""Load JSON definitions from the active component search path, and the
components that are Python files, as the g4setups."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import ModuleType
from typing import Any

from raser.supports.paths import component_file_path
from raser.supports.paths import component_path
from raser.supports.paths import component_roots


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise TypeError(f"Component definition must be a JSON object: {path}")
    return value


def _explicit(selector: str | Path) -> bool:
    """Whether `selector` is a path rather than a name."""
    candidate = Path(selector)
    return bool(
        hasattr(selector, "__fspath__")
        or candidate.is_absolute()
        or (candidate.parts and candidate.parts[0] in {".", ".."})
        or candidate.suffix
    )


def load_component(kind: str, selector: str | Path) -> tuple[Path, dict[str, Any]]:
    explicit = _explicit(selector)
    path = (
        component_file_path(kind, selector)
        if explicit
        else component_path(kind, str(selector) + ".json")
    )
    return path, _read_json(path)


def load_source(selector: str | Path) -> tuple[Path, dict[str, Any]]:
    return load_component("source", selector)


def load_laser(selector: str | Path) -> tuple[Path, dict[str, Any]]:
    return load_component("laser", selector)


# A Python component is run once for a path and its content: (path, sha256) -> module.
_LOADED: dict[tuple[str, str], ModuleType] = {}


def load_python_component(kind: str, selector: str | Path) -> tuple[Path, ModuleType]:
    """The component of `kind` that is a Python file: <kind>/<selector>.py
    among the component roots, or the path given. It is loaded from its path
    under a name of its own and is not put into sys.modules, so two
    experiments' scripts of one name do not take each other's place."""
    path = component_file_path(kind, selector, ".py") if _explicit(selector) else component_path(kind, f"{selector}.py")
    # The bytes are read once: what runs is what the digest is of, never a
    # cached bytecode of the file as it was before.
    source = path.read_bytes()
    digest = hashlib.sha256(source).hexdigest()
    key = (str(path.resolve()), digest)
    if key not in _LOADED:
        module = ModuleType(f"raser_{kind}_{digest[:16]}")
        module.__file__ = str(path)
        exec(compile(source, str(path), "exec"), module.__dict__)
        module.SHA256 = digest
        _LOADED[key] = module
    return path, _LOADED[key]


def read_g4setup(selector: str | Path) -> dict[str, Any]:
    """The g4setup `selector` names, as run.json records it.

    From <name>.py: its G4SETUP, with "file", the name or the path as it was
    given, and "sha256", of the file: a change of the script makes the runs
    that took it out of date even when G4SETUP stays. Its build() is not
    touched here; the deposits slice takes it when it runs. From <name>.json,
    until the g4setups are scripts: the file as it is. A .py and a .json of
    one name in one component root are an error."""
    if _explicit(selector):
        path = Path(selector).expanduser()
        if path.suffix != ".py":
            return load_component("g4setup", selector)[1]
    else:
        for root in component_roots():
            script, data = root / "g4setup" / f"{selector}.py", root / "g4setup" / f"{selector}.json"
            if script.is_file() and data.is_file():
                raise ValueError(f"{root / 'g4setup'}: both {script.name} and {data.name}; keep one of them")
            if data.is_file():
                return load_component("g4setup", selector)[1]
            if script.is_file():
                break
    path, module = load_python_component("g4setup", selector)
    return {**module.G4SETUP, "file": str(selector), "sha256": module.SHA256}
