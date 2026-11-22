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


@pytest.mark.ngspice
def test_each_electrode_read_out_has_the_pulse_of_the_charge_it_collects():
    # both electrodes of HPK-Si-PiN read out, the top on +200 V: the top
    # collects electrons, the back holes
    content = json.loads(device_file("HPK-Si-PiN").read_text(encoding="utf-8"))
    content.update(
        {
            "electrodes": "strip",
            "read_ele_num": 2,
            "p_x": 1300,
            "read_out_contact": [{"name": "bot"}, {"name": "top"}],
        }
    )
    both = Detector("HPK-Si-PiN", content)
    plain = {"stages": {"wire": WIRE}, "load": LOAD}

    assert pulse_edges(both, plain, ["bot", "top"]) == ["rising", "falling"]


@pytest.mark.ngspice
def test_way_of_a_chain_is_its_swing_from_where_its_output_rests():
    # the inverting stage with its output lifted by 1 V: the pulse dips from
    # +1 V and stays above zero
    lifted = {
        "ports": {"in": "a", "out": "c"},
        "elements": {
            "R1": {"between": ["a", "0"], "ohm": 50.0},
            "E1": {"between": ["b", "0"], "follows": ["a", "0"], "gain": -10.0},
            "V1": {"between": ["c", "b"], "volt": 1.0},
        },
    }
    # the input on 50 Ohm, the output on its own 50 Ohm: nothing passes
    dead = {
        "ports": {"in": "a", "out": "b"},
        "elements": {
            "R1": {"between": ["a", "0"], "ohm": 50.0},
            "R2": {"between": ["b", "0"], "ohm": 50.0},
        },
    }

    assert chain_sign({"stages": {"lifted": lifted}, "load": LOAD}) == -1
    with pytest.raises(ValueError, match="does not answer"):
        chain_sign({"stages": {"dead": dead}, "load": LOAD})


def test_pulse_edge_of_each_electrode_is_kept_in_the_file(tmp_path):
    record = EventWaveforms(0, 0.0, np.zeros((2, 3)))

    append_waveforms(
        tmp_path / "a.h5",
        ["left", "right"],
        1e-12,
        3e-12,
        record,
        pulse_edge=["rising", "falling"],
    )
    append_waveforms(tmp_path / "b.h5", ["left", "right"], 1e-12, 3e-12, record)

    assert read_waveforms(tmp_path / "a.h5").pulse_edge == ["rising", "falling"]
    with pytest.raises(ValueError, match="run the readout again"):
        read_waveforms(tmp_path / "b.h5")
    with pytest.raises(ValueError, match="pulse_edge"):
        append_waveforms(
            tmp_path / "c.h5",
            ["left", "right"],
            1e-12,
            3e-12,
            record,
            pulse_edge=["up", "up"],
        )
