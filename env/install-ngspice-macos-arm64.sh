#!/usr/bin/env bash
set -euo pipefail

if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
    echo "This installer is only for native macOS arm64." >&2
    exit 1
fi

if [ -z "${CONDA_PREFIX:-}" ]; then
    echo "Activate the target conda environment before running this script." >&2
    exit 1
fi

version=${NGSPICE_VERSION:-46}
url=${NGSPICE_URL:-"https://downloads.sourceforge.net/project/ngspice/ng-spice-rework/${version}/ngspice-${version}.tar.gz"}
expected_sha256=${NGSPICE_SHA256:-"a0d1699af1940b06649276dcd6ff5a566c8c0cad01b2f7b5e99dedbb4d64c19b"}

if [ "$version" != "46" ] && [ -z "${NGSPICE_SHA256:-}" ]; then
    echo "Set NGSPICE_SHA256 when overriding NGSPICE_VERSION." >&2
    exit 1
fi

if [ -x "$CONDA_PREFIX/bin/ngspice" ] && [ "${1:-}" != "--force" ]; then
    if "$CONDA_PREFIX/bin/ngspice" -v 2>&1 | grep -q "ngspice-${version}"; then
        echo "ngspice ${version} is already installed in $CONDA_PREFIX"
        exit 0
    fi
fi

for tool in curl shasum tar make pkg-config; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "Missing required build tool: $tool" >&2
        exit 1
    fi
done

workdir=$(mktemp -d "${TMPDIR:-/tmp}/raser-ngspice.XXXXXX")
trap 'rm -rf "$workdir"' EXIT

tarball="$workdir/ngspice-${version}.tar.gz"
curl -L --fail --retry 3 -o "$tarball" "$url"

actual_sha256=$(shasum -a 256 "$tarball" | awk '{print $1}')
if [ "$actual_sha256" != "$expected_sha256" ]; then
    echo "ngspice source checksum mismatch:" >&2
    echo "  expected: $expected_sha256" >&2
    echo "  actual:   $actual_sha256" >&2
    exit 1
fi

tar -xzf "$tarball" -C "$workdir"
srcdir="$workdir/ngspice-${version}"

export PATH="$CONDA_PREFIX/bin:$PATH"
export CPPFLAGS="-I$CONDA_PREFIX/include ${CPPFLAGS:-}"
export LDFLAGS="-L$CONDA_PREFIX/lib -Wl,-rpath,$CONDA_PREFIX/lib ${LDFLAGS:-}"
export PKG_CONFIG_PATH="$CONDA_PREFIX/lib/pkgconfig:$CONDA_PREFIX/share/pkgconfig:${PKG_CONFIG_PATH:-}"

cd "$srcdir"
./configure \
    --prefix="$CONDA_PREFIX" \
    --with-x=no \
    --with-readline=yes \
    --enable-xspice \
    --disable-openmp \
    --disable-debug

jobs=${NGSPICE_MAKE_JOBS:-$(sysctl -n hw.ncpu 2>/dev/null || echo 2)}
make -j "$jobs"
make install

"$CONDA_PREFIX/bin/ngspice" -v
