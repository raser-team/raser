import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest


SITE_CONDA = Path(
    "/cvmfs/common.ihep.ac.cn/software/anaconda/miniconda3-202505/etc/profile.d/conda.sh"
)


def _activate_conda_route(
    tmp_path: Path, active_prefix: str | None, bundled_geant4: bool = False
) -> tuple[dict[str, str], Path]:
    repo = tmp_path / "raser"
    env_dir = repo / "env"
    bin_dir = tmp_path / "bin"
    conda_base = tmp_path / "conda"
    project_env = repo / ".conda" / "envs" / "raser"
    env_dir.mkdir(parents=True)
    bin_dir.mkdir()
    (conda_base / "etc" / "profile.d").mkdir(parents=True)
    project_env.mkdir(parents=True)
    if bundled_geant4:
        (project_env / "bin").mkdir()
        geant4_config = project_env / "bin" / "geant4-config"
        geant4_config.write_text("#!/bin/sh\n")
        geant4_config.chmod(0o755)

    source = Path(__file__).parents[2] / "env" / "setup_cvmfs.sh"
    shutil.copy2(source, env_dir / "setup_cvmfs.sh")
    (env_dir / "setup.sh").write_text(":\n")
    conda = bin_dir / "conda"
    conda.write_text(f"#!/bin/sh\nprintf '%s\\n' {shlex.quote(str(conda_base))}\n")
    conda.chmod(0o755)
    (conda_base / "etc" / "profile.d" / "conda.sh").write_text(
        'conda() { [ "$1" = activate ] && export CONDA_PREFIX="$2"; }\n'
    )

    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("CONDA", "RASER_", "G4PPYY"))
    }
    env["PATH"] = f"{bin_dir}:/usr/bin:/bin"
    if active_prefix is not None:
        env["CONDA_PREFIX"] = active_prefix.format(conda_base=conda_base)
    result = subprocess.run(
        [
            "/bin/bash",
            "--noprofile",
            "--norc",
            "-c",
            f"set -e; source {shlex.quote(str(env_dir / 'setup_cvmfs.sh'))} conda; env -0",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    exported = dict(item.split("=", 1) for item in result.stdout.split("\0") if item)
    return exported, project_env


def test_conda_route_falls_back_to_local_conda(tmp_path: Path) -> None:
    if SITE_CONDA.is_file():
        pytest.skip("site conda route is available")

    exported, project_env = _activate_conda_route(tmp_path, None)

    assert exported["CONDA_PREFIX"] == str(project_env)


def test_conda_route_replaces_active_base_environment(tmp_path: Path) -> None:
    if SITE_CONDA.is_file():
        pytest.skip("site conda route is available")

    exported, project_env = _activate_conda_route(tmp_path, "{conda_base}")

    assert exported["CONDA_PREFIX"] == str(project_env)


def test_conda_route_with_bundled_geant4_skips_cvmfs_geant4(tmp_path: Path) -> None:
    if SITE_CONDA.is_file():
        pytest.skip("site conda route is available")

    exported, _ = _activate_conda_route(tmp_path, None, bundled_geant4=True)

    assert "RASER_GEANT4_INSTALL" not in exported
    assert "G4PPYY_INCLUDE_DIRS" not in exported


def test_conda_route_without_geant4_selects_cvmfs_geant4(tmp_path: Path) -> None:
    if SITE_CONDA.is_file():
        pytest.skip("site conda route is available")

    exported, _ = _activate_conda_route(tmp_path, None, bundled_geant4=False)

    assert exported["RASER_GEANT4_INSTALL"].startswith("/cvmfs/geant4.cern.ch/")
    assert exported["G4PPYY_INCLUDE_DIRS"].endswith("/include")


def test_el9_route_takes_root_from_lcg_view(tmp_path: Path) -> None:
    repo = tmp_path / "raser"
    (repo / "env").mkdir(parents=True)
    (repo / "bootstrap" / "el9").mkdir(parents=True)
    root = Path(__file__).parents[2]
    shutil.copy2(root / "env" / "setup_cvmfs.sh", repo / "env" / "setup_cvmfs.sh")
    shutil.copy2(
        root / "bootstrap" / "el9" / "setup_sif.sh",
        repo / "bootstrap" / "el9" / "setup_sif.sh",
    )
    (repo / "env" / "setup.sh").write_text(":\n")
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("G4", "GEANT4", "RASER_", "APPTAINER"))
    }

    result = subprocess.run(
        [
            "/bin/bash",
            "--noprofile",
            "--norc",
            "-c",
            f"source {shlex.quote(str(repo / 'env' / 'setup_cvmfs.sh'))} el9; env -0",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    exported = dict(item.split("=", 1) for item in result.stdout.split("\0") if item)
    binds = exported["APPTAINER_BINDPATH"].split(",")

    assert exported["APPTAINERENV_RASER_LCG_VIEW"].endswith("/x86_64-el9-gcc11-opt")
    assert binds.count(exported["RASER_LCG_VIEW"]) == 1
    assert "/cvmfs/sft.cern.ch/lcg/contrib" in binds
