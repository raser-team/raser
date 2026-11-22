"""The file of a slice of a job.

Written into the node of the slice, <experiment>/nodes/<stage>/<node>/, which
several points read when the slice does not read what makes them differ:
    deposit.h5    energy deposits and pairs of the recorded events
    current.h5    induced current of every electrode, event by event
    readout.h5    output voltage of the electronics, event by event
A slice of one position of several, current.<position>, writes current.<position>.h5.
"""

import os
from contextlib import nullcontext

from raser.supports.paths import project_root_context


def _job(kwargs):
    return kwargs.get("job_index") or 0


def output(kwargs, name):
    """The file of the slice `name` of this job, in the node of the slice."""
    return os.path.join(kwargs["_node_paths"][name], "%s.h5" % name)


def plots(kwargs, name):
    """The folder of the pictures of the slice `name` of this job, in its node."""
    return os.path.join(kwargs["_node_paths"][name], "plots")


def field_project(kwargs):
    """The project the field of the device of this slice is looked up in.

    An experiment of several devices has the field of each in the project of
    that device, work/<device>/field, given as "_field_project"; everything
    else of the slice stays in the project of the experiment. With one device
    the two are the same project and nothing changes."""
    project = kwargs.get("_field_project")
    return nullcontext() if project is None else project_root_context(project)
