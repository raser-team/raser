#sweep
import sys
import subprocess
from concurrent.futures import ProcessPoolExecutor
import os
from ..util import batchjob
def main(kwargs):
    label = kwargs['label']
    use_cluster = kwargs.get('batch', False)
    run = kwargs.get('run', False)
    Xray = kwargs.get('Xray', False)
    if label == "sweep":
        if run:
            args = sys.argv
            command_tail_list = args[args.index('sweep'):]
            if '-b' in command_tail_list:
                command_tail_list.remove('-b')
            if '--batch' in command_tail_list:
                command_tail_list.remove('--batch')
            if use_cluster:
                args = command_tail_list
                command = ' '.join(args)
                print(command)
                destination = 'sweep'
                batchjob.main(destination, command, mem, is_test=False)

        elif Xray:
            from . import energy_resolution
            energy_resolution.main(kwargs)

        else:
            from . import sweep
            sweep.main(kwargs)
    
            # from . import root_test
            # root_test.main(kwargs)

        
        #det_name = kwargs['det_name']
        #my_d = bdv.Detector(det_name)