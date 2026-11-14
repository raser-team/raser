"""The solved field that a run of a device takes.

Fields are in <project>/field: the one of the device as it is in that folder,
those of a scanned irradiation flux in folders inside it. run.json of each
records the flux, what the solve read from the device, and what is solved.
"""

import json

from raser.supports.paths import project_path

from .reading import changed


def _flux(record):
    """The flux a field was solved at: its option, else that of its device."""
    asked = record["options"]["irradiation_flux"]
    if asked is not None:
        return float(asked)
    irradiation = record["files"]["device"].get("irradiation", {})
    return float(irradiation.get("irradiation_flux", 0))


def solved_field(my_d, voltage, irradiation_flux):
    """The folder of the field of `my_d` at this flux that holds the potential
    and the weighting field at this bias. An error says what is missing."""
    root = project_path("field")
    again = f"raser field {my_d.det_name} -bias {voltage}"
    records = {
        path.parent: json.loads(path.read_text())
        for path in [root / "run.json", *sorted(root.glob("*/run.json"))]
        if path.is_file()
    }
    at_flux = {
        folder: record
        for folder, record in records.items()
        if "options" in record and _flux(record) == float(irradiation_flux)
    }
    if not at_flux:
        have = sorted({_flux(record) for record in records.values() if "options" in record})
        raise FileNotFoundError(
            f"no field of {my_d.det_name} at the irradiation flux {irradiation_flux:g} "
            f"in {root} (solved at: {have}); solve it with `{again} -irr {irradiation_flux:g}`"
        )
    folder, record = next(iter(at_flux.items()))
    differing = changed(record["read"], my_d) if "read" in record else ["nothing solved yet"]
    if differing:
        raise ValueError(
            f"the field in {folder} was solved for another device ({', '.join(differing)}); "
            f"solve it again with `{again}`"
        )
    solved = record.get("solved", {})
    if float(voltage) not in solved.get("potential", []):
        raise FileNotFoundError(
            f"the field in {folder} is not solved at {voltage} V "
            f"(solved at: {solved.get('potential', [])}); solve it with `{again}`"
        )
    if float(voltage) not in solved.get("weighting", []):
        raise FileNotFoundError(
            f"the field in {folder} has no weighting field at {voltage} V "
            f"(solved at: {solved.get('weighting', [])}); solve it with `{again} -wf`"
        )
    return folder
