from . import *
def main(kwargs):
    label = kwargs['label']
    if label == 'temperature':
        from . import cal_temp
        cal_temp.main()

    if label == 'cflm_v1':
        from . import cflm
        cflm.main()
    else:
        raise NameError(label)