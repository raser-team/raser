"""The currents of one pad: currents.<pad>_<job>.h5.

Every pad is a device of its own, of the device file of the command: its
currents are those of its own deposits in the deposits file. A pad that
got no deposit in any bunch of the job has no file; its slice leaves
{"events": 0} with its mark.
"""

import os

from raser.apps.signal.gen_signal import output
from raser.apps.signal.gen_signal import solved
from raser.core.current.cal_current import write_induced_currents
from raser.core.device import build_device as bdv
from raser.core.interaction.deposits import read_deposits


def currents(kwargs, pad):
    deposits_path = output(kwargs, "deposits")
    if not any(pad in record.detector for record in read_deposits(deposits_path).events):
        return {"events": 0}
    my_d = bdv.Detector(kwargs["det_name"], kwargs["_files"]["device"])
    name = f"currents.{pad}"
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

