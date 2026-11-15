"""The slices of a signal job.

Each takes what its stage needs out of the run.json of the seed folder
(kwargs["_files"], the folders, the job) and calls the entry of the module
that owns the stage. Nothing is written onto the device.

Written into batch/ of the seed folder that holds the slice, which is the
one of another point when the slice does not read what makes this point
differ; one file per job and slice:
    deposits_<job>.h5    energy deposits and pairs of the recorded events
    currents_<job>.h5    induced current of every electrode, event by event
    waveforms_<job>.h5   output voltage of the electronics, event by event
"""

import os

from raser.core.current.cal_current import electrode_names
from raser.core.current.cal_current import write_induced_currents
from raser.core.device import build_device as bdv
from raser.core.field import devsim_field as devfield
from raser.core.field.solved import solved_field
from raser.core.frontend.circuit import named_chain
from raser.core.frontend.device_circuit import device_sensor
from raser.core.frontend.job import write_waveforms
from raser.core.interaction.simulate_deposits import write_simulated_deposits
from raser.core.interaction.view_geometry import view_geometry


def _job(kwargs):
    return kwargs.get("job_index") or 0


def output(kwargs, name):
    """The file of the slice `name` of this job, in the point that holds the slice."""
    return os.path.join(
        kwargs["_slice_batch_paths"][name], "%s_%s.h5" % (name, _job(kwargs))
    )


def deposits(kwargs):
    """The source in the g4setup, or the device alone: deposits_<job>.h5."""
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
    write_simulated_deposits(
        output(kwargs, "deposits"),
        my_d,
        files["source"],
        files.get("g4setup"),
        int(kwargs["events_per_job"]),
        kwargs["seed"],
        kwargs.get("edep_min"),
        kwargs.get("edep_max"),
    )


def solved(my_d, kwargs):
    """The solved field of the device at its bias; the flux is of the field
    the run takes, not of the device."""
    flux = my_d.irradiation_flux
    if kwargs.get("irradiation") is not None:
        flux = float(kwargs["irradiation"])
    return devfield.DevsimField(
        my_d.device,
        my_d.voltage,
        my_d.read_out_contact,
        irradiation_flux=flux,
        bounds=my_d.bound,
        field_directory=solved_field(my_d, my_d.voltage, flux),
        interpolation_bins=my_d.device_dict.get("field_interpolation_bins"),
    )


def currents(kwargs):
    """The deposits drifted in the solved field of the device: currents_<job>.h5,
    and the pictures of the first `plots` events in plots/job_<job>."""
    my_d = bdv.Detector(kwargs["det_name"], kwargs["_files"]["device"])
    write_induced_currents(
        output(kwargs, "deposits"),
        output(kwargs, "currents"),
        my_d,
        solved(my_d, kwargs),
        int(kwargs["plots"]),
        os.path.join(
            os.path.dirname(kwargs["_slice_batch_paths"]["currents"]),
            "plots",
            "job_%s" % _job(kwargs),
        ),
    )


def waveforms(kwargs):
    """The currents through the sensor circuit of the device and the chain the
    amplifier names: waveforms_<job>.h5. The noise of the circuit is drawn
    with the seed lifecycle gives the slice; a run without seeds has no noise."""
    my_d = bdv.Detector(kwargs["det_name"], kwargs["_files"]["device"])
    sensor, _ = device_sensor(
        my_d, electrode_names(my_d.read_out_contact, my_d.read_ele_num)
    )
    write_waveforms(
        output(kwargs, "currents"),
        output(kwargs, "waveforms"),
        named_chain(str(kwargs["amplifier"])),
        sensor,
        kwargs.get("seed"),
    )
