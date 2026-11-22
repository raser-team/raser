import json

import h5py
import pytest

from raser.core import seeding
from raser.lifecycle.slices import Ended
from raser.stages.deposit import deposits
from raser.supports.paths import component_path

# a straight track in HPK-Si-PiN: about half of them lose more than 0.0185 MeV
SOURCE = {"kind": "toy_mip", "landau_sampling": True}


def _options(tmp_path, **counts):
    device = json.loads(component_path("device", "HPK-Si-PiN.json").read_text())
    return {
        "det_name": "HPK-Si-PiN",
        "_files": {"source": SOURCE, "device": device},
        "_node_paths": {"deposit": str(tmp_path)},
        "seed": 1,
        "fano": False,
        "edep_min": 0.0185,
        **counts,
    }


def _attributes(tmp_path):
    with h5py.File(tmp_path / "deposit.h5") as file:
        return int(file.attrs["generated_events"]), int(file.attrs["recorded_events"])


def test_events_per_job_records_that_many(tmp_path) -> None:
    seeding.seed_generators(1)
    deposits(_options(tmp_path, events_per_job=5))
    generated, recorded = _attributes(tmp_path)
    assert recorded == 5 and generated > 5


def test_generated_per_job_generates_that_many(tmp_path) -> None:
    seeding.seed_generators(1)
    deposits(_options(tmp_path, generated_per_job=20))
    generated, recorded = _attributes(tmp_path)
    assert generated == 20 and 0 < recorded < 20


def test_generated_limit_bounds_the_generation(tmp_path) -> None:
    options = _options(tmp_path, events_per_job=5, generated_limit=30, edep_min=100.0)
    with pytest.raises(RuntimeError, match="limit of 30"):
        deposits(options)


def test_one_count_and_only_one(tmp_path) -> None:
    with pytest.raises(ValueError, match="exactly one"):
        deposits(_options(tmp_path, events_per_job=5, generated_per_job=20))
    with pytest.raises(ValueError, match="exactly one"):
        deposits(_options(tmp_path))
    # a job that recorded nothing ends after writing its file
    with pytest.raises(Ended):
        deposits(_options(tmp_path, generated_per_job=1, edep_min=100.0))
