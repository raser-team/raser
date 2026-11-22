from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from raser.lifecycle import nodes


def test_a_whole_float_is_its_int_and_any_other_float_is_kept_to_the_last_bit() -> None:
    assert nodes.node_of({"voltage": 100.0}) == nodes.node_of({"voltage": 100})
    assert nodes.node_of({"x": 0.1 + 0.2}) != nodes.node_of({"x": 0.3})
    assert nodes.node_of({"fano": True}) != nodes.node_of({"fano": 1})
    assert nodes.node_of({"a": 1, "b": 2}) == nodes.node_of({"b": 2, "a": 1})
    assert nodes.node_of({"stages": ["A", "B"]}) != nodes.node_of(
        {"stages": ["B", "A"]}
    )
    with pytest.raises(ValueError, match="not finite"):
        nodes.node_of({"x": float("nan")})


def test_the_name_of_a_point_and_the_axes_after_the_measurement_leave_the_job_seed_as_it_is() -> (
    None
):
    at_100 = nodes.job_seed(1, 0, {"field.voltage": 100})

    assert (
        nodes.job_seed(1, 0, {"field.voltage": 100.0, "readout.amplifier.R1": 499})
        == at_100
    )
    assert (
        nodes.job_seed(1, 0, {"field.voltage": 100, "digitizer.device.full_scale_V": 2})
        == at_100
    )


def test_another_bias_source_job_or_run_seed_is_another_measurement() -> None:
    seeds = {
        nodes.job_seed(1, 0, {"field.voltage": 100}),
        nodes.job_seed(1, 0, {"field.voltage": 200}),
        nodes.job_seed(1, 0, {"field.voltage": 100, "deposit.source": "bunch"}),
        nodes.job_seed(1, 0, {"field.voltage": 100, "current.plots": 0}),
        nodes.job_seed(1, 1, {"field.voltage": 100}),
        nodes.job_seed(2, 0, {"field.voltage": 100}),
    }

    assert len(seeds) == 6
    assert all(1 <= seed <= 2**31 - 1 for seed in seeds)


def test_with_same_seeds_the_jobs_of_one_index_share_their_seed_over_the_points() -> (
    None
):
    assert nodes.job_seed(
        1, 0, {"field.voltage": 100}, same_seeds=True
    ) == nodes.job_seed(1, 0, {"field.voltage": 200}, same_seeds=True)
    assert nodes.job_seed(1, 0, {}, same_seeds=True) != nodes.job_seed(
        1, 1, {}, same_seeds=True
    )


def test_the_stages_of_a_job_draw_from_seeds_of_their_own() -> None:
    assert nodes.stage_seed(7, "readout") != nodes.stage_seed(7, "digitizer")
    assert nodes.stage_seed(7, "readout") != nodes.stage_seed(8, "readout")


def test_a_node_takes_its_name_when_it_is_whole_and_keeps_what_the_stage_noted(
    tmp_path: Path,
) -> None:
    inputs = {
        "settings": {"plots": 0},
        "upstream": {"deposit": "aaaaaaaaaaaa"},
        "seed": 3,
    }
    folder = nodes.node_dir(tmp_path, "current", nodes.node_of(inputs))

    assert nodes.found(folder, inputs) is None
    part = nodes.start(folder, "current", inputs, {"code": "abc", "job": {"index": 0}})
    (part / "current.h5").write_text("data")
    record = nodes.read(part)
    record["solved"] = [100.0]  # a key of the stage itself
    (part / "node.json").write_text(json.dumps(record))

    assert not folder.exists() and nodes.read(part)["state"] == "running"
    assert nodes.finish(part, notes={"events": 5}) == folder
    assert not part.exists() and (folder / "current.h5").read_text() == "data"
    record = nodes.found(folder, inputs)
    assert (record["state"], record["notes"], record["solved"]) == (
        "done",
        {"events": 5},
        [100.0],
    )
    assert (record["stage"], record["code"], record["job"]) == (
        "current",
        "abc",
        {"index": 0},
    )
    assert record["inputs"] == inputs and record["fingerprint"] == nodes.fingerprint(
        inputs
    )


def test_what_an_interrupted_writing_left_is_not_in_the_node_written_after_it(
    tmp_path: Path,
) -> None:
    inputs = {"seed": 1}
    folder = nodes.node_dir(tmp_path, "deposit", nodes.node_of(inputs))
    (nodes.start(folder, "deposit", inputs, {}) / "half.h5").write_text("half")

    assert nodes.found(folder, inputs) is None
    whole = nodes.finish(nodes.start(folder, "deposit", inputs, {}), "ended")

    assert sorted(path.name for path in whole.iterdir()) == ["node.json"]
    assert nodes.read(whole)["state"] == "ended"


def test_a_node_that_read_other_inputs_under_the_same_name_is_refused(
    tmp_path: Path,
) -> None:
    folder = nodes.node_dir(tmp_path, "deposit", "0123456789ab")
    nodes.finish(nodes.start(folder, "deposit", {"seed": 1}, {}))

    with pytest.raises(
        RuntimeError, match="two fingerprints share the name 0123456789ab"
    ):
        nodes.found(folder, {"seed": 2})


def test_the_commit_of_the_code_is_noted_and_does_not_name_a_node(
    tmp_path: Path,
) -> None:
    inputs = {"seed": 1}
    folder = nodes.node_dir(tmp_path, "deposit", nodes.node_of(inputs))
    nodes.finish(nodes.start(folder, "deposit", inputs, {"code": "old"}))
    record = nodes.found(folder, inputs)

    assert nodes.code_differs(record, "old") is None
    assert "written by old, the code is new now" in nodes.code_differs(record, "new")


def test_a_second_process_does_not_write_a_node_that_is_being_written(
    tmp_path: Path,
) -> None:
    folder = nodes.node_dir(tmp_path, "deposit", "0123456789ab")
    held = nodes.lock(folder)

    with pytest.raises(nodes.Running, match="written by another process"):
        nodes.lock(folder)
    held.close()
    nodes.lock(folder).close()


def test_the_view_of_a_point_links_each_job_to_its_node_and_follows_a_new_one(
    tmp_path: Path,
) -> None:
    first = nodes.finish(
        nodes.start(
            nodes.node_dir(tmp_path, "deposit", "a" * 12), "deposit", {"seed": 1}, {}
        )
    )
    other = nodes.finish(
        nodes.start(
            nodes.node_dir(tmp_path, "deposit", "b" * 12), "deposit", {"seed": 2}, {}
        )
    )
    field = nodes.finish(
        nodes.start(
            tmp_path.parent / "field" / ("c" * 12), "field", {"voltage": 100}, {}
        )
    )

    nodes.link_view(tmp_path, "voltage_100", "deposit", first, job=0)
    link = nodes.link_view(tmp_path, "voltage_100", "deposit", first, job=1)
    nodes.link_view(tmp_path, "voltage_100", "deposit", other, job=1)
    nodes.link_view(tmp_path, "voltage_100", "field", field)

    view = tmp_path / "points" / "voltage_100"
    assert (view / "deposit" / "0").resolve() == first.resolve()
    assert link == view / "deposit" / "1" and link.resolve() == other.resolve()
    assert not os.path.isabs(os.readlink(link))
    assert (view / "field").is_symlink() and (
        view / "field"
    ).resolve() == field.resolve()
    with pytest.raises(FileNotFoundError, match="no node to link"):
        nodes.link_view(
            tmp_path,
            "voltage_100",
            "deposit",
            tmp_path / "nodes" / "deposit" / "missing",
            job=2,
        )
    (view / "current").mkdir()
    with pytest.raises(FileExistsError, match="holds only links"):
        nodes.link_view(tmp_path, "voltage_100", "current", first)


def test_the_table_of_points_holds_the_values_and_the_nodes_of_every_job(
    tmp_path: Path,
) -> None:
    rows = {
        "voltage_100": {
            "values": {"field.voltage": 100.0},
            "nodes": {"field": "c" * 12, "deposit": ["a" * 12, "b" * 12]},
        }
    }

    path = nodes.write_points(tmp_path, rows)

    assert json.loads(path.read_text()) == {
        "voltage_100": {
            "values": {"field.voltage": 100},
            "nodes": {"field": "c" * 12, "deposit": ["a" * 12, "b" * 12]},
        }
    }
    assert (
        '"field.voltage": 100\n' in path.read_text()
    )  # one spelling, as in the fingerprints
    assert [item.name for item in tmp_path.iterdir()] == ["points.json"]
