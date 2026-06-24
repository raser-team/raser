# RASER Linux x86 Bootstrap

This bootstrap follows the repository environment split:

- `env/uv-linux-x86.txt` locks the uv-managed Python environment.
- The SIF route does not install or use conda.
- ROOT and Geant4 are expected from the external site environment when available.

Build with Apptainer:

    apptainer build raser_latest.sif bootstrap/linux_x86/raser-linux-reference.def

The image creates `/opt/raser-venv` with uv and syncs the locked Python
requirements into it.

Run on lxlogin with the site ROOT/Geant4 runtime:

    source env/setup.sh lxlogin
    apptainer exec --bind /cvmfs,$PWD,/scratchfs2 --env-file .raser/env raser_latest.sif \
        python -m src.raser signal HPK-Si-PiN

`G4PPYY_LOAD_VIS=1` opts back into g4ppyy's Jupyter/K3D visualization imports.
