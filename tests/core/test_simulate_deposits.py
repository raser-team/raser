import pytest

from raser.core.interaction.simulate_deposits import simulate_deposits
from raser.core.interaction.simulate_deposits import g4_configuration

SOURCE = {
    "name": "pion",
    "kind": "beam",
    "par_type": "pi-",
    "par_energy": 1000.0,
    "par_in": [0, 0, 1000],
    "par_out": [0, 0, -1000],
}
G4SETUP = {
    "name": "time_resolution",
    "geant4_model": "time_resolution",
    "total_events": 10000,
    "edep_min": 9.0,
    "object": {"elemental": {}},
    "world": "G4_Galactic",
    "maxstep": 2,
    "g4_vis": False,
    "par_energy": 5.0,
}


def test_experiment_overrides_source_overrides_g4setup() -> None:
    configuration = g4_configuration(SOURCE, G4SETUP, 3, None, 0.1)

    # of the experiment, whatever the files say
    assert configuration["total_events"] == 3
    assert configuration["edep_min"] is None
    assert configuration["edep_max"] == 0.1
    # the particle is of the source
    assert configuration["par_energy"] == 1000.0
    # the surroundings are of the g4setup; the names of the files are gone
    assert configuration["geant4_model"] == "time_resolution"
    assert configuration["object"] == {"elemental": {}}
    assert "name" not in configuration and "kind" not in configuration


def test_source_that_geant4_does_not_simulate_is_refused() -> None:
    with pytest.raises(ValueError, match="toy_mip"):
        simulate_deposits(None, {"kind": "toy_mip"}, None, 1, 0)
