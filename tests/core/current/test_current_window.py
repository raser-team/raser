"""The time window of a current is set by the drift, and max_drift_time by the device."""

import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from raser.core.current import cal_current
from raser.core.current.cal_current import CalCurrent
from raser.core.current.drift import max_drift_time_of

sys.path.insert(0, str(Path(__file__).parent))
from test_current_gain_time_axis import _lgad, _last_stop, _UniformField  # noqa: E402

E_FIELD = 1.0e4  # V/cm, the field of _UniformField


class _ConstantMobility:
    """Holes and electrons move at 1000 cm^2/V/s: 100 um/ns in 10 kV/cm."""

    def __init__(self, material, **_):
        pass

    def cal_mobility(self, temperature, doping, charge, field):
        return 1000.0


def _no_gain_device(**keys):
    return SimpleNamespace(
        **{**vars(_lgad()), "has_avalanche": False, "max_drift_time_ns": 100.0, **keys}
    )


def test_the_window_opens_at_the_first_creation_and_reaches_the_last_stop(
    monkeypatch,
) -> None:
    # pairs made at 25.1 um, at 1 us and 3.3 ps after: the electrons reach the
    # face at 0 after 251 ps, the holes the face at 50 um after 249 ps, so the
    # last stop is that of the electrons of the second pair
    monkeypatch.setattr(cal_current, "Material", _ConstantMobility)
    current = CalCurrent(
        _no_gain_device(),
        _UniformField(),
        [100.0, 100.0],
        [[50.0, 50.0, 25.1, 1.0e-6], [50.0, 50.0, 25.1, 1.0e-6 + 3.3e-12]],
        diffusion=False,
    )

    stop = 1.0e-6 + 3.3e-12 + 251e-12
    assert _last_stop(current) == pytest.approx(stop, rel=1e-9, abs=0)
    assert current.t_start == 1.0e-6
    assert 0.0 <= current.t_end - _last_stop(current) < current.t_bin
    # nothing falls before or after the window, and the window holds the charge
    for histogram in (
        current.sum_cu[0],
        current.positive_cu[0],
        current.negative_cu[0],
    ):
        assert histogram.GetBinContent(0) == 0.0
        assert histogram.GetBinContent(current.n_bin + 1) == 0.0
    assert current.current[0].sum() * current.t_bin == pytest.approx(
        current.charge[0], rel=1e-9, abs=0
    )
    assert current.charge[0] != 0.0


def test_the_window_covers_the_stops_of_the_gain_clusters_too() -> None:
    current = CalCurrent(
        SimpleNamespace(**{**vars(_lgad()), "max_drift_time_ns": 100.0}),
        _UniformField(),
        [100.0],
        [[50.0, 50.0, 25.0, 0.0]],
        diffusion=False,
    )

    gain_stops = [
        path[-1][3]
        for system in (
            current.gain_current.electron_system,
            current.gain_current.hole_system,
        )
        if system is not None
        for path in system.paths
    ]
    assert gain_stops
    assert current.t_end >= max(gain_stops)
    assert current.sum_cu[0].GetBinContent(current.n_bin + 1) == 0.0


def _depth_device(**keys):
    return SimpleNamespace(
        l_x=100.0,
        l_y=100.0,
        l_z=50.0,
        temperature=300.0,
        det_name="strip",
        voltage=100.0,
        **keys,
    )


class _Field:
    """`high` V/cm along z above `edge` um, `low` V/cm below it."""

    def __init__(self, high, low=None, edge=0.0):
        self.high, self.low, self.edge = high, high if low is None else low, edge

    def get_e_field_cached(self, x, y, z):
        return (0.0, 0.0, self.high if z >= self.edge else self.low)

    def get_doping_cached(self, x, y, z):
        return 0.0


def _mobility(temperature, doping, charge, field):
    """Electrons 1500, holes 500 cm^2/V/s."""
    return 500.0 if charge > 0 else 1500.0


def test_the_estimate_is_10_times_the_longer_drift_through_the_thickness() -> None:
    # holes: 50 um at 500 * 1e4 cm/s = 1 ns; electrons: 0.33 ns
    estimate = max_drift_time_of(_depth_device(), _Field(E_FIELD), _mobility)

    assert estimate == pytest.approx(10 * 50e-4 / (500.0 * E_FIELD), rel=1e-9, abs=0)


def test_the_estimate_leaves_out_the_part_of_the_depth_where_the_field_is_not_above_min_intensity() -> (
    None
):
    # 0.5 V/cm below 25 um, where a carrier stops: only the upper 25 um count
    estimate = max_drift_time_of(
        _depth_device(), _Field(E_FIELD, low=0.5, edge=25.0), _mobility
    )

    assert estimate == pytest.approx(10 * 25e-4 / (500.0 * E_FIELD), rel=1e-9, abs=0)


def test_a_device_with_no_field_above_min_intensity_along_its_depth_needs_the_key() -> (
    None
):
    with pytest.raises(
        ValueError,
        match=r"strip has no field above 1 V/cm along its depth at the bias 100.0 V",
    ):
        max_drift_time_of(_depth_device(), _Field(0.5), _mobility)


def test_the_estimate_skips_points_where_the_field_has_no_value() -> None:
    class _HalfMesh(_Field):
        def get_e_field_cached(self, x, y, z):
            if z < 25.0:
                raise ValueError("outside the mesh")
            return super().get_e_field_cached(x, y, z)

    estimate = max_drift_time_of(_depth_device(), _HalfMesh(E_FIELD), _mobility)

    assert estimate == pytest.approx(10 * 25e-4 / (500.0 * E_FIELD), rel=1e-9, abs=0)


def test_the_key_of_the_device_file_is_used_in_place_of_the_estimate() -> None:
    # no field at all would make the estimate fail
    assert max_drift_time_of(
        _depth_device(max_drift_time_ns=20.0), _Field(0.5), _mobility
    ) == pytest.approx(20e-9, rel=1e-12, abs=0)


@pytest.mark.parametrize("value", [0, -5.0, float("nan"), float("inf"), "20", None])
def test_a_key_that_is_not_a_positive_finite_number_is_refused(value) -> None:
    device = _depth_device(max_drift_time_ns=value)
    if value is None:
        # an absent key and a key of null both ask for the estimate
        assert max_drift_time_of(device, _Field(E_FIELD), _mobility) > 0
        return
    with pytest.raises(
        ValueError,
        match=r"max_drift_time_ns of strip must be a positive finite number in ns, not ",
    ):
        max_drift_time_of(device, _Field(E_FIELD), _mobility)


def test_a_cluster_drifts_no_longer_than_the_key_of_the_device_file_says(
    monkeypatch,
) -> None:
    # 100 ps: the pair made at 25 um is stopped by the time, not by a face
    # that it would reach after 250 ps
    monkeypatch.setattr(cal_current, "Material", _ConstantMobility)
    current = CalCurrent(
        _no_gain_device(max_drift_time_ns=0.1),
        _UniformField(),
        [100.0],
        [[50.0, 50.0, 25.0, 0.0]],
        diffusion=False,
    )

    assert current.max_drift_time == pytest.approx(100e-12, rel=1e-12, abs=0)
    assert current.ends == {"time_out": [2, 200.0]}
    assert math.isclose(_last_stop(current), 100e-12, abs_tol=2e-12)
