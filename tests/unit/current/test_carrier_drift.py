from types import SimpleNamespace

import pytest

import raser.core.current.carrier as carrier_module


class FakePlanarField:
    def __init__(self, thickness):
        self.thickness = float(thickness)

    def get_e_field_cached(self, x, y, z):
        return (0.0, 0.0, 2.0e4)

    def get_doping_cached(self, x, y, z):
        return 1.0e12

    def get_w_p_cached(self, x, y, z, electrode_idx):
        return float(z) / self.thickness


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
        vector_delta_t=5.0e-11,
        vector_max_steps=1,
        vector_min_field_strength=0.1,
        vector_boundary_tolerance=0.1,
    )


@pytest.mark.root
def test_drift_step_applies_diffusion_to_carrier_path(monkeypatch):
    detector = make_detector()
    field = FakePlanarField(detector.l_z)
    monkeypatch.setattr(carrier_module.random, "gauss", lambda mu, sigma: 0.25)
    system = carrier_module.VectorizedCarrierSystem(
        [[50.0, 50.0, 25.0]],
        [-10.0],
        [0],
        [[]],
        "Si",
        "electron",
        detector.read_out_contact,
        detector,
    )

    system.drift_batch(detector, field, delta_t=detector.vector_delta_t)

    initial_path = system.paths_reduced[0][0]
    diffused_path = system.paths_reduced[0][1]
    assert diffused_path[0] == pytest.approx(initial_path[0] + 0.25)
    assert diffused_path[1] == pytest.approx(initial_path[1] + 0.25)
    assert diffused_path[2] != pytest.approx(initial_path[2])


@pytest.mark.root
def test_drift_can_skip_full_path_while_keeping_reduced_path(monkeypatch):
    detector = make_detector()
    field = FakePlanarField(detector.l_z)
    monkeypatch.setattr(carrier_module.random, "gauss", lambda mu, sigma: 0.0)
    system = carrier_module.VectorizedCarrierSystem(
        [[50.0, 50.0, 25.0]],
        [-10.0],
        [0],
        [[]],
        "Si",
        "electron",
        detector.read_out_contact,
        detector,
        keep_drift_paths=False,
    )

    system.drift_batch(detector, field, delta_t=detector.vector_delta_t)

    assert system.paths == []
    assert len(system.paths_reduced[0]) == 2
