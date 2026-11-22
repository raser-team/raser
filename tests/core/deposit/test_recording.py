import pytest

from raser.core.deposit.recording import check_condition
from raser.core.deposit.recording import event_recorded
from raser.core.deposit.recording import is_recorded
from raser.core.deposit.recording import parse_require
from raser.core.deposit.recording import slot_hits

SLOTS = ["a", "b", "c"]
NS = 1.0e-9


def test_and_binds_tighter_than_or_and_brackets_change_it() -> None:
    assert parse_require("a OR b AND c", SLOTS) == ("OR", ["a", ("AND", ["b", "c"])])
    assert parse_require("a AND b OR c", SLOTS) == ("OR", [("AND", ["a", "b"]), "c"])
    assert parse_require("(a OR b) AND c", SLOTS) == ("AND", [("OR", ["a", "b"]), "c"])
    # one slot: the slot itself
    assert parse_require("all", ["a"]) == "a"


def test_any_and_all_are_the_or_and_the_and_of_every_slot() -> None:
    assert parse_require("any", SLOTS) == ("OR", SLOTS)
    assert parse_require("all", SLOTS) == ("AND", SLOTS)


@pytest.mark.parametrize(
    ("require", "message"),
    [
        ("a AND d", "require 'a AND d' names unknown slot 'd'"),
        ("a AND b", "require 'a AND b' does not use the slot 'c'"),
        ("a OR (b AND c) OR d", "names unknown slot 'd'"),
        ("a AND", "invalid require expression"),
        ("AND a OR b OR c", "invalid require expression"),
        ("a b OR c", "invalid require expression"),
        ("(a OR b AND c", "invalid require expression"),
        ("a OR b) AND c", "invalid require expression"),
        ("a OR OR b OR c", "invalid require expression"),
        ("", "invalid require expression"),
        ("()", "invalid require expression"),
    ],
)
def test_an_expression_that_is_not_over_the_slots_is_refused(require, message) -> None:
    with pytest.raises(ValueError, match=message.replace("(", r"\(")):
        parse_require(require, SLOTS)


def test_the_conditions_of_an_experiment_are_checked_against_its_slots() -> None:
    windows = {slot: (None, None) for slot in SLOTS}
    assert check_condition(SLOTS, windows, "any", 2.0) == ("OR", SLOTS)
    with pytest.raises(ValueError, match=r"energy windows are for \['a', 'b'\]"):
        check_condition(SLOTS, {"a": (None, None), "b": (None, None)}, "any", None)
    with pytest.raises(
        ValueError, match=r"slot 'b' has edep_min \(0.2 MeV\) > edep_max \(0.1 MeV\)"
    ):
        check_condition(SLOTS, {**windows, "b": (0.2, 0.1)}, "any", None)
    for width in (0, -1.0):
        with pytest.raises(ValueError, match="coincidence_window_ns must be positive"):
            check_condition(SLOTS, windows, "any", width)


def test_a_slot_is_hit_by_energy_above_zero_inside_its_own_window() -> None:
    windows = {"a": (0.1, 0.3), "b": (None, 0.3), "c": (0.1, None)}
    energies = {"a": 0.3, "b": 0.05, "c": 0.0}
    times = {"a": 4e-9, "b": 5e-9}

    # a sits on its upper bound; b below it, no lower bound; c has nothing
    assert slot_hits(windows, energies, times) == {"a": 4e-9, "b": 5e-9}
    # a bound is part of the window on either side
    assert slot_hits({"a": (0.1, 0.3)}, {"a": 0.1}, {"a": 1e-9}) == {"a": 1e-9}
    # below the lower bound of a, above the upper bound of b, nothing in c
    assert slot_hits(windows, {"a": 0.0999, "b": 0.31, "c": 0.0}, times) == {}
    # no lower bound still wants energy: a bound of 0 or none does not hit an empty slot
    assert slot_hits({"b": (None, None)}, {"b": 0.0}, {}) == {}
    assert slot_hits({"c": (None, None)}, {"c": 1e-6}, {"c": 1e-9}) == {"c": 1e-9}


def test_without_a_window_in_time_the_logic_alone_decides() -> None:
    tree = parse_require("a AND b", ["a", "b"])
    both = {"a": 0.0, "b": 9.0}
    assert is_recorded(tree, ["a", "b"], both, None)
    assert not is_recorded(tree, ["a", "b"], {"a": 0.0}, None)
    anyone = parse_require("any", ["a", "b"])
    assert is_recorded(anyone, ["a", "b"], {"b": 3e-9}, None)
    assert not is_recorded(anyone, ["a", "b"], {}, None)


def test_coincidence_window_counts_only_hits_within_it_of_some_hit() -> None:
    tree = parse_require("a AND b", ["a", "b"])
    hits = {"a": 1 * NS, "b": 3 * NS}

    assert is_recorded(tree, ["a", "b"], hits, 2.5)
    assert not is_recorded(tree, ["a", "b"], hits, 1.5)
    # the window includes its end: b is exactly 2 ns after a
    assert is_recorded(tree, ["a", "b"], hits, 2.0)
    # the slot hit first does not have to be the one that opens the window
    assert is_recorded(tree, ["a", "b"], {"a": 3 * NS, "b": 1 * NS}, 2.5)


def test_window_in_time_is_tried_from_every_hit() -> None:
    slots = ["a", "b", "c"]
    hits = {"a": 0.0, "b": 10 * NS, "c": 11 * NS}

    # b and c are close, a is far from both: the window opens at b, not at a
    assert is_recorded(("AND", ["b", "c"]), slots, hits, 2.0)
    assert not is_recorded(parse_require("all", slots), slots, hits, 2.0)
    assert is_recorded(parse_require("all", slots), slots, hits, 11.0)
    # a slot out of the window counts as not hit: (a AND b) OR c is true through c alone
    assert is_recorded(parse_require("(a AND b) OR c", slots), slots, hits, 2.0)
    assert not is_recorded(
        parse_require("(a AND b) OR c", slots), slots, {"a": 0.0, "b": 10 * NS}, 2.0
    )


def test_an_event_is_recorded_by_the_windows_of_each_slot_then_the_logic() -> None:
    windows = {"ref": (0.01, None), "dut": (None, 0.1)}
    tree = parse_require("ref AND dut", ["ref", "dut"])
    first = {"ref": 0.0, "dut": 0.0}

    assert event_recorded(
        tree, ["ref", "dut"], windows, {"ref": 0.02, "dut": 0.05}, first, None
    )
    # ref below its own lower bound; dut above its upper bound
    assert not event_recorded(
        tree, ["ref", "dut"], windows, {"ref": 0.005, "dut": 0.05}, first, None
    )
    assert not event_recorded(
        tree, ["ref", "dut"], windows, {"ref": 0.02, "dut": 0.2}, first, None
    )
    # one slot without deposits
    assert not event_recorded(
        tree, ["ref", "dut"], windows, {"ref": 0.02, "dut": 0.0}, {"ref": 0.0}, None
    )
    # the same energies, any: one slot is enough
    anyone = parse_require("any", ["ref", "dut"])
    assert event_recorded(
        anyone, ["ref", "dut"], windows, {"ref": 0.02, "dut": 0.0}, {"ref": 0.0}, None
    )
    # times apart by more than the window
    apart = {"ref": 0.0, "dut": 5 * NS}
    assert not event_recorded(
        tree, ["ref", "dut"], windows, {"ref": 0.02, "dut": 0.05}, apart, 2.0
    )
