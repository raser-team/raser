"""The Geant4 runtime: g4ppyy and the release of its global managers."""

import g4ppyy as g4b

from raser.supports import process


def _release():
    # g4ppyy creates both managers on import. Geant4 visualization keeps
    # pointers into the run manager; release it first.
    for name in ("VisExecutive", "RunManager"):
        manager = getattr(g4b._managers, name, None)
        if hasattr(manager, "__destruct__"):
            manager.__destruct__()
            setattr(g4b._managers, name, None)


process.at_process_end(_release)
