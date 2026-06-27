"""Signal experiment and source configuration helpers."""

import copy
import json
from pathlib import Path

from raser.supports.paths import PACKAGE_ROOT
from raser.supports.paths import component_file_path
from raser.supports.paths import component_path
from raser.supports.paths import component_roots


DEFAULT_EXPERIMENT = "charge_collection"
DEFAULT_SOURCE = "decay/Sr90"
APP_EXPERIMENTS = {
    "charge_collection": PACKAGE_ROOT / "apps" / "cce" / "charge_collection.json",
    "time_resolution": PACKAGE_ROOT / "apps" / "timeres" / "time_resolution.json",
}


def _is_explicit_path(value):
    path = Path(value)
    return (
        hasattr(value, "__fspath__")
        or path.is_absolute()
        or (path.parts and path.parts[0] in {".", ".."})
        or path.suffix
    )


def _load_json(config_json):
    with open(config_json) as f:
        config = json.load(f)
    config.setdefault("name", Path(config_json).stem)
    return config


def load_signal_experiment(name_or_path=None):
    config_name = name_or_path or DEFAULT_EXPERIMENT
    if _is_explicit_path(config_name):
        return _load_json(component_file_path("experiment", config_name))
    try:
        return _load_json(APP_EXPERIMENTS[str(config_name)])
    except KeyError as exc:
        raise FileNotFoundError(f"Cannot find RASER app experiment: {config_name}") from exc


def load_signal_source(name_or_path=None):
    config_name = name_or_path or DEFAULT_SOURCE
    if _is_explicit_path(config_name):
        return _load_json(component_file_path("source", config_name))
    try:
        return _load_json(component_path("source", str(config_name) + ".json"))
    except FileNotFoundError:
        matches = []
        for root in component_roots():
            matches.extend(root.joinpath("source").glob(f"*/{config_name}.json"))
        if len(matches) != 1:
            raise
        return _load_json(matches[0])


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
    my_d.signal_output_label = experiment.get("output_label", experiment["name"])

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
