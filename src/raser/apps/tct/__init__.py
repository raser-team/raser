"""
Description:  tct/__init__.py
@Date       : 2025
@Author     : Xin Shi, Chenxi Fu, Lin Zhu
@version    : 2.0
"""

from raser.supports import jobs
from raser.supports import runs

from .workflow import load_defaults


def _apply_defaults(kwargs):
    config = load_defaults()
    kwargs["amplifier"] = kwargs.get("amplifier") or config.get("amplifier")
    if kwargs["amplifier"] is None:
        raise ValueError("TCT app config is missing required setting: amplifier")


def _run_scan(kwargs):
    prefix = list(kwargs["_entry_command_prefix"])
    tail = jobs.command_tail(
        kwargs["_argv"],
        prefix,
        {"-s", "--scan", "--job", "--run"},
    )
    tail.extend(["--run", runs.ensure_run_id(kwargs)])
    return jobs.run_indexed_jobs(
        prefix,
        tail,
        kwargs["scan"],
        use_cluster=kwargs["signal_batch"],
        mem=kwargs["mem"],
        destination="tct",
    )


def run_signal(kwargs):
    from .workflow import build_plan

    plan = build_plan(kwargs)
    if kwargs.get("dry_run"):
        plan.show()
        return plan
    from raser.apps._planning import activate_plan

    activate_plan(plan, kwargs)
    _apply_defaults(kwargs)
    if kwargs["job"] is not None:
        from . import tct_signal_scan

        tct_signal_scan.job_main(kwargs)
    elif kwargs["scan"] is not None:
        _run_scan(kwargs)
    else:
        from . import tct_signal

        tct_signal.main(kwargs)


def run_position_signal(kwargs):
    from .workflow import build_plan

    plan = build_plan(kwargs)
    if kwargs.get("dry_run"):
        plan.show()
        return plan
    from raser.apps._planning import activate_plan

    activate_plan(plan, kwargs)
    _apply_defaults(kwargs)
    from . import tct_signal_position_scan

    if kwargs["job"] is not None:
        tct_signal_position_scan.job_main(kwargs)
    elif kwargs["scan"] is not None:
        _run_scan(kwargs)
    else:
        kwargs["job"] = 0
        tct_signal_position_scan.job_main(kwargs)


def run_position_scan_draw(kwargs):
    from . import tct_signal_position_scan_draw

    tct_signal_position_scan_draw.main(kwargs)
