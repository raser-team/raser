"""The Geant4 runtime: g4ppyy and the release of its global managers."""

from raser.supports import process
from raser.supports.dependency import MissingDependency

try:
    import g4ppyy as g4b
except ModuleNotFoundError as error:
    if error.name != "g4ppyy":
        raise
    raise MissingDependency(
        "Geant4's Python bindings, g4ppyy, are not installed in this Python",
        "Install them with uv pip install -r env/uv.txt, and Geant4 with "
        "env/install_conda.sh or by setting RASER_GEANT4_INSTALL to a Geant4 installation",
    ) from error


def _release():
    # g4ppyy creates both managers on import. Geant4 visualization keeps
    # pointers into the run manager; release it first.
    for name in ("VisExecutive", "RunManager"):
        manager = getattr(g4b._managers, name, None)
        if hasattr(manager, "__destruct__"):
            manager.__destruct__()
            setattr(g4b._managers, name, None)


process.at_process_end(_release)
