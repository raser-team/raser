"""The solved field that a run of a device takes.

Fields are in <project>/field: the one of the device as it is in that folder,
those of a scanned irradiation flux in folders inside it. run.json of each
records the flux, what the solve read from the device, and what is solved.
"""

import importlib.util
import json

from raser.supports.paths import project_path

from .reading import changed

# The full and the semi_fast mode of a field are solved with devsim. Where
# it is not installed the mode is the fast one, unless another is asked.
HAS_DEVSIM = importlib.util.find_spec("devsim") is not None
DEFAULT_MODE = "full" if HAS_DEVSIM else "fast"


def _flux(record):
    """The flux a field was solved at: its option, else that of its device."""
    asked = record["options"]["irradiation_flux"]
    if asked is not None:
        return float(asked)
    irradiation = record["files"]["device"].get("irradiation", {})
    return float(irradiation.get("irradiation_flux", 0))


def solved_field(my_d, voltage, irradiation_flux, mode=DEFAULT_MODE):
    """The folder of the field of `my_d` at this flux, found in this mode,
    that holds the potential and the weighting field at this bias. An error
    says what is missing."""
    root = project_path("field")
    again = f"raser field {my_d.det_name} -bias {voltage} --mode {mode}"
    records = {
        path.parent: json.loads(path.read_text())
        for path in [root / "run.json", *sorted(root.glob("*/run.json"))]
        if path.is_file()
    }
    at_flux = {
        folder: record
        for folder, record in records.items()
        if "options" in record
        and _flux(record) == float(irradiation_flux)
        and record["options"].get("mode") == mode
    }
    if not at_flux:
        have = sorted(
            {(_flux(record), str(record["options"].get("mode"))) for record in records.values() if "options" in record}
        )
        raise FileNotFoundError(
            f"no {mode} field of {my_d.det_name} at the irradiation flux {irradiation_flux:g} "
            f"in {root} (flux and mode of those solved: {have}); "
            f"solve it with `{again} -irr {irradiation_flux:g}`"
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


def solved_capacitance(folder, voltage):
    """The capacitance [F] of the device at this bias, as the field in
    `folder` gives it: the specific capacitance of the mesh times the area
    factor of the device. An error says what is missing."""
    record = json.loads((folder / "run.json").read_text())
    name = record["files"]["device"]["det_name"]
    solved = record.get("solved", {}).get("capacitance", [])
    if float(voltage) not in solved:
        raise FileNotFoundError(
            f"the field in {folder} has no capacitance at {voltage} V "
            f"(solved at: {solved}); solve it with `raser field {name} -cv {voltage}`"
        )
    point = json.loads((folder / f"{float(voltage)}V.cv.json").read_text())
    return float(point["specific_capacitance_pF"]) * float(point["area_factor"]) * 1e-12


def solved_undepleted(folder, voltage):
    """The undepleted bulk of a planar device at this bias, as the field in
    `folder` gives it: (resistance [Ohm], capacitance [F]) of that layer for
    the area factor of the device, or None when the device is fully depleted.
    An error says what is missing."""
    record = json.loads((folder / "run.json").read_text())
    device = record["files"]["device"]
    solved = record.get("solved", {}).get("undepleted", [])
    if float(voltage) not in solved:
        raise FileNotFoundError(
            f"the field in {folder} has no undepleted bulk at {voltage} V (solved at: {solved}): "
            f"it is stored for a field in one dimension; solve it with `raser field {device['det_name']} -bias {voltage}`"
        )
    layer = json.loads((folder / f"{float(voltage)}V.undepleted.json").read_text())
    if not layer["undepleted_width_um"]:
        return None
    area = float(device.get("area_factor", 1.0))
    return float(layer["specific_resistance_ohm_cm2"]) / area, float(layer["specific_capacitance_pF"]) * area * 1e-12
