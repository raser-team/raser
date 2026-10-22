import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest


SITE_CONDA = Path(
    "/cvmfs/common.ihep.ac.cn/software/anaconda/miniconda3-202505/etc/profile.d/conda.sh"
)


def test_conda_route_falls_back_to_local_conda(tmp_path: Path) -> None:
    if SITE_CONDA.is_file():
        pytest.skip("site conda route is available")

    repo = tmp_path / "raser"
    env_dir = repo / "env"
    bin_dir = tmp_path / "bin"
    conda_base = tmp_path / "conda"
    project_env = repo / ".conda" / "envs" / "raser"
    env_dir.mkdir(parents=True)
    bin_dir.mkdir()
    (conda_base / "etc" / "profile.d").mkdir(parents=True)
    project_env.mkdir(parents=True)

    source = Path(__file__).parents[2] / "env" / "setup_cvmfs.sh"
    shutil.copy2(source, env_dir / "setup_cvmfs.sh")
    (env_dir / "setup.sh").write_text(":\n")
    conda = bin_dir / "conda"
    conda.write_text(f"#!/bin/sh\nprintf '%s\\n' {shlex.quote(str(conda_base))}\n")
    conda.chmod(0o755)
    (conda_base / "etc" / "profile.d" / "conda.sh").write_text(
        'conda() { [ "$1" = activate ] && export CONDA_PREFIX="$2"; }\n'
    )

    result = subprocess.run(
        [
            "/bin/bash",
            "--noprofile",
            "--norc",
            "-c",
            f"set -e; source {shlex.quote(str(env_dir / 'setup_cvmfs.sh'))} conda; printf '%s' \"$CONDA_PREFIX\"",
        ],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": f"{bin_dir}:/usr/bin:/bin"},
    )

    assert result.stdout == str(project_env)
