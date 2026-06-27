'''
Description:  tct/__init__.py
@Date       : 2025
@Author     : Xin Shi, Chenxi Fu, Lin Zhu
@version    : 2.0
'''


def run_signal(kwargs):
    if kwargs['scan'] is not None:
        from . import tct_signal_scan
        if kwargs['job'] is not None:
            tct_signal_scan.job_main(kwargs)
        else:
            tct_signal_scan.main(kwargs)
    else:
        from . import tct_signal
        tct_signal.main(kwargs)


def run_position_signal(kwargs):
    from . import tct_signal_position_scan

    if kwargs['scan'] is not None:
        if kwargs['job'] is not None:
            tct_signal_position_scan.job_main(kwargs)
        else:
            tct_signal_position_scan.main(kwargs)
    else:
        kwargs['scan']=1
        kwargs['job']=str(0)
        tct_signal_position_scan.job_main(kwargs)


def run_position_scan_draw(kwargs):
    from . import tct_signal_position_scan_draw

    tct_signal_position_scan_draw.main(kwargs)
