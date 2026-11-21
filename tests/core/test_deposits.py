from raser.core.interaction.deposits import Deposits
from raser.core.interaction.deposits import EventDeposits
from raser.core.interaction.deposits import deposits_of_steps
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
                pairs=[8300.0, 11100.0, 5600.0],
            ),
            EventDeposits(
                event=4,
                detector=["Device"],
                x=[10.0],
                y=[20.0],
                z=[30.0],
                t=[1.0e-12],
                e=[0.06],
                pairs=[16700.0],
            ),
        ],
    )
    path = tmp_path / "deposits.h5"

    write_deposits(path, deposits)

    assert read_deposits(path) == deposits


def test_deposits_of_steps_drop_steps_and_events_without_energy() -> None:
    deposits = deposits_of_steps(
        "Device",
        event_numbers=[0, 1, 2],
        positions=[
            [[1.0, 2.0, 30.0], [1.5, 2.5, 20.0], [2.0, 3.0, 10.0]],
            [[0, 0, 0]],
            [[7.0, 8.0, 9.0], [7.5, 8.5, 4.0]],
        ],
        energies=[[0.02, 0.0, 0.03], [0], [0.0, 0.01]],
        times=[[1.0e-12, 1.1e-12, 1.2e-12], [0], [2.0e-12, 2.1e-12]],
        generated_events=3,
        edep_min=None,
        edep_max=0.1,
    )

    assert deposits == Deposits(
        generated_events=3,
        edep_min=None,
        edep_max=0.1,
        events=[
            EventDeposits(
                event=0,
                detector=["Device", "Device"],
                x=[1.0, 2.0],
                y=[2.0, 3.0],
                z=[30.0, 10.0],
                t=[1.0e-12, 1.2e-12],
                e=[0.02, 0.03],
            ),
            EventDeposits(
                event=2,
                detector=["Device"],
                x=[7.5],
                y=[8.5],
                z=[4.0],
                t=[2.1e-12],
                e=[0.01],
            ),
        ],
    )
