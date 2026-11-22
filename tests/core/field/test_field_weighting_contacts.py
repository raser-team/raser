from __future__ import annotations

import pytest

from raser.core.field.solver_section import weighting_contacts


def test_a_resistive_layer_is_one_electrode_on_its_contact_whatever_the_nodes_listed() -> (
    None
):
    device = {
        "det_name": "layered",
        "read_out_contact": [{"name": "node"}],
        "resistive_layer": {"sheet_resistance": 630.0, "contact": "top"},
    }

    assert weighting_contacts(device) == ["top"]


def test_a_resistive_layer_without_its_contact_is_an_error_that_names_the_device_and_the_key() -> (
    None
):
    device = {
        "det_name": "layered",
        "read_out_contact": [{"name": "node"}],
        "resistive_layer": {"sheet_resistance": 630.0},
    }

    with pytest.raises(ValueError, match=r"layered.*resistive_layer\.contact"):
        weighting_contacts(device)


def test_a_device_without_a_resistive_layer_has_its_readout_contacts() -> None:
    device = {"read_out_contact": [{"name": "a", "x_span": 0}, {"name": "b"}]}

    assert weighting_contacts(device) == ["a", "b"]
