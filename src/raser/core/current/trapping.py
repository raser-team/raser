"""Trapping, release and finite lifetime of the carriers of a cluster."""

import math
from dataclasses import dataclass

import numpy as np

from raser.core.seeding import stream

MODES = ("deterministic", "stochastic")
MODEL_KEYS = {
    "enabled",
    "lifetime_enabled",
    "mode",
    "electron_release_time",
    "hole_release_time",
    "trapping_rate_scale",
    "spatial_variation",
}
SPATIAL_KEYS = {"enabled", "seed", "cell_size_um", "lognormal_sigma", "interface"}
INTERFACE_KEYS = {"enabled", "depth_um", "profile_um", "factor"}
max_binomial = 2**31 - 1  # the most carriers ROOT draws a binomial of


@dataclass(frozen=True)
class Interface:
    """Raised trapping within `depth_um` of the contacts at z = 0 and z = l_z."""

    depth_um: float
    profile_um: float
    factor: dict  # "electron", "hole": trapping rate at the contact over that in the bulk
    l_z: float  # um


@dataclass(frozen=True)
class Spatial:
    """Log-normal variation of the trapping rate from cell to cell."""

    seed: int
    cell_size_um: float
    lognormal_sigma: float
    interface: Interface | None


@dataclass(frozen=True)
class Trapping:
    """How the carriers of a cluster are lost on their way.

    `trap`: they are trapped at the rate the field gives; `lifetime`: the
    lifetime [s] of electrons and holes, None where they do not decay.
    Without arguments: trapped at the rate of the field, nothing else.
    """

    trap: bool = True
    lifetime: dict | None = None
    mode: str = "deterministic"
    release_time: dict | None = None  # s, of "electron" and "hole"; None: not released
    scale: dict | None = None  # of the trapping rate, of "electron" and "hole"
    spatial: Spatial | None = None

    @classmethod
    def from_device(cls, my_d):
        """The settings in the keys of `my_d`; see docs/cn/core/current.md."""
        model = getattr(my_d, "trapping_model", None) or {}
        unknown = set(model) - MODEL_KEYS
        if unknown:
            raise ValueError("`trapping_model` has no key {}".format(sorted(unknown)))

        trap = _switch(my_d, "enable_trapping", my_d.irradiation_model is not None)
        if model.get("enabled", True) is False:
            trap = False
        decay = _switch(my_d, "enable_lifetime_decay", False)
        if model.get("lifetime_enabled", True) is False:
            decay = False
        lifetime = None
        if decay:
            lifetime = {}
            for carrier in ("electron", "hole"):
                key = carrier + "_lifetime"
                value = getattr(my_d, key, None)
                if value is None:
                    raise ValueError("`enable_lifetime_decay` is true but `{}` is missing".format(key))
                lifetime[carrier] = _positive(value, key)

        mode = model.get("mode", "deterministic")
        if mode not in MODES:
            raise ValueError("`trapping_model.mode` must be one of {}, not {!r}".format(MODES, mode))

        release = {}
        for carrier in ("electron", "hole"):
            key = carrier + "_release_time"
            if key in model:
                release[carrier] = _positive(model[key], "trapping_model." + key)

        scale = {"electron": 1.0, "hole": 1.0}
        for carrier, value in (model.get("trapping_rate_scale") or {}).items():
            if carrier not in scale:
                raise ValueError("`trapping_model.trapping_rate_scale` has no key {!r}".format(carrier))
            scale[carrier] = _non_negative(value, "trapping_model.trapping_rate_scale." + carrier)

        return cls(trap, lifetime, mode, release or None, scale, _spatial(model, my_d))

    @property
    def active(self):
        """Whether any carrier is lost on the way."""
        return self.trap or self.lifetime is not None


def _switch(my_d, key, default):
    value = getattr(my_d, key, None)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError("`{}` must be true or false, not {!r}".format(key, value))
    return value


def _number(value, key):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("`{}` must be a finite number, not {!r}".format(key, value))
    return float(value)


def _positive(value, key):
    value = _number(value, key)
    if value <= 0:
        raise ValueError("`{}` must be above 0, not {!r}".format(key, value))
    return value


def _non_negative(value, key):
    value = _number(value, key)
    if value < 0:
        raise ValueError("`{}` must not be below 0, not {!r}".format(key, value))
    return value


def _required(block, key, where):
    if key not in block:
        raise ValueError("`{}` is enabled but `{}.{}` is missing".format(where, where, key))
    return block[key]


def _spatial(model, my_d):
    block = model.get("spatial_variation") or {}
    where = "trapping_model.spatial_variation"
    unknown = set(block) - SPATIAL_KEYS
    if unknown:
        raise ValueError("`{}` has no key {}".format(where, sorted(unknown)))
    if not block.get("enabled", False):
        return None
    seed = _required(block, "seed", where)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("`{}.seed` must be an integer, not {!r}".format(where, seed))
    cell = _positive(_required(block, "cell_size_um", where), where + ".cell_size_um")
    sigma = _non_negative(_required(block, "lognormal_sigma", where), where + ".lognormal_sigma")

    interface = None
    block_i = block.get("interface") or {}
    where_i = where + ".interface"
    unknown = set(block_i) - INTERFACE_KEYS
    if unknown:
        raise ValueError("`{}` has no key {}".format(where_i, sorted(unknown)))
    if block_i.get("enabled", False):
        depth = _non_negative(_required(block_i, "depth_um", where_i), where_i + ".depth_um")
        profile = _positive(_required(block_i, "profile_um", where_i), where_i + ".profile_um")
        factor = _required(block_i, "factor", where_i)
        factor = {
            carrier: _non_negative(_required(factor, carrier, where_i + ".factor"), where_i + ".factor." + carrier)
            for carrier in ("electron", "hole")
        }
        interface = Interface(depth, profile, factor, float(my_d.l_z))
    return Spatial(seed, cell, sigma, interface)


def _carrier(carriers):
    return "hole" if carriers > 0 else "electron"


# Gaussian numbers of the cells, one for each cell of a seed, drawn once from a
# stream of its own so that a cell has the same number whichever cluster
# reaches it first. They are drawn anew when the generators are seeded anew,
# which replaces the stream `_anchor` holds.
_cells = {}
_anchor = None


def _cell_number(seed, cell):
    global _anchor
    anchor = stream("trap_cells")
    if anchor is not _anchor:
        _cells.clear()
        _anchor = anchor
    key = (seed, *cell)
    if key not in _cells:
        _cells[key] = stream("trap_cell/{}/{}/{}/{}".format(seed, *cell)).Gaus(0.0, 1.0)
    return _cells[key]


def spatial_factor(spatial, carrier, x, y, z):
    """Factor of the trapping rate at x, y, z [um] from the interface and the cell.

    The interface raises the rate within `depth_um` of a contact by
    1 + (factor - 1) exp(-d / profile_um), d the distance to the contact;
    the cell, a cube of `cell_size_um`, scales it by
    exp(sigma g - sigma^2 / 2), g a Gaussian number fixed by the job seed,
    `seed` and the cell, so that the mean of the factor is 1.
    """
    factor = 1.0
    interface = spatial.interface
    if interface is not None:
        zc = min(max(z, 0.0), interface.l_z)
        distance = min(zc, interface.l_z - zc)
        if distance <= interface.depth_um:
            factor *= 1.0 + (interface.factor[carrier] - 1.0) * math.exp(-distance / interface.profile_um)
    sigma = spatial.lognormal_sigma
    if sigma > 0:
        cell = tuple(math.floor(value / spatial.cell_size_um) for value in (x, y, z))
        factor *= math.exp(sigma * _cell_number(spatial.seed, cell) - 0.5 * sigma * sigma)
    return factor


def trap_rates(path, carriers, my_f, trapping):
    """Rate [1/s] each step of a path traps its carriers at, read at its start."""
    if not trapping.trap:
        return np.zeros(len(path) - 1)
    carrier = _carrier(carriers)
    rate = my_f.get_trap_h_cached if carriers > 0 else my_f.get_trap_e_cached
    rates = np.array([rate(x, y, z) for x, y, z, _ in path[:-1]])
    if trapping.scale is not None and trapping.scale[carrier] != 1.0:
        rates = rates * trapping.scale[carrier]
    if trapping.spatial is not None:
        rates = rates * np.array([spatial_factor(trapping.spatial, carrier, x, y, z) for x, y, z, _ in path[:-1]])
    return rates


def _loss_rates(rates, carriers, trapping):
    if trapping.lifetime is None:
        return rates
    return rates + 1.0 / trapping.lifetime[_carrier(carriers)]


def survivors(path, carriers, my_f, trapping):
    """Carriers of a cluster not yet lost, with their sign: an array (points - 1,).

    `deterministic`: the carriers at the middle of each step, N0 exp(-H), H
    the sum of rate times time over the steps before and half of the step.
    `stochastic`: one realisation, the mean of the numbers at the start and
    at the end of each step; see `stochastic_survivors`.
    """
    if trapping.mode == "stochastic":
        return stochastic_survivors(path, carriers, my_f, trapping)
    rates = _loss_rates(trap_rates(path, carriers, my_f, trapping), carriers, trapping)
    decay = rates * np.diff(path[:, 3])
    return carriers * np.exp(-(np.cumsum(decay) - decay / 2))


def survivors_at(path, carriers, my_f, trapping, step, fraction):
    """Carriers of a cluster not yet lost `fraction` of the way through step
    `step` of its path, as `survivors` does for `deterministic`."""
    rates = _loss_rates(trap_rates(path[: step + 2], carriers, my_f, trapping), carriers, trapping)
    decay = rates * np.diff(path[: step + 2, 3])
    return carriers * np.exp(-(decay[:step].sum() + fraction * decay[step]))


def stochastic_survivors(path, carriers, my_f, trapping):
    """Carriers of a cluster not yet lost, drawn one by one in steps.

    The cluster stands for round(|carriers|) carriers, at least 1, each of
    charge carriers / that number. In a step of time dt a carrier on the
    move is trapped with the probability 1 - exp(-Gamma dt) and lost to its
    lifetime with 1 - exp(-dt / tau); with both, one of them happens with
    probability 1 - exp(-(Gamma + 1 / tau) dt) and is the capture with
    probability Gamma / (Gamma + 1 / tau). Each carrier that was trapped
    before the step is released with probability 1 - exp(-dt / t_release).
    The numbers are binomial draws from the random stream "trap_electron"
    or "trap_hole". Returns, for each step, the carriers on the move at its
    start and end averaged, times their charge.
    """
    carrier = _carrier(carriers)
    steps = len(path) - 1
    if carriers == 0:
        return np.zeros(steps)
    count = max(int(round(abs(carriers))), 1)
    if count > max_binomial:
        raise ValueError(
            "a cluster of {} carriers is too many to draw: at most {}".format(carriers, max_binomial)
        )
    charge = carriers / count

    rates = trap_rates(path, carriers, my_f, trapping)
    lifetime_rate = 0.0 if trapping.lifetime is None else 1.0 / trapping.lifetime[carrier]
    release_time = None if trapping.release_time is None else trapping.release_time.get(carrier)
    release_rate = 0.0 if release_time is None or not trapping.trap else 1.0 / release_time
    generator = stream("trap_" + carrier)
    times = np.diff(path[:, 3])

    mobile = count
    trapped = 0
    out = np.empty(steps)
    for k in range(steps):
        before = mobile
        rate = float(rates[k])
        dt = max(float(times[k]), 0.0)
        old_trapped = trapped
        total = rate + lifetime_rate
        if mobile > 0 and total > 0 and dt > 0:
            events = generator.Binomial(mobile, min(max(-math.expm1(-total * dt), 0.0), 1.0))
            captured = 0
            if events > 0 and rate > 0:
                captured = generator.Binomial(events, min(max(rate / total, 0.0), 1.0))
            mobile -= events
            trapped += captured
        if release_rate > 0 and old_trapped > 0 and dt > 0:
            released = generator.Binomial(old_trapped, min(max(-math.expm1(-release_rate * dt), 0.0), 1.0))
            trapped -= released
            mobile += released
        out[k] = charge * (before + mobile) / 2
    return out
