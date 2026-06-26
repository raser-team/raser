import pytest


pytestmark = pytest.mark.root


def test_set_tmp_cir_rewrites_pwl_raw_and_noise_lines(tmp_path):
    from raser.core.analog.ngspice import set_tmp_cir

    circuit = tmp_path / "amplifier.cir"
    circuit.write_text(
        "\n".join(
            [
                "I1 2 0 pulse(0 1 0)",
                "wrdata old.raw v(out)",
                "noise v(out) I1 dec 10 1 1e6",
                "setplot noise1",
                "onoise_spectrum",
                "R1 2 0 50",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    tmp_cirs, raws = set_tmp_cir(
        read_ele_num=1,
        path=str(tmp_path),
        input_current_strs=["0,0,1e-9,1e-6"],
        ele_cir=str(circuit),
        label="case",
    )

    assert tmp_cirs == [str(tmp_path / "case_tmp.cir")]
    assert raws == [str(tmp_path / "case.raw")]

    lines = (tmp_path / "case_tmp.cir").read_text(encoding="utf-8").splitlines()
    assert "I1 2 0 PWL(0,0,1e-9,1e-6) " in lines
    assert f"wrdata {tmp_path / 'case.raw'} v(out)" in lines
    assert "* skipped: noise v(out) I1 dec 10 1 1e6" in lines
    assert "* skipped: setplot noise1" in lines
    assert "* skipped: onoise_spectrum" in lines
    assert "R1 2 0 50" in lines
