import numpy as np
import pytest

from raser.core.field.device_circuit import planar_circuit
from raser.core.readout.spice import output_noise_spectrum
from raser.core.readout.spice import solve
from raser.supports.dependency import MissingDependency

LOAD = {
    "ports": {"in": "a"},
    "elements": {"R1": {"between": ["a", "0"], "ohm": 50.0}},
}


@pytest.mark.parametrize("analysis", ["transient", "noise"])
def test_without_ngspice_the_readout_says_how_to_get_it(monkeypatch, analysis):
    monkeypatch.setattr("raser.core.readout.spice.shutil.which", lambda _: None)
    chain = {"stages": {}, "load": LOAD}
    circuit = planar_circuit("top", 1e-12)

    with pytest.raises(MissingDependency, match="ngspice is not installed.*Install"):
        if analysis == "transient":
            solve(chain, ["top"], 5e-12, [np.zeros(10)], circuit)
        else:
            output_noise_spectrum(chain, circuit, 1e3, 1e9)
