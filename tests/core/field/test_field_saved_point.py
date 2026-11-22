from __future__ import annotations

import devsim
import pytest

from raser.core.field.saved_point import load_point
from raser.core.field.saved_point import save_point

pytestmark = pytest.mark.devsim


def _bar(device: str) -> None:
    devsim.create_1d_mesh(mesh=device)
    devsim.add_1d_mesh_line(mesh=device, pos=0.0, ps=0.1, tag="left")
    devsim.add_1d_mesh_line(mesh=device, pos=1.0, ps=0.1, tag="right")
    devsim.add_1d_contact(mesh=device, name="left", tag="left", material="metal")
    devsim.add_1d_contact(mesh=device, name="right", tag="right", material="metal")
    devsim.add_1d_region(mesh=device, material="Silicon", region="bar", tag1="left", tag2="right")
    devsim.finalize_mesh(mesh=device)
    devsim.create_device(mesh=device, device=device)


def test_a_saved_point_read_back_evaluates_a_model_on_the_parameters_it_was_saved_with(
    tmp_path,
) -> None:
    _bar("saved")
    # a model on a parameter of each kind, none of which create_parameter knows
    devsim.set_parameter(name="of_everything", value=2.0)
    devsim.set_parameter(device="saved", name="of_the_device", value=3.0)
    devsim.set_parameter(device="saved", region="bar", name="of_the_region", value=5.0)
    devsim.node_model(
        device="saved", region="bar", name="product", equation="of_everything*of_the_device*of_the_region"
    )
    save_point("saved", tmp_path / "1.0V.devsim")

    # devsim forgets the device and its parameters; the global one is left at another value
    devsim.delete_device(device="saved")
    devsim.delete_mesh(mesh="saved")
    devsim.set_parameter(name="of_everything", value=7.0)
    load_point("saved", tmp_path / "1.0V.devsim")

    values = devsim.get_node_model_values(device="saved", region="bar", name="product")
    assert values == pytest.approx([30.0] * len(values), rel=1e-12, abs=0)


def test_a_point_saved_without_its_parameters_is_an_error_that_says_to_solve_again(tmp_path) -> None:
    _bar("bare")
    devsim.write_devices(file=str(tmp_path / "1.0V.devsim"), type="devsim")

    devsim.delete_device(device="bare")
    devsim.delete_mesh(mesh="bare")
    with pytest.raises(FileNotFoundError, match=r"1\.0V\.parameters\.json.*solved again"):
        load_point("bare", tmp_path / "1.0V.devsim")
