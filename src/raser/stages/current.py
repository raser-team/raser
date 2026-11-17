"""The currents slice of a signal job, and the solved field it drifts in."""

import os

from raser.core.current.cal_current import write_induced_currents
from raser.core.device import build_device as bdv
from raser.core.field import devsim_field as devfield
from raser.core.field.solved import solved_field
from raser.stages.files import _job
from raser.stages.files import output


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
    """The deposits drifted in the solved field of the device: current_<job>.h5,
    and the pictures of the first `plots` events in plots/job_<job>."""
    my_d = bdv.Detector(kwargs["det_name"], kwargs["_files"]["device"])
    write_induced_currents(
        output(kwargs, "deposit"),
        output(kwargs, "current"),
        my_d,
        solved(my_d, kwargs),
        int(kwargs["plots"]),
        os.path.join(
            os.path.dirname(kwargs["_slice_batch_paths"]["current"]),
            "plots",
            "job_%s" % _job(kwargs),
        ),
    )
