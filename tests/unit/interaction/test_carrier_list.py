from types import SimpleNamespace

import pytest

from raser.core.interaction.carrier_list import CarrierListFromG4P


def test_g4_carrier_list_uses_zero_trigger_time():
    g4 = SimpleNamespace(
        p_steps_current=[[[1.0, 2.0, 3.0]]],
        energy_steps=[[3.6e-6]],
        edep_devices=[3.6e-6],
        selected_batch_number=None,
    )

    carrier_list = CarrierListFromG4P("Si", g4, 0)

    assert carrier_list.track_position == [[1.0, 2.0, 3.0, 0.0]]
    assert carrier_list.ionized_pairs == pytest.approx([1.0])
