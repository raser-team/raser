"""Trapping, release and lifetime of the carriers of a cluster."""

import math
from types import SimpleNamespace

import numpy as np
import pytest

from raser.core import seeding
from raser.core.current.cal_current import CalCurrent
from raser.core.current.drift import surviving
from raser.core.current.trapping import Trapping, spatial_factor, stochastic_survivors

STEPS = 50
STEP = 1.0e-10  # s


class _Rates:
    """Electrons and holes trapped at `rate` [1/s] everywhere."""

    def __init__(self, rate):
        self.rate = rate

    def get_trap_e_cached(self, x, y, z):
        return self.rate

    def get_trap_h_cached(self, x, y, z):
        return self.rate


def _path(steps=STEPS, step=STEP):
    """A path of `steps` steps of `step` [s], 1 um long each, along z."""
    z = np.arange(steps + 1, dtype=float)
    return np.column_stack([np.full(steps + 1, 50.0), np.full(steps + 1, 50.0), z, np.arange(steps + 1) * step])


def _device(**keys):
    return SimpleNamespace(**{"irradiation_model": None, "l_z": 50.0, **keys})


def test_without_the_new_keys_the_carriers_are_trapped_as_before() -> None:
    path = _path()
    rates = np.linspace(1.0e8, 5.0e9, STEPS)

    class _Varying:
        def get_trap_h_cached(self, x, y, z):
            return rates[int(z)]

        get_trap_e_cached = get_trap_h_cached

    decay = rates * np.diff(path[:, 3])
    before = 100.0 * np.exp(-(np.cumsum(decay) - decay / 2))

    settings = Trapping.from_device(_device(irradiation_model="CommonDefect"))

    assert settings.active
    assert np.array_equal(surviving(path, 100.0, _Varying(), settings), before)
    assert np.array_equal(surviving(path, 100.0, _Varying()), before)
    assert not Trapping.from_device(_device()).active


def test_trapping_follows_the_switch_and_not_the_name_of_the_irradiation_model() -> None:
    path = _path()
    field = _Rates(2.0e9)

    off = Trapping.from_device(_device(irradiation_model="CommonDefect", enable_trapping=False))
    on = Trapping.from_device(_device(enable_trapping=True))

    assert not off.active
    assert surviving(path, 100.0, field, off) == pytest.approx(100.0, abs=0.0)
    assert surviving(path, 100.0, field, on)[-1] == pytest.approx(
        100.0 * math.exp(-2.0e9 * (STEPS - 0.5) * STEP), rel=1e-12, abs=0.0
    )


def test_a_cluster_with_a_lifetime_and_no_trapping_decays_as_exp_of_time_over_lifetime() -> None:
    path = _path()
    tau = {"electron_lifetime": 3.0e-9, "hole_lifetime": 8.0e-9}
    settings = Trapping.from_device(_device(enable_trapping=True, enable_lifetime_decay=True, **tau))

    holes = surviving(path, 100.0, _Rates(0.0), settings)
    electrons = surviving(path, -100.0, _Rates(0.0), settings)

    middle = (np.arange(STEPS) + 0.5) * STEP
    assert holes == pytest.approx(100.0 * np.exp(-middle / 8.0e-9), rel=1e-12, abs=0.0)
    assert electrons == pytest.approx(-100.0 * np.exp(-middle / 3.0e-9), rel=1e-12, abs=0.0)


def test_a_lifetime_without_the_switch_is_not_applied_and_the_switch_needs_both_lifetimes() -> None:
    off = Trapping.from_device(_device(enable_trapping=False, electron_lifetime=1.0e-9, hole_lifetime=1.0e-9))
    assert not off.active

    with pytest.raises(ValueError, match="hole_lifetime"):
        Trapping.from_device(_device(enable_lifetime_decay=True, electron_lifetime=1.0e-9))
    with pytest.raises(ValueError, match="above 0"):
        Trapping.from_device(
            _device(enable_lifetime_decay=True, electron_lifetime=0.0, hole_lifetime=1.0e-9)
        )


def test_twice_the_trapping_rate_scale_doubles_the_exponent() -> None:
    path = _path()
    field = _Rates(1.0e9)

    def exponent(scale):
        settings = Trapping.from_device(
            _device(enable_trapping=True, trapping_model={"trapping_rate_scale": scale})
        )
        return -np.log(surviving(path, 100.0, field, settings)[-1] / 100.0)

    base = exponent({"electron": 1, "hole": 1})
    assert base == pytest.approx(1.0e9 * (STEPS - 0.5) * STEP, rel=1e-12, abs=0.0)
    assert exponent({"electron": 1, "hole": 2}) == pytest.approx(2.0 * base, rel=1e-12, abs=0.0)
    # the scale of the electrons is not that of the holes
    settings = Trapping.from_device(
        _device(enable_trapping=True, trapping_model={"trapping_rate_scale": {"electron": 3}})
    )
    assert -np.log(-surviving(path, -100.0, field, settings)[-1] / 100.0) == pytest.approx(
        3.0 * base, rel=1e-12, abs=0.0
    )
    assert -np.log(surviving(path, 100.0, field, settings)[-1] / 100.0) == pytest.approx(
        base, rel=1e-12, abs=0.0
    )


def _stochastic(**model):
    return Trapping.from_device(_device(enable_trapping=True, trapping_model={"mode": "stochastic", **model}))


def _mean_fraction(settings, clusters, carriers, rate, path):
    """The last step's share of the carriers left, over `clusters` clusters, and its standard error."""
    left = sum(stochastic_survivors(path, carriers, _Rates(rate), settings)[-1] for _ in range(clusters))
    total = clusters * carriers
    fraction = left / total
    return fraction, math.sqrt(fraction * (1 - fraction) / total)


def test_the_mean_of_the_stochastic_survivors_is_the_deterministic_number() -> None:
    seeding.seed_generators(7)
    path = _path()
    rate = 2.0e8  # trap hazard 1.0 over the path
    expected = surviving(path, 1000.0, _Rates(rate), Trapping())[-1] / 1000.0

    fraction, error = _mean_fraction(_stochastic(), 400, 1000.0, rate, path)

    assert abs(fraction - expected) < 3 * error
    # a rate off by 2 % is outside 3 sigma, so the comparison can tell
    assert abs(fraction - expected * math.exp(-0.02)) > 3 * error


def test_the_stochastic_survivors_follow_the_seed() -> None:
    path = _path()
    settings = _stochastic()

    def draw(seed):
        seeding.seed_generators(seed)
        return stochastic_survivors(path, 500.0, _Rates(2.0e8), settings)

    first = draw(11)
    assert np.array_equal(first, draw(11))
    assert not np.array_equal(first, draw(12))
    # carriers of whole charge are lost whole: 500 carriers of charge 1
    seeding.seed_generators(11)
    assert np.all(first * 2 == np.round(first * 2))


def test_trapped_carriers_that_are_released_come_back_to_the_current() -> None:
    seeding.seed_generators(3)
    path = _path(steps=400)
    rate = 1.0e8  # one trap in 10 ns; the path takes 40 ns

    kept, _ = _mean_fraction(_stochastic(), 20, 1000.0, rate, path)
    released, error = _mean_fraction(_stochastic(hole_release_time=1.0e-8), 20, 1000.0, rate, path)

    assert kept < 0.05
    # trapped and released at the same rate, half are on the move after long
    assert released == pytest.approx(0.5, abs=4 * error)
    # the release of electrons does not release holes
    electrons_only, _ = _mean_fraction(_stochastic(electron_release_time=1.0e-8), 20, 1000.0, rate, path)
    assert electrons_only < 0.05


def test_the_stochastic_carriers_lost_to_the_lifetime_are_not_released() -> None:
    seeding.seed_generators(5)
    path = _path(steps=400)
    settings = Trapping.from_device(
        _device(
            enable_trapping=True,
            enable_lifetime_decay=True,
            electron_lifetime=1.0e-8,
            hole_lifetime=1.0e-8,
            trapping_model={"mode": "stochastic", "hole_release_time": 1.0e-9},
        )
    )

    fraction, error = _mean_fraction(settings, 20, 1000.0, 0.0, path)

    # nothing is trapped, so nothing is released: exp(-t / tau) with t = 40 ns
    assert fraction == pytest.approx(math.exp(-4.0 + 0.0), abs=4 * error + 1.0e-3)


def test_unknown_keys_and_modes_are_refused() -> None:
    with pytest.raises(ValueError, match="mode"):
        Trapping.from_device(_device(trapping_model={"mode": "mean"}))
    with pytest.raises(ValueError, match="random_seed"):
        Trapping.from_device(_device(trapping_model={"random_seed": 1}))
    with pytest.raises(ValueError, match="cell_size_um"):
        Trapping.from_device(
            _device(trapping_model={"spatial_variation": {"enabled": True, "seed": 1, "lognormal_sigma": 0.3}})
        )


SPATIAL = {
    "enabled": True,
    "seed": 5,
    "cell_size_um": 25.0,
    "lognormal_sigma": 0.3,
    "interface": {
        "enabled": True,
        "depth_um": 5.0,
        "profile_um": 2.0,
        "factor": {"electron": 3.0, "hole": 4.0},
    },
}


def _spatial(**changes):
    block = {**SPATIAL, **changes}
    return Trapping.from_device(
        _device(enable_trapping=True, trapping_model={"spatial_variation": block})
    ).spatial


def test_the_interface_raises_the_rate_at_the_contacts_by_its_factor_and_the_bulk_not() -> None:
    spatial = _spatial(lognormal_sigma=0.0)

    assert spatial_factor(spatial, "electron", 10.0, 10.0, 0.0) == pytest.approx(3.0, rel=1e-12, abs=0.0)
    assert spatial_factor(spatial, "hole", 10.0, 10.0, 50.0) == pytest.approx(4.0, rel=1e-12, abs=0.0)
    assert spatial_factor(spatial, "hole", 10.0, 10.0, 2.0) == pytest.approx(
        1.0 + 3.0 * math.exp(-1.0), rel=1e-12, abs=0.0
    )
    assert spatial_factor(spatial, "electron", 10.0, 10.0, 5.1) == 1.0
    assert spatial_factor(spatial, "electron", 10.0, 10.0, 25.0) == 1.0


def test_the_cells_vary_with_mean_one_and_a_cell_keeps_its_value() -> None:
    seeding.seed_generators(9)
    spatial = _spatial(interface={"enabled": False})
    cells = [(25.0 * i + 1.0, 25.0 * j + 1.0, 25.0 * k + 1.0) for i in range(12) for j in range(12) for k in range(12)]

    values = np.array([spatial_factor(spatial, "hole", *cell) for cell in cells])

    sigma = 0.3
    assert values.mean() == pytest.approx(1.0, abs=4 * math.sqrt((math.exp(sigma**2) - 1) / len(cells)))
    assert np.log(values).std() == pytest.approx(sigma, rel=0.05)
    # the same cell, from another point of it and after others were asked for
    assert spatial_factor(spatial, "hole", 1.0, 1.0, 1.0) == values[0]
    assert spatial_factor(spatial, "hole", 24.0, 12.0, 20.0) == values[0]
    assert spatial_factor(spatial, "electron", 1.0, 1.0, 1.0) == values[0]
    assert len(set(values)) == len(cells)


def test_the_cells_follow_the_job_seed_and_the_seed_of_the_key() -> None:
    def factor(job, key):
        seeding.seed_generators(job)
        return spatial_factor(_spatial(seed=key, interface={"enabled": False}), "hole", 1.0, 1.0, 1.0)

    assert factor(1, 5) == factor(1, 5)
    assert factor(1, 5) != factor(2, 5)
    assert factor(1, 5) != factor(1, 6)


def test_the_cells_do_not_depend_on_which_is_asked_first() -> None:
    spatial = _spatial(interface={"enabled": False})
    seeding.seed_generators(4)
    a_then_b = (spatial_factor(spatial, "hole", 1.0, 1.0, 1.0), spatial_factor(spatial, "hole", 30.0, 1.0, 1.0))
    seeding.seed_generators(4)
    b_then_a = (spatial_factor(spatial, "hole", 30.0, 1.0, 1.0), spatial_factor(spatial, "hole", 1.0, 1.0, 1.0))

    assert a_then_b == b_then_a[::-1]


class _UniformField:
    """10 kV/cm along z, trapped at `rate`; weighting potential falls linearly from z = 0."""

    cells_either_side = 0
    axes = ("z",)

    def __init__(self, rate):
        self.rate = rate

    def get_e_field_cached(self, x, y, z):
        return (0.0, 0.0, 1.0e4)

    def get_doping_cached(self, x, y, z):
        return 0.0

    def get_conductive(self, x, y, z):
        return False

    def get_w_p(self, x, y, z, electrode):
        return 1.0 - z / 50.0

    def get_trap_e_cached(self, x, y, z):
        return self.rate

    get_trap_h_cached = get_trap_e_cached

    def get_cache_stats(self):
        return {"hits": 0, "misses": 0, "errors": 0, "fallbacks": 0, "hit_rate": 0.0}


def _detector(**keys):
    return SimpleNamespace(**{
        "dimension": 1,
        "is_plugin": lambda: False,
        "material": "Si",
        "temperature": 300.0,
        "l_x": 100.0,
        "l_y": 100.0,
        "l_z": 50.0,
        "p_x": 100.0,
        "p_y": 100.0,
        "x_ele_num": 1,
        "y_ele_num": 1,
        "read_ele_num": 1,
        "read_out_contact": [{"x_span": 0, "y_span": 0, "name": "top"}],
        "irradiation_model": None,
        "det_model": "planar",
        "voltage": 200.0,
        "has_avalanche": False,
        **keys,
    })


def _charge(my_d, rate=2.0e9):
    current = CalCurrent(my_d, _UniformField(rate), [100.0], [[50.0, 50.0, 25.0, 0.0]], diffusion=False)
    return current.charge[0]


def test_the_induced_charge_follows_the_trapping_switch_through_the_current() -> None:
    free = _charge(_detector())
    trapped = _charge(_detector(enable_trapping=True))

    assert _charge(_detector(irradiation_model="CommonDefect", enable_trapping=False)) == free
    assert _charge(_detector(irradiation_model="CommonDefect")) == trapped
    assert abs(trapped) < 0.8 * abs(free)
    # a cluster that is released after a short time is in the current again
    seeding.seed_generators(2)
    stochastic = _charge(
        _detector(
            enable_trapping=True,
            trapping_model={"mode": "stochastic", "electron_release_time": 1.0e-10, "hole_release_time": 1.0e-10},
        )
    )
    seeding.seed_generators(2)
    never = _charge(_detector(enable_trapping=True, trapping_model={"mode": "stochastic"}))
    assert abs(stochastic) > abs(never)
