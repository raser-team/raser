from raser.afe.set_pwl_input import set_pwl_input


def test_set_pwl_input_rewrites_current_source_and_output_file(tmp_path):
    pwl_file = tmp_path / "input.pwl"
    cir_file = tmp_path / "amplifier.cir"
    voltage_file = tmp_path / "voltage.out"
    output_folder = tmp_path / "out"
    output_folder.mkdir()

    pwl_file.write_text("0 0\n1e-9 2e-6\n", encoding="utf-8")
    cir_file.write_text(
        "\n".join(
            [
                "* amplifier",
                "I1 2 0 DC 0",
                "R1 2 0 50",
                ".control",
                "wrdata old.out v(out)",
                ".endc",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    set_pwl_input(str(pwl_file), str(cir_file), str(voltage_file), str(output_folder))

    tmp_cir = output_folder / "amplifier_tmp.cir"
    assert tmp_cir.exists()
    assert not (output_folder / "amplifier.cir").exists()

    lines = tmp_cir.read_text(encoding="utf-8").splitlines()
    assert "I1 2 0 PWL(0,0,1e-9,2e-6)" in lines
    assert f"wrdata {voltage_file} v(out)" in lines
    assert "R1 2 0 50" in lines
