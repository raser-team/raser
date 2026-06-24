# RASER Bootstrap Routes

The repository default for personal Linux use is the native conda route in the
top-level `README.md`. The bootstrap directory keeps container routes for
cluster or isolated deployments.

`ubuntu/raser-ubuntu-sif.def` builds the Ubuntu22.04 SIF route. It uses a
Python 3.11 project venv, installs ngspice from Ubuntu packages, and relies on
the ubuntu2204 LCG view for the matched ROOT and Geant4 ABI chain. Source the
site setup once to prepare binds and shell commands:

    apptainer build --mksquashfs-args '-processors 1' \
        img/raser_ubuntu.sif bootstrap/ubuntu/raser-ubuntu-sif.def
    source env/setup_cvmfs.sh ubuntu
    raser signal HPK-Si-PiN

Optional build tarballs for routes that need local source or binary archives
can be cached in `bootstrap/ingredients/`. The single-processor squashfs option
avoids `mksquashfs` thread creation failures seen on restricted cluster nodes.

`el9/raser-el9-sif.def` builds the EL9 SIF route. It installs ROOT, ngspice,
and the runtime libraries needed by the external EL9 Geant4 build, including
Motif, Qt, OpenGL, HDF5, and TBB. It has the same route-local setup entrypoint:

    apptainer build --mksquashfs-args '-processors 1' \
        img/raser_el9.sif bootstrap/el9/raser-el9-sif.def
    source env/setup_cvmfs.sh el9
    raser signal HPK-Si-PiN
