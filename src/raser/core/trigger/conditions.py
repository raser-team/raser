"""Validated trigger conditions from component configuration."""

from dataclasses import dataclass
import re

from raser.core.digitizer.settings import number


_CHANNEL_PATTERN = re.compile(r"CH([1-9][0-9]*)")


@dataclass(frozen=True)
class TriggerCondition:
    channel: str
    level_V: float
    slope: str | None = None
    state: str | None = None

    @property
    def place(self):
        return int(self.channel[2:]) - 1


@dataclass(frozen=True)
class TriggerConditions:
    mode: str
    conditions: tuple[TriggerCondition, ...]

    @classmethod
    def from_component(cls, values: dict):
        if not isinstance(values, dict):
            raise ValueError("trigger condition must be a mapping with key 'mode'")
        if "mode" not in values:
            raise ValueError("trigger condition is missing key 'mode'")
        mode = values["mode"]
        if mode not in {"edge", "pattern"}:
            raise ValueError("key 'mode' must be 'edge' or 'pattern'")
        if mode == "edge":
            _check_keys(
                values, {"mode", "source", "level_V", "slope"}, "trigger condition"
            )
            channel = _validate_channel(values["source"], "source")
            level = number(values["level_V"], "level_V")
            slope = values["slope"]
            if slope not in {"falling", "rising"}:
                raise ValueError("key 'slope' must be 'falling' or 'rising'")
            return cls("edge", (TriggerCondition(channel, level, slope=slope),))

        _check_keys(values, {"mode", "channels"}, "trigger condition")
        channels = values["channels"]
        if not isinstance(channels, dict) or not channels:
            raise ValueError("key 'channels' must be a non-empty mapping")
        parsed = []
        for raw_channel, condition in channels.items():
            channel = _validate_channel(raw_channel, "channels")
            if not isinstance(condition, dict):
                raise ValueError(f"trigger channel {channel!r} must be a mapping")
            _check_keys(condition, {"level_V", "state"}, f"trigger channel {channel!r}")
            level = number(condition["level_V"], f"channels.{channel}.level_V")
            state = condition["state"]
            if state not in {"low", "high"}:
                raise ValueError(
                    f"key 'channels.{channel}.state' must be 'low' or 'high'"
                )
            parsed.append(TriggerCondition(channel, level, state=state))
        parsed.sort(key=lambda item: item.place)
        return cls("pattern", tuple(parsed))

    @property
    def sources(self):
        return [condition.channel for condition in self.conditions]

    @property
    def levels_V(self):
        return [condition.level_V for condition in self.conditions]

    @property
    def slopes(self):
        return [condition.slope for condition in self.conditions]

    @property
    def states(self):
        return [condition.state for condition in self.conditions]

    @property
    def places(self):
        return [condition.place for condition in self.conditions]

    def place(self, channel):
        if isinstance(channel, int) and not isinstance(channel, bool) and channel >= 1:
            return channel - 1
        return int(_validate_channel(channel, "channel")[2:]) - 1

    def __len__(self):
        return len(self.conditions)

    def __iter__(self):
        return iter(self.conditions)


def _validate_channel(value, key):
    match = _CHANNEL_PATTERN.fullmatch(str(value))
    if match is None:
        raise ValueError(f"key '{key}' must be a channel named CH<n>")
    return str(value)


def _check_keys(values, required, what):
    missing = sorted(required - values.keys())
    if missing:
        raise ValueError(f"{what} is missing key {missing[0]!r}")
    extra = sorted(values.keys() - required)
    if extra:
        raise ValueError(f"{what} has unknown key {extra[0]!r}")
