"""The field of a device taken from a TCAD solution: a TDR file of Sentaurus,
solved at one bias, put into the field folder as a field solved at that bias."""

import os

import devsim
import h5py

from .create_mesh import mesh_axes
from .reading import Reading
from .save_milestone import save_milestone
from .save_milestone import save_record
from .save_milestone import save_solved
from .tdr_import import import_tdr


def electrode_voltages(tdr):
    """The voltage on each electrode of the solution in `tdr`, in V, by the
    name the electrode has in the file."""
    with h5py.File(tdr, "r") as source:
        geometry = source["collection"]["geometry_0"]
        return {
            geometry[f"region_{int(dataset.attrs['region'])}"].attrs["name"].decode(): float(
                dataset["values"][0]
            )
            for dataset in geometry["state_0"].values()
            if dataset.attrs["name"].decode() == "ContactExternalVoltage"
        }


def bias_of(tdr, electrode, asked=None):
    """The bias the solution in `tdr` was solved at: the voltage the file
    holds for `electrode`, the electrode the device is biased on. `asked` is
    the bias of the command, if it gave one: it has to be that of the file,
    and is taken for a file that holds no electrode voltages."""
    voltages = electrode_voltages(tdr)
    if not voltages:
        if asked is None:
            raise ValueError(f"{tdr} holds no electrode voltages: give its bias with -bias")
        return float(asked)
    if electrode not in voltages:
        raise ValueError(
            f"{tdr} has no electrode {electrode}, the one the device is biased on; "
            f"its electrodes are {voltages}"
        )
    if asked is not None and float(asked) != voltages[electrode]:
        raise ValueError(
            f"{tdr} was solved with {voltages[electrode]} V on {electrode}, not at {asked} V"
        )
    return voltages[electrode]


def import_field(tdr, my_d, folder, asked=None, flip=False):
    """Put the solution in `tdr` into `folder` as the field of `my_d` at the
    bias of the file, and list it in run.json as solved. Returns that bias."""
    my_d = Reading(my_d)
    bias = bias_of(tdr, my_d.device_dict["bias"]["electrode"], asked)
    try:
        device = import_tdr(tdr, os.path.join(folder, "converted.devsim"))
        save_milestone(device, bias, str(folder), my_d.dimension, None, False, is_tcad=True, is_flip=flip)
    finally:
        devsim.reset_devsim()
    save_record(str(folder), axes=mesh_axes(my_d), read=my_d.read)
    save_solved(str(folder), "potential", bias)
    return bias
