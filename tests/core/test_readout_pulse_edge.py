import json

import numpy as np
import pytest

from raser.core.device.build_device import Detector
from raser.core.device.build_device import device_file
from raser.core.readout.circuit import named_chain
from raser.core.readout.pulse_edge import chain_sign
from raser.core.readout.pulse_edge import pulse_edges
from raser.core.readout.waveforms import EventWaveforms
from raser.core.readout.waveforms import append_waveforms
from raser.core.readout.waveforms import read_waveforms

LOAD = {
    "ports": {"in": "a"},
    "elements": {"R1": {"between": ["a", "0"], "ohm": 50.0}},
}
WIRE = {
    "ports": {"in": "a", "out": "b"},
    "elements": {"R1": {"between": ["a", "b"], "ohm": 1e-6}},
}
# 50 Ohm at the input, ten times its voltage turned over at the output
INVERTING = {
    "ports": {"in": "a", "out": "b"},
    "elements": {
        "R1": {"between": ["a", "0"], "ohm": 50.0},
        "E1": {"between": ["b", "0"], "follows": ["a", "0"], "gain": -10.0},
    },
}


def _device(name):
    return Detector(name, json.loads(device_file(name).read_text(encoding="utf-8")))


@pytest.mark.ngspice
@pytest.mark.parametrize(
    "name, edge",
    [
        # as the reconstruction line measured them in full runs, 2026-11-18
        ("HPK-Si-PiN", "falling"),
        ("HPK-Si-LGAD", "falling"),
        ("DJLGAD_Ayyoub_Table1_1D", "falling"),
        ("ITk-md8", "falling"),
        ("NJU-PiN", "rising"),
        ("NJU-PiN-bmos", "rising"),
        ("SICAR-1-PiN", "rising"),
        ("SICAR-1", "rising"),
        ("iLGAD", "rising"),
    ],
)
def test_pulse_of_a_device_goes_the_way_its_bias_and_the_default_chain_make_it(
    name, edge
):
    chain = named_chain("SantaCruz+Gali52+Termination50")

    assert pulse_edges(_device(name), chain, ["top"]) == [edge]


@pytest.mark.ngspice
def test_an_inverting_stage_turns_the_pulse_over():
    plain = {"stages": {"wire": WIRE}, "load": LOAD}
    inverted = {"stages": {"inverting": INVERTING}, "load": LOAD}

    assert chain_sign(plain) == 1
    assert chain_sign(inverted) == -1
    # HPK-Si-PiN collects electrons: down through the wire, up when inverted
    assert pulse_edges(_device("HPK-Si-PiN"), plain, ["a", "b"]) == ["falling"] * 2
    assert pulse_edges(_device("HPK-Si-PiN"), inverted, ["a"]) == ["rising"]


def test_pulse_edge_of_each_electrode_is_kept_in_the_file(tmp_path):
    record = EventWaveforms(0, 0.0, np.zeros((2, 3)))

    append_waveforms(
        tmp_path / "a.h5", ["left", "right"], 1e-12, record, pulse_edge=["rising"] * 2
    )
    append_waveforms(tmp_path / "b.h5", ["left", "right"], 1e-12, record)

    assert read_waveforms(tmp_path / "a.h5").pulse_edge == ["rising", "rising"]
    assert read_waveforms(tmp_path / "b.h5").pulse_edge is None
    with pytest.raises(ValueError, match="pulse_edge"):
        append_waveforms(
            tmp_path / "c.h5", ["left", "right"], 1e-12, record, pulse_edge=["up", "up"]
        )
