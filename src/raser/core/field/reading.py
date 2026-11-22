"""What a field solve reads from its device.

The solve is handed a `Reading` in place of the detector. It behaves as the
detector does and notes every attribute and json key that is read, with the
value that was read. A field is out of date when one of them has changed.
"""

import hashlib
import json
import types
from pathlib import Path


ABSENT = ["absent"]  # noted for a key or attribute that was looked for and is not there


def noted(value):
    """A value as it is written down: itself when it is a number, a text or
    null, and a hash of its json otherwise."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return _hash(json.dumps(value, sort_keys=True, default=str).encode())


def _hash(content):
    return "sha256:" + hashlib.sha256(content).hexdigest()


class Keys(dict):
    """The json of a device, or one object inside it, noting the keys read.

    A key that holds an object is noted through the keys read inside it, one
    level down, as {key: {inner key: value}}; deeper values, and an object that
    is only asked to be there or gone through, are noted whole. What is written
    into it stays in it: the device keeps its json."""

    def __init__(self, content, read, inside=None):
        super().__init__(content)
        self._read, self._inside = read, inside

    def _note(self, key, whole=False):
        value = super().get(key)
        if isinstance(value, dict) and self._inside is None and not whole:
            if not isinstance(value, Keys):
                value = Keys(value, self._read, key)
                super().__setitem__(key, value)
            return value
        entry = noted(value) if super().__contains__(key) else ABSENT
        if self._inside is None:
            self._read[key] = entry
        elif isinstance(self._read.setdefault(self._inside, {}), dict):
            self._read[self._inside][key] = entry  # unless the object is noted whole
        return value

    def __getitem__(self, key):
        super().__getitem__(key)  # a missing key is an error, as in a dict
        return self._note(key)

    def get(self, key, default=None):
        value = self._note(key)
        return value if super().__contains__(key) else default

    def __contains__(self, key):
        self._note(key, whole=True)
        return super().__contains__(key)

    def __iter__(self):
        for key in super().__iter__():
            self._note(key, whole=True)
        return super().__iter__()

    def keys(self):
        list(self)  # going through the keys notes them
        return super().keys()

    def values(self):
        return [self[key] for key in self]

    def items(self):
        return [(key, self[key]) for key in self]


class Reading:
    """A detector that notes what is read from it, in `read`:
    {"attributes": {name: value}, "keys": {key: value or {inner key: value}},
    "files": {name: hash}}."""

    def __init__(self, my_d):
        self.__dict__["_d"] = my_d
        self.__dict__["read"] = {"attributes": {}, "keys": {}, "files": {}}

    def file(self, name):
        path = self._d.file(name)
        self.read["files"][str(name)] = _hash(path.read_bytes())
        return path

    def __getattr__(self, name):
        try:
            value = getattr(self._d, name)
        except AttributeError:
            self.read["attributes"][name] = ABSENT
            raise
        if name == "device_dict":
            return Keys(value, self.read["keys"])
        if isinstance(value, types.MethodType):
            return types.MethodType(value.__func__, self)  # its reads are noted too
        if not isinstance(value, Path):  # where a file is, not what the device is
            self.read["attributes"][name] = noted(value)
        return value


def changed(read, my_d):
    """The attributes, json keys and files noted in `read` that are now other in `my_d`."""

    def now(place, key):
        return noted(place[key]) if isinstance(place, dict) and key in place else ABSENT

    differing = [
        name
        for name, value in read["attributes"].items()
        if (noted(getattr(my_d, name)) if hasattr(my_d, name) else ABSENT) != value
    ]
    for key, value in read["keys"].items():
        if not isinstance(value, dict):
            if now(my_d.device_dict, key) != value:
                differing.append(key)
            continue
        inside = my_d.device_dict.get(key)
        differing += [
            f"{key}.{inner}" for inner, entry in value.items() if now(inside, inner) != entry
        ]
    for name, value in read["files"].items():
        try:
            same = _hash(my_d.file(name).read_bytes()) == value
        except FileNotFoundError:
            same = False
        if not same:
            differing.append(name)
    return differing
