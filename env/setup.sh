# Setup raser runtime environment

[ -z "${PS1:-}" ] && echo "Setting up raser ..."

dir_raser=$(cd "$(dirname "$(dirname "${BASH_SOURCE[0]}")")" && pwd)
raser_mplconfigdir=${TMPDIR:-/tmp}/raser-matplotlib-$(id -u)
mkdir -p "$raser_mplconfigdir"
raser_in_container=
[ -n "${APPTAINER_CONTAINER:-}${SINGULARITY_CONTAINER:-}" ] && raser_in_container=1
raser_sif_host=
if [ -z "$raser_in_container" ]; then
    case "${RASER_ENV_ROUTE:-}" in
        ubuntu|el9) raser_sif_host=1 ;;
    esac
fi

root_prefix=
raser_conda_prefix=
[ -d "$dir_raser/.conda/envs/raser" ] && raser_conda_prefix=$dir_raser/.conda/envs/raser
geant4_prefix_hint=${RASER_GEANT4_INSTALL:-${GEANT4_INSTALL:-${GEANT4_DIR:-}}}
unset PYTHONHOME PYTHONPATH
raser_python_startup_path=$dir_raser/env/python-startup

if [ -z "$raser_sif_host" ] && [ -n "${RASER_LCG_VIEW:-}" ] && [ -r "$RASER_LCG_VIEW/setup.sh" ]; then
    . "$RASER_LCG_VIEW/setup.sh" || return $?
fi
geant4_config=
raser_conda_geant4=
raser_external_geant4=
if [ -z "$raser_sif_host$raser_in_container" ] && [ -n "${RASER_GEANT4_INSTALL:-}" ] && [ -x "$RASER_GEANT4_INSTALL/bin/geant4-config" ]; then
    # An explicit external Geant4 takes precedence over the one bundled in conda.
    geant4_config=$RASER_GEANT4_INSTALL/bin/geant4-config
    raser_external_geant4=1
elif [ -z "$raser_sif_host$raser_in_container" ] && [ -x "${CONDA_PREFIX:-}/bin/geant4-config" ]; then
    geant4_config=$CONDA_PREFIX/bin/geant4-config
    raser_conda_geant4=1
elif [ -n "$geant4_prefix_hint" ] && [ -x "$geant4_prefix_hint/bin/geant4-config" ]; then
    geant4_config=$geant4_prefix_hint/bin/geant4-config
elif command -v geant4-config >/dev/null 2>&1; then
    geant4_config=$(command -v geant4-config)
fi
if [ -n "$geant4_config" ]; then
    geant4_prefix=$("$geant4_config" --prefix 2>/dev/null) || return $?
else
    geant4_prefix=$geant4_prefix_hint
fi
[ -n "$geant4_prefix" ] && [ -d "$geant4_prefix" ] && geant4_prefix=$(cd "$geant4_prefix" && pwd -P)
if [ -n "$raser_sif_host" ]; then
    :
elif [ -n "$raser_conda_geant4" ]; then
    # Conda activation sets the G4*DATA variables of the bundled Geant4;
    # geant4.sh and geant4-config --sh name dataset directories it does not use.
    :
elif [ -x "$geant4_prefix/bin/geant4.sh" ]; then
    . "$geant4_prefix/bin/geant4.sh" || return $?
    if [ -x "$geant4_prefix/bin/geant4-config" ]; then
        raser_geant4_environment=$("$geant4_prefix/bin/geant4-config" --sh) || return $?
        eval "$raser_geant4_environment" || return $?
    fi
elif [ -n "$geant4_prefix" ]; then
    echo "Warning from raser setup: cannot find geant4.sh under $geant4_prefix" >&2
else
    echo "Warning from raser setup: put geant4-config on PATH, or set RASER_GEANT4_INSTALL, GEANT4_INSTALL, or GEANT4_DIR" >&2
fi

if [ -z "$raser_sif_host$raser_in_container" ] && [ -n "${RASER_GEANT4_INSTALL:-}" ] && [ -z "$raser_external_geant4" ]; then
    echo "Warning from raser setup: RASER_GEANT4_INSTALL=$RASER_GEANT4_INSTALL has no bin/geant4-config" >&2
fi
if [ -z "$raser_sif_host$raser_in_container" ] && [ -n "${RASER_ROOT_INSTALL:-}" ] && [ ! -x "$RASER_ROOT_INSTALL/bin/root-config" ]; then
    echo "Warning from raser setup: RASER_ROOT_INSTALL=$RASER_ROOT_INSTALL has no bin/root-config" >&2
fi
raser_external_root=
if [ -z "$raser_sif_host$raser_in_container" ] && [ -n "${RASER_ROOT_INSTALL:-}" ] && [ -x "$RASER_ROOT_INSTALL/bin/root-config" ]; then
    # An explicit external ROOT takes precedence over the one bundled in conda.
    root_prefix=$("$RASER_ROOT_INSTALL/bin/root-config" --prefix 2>/dev/null) || return $?
    raser_external_root=1
    if [ -r "$root_prefix/bin/thisroot.sh" ]; then
        . "$root_prefix/bin/thisroot.sh" || return $?
    fi
    case "$("$root_prefix/bin/root-config" --python-version 2>/dev/null)" in
        3.11*) ;;
        *) echo "Warning from raser setup: $root_prefix is not built for Python 3.11; PyROOT will not import" >&2 ;;
    esac
elif [ -n "${CONDA_PREFIX:-}" ] && [ -x "$CONDA_PREFIX/bin/root-config" ]; then
    root_prefix=$("$CONDA_PREFIX/bin/root-config" --prefix 2>/dev/null) || return $?
elif [ -z "$raser_in_container" ] && [ -n "$raser_conda_prefix" ] && [ -x "$raser_conda_prefix/bin/root-config" ]; then
    root_prefix=$("$raser_conda_prefix/bin/root-config" --prefix 2>/dev/null) || return $?
elif [ -n "$raser_in_container" ] && [ -n "${ROOTSYS:-}" ]; then
    root_prefix=$ROOTSYS
fi
if [ -n "$raser_in_container" ] && [ -n "${RASER_LCG_VIEW:-}" ] && [ -n "$root_prefix" ]; then
    raser_pythonpath=
    for venv_site in "${VIRTUAL_ENV:-}"/lib/python*/site-packages; do
        [ -d "$venv_site" ] && raser_pythonpath=$raser_pythonpath:$venv_site
    done
    PYTHONPATH=${raser_pythonpath#:}:$root_prefix/lib
fi

if [ -n "$raser_in_container" ] && [ -z "${RASER_LCG_VIEW:-}" ] && [ -n "${VIRTUAL_ENV:-}" ] && [ -d "$VIRTUAL_ENV/bin" ]; then
    PATH=$VIRTUAL_ENV/bin:$PATH
elif [ -z "$raser_in_container" ] && [ -z "$raser_sif_host" ]; then
    [ -n "$raser_conda_prefix" ] && [ -d "$raser_conda_prefix/bin" ] && PATH=$raser_conda_prefix/bin:$PATH
    [ -d "$dir_raser/.venv/bin" ] && PATH=$dir_raser/.venv/bin:$PATH
fi
if [ -n "$raser_in_container" ] && [ -z "${RASER_LCG_VIEW:-}" ]; then
    # Keep container runtime libraries ahead of externally mounted libraries so
    # Python extension modules, e.g. sqlite3, do not bind to an incompatible ABI.
    for system_lib in /lib/x86_64-linux-gnu /usr/lib/x86_64-linux-gnu; do
        [ -d "$system_lib" ] && LD_LIBRARY_PATH=$system_lib:${LD_LIBRARY_PATH:-}
    done
fi
# Python wheels on the conda route, e.g. gmsh, load OpenGL and X11 libraries
# from the environment.
if [ -z "$raser_sif_host$raser_in_container" ] && [ -d "${CONDA_PREFIX:-}/lib" ]; then
    LD_LIBRARY_PATH=$CONDA_PREFIX/lib:${LD_LIBRARY_PATH:-}
fi
if [ -n "$root_prefix" ]; then
    export ROOTSYS=$root_prefix
    for root_lib in "$root_prefix/lib64" "$root_prefix/lib"; do
        [ -d "$root_lib" ] && LD_LIBRARY_PATH=$root_lib:${LD_LIBRARY_PATH:-}
    done
else
    unset ROOTSYS
fi
# External installs go ahead of the conda environment, which may bundle its
# own ROOT and Geant4 libraries, executables and Python modules.
if [ -n "$raser_external_root" ] && [ -n "$raser_conda_geant4" ]; then
    echo "Warning from raser setup: the conda Geant4 was built with the conda ROOT; set RASER_GEANT4_INSTALL to a Geant4 matching $root_prefix" >&2
fi
if [ -n "$raser_external_root" ]; then
    PATH=$root_prefix/bin:$PATH
    PYTHONPATH=$root_prefix/lib${PYTHONPATH:+:$PYTHONPATH}
    LD_LIBRARY_PATH=$root_prefix/lib:${LD_LIBRARY_PATH:-}
    echo "raser setup: external ROOT $("$root_prefix/bin/root-config" --version) from $root_prefix" >&2
fi
if [ -n "$raser_external_geant4" ]; then
    PATH=$geant4_prefix/bin:$PATH
    for geant4_lib in "$geant4_prefix/lib" "$geant4_prefix/lib64"; do
        [ -d "$geant4_lib" ] && LD_LIBRARY_PATH=$geant4_lib:${LD_LIBRARY_PATH:-}
    done
    echo "raser setup: external Geant4 $("$geant4_prefix/bin/geant4-config" --version) from $geant4_prefix" >&2
fi
if [ -n "$raser_external_root$raser_external_geant4" ] && [ -d "$dir_raser/.venv/bin" ]; then
    PATH=$dir_raser/.venv/bin:$PATH
fi
if [ -d "$raser_python_startup_path" ]; then
    # env/python-startup contains version-gated Python startup hooks for external
    # packages whose import-time behavior depends on the selected route.
    PYTHONPATH=$raser_python_startup_path${PYTHONPATH:+:$PYTHONPATH}
fi
PYTHONPATH=$dir_raser/src:$dir_raser${PYTHONPATH:+:$PYTHONPATH}
export PATH PYTHONPATH LD_LIBRARY_PATH GEANT4_INSTALL=$geant4_prefix GEANT4_DIR=$geant4_prefix
export RASER_WORK_PATH=${RASER_WORK_PATH:-$dir_raser/work}
export RASER_COMPONENT_PATH=$dir_raser/src/raser/components
export RASER_SETTING_PATH=$RASER_COMPONENT_PATH OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=$raser_mplconfigdir

unalias raser raser-test mesh raser-shell raser-exec 2>/dev/null || true
unset -f raser raser-test mesh raser-shell raser-exec 2>/dev/null || true

if [ -n "$raser_sif_host" ]; then
    # Recheck inherited session mounts on the host that starts the container.
    raser_apptainer() (
        for raser_bind_name in APPTAINER_BIND APPTAINER_BINDPATH SINGULARITY_BIND SINGULARITY_BINDPATH BINDPATH RASER_SIF_BIND RASER_SIF_EXTRA_BINDS; do
            [ -n "${!raser_bind_name:-}" ] || continue
            IFS=, read -r -a raser_binds <<< "${!raser_bind_name}"
            raser_filtered_binds=
            for raser_bind in "${raser_binds[@]}"; do
                raser_bind_source=${raser_bind%%:*}
                if [[ ! -e "$raser_bind_source" && ( "$raser_bind_source" =~ ^/run/user/[0-9]+/?$ ||
                    ( -n "${XDG_RUNTIME_DIR:-}" && "${raser_bind_source%/}" = "${XDG_RUNTIME_DIR%/}" ) ) ]]; then
                    continue
                fi
                raser_filtered_binds=${raser_filtered_binds:+$raser_filtered_binds,}$raser_bind
            done
            unset "$raser_bind_name"
            [ -z "$raser_filtered_binds" ] || export "$raser_bind_name=$raser_filtered_binds"
        done
        apptainer "$@"
    )

    raser-shell() {
        if [ -z "${RASER_SIF_IMAGE:-}" ]; then
            echo "raser-shell: source env/setup_cvmfs.sh ubuntu or el9 first" >&2
            return 2
        fi
        local raser_shellrc
        raser_shellrc=$(mktemp "${TMPDIR:-/tmp}/raser-shellrc.XXXXXX") || return 1
        {
            printf 'cd %q || exit $?\n' "$dir_raser"
            printf '%s\n' '. env/setup.sh || exit $?'
            printf '%s\n' 'PS1="(raser) ${PS1:-\u@\h:\w\$ }"'
        } > "$raser_shellrc"
        raser_apptainer exec "$RASER_SIF_IMAGE" bash --rcfile "$raser_shellrc" -i
    }

    raser-exec() {
        if [ -z "${RASER_SIF_IMAGE:-}" ]; then
            echo "raser-exec: source env/setup_cvmfs.sh ubuntu or el9 first" >&2
            return 2
        fi
        raser_apptainer exec "$RASER_SIF_IMAGE" \
            bash -lc 'cd "$1" || exit $?; shift; . env/setup.sh || exit $?; exec "$@"' bash "$dir_raser" "$@"
    }

    raser() {
        # Cluster submissions planned in the SIF are queued and run on the host.
        local raser_submit_queue raser_submit_command raser_status raser_accepted=0
        raser_submit_queue=$(mktemp "${TMPDIR:-/tmp}/raser-submit.XXXXXX") || return 1
        if RASER_SUBMIT_QUEUE=$raser_submit_queue raser-exec python -m raser.cli.raser "$@"; then
            raser_status=0
        else
            raser_status=$?
            if [ -s "$raser_submit_queue" ]; then
                printf 'Command failed; no jobs submitted.\n' >&2
            fi
        fi
        while [ "$raser_status" -eq 0 ] && IFS= read -r raser_submit_command; do
            if eval "$raser_submit_command"; then
                raser_accepted=$((raser_accepted + 1))
            else
                raser_status=$?
            fi
        done < "$raser_submit_queue"
        if [ "$raser_status" -eq 0 ] || [ ! -s "$raser_submit_queue" ]; then
            rm -f "$raser_submit_queue"
        else
            local raser_pending_queue=$raser_submit_queue.pending raser_queued
            raser_queued=$(wc -l < "$raser_submit_queue")
            if [ "$raser_accepted" -gt 0 ]; then
                printf 'Cluster accepted indices [0..%s]; pending indices [%s..%s].\n' \
                    "$((raser_accepted - 1))" "$raser_accepted" "$((raser_queued - 1))" >&2
            else
                printf 'Cluster accepted indices []; pending indices [0..%s].\n' "$((raser_queued - 1))" >&2
            fi
            printf 'Original submission queue retained: %s\n' "$raser_submit_queue" >&2
            if tail -n "+$((raser_accepted + 1))" "$raser_submit_queue" > "$raser_pending_queue"; then
                printf 'Pending submission commands saved: %s\n' "$raser_pending_queue" >&2
            else
                printf 'Could not save pending commands; use the original queue from line %s.\n' \
                    "$((raser_accepted + 1))" >&2
            fi
        fi
        return "$raser_status"
    }

    raser-test() {
        raser-exec python -m pytest -m "not root and not devsim and not geant4 and not ngspice and not hardware and not slow" "$@"
    }

    mesh() {
        raser-exec python src/raser/components/detector "$@"
    }
else
    raser() {
        python -m raser.cli.raser "$@"
    }
    alias raser-test='python -m pytest -m "not root and not devsim and not geant4 and not ngspice and not hardware and not slow"'
    alias mesh="python src/raser/components/detector"
fi
