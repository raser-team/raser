import os
import subprocess
import sys

try:
    from ..util.output import output
except ImportError:
    from util.output import output

def main(kwargs):
    label = kwargs['label'] # Operation label or detector name
    name = kwargs['name'] # readout electronics name
    os.makedirs('output/afe/{}'.format(name), exist_ok=True)

    if label == 'trans':
        subprocess.run(['ngspice -b setting/electronics/{}.cir'.format(name)], shell=True)
    elif label == 'readout':
        from . import readout
        readout.main(name)
    elif label in (
        'estimate_noise',
        'estimate_noise_spectrum',
        'noise_spectrum',
        'estimate_spice_noise',
        'estimate_spice_noise_spectrum',
        'spice_noise',
        'spice_noise_spectrum',
    ):
        from . import noise_estimation
        noise_estimation.main(kwargs)
    elif label in ('validate_noise', 'validate_noise_spectrum', 'noise_validation'):
        from . import noise_validation
        noise_validation.main(kwargs)
    elif label == 'batch_signal':
        if kwargs['job_file'] == None:
            try:
                from ..util import batchjob
            except ImportError:
                from util import batchjob
            args = sys.argv

            if kwargs['tct'] != None:
                input_path = "output/tct/" + kwargs['source'] + "/" + kwargs['tct']
            else:
                input_path = "output/signal/" + kwargs['source'] + "/batch"
            files = os.listdir(input_path)
            files.sort()

            command_tail_list = args[args.index('afe')+1:]
            for file in files:
                if '.root' not in file:
                    continue
                file = os.path.join(input_path, file)
                args = ['afe', '-job_file', file] + command_tail_list
                command = ' '.join(args) 
                print(command)
                destination = 'afe'
                batchjob.main(destination, command, 1, is_test=False)
        else:
            from . import recreate_batch_signals
            recreate_batch_signals.main(name, kwargs['source'], kwargs['job_file'], kwargs['tct'])
    else:
        raise NameError
