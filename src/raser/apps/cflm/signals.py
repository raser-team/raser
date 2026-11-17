"""The currents and the waveforms of one pad: currents.<pad>_<job>.h5 and
waveforms.<pad>_<job>.h5.

Every pad is a device of its own, of the device file of the command: its
currents are those of its own deposits in the deposits file. A pad that
got no deposit in any bunch of the job has neither file; its two slices
leave {"events": 0} with their marks.
"""

import os

from raser.stages.current import solved
from raser.stages.files import output
from raser.core.current.cal_current import electrode_names
from raser.core.current.cal_current import write_induced_currents
from raser.core.device import build_device as bdv
from raser.core.readout.circuit import named_chain
from raser.core.field.circuit_parameters import device_sensor
from raser.core.readout.job import write_waveforms
from raser.core.deposit.deposits import read_deposits


def currents(kwargs, pad):
    deposits_path = output(kwargs, "deposit")
    if not any(pad in record.detector for record in read_deposits(deposits_path).events):
        return {"events": 0}
    my_d = bdv.Detector(kwargs["det_name"], kwargs["_files"]["device"])
    name = f"current.{pad}"
    write_induced_currents(
        deposits_path,
        output(kwargs, name),
        my_d,
        solved(my_d, kwargs),
        int(kwargs["plots"]),
        os.path.join(
            os.path.dirname(kwargs["_slice_batch_paths"][name]),
            "plots",
            "job_%s_%s" % (kwargs.get("job_index") or 0, pad),
        ),
        detector=pad,
    )
    return None


def waveforms(kwargs, pad):
    currents_path = output(kwargs, f"current.{pad}")
    if not os.path.exists(currents_path):
        return {"events": 0}
    my_d = bdv.Detector(kwargs["det_name"], kwargs["_files"]["device"])
    sensor, values = device_sensor(my_d, electrode_names(my_d.read_out_contact, my_d.read_ele_num))
    write_waveforms(
        currents_path,
        output(kwargs, f"readout.{pad}"),
        named_chain(str(kwargs["amplifier"])),
        sensor,
        kwargs.get("seed"),
        sensor_values=values,
    )
    return None
