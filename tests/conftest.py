from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest


os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/fucx/matplotlib")

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


@pytest.fixture
def device_project(tmp_path: Path) -> Path:
    project = tmp_path / "TestPad"
    project.mkdir()
    definition = {
        "det_name": "TestPad",
        "det_model": "planar",
        "material": "Si",
        "l_x": 100.0,
        "l_y": 80.0,
        "l_z": 50.0,
        "bias": {"electrode": "readout", "voltage": -200.0},
        "temperature": 293.0,
        "irradiation": {"fluence": 0.0, "unit": "cm^-2"},
        "field": {
            "source": "devsim",
            "dimension": 2,
            "mesh": {"maximum_spacing_um": 2.0},
        },
        "runtime_bounds": {
            "x": [0.0, 100.0],
            "y": [0.0, 80.0],
            "z": [0.0, 50.0],
        },
        "read_out_contact": [{"name": "readout"}],
        "capacitance_pF": 2.5,
        "geant4": {
            "envelope_um": [140.0, 120.0, 70.0],
            "sensitive_volumes": ["sensor_bulk"],
            "detector_mapping": {"translation_um": [20.0, 20.0, 10.0]},
        },
    }
    (project / "device.json").write_text(
        json.dumps(definition, indent=2) + "\n",
        encoding="utf-8",
    )
    return project
