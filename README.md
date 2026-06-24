RASER
======

**RA**diation **SE**miconducto**R** 

Welcome to Fork and contribute! 

link: <https://raser.team/docs/raser/> 

Citation: [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18905684.svg)](https://doi.org/10.5281/zenodo.18905684)

Prerequisites
======

RASER uses the CERN LCG view as the reference HEP runtime on lxlogin:

    export RASER_LCG_VIEW=${RASER_LCG_VIEW:-/cvmfs/sft.cern.ch/lcg/views/LCG_106a_geant4ext20241128/x86_64-el9-gcc11-opt}
    source env/setup.sh lxlogin

This view provides the matched CERN stack used by g4ppyy: Python 3.11.9, ROOT 6.32.08, and the runtime libraries used by Geant4 11.3.2. Geant4 itself is loaded from `/cvmfs/geant4.cern.ch/geant4/11.3.p02`, with data from `/cvmfs/geant4.cern.ch/share/data`.

Use conda for native tools that are not in the LCG view, and uv for Python packages:

    conda env create -p .conda/envs/raser -f env/conda.yml
    conda activate $PWD/.conda/envs/raser
    source env/setup.sh lxlogin
    uv venv --system-site-packages --python "$(command -v python3.11)" .venv
    uv pip sync --python .venv/bin/python env/uv-linux-x86.txt

Before Run
======

While running raser you need in the directory of raser.

run steps:

    source env/setup.sh # before run
    uv run python -m src.raser <option <option tag>>

update:

    git pull

For internal users on lxlogin, use env/setup.sh; it auto-detects lxlogin.
To force the lxlogin profile manually:

    source env/setup.sh lxlogin

Output
======

The output of raser will store inside <directory of raser>/output/ .

Run Options
======

checkout __main__.py for detail.

Tutorial
======

For signal simulation of 
    HPK-Si-PiN and HPK-Si-LGAD in 10.1016/j.nima.2024.169479 (under reorganization):

    raser field [-cv] <device_name in `setting/detector`>
    raser field -wf <device_name>
    raser signal <device_name>
    raser tct signal <device_name> <laser_name in `setting/laser`>

For time resolution of 
    NJU-PiN in 10.3389/fphy.2022.718071
    SICAR-1 in 10.1007/s41605-023-00431-y and 10.1109/TNS.2024.3471863:

    raser field [-cv] <device_name>
    raser field -wf <device_name>
    raser signal -s 20 <device_name>
    raser resolution <device_name>

For irradiation simulation of 
    ATLAS ITk-md8 and ITk-Si-strip in arXiv:2504.20463
    NJU-PiN in arXiv:2503.0901 6 (under reorganization):

    raser field [-cv] <device_name>
    raser field -wf <device_name>
    raser signal <device_name>
