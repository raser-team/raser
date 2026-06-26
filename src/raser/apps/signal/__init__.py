'''
Description:  signal/__init__.py
@Date       : 2025
@Author     : Xin Shi, Chenxi Fu, Jian Feng
@version    : 2.0
'''

import sys
import subprocess
from concurrent.futures import ProcessPoolExecutor
import os 

def run_local_job(args_tuple):
    i, command_name, command_tail_list = args_tuple
    args = [command_name, '--job', str(i)] + command_tail_list
    command = ' '.join(args)
    print(command)
    subprocess.run(['raser'] + args, shell=False)
        
def main(kwargs):    
    label = kwargs['label']
    scan_number = kwargs['scan']
    job_number = kwargs['job']
    mem = kwargs['mem']
    use_cluster = kwargs['signal_batch']
    command_name = kwargs['subparser_name']
    if label == 'signal':
        if scan_number != None:
            from raser.supports import batchjob
            scan_number = kwargs['scan']
            args = sys.argv
            command_tail_list = args[args.index(command_name)+1:]
            for i in command_tail_list:
                if i == '-s':
                    index = command_tail_list.index(i)
                    command_tail_list.remove(command_tail_list[index+1]) # remove scan number
                    command_tail_list.remove(i) # remove '-s'
                    break
            if '-b' in command_tail_list:
                command_tail_list.remove('-b')
            if '--batch' in command_tail_list:
                command_tail_list.remove('--batch')
            if use_cluster:
                for i in range(scan_number):
                    args = [command_name, '--job', str(i)] + command_tail_list
                    command = ' '.join(args) 
                    print(command)
                    destination = command_name
                    batchjob.main(destination, command, mem, is_test=False)
            else:
                max_processes = min(scan_number, os.cpu_count() or 4)
                task_args = [
                    (i, command_name, command_tail_list)
                    for i in range(scan_number)
                ]
                with ProcessPoolExecutor(max_workers=max_processes) as executor:
                    executor.map(run_local_job, task_args)
        elif job_number != None:
            from . import gen_signal_scan
            gen_signal_scan.main(kwargs)
        else:
            from . import gen_signal_main
            gen_signal_main.main(kwargs)
