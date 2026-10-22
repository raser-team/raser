from __future__ import annotations

import json
from pathlib import Path

import pytest

from raser.core.device import load_definition
from raser.core.device import resolve_device
from raser.core.field import FieldConfiguration
from raser.core.field import FieldData
from raser.core.field import plan_field
from raser.core.field import read_field_data
from raser.core.field import write_field_data
from raser.core.field.interpolation import calculate_gradient
from raser.core.field.interpolation import interpolate_1d


def test_device_resolution_keeps_definition_and_operating_state_distinct(
    device_project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = tmp_path / "application"
    component_directory = application / "components" / "device"
    component_directory.mkdir(parents=True)
    component = {
        "name": "selected-sensor",
        "device": str(device_project),
        "state": {
            "bias_voltage": -300.0,
            "irradiation": {"fluence": 1.0e14, "unit": "cm^-2"},
        },
        "field": {"mesh": {"maximum_spacing_um": 1.0}},
    }
    (component_directory / "selected-sensor.json").write_text(
        json.dumps(component),
        encoding="utf-8",
    )
    monkeypatch.setenv("RASER_PROJECT_PATH", str(application))

    definition = load_definition(device_project)
    selected = resolve_device(
        "selected-sensor",
        state={"temperature": 300.0},
        field={"solver": {"voltage_step": {"relative_error": 1.0e-8}}},
    )

    assert definition.defaults.bias_voltage == -200.0
    assert selected.state.bias_voltage == -300.0
    assert selected.state.temperature == 300.0
    assert selected.state.irradiation["fluence"] == 1.0e14
    assert selected.field_values["source"] == "devsim"
    assert selected.field_values["dimension"] == 2
    assert selected.field_values["mesh"] == {"maximum_spacing_um": 1.0}
    assert selected.field_values["solver"] == {
        "voltage_step": {"relative_error": 1.0e-8}
    }
    assert selected.definition.runtime_bounds.contains((50.0, 40.0, 25.0))
    assert selected.definition.geant4["envelope_um"] == [140.0, 120.0, 70.0]
    assert selected.definition.readout.electrode_order == ((0, 0),)
    assert selected.definition.electrical["bulk_capacitance_pF"] == 2.5


def test_field_configuration_addresses_device_owned_data(device_project: Path) -> None:
    device = resolve_device(device_project)
    first = FieldConfiguration.from_device(
        device,
        {
            "solver": {
                "voltage_step": {
                    "relative_error": 1.0e-8,
                    "absolute_error": 1.0e10,
                }
            }
        },
    )
    reordered = FieldConfiguration.from_device(
        device,
        {
            "solver": {
                "voltage_step": {
                    "absolute_error": 1.0e10,
                    "relative_error": 1.0e-8,
                }
            }
        },
    )
    changed = FieldConfiguration.from_device(
        device,
        {
            "solver": {
                "voltage_step": {
                    "absolute_error": 1.0e10,
                    "relative_error": 1.0e-7,
                }
            }
        },
    )

    assert first.digest == reordered.digest
    assert first.digest != changed.digest
    assert first.directory(device) == device_project / "field" / first.digest
    assert first.values["solver"]["initial"] == {
        "absolute_error": 1e10,
        "relative_error": 1e-4,
        "maximum_iterations": 100,
    }
    assert first.values["solver"]["voltage_step"]["relative_error"] == 1.0e-8

    config_path = first.write(device)
    assert json.loads(config_path.read_text(encoding="utf-8")) == first.as_dict()


def test_field_plans_cover_solve_import_and_weighting(
    device_project: Path,
    tmp_path: Path,
) -> None:
    device = resolve_device(device_project)
    solve = plan_field("solve", device)
    assert solve.action == "solve"

    tdr = tmp_path / "input.tdr"
    tdr.write_bytes(b"tdr")
    imported = plan_field(
        "import",
        device,
        replacements={"source": "tcad"},
        input_path=tdr,
    )
    assert imported.input_path == tdr.resolve()
    assert imported.configuration.values["source"] == "tcad"
    assert imported.configuration.values["converter"]["input_name"] == "input.tdr"
    assert len(imported.configuration.values["converter"]["input_sha256"]) == 64

    weighting = plan_field("weight", device)
    assert weighting.action == "weight"

    with pytest.raises(ValueError, match="Unknown Field action"):
        plan_field("sample", device)


def test_field_data_round_trip_preserves_values(tmp_path: Path) -> None:
    field_data = FieldData(
        points=((0.0, 0.0), (1.0, 0.0)),
        values=(0.0, 4.0),
        metadata={"voltage": -200.0, "dimension": 2},
    )
    path = write_field_data(tmp_path / "potential.pkl", field_data)

    assert read_field_data(path) == field_data

    with pytest.raises(ValueError, match="equal length"):
        FieldData(points=(0.0,), values=(), metadata={"voltage": 0.0, "dimension": 1})


def test_field_interpolation_and_gradient_use_field_coordinates() -> None:
    potential = interpolate_1d({"points": (0.0, 1.0, 2.0), "values": (0.0, 2.0, 4.0)})
    assert float(potential(1.5)) == pytest.approx(3.0)
    assert calculate_gradient(
        lambda x, y: x * x + 3.0 * y, (2.0, 4.0)
    ) == pytest.approx((4.0, 3.0))
