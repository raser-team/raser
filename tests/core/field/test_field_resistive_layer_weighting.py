from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from raser.core.device.build_device import device_file
from raser.core.field.devsim_field import DevsimField

pytestmark = pytest.mark.devsim

BIAS = 200.0


def _device() -> dict:
    """A planar slab with a resistive layer on its top contact: an n+ top of 1 um,
    49 um of 5e11 /cm3 acceptors, a p+ back; three RC nodes listed as one electrode.
    At 200 V it depletes 72 um, so the 49 um are depleted."""
    content = json.loads(device_file("HPK-Si-PiN").read_text(encoding="utf-8"))
    content["doping"]["Acceptors"] = (
        "5e11*(step((50e-4)-x)-step(1e-4-x)) + 1.0e18*(step((151e-4)-x)-step((50e-4)-x))"
    )
    content["electrodes"] = "strip"
    content["read_ele_num"] = 3
    content["p_x"] = 1300.0 / 3
    content["resistive_layer"] = {"sheet_resistance": 630.0, "contact": "top"}
    return content


def _kwargs(folder: Path, wf: bool) -> dict:
    return {
        "target": "HPK-Si-PiN", "cv": False, "wf": wf, "noise": False, "irradiation_flux": None,
        "bias": BIAS, "_files": {"device": _device()}, "_field_directory": folder,
    }  # fmt: skip


def test_the_weighting_potential_of_a_resistive_layer_is_the_one_of_a_plane_electrode(
    tmp_path: Path,
) -> None:
    from raser.core.field import solver_section

    try:
        solver_section.main(_kwargs(tmp_path, wf=False))
        solver_section._empty_devsim()
        solver_section.main(_kwargs(tmp_path, wf=True))
    finally:
        solver_section._empty_devsim()

    stored = tmp_path / "weightingfield" / "top"
    assert list(stored.glob("Potential_*V.pkl"))
    assert not (tmp_path / "weightingfield" / "node").exists()
    field = DevsimField(
        "HPK-Si-PiN", BIAS, [{"name": "top"}],
        bounds={"x": (0, 1300.0), "y": (0, 1300.0), "z": (0, 50.0)}, field_directory=tmp_path,
    )  # fmt: skip
    # from the n+ layer at 1 um to the p+ back at 50 um the potential falls from 1 to 0 along a line
    depths = np.linspace(3.0, 48.0, 10)
    along = np.array([field.get_w_p(650.0, 650.0, z, 0) for z in depths])
    assert np.abs(along - (1.0 - (depths - 1.0) / 49.0)).max() <= 0.02
