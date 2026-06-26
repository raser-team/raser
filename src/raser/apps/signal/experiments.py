"""Signal experiment and source configuration helpers."""

import copy
import json
from pathlib import Path

from raser.supports.paths import app_component_roots
from raser.supports.paths import component_file_path
from raser.supports.paths import component_path


DEFAULT_EXPERIMENT = "charge_collection"
DEFAULT_SOURCE = "radioactive/Am241"


def _load_app_component(kind, name_or_path):
    config_name = name_or_path
    config_path = Path(config_name)
    if (
        hasattr(config_name, "__fspath__")
        or config_path.is_absolute()
        or (config_path.parts and config_path.parts[0] in {".", ".."})
        or config_path.suffix
    ):
        config_json = component_file_path(kind, config_name)
    else:
        config_json = component_path(
            kind,
            str(config_name) + ".json",
            roots=app_component_roots("signal"),
        )
    with open(config_json) as f:
        config = json.load(f)
    config.setdefault("name", config_json.stem)
    return config


def load_signal_experiment(name_or_path=None):
    experiment = _load_app_component(
        "signal_experiment",
        name_or_path or DEFAULT_EXPERIMENT,
    )
    experiment.setdefault("output_label", experiment["name"])
    return experiment


def load_signal_source(name_or_path=None):
    return _load_app_component("source", name_or_path or DEFAULT_SOURCE)


def compose_g4_config(experiment, source):
    g4_config = copy.deepcopy(experiment["g4"])
    g4_config.update(source)
    for metadata_key in ("name", "kind", "description"):
        g4_config.pop(metadata_key, None)
    return g4_config


def apply_signal_experiment(my_d, kwargs):
    experiment = load_signal_experiment(kwargs.get("experiment"))
    source = load_signal_source(kwargs.get("source"))
    g4_config = compose_g4_config(experiment, source)

    my_d.g4experiment = experiment["name"]
    my_d.g4_config = g4_config
    my_d.amplifier = kwargs.get("amplifier") or experiment.get("amplifier")
    my_d.daq = experiment.get("daq") or my_d.daq
    my_d.signal_experiment = experiment["name"]
    my_d.signal_source = source["name"]
    my_d.signal_output_label = experiment["output_label"]

    missing = [
        name
        for name in ("amplifier",)
        if getattr(my_d, name) is None
    ]
    if missing:
        raise ValueError(
            "Signal experiment is missing required setting(s): "
            + ", ".join(missing)
        )

    return experiment, source
