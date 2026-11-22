"""The deposits slice of a signal job.

It takes what it needs out of the run.json of the seed folder
(kwargs["_files"], the folders, the job) and calls the entry of the module
that owns the stage. Nothing is written onto the device.
"""

import os

from raser.core.device import build_device as bdv
from raser.core.deposit.generation import GENERATED_LIMIT
from raser.core.deposit.simulate_deposits import write_simulated_deposits
from raser.core.deposit.view_geometry import view_geometry
from raser.lifecycle.slices import Ended
from raser.stages.files import output
from raser.stages.files import plots


def detectors(kwargs, slots=None):
    """The detectors of the slots of the setup, in the order of the slots; for
    a single device, {"Device": detector}."""
    files = kwargs["_files"]
    if slots is None:
        return {"Device": bdv.Detector(kwargs["det_name"], files["device"])}
    return {slot: bdv.Detector(files[slot]["device"]["det_name"], files[slot]["device"]) for slot in slots}


def deposits(kwargs, slots=None):
    """The source in the g4setup, or the device alone: deposit_<job>.h5.

    The job records events_per_job events, the source generating until there
    are that many (at most generated_limit), or what is recorded of
    generated_per_job generated events; one of the two is set. A job that
    recorded no event ends here."""
    files = kwargs["_files"]
    placed = detectors(kwargs, slots)
    events, generated = kwargs.get("events_per_job"), kwargs.get("generated_per_job")
    if (events is None) == (generated is None):
        raise ValueError(
            f"events_per_job ({events}) and generated_per_job ({generated}): a job "
            "records a number of events or generates one, so exactly one of them is set"
        )
    limit = kwargs.get("generated_limit")
    if kwargs.get("g4_vis"):
        # A window to turn the Geant4 geometry and the tracks in: the job ends
        # when it is closed. An off-screen driver writes the picture instead.
        driver = kwargs["g4_vis_driver"]
        picture = None
        if driver.upper() in ("TSG", "TSG_FILE", "TSG_OFFSCREEN"):
            picture = os.path.join(kwargs["_run_path"], "g4_geometry")
        view_geometry(
            placed,
            files["source"],
            files.get("g4setup"),
            int(events if generated is None else generated),
            kwargs["seed"],
            driver,
            picture,
        )
        raise SystemExit
    recorded = write_simulated_deposits(
        output(kwargs, "deposit"),
        placed,
        files["source"],
        files.get("g4setup"),
        None if events is None else int(events),
        kwargs["seed"],
        _windows(kwargs, placed),
        kwargs["require"],
        kwargs.get("coincidence_window_ns"),
        kwargs["fano"],
        None if generated is None else int(generated),
        GENERATED_LIMIT if limit is None else int(limit),
        *_picture(kwargs),
    )
    if not recorded:
        # the file keeps the number of generated events; nothing is left to drift
        raise Ended


def _windows(kwargs, placed):
    """The energy window (edep_min, edep_max) of each slot: deposit.edep_min and
    deposit.edep_max, each side replaced by the slot's own deposit.<slot>.edep_min
    or deposit.<slot>.edep_max where that is given."""
    bounds = ("edep_min", "edep_max")
    return {
        slot: tuple(
            kwargs[f"{slot}.{bound}"] if kwargs.get(f"{slot}.{bound}") is not None else kwargs.get(bound)
            for bound in bounds
        )
        for slot in placed
    }


def _picture(kwargs):
    """The picture of the Geant4 geometry and the first `plots` recorded
    events of this job, plots/g4_geometry.png in the node of the
    deposits, and the number of events drawn; none for plots 0."""
    drawn = int(kwargs.get("plots") or 0)
    if not drawn:
        return None, 0
    folder = plots(kwargs, "deposit")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "g4_geometry"), drawn
