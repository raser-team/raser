"""Charge collected by diffusion alone, in a pixel sensor without a drift field.

The model, for a MAPS at low bias whose epitaxial layer is taken as field
free: the electrons of an event walk at random in x and y; one that enters
the collection region of a pixel is collected by that pixel at once. The
collection region is a rectangle of e_width_x by e_width_y [um] at the
centre of every pixel, through the whole thickness.

What the model leaves out: the field of the junction and the drift in it, any
motion along z, recombination, the holes, and the current induced before an
electron arrives. The current it gives is the charge arriving per time bin.
"""

from __future__ import annotations

import math

import numpy as np

from raser.core.seeding import stream

from ..model.material import Material

ELEMENTARY_CHARGE = 1.602176634e-19  # C
BOLTZMANN = 8.617385e-5  # eV/K


def collect_by_diffusion(my_d, pairs, positions, window, step):
    """The charge the pixels of `my_d` collect from one event.

    Parameters:
        my_d : Detector
            a pixel device with e_width_x and e_width_y [um]; its
            doping is two numbers [cm^-3]
        pairs : float[]
            electron-hole pairs of every deposit
        positions : float[][]
            x, y, z [um] and time [s] of every deposit, in device coordinates
        window : float
            how long after its creation an electron can still be collected [s]
        step : float
            time of one random step, and width of a time bin [s]
    Returns:
        t0 : float
            left edge of the first time bin [s]
        current : (electrodes, bins) array
            mean current of every pixel in every bin [A], negative: electrons
        charge : (electrodes,) array
            net charge of every pixel [C]
    The pixel i along x and j along y is the electrode i * y_ele_num + j.
    """
    if not my_d.is_pixel:
        raise ValueError(f"{my_d.det_name} is not a pixel device")
    for key in ("e_width_x", "e_width_y"):
        if not hasattr(my_d, key):
            raise ValueError(f"the device file of {my_d.det_name} has no {key} [um]")
    low_x = (my_d.p_x - my_d.e_width_x) / 2
    low_y = (my_d.p_y - my_d.e_width_y) / 2

    neff = float(my_d.doping["Donors"]) - float(my_d.doping["Acceptors"])
    mobility = Material(my_d.material).cal_mobility(my_d.temperature, neff, -1, 0)
    # one step along an axis is a Gaussian of variance 2 D step, D = mobility kT/e
    sigma = math.sqrt(2 * BOLTZMANN * my_d.temperature * mobility * step) * 1e4  # um

    steps = round(window / step)
    t0 = min((position[3] for position in positions), default=0.0)
    last = max((position[3] for position in positions), default=0.0)
    bins = round((last - t0) / step) + steps + 1
    electrons = np.zeros((my_d.x_ele_num * my_d.y_ele_num, bins))

    generator = stream("diffusion")
    for n_pairs, (x, y, z, t) in zip(pairs, positions, strict=True):
        if not 0 <= z <= my_d.l_z:
            continue
        first = round((t - t0) / step)
        for k in range(steps + 1):
            if not (0 < x < my_d.l_x and 0 < y < my_d.l_y):
                break  # left through the side
            i, j = int(x // my_d.p_x), int(y // my_d.p_y)
            in_x = low_x < x - i * my_d.p_x < my_d.p_x - low_x
            in_y = low_y < y - j * my_d.p_y < my_d.p_y - low_y
            if in_x and in_y and i < my_d.x_ele_num and j < my_d.y_ele_num:
                electrons[i * my_d.y_ele_num + j, first + k] += n_pairs
                break
            x += generator.Gaus(0.0, sigma)
            y += generator.Gaus(0.0, sigma)

    charge = -ELEMENTARY_CHARGE * electrons.sum(axis=1)
    return t0, -ELEMENTARY_CHARGE * electrons / step, charge
