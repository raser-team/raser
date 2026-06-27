"""
@Date       : 2023
@Author     : Chenxi Fu
@version    : 2.0
"""

import os
import subprocess
import sys
from pathlib import Path

from raser.supports.output import create_path
from raser.supports.paths import component_path
from raser.supports.paths import project_path


def trans(name):
    create_path(project_path("analog", name))
    ele_cir = component_path("electronics", "analog", name + ".cir")
    subprocess.run(["ngspice -b {}".format(ele_cir)], shell=True)


def readout(name):
    create_path(project_path("analog", name))
    from . import readout

    readout.main(name)


def _batch_input_path(kwargs):
    if kwargs["tct"] is not None:
        return project_path("tct", kwargs["tct"])
    source = kwargs["source"]
    if source is None:
        raise ValueError("analog batch_signal requires -source such as cce/Am241")
    source_path = Path(source)
    if source_path.is_absolute() or len(source_path.parts) > 2:
        return source_path
    source_parts = source_path.parts
    if len(source_parts) != 2:
        raise ValueError("analog batch_signal -source must be like cce/Am241")
    return project_path("signal", source_parts[0], source_parts[1], "batch")


def _submit_batch_signal(kwargs):
    from raser.supports import batchjob

    input_path = _batch_input_path(kwargs)
    command_tail_list = sys.argv[sys.argv.index("analog") + 1 :]
    for file in sorted(os.listdir(input_path)):
        if ".root" not in file:
            continue
        file = os.path.join(input_path, file)
        args = ["analog", "-job_file", file] + command_tail_list
        command = " ".join(args)
        print(command)
        batchjob.main("analog", command, 1, is_test=False)


def batch_signal(kwargs):
    name = kwargs["name"]
    create_path(project_path("analog", name))
    if kwargs["job_file"] is None:
        _submit_batch_signal(kwargs)
    else:
        from . import recreate_batch_signals

        recreate_batch_signals.main(
            name, kwargs["source"], kwargs["job_file"], kwargs["tct"]
        )
