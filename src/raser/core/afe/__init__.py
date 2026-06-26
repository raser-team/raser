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


def main(kwargs):
    label = kwargs["label"]  # Operation label or detector name
    name = kwargs["name"]  # readout electronics name
    create_path(project_path("afe", name))

    if label == "trans":
        ele_cir = component_path("electronics", name + ".cir")
        subprocess.run(["ngspice -b {}".format(ele_cir)], shell=True)
    elif label == "readout":
        from . import readout

        readout.main(name)
    elif label == "batch_signal":
        if kwargs["job_file"] is None:
            from raser.supports import batchjob

            args = sys.argv

            if kwargs["tct"] is not None:
                input_path = project_path("tct", kwargs["tct"])
            else:
                source = kwargs["source"]
                if source is None:
                    raise ValueError("afe batch_signal requires -source such as cce/Am241")
                source_path = Path(source)
                if source_path.is_absolute() or len(source_path.parts) > 2:
                    input_path = source_path
                else:
                    source_parts = source_path.parts
                    if len(source_parts) != 2:
                        raise ValueError("afe batch_signal -source must be like cce/Am241")
                    input_path = project_path("signal", source_parts[0], source_parts[1], "batch")
            files = os.listdir(input_path)
            files.sort()

            command_tail_list = args[args.index("afe") + 1 :]
            for file in files:
                if ".root" not in file:
                    continue
                file = os.path.join(input_path, file)
                args = ["afe", "-job_file", file] + command_tail_list
                command = " ".join(args)
                print(command)
                destination = "afe"
                batchjob.main(destination, command, 1, is_test=False)
        else:
            from . import recreate_batch_signals

            recreate_batch_signals.main(
                name, kwargs["source"], kwargs["job_file"], kwargs["tct"]
            )
    else:
        raise NameError
