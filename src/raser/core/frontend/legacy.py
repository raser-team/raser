"""
@Date       : 2023
@Author     : Chenxi Fu
@version    : 2.0
"""

import subprocess

from raser.supports.output import create_path
from raser.supports.paths import component_path
from raser.supports.paths import project_path


def trans(name):
    create_path(project_path("frontend", name))
    ele_cir = component_path("afe", name + ".cir")
    subprocess.run(["ngspice", "-b", str(ele_cir)], shell=False, check=True)


def readout(name):
    create_path(project_path("frontend", name))
    from . import legacy_readout

    legacy_readout.main(name)
