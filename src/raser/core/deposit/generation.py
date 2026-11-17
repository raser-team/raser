"""How many events a source generates."""

from __future__ import annotations

from collections.abc import Callable, Iterator

# The most events generated for the recorded events asked for.
GENERATED_LIMIT = 10_000_000


def asked(events: int | None, generated: int | None, limit: int = GENERATED_LIMIT) -> None:
    """Either `events`, the recorded events asked for, or `generated`, the
    events to generate, is given: not both, not neither. That number and
    `limit`, the most events generated for `events`, are positive."""
    if (events is None) == (generated is None):
        raise ValueError(
            f"either the recorded events ({events}) or the generated events "
            f"({generated}) are asked for, not both and not neither"
        )
    for name, number in (("recorded events", events), ("generated events", generated), ("generated_limit", limit)):
        if number is not None and int(number) < 1:
            raise ValueError(f"the {name} asked for are {number}: at least 1")


def too_few(events: int, recorded: int, generated: int) -> RuntimeError:
    """The error of a source that generated its limit without recording the
    events asked for."""
    return RuntimeError(
        f"{recorded} of the {events} events asked for were recorded when the limit of "
        f"{generated} generated events was reached: {recorded / generated:.3g} of the "
        "generated events are recorded. Ask for fewer events, or raise generated_limit"
    )


def generation(
    events: int | None, generated: int | None, limit: int, recorded: Callable[[], int]
) -> Iterator[int]:
    """The numbers of the events to generate, from 0: `generated` of them,
    or as many as it takes until `recorded()` is `events`, at most `limit`."""
    asked(events, generated, limit)
    if generated is not None:
        yield from range(int(generated))
        return
    number = 0
    while recorded() < int(events):
        if number >= limit:
            raise too_few(int(events), recorded(), number)
        yield number
        number += 1
