"""Drift of a cluster of charge carriers through a detector."""

import math

import numpy as np

min_intensity = 1  # V/cm, a carrier in a field not above this stops
max_drift_time = 100e-9  # s, a carrier still drifting after this stops


def drift(x, y, z, t, charge, my_d, my_f, mobility, delta_t):
    """Path of one cluster of carriers and why it stopped.

    The cluster starts at x, y, z [um] and time t [s]; the sign of `charge`
    tells holes from electrons. Each step of `delta_t` [s] moves it along
    the field of `my_f` [V/cm] with `mobility(temperature, doping, charge,
    field)` [cm^2/V/s].

    Returns the path, an array (points, 4) of x, y, z [um] and t [s], and
    one of
        left_device  the path ends where it crosses the surface of `my_d`,
                     at the time of the crossing
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
        step = [sign * component * mu * delta_t * 1e4 for component in field]  # um

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
