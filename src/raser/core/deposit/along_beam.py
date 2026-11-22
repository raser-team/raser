"""Where the items of a g4setup lie along the beam, in the coordinates of the
Geant4 world.

The key "along_beam" of a g4setup is a column that starts at "source". The
world origin is on the source and z runs along the beam, downstream. Every
item takes its length along z: a gap its width, an object its side_z, a slot
the thickness of its device, a list of items side by side the thickest of
them; the front face of an item is at the sum of the lengths before it. Reading
this imports no Geant4.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

# (cos, sin) of the rotations about z that a slot may have [degree].
ROTATIONS = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}
FACINGS = ("upstream", "downstream")
# Colour of a slot that gives none.
SLOT_COLOUR = (1.0, 0.1, 0.8)

_SLOT_KEYS = {"slot", "facing", "offset", "rotation_z", "colour"}
_OBJECT_KEYS = {"object", "offset"}


def inactive_thickness(device) -> float:
    """The thickness [um] of the layers of `device` around its active layer.

    The device files do not describe these layers yet, so it is 0. Once they
    do, it is the sum of their thicknesses, and it adds to the thickness of
    the slot of the device here and nowhere else.
    """
    return 0.0


def device_thickness(device) -> float:
    """The thickness [um] of the slot of `device` along z: the active layer
    l_z and the layers around it. Of those, see `inactive_thickness`."""
    return float(device.l_z) + inactive_thickness(device)


@dataclass(frozen=True)
class PlacedObject:
    """An object of the g4setup in the column. z is its front face [um],
    offset the x and y of its centre, side its full width along x and y."""

    name: str
    z: float
    offset: tuple[float, float]
    thickness: float
    side: tuple[float, float]


@dataclass(frozen=True)
class PlacedSlot:
    """A slot of the column holding a device of the sizes l_x, l_y, l_z
    [um] and, around the active layer, the thickness t.

    z is the front face of the slot in the column. `front` is the centre of
    the face z = 0 of the device, its front face; facing "downstream" turns
    the device about y, so that its front face is the one downstream.
    """

    name: str
    z: float
    offset: tuple[float, float]
    facing: str
    rotation_z: int
    colour: tuple[float, float, float]
    l_x: float
    l_y: float
    l_z: float
    t: float

    @property
    def thickness(self) -> float:
        return self.l_z + self.t

    @property
    def front(self) -> tuple[float, float, float]:
        """The point P of the face z = 0 of the device, its middle, in the
        world [um]."""
        z = self.z if self.facing == "upstream" else self.z + self.thickness
        return (self.offset[0], self.offset[1], z)

    @property
    def side(self) -> tuple[float, float]:
        """Full width of the slot along x and y of the world [um], after the
        rotation about z."""
        if self.rotation_z in (90, 270):
            return (self.l_y, self.l_x)
        return (self.l_x, self.l_y)

    @property
    def active_z(self) -> tuple[float, float]:
        """The z range [um] of the active layer in the world."""
        if self.facing == "upstream":
            return (self.z, self.z + self.l_z)
        return (self.z + self.t, self.z + self.t + self.l_z)

    def to_world(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        """The point (x, y, z) [um] of the coordinates of the device in the
        world."""
        cos, sin = ROTATIONS[self.rotation_z]
        u, v, w = x - self.l_x / 2, y - self.l_y / 2, z
        if self.facing == "downstream":
            u, w = -u, -w
        px, py, pz = self.front
        return (px + cos * u - sin * v, py + sin * u + cos * v, pz + w)

    def to_device(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        """The point (x, y, z) [um] of the world in the coordinates of the
        device: the inverse of `to_world`."""
        cos, sin = ROTATIONS[self.rotation_z]
        px, py, pz = self.front
        dx, dy, w = x - px, y - py, z - pz
        u, v = cos * dx + sin * dy, -sin * dx + cos * dy
        if self.facing == "downstream":
            u, w = -u, -w
        return (u + self.l_x / 2, v + self.l_y / 2, w)


@dataclass(frozen=True)
class Layout:
    """The items of an along_beam column. `objects` and `slots` are in the
    order of the column; length is the length of the column [um]."""

    objects: tuple[PlacedObject, ...]
    slots: tuple[PlacedSlot, ...]
    length: float

    @property
    def reach(self) -> float:
        """The farthest an item reaches from the axis along x or y [um]: the
        offset of its centre and half its width."""
        reach = 0.0
        items: list[PlacedObject | PlacedSlot] = [*self.objects, *self.slots]
        for item in items:
            reach = max(
                reach,
                abs(item.offset[0]) + item.side[0] / 2,
                abs(item.offset[1]) + item.side[1] / 2,
            )
        return reach

    def slot(self, name: str) -> PlacedSlot:
        for slot in self.slots:
            if slot.name == name:
                return slot
        raise KeyError(name)


def objects_of(g4setup: Mapping) -> dict[str, dict]:
    """The objects of the g4setup by name, whichever of "elemental" and
    "binary_compounds" lists them."""
    table: dict[str, dict] = {}
    for group in (g4setup.get("object") or {}).values():
        table.update(group)
    return table


def slot_names(g4setup: Mapping) -> list[str]:
    """The slots of the along_beam column in the order of the column, after
    the checks of `parse_along_beam` that need no device."""
    return [slot["slot"] for _, slot in _structure(g4setup)[1]]


def parse_along_beam(g4setup: Mapping, devices: Mapping) -> Layout:
    """The positions of the items of the column along_beam of the g4setup,
    with the devices of its slots.

    devices maps the name of every slot to its device, which gives l_x, l_y
    and l_z. A column that does not start with "source", a negative gap, an
    object that the g4setup does not have, a name twice, a facing that is not
    "upstream" or "downstream", a rotation_z that is not 0, 90, 180 or 270,
    items side by side that overlap, and slots that are not the devices are
    errors (ValueError).
    """
    steps, slots = _structure(g4setup)
    placed = [slot["slot"] for _, slot in slots]
    if sorted(placed) != sorted(devices):
        raise ValueError(
            f"the g4setup places {placed}, the devices are {list(devices)}"
        )
    table = objects_of(g4setup)
    z = 0.0
    objects: list[PlacedObject] = []
    slot_items: list[PlacedSlot] = []
    for step in steps:
        if isinstance(step, float):
            z += step
            continue
        members: list[PlacedObject | PlacedSlot] = []
        for item in step:
            offset = _offset(item)
            if "slot" in item:
                device = devices[item["slot"]]
                members.append(
                    PlacedSlot(
                        name=item["slot"],
                        z=z,
                        offset=offset,
                        facing=item.get("facing", "upstream"),
                        rotation_z=int(item.get("rotation_z", 0)),
                        colour=_colour(item),
                        l_x=float(device.l_x),
                        l_y=float(device.l_y),
                        l_z=float(device.l_z),
                        t=inactive_thickness(device),
                    )
                )
            else:
                body = table[item["object"]]
                members.append(
                    PlacedObject(
                        name=item["object"],
                        z=z,
                        offset=offset,
                        thickness=float(body["side_z"]),
                        side=(float(body["side_x"]), float(body["side_y"])),
                    )
                )
        _no_overlap(members)
        for member in members:
            if isinstance(member, PlacedSlot):
                slot_items.append(member)
            else:
                objects.append(member)
        z += max(member.thickness for member in members)
    return Layout(tuple(objects), tuple(slot_items), z)


def _colour(item: Mapping) -> tuple[float, float, float]:
    red, green, blue = item.get("colour", SLOT_COLOUR)
    return (float(red), float(green), float(blue))


def _offset(item: Mapping) -> tuple[float, float]:
    offset = item.get("offset", [0, 0])
    if len(offset) != 2:
        raise ValueError(f"offset {offset} of {item} is not [x, y]")
    return (float(offset[0]), float(offset[1]))


def _no_overlap(members: list[PlacedObject | PlacedSlot]) -> None:
    for first in range(len(members)):
        for second in range(first + 1, len(members)):
            a, b = members[first], members[second]
            if (
                abs(a.offset[0] - b.offset[0]) < (a.side[0] + b.side[0]) / 2
                and abs(a.offset[1] - b.offset[1]) < (a.side[1] + b.side[1]) / 2
            ):
                raise ValueError(
                    f"side-by-side items overlap: {a.name!r} and {b.name!r}"
                )


def _structure(g4setup: Mapping):
    """The column as steps, a gap [um] or the list of the items placed at one
    z, each a dict, and the slots with their dicts; the checks that need no
    device are made here."""
    if "along_beam" not in g4setup:
        raise ValueError(f"the g4setup {g4setup.get('name')!r} has no along_beam")
    column = list(g4setup["along_beam"])
    if not column or column[0] != "source":
        raise ValueError("the first item of along_beam must be 'source'")
    table = objects_of(g4setup)
    seen: set[str] = set()
    steps: list = []
    slots: list = []

    def member(item):
        if isinstance(item, str):
            item = {"object": item}
        if not isinstance(item, dict):
            raise ValueError(f"item {item!r} of along_beam is not an object or a slot")
        kind = ("slot" in item) + ("object" in item)
        if kind != 1:
            raise ValueError(
                f"item {item!r} of along_beam is one of an object and a slot"
            )
        known = _SLOT_KEYS if "slot" in item else _OBJECT_KEYS
        if set(item) - known:
            raise ValueError(
                f"item {item!r} of along_beam has keys {sorted(set(item) - known)}"
            )
        name = str(item.get("slot", item.get("object")))
        if "object" in item and name not in table:
            raise ValueError(f"object {name!r} is not in object")
        if name in seen:
            raise ValueError(f"duplicate {name!r} in along_beam")
        seen.add(name)
        if "slot" in item:
            facing = item.get("facing", "upstream")
            if facing not in FACINGS:
                raise ValueError(
                    f"slot {name!r} has facing {facing!r}: expected 'upstream' or 'downstream'"
                )
            rotation = item.get("rotation_z", 0)
            if rotation not in ROTATIONS:
                raise ValueError(
                    f"slot {name!r} has rotation_z {rotation!r}: expected 0, 90, 180 or 270"
                )
            slots.append((len(steps), item))
        return item

    for item in column[1:]:
        if isinstance(item, dict) and "gap" in item:
            if set(item) != {"gap"}:
                raise ValueError(f"item {item!r} of along_beam has keys besides gap")
            if item["gap"] < 0:
                raise ValueError(f"gap must be non-negative, got {item['gap']}")
            steps.append(float(item["gap"]))
        elif isinstance(item, list):
            if not item:
                raise ValueError("a list of items side by side in along_beam is empty")
            steps.append([member(one) for one in item])
        else:
            steps.append([member(item)])
    return steps, slots
