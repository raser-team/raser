"""Validated settings and derived units for a digitizer."""

from dataclasses import dataclass
import math


_COMMON_KEYS = {
    "channels",
    "bits",
    "max_sampling_rate_GSps",
    "response",
    "aperture_jitter_ps",
    "sampling_rate_GSps",
    "full_scale_V",
    "offset_V",
}


def number(value, key):
    """Return ``value`` as a finite float; only int and float are accepted."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"key '{key}' must be a number")
    if not math.isfinite(value):
        raise ValueError(f"key '{key}' must be finite")
    return float(value)


@dataclass(frozen=True)
class DigitizerSettings:
    channels: int
    bits: int
    max_sampling_rate_GSps: float
    response: str
    bandwidth_GHz: float | None
    aperture_jitter_ps: float
    sampling_rate_GSps: float
    full_scale_V: float
    offset_V: float

    @classmethod
    def from_component(cls, name: str, values: dict):
        values = {key: value for key, value in values.items() if key != "trigger"}
        missing = sorted(_COMMON_KEYS - values.keys())
        if missing:
            raise ValueError(
                f"digitizer component {name} is missing key {missing[0]!r}"
            )
        extra = sorted(values.keys() - _COMMON_KEYS - {"bandwidth_GHz"})
        if extra:
            raise ValueError(f"digitizer component {name} has unknown key {extra[0]!r}")

        response = values["response"]
        if response not in {"brickwall", "none"}:
            raise ValueError("key 'response' must be 'brickwall' or 'none'")
        has_bandwidth = "bandwidth_GHz" in values
        if response == "brickwall" and not has_bandwidth:
            raise ValueError("digitizer component is missing key 'bandwidth_GHz'")
        if response == "none" and has_bandwidth:
            raise ValueError("key 'bandwidth_GHz' is not allowed for response 'none'")

        try:
            channels = int(values["channels"])
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("key 'channels' must be a positive integer") from error
        if (
            isinstance(values["channels"], bool)
            or channels <= 0
            or channels != values["channels"]
        ):
            raise ValueError("key 'channels' must be a positive integer")

        try:
            bits = int(values["bits"])
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(
                "key 'bits' must be an integer from 1 through 15"
            ) from error
        if (
            isinstance(values["bits"], bool)
            or bits != values["bits"]
            or not 1 <= bits <= 15
        ):
            raise ValueError("key 'bits' must be an integer from 1 through 15")

        numbers = {
            key: number(values[key], key)
            for key in (
                "max_sampling_rate_GSps",
                "aperture_jitter_ps",
                "sampling_rate_GSps",
                "full_scale_V",
                "offset_V",
            )
        }
        bandwidth = (
            number(values["bandwidth_GHz"], "bandwidth_GHz") if has_bandwidth else None
        )

        for key in ("max_sampling_rate_GSps", "sampling_rate_GSps", "full_scale_V"):
            if numbers[key] <= 0:
                raise ValueError(f"key '{key}' must be positive")
        if bandwidth is not None and bandwidth <= 0:
            raise ValueError("key 'bandwidth_GHz' must be positive")
        if numbers["sampling_rate_GSps"] > numbers["max_sampling_rate_GSps"]:
            raise ValueError(
                "key 'sampling_rate_GSps' must not exceed 'max_sampling_rate_GSps'"
            )
        if numbers["aperture_jitter_ps"] < 0:
            raise ValueError("key 'aperture_jitter_ps' must be finite and not negative")

        return cls(
            channels,
            bits,
            numbers["max_sampling_rate_GSps"],
            response,
            bandwidth,
            numbers["aperture_jitter_ps"],
            numbers["sampling_rate_GSps"],
            numbers["full_scale_V"],
            numbers["offset_V"],
        )

    @property
    def period_s(self) -> float:
        return 1e-9 / self.sampling_rate_GSps

    @property
    def bandwidth_hz(self) -> float | None:
        return None if self.bandwidth_GHz is None else self.bandwidth_GHz * 1e9

    @property
    def aperture_jitter_s(self) -> float:
        """Aperture jitter (rms), in seconds."""
        return self.aperture_jitter_ps * 1e-12

    @property
    def lsb_V(self) -> float:
        return self.full_scale_V / (1 << self.bits)
