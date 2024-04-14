#!/usr/bin/env python3
# Main driver to run raser    
# Author FU Chenxi <1256257282@qq.com>, SHI Xin <shixin@ihep.ac.cn>
# Created [2023-08-29 Tue 11:48] 

import sys 
import argparse
import importlib
import subprocess

VERSION = 4.0

parser = argparse.ArgumentParser(prog='raser')
parser.add_argument('--version', action='version', 
                    version='%(prog)s {}'.format(VERSION))
parser.add_argument('-b', '--batch', help='submit BATCH job to cluster', action="store_true")
parser.add_argument('-t', '--test', help='TEST', action="store_true")
parser.add_argument('-sh', '--shell', help='flag of run raser in SHELL', action="store_true")

subparsers = parser.add_subparsers(help='sub-command help', dest="subparser_name")

parser_asic = subparsers.add_parser('asic', help='ASIC design')
parser_asic.add_argument('label', help='LABEL to identify ASIC design')

parser_draw = subparsers.add_parser('current', help='calculate drift current')
parser_draw.add_argument('label', help='LABEL to identify root files')

parser_draw = subparsers.add_parser('draw', help='draw figures')
parser_draw.add_argument('label', help='LABEL to identify root files')

parser_gsignal = subparsers.add_parser('elec', help='electronic readout')
parser_gsignal.add_argument('label', help='LABEL to identify electronics files')

parser_field = subparsers.add_parser('field', help='calculate field and iv/cv')
parser_field.add_argument('label', help='LABEL to identify operation')
parser_field.add_argument('-v', '--verbose', help='VERBOSE level', 
                          action='count', default=0)
parser_field.add_argument('-cv', help='CV simulation', action="store_true")

parser_fpga = subparsers.add_parser('fpga', help='FPGA design')
parser_fpga.add_argument('label', help='LABEL to identify FPGA design')

parser_gen_signal = subparsers.add_parser('gen_signal', help='generate signal')
parser_gen_signal.add_argument('det_name', help='name of the detector')
parser_gen_signal.add_argument('-vol', '--voltage', type=str, help='bias voltage')
parser_gen_signal.add_argument('-abs', '--absorber', type=str, help='model of particle energy absorber')
parser_gen_signal.add_argument('-amp', '--amplifier', type=str, help='amplifier')
parser_gen_signal.add_argument('-s', '--scan', type=int, help='instance number for scan mode')

parser_gsignal = subparsers.add_parser('particle', help='calculate particle')
parser_gsignal.add_argument('label', help='LABEL to identify spaceres files')

parser_root = subparsers.add_parser('root', help='root files conversion')
parser_root.add_argument('label', help='LABEL to identify root files')

parser_spaceres = subparsers.add_parser('spaceres', help='space resolution calculation')
parser_spaceres.add_argument('label', help='LABEL to identify spaceres files')

parser_spaceres = subparsers.add_parser('timeres', help='time resolution calculation')
parser_spaceres.add_argument('det_name', help='name of the detector')

args = parser.parse_args()

if len(sys.argv) == 1:
    parser.print_help()
    sys.exit(1)

kwargs = vars(args)

submodules = ['asic', 'current', 'draw', 'elec', 'field', 'fpga', 'gen_signal', 'particle', 'root', 'spaceres', 'timeres']

submodule = kwargs['subparser_name']
if submodule not in submodules:
    raise NameError(submodule)

if kwargs['batch'] == True:
    from util import batchjob
    destination = submodule
    command = ' '.join(sys.argv[1:])
    command = command.replace('--batch ', '')
    command = command.replace('-b ', '')
    batchjob.main(destination, command, args)

elif kwargs['shell'] == False: # not in shell
    try:
        for package in ['ROOT', 'geant4_pybind', 'devsim']:
            # package dependency check
            import package
        submodule = importlib.import_module(submodule)
        submodule.main(kwargs)

    except ModuleNotFoundError:
        # use apptainer instead
        command = ' '.join(['-sh']+sys.argv[1:])
        import os
        IMGFILE = os.environ.get('IMGFILE')
        BINDPATH = os.environ.get('BINDPATH')
        raser_shell = "/usr/bin/apptainer exec --env-file cfg/env -B" + " " \
                    + BINDPATH + " " \
                    + IMGFILE + " " \
                    + "python3 raser"
        subprocess.run([raser_shell+' '+command], shell=True, executable='/bin/bash')

else: # in shell
    submodule = importlib.import_module(submodule)
    submodule.main(kwargs)
    
