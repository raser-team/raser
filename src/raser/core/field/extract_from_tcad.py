#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
@File    :   extract_from_tcad.py
@Time    :   2025/04/01
@Author  :   Chenxi Fu
@Version :   1.0
'''

import os
import sys
import subprocess
from pathlib import Path

import devsim

from .save_milestone import save_milestone
from ..device.build_device import Detector
from raser.supports.output import create_path

def main(tdr_file, detector, output_directory, bias_voltage, is_flip=False):
    destination = create_path(Path(output_directory))
    devsim_file = destination / "converted.devsim"
    my_detector = Detector(detector)

    subprocess.run(
        [
            "tdr_convert",
            "--tdr",
            str(tdr_file),
            "--devsim",
            str(devsim_file),
            "--load_datasets",
        ],
        check=True,
    )

    devsim.load_devices(file=str(devsim_file)) # no positional arguments
    print(devsim.get_device_list()[0])
    device = devsim.get_device_list()[0]

    save_milestone(
        device,
        float(bias_voltage),
        str(destination),
        my_detector.dimension,
        None,
        False,
        is_tcad=True,
        is_flip=is_flip,
    )

    devsim.reset_devsim()

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]))
