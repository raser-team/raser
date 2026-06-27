# Repository Working Rules

- Treat environment, bootstrap, and runtime-path changes as forward-only. Do not roll them back or add fallback compatibility unless the user explicitly asks.
- Do not add legacy import compatibility shims while reorganizing modules.
- Keep `src/raser/` for installable, reusable RASER library code.
- Keep repository-local applications under top-level `apps/`; applications may import `raser`, but `raser` library modules must not import `apps`.
- The `raser` CLI may route to repository applications. CLI reachability does not make an application part of the installable library API.
- Scientific-computing internals must use explicit contracts and fail visibly when the contract is not met. Do not add capability-probing fallbacks, silent scalar fallbacks, or compatibility fallback paths inside physics/numerics code unless the user explicitly asks for that behavior.
- Simple 1D electric-field models must carry depletion-state parameters explicitly. Do not encode them as geometry-only linear profiles; below-depletion bias must leave an undepleted zero-field region unless a separate diffusion model is explicitly implemented.

## Environment Initialization

RASER's CVMFS setup prefers a local SIF image when one is available, then falls
back to the native conda route. Use conda for ROOT/ngspice/MKL where available
and uv for Python packages. The SIF routes are kept under `bootstrap/` for
cluster or containerized deployments.

When using git worktrees from this checkout, keep the SIF images and local
runtime environments in the main checkout's ignored `img/`, `.conda/`, and
`.venv/` directories. Link each worktree back to those shared paths, for
example `ln -s ../../img .worktrees/dev-3d-lgad/img`,
`ln -s ../../.conda .worktrees/dev-3d-lgad/.conda`, and
`ln -s ../../.venv .worktrees/dev-3d-lgad/.venv`. This lets
`env/setup_cvmfs.sh` find the same local runtime from every worktree without
copying large SIF or environment directories.

Geant4 is external to these routes. Before sourcing `env/setup.sh`, make
`geant4-config` visible on `PATH`, or set `RASER_GEANT4_INSTALL` to the Geant4
install prefix.

For the native Linux x86 conda route:

    conda env create -p .conda/envs/raser -f env/conda-linux-x86.yml
    conda activate $PWD/.conda/envs/raser
    uv venv --system-site-packages --python "$(command -v python3.11)" .venv
    uv pip install --python .venv/bin/python -r env/uv.txt
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
    uv pip install --python .venv/bin/python -r env/uv.txt

The matching explicit conda spec can be used instead of the YAML file:

    conda create -p .conda/envs/raser -c conda-forge --file env/conda-macos-arm64.lock

Before running RASER, work from the repository root:

    source env/setup.sh
    uv run python -m src.raser <option <option tag>>
