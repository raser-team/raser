"""The deposits slice of a signal job.

It takes what it needs out of the run.json of the seed folder
(kwargs["_files"], the folders, the job) and calls the entry of the module
that owns the stage. Nothing is written onto the device.
"""

import os

from raser.core.device import build_device as bdv
from raser.core.deposit.simulate_deposits import write_simulated_deposits
from raser.core.deposit.view_geometry import view_geometry
from raser.lifecycle.slices import Ended
from raser.stages.files import output


def deposits(kwargs):
    """The source in the g4setup, or the device alone: deposit_<job>.h5.
    A job that recorded no event ends here."""
    files = kwargs["_files"]
    my_d = bdv.Detector(kwargs["det_name"], files["device"])
    if kwargs.get("g4_vis"):
        # Only the Geant4 geometry and the tracks are drawn: the job ends here.
        driver = kwargs["g4_vis_driver"]
        picture = None
        if driver.upper().startswith(("TSG", "OGL")):  # the drivers that write a picture
            picture = os.path.join(kwargs["_run_path"], "g4_geometry")
        view_geometry(
            my_d,
            files["source"],
            files.get("g4setup"),
            int(kwargs["events_per_job"]),
            kwargs["seed"],
            driver,
            picture,
        )
        raise SystemExit
    recorded = write_simulated_deposits(
        output(kwargs, "deposit"),
        my_d,
        files["source"],
        files.get("g4setup"),
        int(kwargs["events_per_job"]),
        kwargs["seed"],
        kwargs.get("edep_min"),
        kwargs.get("edep_max"),
        kwargs["fano"],
    )
    if not recorded:
        # the file keeps the number of generated events; nothing is left to drift
        raise Ended
