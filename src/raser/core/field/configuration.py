"""Canonical Field configuration and Device-owned data paths."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from raser.core.device import ResolvedDevice


DEFAULT_SOLVER_SETTINGS: dict[str, Any] = {
    "initial": {
        "absolute_error": 1e10,
        "relative_error": 1e-4,
        "maximum_iterations": 100,
    },
    "voltage_step": {
        "absolute_error": 1e20,
        "relative_error": 1e-4,
        "maximum_iterations": 100,
        "initial": 1.0,
        "maximum": 8.0,
        "increase_factor": 2.0,
        "decrease_factor": 0.5,
    },
    "saved_voltage_interval": 100.0,
    "ac": {
        "real": 1.0,
        "imaginary": 0.0,
        "frequency": 1000.0,
    },
}


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _merge_mapping(
    base: Mapping[str, Any],
    *updates: Mapping[str, Any],
) -> dict[str, Any]:
    merged = dict(base)
    for update in updates:
        for name, value in update.items():
            if isinstance(value, Mapping) and isinstance(merged.get(name), Mapping):
                merged[name] = _merge_mapping(merged[name], value)
            else:
                merged[name] = value
    return merged


@dataclass(frozen=True)
class FieldConfiguration:
    values: Mapping[str, Any]

    @classmethod
    def from_device(
        cls,
        device: ResolvedDevice,
        replacements: Mapping[str, Any] | None = None,
    ) -> "FieldConfiguration":
        field_values = dict(device.field_values)
        replacement_values = dict(replacements or {})
        device_solver = field_values.pop("solver", {})
        replacement_solver = replacement_values.pop("solver", {})
        if not isinstance(device_solver, Mapping) or not isinstance(
            replacement_solver, Mapping
        ):
            raise TypeError("Field solver settings must be a JSON object")

        solver_defaults = deepcopy(DEFAULT_SOLVER_SETTINGS)
        raw_frequency = device.definition.raw.get("frequency")
        if raw_frequency is not None:
            solver_defaults["ac"]["frequency"] = float(raw_frequency)

        values: dict[str, Any] = {
            "device": device.name,
            "device_revision": device.definition.revision,
            "bias_voltage": device.state.bias_voltage,
            "temperature": device.state.temperature,
            "irradiation": dict(device.state.irradiation),
            "area_factor": float(device.definition.raw.get("area_factor", 1.0)),
        }
        values.update(field_values)
        values.update(replacement_values)
        values["solver"] = _merge_mapping(
            solver_defaults,
            device_solver,
            replacement_solver,
        )
        required = ("source", "dimension", "bias_voltage", "temperature")
        missing = [name for name in required if name not in values]
        if missing:
            raise ValueError(f"Field configuration is missing: {', '.join(missing)}")
        values["dimension"] = int(values["dimension"])
        values["bias_voltage"] = float(values["bias_voltage"])
        values["temperature"] = float(values["temperature"])
        if values["dimension"] not in (1, 2, 3):
            raise ValueError("Field dimension must be 1, 2, or 3")
        if str(values["source"]).lower() not in {"devsim", "tcad"}:
            raise ValueError("Field source must be devsim or tcad")
        return cls(values)

    @classmethod
    def resolve(
        cls,
        device: ResolvedDevice,
        replacements: Mapping[str, Any] | None = None,
    ) -> "FieldConfiguration":
        configuration = cls.from_device(device, replacements)
        if str(configuration.values["source"]).lower() != "tcad":
            return configuration

        expected = configuration.as_dict()
        converter = expected.pop("converter", {})
        matches = []
        for path in (device.definition.project_directory / "field").glob(
            "*/config.json"
        ):
            imported = cls(json.loads(path.read_text(encoding="utf-8")))
            values = imported.as_dict()
            imported_converter = values.pop("converter", {})
            if values != expected or not imported_converter.get("input_sha256"):
                continue
            if any(
                imported_converter.get(key) != value for key, value in converter.items()
            ):
                continue
            if path.parent != imported.directory(device):
                raise ValueError(
                    f"TCAD Field configuration does not match its directory: {path}"
                )
            matches.append(imported)
        if not matches:
            raise FileNotFoundError(
                f"No TCAD Field import matches Device {device.name}"
            )
        if len(matches) != 1:
            raise ValueError(f"Multiple TCAD Field imports match Device {device.name}")
        return matches[0]

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical(self.values).encode("utf-8")).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return dict(self.values)

    def directory(self, device: ResolvedDevice) -> Path:
        return device.definition.project_directory / "field" / self.digest

    def write(self, device: ResolvedDevice) -> Path:
        directory = self.directory(device)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "config.json"
        path.write_text(
            json.dumps(self.values, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path


@dataclass(frozen=True)
class FieldPlan:
    action: str
    device: ResolvedDevice
    configuration: FieldConfiguration
    directory: Path
    input_path: Path | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "device": self.device.as_dict(),
            "field_configuration": self.configuration.as_dict(),
            "field_hash": self.configuration.digest,
            "directory": str(self.directory),
            "input": str(self.input_path) if self.input_path else None,
        }


def plan_field(
    action: str,
    device: ResolvedDevice,
    *,
    replacements: Mapping[str, Any] | None = None,
    input_path: str | Path | None = None,
) -> FieldPlan:
    if action not in {"solve", "import", "weight"}:
        raise ValueError(f"Unknown Field action: {action}")
    source_path = Path(input_path).expanduser().resolve() if input_path else None
    if action == "import" and (source_path is None or not source_path.is_file()):
        raise FileNotFoundError(f"Cannot find TCAD input: {source_path}")
    configuration_values = dict(replacements or {})
    if action == "import" and source_path is not None:
        with source_path.open("rb") as stream:
            input_digest = hashlib.file_digest(stream, "sha256").hexdigest()
        converter = dict(configuration_values.get("converter", {}))
        converter.update(
            {
                "input_name": source_path.name,
                "input_sha256": input_digest,
            }
        )
        configuration_values["converter"] = converter
    if action == "import":
        configuration = FieldConfiguration.from_device(device, configuration_values)
    else:
        configuration = FieldConfiguration.resolve(device, configuration_values)
    return FieldPlan(
        action=action,
        device=device,
        configuration=configuration,
        directory=configuration.directory(device),
        input_path=source_path,
    )
