RASER
======

**RA**diation **SE**miconducto**R** 

Welcome to Fork and contribute! 

link: <https://raser.team/docs/raser/> 

Citation: [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18905684.svg)](https://doi.org/10.5281/zenodo.18905684)

Prerequisites
======

RASER's CVMFS setup prefers a local SIF image when one is available, then falls
back to the native conda route. Use conda for ROOT/ngspice/MKL where available
and uv for Python packages. The SIF routes are kept under `bootstrap/` for
cluster or containerized deployments.

Geant4 is external to these routes. Before sourcing `env/setup.sh`, make
`geant4-config` visible on `PATH`, or set `RASER_GEANT4_INSTALL` to the Geant4
install prefix.

For the native Linux x86 conda route:

    conda env create -p .conda/envs/raser -f env/conda-linux-x86.yml
    conda activate $PWD/.conda/envs/raser
    uv venv --system-site-packages --python "$(command -v python3.11)" .venv
    uv sync --python .venv/bin/python --locked
    source env/setup_cvmfs.sh conda

For the Ubuntu22.04 LCG cluster SIF route:

    apptainer build --mksquashfs-args '-processors 1' \
        img/raser_ubuntu.sif bootstrap/ubuntu/raser-ubuntu-sif.def
    source env/setup_cvmfs.sh ubuntu
    raser signal HPK-Si-PiN

This route uses the ubuntu2204 LCG view for the matched Python 3.11, ROOT, and
Geant4 ABI chain. The SIF supplies the project Python environment, ngspice, and
the Ubuntu runtime libraries needed by the LCG binaries.

For the EL9 cluster SIF route:

    apptainer build --mksquashfs-args '-processors 1' \
        img/raser_el9.sif bootstrap/el9/raser-el9-sif.def
    source env/setup_cvmfs.sh el9
    raser signal HPK-Si-PiN

Optional build tarballs can be cached under `bootstrap/ingredients/`. See
`bootstrap/README.md` for route details. The single-processor squashfs option
avoids mksquashfs thread creation failures seen on restricted cluster nodes.

The native Linux x86 conda environment includes `root_base`, `ngspice`, and
MKL. This gives users without a site ROOT installation a working PyROOT matched
to Python 3.11.

The matching explicit conda spec can be used instead of the YAML file:

    conda create -p .conda/envs/raser -c conda-forge --file env/conda-linux-64.lock

Geant4 is intentionally not installed by conda. Use the Geant4 already provided
by the host environment, or install Geant4 from the official source
distribution and point RASER at it:

    export RASER_GEANT4_INSTALL=/path/to/geant4-install
    source env/setup.sh

For the macOS SIF route:

    make run-raser-sif-macos

For native Apple Silicon, use the macOS arm64 conda environment. It does not
install MKL; `root_base` is installed in the conda environment so PyROOT
matches Python 3.11, and ngspice is built from the official source tarball into
the active conda environment. The pinned Python packages require macOS 14 or
newer on arm64 because the devsim wheel is tagged `macosx_14_0_arm64`:

    conda env create -p .conda/envs/raser -f env/conda-macos-arm64.yml
    conda activate $PWD/.conda/envs/raser
    env/install-ngspice-macos-arm64.sh
    export RASER_GEANT4_INSTALL=/path/to/geant4-install
    source env/setup.sh
    uv venv --system-site-packages --python "$(command -v python3.11)" .venv
    uv sync --python .venv/bin/python --locked

The matching explicit conda spec can be used instead of the YAML file:

    conda create -p .conda/envs/raser -c conda-forge --file env/conda-macos-arm64.lock

Before Run
======

While running raser you need in the directory of raser.

run steps:

    source env/setup.sh # before run
    uv run python -m src.raser <option <option tag>>

update:

    git pull

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
