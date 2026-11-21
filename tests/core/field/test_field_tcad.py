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


@pytest.mark.devsim
def test_the_weighting_potential_falls_across_the_dielectric_and_is_flat_in_a_conductor() -> (
    None
):
    """A bar 10 long between two electrodes whose last 4 conduct: the weighting
    potential of the first electrode falls from 1 to 0 over the first 6."""
    import devsim

    from raser.core.field.tcad import set_up_weighting
    from raser.core.field.tcad import solve_weighting

    devsim.create_1d_mesh(mesh="bar")
    devsim.add_1d_mesh_line(mesh="bar", pos=0.0, ps=1.0, tag="top")
    devsim.add_1d_mesh_line(mesh="bar", pos=10.0, ps=1.0, tag="bottom")
    devsim.add_1d_contact(mesh="bar", name="top", tag="top", material="metal")
    devsim.add_1d_contact(mesh="bar", name="bottom", tag="bottom", material="metal")
    devsim.add_1d_region(mesh="bar", material="Silicon", region="bulk", tag1="top", tag2="bottom")
    devsim.finalize_mesh(mesh="bar")
    devsim.create_device(mesh="bar", device="bar")
    try:
        x = np.array(devsim.get_node_model_values(device="bar", region="bulk", name="x"))
        held_by = set_up_weighting("bar", 1, {"bulk": (x >= 6.0).astype(float)})

        solve_weighting("bar", held_by, "top")
        of_top = np.array(devsim.get_node_model_values(device="bar", region="bulk", name="Potential"))
        solve_weighting("bar", held_by, "bottom")
        of_bottom = np.array(
            devsim.get_node_model_values(device="bar", region="bulk", name="Potential")
        )
    finally:
        devsim.reset_devsim()

    assert of_top == pytest.approx(np.clip(1 - x / 6.0, 0, 1), abs=1e-6)
    assert of_bottom == pytest.approx(np.clip(x / 6.0, 0, 1), abs=1e-6)
