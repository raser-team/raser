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

Installation is intentionally explicit rather than one-click: run the listed
commands once for the selected platform. After that, activation is one command
per shell.

### Native Linux x86-64

The conda environment provides Python 3.11, ROOT, ngspice, and MKL. The project
venv inherits those system packages and adds the Python packages pinned in
`env/uv.txt`.

```bash
conda env create -p .conda/envs/raser -f env/conda-linux-x86.yml
conda activate "$PWD/.conda/envs/raser"
uv venv --system-site-packages --python "$(command -v python3.11)" .venv
uv pip sync --python .venv/bin/python env/uv.txt
```

The explicit conda specification is available when exact conda artifacts are
required:

```bash
conda create -p .conda/envs/raser -c conda-forge --file env/conda-linux-64.lock
```

The host or an external installation provides Geant4. The conda environment
provides the remaining native runtime.

### Ubuntu 22.04 cluster SIF

```bash
apptainer build --mksquashfs-args '-processors 1' \
    img/raser_ubuntu.sif bootstrap/ubuntu/raser-ubuntu-sif.def
```

This image supplies the project Python environment, ngspice, and Ubuntu runtime
libraries. ROOT and Geant4 come from the matched `ubuntu2204` LCG view.

### EL9 cluster SIF

```bash
apptainer build --mksquashfs-args '-processors 1' \
    img/raser_el9.sif bootstrap/el9/raser-el9-sif.def
```

This image supplies ROOT, ngspice, the project Python environment, and runtime
libraries matched to the external EL9 Geant4 installation. Optional source
archives may be cached under `bootstrap/ingredients/`.

The single-processor squashfs option avoids thread-creation failures on
restricted cluster nodes. See the [container route notes](../../bootstrap/README.md)
for image-specific details.

### Native Apple Silicon

The pinned Python packages require macOS 14 or newer on arm64. ROOT is provided
by conda; ngspice is built into the active conda environment.

```bash
conda env create -p .conda/envs/raser -f env/conda-macos-arm64.yml
conda activate "$PWD/.conda/envs/raser"
env/install-ngspice-macos-arm64.sh
uv venv --system-site-packages --python "$(command -v python3.11)" .venv
uv pip sync --python .venv/bin/python env/uv.txt
```

The matching explicit conda specification is also available:

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
available; otherwise it loads conda from `PATH` and activates
`.conda/envs/raser` automatically.

Outside the configured CVMFS site, make `geant4-config` visible on `PATH` or set
the external install prefix, then use the same one-command activation:

```bash
export RASER_GEANT4_INSTALL=/path/to/geant4-install
source env/setup_cvmfs.sh conda
```

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
