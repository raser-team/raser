"""The file of a slice of a job.

Written into the node of the slice, <experiment>/nodes/<stage>/<node>/, which
several points read when the slice does not read what makes them differ:
    deposit.h5    energy deposits and pairs of the recorded events
    current.h5    induced current of every electrode, event by event
    readout.h5    output voltage of the electronics, event by event
A slice of one position of several, current.<position>, writes current.<position>.h5.
"""

import os


def _job(kwargs):
    return kwargs.get("job_index") or 0


def output(kwargs, name):
    """The file of the slice `name` of this job, in the node of the slice."""
    return os.path.join(kwargs["_node_paths"][name], "%s.h5" % name)


def plots(kwargs, name):
    """The folder of the pictures of the slice `name` of this job, in its node."""
    return os.path.join(kwargs["_node_paths"][name], "plots")
