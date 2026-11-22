"""Whether an event is recorded: the slots it hits, and the condition on them.

A slot is hit when the energy deposited in it is above 0 and inside its
window; the event is recorded when the logic expression `require` over the
slots hit, within the window in time, is true. `require` names slots and
joins them with AND, OR and parentheses, AND binding tighter than OR; "any"
is the OR of all the slots and "all" the AND of all of them. Reading this
imports no Geant4.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

Window = tuple[float | None, float | None]

_TOKEN = re.compile(r"\(|\)|[^\s()]+")
_OPERATORS = ("AND", "OR")


def parse_require(require: str, slots) -> tuple:
    """The tree of the logic expression `require` over `slots`: a slot name,
    or ("AND", operands) or ("OR", operands).

    A name that is not a slot, a slot that the expression does not use, and a
    syntax error are errors (ValueError).
    """
    slots = list(slots)
    text = require.strip()
    if text == "any":
        tree = ("OR", slots) if len(slots) > 1 else slots[0]
    elif text == "all":
        tree = ("AND", slots) if len(slots) > 1 else slots[0]
    else:
        tree = _Parser(require, slots).parse()
    used = _names(tree)
    for slot in slots:
        if slot not in used:
            raise ValueError(f"require {require!r} does not use the slot {slot!r}")
    return tree


class _Parser:
    def __init__(self, require: str, slots: list[str]):
        self.require = require
        self.slots = slots
        self.tokens = _TOKEN.findall(require)
        self.at = 0

    def invalid(self) -> ValueError:
        return ValueError(f"invalid require expression {self.require!r}")

    def peek(self) -> str | None:
        return self.tokens[self.at] if self.at < len(self.tokens) else None

    def parse(self):
        tree = self.disjunction()
        if self.peek() is not None:
            raise self.invalid()
        return tree

    def disjunction(self):
        operands = [self.conjunction()]
        while self.peek() == "OR":
            self.at += 1
            operands.append(self.conjunction())
        return operands[0] if len(operands) == 1 else ("OR", operands)

    def conjunction(self):
        operands = [self.operand()]
        while self.peek() == "AND":
            self.at += 1
            operands.append(self.operand())
        return operands[0] if len(operands) == 1 else ("AND", operands)

    def operand(self):
        token = self.peek()
        if token is None or token in _OPERATORS or token == ")":
            raise self.invalid()
        self.at += 1
        if token == "(":
            tree = self.disjunction()
            if self.peek() != ")":
                raise self.invalid()
            self.at += 1
            return tree
        if token not in self.slots:
            raise ValueError(f"require {self.require!r} names unknown slot {token!r}")
        return token


def _names(tree) -> set[str]:
    if isinstance(tree, str):
        return {tree}
    return set().union(*(_names(operand) for operand in tree[1]))


def _value(tree, hit: Mapping[str, bool]) -> bool:
    if isinstance(tree, str):
        return hit[tree]
    values = (_value(operand, hit) for operand in tree[1])
    return all(values) if tree[0] == "AND" else any(values)


def check_condition(
    slots,
    windows: Mapping[str, Window],
    require: str,
    coincidence_window_ns: float | None,
) -> tuple:
    """The parsed `require` over `slots`, after checking the rest of the
    condition: the energy windows [MeV] are of the slots, no window has its
    lower bound above its upper, and the window in time is positive."""
    slots = list(slots)
    if sorted(windows) != sorted(slots):
        raise ValueError(
            f"the energy windows are for {list(windows)}, the devices are {slots}"
        )
    for slot, (low, high) in windows.items():
        if low is not None and high is not None and low > high:
            raise ValueError(
                f"slot {slot!r} has edep_min ({low} MeV) > edep_max ({high} MeV)"
            )
    tree = parse_require(require, slots)
    if coincidence_window_ns is not None and not coincidence_window_ns > 0:
        raise ValueError(
            f"coincidence_window_ns must be positive, got {coincidence_window_ns} ns"
        )
    return tree


def slot_hits(
    windows: Mapping[str, Window],
    energies: Mapping[str, float],
    first_times: Mapping[str, float],
) -> dict[str, float]:
    """The slots hit, with the time of the earliest deposit in each [s].

    energies is the energy deposited in each slot [MeV], first_times the time
    of its earliest deposit (a slot without a deposit has none). A slot is
    hit when its energy is above 0 and not below the lower nor above the
    upper bound of its window; a bound that is None is not checked.
    """
    hits = {}
    for slot, (low, high) in windows.items():
        energy = energies.get(slot, 0.0)
        if energy <= 0:
            continue
        if low is not None and energy < low:
            continue
        if high is not None and energy > high:
            continue
        hits[slot] = first_times[slot]
    return hits


def is_recorded(
    tree,
    slots,
    hits: Mapping[str, float],
    coincidence_window_ns: float | None,
) -> bool:
    """Whether an event is recorded: `tree` is true when the slots in `hits`
    (each with the time of its earliest deposit [s]) are the slots hit.

    With a window W in time [ns], some t0 must make `tree` true when only the
    slots hit with their time in [t0, t0 + W] count; the times of the slots
    hit are the t0 to try. Without a window the time does not matter.
    """
    if coincidence_window_ns is None:
        return _value(tree, {slot: slot in hits for slot in slots})
    width = coincidence_window_ns * 1.0e-9
    for t0 in hits.values():
        inside = {
            slot: slot in hits and t0 <= hits[slot] <= t0 + width for slot in slots
        }
        if _value(tree, inside):
            return True
    return False


def event_recorded(
    tree,
    slots,
    windows: Mapping[str, Window],
    energies: Mapping[str, float],
    first_times: Mapping[str, float],
    coincidence_window_ns: float | None,
) -> bool:
    """Whether an event is recorded: the slots it hits (`slot_hits`), and
    `tree` over them in the window in time (`is_recorded`)."""
    hits = slot_hits(windows, energies, first_times)
    return is_recorded(tree, slots, hits, coincidence_window_ns)


class RecordedSteps:
    """The steps of the recorded events, slot by slot, as a Geant4 run
    collects them: `events` holds the event numbers, and for each slot
    `positions`, `starts` [um], `energies` [MeV] and `times` [s] hold, one
    list per recorded event, its steps in the coordinates of the Geant4
    world. A slot that an event leaves nothing in has an empty list."""

    def __init__(self, slots):
        self.slots = list(slots)
        self.events: list[int] = []
        self.positions: dict[str, list[list[list[float]]]] = {
            slot: [] for slot in self.slots
        }
        self.starts: dict[str, list[list[list[float]]]] = {
            slot: [] for slot in self.slots
        }
        self.energies: dict[str, list[list[float]]] = {slot: [] for slot in self.slots}
        self.times: dict[str, list[list[float]]] = {slot: [] for slot in self.slots}
