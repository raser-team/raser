import importlib
from types import SimpleNamespace

import pytest

from raser.cli import raser


@pytest.mark.parametrize(
    ("argv", "expected_import", "expected_function"),
    [
        (["bmos", "HPK-Si-PiN", "GetSignal"], (".apps.bmos.get_signal", "raser"), "get_signal"),
        (["cce", "run", "HPK-Si-PiN"], (".apps.cce", "raser"), "run"),
        (
            ["cce", "run", "HPK-Si-PiN", "beam/proton"],
            (".apps.cce", "raser"),
            "run",
        ),
        (["dev", "analog", "readout", "amp"], (".core.analog", "raser"), "readout"),
        (["dev", "control", "regincr_sim"], (".core.control.regincr_sim", "raser"), "main"),
        (["dev", "current", "model"], (".core.current.model", "raser"), "main"),
        (["dev", "digital", "regincr"], (".core.digital.regincr", "raser"), "main"),
        (["field", "solve", "HPK-Si-PiN"], (".apps.field", "raser"), "solve"),
        (["field", "import", "/tmp/HPK-Si-PiN/200V.tdr"], (".apps.field", "raser"), "import_field"),
        (["field", "weight", "200", "top", "HPK-Si-PiN"], (".apps.field", "raser"), "weight"),
        (["dev", "field", "HPK-Si-PiN"], (".apps.field", "raser"), "main"),
        (
            ["dev", "interaction", "energy_deposit"],
            (".core.interaction.g4_sic_energy_deposition", "raser"),
            "main",
        ),
        (["dev", "metrics", "HPK-Si-PiN"], (".core.metrics", "raser"), "main"),
        (["lumi", "pe_dis"], (".apps.lumi.data_file", "raser"), "main"),
        (["signal", "HPK-Si-PiN"], (".apps.signal", "raser"), "run_signal"),
        (["timeres", "run", "HPK-Si-PiN"], (".apps.timeres", "raser"), "run"),
        (
            ["timeres", "run", "HPK-Si-PiN", "beam/muon"],
            (".apps.timeres", "raser"),
            "run",
        ),
        (["timeres", "analyze", "HPK-Si-PiN"], (".apps.timeres", "raser"), "analyze"),
        (["tct", "signal", "HPK-Si-PiN", "red"], (".apps.tct", "raser"), "run_signal"),
        (["telescope", "taichu_v1"], (".apps.telescope.telescope_signal", "raser"), "main"),
    ],
)
def test_cli_routes_subcommands_to_concrete_entries(monkeypatch, argv, expected_import, expected_function):
    imported = []
    called = []

    def recorder(name):
        def record(*args, **kwargs):
            called.append((name, args, kwargs))

        return record

    def fake_import_module(name, package=None):
        imported.append((name, package))
        return SimpleNamespace(
            batch_signal=recorder("batch_signal"),
            analyze=recorder("analyze"),
            derive_weight=recorder("derive_weight"),
            get_signal=recorder("get_signal"),
            import_field=recorder("import_field"),
            main=recorder("main"),
            readout=recorder("readout"),
            run=recorder("run"),
            solve=recorder("solve"),
            run_metrics=recorder("run_metrics"),
            run_position_signal=recorder("run_position_signal"),
            run_signal=recorder("run_signal"),
            taichu_v2=recorder("taichu_v2"),
            trans=recorder("trans"),
            weight=recorder("weight"),
        )

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    assert raser.main(argv) == 0

    assert imported == [expected_import]
    assert len(called) == 1
    assert called[0][0] == expected_function


def test_bmos_requires_sensor_before_command(monkeypatch):
    called = []

    def fake_import_module(name, package=None):
        return SimpleNamespace(get_signal=lambda sensor: called.append(sensor))

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    assert raser.main(["bmos", "HPK-Si-PiN", "GetSignal"]) == 0

    assert called == ["HPK-Si-PiN"]


def test_bmos_rejects_legacy_command_without_sensor():
    with pytest.raises(SystemExit) as excinfo:
        raser.main(["bmos", "GetSignal"])

    assert excinfo.value.code == 2


def test_cce_run_leaves_default_source_to_run_config(monkeypatch):
    called = []

    def fake_import_module(name, package=None):
        return SimpleNamespace(run=lambda kwargs: called.append(kwargs.copy()))

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    assert raser.main(["cce", "run", "HPK-Si-PiN"]) == 0

    assert called[0]["det_name"] == "HPK-Si-PiN"
    assert called[0]["source"] is None


def test_timeres_run_leaves_default_source_to_run_config(monkeypatch):
    called = []

    def fake_import_module(name, package=None):
        return SimpleNamespace(run=lambda kwargs: called.append(kwargs.copy()))

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    assert raser.main(["timeres", "run", "HPK-Si-PiN"]) == 0

    assert called[0]["det_name"] == "HPK-Si-PiN"
    assert called[0]["source"] is None
    assert called[0]["step"] == "run"


def test_cli_without_subcommand_prints_help(capsys):
    assert raser.main([]) == 1
    assert "sub-command help" in capsys.readouterr().out


@pytest.mark.parametrize("command", ["resolution", "time_resolution"])
def test_cli_does_not_keep_split_metric_commands(command):
    with pytest.raises(SystemExit) as excinfo:
        raser.main([command, "HPK-Si-PiN"])

    assert excinfo.value.code == 2


@pytest.mark.parametrize("command", ["analog", "current", "digital", "metrics"])
def test_core_commands_are_not_public_top_level_commands(command):
    with pytest.raises(SystemExit) as excinfo:
        raser.main([command, "HPK-Si-PiN"])

    assert excinfo.value.code == 2
