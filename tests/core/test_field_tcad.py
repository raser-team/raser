from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
import pytest

from raser.core.field.tcad import bias_of


def _tdr(path: Path, voltages: dict[str, float]) -> Path:
    """A TDR file that holds only its electrodes and the voltage on each."""
    with h5py.File(path, "w") as target:
        geometry = target.create_group("collection").create_group("geometry_0")
        state = geometry.create_group("state_0")
        bulk = state.create_group("dataset_0")  # a node quantity, among the voltages
        bulk.attrs["name"] = np.bytes_("ElectrostaticPotential")
        bulk.attrs["region"] = 0
        for index, (name, voltage) in enumerate(voltages.items(), start=1):
            geometry.create_group(f"region_{index}").attrs["name"] = np.bytes_(name)
            dataset = state.create_group(f"dataset_{index}")
            dataset.attrs["name"] = np.bytes_("ContactExternalVoltage")
            dataset.attrs["region"] = index
            dataset.create_dataset("values", data=np.array([voltage]))
    return path


def test_the_bias_of_a_tcad_file_is_the_voltage_on_the_biased_electrode(
    tmp_path: Path,
) -> None:
    tdr = _tdr(tmp_path / "solved.tdr", {"anode": 0.0, "cathode": -200.0, "guard": -50.0})

    assert bias_of(tdr, "cathode") == -200.0
    assert bias_of(tdr, "cathode", asked=-200) == -200.0


def test_a_tcad_file_is_refused_at_another_bias_or_without_the_biased_electrode(
    tmp_path: Path,
) -> None:
    tdr = _tdr(tmp_path / "solved.tdr", {"anode": 0.0, "cathode": -200.0})

    with pytest.raises(ValueError, match=r"-200\.0 V on cathode, not at -500"):
        bias_of(tdr, "cathode", asked=-500)
    with pytest.raises(ValueError, match=r"no electrode center.*anode.*cathode"):
        bias_of(tdr, "center")


def test_a_tcad_file_without_electrode_voltages_takes_the_bias_of_the_command(
    tmp_path: Path,
) -> None:
    tdr = _tdr(tmp_path / "solved.tdr", {})

    assert bias_of(tdr, "cathode", asked=-500) == -500.0
    with pytest.raises(ValueError, match="give its bias with -bias"):
        bias_of(tdr, "cathode")
