"""The events of one signal job.

The device, its solved field, the events Geant4 recorded, and for each of
them the induced current and the amplified waveform of every read-out
electrode. Everything the job reads comes from the run.json of its seed
folder (kwargs["_files"]); nothing is written onto the device.

Written into batch/ of the seed folder, one file per job:
    deposits_<job>.h5   energy deposits of the recorded events
    currents_<job>.h5   induced current of every electrode, event by event
The amplified waveforms are not written yet.
"""

import os
from copy import deepcopy
from pathlib import Path

import ROOT

from raser.core.current import cal_current as ccrt
from raser.core.current.currents import EventCurrents, append_currents
from raser.core.device import build_device as bdv
from raser.core.field import devsim_field as devfield
from raser.core.field.solved import solved_field
from raser.core.frontend.toy_readout import Amplifier
from raser.core.interaction.deposits import write_deposits
from raser.core.interaction.interaction import GeneralG4Interaction

from .draw_save import draw_drift_path

ROOT.gROOT.SetBatch(True)

# Geant4 set-up of a run that names none: the device alone in vacuum, one event.
DEVICE_ALONE = {
    "geant4_model": "device",
    "total_events": 1,
    "object": {},
    "world": "G4_Galactic",
    "maxstep": 2,
    "g4_vis": False,
}


def g4_config(kwargs):
    """Geant4 configuration of the job: the set-up, then the source over it."""
    files = kwargs["_files"]
    if files["source"].get("kind") == "toy_mip":
        raise NotImplementedError(
            "a toy_mip source does not hand over Deposits yet; this job only runs Geant4"
        )
    config = deepcopy(files.get("g4setup", DEVICE_ALONE))
    config.update(files["source"])
    for key in ("name", "kind", "description"):
        config.pop(key, None)
    if kwargs.get("events_per_job") is not None:
        config["total_events"] = int(kwargs["events_per_job"])
    if kwargs.get("g4_vis_driver"):
        config["g4_vis_driver"] = kwargs["g4_vis_driver"]
    if kwargs.get("g4_vis"):
        config["g4_vis_output"] = os.path.join(kwargs["_run_path"], "g4_geometry")
    return config


def run_events(my_d, my_f, my_g4, amplifier, batch_path, job, plots, plot_path):
    """Current and waveform of every event Geant4 recorded.

    The first `plots` events are also drawn, each in plot_path/event_<number>:
    drift paths, currents, waveform.
    """
    deposits = my_g4.deposits()
    index = {number: i for i, number in enumerate(my_g4.eventIDs)}
    write_deposits(os.path.join(batch_path, "deposits_%s.h5" % (job)), deposits)
    currents_path = os.path.join(batch_path, "currents_%s.h5" % (job))
    if os.path.exists(currents_path):  # of an earlier start of this job
        os.remove(currents_path)
    print(
        "detection_efficiency=%s" % (len(deposits.events) / deposits.generated_events),
        flush=True,
    )
    if not deposits.events:
        print("no event left a deposit in the device", flush=True)
    if 0 < plots < len(deposits.events):
        print(
            "%s events recorded; only the first %s are drawn (--plots)"
            % (len(deposits.events), plots),
            flush=True,
        )

    for count, record in enumerate(deposits.events):
        print("run events number:%s" % (record.event))
        drawn = count < plots
        my_current = ccrt.CalCurrentG4P(
            my_d, my_f, my_g4, index[record.event], keep_drift_paths=drawn
        )
        append_currents(
            currents_path,
            my_current.electrodes,
            my_current.t_bin,
            EventCurrents(record.event, my_current.t_start, my_current.current, my_current.charge),
        )
        ele_current = Amplifier(my_current.sum_cu, amplifier, CDet=my_d.capacitance)

        if drawn:
            path = os.path.join(plot_path, "event_%s" % (record.event))
            os.makedirs(path, exist_ok=True)
            draw_drift_path(my_d, my_g4, my_f, my_current, path)
            my_current.draw_currents(path)
            ele_current.draw_waveform(my_current.sum_cu, path)
            if my_d.is_strip:
                my_current.charge_collection_strip(path)
            if my_d.is_pixel:
                my_current.charge_collection_pixel(path)


def main(kwargs):
    files = kwargs["_files"]
    my_d = bdv.Detector(kwargs["det_name"], files["device"])

    # The flux is of the field the run takes, not of the device.
    flux = my_d.irradiation_flux if kwargs["irradiation"] is None else float(kwargs["irradiation"])
    my_f = devfield.DevsimField(
        my_d.device,
        my_d.voltage,
        my_d.read_out_contact,
        irradiation_flux=flux,
        bounds=my_d.bound,
        field_directory=solved_field(my_d, my_d.voltage, flux),
        interpolation_bins=my_d.device_dict.get("field_interpolation_bins"),
    )

    interaction_options = {}
    if kwargs.get("_g4_action_initialization") is not None:
        interaction_options["MyActionInitialization"] = kwargs["_g4_action_initialization"]
    my_g4 = GeneralG4Interaction(
        my_d,
        g4_config(kwargs),
        kwargs["seed"],
        kwargs.get("g4_vis", False),
        **interaction_options,
    )

    # The amplifier is still found by the name of its file.
    amplifier = Path(str(kwargs["amplifier"])).stem
    job = kwargs.get("job_index") or 0
    try:
        run_events(
            my_d,
            my_f,
            my_g4,
            amplifier,
            kwargs["_run_batch_path"],
            job,
            int(kwargs["plots"]),
            os.path.join(kwargs["_run_path"], "plots", "job_%s" % (job)),
        )
    finally:
        my_g4.close()
