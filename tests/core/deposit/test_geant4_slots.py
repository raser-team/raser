import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from raser.core.deposit.along_beam import parse_along_beam
from raser.supports.paths import component_path

pytestmark = pytest.mark.geant4

# One Geant4 run per process: each run here is a process of its own.
RUN = """
import json, sys
from raser.core.device.build_device import Detector
from raser.core.deposit.simulate_deposits import simulate_deposits
from raser.core.seeding import seed_generators

case = json.loads(sys.argv[1])
seed_generators(case["seed"])
devices = {}
for name, spec in case["devices"].items():
    if isinstance(spec, str):
        devices[name] = Detector(spec)
    else:
        from types import SimpleNamespace
        devices[name] = SimpleNamespace(**spec)
deposits = simulate_deposits(
    devices, case["source"], case["setup"], None, case["seed"],
    {name: tuple(window) for name, window in case["windows"].items()},
    case["require"], case["coincidence_window_ns"], False, generated=case["generated"],
)
fields = ("event", "detector", "x", "y", "z", "t", "e")
print("RESULT " + json.dumps([{f: getattr(e, f) for f in fields} for e in deposits.events]))
"""


def _simulate(case):
    done = subprocess.run(
        [sys.executable, "-c", RUN, json.dumps(case)],
        capture_output=True,
        text=True,
        check=False,
    )
    lines = [line for line in done.stdout.splitlines() if line.startswith("RESULT ")]
    assert lines, done.stdout[-2000:] + done.stderr[-2000:]
    return json.loads(lines[-1][len("RESULT ") :])


def _setup(column):
    return {
        "geant4_model": "device",
        "world": "G4_Galactic",
        "maxstep": 2,
        "objects": {},
        "source": {"angle": 0},
        "along_beam": column,
    }


@pytest.mark.parametrize("rotation_z", [0, 90, 180, 270])
@pytest.mark.parametrize("facing", ["upstream", "downstream"])
def test_a_pencil_beam_lands_in_a_slot_where_the_transform_says(
    facing, rotation_z
) -> None:
    device = {"l_x": 1000.0, "l_y": 600.0, "l_z": 50.0, "material": "Si"}
    # three beams along z at x, y [um] from the slot's offset: inside the
    # footprint of the device for rotation 0 and 180 only, for 90 and 270
    # only, and for all
    points = [(400.0, 0.0), (0.0, 400.0), (170.0, 120.0)]
    beam = {
        "kind": "beam",
        "par_type": "pi-",
        "par_energy": 10000.0,
        "particles": [{"offset": [30.0 + x, -20.0 + y, 0.0]} for x, y in points],
    }
    slot = {
        "slot": "ref",
        "facing": facing,
        "rotation_z": rotation_z,
        "offset": [30, -20],
    }
    setup = _setup(["source", {"gap": 500}, slot])
    placed = parse_along_beam(setup, {"ref": SimpleNamespace(**device)}).slots[0]
    # where each beam crosses the slot, in the coordinates of the device
    crossings = [placed.to_device(30.0 + x, -20.0 + y, 0) for x, y in points]
    inside = [
        0 <= c[0] <= device["l_x"] and 0 <= c[1] <= device["l_y"] for c in crossings
    ]
    assert inside[2] and inside[0] != inside[1]

    events = _simulate(
        {
            "seed": 1,
            "devices": {"ref": device},
            "source": beam,
            "setup": setup,
            "windows": {"ref": [None, None]},
            "require": "all",
            "coincidence_window_ns": None,
            "generated": 3,
        }
    )

    assert len(events) == 3
    for event in events:
        steps = list(zip(event["x"], event["y"]))
        for crossing, lands in zip(crossings, inside):
            near = [
                k
                for k, (x, y) in enumerate(steps)
                if abs(x - crossing[0]) < 5.0 and abs(y - crossing[1]) < 5.0
            ]
            # a beam that crosses the device leaves its steps there, and one
            # that misses leaves none
            assert bool(near) == lands
            if lands:
                # into the front face of a slot that faces upstream, into the
                # back of one that faces downstream
                first = min(near, key=lambda k: event["t"][k])
                assert event["z"][first] == pytest.approx(
                    0 if facing == "upstream" else 50, abs=2.1
                )
        assert min(event["z"]) >= 0 and max(event["z"]) <= 50


def test_two_slots_record_by_the_logic_over_them() -> None:
    from raser.core.device.build_device import Detector

    source = json.loads(component_path("source", "decay", "Sr90.json").read_text())
    source["par_radius"] = 200
    sizes = {"ref": Detector("HPK-Si-LGAD"), "dut": Detector("HPK-Si-PiN")}
    setup = _setup(
        ["source", {"gap": 3000}, {"slot": "ref"}, {"gap": 300}, {"slot": "dut"}]
    )

    def run(require):
        return _simulate(
            {
                "seed": 2,
                "devices": {"ref": "HPK-Si-LGAD", "dut": "HPK-Si-PiN"},
                "source": source,
                "setup": setup,
                "windows": {"ref": [None, None], "dut": [None, None]},
                "require": require,
                "coincidence_window_ns": None,
                "generated": 6000,
            }
        )

    both = run("ref AND dut")
    anyone = run("any")

    assert len(both) > 5
    for event in both:
        # a recorded event has the deposits of both slots, inside their devices
        assert set(event["detector"]) == {"ref", "dut"}
        for name, device in sizes.items():
            rows = [k for k, one in enumerate(event["detector"]) if one == name]
            assert all(-1e-6 <= event["x"][k] <= device.l_x + 1e-6 for k in rows)
            assert all(-1e-6 <= event["y"][k] <= device.l_y + 1e-6 for k in rows)
            assert all(-1e-6 <= event["z"][k] <= device.l_z + 1e-6 for k in rows)
            assert sum(event["e"][k] for k in rows) > 0
    assert len(anyone) >= len(both)
    # "any" adds events with deposits in one slot only
    assert any(len(set(event["detector"])) == 1 for event in anyone)

    # a slot that is not hit keeps its deposits in an event another slot makes
    # recorded: dut cannot be hit with a window above any energy it can get
    unhit = _simulate(
        {
            "seed": 2,
            "devices": {"ref": "HPK-Si-LGAD", "dut": "HPK-Si-PiN"},
            "source": source,
            "setup": setup,
            "windows": {"ref": [None, None], "dut": [1000.0, None]},
            "require": "ref OR dut",
            "coincidence_window_ns": None,
            "generated": 6000,
        }
    )
    assert any(set(event["detector"]) == {"ref", "dut"} for event in unhit)
    assert {event["event"] for event in unhit} == {
        event["event"] for event in anyone if "ref" in event["detector"]
    }
