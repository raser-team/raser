"""The deposits slice of a bmos job: deposits_<job>.h5.

The bunches are those of bmos.json: BeamOn bunches of par_num particles.
A bunch that leaves nothing in the detector is counted in the generated
events of the file and has no record in it.
"""

from raser.apps.signal.gen_signal import output
from raser.core.device import build_device as bdv
from raser.core.interaction.deposits import deposits_of_steps
from raser.core.interaction.deposits import write_deposits
from raser.core.interaction.ionization import ionized_pairs
from raser.lifecycle.slices import Ended

from . import bmos


def deposits(kwargs):
    my_d = bdv.Detector(kwargs["det_name"], kwargs["_files"]["device"])
    bmos.g4b.cppyy.gbl.CLHEP.HepRandom.setTheSeed(kwargs["seed"])
    my_g4 = bmos.bmosG4Interaction(my_d)
    bunches = len(my_g4.energy_steps)
    found = deposits_of_steps(
        "Device",
        range(bunches),
        my_g4.p_steps_current,
        my_g4.energy_steps,
        # the steps of bmos carry no time: every deposit is at t = 0
        [[0.0] * len(energies) for energies in my_g4.energy_steps],
        bunches,
        None,
        None,
    )
    for event in found.events:
        event.pairs, _ = ionized_pairs(event, my_d.material)
    write_deposits(output(kwargs, "deposits"), found)
    if not found.events:
        raise Ended  # no bunch reached the detector: there is no current to drift
