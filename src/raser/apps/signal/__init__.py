'''
Description:  signal/__init__.py
@Date       : 2025
@Author     : Xin Shi, Chenxi Fu, Jian Feng
@version    : 2.0
'''

from raser.supports import jobs
from raser.supports import runs


def _command_tail(kwargs):
    command_prefix = list(kwargs['_entry_command_prefix'])
    return jobs.command_tail(
        kwargs['_argv'],
        command_prefix,
        {"-s", "--scan", "--job", "--run"},
    )


def _run_scan(kwargs):
    scan_number = kwargs['scan']
    mem = kwargs['mem']
    use_cluster = kwargs['signal_batch']
    command_prefix = list(kwargs['_entry_command_prefix'])
    command_tail_list = _command_tail(kwargs)
    run_id = runs.ensure_run_id(kwargs)
    command_tail_list.extend(["--run", run_id])
    jobs.run_indexed_jobs(
        command_prefix,
        command_tail_list,
        scan_number,
        use_cluster=use_cluster,
        mem=mem,
        destination=command_prefix[0],
    )


def _run_signal_samples(kwargs):
    sample_count = kwargs["scan"]
    kwargs["events_per_job"] = sample_count
    kwargs["job"] = 0
    kwargs["scan"] = None
    kwargs["_signal_plot_samples"] = sample_count
    from . import gen_signal_scan

    gen_signal_scan.main(kwargs)


def run_signal(kwargs):
    runs.apply_run_config(kwargs)
    if kwargs['scan'] is not None:
        if kwargs.get("_command") == "signal" and not kwargs["signal_batch"]:
            _run_signal_samples(kwargs)
        else:
            _run_scan(kwargs)
    elif kwargs['job'] is not None:
        from . import gen_signal_scan
        gen_signal_scan.main(kwargs)
    else:
        from . import gen_signal_main
        gen_signal_main.main(kwargs)
