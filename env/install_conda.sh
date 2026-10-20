#!/usr/bin/env bash
# Create the native conda route: a conda environment with ROOT, Geant4 and
# ngspice, plus the project venv pinned by env/uv.txt.
#
# --without-geant4 leaves Geant4 out; --without-root leaves out ROOT and Geant4,
# whose Python bindings use the cppyy that ROOT provides. Activation then takes
# them from RASER_GEANT4_INSTALL or RASER_ROOT_INSTALL.
set -euo pipefail

dir_raser=$(cd "$(dirname "$(dirname "${BASH_SOURCE[0]}")")" && pwd)
cd "$dir_raser"

prefix=$dir_raser/.conda/envs/raser
venv=$dir_raser/.venv
with_geant4=1
with_root=1
while [ $# -gt 0 ]; do
    case "$1" in
        --without-geant4) with_geant4= ;;
        --without-root) with_root= with_geant4= ;;
        *)
            echo "Usage: env/install_conda.sh [--without-geant4] [--without-root]" >&2
            exit 2
            ;;
    esac
    shift
done

case "$(uname -s)/$(uname -m)" in
    Linux/x86_64)
        spec=env/conda-linux-x86.yml
        build_ngspice=
        ;;
    Linux/aarch64)
        spec=env/conda-linux-aarch64.yml
        build_ngspice=1
        ;;
    Darwin/arm64)
        spec=env/conda-macos-arm64.yml
        build_ngspice=1
        ;;
    *)
        echo "No conda route for $(uname -s) $(uname -m)." >&2
        exit 1
        ;;
esac

conda_exe=${CONDA_EXE:-$(command -v conda || true)}
if [ -z "$conda_exe" ]; then
    echo "Put conda on PATH or source its conda.sh before running this script." >&2
    exit 1
fi
for target in "$prefix" "$venv"; do
    if [ -e "$target" ]; then
        echo "$target already exists; remove it to reinstall." >&2
        exit 1
    fi
done

spec_dir=$(mktemp -d "${TMPDIR:-/tmp}/raser-conda.XXXXXX")
trap 'rm -rf "$spec_dir"' EXIT
awk -v geant4="$with_geant4" -v root="$with_root" '
    !geant4 && /^  - geant4=/ { next }
    !root && /^  - root_base/ { next }
    { print }
' "$spec" > "$spec_dir/raser.yml"

# conda activation scripts, including the Geant4 dataset hooks, read unset variables.
set +u
eval "$("$conda_exe" shell.bash hook)"
conda env create -p "$prefix" -f "$spec_dir/raser.yml"
conda activate "$prefix"
set -u
if [ -n "$build_ngspice" ]; then
    env/install-ngspice.sh
fi
uv venv --system-site-packages --python "$(command -v python3.11)" "$venv"
uv pip sync --python "$venv/bin/python" env/uv.txt
