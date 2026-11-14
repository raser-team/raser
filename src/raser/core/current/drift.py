"""Drift of a cluster of charge carriers through a detector."""

import math

import numpy as np

from raser.core.seeding import stream

kboltz = 8.617385e-5  # eV/K
e0 = 1.60217733e-19  # C
min_intensity = 1  # V/cm, a carrier in a field not above this stops
max_drift_time = 100e-9  # s, a carrier still drifting after this stops

# where resistivity and field are both low is taken as metal: a carrier there is collected
metal_resistivity = 10  # ohm cm, below it the resistivity is low
thermal_length = 1e-4  # cm, the field is low when its drop over this length is below kT/e


def drift(x, y, z, t, charge, my_d, my_f, mobility, delta_t, diffusion=True):
    """Path of one cluster of carriers and why it stopped.

    The cluster starts at x, y, z [um] and time t [s]; the sign of `charge`
    tells holes from electrons. Each step of `delta_t` [s] moves it along
    the field of `my_f` [V/cm] with `mobility(temperature, doping, charge,
    field)` [cm^2/V/s]. With `diffusion` each step also moves it at random,
    by a Gaussian of variance 2 D delta_t on each axis, D = mobility kT/e,
    drawn from the random stream "drift"; the cluster diffuses as one
    carrier. Without it the stream is not asked.

    Returns the path, an array (points, 4) of x, y, z [um] and t [s], and
    one of
        left_device  the path ends where it crosses the surface of `my_d`,
                     at the time of the crossing
        collected    the cluster is where the resistivity, 1 / (e |net
                     doping| majority mobility), is below metal_resistivity
                     and the field below kT/e over thermal_length
        low_field    the field is not above min_intensity
        no_field     the field has no value at the position
        time_out     max_drift_time has passed
    """
    size = (my_d.l_x, my_d.l_y, my_d.l_z)
    sign = 1 if charge > 0 else -1
    position = [x, y, z]
    path = [(x, y, z, t)]
    start = t
    while True:
        if t - start >= max_drift_time:
            reason = "time_out"
            break
        try:
            field = my_f.get_e_field_cached(*position)
        except ValueError:
            reason = "no_field"
            break
        intensity = math.hypot(*field)
        if intensity <= min_intensity:
            reason = "low_field"
            break
        doping = float(my_f.get_doping_cached(*position))
        mu = mobility(my_d.temperature, doping, charge, intensity)
        if intensity < kboltz * my_d.temperature / thermal_length and doping != 0:
            # positive doping is n type: electrons are the majority carriers
            majority = mobility(my_d.temperature, doping, -1 if doping > 0 else 1, intensity)
            if 1.0 / (e0 * abs(doping) * majority) < metal_resistivity:
                reason = "collected"
                break
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
            position = [here + move * inside for here, move in zip(position, step)]
            t += delta_t * inside
            path.append((*position, t))
        if inside < 1:
            reason = "left_device"
            break
    return np.array(path), reason


def induced_charges(path, charge, my_f, electrode):
    """Charge that each step of a path induces on one electrode [C].

    `path` is what `drift` returns, `charge` the number of carriers of the
    cluster with their sign, `electrode` the number of the electrode in
    `my_f`. By the Shockley-Ramo theorem a step from a to b induces
    charge e0 (U_w(b) - U_w(a)), U_w the weighting potential of the
    electrode.
    """
    potential = np.array([my_f.get_w_p_cached(x, y, z, electrode) for x, y, z, _ in path])
    return charge * e0 * np.diff(potential)

