"""Geant4's own drivers on the vis executive g4ppyy creates, which registers
only its Jupyter drivers."""

import os

# nickname -> the library of the graphics system, its header and its class.
# TSG_QT_GLES and OGL open a window on the Qt session of G4UIExecutive.
_SYSTEMS = {
    "TSG_OFFSCREEN": ("libG4ToolsSG", "G4ToolsSGOffscreen.hh", "G4ToolsSGOffscreen"),
    "TSG_QT_GLES": ("libG4ToolsSG", "G4ToolsSGQtGLES.hh", "G4ToolsSGQtGLES"),
    "OGL": ("libG4OpenGL", "G4OpenGLStoredQt.hh", "G4OpenGLStoredQt"),
    "VRML2FILE": ("libG4VRML", "G4VRML2File.hh", "G4VRML2File"),
    "ATREE": ("libG4Tree", "G4ASCIITree.hh", "G4ASCIITree"),
}
_registered: dict = {}


def register_driver(g4b, nickname: str) -> None:
    """Register the graphics system of `nickname` on g4ppyy's vis executive,
    once, and let /vis/open and /vis/sceneHandler/create take it. A nickname
    of none of these systems is left to Geant4."""
    key = nickname.upper()
    if key not in _SYSTEMS or key in _registered:
        return
    from g4ppyy._lazy_loader import _G4PREFIX

    cppyy = g4b.cppyy
    library, header, name = _SYSTEMS[key]
    suffix = ".dylib" if os.uname().sysname == "Darwin" else ".so"
    cppyy.load_library(os.path.join(_G4PREFIX, "lib", library + suffix))
    cppyy.include(header)
    system = getattr(cppyy.gbl, name)()
    system.__python_owns__ = False
    executive = g4b._managers.VisExecutive
    executive.RegisterGraphicsSystem(system)
    _registered[key] = system
    # the two commands took their list of drivers when the executive was
    # initialised: give them every nickname registered since
    nicknames = []
    systems = executive.GetAvailableGraphicsSystems()
    for i in range(systems.size()):
        system = systems[i]
        nicknames += [str(system.GetNickname()), *map(str, system.GetNicknames())]
    candidates = " ".join(dict.fromkeys(n for n in nicknames if n))
    for header_of_command in ("G4UIcommandTree.hh", "G4UIcommand.hh", "G4UIparameter.hh"):
        cppyy.include(header_of_command)
    tree = g4b.G4UImanager.GetUIpointer().GetTree()
    for path in ("/vis/open", "/vis/sceneHandler/create"):
        tree.FindPath(path).GetParameter(0).SetParameterCandidates(candidates)
