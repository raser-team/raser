"""Lumi application package."""

import importlib

from raser.supports.output import output

TASKS = {
    "pe_dis": "data_file",
    "spd_dis": "spd_dis",
    "spd_dis_plot": "spd_plot",
    "np_precision_plot": "np_precision_plot",
    "lumi_fit": "lumi_TSC_precision_fit",
    "Amp_dis": "amplitude_dis",
    "bunch_number": "bunch_number",
    "p1_sample": "p1_sample",
    "DAQ_sim": "DAQ_system_sim",
    "current": "get_current_p1",
    "Pixel_current": "pixel_current_plot",
}


def register(subparsers):
    parser = subparsers.add_parser("lumi", help="CEPC Fast Luminosity Monitor")
    tasks = parser.add_subparsers(dest="lumi_task", required=True)
    for task in TASKS:
        tasks.add_parser(task)
    parser.set_defaults(_run=run)


def run(kwargs):
    task = kwargs["lumi_task"]
    module = importlib.import_module("." + TASKS[task], __package__)
    if task == "current":
        return module.main(output(__file__, "test"))
    if task == "Pixel_current":
        return module.main(output(__file__, "N0_3_4"), "340")
    return module.main()
