# RASER Linux Bootstrap

This bootstrap follows the repository environment split:

- `env/uv.txt` locks the uv-managed Python environment.
- The reference SIF route does not install or use conda.
- Geant4 is expected from the external host environment.
- Native conda environments are separate self-managed routes for users who need
  host ROOT, ngspice, or MKL.

The Linux SIF route follows the builder architecture. Build it on x86_64 for an
x86_64 image, or on aarch64 for an arm64 image. It intentionally stays
independent from conda.

The macOS SIF entrypoint runs this Linux container route through Lima:

    make run-raser-sif-macos

Build with Apptainer:

    apptainer build raser_latest.sif bootstrap/linux/raser-linux-reference.def

The image creates `/opt/raser-venv` with uv, syncs the locked Python
requirements into it, and installs the system `ngspice` package.

Run with the external Geant4 runtime visible to `env/setup.sh`:

    source env/setup.sh
    apptainer exec --bind "$BINDPATH" --env-file .raser/env "$IMGFILE" \
        python -m src.raser signal HPK-Si-PiN

For users using a native self-managed route instead of SIF, create the conda
environment from the repository root before creating the Python virtual
environment:

    conda env create -p .conda/envs/raser -f env/conda-linux-x86.yml
    conda activate $PWD/.conda/envs/raser

That environment includes `root_base`, `ngspice`, and MKL on Linux x86.
Geant4 remains external by design: use the host-provided Geant4, or install
Geant4 from the official source distribution and set `RASER_GEANT4_INSTALL` to
its install prefix before running `env/setup.sh`.
