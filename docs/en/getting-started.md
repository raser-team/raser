# Getting started

> RASER 5.0 · Python 3.11 · Installation and use are separate steps

Install an environment once. In each new shell, activate one complete route
before running RASER. That route supplies a matched Python, ROOT, Geant4, and
ngspice runtime.

---

## 📦 Install an environment

Choose one route for the host platform. The commands in this section create
environments or images. Workflow commands appear under
[Run RASER](#run-raser).

Run the listed commands once for the selected platform. After that, activation
is one command per shell.

### Native Linux and WSL

With `conda` on `PATH`, one command creates `.conda/envs/raser` and the project
venv:

```bash
env/install_conda.sh
```

The script selects the conda specification for the host architecture. The conda
environment provides Python 3.11, ROOT, Geant4 11.3.2 with its datasets, and
ngspice; on x86-64 it also provides MKL, and on aarch64 `env/install-ngspice.sh`
builds ngspice into the environment. The project venv inherits those packages
and adds the Python packages pinned in `env/uv.txt`. In WSL, use this route in
the Linux distribution.

`env/install_conda.sh --without-geant4` leaves Geant4 out of the environment;
`--without-root` leaves out ROOT and Geant4, because the Geant4 Python bindings
use the cppyy that ROOT provides. [Use external ROOT or Geant4](#use-external-root-or-geant4)
describes how activation then finds them.

| Architecture | Conda specification | Explicit specification |
| --- | --- | --- |
| x86-64 | `env/conda-linux-x86.yml` | `env/conda-linux-64.lock` |
| aarch64 | `env/conda-linux-aarch64.yml` | `env/conda-linux-aarch64.lock` |

When exact conda artifacts are required, create the environment from the
explicit specification and then run the venv steps:

```bash
conda create -p .conda/envs/raser -c conda-forge --file env/conda-linux-64.lock
conda activate "$PWD/.conda/envs/raser"
uv venv --system-site-packages --python "$(command -v python3.11)" .venv
uv pip sync --python .venv/bin/python env/uv.txt
```

### IHEP computing cluster: Conda

On the cluster, source the conda shell integration below, then run the native
Linux installer:

```bash
source /cvmfs/common.ihep.ac.cn/software/anaconda/miniconda3-202505/etc/profile.d/conda.sh
env/install_conda.sh
```

### IHEP computing cluster: Ubuntu 22.04 SIF

```bash
apptainer build --mksquashfs-args '-processors 1' \
    img/raser_ubuntu.sif bootstrap/ubuntu/raser-ubuntu-sif.def
```

This image supplies the project Python environment, ngspice, and Ubuntu runtime
libraries. ROOT and Geant4 come from the matched `ubuntu2204` LCG view.

### IHEP computing cluster: EL9 SIF

```bash
apptainer build --mksquashfs-args '-processors 1' \
    img/raser_el9.sif bootstrap/el9/raser-el9-sif.def
```

This image supplies the project Python environment, ngspice, and EL9 runtime
libraries. ROOT comes from the matched `x86_64-el9` LCG view and Geant4 from the
external EL9 installation. Optional source archives may be cached under
`bootstrap/ingredients/`.

The single-processor squashfs option avoids thread-creation failures on
restricted cluster nodes. See the [container route notes](../../bootstrap/README.md)
for image-specific details.

### Native Apple Silicon

The pinned Python packages require macOS 14 or newer on arm64. ROOT and Geant4
11.3.2 with its datasets are provided by conda; ngspice is built into the conda
environment. The same installer and options cover this platform:

```bash
env/install_conda.sh
```

The matching explicit conda specification is also available; after creating the
environment from it, activate it and run `env/install-ngspice.sh` before the
venv steps:

```bash
conda create -p .conda/envs/raser -c conda-forge --file env/conda-macos-arm64.lock
```

For the Lima-based macOS route, build the Ubuntu SIF and use
`make run-raser-sif-macos`.

## 🔌 Activate a route

Activate exactly one route:

| Route | Command |
| --- | --- |
| Native conda | `source env/setup_cvmfs.sh conda` |
| Ubuntu 22.04 SIF | `source env/setup_cvmfs.sh ubuntu` |
| EL9 SIF | `source env/setup_cvmfs.sh el9` |
| Automatic local selection | `source env/setup_cvmfs.sh` |

Automatic selection prefers a local Ubuntu SIF, then a local EL9 SIF, and then
the conda route. The conda route loads the configured CVMFS profile when it is
available; otherwise it loads conda from `PATH`. It then activates
`.conda/envs/raser`, including when another conda environment is active.

### Use external ROOT or Geant4

On the conda route, an installation named before activation takes precedence
over the one in `.conda/envs/raser`, whether or not the environment includes
that package:

```bash
export RASER_ROOT_INSTALL=/path/to/root      # contains bin/root-config and bin/thisroot.sh; built for Python 3.11
export RASER_GEANT4_INSTALL=/path/to/geant4  # contains bin/geant4-config and bin/geant4.sh
source env/setup_cvmfs.sh conda
```

`RASER_ROOT_INSTALL` names a standalone ROOT installation, such as a CERN
binary release, an LCG release on CVMFS, or a source build. A ROOT package in
another conda environment runs only inside that activated environment.
Activation reports each external installation and its version, and warns when
an external ROOT meets the Geant4 bundled with the conda ROOT. An environment
installed with `--without-geant4` and no `RASER_GEANT4_INSTALL` uses the CVMFS
Geant4 11.3.p02 EL9 build.

The setup adds the project CLI, component search path, and `work/` location to
the active shell. Dependency installation occurs in the preceding environment
preparation step.

## 🚀 Run RASER

First verify the active route with the metadata commands:

```bash
raser --version
raser --help
```

Then run a workflow through the public CLI:

```bash
raser field -cv HPK-Si-PiN
raser signal HPK-Si-PiN
raser cce NJU-PiN
```

Use `raser <command> --help` for options. The public command is `raser`;
source-tree module paths remain implementation details.

## Validate a complete sensor chain

The following commands solve the Device field data and run the three primary
sensor-response applications with fixed operating values and random seeds:

```bash
source env/setup_cvmfs.sh conda
raser field HPK-Si-PiN -bias 200
raser field -wf HPK-Si-PiN -bias 200
raser signal HPK-Si-PiN decay/Sr90 -vol 200 --events-per-job 1 --seed 7
raser tct signal HPK-Si-PiN SPA_top_Si_IR -vol 200 --seed 7
raser timeres HPK-Si-PiN decay/Sr90 -vol 200 --events-per-job 100 --seed 7
```

Signal processes one Geant4 event. TCT calculates the laser-generated carrier
groups. Timeres processes 100 Geant4 events and writes the timing analysis.

## 🌳 Share environments with worktrees

Local SIF images and conda/venv directories are ignored runtime assets. Link a
worktree to the shared assets in the main checkout:

```bash
cd .worktrees/<name>
ln -s ../../img img
ln -s ../../.conda .conda
ln -s ../../.venv .venv
```

Run activation commands from the worktree root so paths resolve to that source
tree while the large runtime assets remain shared.

## 📌 Dependency policy

RASER omits `uv.lock` by policy. Direct Python dependencies stay readable in
`pyproject.toml`; the compact, pinned `env/uv.txt` defines deployed Python
packages and is consumed by native and SIF routes. Conda YAML and explicit spec
files define compiled dependencies. Generating `uv.lock` requires an explicit
policy change.
