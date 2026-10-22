from __future__ import annotations

from types import SimpleNamespace

import pytest

from raser.core.current.carrier import VectorizedCarrierSystem


class _WeightingField:
    def get_w_p_cached(self, x, y, z, electrode):
        return (electrode + 1) * z / 100.0


class _MissingWeightingField:
    def get_w_p_cached(self, x, y, z, electrode):
        return None


def _system() -> VectorizedCarrierSystem:
    system = VectorizedCarrierSystem.__new__(VectorizedCarrierSystem)
    system.positions = [(5.0, 5.0, 10.0)]
    system.charges = [-1.0]
    system.paths_reduced = [[[5.0, 5.0, 10.0, 0, 0, 0], [5.0, 5.0, 20.0, 1, 0, 0]]]
    system.signals = [[]]
    system._signal_warning_logged = False
    return system


def test_multielectrode_weighting_signals_remain_grouped_by_carrier() -> None:
    system = _system()

    processed = system._process_carrier_signal_multi(
        0,
        _WeightingField(),
        1.0,
        1.0,
        False,
        2,
    )

    assert processed is True
    assert system.signals == [[[-0.1], [-0.2]]]


def test_missing_weighting_potential_fails_at_current_boundary() -> None:
    system = _system()

    with pytest.raises(RuntimeError, match="返回 None"):
        system._get_weighting_potentials_batch(
            _MissingWeightingField(),
            [0.0],
            [0.0],
            [0.0],
            0,
        )


def test_multielectrode_signal_propagates_missing_weighting_potential() -> None:
    system = _system()

    with pytest.raises(RuntimeError, match="返回 None"):
        system._process_carrier_signal_multi(
            0,
            _MissingWeightingField(),
            1.0,
            1.0,
            False,
            2,
        )


def test_vector_step_limit_uses_drift_step_count() -> None:
    system = _system()
    system.active = [True]
    system.steps_drifted = [3]
    system.end_conditions = [0]
    system.reduced_positions = [(5.0, 5.0)]
    system.performance_stats = {
        "boundary_checks": 0,
        "boundary_terminations": 0,
        "carriers_terminated": 0,
    }
    system._params = {"boundary_tolerance": 0.01, "max_vector_steps": 3}
    detector = SimpleNamespace(l_x=10.0, l_y=10.0, l_z=100.0)

    terminated = system.drift_step_batch(
        detector,
        object(),
        delta_t=1.0e-12,
        active_indices=[0],
    )

    assert terminated == 1
    assert system.end_conditions[0] == 4
