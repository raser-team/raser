"""What a field solve reads from its device.

The solve is handed a `Reading` in place of the detector. It behaves as the
detector does and notes every attribute and json key that is read, with the
value that was read. A field is out of date when one of them has changed.
"""

import hashlib
import json
import types
from pathlib import Path


def noted(value):
    """A value as it is written down: itself when it is a number, a text or
    nothing, and a hash of its json otherwise."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return _hash(json.dumps(value, sort_keys=True, default=str).encode())


def _hash(content):
    return "sha256:" + hashlib.sha256(content).hexdigest()


class Keys(dict):
    """The json of a device, or one object inside it, noting the keys read.

    A key that holds an object is noted through the keys read inside it, one
    level down; deeper values, and an object that is only asked to be there or
    gone through, are noted whole. What is written into it stays in it: the
    device keeps its json."""

    def __init__(self, content, read, prefix=""):
        super().__init__(content)
        self._read, self._prefix = read, prefix

    def _note(self, key, whole=False):
        value = super().get(key)
        if isinstance(value, dict) and not self._prefix and not whole:
            if not isinstance(value, Keys):
                value = Keys(value, self._read, f"{key}.")
                super().__setitem__(key, value)
            return value
        self._read[self._prefix + str(key)] = noted(value)
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
    {"attributes": {name: value}, "keys": {json path: value}, "files": {name: hash}}."""

    def __init__(self, my_d):
        self.__dict__["_d"] = my_d
        self.__dict__["read"] = {"attributes": {}, "keys": {}, "files": {}}

    def file(self, name):
        path = self._d.file(name)
        self.read["files"][str(name)] = _hash(path.read_bytes())
        return path

    def __getattr__(self, name):
        value = getattr(self._d, name)
        if name == "device_dict":
            return Keys(value, self.read["keys"])
        if isinstance(value, types.MethodType):
            return types.MethodType(value.__func__, self)  # its reads are noted too
        if not isinstance(value, Path):  # where a file is, not what the device is
            self.read["attributes"][name] = noted(value)
        return value


def changed(read, my_d):
    """The attributes and json keys noted in `read` that are now other in `my_d`."""
    differing = [
        name
        for name, value in read["attributes"].items()
        if noted(getattr(my_d, name, None)) != value
    ]
    for path, value in read["keys"].items():
        place = my_d.device_dict
        for step in path.split("."):
            place = place.get(step) if isinstance(place, dict) else None
        if noted(place) != value:
            differing.append(path)
    for name, value in read["files"].items():
        try:
            same = _hash(my_d.file(name).read_bytes()) == value
        except FileNotFoundError:
            same = False
        if not same:
            differing.append(name)
    return differing
