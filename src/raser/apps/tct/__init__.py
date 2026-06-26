# def main(kwargs):
#     label = kwargs['label']

#     if label == 'signal':
#         from . import tct_signal
#         tct_signal.main(kwargs)
#     else:
#         raise NameError

'''
Description:  tct/__init__.py
@Date       : 2025
@Author     : Xin Shi, Chenxi Fu, Lin Zhu
@version    : 2.0
'''

def main(kwargs):    
    print(kwargs)
    label = kwargs['label']
    scan_number = kwargs['scan']
    job_number = kwargs['job']
    if label == 'signal':
        if scan_number != None:
            if job_number != None:
                from . import tct_signal_scan
                tct_signal_scan.job_main(kwargs)
            else:
                from . import tct_signal_scan
                tct_signal_scan.main(kwargs)
        else:
            from . import tct_signal
            tct_signal.main(kwargs)
    elif label == 'position_signal':
        if scan_number != None:
            if job_number != None:
                from . import tct_signal_position_scan
                tct_signal_position_scan.job_main(kwargs)
            else:
                from . import tct_signal_position_scan
                tct_signal_position_scan.main(kwargs)
        else:
            kwargs['scan']=1
            kwargs['job']=str(0)
            # print(kwargs)
            from . import tct_signal_position_scan
            tct_signal_position_scan.job_main(kwargs)
            # tct_signal_position_scan.main(kwargs)
    elif label == 'position_scan_draw':
        from . import tct_signal_position_scan_draw
        tct_signal_position_scan_draw.main(kwargs)
    else:
        raise NameError