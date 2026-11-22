from __future__ import annotations

from types import SimpleNamespace

import pytest

from raser.stages import current


def _taken(
    monkeypatch: pytest.MonkeyPatch, device_dict: dict, read_out_contact: list[dict]
) -> list:
    """The electrodes the stage hands to the field of a device."""
    given: list = []

    def field(name, voltage, electrodes, **kwargs):
        given.append(electrodes)
        return "field"

    monkeypatch.setattr("raser.stages.current.devfield.DevsimField", field)
    monkeypatch.setattr(
        "raser.stages.current.solved_field", lambda my_d, voltage, flux: "folder"
    )
    device = SimpleNamespace(
        device="d", voltage=200.0, read_out_contact=read_out_contact, irradiation_flux=0.0,
        bound={}, device_dict=device_dict, p_x=50.0, p_y=50.0,
    )  # fmt: skip

    assert current.solved(device, {}) == "field"
    return given


def test_the_field_of_a_device_with_a_resistive_layer_is_the_one_of_the_contact_of_the_layer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    given = _taken(
        monkeypatch,
        {"resistive_layer": {"contact": "top"}},
        [{"name": "node", "x_span": 0}],
    )

    assert given == [[{"name": "top"}]]


def test_the_field_of_a_device_without_one_is_the_one_of_its_readout_contacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listed = [{"name": "a"}, {"name": "b"}]

    assert _taken(monkeypatch, {}, listed) == [listed]
