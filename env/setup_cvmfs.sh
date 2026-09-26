#!/usr/bin/env bash
unset PYTHONHOME PYTHONPATH
dir_raser=$(cd "$(dirname "$(dirname "${BASH_SOURCE[0]}")")" && pwd)
raser_route=${1:-}
raser_conda_setup=/cvmfs/common.ihep.ac.cn/software/anaconda/miniconda3-202505/etc/profile.d/conda.sh

if [ -z "$raser_route" ]; then
    if [ -f "$dir_raser/img/raser_ubuntu.sif" ]; then
        raser_route=ubuntu
    elif [ -f "$dir_raser/img/raser_el9.sif" ]; then
        raser_route=el9
    elif [ -f "$raser_conda_setup" ]; then
        raser_route=conda
    else
        raser_route=conda
    fi
fi

case "$raser_route" in
    conda)
        raser_conda_ready=
        if [ -f "$raser_conda_setup" ]; then
            . "$raser_conda_setup"
            raser_conda_ready=1
        elif command -v conda >/dev/null 2>&1; then
            raser_conda_base=$(conda info --base 2>/dev/null)
            if [ -n "$raser_conda_base" ] && [ -f "$raser_conda_base/etc/profile.d/conda.sh" ]; then
                . "$raser_conda_base/etc/profile.d/conda.sh"
                raser_conda_ready=1
            fi
        fi
        if [ -n "$raser_conda_ready" ] && [ -d "$dir_raser/.conda/envs/raser" ] \
            && [ "$(cd "${CONDA_PREFIX:-/}" && pwd -P)" != "$(cd "$dir_raser/.conda/envs/raser" && pwd -P)" ]; then
            conda activate "$dir_raser/.conda/envs/raser"
        fi
        # An environment installed with --without-geant4 takes Geant4 from CVMFS.
        if [ ! -x "${CONDA_PREFIX:-}/bin/geant4-config" ]; then
            export RASER_GEANT4_INSTALL=${RASER_GEANT4_INSTALL:-/cvmfs/geant4.cern.ch/geant4/11.3.p02/x86_64-el9-gcc11-optdeb}
            export RASER_GEANT4_DATA=${RASER_GEANT4_DATA:-/cvmfs/geant4.cern.ch/share/data}
            export RASER_GEANT4_DEP_PREFIX=${RASER_GEANT4_DEP_PREFIX:-/cvmfs/sft.cern.ch/lcg/views/LCG_106a_geant4ext20241128/x86_64-el9-gcc11-opt}
            export RASER_CLHEP_PREFIX=${RASER_CLHEP_PREFIX:-/cvmfs/sft.cern.ch/lcg/releases/clhep/2.4.7.1-b7a7d/x86_64-el9-gcc11-opt}
        fi
        ;;
    ubuntu)
        export RASER_LCG_VIEW=${RASER_LCG_VIEW:-/cvmfs/sft.cern.ch/lcg/views/LCG_106a_geant4ext20241128/x86_64-ubuntu2204-gcc11-opt}
        export RASER_GEANT4_INSTALL=${RASER_GEANT4_INSTALL:-/cvmfs/sft.cern.ch/lcg/releases/Geant4/11.3.2-90e03/x86_64-ubuntu2204-gcc11-opt}
        export RASER_GEANT4_DATA=${RASER_GEANT4_DATA:-/cvmfs/geant4.cern.ch/share/data}
        export RASER_GEANT4_DEP_PREFIX=${RASER_GEANT4_DEP_PREFIX:-$RASER_LCG_VIEW}
        export RASER_CLHEP_PREFIX=${RASER_CLHEP_PREFIX:-/cvmfs/sft.cern.ch/lcg/releases/clhep/2.4.7.1-6b452/x86_64-ubuntu2204-gcc11-opt}
        export RASER_SIF_EXTRA_BINDS=${RASER_SIF_EXTRA_BINDS:-/cvmfs/sft.cern.ch/lcg/releases,/cvmfs/sft.cern.ch/lcg/contrib}
        . "$dir_raser/bootstrap/ubuntu/setup_sif.sh"
        ;;
    el9)
        export RASER_LCG_VIEW=${RASER_LCG_VIEW:-/cvmfs/sft.cern.ch/lcg/views/LCG_106a_geant4ext20241128/x86_64-el9-gcc11-opt}
        export RASER_GEANT4_INSTALL=${RASER_GEANT4_INSTALL:-/cvmfs/geant4.cern.ch/geant4/11.3.p02/x86_64-el9-gcc11-optdeb}
        export RASER_GEANT4_DATA=${RASER_GEANT4_DATA:-/cvmfs/geant4.cern.ch/share/data}
        export RASER_GEANT4_DEP_PREFIX=${RASER_GEANT4_DEP_PREFIX:-$RASER_LCG_VIEW}
        export RASER_CLHEP_PREFIX=${RASER_CLHEP_PREFIX:-/cvmfs/sft.cern.ch/lcg/releases/clhep/2.4.7.1-b7a7d/x86_64-el9-gcc11-opt}
        export RASER_SIF_EXTRA_BINDS=${RASER_SIF_EXTRA_BINDS:-/cvmfs/sft.cern.ch/lcg/releases,/cvmfs/sft.cern.ch/lcg/contrib}
        . "$dir_raser/bootstrap/el9/setup_sif.sh"
        ;;
    *)
        echo "Usage: source env/setup_cvmfs.sh [conda|ubuntu|el9]" >&2
        return 2 2>/dev/null || exit 2
        ;;
esac
if [ -n "${RASER_CLHEP_PREFIX:-}" ]; then
    export G4PPYY_INCLUDE_DIRS=${G4PPYY_INCLUDE_DIRS:-$RASER_CLHEP_PREFIX/include}
    export G4PPYY_LIBRARY_DIRS=${G4PPYY_LIBRARY_DIRS:-$RASER_CLHEP_PREFIX/lib}
fi
export RASER_ENV_ROUTE=$raser_route
. "$dir_raser/env/setup.sh"
