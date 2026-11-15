"""The events of one signal job.

The device, its solved field, the energy deposits of the recorded events,
and for each event the induced current and the amplified waveform of every
read-out electrode. Everything the job reads comes from the run.json of its seed
folder (kwargs["_files"]); nothing is written onto the device.

Written into batch/ of the seed folder, one file per job:
    deposits_<job>.h5   energy deposits of the recorded events
    currents_<job>.h5   induced current of every electrode, event by event
The amplified waveforms are not written yet.
"""

import os
from pathlib import Path

import ROOT

from raser.core.current import cal_current as ccrt
from raser.core.current.currents import EventCurrents, append_currents
from raser.core.device import build_device as bdv
from raser.core.field import devsim_field as devfield
from raser.core.field.solved import solved_field
from raser.core.frontend.toy_readout import Amplifier
from raser.core.interaction.deposits import write_deposits
from raser.core.interaction.simulate_deposits import simulate_deposits
from raser.core.interaction.view_geometry import view_geometry

from raser.core.current.draw_drift_path import draw_drift_path

ROOT.gROOT.SetBatch(True)

def run_events(my_d, my_f, deposits, amplifier, batch_path, job, plots, plot_path):
    """Current and waveform of every recorded event.

    The first `plots` events are also drawn, each in plot_path/event_<number>:
    drift paths, currents, waveform.
    """
    write_deposits(os.path.join(batch_path, "deposits_%s.h5" % (job)), deposits)
    currents_path = os.path.join(batch_path, "currents_%s.h5" % (job))
    if os.path.exists(currents_path):  # of an earlier start of this job
        os.remove(currents_path)
    print(
        "detection_efficiency=%s" % (len(deposits.events) / deposits.generated_events),
        flush=True,
    )
    if not deposits.events:
        print("no event was recorded", flush=True)
    if 0 < plots < len(deposits.events):
        print(
            "%s events recorded; only the first %s are drawn (--plots)"
            % (len(deposits.events), plots),
            flush=True,
        )

    for count, record in enumerate(deposits.events):
        print("run events number:%s" % (record.event))
        drawn = count < plots
        positions = [list(point) for point in zip(record.x, record.y, record.z, record.t)]
        my_current = ccrt.CalCurrent(my_d, my_f, record.pairs, positions, keep_drift_paths=drawn)
        append_currents(
            currents_path,
            my_current.electrodes,
            my_current.t_bin,
            EventCurrents(
                record.event,
                my_current.t_start,
                my_current.current,
                my_current.charge,
                my_current.pairs,
            ),
        )
        ele_current = Amplifier(my_current.sum_cu, amplifier, CDet=my_d.capacitance)

        if drawn:
            path = os.path.join(plot_path, "event_%s" % (record.event))
            os.makedirs(path, exist_ok=True)
            track = list(zip(record.x, record.y, record.z))
            draw_drift_path(my_d, track, my_f, my_current, path)
            my_current.draw_currents(path)
            ele_current.draw_waveform(my_current.sum_cu, path)
            if my_d.is_strip:
                my_current.charge_collection_strip(path)
            if my_d.is_pixel:
                my_current.charge_collection_pixel(path)


def main(kwargs):
    files = kwargs["_files"]
    my_d = bdv.Detector(kwargs["det_name"], files["device"])

    if kwargs.get("g4_vis"):
        # Only the Geant4 geometry and the tracks are drawn; no signal is run.
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
        return

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

    deposits = simulate_deposits(
        my_d,
        files["source"],
        files.get("g4setup"),
        int(kwargs["events_per_job"]),
        kwargs["seed"],
        kwargs.get("edep_min"),
        kwargs.get("edep_max"),
    )

    # The amplifier is still found by the name of its file.
    amplifier = Path(str(kwargs["amplifier"])).stem
    job = kwargs.get("job_index") or 0
    run_events(
        my_d,
        my_f,
        deposits,
        amplifier,
        kwargs["_run_batch_path"],
        job,
        int(kwargs["plots"]),
        os.path.join(kwargs["_run_path"], "plots", "job_%s" % (job)),
    )
