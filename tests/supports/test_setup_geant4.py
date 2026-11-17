import os
import shlex
import shutil
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).parents[2]
GEANT4_CONFIG = """#!/bin/sh
case "$1" in
    --prefix) printf '%s\\n' {prefix} ;;
    --sh) printf 'export G4ENSDFSTATEDATA={prefix}/share/Geant4/data/G4ENSDFSTATE3.0\\n' ;;
esac
"""


def _install_geant4(prefix: Path) -> None:
    (prefix / "bin").mkdir(parents=True)
    config = prefix / "bin" / "geant4-config"
    config.write_text(GEANT4_CONFIG.format(prefix=shlex.quote(str(prefix))))
    config.chmod(0o755)
    geant4_sh = prefix / "bin" / "geant4.sh"
    geant4_sh.write_text(
        f"export G4ENSDFSTATEDATA={shlex.quote(str(prefix))}/share/Geant4/data/G4ENSDFSTATE3.0\n"
    )
    geant4_sh.chmod(0o755)


def _source_setup(tmp_path: Path, env: dict[str, str]) -> dict[str, str]:
    repo = tmp_path / "raser"
    (repo / "env").mkdir(parents=True)
    shutil.copy2(REPOSITORY_ROOT / "env" / "setup.sh", repo / "env" / "setup.sh")
    result = subprocess.run(
        [
            "/bin/bash",
            "--noprofile",
            "--norc",
            "-c",
            f"source {shlex.quote(str(repo / 'env' / 'setup.sh'))} >/dev/null; env -0",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return dict(item.split("=", 1) for item in result.stdout.split("\0") if item)


def _conda_route_env(conda_prefix: Path) -> dict[str, str]:
    conda_prefix.mkdir(parents=True, exist_ok=True)
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(
            ("G4", "GEANT4", "RASER_", "APPTAINER", "SINGULARITY", "CONDA", "ROOTSYS")
        )
    }
    env.update(
        CONDA_PREFIX=str(conda_prefix),
        PATH=f"{conda_prefix / 'bin'}:/usr/bin:/bin",
        RASER_ENV_ROUTE="conda",
    )
    return env


def _install_root(prefix: Path, python_version: str) -> None:
    (prefix / "bin").mkdir(parents=True)
    (prefix / "lib").mkdir()
    config = prefix / "bin" / "root-config"
    config.write_text(
        "#!/bin/sh\n"
        'case "$1" in\n'
        f"    --prefix) printf '%s\\n' {shlex.quote(str(prefix))} ;;\n"
        f"    --python-version) printf '%s\\n' {python_version} ;;\n"
        "    --version) printf '6.34.10\\n' ;;\n"
        "esac\n"
    )
    config.chmod(0o755)


def test_conda_route_keeps_bundled_geant4_dataset_paths(tmp_path: Path) -> None:
    conda_prefix = tmp_path / "conda-env"
    _install_geant4(conda_prefix)
    conda_dataset = conda_prefix / "share" / "Geant4" / "data" / "ENSDFSTATE3.0"
    unrelated = tmp_path / "other-geant4"
    _install_geant4(unrelated)
    env = _conda_route_env(conda_prefix)
    env.update(G4ENSDFSTATEDATA=str(conda_dataset), GEANT4_DIR=str(unrelated))

    result = _source_setup(tmp_path, env)

    assert result["G4ENSDFSTATEDATA"] == str(conda_dataset)
    assert result["GEANT4_DIR"] == str(conda_prefix)


def test_external_geant4_takes_precedence_over_bundled(tmp_path: Path) -> None:
    conda_prefix = tmp_path / "conda-env"
    _install_geant4(conda_prefix)
    (conda_prefix / "lib").mkdir()
    external = tmp_path / "cvmfs-geant4"
    _install_geant4(external)
    (external / "lib64").mkdir()
    env = _conda_route_env(conda_prefix)
    env["RASER_GEANT4_INSTALL"] = str(external)

    result = _source_setup(tmp_path, env)

    assert result["GEANT4_DIR"] == str(external)
    assert result["G4ENSDFSTATEDATA"] == str(
        external / "share" / "Geant4" / "data" / "G4ENSDFSTATE3.0"
    )
    path = result["PATH"].split(":")
    assert path.index(str(external / "bin")) < path.index(str(conda_prefix / "bin"))
    assert result["LD_LIBRARY_PATH"].split(":")[0] == str(external / "lib64")


def test_conda_route_without_geant4_uses_external_install(tmp_path: Path) -> None:
    external = tmp_path / "cvmfs-geant4"
    _install_geant4(external)
    env = _conda_route_env(tmp_path / "conda-env")
    env["RASER_GEANT4_INSTALL"] = str(external)

    result = _source_setup(tmp_path, env)

    assert result["GEANT4_DIR"] == str(external)
    assert result["G4ENSDFSTATEDATA"] == str(
        external / "share" / "Geant4" / "data" / "G4ENSDFSTATE3.0"
    )


def test_external_root_takes_precedence_over_bundled(tmp_path: Path) -> None:
    conda_prefix = tmp_path / "conda-env"
    _install_root(conda_prefix, "3.11")
    external_root = tmp_path / "root"
    _install_root(external_root, "3.11")
    env = _conda_route_env(conda_prefix)
    env["RASER_ROOT_INSTALL"] = str(external_root)

    result = _source_setup(tmp_path, env)

    assert result["ROOTSYS"] == str(external_root)
    path = result["PATH"].split(":")
    assert path.index(str(external_root / "bin")) < path.index(
        str(conda_prefix / "bin")
    )
    assert result["LD_LIBRARY_PATH"].split(":")[0] == str(external_root / "lib")
    python_path = result["PYTHONPATH"].split(":")
    assert str(external_root / "lib") in python_path
    assert str(conda_prefix / "lib") not in python_path


def test_external_root_with_bundled_geant4_is_reported(tmp_path: Path) -> None:
    conda_prefix = tmp_path / "conda-env"
    _install_geant4(conda_prefix)
    external_root = tmp_path / "root"
    _install_root(external_root, "3.11")
    repo = tmp_path / "raser"
    (repo / "env").mkdir(parents=True)
    shutil.copy2(REPOSITORY_ROOT / "env" / "setup.sh", repo / "env" / "setup.sh")
    env = _conda_route_env(conda_prefix)
    env["RASER_ROOT_INSTALL"] = str(external_root)

    result = subprocess.run(
        [
            "/bin/bash",
            "--noprofile",
            "--norc",
            "-c",
            f"source {shlex.quote(str(repo / 'env' / 'setup.sh'))}",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert "conda Geant4 was built with the conda ROOT" in result.stderr
