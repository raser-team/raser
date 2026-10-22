# RASER container routes

> Maintainer index for Apptainer build assets

This directory contains the SIF definitions used by cluster and isolated
deployments. User-facing build, activation, and runtime instructions live in
the [documentation index](../docs/README.md).

---

## 📦 Routes

| Route | Definition | Runtime contract |
| --- | --- | --- |
| Ubuntu 22.04 | `ubuntu/raser-ubuntu-sif.def` | Project Python and ngspice in the image; ROOT and Geant4 from the matched `ubuntu2204` LCG view |
| EL9 | `el9/raser-el9-sif.def` | Project Python, ROOT, ngspice, and supporting libraries in the image; Geant4 from the external EL9 installation |

The route-specific setup scripts under `ubuntu/` and `el9/` prepare container
binds and runtime paths. `env/setup_cvmfs.sh` is the public activation entry
point and selects one complete route.

## 🧱 Build inputs

Optional source or binary archives may be cached under `ingredients/`. Keep
large generated SIF images under the repository-local, ignored `img/`
directory; do not commit them.

Use the single-processor squashfs option documented in the getting-started
guide on restricted cluster nodes where `mksquashfs` cannot create worker
threads.
