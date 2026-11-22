import math

import numpy as np
import pytest

from raser.core.current.currents import EventCurrents, append_currents
from raser.core.field.device_circuit import planar_circuit
from raser.core.readout.job import write_waveforms
from raser.core.readout.window import post_window
from raser.core.readout.waveforms import read_waveforms

pytestmark = pytest.mark.ngspice

DT_S = 100e-12
# one pole: the 10 pF of the probe on 1 kOhm, a time constant of 10 ns
TAU_S = 1000.0 * 10e-12
POLE = {
    "stages": {
        "wire": {
            "ports": {"in": "a", "out": "b"},
            "elements": {"R1": {"between": ["a", "b"], "ohm": 1e-6}},
        }
    },
    "load": {
        "ports": {"in": "a"},
        "elements": {"R1": {"between": ["a", "0"], "ohm": 1000.0}},
    },
}


def test_chain_settles_in_the_time_its_pole_takes_to_fall_to_a_thousandth():
    settle = post_window(POLE, 10e-12, DT_S, 1e-6)

    # the output of one pole falls as exp(-t / tau) from its peak, to 1e-3 of
    # it at tau ln(1000); the bins place the peak and the last bin beyond the
    # edge within two bins of that
    assert settle == pytest.approx(TAU_S * math.log(1000), abs=2 * DT_S)


def test_post_window_cut_by_its_limit_says_so(capsys):
    limit = 30e-9

    settle = post_window(POLE, 10e-12, DT_S, limit)

    assert settle == limit
    line = capsys.readouterr().out.strip()
    assert line.startswith("INFO: readout: the amplifier chain settles in at least ")
    assert line.endswith("ns; the post-window is 30 ns (readout.max_post_window_ns)")
    # at least what the 30 ns window shows: where it fell to 1e-3 of its peak
    # is beyond the window, so the last time beyond the edge is its end
    least = float(line.split("at least ")[1].split(" ns")[0])
    assert least == pytest.approx(30.0, abs=0.2)


def test_post_window_within_its_limit_prints_nothing(capsys):
    post_window(POLE, 10e-12, DT_S, 1e-6)

    assert capsys.readouterr().out == ""


def test_chain_that_does_not_answer_is_an_error():
    dead = {
        "stages": {},
        "load": {
            "ports": {"in": "a"},
            "elements": {"R1": {"between": ["a", "0"], "ohm": 1e-6}},
        },
    }

    with pytest.raises(ValueError, match="does not answer"):
        post_window(dead, 10e-12, DT_S, 1e-6)


def _write(tmp_path, pre_s, post_s):
    bins = 200
    path = tmp_path / "currents.h5"
    current = np.zeros((1, bins))
    current[0, 20:40] = 1e-6
    append_currents(
        path, ["top"], DT_S, EventCurrents(3, -2e-9, current, np.zeros(1), 0.0)
    )
    out = tmp_path / "waveforms.h5"
    write_waveforms(
        path,
        out,
        POLE,
        planar_circuit("top", 10e-12),
        None,
        None,
        pulse_edge=["rising"],
        pre_window_s=pre_s,
        post_window_s=post_s,
    )
    return bins, read_waveforms(out).events[0]


def test_window_is_lengthened_before_and_after_the_currents(tmp_path):
    bins, plain = _write(tmp_path, 0.0, 0.0)
    # 1.05 ns is 11 bins of 100 ps, 2.31 ns is 24
    _, padded = _write(tmp_path, 1.05e-9, 2.31e-9)

    n_pre, n_post = 11, 24
    assert plain.voltage.shape == (1, bins)
    assert padded.voltage.shape == (1, n_pre + bins + n_post)
    assert padded.t0 == pytest.approx(plain.t0 - n_pre * DT_S, abs=1e-15)
    # the circuit is at rest before the current: the level of the first bin
    # holds, and the current's own bins come out as without the lengthening
    assert padded.voltage[0, :n_pre] == pytest.approx(padded.voltage[0, 0], abs=1e-12)
    assert padded.voltage[0, 0] == pytest.approx(0.0, abs=1e-12)
    assert padded.voltage[0, n_pre : n_pre + bins] == pytest.approx(
        plain.voltage[0], abs=1e-9
    )
    # after the current the output decays on, from where the window ended
    tail = padded.voltage[0, n_pre + bins :]
    assert tail[0] == pytest.approx(
        plain.voltage[0, -1] * math.exp(-DT_S / TAU_S), rel=0.05
    )
    assert np.all(np.diff(tail) < 0)
