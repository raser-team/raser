import importlib
import sys

import pytest

from raser.supports.dependency import MissingDependency

RUNTIME = "raser.core.deposit.geant4.g4ppyy_runtime"


def test_geant4_runtime_without_g4ppyy_says_what_is_missing_and_how_to_get_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(sys.modules, RUNTIME, raising=False)
    monkeypatch.setitem(sys.modules, "g4ppyy", None)  # importing it now fails

    with pytest.raises(MissingDependency, match="g4ppyy") as missing:
        importlib.import_module(RUNTIME)
    assert "env/uv.txt" in missing.value.how
