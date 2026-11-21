from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from raser.core.field import create_parameter


def test_the_solver_takes_the_temperature_of_the_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An ITk sensor runs at 254 K: the thermal voltage kT/q is 21.9 mV, not 25.9 mV.
    parameters: dict[str, Any] = {}
    devsim = SimpleNamespace(
        set_parameter=lambda device, region, name, value: parameters.__setitem__(name, value),
        get_material=lambda device, region: "Silicon",
    )
    monkeypatch.setattr(create_parameter, "devsim", devsim)
    monkeypatch.setattr(create_parameter.model_create, "CreateNodeModel", lambda *args: None)
    detector = SimpleNamespace(device_dict={"temperature": 254.0})

    create_parameter.create_parameter(detector, "device", "region")

    assert parameters["T"] == 254.0
    assert parameters["Volt_thermal"] == pytest.approx(1.380649e-23 * 254.0 / 1.602176634e-19, rel=1e-5)
