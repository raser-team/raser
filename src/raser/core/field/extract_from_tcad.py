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
import re

import devsim

from .save_milestone import save_milestone
from ..device.build_device import Detector

def main(tdr_file, is_flip=False):
    # make sure the file is in output/[det_name]/ or output/[det_name]/weightingfield/[electrode_name]/
    # and named as [bias voltage]V.tdr
    dir_name = os.path.dirname(tdr_file)
    file_base_name = os.path.basename(tdr_file)

    try:
        bias_voltage = float(file_base_name[:-5]) # remove the V.tdr suffix
    except ValueError:
        raise ValueError("The input file should be '[float:bias voltage]V.tdr'")
    
    if os.path.basename(os.path.dirname(dir_name)) == 'weightingfield':
        det_name = os.path.basename(os.path.dirname(os.path.dirname(dir_name)))
    else:
        det_name = os.path.basename(dir_name)
    
    devsim_file = os.path.join(dir_name, file_base_name[:-5]+'.devsim')
    my_detector = Detector(det_name)

    subprocess.run(['tdr_convert', 
                    '--tdr', tdr_file, 
                    '--devsim', devsim_file,
                    '--load_datasets'])

    devsim.load_devices(file=devsim_file) # no positional arguments
    print(devsim.get_device_list()[0])
    device = devsim.get_device_list()[0]

    save_milestone(device, bias_voltage, dir_name, my_detector.dimension, None, False, is_tcad=True, is_flip=is_flip,)

    devsim.reset_devsim()

if __name__ == '__main__':
    main(sys.argv[1])