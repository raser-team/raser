# Setup raser environment

[ -z "$PS1" ] && echo "Setting up raser ..."

dir_raser=$(cd "$(dirname "$(dirname "${BASH_SOURCE[0]}")")" && pwd)
conda_prefix=${CONDA_PREFIX:-}
[ -z "$conda_prefix" ] && [ -d "$dir_raser/.conda/envs/raser" ] && conda_prefix=$dir_raser/.conda/envs/raser

geant4_prefix=${RASER_GEANT4_INSTALL:-${GEANT4_INSTALL:-${GEANT4_DIR:-}}}
if [ -z "$geant4_prefix" ] && command -v geant4-config >/dev/null 2>&1; then
    geant4_prefix=$(geant4-config --prefix 2>/dev/null)
fi
[ -n "$geant4_prefix" ] && [ -d "$geant4_prefix" ] && geant4_prefix=$(cd "$geant4_prefix" && pwd -P)
if [ -n "$geant4_prefix" ] && [ -x "$geant4_prefix/bin/geant4-config" ]; then
    . "$geant4_prefix/bin/geant4.sh"
else
    if [ -n "$geant4_prefix" ]; then
        echo "Warning from raser setup: cannot find geant4-config under $geant4_prefix" >&2
    else
        echo "Warning from raser setup: cannot find geant4-config; set RASER_GEANT4_INSTALL or add geant4-config to PATH" >&2
    fi
fi
[ -n "${VIRTUAL_ENV:-}" ] && export PATH=$VIRTUAL_ENV/bin:$PATH

if [ -n "$conda_prefix" ] && [ -x "$conda_prefix/bin/root-config" ]; then
    root_prefix=$("$conda_prefix/bin/root-config" --prefix 2>/dev/null)
else
    root_prefix=/usr/local/share/root_install
fi
root_python_paths="$root_prefix/lib64/python3.11/site-packages $root_prefix/lib/python3.11/site-packages"
export ROOTSYS=$root_prefix GEANT4_INSTALL=$geant4_prefix GEANT4_DIR=$geant4_prefix

if [ -n "${VIRTUAL_ENV:-}" ]; then
    for venv_site in "$VIRTUAL_ENV"/lib/python*/site-packages; do
        [ -d "$venv_site" ] || continue
        : > "$venv_site/raser-root.pth"
        for path in $root_python_paths; do
            [ -d "$path/ROOT" ] && echo "$path" >> "$venv_site/raser-root.pth"
        done
    done
fi

raser_state_dir=$dir_raser/.raser
mkdir -p "$raser_state_dir"
mkdir -p "$raser_state_dir/matplotlib"
cfg_env=$raser_state_dir/env
rm -f "$cfg_env"
cat > "$cfg_env" << EOF
# ROOT
ROOTSYS=$root_prefix

# Geant4
GEANT4_INSTALL=$geant4_prefix
GEANT4_DIR=$geant4_prefix
EOF

if [ -x "$geant4_prefix/bin/geant4-config" ]; then
    while read -r _ env_name path; do
        [ -z "$env_name" ] && continue
        if [ -d "$path" ]; then
            echo "$env_name=$path" >> "$cfg_env"
            export "$env_name=$path"
        else
            echo "Warning from raser setup: cannot resolve Geant4 dataset $env_name from $path" >&2
        fi
    done << EOF
$("$geant4_prefix/bin/geant4-config" --datasets 2>/dev/null)
EOF
fi

cat >> "$cfg_env" << EOF

# Python
PYTHONPATH=
LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-}
MPLCONFIGDIR=$raser_state_dir/matplotlib

#pyMTL3 Verilator
PYMTL_VERILATOR_INCLUDE_DIR="/usr/local/share/verilator/include"
EOF

IMGFILE=$dir_raser/img/raser_latest.sif
BINDPATH=$dir_raser,$geant4_prefix,/cvmfs/geant4.cern.ch/share/data,/cvmfs/sft.cern.ch/lcg
[ -n "${RASER_EXTRA_BINDPATH:-}" ] && BINDPATH=$BINDPATH,$RASER_EXTRA_BINDPATH
raser_test_path=raser/tests

clean_bindpath=
IFS=',' read -ra bind_items <<< "$BINDPATH"
for path in "${bind_items[@]}"; do
    if [ -L "$path" ]; then
        path=$(readlink -f "$path")
    elif [ ! -e "$path" ]; then
        [ -z "$PS1" ] && echo "Warning from raser setup: $path do not exist" >&2
        continue
    fi
    [ -z "$clean_bindpath" ] && clean_bindpath=$path || clean_bindpath=$clean_bindpath,$path
done
export IMGFILE BINDPATH=$clean_bindpath RASER_SETTING_PATH=$dir_raser/setting OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=$raser_state_dir/matplotlib

alias raser-shell="apptainer shell --env-file $cfg_env -B $BINDPATH $IMGFILE"
raser_exec="apptainer exec --env-file $cfg_env -B $BINDPATH $IMGFILE"
raser_python="$raser_exec /opt/raser/bin/python"
alias raser="$raser_python -m src.raser"
alias raser-test="$raser_python -m unittest discover -v -s $raser_test_path"
alias pytest="$raser_exec pytest"
alias raser-install="$raser_exec pip install -e ."
alias mesh="$raser_python setting/detector"
