"""Look at the Geant4 geometry of a job, with the tracks of a few events."""

from __future__ import annotations

import os

from raser.supports.paths import component_path

from .simulate_deposits import g4_configuration
from .simulate_deposits import tilted

# Drivers that write a file and open no window.
_DRIVERS_WITHOUT_SESSION = {
    "DAWNFILE",
    "HEPREPFILE",
    "K3DJUPYTER",
    "MPLJUPYTER",
    "TSG",
    "TSG_FILE",
    "TSG_OFFSCREEN",
    "VRML2FILE",
}
_TSG_DRIVERS = {"TSG", "TSG_FILE", "TSG_OFFSCREEN"}


def view_geometry(
    my_d,
    source: dict,
    g4setup: dict | None,
    events: int,
    g4_seed: int,
    driver: str,
    output: str | None = None,
) -> None:
    """Draw the device, the objects of the g4setup and `events` events.

    driver is a Geant4 visualization driver (OGL, TSG_OFFSCREEN, ...); one
    that Geant4 cannot open is an error. A driver with a window opens a
    session and returns when it is closed. output is the path of the
    picture without its extension, for the TSG and OGL drivers only; None
    writes no picture. The macros
    g4macro/init_vis.mac, vis.mac and vis_pcb.mac are found among the
    components. No deposits are returned.
    """
    tsg = driver.upper() in _TSG_DRIVERS
    if output and not tsg and not driver.upper().startswith("OGL"):
        raise ValueError(
            f"the driver {driver!r} writes no picture to a given path; "
            "use a TSG or an OGL driver, or no output"
        )
    # g4ppyy creates the Geant4 managers when imported.
    from raser.core.deposit.geant4.g4ppyy_runtime import g4b

    from .geant4.interaction import GeneralG4Interaction, _release_cppyy_ownership

    def command(text: str) -> None:
        status = g4b.G4UImanager.GetUIpointer().ApplyCommand(text)
        if status != 0:
            raise RuntimeError(f"Geant4 refused the command {text!r} (status {status})")

    class ViewedG4Interaction(GeneralG4Interaction):
        def beam_on(self):
            vis_manager = g4b.cppyy.gbl.G4VVisManager.GetConcreteInstance()
            if not vis_manager:
                vis_manager = g4b.G4VisExecutive()
                vis_manager.Initialize()
            self.visManager = vis_manager
            command(f"/vis/open {driver}")
            if self.geant4_model == "gdml_import":
                command(f"/control/execute {component_path('g4macro', 'vis_pcb.mac')}")
            else:
                command(f"/control/execute {component_path('g4macro', 'init_vis.mac')}")
                command(f"/control/execute {component_path('g4macro', 'vis.mac')}")
            if output and tsg:
                command("/vis/tsg/offscreen/set/format zb_png")
                command(f"/vis/tsg/offscreen/set/file {output}.png")
            elif output:
                command("/vis/viewer/set/background 1 1 1")
                command("/vis/ogl/set/printMode vectored")
                command("/vis/ogl/set/printSize 2000 2000")
                command(f"/vis/ogl/set/printFilename {output}")

            self.g4RunManager.BeamOn(self.generated_events)

            command("/vis/viewer/flush")
            if output and tsg:
                command("/vis/viewer/rebuild")
            elif output:
                command("/vis/ogl/export")

    # The session of a driver with a window must exist before the run
    # manager, in the current working directory.
    session = None
    if driver.upper() not in _DRIVERS_WITHOUT_SESSION:
        session = g4b.G4UIExecutive(1, [os.getcwd()])
    my_g4 = ViewedG4Interaction(
        my_d,
        tilted(g4_configuration(source, g4setup, None, None, None, generated=events), my_d.l_z),
        g4_seed,
    )
    try:
        if session is not None:
            session.SessionStart()
    finally:
        _release_cppyy_ownership(my_g4.visManager)
        my_g4.visManager = None
        my_g4.close()
