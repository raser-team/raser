from . import *
def main(kwargs):
    label = kwargs['label']

    if label == 'foo':
        foo.main()
    if label == 'ngspice_t1':
        import subprocess
        subprocess.run(['ngspice -b -r t1.raw output/T1_tmp.cir'], shell=True)
    if label == 'drs4_get_analog':
        import subprocess
        subprocess.run(['ngspice -b -r drs4_analog.raw paras/drs4_analog.cir'], shell=True)
    if label == 'drs4_get_fig':
        from . import drs4_get_fig
        drs4_get_fig.main()
    else:
        raise NameError(label)