import subprocess
import sys

DRAW = """
import sys
import ROOT
from raser.core import seeding
from raser.core.frontend.toy_readout import Amplifier

def pulse(sign):
    histogram = ROOT.TH1F("", "", 200, 0, 2e-9)
    histogram.SetDirectory(ROOT.nullptr)
    for index in range(21, 61):
        histogram.SetBinContent(index, sign * 0.05e-6 * (60 - index))
    return histogram

seeding.seed_generators(1)
currents = [pulse(1), pulse(-1), pulse(1)]
Amplifier(currents, "Broad_Band_UCSC", CDet=30).draw_waveform(currents, sys.argv[1])
"""


def test_waveforms_of_all_electrodes_are_drawn(tmp_path):
    # in a process of its own: ROOT took the whole process down at the canvas
    # of the second electrode
    done = subprocess.run([sys.executable, "-c", DRAW, str(tmp_path)], check=False)

    assert done.returncode == 0
    assert sorted(path.name for path in tmp_path.glob("*.pdf")) == [
        "Broad_BandNo.1.pdf",
        "Broad_BandNo.2.pdf",
        "Broad_BandNo.3.pdf",
    ]
