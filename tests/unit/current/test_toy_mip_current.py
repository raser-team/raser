from types import SimpleNamespace

import pytest

from raser.core.current.cal_current import CalCurrentToyMIP
import raser.core.current.carrier as carrier_module
from raser.core.interaction.toy_mip import ToyMIPLineSource
from raser.supports.math import get_common_interpolate_1d


class FakePlanarField:
    def __init__(self, thickness, mesh_points=None):
        self.thickness = float(thickness)
        self.field_calls = 0
        self.weighting_calls = 0
        if mesh_points is None:
            self.weighting_lookup = None
        else:
            points = [
                index * self.thickness / float(mesh_points - 1)
                for index in range(mesh_points)
            ]
            values = [point / self.thickness for point in points]
            self.weighting_lookup = get_common_interpolate_1d(
                {"points": points, "values": values}
            )

    def get_e_field_cached(self, x, y, z):
        self.field_calls += 1
        return (0.0, 0.0, 2.0e4)

    def get_doping_cached(self, x, y, z):
        return 1.0e12

    def get_w_p_cached(self, x, y, z, electrode_idx):
        self.weighting_calls += 1
        if self.weighting_lookup is not None:
            z = max(0.0, min(self.thickness, float(z)))
            return float(self.weighting_lookup(z))
        return max(0.0, min(1.0, float(z) / self.thickness))

    def get_trap_h_cached(self, x, y, z):
        return 0.0

    def get_trap_e_cached(self, x, y, z):
        return 0.0

    def get_cache_stats(self):
        return {"hits": 0, "misses": 0, "errors": 0, "fallbacks": 0, "hit_rate": 0.0}


class FakePlanarDetector(SimpleNamespace):
    def is_plugin(self):
        return False


def make_detector(thickness=50.0, side=100.0):
    return FakePlanarDetector(
        dimension=1,
        l_x=side,
        l_y=side,
        l_z=thickness,
        p_x=side,
        p_y=side,
        x_ele_num=1,
        y_ele_num=1,
        read_ele_num=1,
        read_out_contact=[{"name": "top", "x_span": 0, "y_span": 0}],
        field_shift_x=0.0,
        field_shift_y=0.0,
        material="Si",
        irradiation_model=None,
        det_model="planar",
        has_avalanche=False,
        vector_delta_t=5.0e-11,
        vector_max_steps=500,
        vector_min_field_strength=0.1,
        vector_boundary_tolerance=0.1,
    )


def run_toy_mip_current(monkeypatch, *, thickness=50.0, packets=4, side=100.0, mesh_points=None):
    monkeypatch.setattr(carrier_module.random, "gauss", lambda mu, sigma: 0.0)
    detector = make_detector(thickness=thickness, side=side)
    field = FakePlanarField(detector.l_z, mesh_points=mesh_points)
    source = ToyMIPLineSource.through_sensor(detector, packets=packets, pairs_per_um=10.0)
    current = CalCurrentToyMIP(detector, field, source)
    field_calculations = (
        current.electron_system.performance_stats["field_calculations"]
        + current.hole_system.performance_stats["field_calculations"]
    )
    return current, field, field_calculations


@pytest.mark.root
def test_toy_mip_current_records_stage_timings():
    detector = make_detector()
    detector.vector_max_steps = 20
    detector.vector_boundary_tolerance = 1.0
    source = ToyMIPLineSource.through_sensor(detector, packets=4, pairs_per_um=10.0)

    current = CalCurrentToyMIP(detector, FakePlanarField(detector.l_z), source)

    for key in (
        "carrier_filter",
        "carrier_system_init",
        "electron_drift",
        "electron_signal",
        "hole_drift",
        "hole_signal",
        "current_histogram",
        "total",
    ):
        assert current.timings[key] >= 0.0
    assert current.timings["total"] >= current.timings["current_histogram"]
    assert current.t_start == pytest.approx(-0.25 * current.t_end)
    assert current.sum_cu[0].GetXaxis().GetXmin() < 0.0
    assert current.sum_cu[0].GetXaxis().GetXmax() == pytest.approx(current.t_end)


@pytest.mark.root
def test_toy_mip_current_work_increases_with_packets_and_thickness(monkeypatch):
    _, _, thin_work = run_toy_mip_current(monkeypatch, thickness=20.0, packets=4)
    _, _, thick_work = run_toy_mip_current(monkeypatch, thickness=80.0, packets=4)
    _, _, few_packet_work = run_toy_mip_current(monkeypatch, thickness=50.0, packets=4)
    _, _, many_packet_work = run_toy_mip_current(monkeypatch, thickness=50.0, packets=16)

    assert thick_work > thin_work
    assert many_packet_work > few_packet_work


@pytest.mark.root
def test_toy_mip_current_tracks_weighting_mesh_lookup_without_geant4(monkeypatch):
    coarse_current, coarse_field, coarse_work = run_toy_mip_current(
        monkeypatch, thickness=50.0, packets=4, mesh_points=16
    )
    fine_current, fine_field, fine_work = run_toy_mip_current(
        monkeypatch, thickness=50.0, packets=4, mesh_points=256
    )

    assert coarse_work == fine_work
    assert coarse_field.weighting_calls == fine_field.weighting_calls
    assert coarse_field.weighting_calls > 0
    assert fine_field.weighting_calls > 0
    assert coarse_current.timings["electron_signal"] >= 0.0
    assert fine_current.timings["electron_signal"] >= 0.0
