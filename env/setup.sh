# Setup raser runtime environment

[ -z "${PS1:-}" ] && echo "Setting up raser ..."

dir_raser=$(cd "$(dirname "$(dirname "${BASH_SOURCE[0]}")")" && pwd)
raser_state_dir=$dir_raser/.raser
mkdir -p "$raser_state_dir/matplotlib"
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
raser_ponytail_path=$dir_raser/env/ponytail

if [ -z "$raser_sif_host" ] && [ -n "${RASER_LCG_VIEW:-}" ] && [ -r "$RASER_LCG_VIEW/setup.sh" ]; then
    . "$RASER_LCG_VIEW/setup.sh"
fi
geant4_config=
if [ -n "$geant4_prefix_hint" ] && [ -x "$geant4_prefix_hint/bin/geant4-config" ]; then
    geant4_config=$geant4_prefix_hint/bin/geant4-config
elif command -v geant4-config >/dev/null 2>&1; then
    geant4_config=$(command -v geant4-config)
fi
if [ -n "$geant4_config" ]; then
    geant4_prefix=$("$geant4_config" --prefix 2>/dev/null)
else
    geant4_prefix=$geant4_prefix_hint
fi
[ -n "$geant4_prefix" ] && [ -d "$geant4_prefix" ] && geant4_prefix=$(cd "$geant4_prefix" && pwd -P)
if [ -n "$raser_sif_host" ]; then
    :
elif [ -x "$geant4_prefix/bin/geant4.sh" ]; then
    . "$geant4_prefix/bin/geant4.sh"
    [ -x "$geant4_prefix/bin/geant4-config" ] && eval "$("$geant4_prefix/bin/geant4-config" --sh)"
elif [ -n "$geant4_prefix" ]; then
    echo "Warning from raser setup: cannot find geant4.sh under $geant4_prefix" >&2
else
    echo "Warning from raser setup: put geant4-config on PATH, or set RASER_GEANT4_INSTALL, GEANT4_INSTALL, or GEANT4_DIR" >&2
fi

if [ -n "${CONDA_PREFIX:-}" ] && [ -x "$CONDA_PREFIX/bin/root-config" ]; then
    root_prefix=$("$CONDA_PREFIX/bin/root-config" --prefix 2>/dev/null)
elif [ -z "$raser_in_container" ] && [ -n "$raser_conda_prefix" ] && [ -x "$raser_conda_prefix/bin/root-config" ]; then
    root_prefix=$("$raser_conda_prefix/bin/root-config" --prefix 2>/dev/null)
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
if [ -n "$root_prefix" ]; then
    export ROOTSYS=$root_prefix
    for root_lib in "$root_prefix/lib64" "$root_prefix/lib"; do
        [ -d "$root_lib" ] && LD_LIBRARY_PATH=$root_lib:${LD_LIBRARY_PATH:-}
    done
else
    unset ROOTSYS
fi
if [ -d "$raser_ponytail_path" ]; then
    # env/ponytail contains version-gated Python startup hooks for external
    # packages whose import-time behavior depends on the selected route.
    PYTHONPATH=$raser_ponytail_path${PYTHONPATH:+:$PYTHONPATH}
fi
export PATH PYTHONPATH LD_LIBRARY_PATH GEANT4_INSTALL=$geant4_prefix GEANT4_DIR=$geant4_prefix
export RASER_SETTING_PATH=$dir_raser/setting OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=$raser_state_dir/matplotlib

if [ -n "$raser_sif_host" ]; then
    raser-shell() {
        if [ -z "${RASER_SIF_IMAGE:-}" ]; then
            echo "raser-shell: source env/setup_cvmfs.sh ubuntu or el9 first" >&2
            return 2
        fi
        mkdir -p "$raser_state_dir"
        local raser_shellrc=$raser_state_dir/shellrc
        {
            printf 'cd %q\n' "$dir_raser"
            printf '%s\n' '. env/setup.sh'
            printf '%s\n' 'PS1="(raser) ${PS1:-\u@\h:\w\$ }"'
        } > "$raser_shellrc"
        apptainer exec "$RASER_SIF_IMAGE" bash --rcfile "$raser_shellrc" -i
    }

    raser-exec() {
        if [ -z "${RASER_SIF_IMAGE:-}" ]; then
            echo "raser-exec: source env/setup_cvmfs.sh ubuntu or el9 first" >&2
            return 2
        fi
        apptainer exec "$RASER_SIF_IMAGE" \
            bash -lc 'cd "$1"; shift; . env/setup.sh; exec "$@"' bash "$dir_raser" "$@"
    }

    raser() {
        raser-exec python -m src.raser "$@"
    }

    raser-test() {
        raser-exec python -m unittest discover -v -s src/raser/tests "$@"
    }

    mesh() {
        raser-exec python setting/detector "$@"
    }
else
    alias raser="python -m src.raser"
    alias raser-test="python -m unittest discover -v -s raser/tests"
    alias mesh="python setting/detector"
fi
