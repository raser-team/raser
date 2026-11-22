"""raser deposit|current|readout|reconstruction|analysis <experiment folder or device>: the chain of
an experiment run up to that stage, with what it lacks before it, the field
among it. raser field is the stage command of the field.

The target is an experiment folder, which its config.json names the
workflow and the device of, or a device, whose experiment is
work/<device>/signal, made with the defaults of the stages when it is not
there."""

import json
import os
from functools import partial
from pathlib import Path

from raser.core.device.build_device import device_json
from raser.lifecycle.workflow import WORKFLOWS
from raser.lifecycle.workflow import execute
from raser.lifecycle.workflow import run_arguments
from raser.stages import chain
from raser.supports.paths import project_root_context
from raser.supports.paths import work_root

# stage -> its short command, what it does, and the options of it and of the stages before it
STAGES = {
    "deposit": ("dep", "the energy deposited by the source", (chain.deposit_arguments,)),
    "current": ("cur", "the induced currents, after the deposits and the field", (chain.deposit_arguments, chain.current_arguments)),
    "readout": ("rdo", "the waveforms of the electronics, after all before them", (chain.deposit_arguments, chain.current_arguments, chain.readout_arguments)),
    "reconstruction": ("reco", "every event of the waveforms as a row of its table, after all before them", (chain.deposit_arguments, chain.current_arguments, chain.readout_arguments, chain.reconstruction_arguments)),
    "analysis": ("ana", "the results of the points, after all before them", (chain.deposit_arguments, chain.current_arguments, chain.readout_arguments, chain.reconstruction_arguments)),
}


def _experiment(target):
    """The folder, workflow words and device of the experiment `target` names."""
    folder = Path(target).expanduser()
    config = folder / "config.json"
    if config.is_file():
        record = json.loads(config.read_text())
        return folder.resolve(), record["workflow"].split(), record.get("device")
    try:
        device_json(target)
    except FileNotFoundError:
        raise SystemExit(
            f"{target}: neither an experiment folder (a folder with a config.json) "
            "nor a device; give one of them, e.g. work/<device>/signal or HPK-Si-PiN"
        ) from None
    return work_root() / target / "signal", ["signal"], target


def run(stage, kwargs):
    folder, words, device = _experiment(kwargs["target"])
    workflow = WORKFLOWS[" ".join(words)]
    names = [piece.name for piece in workflow.slices]
    stages = {name.split(".")[0] for name in names} | ({"analysis"} if workflow.analysis else set())
    if stage not in stages:
        raise SystemExit(
            f"{folder}: the experiment {' '.join(words)} has no {stage} slice; its slices: {names}"
        )
    # Its files are found as its own command finds them; the jobs are its own.
    project = folder.parents[len(words) - 1]
    options = {**kwargs, "det_name": device, "until": stage, "_entry_command_prefix": (words[0],)}
    if (folder / "config.json").is_file():
        # A job on the cluster starts the command again from the experiment
        # folder: the target is written as the whole path.
        argv = kwargs.get("_argv") or []
        options["_argv"] = [str(folder) if word == kwargs["target"] else word for word in argv]
    here = os.getcwd()
    with project_root_context(project, kwargs["_components_of"][words[0]]):
        if folder.is_dir():
            os.chdir(folder)  # the experiment of this folder, wherever it is
        try:
            return execute(workflow, options)
        finally:
            os.chdir(here)


def register(subparsers):
    for stage, (short, does, adders) in STAGES.items():
        parser = subparsers.add_parser(
            stage, aliases=[short], help=f"stage: {does}, in an experiment or a device's signal"
        )
        parser.add_argument("target", help="experiment folder, or a device for work/<device>/signal")
        for add in adders:
            add(parser)
        run_arguments(parser)
        parser.set_defaults(_run=partial(run, stage))
