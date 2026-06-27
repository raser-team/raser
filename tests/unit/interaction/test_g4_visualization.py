from types import SimpleNamespace

import pytest

from raser.supports.paths import PACKAGE_ROOT


def test_reuses_existing_geant4_vis_manager(monkeypatch):
    from raser.core.interaction import interaction

    existing = object()
    calls = []

    fake_g4b = SimpleNamespace(
        cppyy=SimpleNamespace(
            gbl=SimpleNamespace(
                G4VVisManager=SimpleNamespace(
                    GetConcreteInstance=lambda: existing,
                )
            )
        ),
        G4VisExecutive=lambda: calls.append("created"),
    )

    monkeypatch.setattr(interaction, "g4b", fake_g4b)

    assert interaction._get_or_create_vis_manager() is existing
    assert calls == []


def test_creates_geant4_vis_manager_when_missing(monkeypatch):
    from raser.core.interaction import interaction

    calls = []

    class VisManager:
        def Initialize(self):
            calls.append("initialized")

    fake_g4b = SimpleNamespace(
        cppyy=SimpleNamespace(
            gbl=SimpleNamespace(
                G4VVisManager=SimpleNamespace(
                    GetConcreteInstance=lambda: None,
                )
            )
        ),
        G4VisExecutive=VisManager,
    )

    monkeypatch.setattr(interaction, "g4b", fake_g4b)

    assert isinstance(interaction._get_or_create_vis_manager(), VisManager)
    assert calls == ["initialized"]


def test_signal_init_vis_macro_has_no_relative_macro_include():
    init_vis = PACKAGE_ROOT / "apps" / "signal" / "components" / "g4macro" / "init_vis.mac"

    assert "/control/execute vis.mac" not in init_vis.read_text()


def test_signal_vis_macro_does_not_force_opengl_driver():
    vis_mac = PACKAGE_ROOT / "apps" / "signal" / "components" / "g4macro" / "vis.mac"

    assert "/vis/open OGL" not in vis_mac.read_text()


def test_geant4_visualization_driver_must_be_explicit(monkeypatch):
    from raser.core.interaction import interaction

    monkeypatch.delenv("G4VIS_DEFAULT_DRIVER", raising=False)

    with pytest.raises(ValueError, match="driver must be explicit"):
        interaction._resolve_vis_driver({})


def test_geant4_visualization_driver_uses_config_before_environment(monkeypatch):
    from raser.core.interaction import interaction

    monkeypatch.setenv("G4VIS_DEFAULT_DRIVER", "MPLJupyter")

    assert interaction._resolve_vis_driver({"g4_vis_driver": "HepRepFile"}) == "HepRepFile"


def test_geant4_file_visualization_driver_does_not_need_ui_session():
    from raser.core.interaction import interaction

    assert not interaction._vis_driver_needs_ui_session("HepRepFile")
    assert not interaction._vis_driver_needs_ui_session("VRML2FILE")
    assert interaction._vis_driver_needs_ui_session("OGL")
