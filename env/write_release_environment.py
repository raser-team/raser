"""Write the conda environment file of a release for Linux x86-64.

    python env/write_release_environment.py [output]

The file installs ROOT, Geant4 with its data and ngspice from conda-forge,
the pinned Python packages of env/uv.txt and the released raser from PyPI:

    conda env create -f raser-<version>-linux-x86.yml

Its conda packages are those of env/conda-linux-x86.yml without uv and git,
which only the repository route needs. The version is the __version__ of
src/raser/__init__.py. The default output is raser-<version>-linux-x86.yml
in the current directory.
"""

import re
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
CONDA_SPEC = REPOSITORY / "env" / "conda-linux-x86.yml"
PIP_PINS = REPOSITORY / "env" / "uv.txt"
VERSION_FILE = REPOSITORY / "src" / "raser" / "__init__.py"
REPOSITORY_ONLY = {"uv", "git"}


def version():
    found = re.search(r'^__version__ = "([^"]+)"$', VERSION_FILE.read_text(), re.M)
    if found is None:
        sys.exit(f"No __version__ = \"...\" line in {VERSION_FILE}")
    return found.group(1)


def conda_packages():
    lines = CONDA_SPEC.read_text().splitlines()
    if "dependencies:" not in lines:
        sys.exit(f"No dependencies: list in {CONDA_SPEC}")
    packages = []
    for line in lines[lines.index("dependencies:") + 1 :]:
        if not line.strip():
            continue
        if not line.startswith("  - "):
            sys.exit(f"Unexpected line in the dependencies of {CONDA_SPEC}: {line!r}")
        package = line[4:].strip()
        if re.split(r"[=<> ]", package)[0] not in REPOSITORY_ONLY:
            packages.append(package)
    return packages


def pip_pins():
    return [line.strip() for line in PIP_PINS.read_text().splitlines() if line.strip()]


def main():
    release = version()
    output = Path(sys.argv[1] if len(sys.argv) > 1 else f"raser-{release}-linux-x86.yml")
    lines = ["name: raser", "channels:", "  - conda-forge", "  - nodefaults", "dependencies:"]
    lines += [f"  - {package}" for package in conda_packages()]
    lines += ["  - pip", "  - pip:"]
    lines += [f"    - {pin}" for pin in pip_pins()]
    lines += [f"    - raser=={release}"]
    output.write_text("\n".join(lines) + "\n")
    print(output)


if __name__ == "__main__":
    main()
