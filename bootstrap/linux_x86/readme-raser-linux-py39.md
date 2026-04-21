# RASER 3.19 Linux Reference Workflow

This directory contains a validated Linux x86 reference workflow for running RASER with:

- external ROOT
- external Geant4
- geant4_pybind as the Geant4 Python interface
- Python 3.9
- devsim
- local editable installation of raser
- Apptainer/Singularity container as the primary runtime wrapper

This workflow is intended as the current reference implementation for the new technical route:

- keep ROOT and Geant4 outside the container
- use geant4_pybind as the Geant4 Python binding layer
- keep the Python runtime and core Python dependencies reproducible inside the container
- validate the core workflow first on Linux x86
- use this Linux workflow as the baseline for future Windows/macOS/native adaptations

================================================================================
1. Current status
================================================================================

The following have been validated on Linux x86:

Local / interactive validation:
- Python 3.9.18 inside container
- geant4_pybind 0.1.2
- devsim
- raser editable install
- external ROOT 6.36.x
- external Geant4 11.2.x
- python -m raser --help
- python -m raser field -h
- python -m raser signal -h
- python -m raser field HPK-Si-PiN

Cluster / batch validation:
- python -m raser field HPK-Si-PiN
- batch execution through scheduler
- output written successfully to external writable host directory

This means the Linux reference workflow is not just importable, but already able to run the core field chain successfully in both interactive and batch-style environments.

Signal initialization has also been exercised, but the full signal chain still requires additional debugging for native/runtime issues in some environments.

================================================================================
2. Technical route
================================================================================

The validated route is:

- external ROOT
- external Geant4
- Python 3.9 runtime inside container
- geant4_pybind as the Geant4 binding layer
- devsim for field/device-related calculations
- raser installed from source
- writable output directory bind-mounted from host

This workflow does not use the old driver as the core interface layer.

The current reference pattern is:

- container provides Python runtime and Python dependencies
- host provides ROOT and Geant4
- host output directory is bind-mounted into the container
- source / setting directories are bind-mounted into the container

================================================================================
3. External dependencies
================================================================================

The following components are expected to be provided externally on the host side.

ROOT
----

Validated versions:

- ROOT 6.36.08 (local)
- ROOT 6.36.04 (system-layout host installation)

Important:

- PyROOT must match the target Python major/minor version
- it is not enough that root-config exists
- the ROOT Python bindings must be usable with Python 3.9 for this workflow

Two host-side ROOT layouts have been encountered:

1. Dedicated external ROOT prefix
   Example:
       /opt/root
       ~/root-py310
   This is the simplest case.

2. System-layout ROOT
   Example:
       root-config --prefix -> /usr
       libraries under /usr/lib64/root
       Python package under /usr/lib64/python3.9/site-packages/ROOT

For system-layout ROOT, direct binding of /usr as /opt/root is not recommended. Instead, the required ROOT Python/runtime pieces should be exposed explicitly.

Geant4
------

Validated versions:

- Geant4 11.2.2 (local)
- Geant4 11.2.1 (cluster/system installation)

Geant4 is kept external and accessed through geant4_pybind.

================================================================================
4. Python environment
================================================================================

Validated Python runtime inside container:

- Python 3.9.18

The container environment includes:

- geant4_pybind
- devsim
- raser
- common runtime dependencies listed in requirements-linux-py39-lock.txt

Recommended dependency file:

- requirements-linux-py39-lock.txt: full frozen runtime dependencies for the validated Python 3.9 workflow

The current workflow is based on Python 3.9, not Python 3.10.

================================================================================
5. Repository / working layout
================================================================================

Recommended local layout:

    ~/raser3.19/
    ├── README.txt
    ├── bootstrap/
    │   └── raser-linux-reference-py39-pybind.def
    ├── requirements-linux-py39-lock.txt
    ├── wheels/
    │   └── geant4_pybind-0.1.2-cp39-cp39-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl
    └── raser-src/

Typical runtime bind layout:

    host source tree      -> /work
    host writable output  -> /opt/py39-venv/raser
    host output mirror    -> /work/output
    host Geant4           -> /opt/geant4
    host ROOT runtime     -> host-dependent

================================================================================
6. Container / runtime concept
================================================================================

The current reference container is designed around:

- Python runtime inside container
- Python dependencies inside container
- Geant4 kept external
- ROOT kept external
- writable output kept external

This means the container is not fully self-contained. It is a reproducible Python runtime wrapper around host scientific libraries.

Why this route is used:

- external ROOT and Geant4 are large and often already managed by host sites
- geant4_pybind provides the intended Geant4 Python interface
- containerizing Python + Python packages gives better reproducibility
- host-provided ROOT/Geant4 keeps the workflow lighter and easier to adapt

================================================================================
7. Installation notes
================================================================================

7.1 Python 3.9
--------------

The validated workflow now uses Python 3.9.18 inside container.

The earlier Python 3.10 route was useful during local prototyping, but the current validated reference route has been updated to Python 3.9 in order to match the available geant4_pybind wheel and host-side PyROOT compatibility more naturally.

7.2 ROOT / Python version matching
----------------------------------

ROOT must be usable with Python 3.9 for this workflow.

If PyROOT is built against the wrong Python version, import ROOT will fail even if root-config exists.

7.3 Editable installation of RASER
----------------------------------

RASER source is installed in editable mode inside the container environment.

7.4 Writable output directory is mandatory
------------------------------------------

RASER writes output under paths rooted at:

    /opt/py39-venv/raser/output/...

Since the container image is read-only, a writable host directory must be bind-mounted to:

    /opt/py39-venv/raser

Without this, field/signal runs will fail with read-only filesystem errors.

7.5 signal expects ./output
---------------------------

In addition to the writable output bind above, some signal paths expect field outputs under:

    ./output/field/<detector_name>/

Therefore, when running signal, it is recommended to also bind:

    host_output/output -> /work/output

This keeps both:
- RASER default output path
- relative ./output lookup path

consistent.

7.6 Build the container
-----------------------

The reference image should be built with the following command:

    apptainer build raser_latest.sif raser-linux-reference-py39-pybind.def

For consistency across local and cluster workflows, the generated image is expected to be named:

    raser_latest.sif

If a different output filename is used during local testing, it should be renamed back to:

    raser_latest.sif

before using the standard setup scripts or shared workflow documentation.

================================================================================
8. Verified commands
================================================================================

8.1 Environment checks
----------------------

    python -m raser --help
    python -m raser field -h
    python -m raser signal -h

8.2 Import verification
-----------------------

Interactive imports have been validated for:

    ROOT
    geant4_pybind
    devsim
    raser

8.3 Field workflow
------------------

Validated command:

    python -m raser field HPK-Si-PiN

This has been verified to complete successfully and generate field-related output files.

Example output includes:

    output/field/HPK-Si-PiN/Potential_200.0V.pkl
    output/field/HPK-Si-PiN/TrappingRate_n_200.0V.pkl
    output/field/HPK-Si-PiN/TrappingRate_p_200.0V.pkl
    output/field/HPK-Si-PiN/simIV0to200.0_picture.pdf
    output/field/HPK-Si-PiN/simIV0to200.0_picture.root

8.4 Batch / scheduler workflow
------------------------------

The field workflow has also been validated through scheduler submission on a Linux cluster environment, using the same container and host-library model.

8.5 Signal workflow
-------------------

Signal entry points have been validated at the CLI/help level.

A signal run for:

    python -m raser signal HPK-Si-PiN -vol 200

now correctly finds field output when the host output directory is bind-mounted both to:

    /opt/py39-venv/raser
    /work/output

However, deeper signal execution may still encounter native/runtime issues depending on the host Geant4 / pybind / ROOT combination. This part is still under active debugging.

================================================================================
9. Host-side ROOT usage notes
================================================================================

Two practical cases exist.

9.1 Dedicated external ROOT prefix
----------------------------------

This is the easiest case.

Example bind:

    --bind /path/to/root:/opt/root

In this setup, PyROOT and ROOT libraries are expected to be self-consistent under the same external prefix.

9.2 System-layout ROOT
----------------------

Some hosts install ROOT as part of the system layout, for example:

- root-config --prefix -> /usr
- libraries under /usr/lib64/root
- Python package under /usr/lib64/python3.9/site-packages/ROOT

In this case, binding /usr wholesale into the container as /opt/root is not recommended.

Instead, the validated approach is to expose only the necessary runtime pieces.

Typical required components include:

- ROOT Python package
- cppyy / cppyy_backend
- libcppyy.so
- libcppyy_backend.so
- ROOT libraries under /usr/lib64/root
- ROOT headers under /usr/include/root
- ROOT shared resources under /usr/share/root
- additional runtime libraries such as liburing.so.2 and libtbb.so.2

A small host-side shim directory containing only the required ROOT Python-side pieces can help avoid polluting the container Python environment with unrelated host packages such as host NumPy.

================================================================================
10. Known issues and notes
================================================================================

10.1 ROOT / Python version matching is mandatory
------------------------------------------------

If PyROOT is built against the wrong Python version, import ROOT will fail even if root-config exists.

10.2 signal depends on pre-generated field outputs
--------------------------------------------------

The signal workflow requires field-related .pkl outputs to be available before signal calculation.

10.3 Output path behavior matters
---------------------------------

Field writes into the default RASER output tree rooted at:

    /opt/py39-venv/raser/output/...

Signal may later look for field output under:

    ./output/field/<detector_name>/

Both paths must be aligned through bind mounts.

10.4 Headless plotting
----------------------

For Linux server / batch environments, the workflow uses:

    MPLBACKEND=Agg

This avoids GUI backend problems with matplotlib.

For stricter headless environments, it is also useful to define writable cache directories such as:

    MPLCONFIGDIR=/tmp/mplconfig
    XDG_CACHE_HOME=/tmp/xdg-cache

10.5 Font / image backend warnings
----------------------------------

In some server or batch environments, font cache and image-library related warnings may appear. These do not necessarily prevent the core field calculation from finishing.

10.6 Signal native/runtime issues
---------------------------------

The full signal workflow may still hit native/runtime issues in some host combinations, even when field runs successfully. This is currently still being debugged.

================================================================================
11. Files prepared for submission
================================================================================

The following items are suitable for version control / GitHub submission:

- bootstrap/raser-linux-reference-py39-pybind.def
- requirements-linux-py39-lock.txt
- raser-src/pyproject.toml
- wheels/geant4_pybind-0.1.2-cp39-cp39-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl
- this README.txt

If helper scripts are added for local or cluster execution, they may also be included.

================================================================================
12. Scope of this README
================================================================================

This README documents the Linux x86 reference workflow that has already been validated in both local and cluster-style environments.

It is not yet the final cross-platform release document for:
- Windows native
- macOS native
- Linux fully self-contained packaging

Instead, it records the currently validated baseline that future platform-specific workflows should follow.