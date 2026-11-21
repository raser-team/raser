import json

import pytest

from raser.supports.paths import component_path

pytestmark = [pytest.mark.geant4, pytest.mark.slow]


def test_view_geometry_writes_an_offscreen_picture(tmp_path, monkeypatch) -> None:
    from raser.core.device.build_device import Detector
    from raser.core.deposit.view_geometry import view_geometry

    source = json.loads(component_path("source", "decay", "Sr90.json").read_text())
    picture = tmp_path / "g4_geometry"
    monkeypatch.chdir(tmp_path)
    # TSG_OFFSCREEN is one of Geant4's own drivers, which g4ppyy does not
    # register: the picture exists only when RASER registers them
    view_geometry(
        Detector("HPK-Si-PiN"), source, None, 1, 3, "TSG_OFFSCREEN", str(picture)
    )

    written = tmp_path / "g4_geometry.png"
    assert written.is_file()
    assert written.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert written.stat().st_size > 1000
    # the one picture asked for, and no other file of the driver in the
    # working directory
    assert sorted(p.name for p in tmp_path.iterdir()) == ["g4_geometry.png"]
