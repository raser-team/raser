"""The slices of a TCT signal job: one laser pulse, without seeds.

Written into batch/ of the point folder:
    currents_0.h5    induced current of every electrode, the pulse as event 0
    waveforms_0.h5   output voltage of the electronics, without noise
"""

import os

from raser.core.current.cal_current import write_laser_currents
from raser.core.device import build_device as bdv
from raser.core.deposit.laser import LaserInjection
from raser.stages import readout
from raser.stages.current import solved
from raser.stages.files import output


def currents(kwargs):
    """The pairs of the laser pulse drifted in the solved field of the device:
    currents_0.h5, and the pictures of the pulse and of the currents in plots/."""
    files = kwargs["_files"]
    my_d = bdv.Detector(kwargs["det_name"], files["device"])
    my_l = LaserInjection(my_d, dict(files["laser"]))
    path = os.path.join(os.path.dirname(kwargs["_slice_batch_paths"]["current"]), "plots")
    write_laser_currents(
        output(kwargs, "current"),
        my_d,
        solved(my_d, kwargs),
        my_l,
        path,
    )
    my_l.draw_nocarrier3D(path)
    my_l.draw_nocarrier2D(path)


waveforms = readout.waveforms
