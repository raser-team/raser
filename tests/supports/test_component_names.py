from pathlib import Path

import pytest

from raser.supports.paths import component_path
from raser.supports.paths import optional_component_path


# Deliberate change: the candidate taken when the file system says it exists.
# On a file system that tells capitals apart the misspelt name is not found
# either way; on one that does not, as of macOS, only the check finds it out.
def test_a_component_is_found_by_its_name_as_it_is_written(tmp_path: Path) -> None:
    library = tmp_path / "library"
    (library / "device").mkdir(parents=True)
    (library / "device" / "HPK-Si-PiN.json").write_text("{}")
    (library / "source" / "decay").mkdir(parents=True)
    (library / "source" / "decay" / "Sr90.json").write_text("{}")

    assert component_path("device", "HPK-Si-PiN.json", roots=[library]) == library / "device" / "HPK-Si-PiN.json"
    assert component_path("source", "decay/Sr90.json", roots=[library]) == library / "source" / "decay" / "Sr90.json"
    with pytest.raises(FileNotFoundError, match="Cannot find RASER component device/HPK-Si-PIN.json"):
        component_path("device", "HPK-Si-PIN.json", roots=[library])
    with pytest.raises(FileNotFoundError, match="Cannot find RASER component source/Decay/Sr90.json"):
        component_path("source", "Decay/Sr90.json", roots=[library])
    assert optional_component_path("device", "hpk-si-pin.json", roots=[library]) is None


def test_the_first_root_that_holds_the_component_gives_it(tmp_path: Path) -> None:
    project, library = tmp_path / "project", tmp_path / "library"
    for root in (project, library):
        (root / "device").mkdir(parents=True)
    (library / "device" / "a.json").write_text("{}")
    (library / "device" / "b.json").write_text("{}")
    (project / "device" / "b.json").write_text("{}")

    assert component_path("device", "a.json", roots=[project, library]) == library / "device" / "a.json"
    assert component_path("device", "b.json", roots=[project, library]) == project / "device" / "b.json"
