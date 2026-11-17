"""The deposits slice of a cflm job: deposit_<job>.h5.

An event is one bunch: the lost electrons of cflm_p1.json shot into the beam
pipe together. The pads are 24 detectors of the file, named <side>_<i>_<j>;
every deposit is in the coordinates of its own pad. A bunch that leaves
nothing in any pad is counted in the generated events of the file and has
no record in it.
"""

import json

from raser.stages.files import output
from raser.core.device import build_device as bdv
from raser.core.deposit.deposits import Deposits
from raser.core.deposit.deposits import EventDeposits
from raser.core.deposit.deposits import write_deposits
from raser.core.deposit.ionization import ionized_pairs
from raser.lifecycle.slices import Ended
from raser.supports.paths import app_file_path

from . import cflm_p1

def pad_frame(side, i, j, step, my_d, g4_dic):
    """A step [um, frame of the beam pipe] in the coordinates of the pad i_j of a side.

    z is the depth into the pad from its face, which touches the outer
    surface of the pipe.
    """
    surface = g4_dic["pipe"]["Rmax"] * 1000
    centre_y = (i + 0.5) * my_d.l_x
    centre_z = g4_dic["pads_from_z_mm"] * 1000 + (j + 0.5) * my_d.l_y
    depth = -step[0] - surface if side == "I" else step[0] - surface
    return (
        my_d.l_x / 2 - step[1] + centre_y,
        my_d.l_y / 2 + step[2] - centre_z,
        depth,
    )


def bunch_deposits(my_d, g4_dic, seed):
    """The deposits of the bunches of g4_dic in the 24 pads."""
    steps, energies, _ = cflm_p1.simulate_bunches(g4_dic, seed, my_d)
    bunches = int(g4_dic["BeamOn"])
    events = []
    for bunch in range(bunches):
        event = EventDeposits(bunch, [], [], [], [], [], [])
        for side in ("I", "II"):
            for pad, of_pad in steps[f"detector_{side}"].items():
                i, j = (int(index) for index in pad.split("_"))
                of_energy = energies[f"detector_{side}"][pad][bunch]
                for step, energy in zip(of_pad[bunch], of_energy, strict=True):
                    if energy <= 0:
                        continue
                    x, y, z = pad_frame(side, i, j, step, my_d, g4_dic)
                    event.detector.append(f"{side}_{pad}")
                    event.x.append(x)
                    event.y.append(y)
                    event.z.append(z)
                    event.t.append(0.0)  # the steps of cflm_p1 carry no time
                    event.e.append(energy)
        if event.e:
            event.pairs, _ = ionized_pairs(event, my_d.material)
            events.append(event)
    return Deposits(bunches, None, None, events)


def deposits(kwargs):
    my_d = bdv.Detector(kwargs["det_name"], kwargs["_files"]["device"])
    with open(app_file_path("apps/cflm", "cflm_p1.json")) as file:
        g4_dic = json.load(file)
    found = bunch_deposits(my_d, g4_dic, kwargs["seed"])
    write_deposits(output(kwargs, "deposit"), found)
    if not found.events:
        raise Ended  # no bunch reached a pad
