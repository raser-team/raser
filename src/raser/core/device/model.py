"""Device definitions, project references, and resolved operating states."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from raser.supports.paths import component_file_path
from raser.supports.paths import project_path
from raser.supports.paths import work_root


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _read_object(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise TypeError(f"Device definition must be a JSON object: {path}")
    return value


def _irradiation(raw: Mapping[str, Any]) -> dict[str, Any]:
    value = raw.get("irradiation", {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError("Device irradiation state must be a JSON object")
    return dict(value)


def _bounds2(values: Any, *, axis: str) -> tuple[float, float]:
    bounds = tuple(map(float, values))
    if len(bounds) != 2:
        raise ValueError(f"Runtime {axis} bounds must contain two values")
    return bounds[0], bounds[1]


@dataclass(frozen=True)
class RuntimeBounds:
    x: tuple[float, float]
    y: tuple[float, float]
    z: tuple[float, float]

    def __post_init__(self) -> None:
        for axis, bounds in zip(("x", "y", "z"), (self.x, self.y, self.z)):
            if len(bounds) != 2 or bounds[0] >= bounds[1]:
                raise ValueError(f"Runtime {axis} bounds must increase")

    def contains(self, point: tuple[float, float, float]) -> bool:
        return all(
            lower <= coordinate <= upper
            for coordinate, (lower, upper) in zip(point, (self.x, self.y, self.z))
        )


@dataclass(frozen=True)
class ReadoutLayout:
    x_count: int
    y_count: int
    pitch_x_um: float
    pitch_y_um: float
    contacts: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.x_count <= 0 or self.y_count <= 0:
            raise ValueError("Readout axis counts must be positive")
        if self.pitch_x_um <= 0 or self.pitch_y_um <= 0:
            raise ValueError("Readout pitches must be positive")
        if len(set(self.contacts)) != len(self.contacts):
            raise ValueError("Readout contact names must be unique")

    @property
    def electrode_count(self) -> int:
        return self.x_count * self.y_count

    @property
    def electrode_order(self) -> tuple[tuple[int, int], ...]:
        return tuple(
            (x_index, y_index)
            for y_index in range(self.y_count)
            for x_index in range(self.x_count)
        )


@dataclass(frozen=True)
class DeviceState:
    bias_voltage: float
    temperature: float
    irradiation: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "bias_voltage": self.bias_voltage,
            "temperature": self.temperature,
            "irradiation": dict(self.irradiation),
        }


@dataclass(frozen=True)
class DeviceDefinition:
    name: str
    model: str
    material: str
    revision: str
    source_path: Path
    project_directory: Path
    dimensions_um: tuple[float, float, float]
    runtime_bounds: RuntimeBounds
    readout: ReadoutLayout
    defaults: DeviceState
    field_defaults: Mapping[str, Any]
    electrical: Mapping[str, Any]
    geant4: Mapping[str, Any]
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class ResolvedDevice:
    definition: DeviceDefinition
    state: DeviceState
    field_values: Mapping[str, Any]
    component_path: Path | None = None

    @property
    def name(self) -> str:
        return self.definition.name

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "revision": self.definition.revision,
            "definition": str(self.definition.source_path),
            "component": str(self.component_path) if self.component_path else None,
            "state": self.state.as_dict(),
            "field": dict(self.field_values),
        }


def _definition_path(selector: str | Path) -> tuple[Path, Path]:
    candidate = Path(selector).expanduser()
    if candidate.is_dir():
        path = candidate / "device.json"
        if path.is_file():
            return path, candidate
        raise FileNotFoundError(f"Device project has no device.json: {candidate}")
    if candidate.suffix or len(candidate.parts) > 1:
        if candidate.is_file():
            return candidate, candidate.parent
        raise FileNotFoundError(f"Cannot find Device definition: {candidate}")

    project_candidate = work_root() / str(selector) / "device.json"
    if project_candidate.is_file():
        return project_candidate, project_candidate.parent

    packaged = component_file_path("device", str(selector))
    return packaged, work_root() / str(selector)


def _readout(raw: Mapping[str, Any]) -> ReadoutLayout:
    model = str(raw["det_model"]).lower()
    length_x = float(raw["l_x"])
    length_y = float(raw["l_y"])
    if "pixel" in model:
        x_count = int(raw["x_ele_num"])
        y_count = int(raw["y_ele_num"])
        pitch_x = float(raw["p_x"])
        pitch_y = float(raw["p_y"])
    elif "strip" in model:
        x_count = int(raw["read_ele_num"])
        y_count = 1
        pitch_x = float(raw["p_x"])
        pitch_y = length_y
    else:
        x_count = 1
        y_count = 1
        pitch_x = length_x
        pitch_y = length_y

    contacts = tuple(str(entry["name"]) for entry in raw.get("read_out_contact", []))
    if not contacts:
        raise ValueError("Device readout requires at least one contact")
    return ReadoutLayout(x_count, y_count, pitch_x, pitch_y, contacts)


def load_definition(selector: str | Path) -> DeviceDefinition:
    path, project_directory = _definition_path(selector)
    raw = _read_object(path)
    required = ("det_model", "material", "l_x", "l_y", "l_z", "bias", "temperature")
    missing = [name for name in required if name not in raw]
    if missing:
        raise ValueError(f"Device definition is missing: {', '.join(missing)}")

    name = str(raw.get("det_name", path.stem))
    dimensions = (float(raw["l_x"]), float(raw["l_y"]), float(raw["l_z"]))
    if any(value <= 0 for value in dimensions):
        raise ValueError("Device dimensions must be positive")

    runtime = raw.get("runtime_bounds")
    if runtime is None:
        runtime_bounds = RuntimeBounds(
            (0.0, dimensions[0]),
            (0.0, dimensions[1]),
            (0.0, dimensions[2]),
        )
    else:
        runtime_bounds = RuntimeBounds(
            _bounds2(runtime["x"], axis="x"),
            _bounds2(runtime["y"], axis="y"),
            _bounds2(runtime["z"], axis="z"),
        )

    bias = raw["bias"]
    defaults = DeviceState(
        bias_voltage=float(bias["voltage"]),
        temperature=float(raw["temperature"]),
        irradiation=_irradiation(raw),
    )
    field_defaults = dict(raw.get("field", {}))
    field_defaults.setdefault("source", raw.get("field_source", "devsim"))
    field_defaults.setdefault(
        "dimension", int(raw.get("field_dimension", raw.get("default_dimension", 1)))
    )

    electrical = dict(raw.get("electrical", {}))
    if "capacitance_pF" in raw:
        electrical.setdefault("bulk_capacitance_pF", float(raw["capacitance_pF"]))
    elif "capacitance" in raw:
        electrical.setdefault("bulk_capacitance_pF", float(raw["capacitance"]))

    geant4 = dict(raw.get("geant4", {}))
    geant4.setdefault("sensitive_volumes", ["Device"])
    geant4.setdefault(
        "detector_mapping",
        {"translation_um": [dimensions[0] / 2.0, dimensions[1] / 2.0, 0.0]},
    )
    sensitive_volumes = geant4["sensitive_volumes"]
    if not isinstance(sensitive_volumes, list) or not all(
        isinstance(name, str) and name for name in sensitive_volumes
    ):
        raise ValueError("Geant4 sensitive volumes must be named")
    mapping = geant4["detector_mapping"]
    if not isinstance(mapping, dict):
        raise TypeError("Geant4 detector mapping must be a JSON object")
    revision = hashlib.sha256(_canonical_json(raw).encode("utf-8")).hexdigest()
    return DeviceDefinition(
        name=name,
        model=str(raw["det_model"]),
        material=str(raw["material"]),
        revision=revision,
        source_path=path.resolve(),
        project_directory=project_directory.resolve(),
        dimensions_um=dimensions,
        runtime_bounds=runtime_bounds,
        readout=_readout(raw),
        defaults=defaults,
        field_defaults=field_defaults,
        electrical=electrical,
        geant4=geant4,
        raw=raw,
    )


def _component_path(selector: str | Path) -> Path | None:
    candidate = Path(selector).expanduser()
    if candidate.is_file():
        value = _read_object(candidate)
        return candidate if "device" in value else None
    if candidate.suffix or len(candidate.parts) > 1:
        return None
    path = project_path("components", "device", str(selector) + ".json")
    return path if path.is_file() else None


def resolve_device(
    selector: str | Path,
    *,
    state: Mapping[str, Any] | None = None,
    field: Mapping[str, Any] | None = None,
) -> ResolvedDevice:
    component_path = _component_path(selector)
    component: dict[str, Any] = {}
    definition_selector: str | Path = selector
    if component_path is not None:
        component = _read_object(component_path)
        definition_selector = component["device"]

    definition = load_definition(definition_selector)
    state_values = definition.defaults.as_dict()
    state_values.update(component.get("state", {}))
    state_values.update(state or {})
    resolved_state = DeviceState(
        bias_voltage=float(state_values["bias_voltage"]),
        temperature=float(state_values["temperature"]),
        irradiation=dict(state_values.get("irradiation", {})),
    )

    field_values = dict(definition.field_defaults)
    field_values.update(component.get("field", {}))
    field_values.update(field or {})
    return ResolvedDevice(definition, resolved_state, field_values, component_path)
