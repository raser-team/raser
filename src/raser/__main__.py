#!/usr/bin/env python3
# Main driver to run raser    
# Author FU Chenxi <1256257282@qq.com>, SHI Xin <shixin@ihep.ac.cn>
# Created [2023-08-29 Tue 11:48] 

import sys 
import argparse
import importlib

VERSION = 4.1

parser = argparse.ArgumentParser(prog='raser')
parser.add_argument('--version', action='version', 
                    version='%(prog)s {}'.format(VERSION))
parser.add_argument('-b', '--batch', help='submit BATCH job to cluster', action='count', default=0, dest='global_batch')
parser.add_argument('-t', '--test', help='TEST', action="store_true")

subparsers = parser.add_subparsers(help='sub-command help', dest="subparser_name")

parser_afe = subparsers.add_parser('afe', help='Analog Front End readout')
parser_afe.add_argument('label', help='LABEL to identify electronics operations')
parser_afe.add_argument('name', help='LABEL to identify electronics files')
parser_afe.add_argument('-source', help='source current file for recreate_batch_signals')
parser_afe.add_argument('-job_file', help='job file for recreate_batch_signals')
parser_afe.add_argument('-tct', help='reprocess TCT signal for recreate_batch_signals')

parser_bmos = subparsers.add_parser('bmos', help='Beam Monitor Online System')
parser_bmos.add_argument('label', help='LABEL to identify BMOS simulations')
parser_bmos.add_argument('-v', '--verbose', help='VERBOSE level', 
                          action='count', default=0)

parser_cce = subparsers.add_parser('cce', help='Charge Collection Efficiency')
parser_cce.add_argument('label', help='LABEL to identify CCE experiment')

parser_current = subparsers.add_parser('current', help='calculate drift current')
parser_current.add_argument('label', help='LABEL to identify root files')

parser_dfe = subparsers.add_parser('dfe', help='Digital Front End design')
parser_dfe.add_argument('label', help='LABEL to identify Digital Front End design')

parser_field = subparsers.add_parser('field', help='calculate field/weight field and iv/cv')
parser_field.add_argument('label', help='LABEL to identify operation')
parser_field.add_argument('-v', '--verbose', help='VERBOSE level', 
                          action='count', default=0)
parser_field.add_argument('-cv', help='CV simulation', action="store_true")
parser_field.add_argument("-wf", help="WeightField Simulation", action="store_true")
parser_field.add_argument("-irr", "--irradiation_flux", help="irradiationm flux", type=float)
parser_field.add_argument("-bias", help="bias voltage", type=float)
parser_field.add_argument("-v_current", help="Current voltage for step-by-step simulation", type=float)
parser_field.add_argument("-noise", help="Detector Noise simulation", action="store_true")
parser_field.add_argument('-umf', help='use umf solver', action="store_true")
parser_field.add_argument('-ext', '--extract', help='extract field from TCAD file', action="store_true")
parser_field.add_argument('-flip', help='flip the direction of the electric field', action="store_true")
parser_field.add_argument('-wf_sub', help='calculate weight field from two devsim file', nargs=2)

parser_interaction = subparsers.add_parser('interaction', help='particle-matter interation module')
parser_interaction.add_argument('label', help='LABEL to identify particle-matter interation')
parser_interaction.add_argument('-v', '--verbose', help='VERBOSE level', 
                          action='count', default=0)

parser_lumi = subparsers.add_parser('lumi', help='CEPC Fast Luminosity Monitor')
parser_lumi.add_argument('label', help='LABEL to identify CFLM simulations')
parser_lumi.add_argument('-v', '--verbose', help='VERBOSE level', 
                          action='count', default=0)

parser_mcu = subparsers.add_parser('mcu', help='Micro Control Unit design')
parser_mcu.add_argument('label', help='LABEL to identify Micro Control Unit design')

parser_resolution = subparsers.add_parser('resolution', help='resolution calculation for time, space and energy')
parser_resolution.add_argument('det_name', help='name of the detector')
parser_resolution.add_argument('-tct', type=str, help='specify TCT signal class')
parser_resolution.add_argument('-daq', type=str, help='specify DAQ system')
parser_resolution.add_argument('-vol', '--voltage', type=str, help='bias voltage')
parser_resolution.add_argument('-irr', '--irradiation', type=str, help='irradiation flux')
parser_resolution.add_argument('-g4', '--g4experiment', type=str, help='model of Geant4 experiment')
parser_resolution.add_argument('-amp', '--amplifier', type=str, help='amplifier')

parser_signal = subparsers.add_parser('signal', help='generate signal')
parser_signal.add_argument('det_name', help='name of the detector')
parser_signal.add_argument('-l','--label', help='LABEL to identify signal generation method', default='signal')
parser_signal.add_argument('-vol', '--voltage', type=str, help='bias voltage')
parser_signal.add_argument('-irr', '--irradiation', type=str, help='irradiation flux')
parser_signal.add_argument('-g4', '--g4experiment', type=str, help='model of Geant4 experiment')
parser_signal.add_argument('-g4_vis', help='visualization of Geant4 experiment', action="store_true")
parser_signal.add_argument('-amp', '--amplifier', type=str, help='amplifier')
parser_signal.add_argument('-s', '--scan', type=int, help='instance number for scan mode')
parser_signal.add_argument('-b', '--batch', action='store_true', help='submit signal scan jobs to cluster (used with -s)', dest='signal_batch')
parser_signal.add_argument('--job', type=int, help='flag of run in job')
parser_signal.add_argument('-mem', type=int, help='memory limit of the job in 8GB', default=1)

parser_tct = subparsers.add_parser('tct', help='TCT simulation')
parser_tct.add_argument('label', help='LABEL to identify TCT options')
parser_tct.add_argument('det_name', help='name of the detector')
parser_tct.add_argument('laser', help='name of the laser')
parser_tct.add_argument('-vol', '--voltage', type=str, help='bias voltage')
parser_tct.add_argument('-amp', '--amplifier', type=str, help='amplifier')
parser_tct.add_argument('-s', '--scan', type=int, help='instance number for scan mode')
parser_tct.add_argument('--job', type=int, help='flag of run in job')

parser_telescope = subparsers.add_parser('telescope', help='telescope')
parser_telescope.add_argument('label', help='LABEL to identify telescope files')

parser_sweep = subparsers.add_parser('sweep', help='parameter sweep')
parser_sweep.add_argument('-l','--label', help='LABEL to identify signal generation method', default='sweep')
parser_sweep.add_argument('det_name', help='name of the detector')
parser_sweep.add_argument('-b', '--batch', action='store_true', help='submit sweep jobs to cluster (used with -s)', dest='signal_batch')
#parser_sweep.add_argument('-p','--parameter',type=str, help='parameter for sweep')
#parser_sweep.add_argument('-ra','--range',type=str, help='sweeped range')
#parser_sweep.add_argument('-st','--step',type=int, help='step for sweep')
#parser_sweep.add_argument('-s','--sweep',type=int, help='instance number for sweep mode')
#parser_sweep.add_argument('-mem', type=int, help='memory limit of the job in 8GB', default=1)
parser_sweep.add_argument('-r', '--run', help='run', action="store_true")
parser_sweep.add_argument('-X', '--Xray', help='Xray energy resolution', action="store_true")
parser_sweep.add_argument('-vol', '--voltage', type=str, help='bias voltage')
parser_sweep.add_argument('-irr', '--irradiation', type=str, help='irradiation flux')
parser_sweep.add_argument('-g4', '--g4experiment', type=str, help='model of Geant4 experiment')
parser_sweep.add_argument('-amp', '--amplifier', type=str, help='amplifier')

args = parser.parse_args()

if __name__ == "__main__":
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
        
    kwargs = vars(args)

    submodule = kwargs['subparser_name']
    # __package__ is src.raser, the "." is meant to coorperate with src.raser to avoid namespace conflict

    if kwargs['global_batch'] != 0:
        if not kwargs.get('signal_batch', False):
            batch_level = kwargs['global_batch']
            import re
            from .util import batchjob
            destination = submodule
            command = ' '.join(sys.argv[1:])
            command = command.replace('--batch ', '')
            for bs in re.findall('-b* ', command):
                command = command.replace(bs, '')
            is_test = vars(args)['test'] 
            batchjob.main(destination, command, batch_level, is_test)
        else:
            submodule = importlib.import_module("." + submodule, package=__package__)
            submodule.main(kwargs)
    else:
        submodule = importlib.import_module("." + submodule, package=__package__)
        submodule.main(kwargs)
        

