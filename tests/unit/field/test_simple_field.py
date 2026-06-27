import pytest

from raser.core.field.simple import LinearDepletionField1D


def test_linear_depletion_field_keeps_full_depleted_sensor_nonzero():
    field = LinearDepletionField1D(
        thickness_um=100.0,
        bias_voltage=200.0,
        depletion_voltage=100.0,
    )

    values = field.get_e_field_z_many([0.0, 50.0, 100.0])

    assert values[0] == pytest.approx(1.0e4)
    assert values[1] == pytest.approx(2.0e4)
    assert values[2] == pytest.approx(3.0e4)


def test_linear_depletion_field_has_zero_undepleted_region_below_depletion():
    field = LinearDepletionField1D(
        thickness_um=100.0,
        bias_voltage=25.0,
        depletion_voltage=100.0,
    )

    values = field.get_e_field_z_many([0.0, 49.0, 50.0, 75.0, 100.0])

    assert values[0] == 0.0
    assert values[1] == 0.0
    assert values[2] == 0.0
    assert values[3] > 0.0
    assert values[4] == pytest.approx(1.0e4)
