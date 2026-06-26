import pytest


def test_regincr_basic_sequence():
    pymtl3 = pytest.importorskip("pymtl3")

    from raser.core.mcu.regincr import RegIncr

    model = RegIncr()
    model.apply(pymtl3.DefaultPassGroup(linetrace=True))
    model.sim_reset()

    def tick(input_value, expected_output):
        model.in_ @= input_value
        model.sim_eval_combinational()
        if expected_output is not None:
            assert model.out == expected_output
        model.sim_tick()

    tick(0x00, None)
    tick(0x13, 0x01)
    tick(0x27, 0x14)
    tick(0x00, 0x28)
    tick(0x00, 0x01)
    tick(0x00, 0x01)
