from __future__ import annotations

import pytest

from raser.cli import raser
from raser.cli.raser import build_parser


def test_top_level_field_and_frontend_routes_point_to_their_core_modules() -> None:
    parser = build_parser()
    field = vars(parser.parse_args(["field", "-wf", "HPK-Si-PiN", "--dry-run"]))
    frontend = vars(parser.parse_args(["frontend", "trans", "T1"]))

    assert field["_entry_module"] == ".core.field.command"
    assert field["_group"] == "core"
    assert field["wf"] is True
    assert frontend["_entry_module"] == ".core.frontend"
    assert frontend["_group"] == "core"


@pytest.mark.parametrize(
    "command",
    [["dev"], ["project", "create", "study"]],
)
def test_retired_routes_are_absent(command: list[str]) -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(command)


def test_signal_apps_have_no_generic_experiment_selector() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            ["signal", "HPK-Si-PiN", "--experiment", "time_resolution"]
        )


def test_global_test_flag_is_reserved_for_batch_submission() -> None:
    parsed = vars(build_parser().parse_args(["-t", "-b", "signal", "HPK-Si-PiN"]))

    assert parsed["test"] is True
    assert parsed["global_batch"] == 1


def test_cli_preserves_an_explicit_entry_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(raser, "_call_entry", lambda kwargs: 7)
    assert raser.main(["field", "HPK-Si-PiN", "--dry-run"]) == 7
