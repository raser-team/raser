from raser.core.current.cal_current import deposits_in
from raser.core.interaction.deposits import EventDeposits


def test_the_deposits_of_one_detector_keep_their_own_pairs():
    record = EventDeposits(
        event=7,
        detector=["I_-1_0", "I_0_0", "I_-1_0", "I_0_0", "I_0_0"],
        x=[1.0, 2.0, 3.0, 4.0, 5.0],
        y=[10.0, 20.0, 30.0, 40.0, 50.0],
        z=[100.0, 200.0, 300.0, 400.0, 500.0],
        t=[0.1, 0.2, 0.3, 0.4, 0.5],
        e=[1e-3, 2e-3, 3e-3, 4e-3, 5e-3],
        pairs=[11.0, 22.0, 33.0, 44.0, 55.0],
    )
    one = deposits_in(record, "I_-1_0")
    assert one.event == 7
    assert one.detector == ["I_-1_0", "I_-1_0"]
    assert (one.x, one.y, one.z, one.t, one.e) == (
        [1.0, 3.0],
        [10.0, 30.0],
        [100.0, 300.0],
        [0.1, 0.3],
        [1e-3, 3e-3],
    )
    assert sum(one.pairs) == 44.0
    assert sum(deposits_in(record, "I_0_0").pairs) == 121.0
    assert deposits_in(record, "II_0_0").detector == []
