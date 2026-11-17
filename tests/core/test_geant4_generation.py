import json

import pytest

from raser.supports.paths import component_path

pytestmark = pytest.mark.geant4


def test_geant4_generates_until_enough_events_are_recorded() -> None:
    from raser.core.device.build_device import Detector
    from raser.core.deposit.simulate_deposits import simulate_deposits

    source = json.loads(component_path("source", "decay", "Sr90.json").read_text())
    # about one Sr-90 decay in thirty leaves energy in the device alone
    deposits = simulate_deposits(Detector("HPK-Si-PiN"), source, None, 5, 3, generated_limit=5000)

    assert len(deposits.events) == 5
    assert 5 < deposits.generated_events < 5000
    # the run stopped at the event that made the fifth: nothing generated after it
    assert deposits.events[-1].event == deposits.generated_events - 1
