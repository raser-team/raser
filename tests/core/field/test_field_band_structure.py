from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any

import pytest

from raser.core.field import create_parameter
from raser.core.model.band_structure import BAND_STRUCTURE


def _solver_parameters(monkeypatch: pytest.MonkeyPatch, material: str, temperature: float) -> dict[str, Any]:
    parameters: dict[str, Any] = {}
    devsim = SimpleNamespace(
        set_parameter=lambda device, region, name, value: parameters.__setitem__(name, value),
        get_material=lambda device, region: material,
    )
    monkeypatch.setattr(create_parameter, "devsim", devsim)
    monkeypatch.setattr(create_parameter.model_create, "CreateNodeModel", lambda *args: None)
    create_parameter.create_parameter(SimpleNamespace(device_dict={"temperature": temperature}), "d", "r")
    return parameters


@pytest.mark.parametrize("temperature", [254.0, 300.0, 350.0])
def test_the_solver_takes_the_silicon_bands_of_core_model_as_they_were(
    monkeypatch: pytest.MonkeyPatch, temperature: float
) -> None:
    # Bitwise the numbers create_parameter worked out itself before.
    n_c = 2.82e19 * pow(temperature / 300, 1.5)
    n_v = 1.83e19 * pow(temperature / 300, 1.5)
    e_g = 1.12 * 1.6e-19
    n_i = pow(n_c * n_v, 0.5) * math.exp(-e_g / (2 * 1.3806503e-23 * temperature))

    parameters = _solver_parameters(monkeypatch, "Silicon", temperature)

    assert (parameters["N_c"], parameters["N_v"], parameters["E_g"], parameters["n_i"]) == (n_c, n_v, e_g, n_i)
    assert parameters["n_i"] == BAND_STRUCTURE["Si"]["n_i"].value(T=temperature)


@pytest.mark.parametrize(
    ("material", "name", "expected"),
    [
        ("SiliconCarbide", "E_g", 3.26 * 1.6 * 1e-19),
        # 4H-SiC n_i from its own bands: 9.3e-9 /cm3 at 300 K, 8.1e-14 at 254 K
        ("SiliconCarbide", "n_i", pow(3.25e15 * pow(254.0, 1.5) * 4.8e15 * pow(254.0, 1.5), 0.5)
         * math.exp(-3.26 * 1.6 * 1e-19 / (2 * 1.3806503e-23 * 254.0))),
        # 4H-SiC at 254 K: 3.25e15 T^1.5, the effective density of states
        ("SiliconCarbide", "N_c", 3.25e15 * pow(254.0, 1.5)),
        ("SiliconCarbide", "N_v", 4.8e15 * pow(254.0, 1.5)),
        ("Diamond", "N_v", 1.5e19 * pow(254.0 / 300, 1.5)),
        ("Diamond", "n_i", pow(1.8e19 * pow(254.0 / 300, 1.5) * 1.5e19 * pow(254.0 / 300, 1.5), 0.5)
         * math.exp(-5.47 * 1.6e-19 / (2 * 1.3806503e-23 * 254.0))),
    ],
)
def test_the_solver_takes_the_other_bands_as_they_were(
    monkeypatch: pytest.MonkeyPatch, material: str, name: str, expected: float
) -> None:
    assert _solver_parameters(monkeypatch, material, 254.0)[name] == expected


def test_the_solver_takes_the_low_field_mobilities_of_diamond(monkeypatch: pytest.MonkeyPatch) -> None:
    # Pernegger et al., J. Appl. Phys. 97 (2005) 073704: electrons 1714, holes 2064 cm2/(V s).
    parameters = _solver_parameters(monkeypatch, "Diamond", 300.0)

    assert (parameters["mu_n"], parameters["mu_p"]) == (1714.0, 2064.0)
