from types import SimpleNamespace

import pytest

from raser.core.interaction.toy_mip import (
    IONIZATION_ENERGY_EV,
    TOY_MIP_PAIRS_PER_UM,
    ToyMIPLineSource,
)


def test_toy_mip_line_source_generates_weighted_packets():
    sensor = SimpleNamespace(l_x=100.0, l_y=50.0, l_z=20.0, material="Si")

    source = ToyMIPLineSource.through_sensor(
        sensor,
        packets=4,
        energy_deposition_mev_per_um=36.0e-6,
        time=2e-9,
    )

    assert len(source.track_position) == 4
    assert source.track_position[0] == [50.0, 25.0, 2.5, 2e-9]
    assert source.track_position[-1] == [50.0, 25.0, 17.5, 2e-9]
    assert source.ionized_pairs == [50.0, 50.0, 50.0, 50.0]
    assert source.energy_deposition_mev == [180.0e-6, 180.0e-6, 180.0e-6, 180.0e-6]
    assert source.energy_loss_ev == IONIZATION_ENERGY_EV["Si"]
    assert source.pairs_per_um == pytest.approx(10.0)


def test_toy_mip_line_source_uses_silicon_ionization_energy_by_default():
    sensor = SimpleNamespace(l_x=100.0, l_y=50.0, l_z=20.0, material="Si")

    source = ToyMIPLineSource.through_sensor(sensor, packets=4)

    assert source.energy_loss_ev == 3.6
    assert source.pairs_per_um == TOY_MIP_PAIRS_PER_UM["Si"]
    assert sum(source.ionized_pairs) == pytest.approx(TOY_MIP_PAIRS_PER_UM["Si"] * sensor.l_z)


def test_toy_mip_line_source_rejects_zero_length_track():
    sensor = SimpleNamespace(l_x=100.0, l_y=50.0, l_z=20.0)

    with pytest.raises(ValueError, match="length"):
        ToyMIPLineSource.through_sensor(
            sensor,
            start=(1.0, 1.0, 1.0),
            end=(1.0, 1.0, 1.0),
        )


def test_toy_mip_line_source_rejects_unknown_material():
    sensor = SimpleNamespace(l_x=100.0, l_y=50.0, l_z=20.0, material="GaAs")

    with pytest.raises(ValueError, match="unsupported"):
        ToyMIPLineSource.through_sensor(sensor)
