"""Three-dimensional vector operations used by carrier transport."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Vector:
    x: float
    y: float
    z: float

    @property
    def components(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def cross(self, other: "Vector") -> "Vector":
        return Vector(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def get_length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def add(self, other: "Vector") -> "Vector":
        return Vector(self.x + other.x, self.y + other.y, self.z + other.z)

    def sub(self, other: "Vector") -> "Vector":
        return Vector(self.x - other.x, self.y - other.y, self.z - other.z)

    def mul(self, factor: float) -> "Vector":
        return Vector(self.x * factor, self.y * factor, self.z * factor)
