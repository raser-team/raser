from raser.core.interaction.deposits import Deposits
from raser.core.interaction.deposits import EventDeposits
from raser.core.interaction.deposits import read_deposits
from raser.core.interaction.deposits import write_deposits


def test_deposits_file_returns_each_event_with_its_own_deposits(tmp_path) -> None:
    deposits = Deposits(
        generated_events=5,
        edep_min=0.05,
        edep_max=None,
        events=[
            EventDeposits(
                event=1,
                detector=["Device", "Device", "Device"],
                x=[500.0, 500.5, 501.0],
                y=[400.0, 400.0, 400.25],
                z=[300.0, 150.0, 0.0],
                t=[2.35e-12, 2.85e-12, 3.36e-12],
                e=[0.03, 0.04, 0.02],
            ),
            EventDeposits(
                event=4,
                detector=["Device"],
                x=[10.0],
                y=[20.0],
                z=[30.0],
                t=[1.0e-12],
                e=[0.06],
            ),
        ],
    )
    path = tmp_path / "deposits.root"

    write_deposits(path, deposits)

    assert read_deposits(path) == deposits
