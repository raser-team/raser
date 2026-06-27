from types import SimpleNamespace

import pytest

from raser.apps.signal.experiments import apply_signal_experiment
from raser.apps.signal.experiments import compose_g4_config
from raser.apps.signal.experiments import load_signal_experiment
from raser.apps.signal.experiments import load_signal_source


def test_default_signal_experiment_is_charge_collection():
    experiment = load_signal_experiment()

    assert experiment["name"] == "charge_collection"
    assert experiment["output_label"] == "cce"
    assert experiment["g4"]["geant4_model"] == "charge_collection"
    assert experiment["amplifier"] == "Broad_Band_UCSC"


def test_default_signal_source_is_sr90():
    source = load_signal_source()

    assert source["name"] == "Sr90"
    assert source["kind"] == "decay_source"
    assert source["par_type"] == "e-"
    assert source["par_energy"] == pytest.approx(2.28)


def test_apply_signal_experiment_populates_detector_runtime_fields():
    detector = SimpleNamespace(g4experiment=None, amplifier=None, daq=None)

    experiment, source = apply_signal_experiment(
        detector,
        {
            "experiment": "charge_collection",
            "source": "decay/Am241",
            "amplifier": None,
        },
    )

    assert experiment["name"] == "charge_collection"
    assert source["name"] == "Am241"
    assert detector.g4experiment == "charge_collection"
    assert detector.g4_config["par_type"] == "alpha"
    assert detector.g4_config["par_energy"] == pytest.approx(5.54)
    assert detector.amplifier == "Broad_Band_UCSC"
    assert detector.daq == "Alibava"
    assert detector.signal_output_label == "cce"
    assert detector.signal_source == "Am241"


def test_time_resolution_with_sr90_composes_beta_source():
    experiment = load_signal_experiment("time_resolution")
    source = load_signal_source("decay/Sr90")

    g4_config = compose_g4_config(experiment, source)

    assert g4_config["geant4_model"] == "time_resolution"
    assert g4_config["par_type"] == "e-"
    assert g4_config["par_energy"] == pytest.approx(2.28)
    assert "kind" not in g4_config


@pytest.mark.parametrize(
    ("source_name", "particle"),
    [
        ("beam/proton", "proton"),
        ("beam/pion", "pi-"),
        ("beam/muon", "mu-"),
        ("beam/electron", "e-"),
    ],
)
def test_builtin_mip_beams_load_as_sources(source_name, particle):
    source = load_signal_source(source_name)

    assert source["kind"] == "beam"
    assert source["par_type"] == particle
    assert source["par_energy"] > 0


def test_abstract_beam_source_can_be_loaded():
    source = load_signal_source("beam/beam")

    assert source["kind"] == "beam"
    assert source["par_type"] == "proton"


def test_apply_signal_experiment_keeps_cli_amplifier_override():
    detector = SimpleNamespace(g4experiment=None, amplifier=None, daq=None)

    apply_signal_experiment(
        detector,
        {
            "experiment": "charge_collection",
            "source": "decay/Am241",
            "amplifier": "custom_amp",
        },
    )

    assert detector.amplifier == "custom_amp"


def test_apply_signal_experiment_reports_missing_required_settings(tmp_path):
    experiment = tmp_path / "minimal.json"
    experiment.write_text(
        '{"name": "minimal", "g4": {"geant4_model": "minimal"}}',
        encoding="utf-8",
    )
    detector = SimpleNamespace(g4experiment=None, amplifier=None, daq=None)

    with pytest.raises(ValueError, match="amplifier"):
        apply_signal_experiment(
            detector,
            {
                "experiment": experiment,
                "source": "decay/Am241",
                "amplifier": None,
            },
        )
