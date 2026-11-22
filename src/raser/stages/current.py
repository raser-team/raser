"""The currents slice of a signal job, and the solved field it drifts in."""

import os

from raser.core.current.cal_current import write_induced_currents
from raser.core.deposit.deposits import read_deposits
from raser.core.device import build_device as bdv
from raser.core.field import devsim_field as devfield
from raser.core.field.solved import solved_field
from raser.stages.files import output
from raser.stages.files import plots


def solved(my_d, kwargs):
    """The solved field of the device at its bias; the flux is of the field
    the run takes, not of the device."""
    flux = my_d.irradiation_flux
    if kwargs.get("irradiation_flux") is not None:
        flux = float(kwargs["irradiation_flux"])
    electrodes = my_d.read_out_contact
    if "resistive_layer" in my_d.device_dict:
        electrodes = [{"name": my_d.device_dict["resistive_layer"]["contact"]}]
    return devfield.DevsimField(
        my_d.device,
        my_d.voltage,
        electrodes,
        irradiation_flux=flux,
        bounds=my_d.bound,
        field_directory=solved_field(my_d, my_d.voltage, flux),
        interpolation_bins=my_d.device_dict.get("field_interpolation_bins"),
        pitch={"x": my_d.p_x, "y": my_d.p_y},
    )


def currents(kwargs, position=None):
    """The deposits drifted in the solved field of the device: current_<job>.h5,
    and the pictures of the first `plots` events in plots/ of its node.

    With a position, the deposits of that position of the device: the slice
    current.<position>, its file and pictures named so; a position with no
    deposit in the job leaves no file and {"events": 0} with its mark."""
    name = "current" if position is None else f"current.{position}"
    if position is not None and not any(position in record.detector for record in read_deposits(output(kwargs, "deposit")).events):
        return {"events": 0}
    my_d = bdv.Detector(kwargs["det_name"], kwargs["_files"]["device"])
    write_induced_currents(
        output(kwargs, "deposit"),
        output(kwargs, name),
        my_d,
        solved(my_d, kwargs),
        int(kwargs["plots"]),
        plots(kwargs, name),
        **({} if position is None else {"detector": position}),
    )
    return None
