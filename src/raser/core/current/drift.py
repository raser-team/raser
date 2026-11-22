"""Drift of a cluster of charge carriers through a detector."""

import logging
import math
from dataclasses import dataclass

import numpy as np

from raser.core.seeding import stream

from .trapping import Trapping, survivors, survivors_at

kboltz = 8.617333262e-5  # eV/K
e0 = 1.602176634e-19  # C
min_intensity = 1  # V/cm, a carrier in a field not above this stops
depth_step = 0.1  # um, the spacing of the points along the depth the estimate of max_drift_time sums over
margin = 10  # the estimate of max_drift_time is this times the longer drift through the thickness

logger = logging.getLogger(__name__)


@dataclass
class Drifted:
    """Clusters of carriers of one sign after their drift, one entry each."""

    carriers: list  # number of carriers of each, with their sign
    paths: list  # what `drift` returns: arrays (points, 4) of x, y, z [um], t [s]
    reasons: list  # why each stopped
    # of each, the carriers not yet trapped at the middle of every step of
    # its path, with their sign: an array (points - 1,), as `surviving`
    # gives; None where nothing is trapped
    remaining: list


@dataclass
class Cluster:
    """A cluster of carriers on its way through the detector."""

    carriers: float  # number of carriers, with their sign
    position: list  # x, y, z [um]
    t: float  # [s]
    start: float  # when it set off [s]
    path: list  # the points (x, y, z [um], t [s]) it has passed, the start first
    reason: str | None = None  # why it stopped; None while it drifts

    @classmethod
    def starting(cls, x, y, z, t, carriers):
        """A cluster of `carriers` carriers at x, y, z [um] and time t [s]."""
        return cls(carriers, [x, y, z], t, t, [(x, y, z, t)])


def drift(x, y, z, t, carriers, my_d, my_f, mobility, delta_t, max_drift_time, diffusion=True):
    """Path of one cluster of carriers and why it stopped.

    The cluster starts at x, y, z [um] and time t [s]; the sign of `carriers`,
    their number, tells holes from electrons. Each step of `delta_t` [s] moves it along
    the field of `my_f` [V/cm] with `mobility(temperature, doping, charge,
    field)` [cm^2/V/s]. With `diffusion` each step also moves it at random,
    by a Gaussian of variance 2 D delta_t on each axis, D = mobility kT/e,
    drawn from the random stream "drift"; the cluster diffuses as one
    carrier. Without it the stream is not asked.

    Returns the path, an array (points, 4) of x, y, z [um] and t [s], and
    one of
        left_device  the path ends where it crosses the surface of `my_d`,
                     at the time of the crossing
        collected    the cluster is where `my_f` says the device conducts
        low_field    the field is not above min_intensity
        no_field     the field has no value at the position
        time_out     `max_drift_time` [s] has passed since it set off

    A field that is not finite where the cluster is raises ValueError,
    which names the position.
    """
    cluster = Cluster.starting(x, y, z, t, carriers)
    while cluster.reason is None:
        advance(cluster, my_d, my_f, mobility, delta_t, max_drift_time, diffusion)
    return np.array(cluster.path), cluster.reason


def max_drift_time_of(my_d, my_f, mobility):
    """How long [s] a cluster may drift before it stops as "time_out".

    The key `max_drift_time_ns` [ns] of the device file if it has one, which
    must be a positive finite number. Otherwise `margin` times the longer of
    the times electrons and holes take to drift through the thickness along
    the depth line at the middle of the device: the sum over points `depth_step`
    [um] apart of dz / (mobility |E|), the points where |E| is above
    min_intensity only. The estimate is made once for a field, kept on it,
    and logged.
    """
    given = getattr(my_d, "max_drift_time_ns", None)
    if given is not None:
        if isinstance(given, bool) or not isinstance(given, (int, float)) or not math.isfinite(given) or given <= 0:
            raise ValueError(
                "max_drift_time_ns of {} must be a positive finite number in ns, not {}".format(
                    my_d.det_name, given
                )
            )
        return float(given) * 1e-9
    kept = getattr(my_f, "estimated_max_drift_time", None)
    if kept is not None:
        return kept
    count = math.ceil(my_d.l_z / depth_step)
    dz = my_d.l_z / count
    x, y = my_d.l_x / 2, my_d.l_y / 2
    fields, dopings = [], []
    for k in range(count):
        z = (k + 0.5) * dz
        try:
            field = math.hypot(*my_f.get_e_field_cached(x, y, z))
        except ValueError:
            continue
        if field > min_intensity:  # false for a field that is not a number
            fields.append(field)
            dopings.append(float(my_f.get_doping_cached(x, y, z)))
    if not fields:
        raise ValueError(
            "{} has no field above {} V/cm along its depth at the bias {} V: "
            "give max_drift_time_ns in the device file".format(my_d.det_name, min_intensity, my_d.voltage)
        )
    times = {}
    for name, charge in (("electrons", -1), ("holes", 1)):
        times[name] = 1e-4 * dz * sum(
            1.0 / (mobility(my_d.temperature, doping, charge, field) * field)
            for field, doping in zip(fields, dopings)
        )
    estimate = margin * max(times.values())
    logger.info(
        "max_drift_time estimated: electrons %.4g s, holes %.4g s through the thickness, taken %.4g s",
        times["electrons"], times["holes"], estimate,
    )
    my_f.estimated_max_drift_time = estimate
    return estimate


def advance(cluster, my_d, my_f, mobility, delta_t, max_drift_time, diffusion=True):
    """One step of `drift` for a cluster that has not stopped.

    Either the cluster moves by one step, of `delta_t` or less where it
    crosses the surface of `my_d`, and its path gains the point it reaches;
    or it stops where it is and `reason` says why. The arguments and the
    reasons are those of `drift`.
    """
    size = (my_d.l_x, my_d.l_y, my_d.l_z)
    sign = 1 if cluster.carriers > 0 else -1
    position = cluster.position
    if cluster.t - cluster.start >= max_drift_time:
        cluster.reason = "time_out"
        return
    if my_f.get_conductive(*position):
        cluster.reason = "collected"
        return
    try:
        field = my_f.get_e_field_cached(*position)
    except ValueError:
        cluster.reason = "no_field"
        return
    if not all(math.isfinite(component) for component in field):
        raise ValueError(
            "the field at x, y, z = {:.4f}, {:.4f}, {:.4f} um is {} V/cm: "
            "a carrier cannot drift in it".format(*position, field)
        )
    intensity = math.hypot(*field)
    if intensity <= min_intensity:
        cluster.reason = "low_field"
        return
    doping = float(my_f.get_doping_cached(*position))
    mu = mobility(my_d.temperature, doping, cluster.carriers, intensity)
    step = [sign * component * mu * delta_t * 1e4 for component in field]  # um
    if diffusion:
        sigma = math.sqrt(2.0 * kboltz * my_d.temperature * mu * delta_t) * 1e4  # um
        generator = stream("drift")
        step = [move + generator.Gaus(0.0, sigma) for move in step]

    # the share of the step that lies inside the device
    inside = 1.0
    for here, move, length in zip(position, step, size):
        if here + move < 0:
            inside = min(inside, -here / move)
        elif here + move > length:
            inside = min(inside, (length - here) / move)
    if inside > 0:
        cluster.position = [here + move * inside for here, move in zip(position, step)]
        cluster.t += delta_t * inside
        cluster.path.append((*cluster.position, cluster.t))
    if inside < 1:
        cluster.reason = "left_device"


def induced_charges(path, carriers, my_f, electrode, offset=(0.0, 0.0)):
    """Charge that each step of a path induces on one electrode [C].

    `path` is what `drift` returns, `carriers` the number of carriers of the
    cluster with their sign, one number or one for each step as `surviving`
    gives, `electrode` the number of the electrode in `my_f`. By the
    Shockley-Ramo theorem a step from a to b induces
    charge e0 (U_w(b) - U_w(a)), U_w the weighting potential of the
    electrode.

    Where equal electrodes repeat, `my_f` holds the weighting potential of
    one of them, and `offset` [um] gives the x and y of the electrode
    asked for minus those of that one: its weighting potential is the one
    of `my_f` moved by `offset`.
    """
    potential = np.array([
        my_f.get_w_p(x - offset[0], y - offset[1], z, electrode) for x, y, z, _ in path
    ])
    return carriers * e0 * np.diff(potential)


def surviving(path, carriers, my_f, trapping=None):
    """Carriers of a cluster not yet lost, at the middle of each step.

    `trapping` is a `Trapping`; without it the carriers are trapped at the
    rate of `my_f` [1/s] for holes or electrons, by the sign of `carriers`,
    read at the start of each step and held over the step. See
    `trapping.survivors` for the other ways to lose them.
    """
    return survivors(path, carriers, my_f, Trapping() if trapping is None else trapping)


def surviving_at(path, carriers, my_f, step, fraction, trapping=None):
    """Carriers of a cluster not yet lost `fraction` of the way through
    step `step` of its path, with the rates `surviving` takes."""
    return survivors_at(path, carriers, my_f, Trapping() if trapping is None else trapping, step, fraction)
