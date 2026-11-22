"""Logic expressions over slots and the coincidence time of equation (3)."""

from dataclasses import dataclass
import math
import re

from raser.core.digitizer.settings import number

_TOKEN = re.compile(r"\s*([A-Za-z0-9_-]+|[():,])")
_KEYWORDS = {"AND", "OR", "AT_LEAST"}


@dataclass(frozen=True)
class Slot:
    """Operand: true when the slot ``name`` is hit."""

    name: str

    def names(self):
        return {self.name}

    def value(self, hits):
        return self.name in hits


@dataclass(frozen=True)
class And:
    """True when every operand is true."""

    operands: tuple

    def names(self):
        return set().union(*(operand.names() for operand in self.operands))

    def value(self, hits):
        return all(operand.value(hits) for operand in self.operands)


@dataclass(frozen=True)
class Or:
    """True when at least one operand is true."""

    operands: tuple

    def names(self):
        return set().union(*(operand.names() for operand in self.operands))

    def value(self, hits):
        return any(operand.value(hits) for operand in self.operands)


@dataclass(frozen=True)
class AtLeast:
    """True when at least ``k`` of the listed slots are hit."""

    k: int
    slots: tuple

    def names(self):
        return set(self.slots)

    def value(self, hits):
        return sum(name in hits for name in self.slots) >= self.k


class _Parser:
    def __init__(self, text):
        self.text = text
        self.tokens = []
        position = 0
        stripped = text.rstrip()
        while position < len(stripped):
            match = _TOKEN.match(stripped, position)
            if match is None:
                raise ValueError(
                    f"require {text!r}: unexpected character "
                    f"{stripped[position:].lstrip()[0]!r}"
                )
            self.tokens.append(match.group(1))
            position = match.end()
        self.index = 0

    def _peek(self):
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def _take(self, expected=None):
        token = self._peek()
        if token is None:
            raise ValueError(
                f"require {self.text!r} ends before the expression is complete"
            )
        if expected is not None and token != expected:
            raise ValueError(
                f"require {self.text!r}: expected {expected!r} but found {token!r}"
            )
        self.index += 1
        return token

    def parse(self):
        if not self.tokens:
            raise ValueError("require is empty")
        node = self._or()
        if self._peek() is not None:
            raise ValueError(f"require {self.text!r}: unexpected {self._peek()!r}")
        return node

    def _or(self):
        operands = [self._and()]
        while self._peek() == "OR":
            self._take()
            operands.append(self._and())
        return operands[0] if len(operands) == 1 else Or(tuple(operands))

    def _and(self):
        operands = [self._atom()]
        while self._peek() == "AND":
            self._take()
            operands.append(self._atom())
        return operands[0] if len(operands) == 1 else And(tuple(operands))

    def _atom(self):
        token = self._take()
        if token == "(":
            node = self._or()
            self._take(")")
            return node
        if token == "AT_LEAST":
            return self._at_least()
        if token in _KEYWORDS or token in {")", ":", ","}:
            raise ValueError(f"require {self.text!r}: unexpected {token!r}")
        return Slot(token)

    def _at_least(self):
        self._take("(")
        text = self._take()
        if not re.fullmatch(r"[0-9]+", text):
            raise ValueError(
                f"require {self.text!r}: AT_LEAST needs an integer k, found {text!r}"
            )
        self._take(":")
        names = [self._name()]
        while self._peek() == ",":
            self._take()
            names.append(self._name())
        self._take(")")
        k = int(text)
        if len(set(names)) != len(names):
            raise ValueError(f"require {self.text!r}: AT_LEAST lists a slot twice")
        if not 1 <= k <= len(names):
            raise ValueError(
                f"require {self.text!r}: k = {k} of AT_LEAST must be an integer "
                f"from 1 through {len(names)}"
            )
        return AtLeast(k, tuple(names))

    def _name(self):
        token = self._take()
        if token in _KEYWORDS or token in {"(", ")", ":", ","}:
            raise ValueError(
                f"require {self.text!r}: expected a slot name, found {token!r}"
            )
        return token


def parse_require(text, slots):
    """Parse the logic expression ``text`` over the slot names ``slots``.

    ``"all"`` joins all slots with AND, ``"any"`` joins them with OR. ``AND``
    binds tighter than ``OR``. Every slot must occur in the expression and
    every name in the expression must be a slot.
    """
    slots = list(slots)
    if not slots:
        raise ValueError("slots must not be empty")
    if len(set(slots)) != len(slots):
        raise ValueError("slots must be unique")
    for name in slots:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", str(name)) or name in _KEYWORDS:
            raise ValueError(
                f"slot name {name!r} must consist of letters, digits, '_' and '-' "
                "and must not be AND, OR or AT_LEAST"
            )
    if not isinstance(text, str):
        raise ValueError("key 'require' must be a string")
    if text == "all":
        operands = tuple(Slot(name) for name in slots)
        return operands[0] if len(operands) == 1 else And(operands)
    if text == "any":
        operands = tuple(Slot(name) for name in slots)
        return operands[0] if len(operands) == 1 else Or(operands)
    expression = _Parser(text).parse()
    names = expression.names()
    unknown = sorted(names - set(slots))
    if unknown:
        raise ValueError(
            f"require {text!r} uses {unknown[0]!r}, which is not one of the slots {slots}"
        )
    unused = [name for name in slots if name not in names]
    if unused:
        raise ValueError(f"require {text!r} does not use the slot {unused[0]!r}")
    return expression


def evaluate(expression, hit_slots):
    """Return whether ``expression`` is true when exactly ``hit_slots`` are hit."""
    hits = set(hit_slots)
    unknown = sorted(hits - expression.names())
    if unknown:
        raise ValueError(f"hit slot {unknown[0]!r} does not occur in the expression")
    return bool(expression.value(hits))


def coincidence_time(expression, hit_times, window_s):
    """Return the trigger time of equation (3), or ``None`` without a solution.

    ``hit_times`` maps each hit slot to its hit time in s; ``window_s`` is the
    coincidence window in s, or ``None`` for no time condition.
    """
    if window_s is not None and (not math.isfinite(window_s) or window_s < 0):
        raise ValueError("window_s must be None or a finite non-negative number")
    for name, time in hit_times.items():
        if not math.isfinite(time):
            raise ValueError(f"hit time of slot {name!r} must be finite")
    for time in sorted(set(hit_times.values())):
        inside = {
            name
            for name, hit in hit_times.items()
            if hit <= time and (window_s is None or hit >= time - window_s)
        }
        if evaluate(expression, inside):
            return float(time)
    return None


_SETTING_KEYS = {"level_V", "slope", "require", "coincidence_window_ns"}


@dataclass(frozen=True)
class CoincidenceSettings:
    """Settings of a coincidence trigger device over the slots ``slots``."""

    slots: tuple[str, ...]
    level_V: dict[str, float]
    slope: str
    require: object
    coincidence_window_s: float | None

    @classmethod
    def from_component(cls, values: dict, slots):
        if not isinstance(values, dict):
            raise ValueError("coincidence component must be a mapping")
        missing = sorted(_SETTING_KEYS - values.keys())
        if missing:
            raise ValueError(f"coincidence component is missing key {missing[0]!r}")
        extra = sorted(values.keys() - _SETTING_KEYS)
        if extra:
            raise ValueError(f"coincidence component has unknown key {extra[0]!r}")
        slots = tuple(slots)
        require = parse_require(values["require"], slots)

        level = values["level_V"]
        if isinstance(level, dict):
            if set(level) != set(slots):
                raise ValueError(
                    f"key 'level_V' must have exactly the slots {list(slots)} as keys"
                )
            levels = {name: number(level[name], f"level_V.{name}") for name in slots}
        else:
            shared = number(level, "level_V")
            levels = {name: shared for name in slots}

        slope = values["slope"]
        if slope not in {"falling", "rising"}:
            raise ValueError("key 'slope' must be 'falling' or 'rising'")

        window = values["coincidence_window_ns"]
        if window is None:
            window_s = None
        else:
            window_s = number(window, "coincidence_window_ns") * 1e-9
            if window_s < 0:
                raise ValueError("key 'coincidence_window_ns' must not be negative")
        return cls(slots, levels, slope, require, window_s)
