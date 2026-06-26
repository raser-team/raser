import importlib
from types import SimpleNamespace

import pytest

from raser.cli import raser


@pytest.mark.parametrize(
    ("argv", "expected_import"),
    [
        (["afe", "readout", "amp"], (".core.afe", "raser")),
        (["bmos", "HPK-Si-PiN", "GetSignal"], (".apps.bmos", "raser")),
        (["cce", "HPK-Si-PiN"], (".apps.cce", "raser")),
        (
            ["cce", "HPK-Si-PiN", "beam/proton"],
            (".apps.cce", "raser"),
        ),
        (["current", "model"], (".core.current", "raser")),
        (["dfe", "regincr"], (".core.dfe", "raser")),
        (["field", "HPK-Si-PiN"], (".core.field", "raser")),
        (["interaction", "energy_deposit"], (".core.interaction", "raser")),
        (["lumi", "pe_dis"], (".apps.lumi", "raser")),
        (["mcu", "regincr_sim"], (".core.mcu", "raser")),
        (["metrics", "HPK-Si-PiN"], (".core.metrics", "raser")),
        (["timeres", "HPK-Si-PiN"], (".apps.timeres", "raser")),
        (
            ["timeres", "HPK-Si-PiN", "beam/muon"],
            (".apps.timeres", "raser"),
        ),
        (["tct", "signal", "HPK-Si-PiN", "red"], (".apps.tct", "raser")),
        (["telescope", "taichu_v1"], (".apps.telescope", "raser")),
    ],
)
def test_cli_routes_subcommands_to_package_modules(monkeypatch, argv, expected_import):
    imported = []
    called = []

    def fake_import_module(name, package=None):
        imported.append((name, package))
        return SimpleNamespace(main=lambda kwargs: called.append(kwargs.copy()))

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    assert raser.main(argv) == 0

    assert imported == [expected_import]
    assert len(called) == 1
    assert called[0]["subparser_name"] == argv[0]


def test_bmos_requires_sensor_before_command(monkeypatch):
    called = []

    def fake_import_module(name, package=None):
        return SimpleNamespace(main=lambda kwargs: called.append(kwargs.copy()))

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    assert raser.main(["bmos", "HPK-Si-PiN", "GetSignal"]) == 0

    assert called[0]["sensor"] == "HPK-Si-PiN"
    assert called[0]["label"] == "GetSignal"


def test_bmos_rejects_legacy_command_without_sensor():
    with pytest.raises(SystemExit) as excinfo:
        raser.main(["bmos", "GetSignal"])

    assert excinfo.value.code == 2


def test_cce_uses_default_am241_source(monkeypatch):
    called = []

    def fake_import_module(name, package=None):
        return SimpleNamespace(main=lambda kwargs: called.append(kwargs.copy()))

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    assert raser.main(["cce", "HPK-Si-PiN"]) == 0

    assert called[0]["det_name"] == "HPK-Si-PiN"
    assert called[0]["source"] == "radioactive/Am241"


def test_timeres_uses_default_sr90_source(monkeypatch):
    called = []

    def fake_import_module(name, package=None):
        return SimpleNamespace(main=lambda kwargs: called.append(kwargs.copy()))

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    assert raser.main(["timeres", "HPK-Si-PiN"]) == 0

    assert called[0]["det_name"] == "HPK-Si-PiN"
    assert called[0]["source"] == "radioactive/Sr90"
    assert called[0]["label"] == "signal"


def test_cli_without_subcommand_prints_help(capsys):
    assert raser.main([]) == 1
    assert "sub-command help" in capsys.readouterr().out


@pytest.mark.parametrize("command", ["resolution", "signal", "time_resolution"])
def test_cli_does_not_keep_split_metric_commands(command):
    with pytest.raises(SystemExit) as excinfo:
        raser.main([command, "HPK-Si-PiN"])

    assert excinfo.value.code == 2
