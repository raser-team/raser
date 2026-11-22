"""The settling of an amplifier chain, which sets how long a readout window
runs on after the current."""

import math

import numpy as np

from raser.core.field.device_circuit import planar_circuit

from .pulse_edge import NO_ANSWER_V
from .spice import solve

# charge injected into the probe circuit [C]
PROBE_CHARGE_C = 1e-15
# the chain has settled when its output is within this of its largest
# deviation from rest
SETTLED = 1e-3
# the first window solved [s]; each one that does not settle is twice as long
FIRST_WINDOW_S = 20e-9


def _last_beyond(chain, capacitance_f, dt, window_s):
    """The last time [s] the output of the chain, after 1 fC at the first bin
    on a probe circuit of capacitance_f, is farther than SETTLED of its
    largest deviation from rest, and whether it is before the last bin of the
    window; times count from the left edge of the first bin of the charge, a
    bin standing at its centre. Rest is the output of a bin before the
    charge."""
    bins = math.ceil(window_s / dt)
    current = np.zeros((1, bins + 1))
    current[0, 1] = PROBE_CHARGE_C / dt
    voltage = solve(
        chain, ["probe"], dt, current, planar_circuit("probe", capacitance_f)
    )[0]
    deviation = np.abs(voltage[1:] - voltage[0])
    largest = deviation.max()
    if largest < NO_ANSWER_V:
        raise ValueError(
            f"The chain moves its output by {largest:.3g} V for 1 fC: it does "
            "not answer, so the way its pulses go is not known"
        )
    beyond = np.nonzero(deviation > SETTLED * largest)[0]
    return (beyond[-1] + 0.5) * dt, beyond[-1] < bins - 1


def post_window(chain, capacitance_f, dt, max_post_s):
    """The length [s] of the readout window after the current: the time the
    chain takes to settle after 1 fC, which a probe circuit of
    capacitance_f [F] gives, but at most max_post_s.

    The window solved is 20 ns at first and doubles until the last time the
    output is beyond SETTLED of its largest deviation is before its end, or
    it has reached max_post_s. A chain that does not settle by max_post_s has
    that length, and an INFO line says that it settles in at least the time found.
    """
    window = FIRST_WINDOW_S
    while True:
        window = min(window, max_post_s)
        last, settled = _last_beyond(chain, capacitance_f, dt, window)
        if settled:
            return min(last, max_post_s)
        if window >= max_post_s:
            print(
                f"INFO: readout: the amplifier chain settles in at least "
                f"{last * 1e9:.6g} ns; the post-window is {max_post_s * 1e9:.6g} ns "
                "(readout.max_post_window_ns)"
            )
            return max_post_s
        window *= 2
