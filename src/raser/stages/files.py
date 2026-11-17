"""The file of a slice of a job.

Written into batch/ of the seed folder that holds the slice, which is the
one of another point when the slice does not read what makes this point
differ; one file per job and slice:
    deposit_<job>.h5    energy deposits and pairs of the recorded events
    current_<job>.h5    induced current of every electrode, event by event
    readout_<job>.h5   output voltage of the electronics, event by event
"""

import os


def _job(kwargs):
    return kwargs.get("job_index") or 0


def output(kwargs, name):
    """The file of the slice `name` of this job, in the point that holds the slice."""
    return os.path.join(
        kwargs["_slice_batch_paths"][name], "%s_%s.h5" % (name, _job(kwargs))
    )
