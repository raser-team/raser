'''
Description:  tct/__init__.py
@Date       : 2025
@Author     : Xin Shi, Chenxi Fu, Lin Zhu
@version    : 2.0
'''

import json

from raser.supports.paths import PACKAGE_ROOT


DEFAULT_CONFIG = PACKAGE_ROOT / "apps" / "tct" / "transient_current.json"


def _load_config():
    with open(DEFAULT_CONFIG) as f:
        return json.load(f)


def _apply_defaults(kwargs):
    config = _load_config()
    kwargs["amplifier"] = kwargs.get("amplifier") or config.get("amplifier")
    if kwargs["amplifier"] is None:
        raise ValueError("TCT app config is missing required setting: amplifier")


def run_signal(kwargs):
    _apply_defaults(kwargs)
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
    _apply_defaults(kwargs)
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
