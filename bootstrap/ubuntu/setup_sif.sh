#!/usr/bin/env bash
dir_raser=$(cd "$(dirname "$(dirname "$(dirname "${BASH_SOURCE[0]}")")")" && pwd)

raser_local_sif_image=$dir_raser/img/raser_ubuntu.sif
if [ -z "${RASER_SIF_IMAGE:-}" ]; then
    if [ -f "$raser_local_sif_image" ]; then
        export RASER_SIF_IMAGE=$raser_local_sif_image
    else
        export RASER_SIF_IMAGE=/afs/ihep.ac.cn/users/f/fucx/raser/img/raser_ubuntu.sif
    fi
fi
geant4_prefix=${RASER_GEANT4_INSTALL:-${GEANT4_INSTALL:-${GEANT4_DIR:-}}}
if [ -z "$geant4_prefix" ]; then
    echo "Warning from raser Ubuntu SIF setup: set RASER_GEANT4_INSTALL, GEANT4_INSTALL, or GEANT4_DIR" >&2
fi
[ -n "${RASER_CLHEP_PREFIX:-}" ] && export G4PPYY_INCLUDE_DIRS=${G4PPYY_INCLUDE_DIRS:-$RASER_CLHEP_PREFIX/include}
[ -n "${RASER_CLHEP_PREFIX:-}" ] && export G4PPYY_LIBRARY_DIRS=${G4PPYY_LIBRARY_DIRS:-$RASER_CLHEP_PREFIX/lib}

raser_sif_bind=$dir_raser
[ -n "$geant4_prefix" ] && raser_sif_bind=$raser_sif_bind,$geant4_prefix
[ -n "${RASER_LCG_VIEW:-}" ] && raser_sif_bind=$raser_sif_bind,$RASER_LCG_VIEW
[ -n "${RASER_GEANT4_DATA:-}" ] && raser_sif_bind=$raser_sif_bind,$RASER_GEANT4_DATA
[ -n "${RASER_GEANT4_DEP_PREFIX:-}" ] && [ "${RASER_GEANT4_DEP_PREFIX:-}" != "${RASER_LCG_VIEW:-}" ] && raser_sif_bind=$raser_sif_bind,$RASER_GEANT4_DEP_PREFIX
[ -n "${RASER_CLHEP_PREFIX:-}" ] && raser_sif_bind=$raser_sif_bind,$RASER_CLHEP_PREFIX
[ -n "${RASER_SIF_EXTRA_BINDS:-}" ] && raser_sif_bind=$raser_sif_bind,$RASER_SIF_EXTRA_BINDS
[ -z "${RASER_CLHEP_PREFIX:-}" ] && [ -n "${G4PPYY_INCLUDE_DIRS:-}" ] && raser_sif_bind=$raser_sif_bind,$G4PPYY_INCLUDE_DIRS
[ -z "${RASER_CLHEP_PREFIX:-}" ] && [ -n "${G4PPYY_LIBRARY_DIRS:-}" ] && raser_sif_bind=$raser_sif_bind,$G4PPYY_LIBRARY_DIRS
[ -d /tmp/.X11-unix ] && raser_sif_bind=$raser_sif_bind,/tmp/.X11-unix
[ -n "${XAUTHORITY:-}" ] && [ -e "$XAUTHORITY" ] && raser_sif_bind=$raser_sif_bind,$XAUTHORITY
[ -z "${XAUTHORITY:-}" ] && [ -e "$HOME/.Xauthority" ] && raser_sif_bind=$raser_sif_bind,$HOME/.Xauthority
[ -n "${XDG_RUNTIME_DIR:-}" ] && [ -d "$XDG_RUNTIME_DIR" ] && raser_sif_bind=$raser_sif_bind,$XDG_RUNTIME_DIR
export RASER_SIF_BIND=${RASER_SIF_BIND:-$raser_sif_bind}
if [ -n "${APPTAINER_BINDPATH:-}" ]; then
    export APPTAINER_BINDPATH=$APPTAINER_BINDPATH,$RASER_SIF_BIND
else
    export APPTAINER_BINDPATH=$RASER_SIF_BIND
fi
export IMGFILE=$RASER_SIF_IMAGE BINDPATH=$APPTAINER_BINDPATH

export APPTAINERENV_RASER_GEANT4_INSTALL=$geant4_prefix
export APPTAINERENV_GEANT4_INSTALL=$geant4_prefix
export APPTAINERENV_GEANT4_DIR=$geant4_prefix
[ -n "${RASER_LCG_VIEW:-}" ] && export APPTAINERENV_RASER_LCG_VIEW=$RASER_LCG_VIEW
[ -n "${DISPLAY:-}" ] && export APPTAINERENV_DISPLAY=$DISPLAY
[ -n "${XAUTHORITY:-}" ] && export APPTAINERENV_XAUTHORITY=$XAUTHORITY
[ -n "${G4PPYY_INCLUDE_DIRS:-}" ] && export APPTAINERENV_G4PPYY_INCLUDE_DIRS=$G4PPYY_INCLUDE_DIRS
[ -n "${G4PPYY_LIBRARY_DIRS:-}" ] && export APPTAINERENV_G4PPYY_LIBRARY_DIRS=$G4PPYY_LIBRARY_DIRS
raser_sif_ld_library_path=
[ -n "$geant4_prefix" ] && [ -d "$geant4_prefix/lib64" ] && raser_sif_ld_library_path=$geant4_prefix/lib64
[ -n "$geant4_prefix" ] && [ -d "$geant4_prefix/lib" ] && raser_sif_ld_library_path=$raser_sif_ld_library_path:$geant4_prefix/lib
[ -n "${G4PPYY_LIBRARY_DIRS:-}" ] && raser_sif_ld_library_path=$raser_sif_ld_library_path:$G4PPYY_LIBRARY_DIRS
[ -n "${RASER_SIF_LD_LIBRARY_PATH:-}" ] && raser_sif_ld_library_path=$raser_sif_ld_library_path:$RASER_SIF_LD_LIBRARY_PATH
export APPTAINERENV_LD_LIBRARY_PATH=${APPTAINERENV_LD_LIBRARY_PATH:-$raser_sif_ld_library_path}
