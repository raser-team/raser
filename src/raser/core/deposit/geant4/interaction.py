"""
Description:  interaction.py
@Date       : 2025
@Author     : Chenxi Fu (Original: Geant4)
@version    : 1.0
"""

from typing import Any

from raser.core.deposit.geant4.g4ppyy_runtime import g4b
from raser.supports.paths import component_path

from ..deposits import Deposits, deposits_of_steps, joined
from ..generation import too_few
from ..recording import RecordedSteps, parse_require
from .detector_construction import GeneralDetectorConstruction
from .action_initialization import GeneralActionInitialization
from .drivers import register_driver

g4b.include("G4RunManager.hh")
g4b.include("G4RadioactiveDecayPhysics.hh")
g4b.include("G4HadronicParameters.hh")

verbose = 0


def _release_cppyy_ownership(value):
    if isinstance(value, dict):
        for item in value.values():
            _release_cppyy_ownership(item)
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _release_cppyy_ownership(item)
        return
    if hasattr(value, "__python_owns__"):
        value.__python_owns__ = False


class GeneralG4Interaction:
    def __init__(
        self,
        devices,
        layout,
        g4_dic,
        g4_seed,
        g4_vis=False,
        MyDetectorConstruction=GeneralDetectorConstruction,
        MyActionInitialization=GeneralActionInitialization,
        picture=None,
        drawn=0,
    ):
        """
        Description:
            General Geant4 main process
            Simulate s_num particles through the devices
            Record the energy depositon in the devices
        Parameters:
            devices : dict
                the device of each slot, by the name of the slot
            layout : Layout
                where the slots and objects lie in the Geant4 world
                (raser.core.deposit.along_beam)
            g4_dic : dict
                Geant4 configuration: source, surroundings, total_events,
                windows [MeV], require and coincidence_window_ns, which
                decide the events that are recorded
        """
        # picture: the path, without its extension, of a png of the geometry
        # and the first `drawn` recorded events, drawn off screen during the
        # run; None or drawn 0 draws nothing
        self.picture = picture if drawn else None
        self.drawn = int(drawn)
        # g4_vis keeps its place among the arguments until the callers that
        # pass it by position are gone.
        if g4_vis:
            raise ValueError(
                "GeneralG4Interaction does not draw; use "
                "raser.core.deposit.view_geometry.view_geometry"
            )

        self.my_g4d: Any
        self.devices = devices
        self.layout = layout
        self.geant4_model = g4_dic["geant4_model"]

        if (
            self.geant4_model == "gdml_import"
            and MyDetectorConstruction is GeneralDetectorConstruction
        ):
            from .g4_gdml_import import GDMLDetectorConstruction

            my_d = devices["Device"]
            self.my_g4d = GDMLDetectorConstruction(
                my_d, g4_dic, my_d.material, g4_dic["maxstep"]
            )
        else:
            self.my_g4d = MyDetectorConstruction(devices, layout, g4_dic, g4_dic["maxstep"])

        self.g4RunManager = g4b.G4RunManager.GetRunManager() or g4b.G4RunManager()
        self.rand_engine = g4b.cppyy.gbl.CLHEP.RanecuEngine()
        g4b.cppyy.gbl.CLHEP.HepRandom.setTheEngine(self.rand_engine)
        g4b.cppyy.gbl.CLHEP.HepRandom.setTheSeed(g4_seed)
        self.g4RunManager.SetUserInitialization(self.my_g4d)

        # set physics list
        self.physics_list = g4b.FTFP_BERT()
        self.step_limiter_physics = g4b.G4StepLimiterPhysics()
        self.physics_list.RegisterPhysics(self.step_limiter_physics)
        # A source of nuclides: Geant4 decays them, whatever their lifetime.
        self.nuclides = g4_dic.get("nuclides")
        self.decay_physics = None
        if self.nuclides is not None:
            self.decay_physics = g4b.G4RadioactiveDecayPhysics()
            self.physics_list.RegisterPhysics(self.decay_physics)
            g4b.G4HadronicParameters.Instance().SetTimeThresholdForRadioactiveDecay(
                1.0e60 * g4b.year
            )
        self.g4RunManager.SetUserInitialization(self.physics_list)

        # the steps of the recorded events, in the coordinates of Geant4
        self.records = RecordedSteps(devices)

        # recorded_events: the run stops when this many events are recorded,
        # and total_events is the most it generates for them; None: the run
        # generates total_events.
        self.recorded_events = g4_dic.get("recorded_events")
        self.total_events = int(g4_dic["total_events"])
        self.windows = g4_dic["windows"]
        self.require = g4_dic["require"]
        self.coincidence_window_ns = g4_dic["coincidence_window_ns"]

        # define action
        self.action_initialization = MyActionInitialization(
            g4_dic["par_in"],
            g4_dic["par_out"],
            g4_dic.get("par_randx", 0),
            g4_dic.get("par_randy", 0),
            g4_dic.get("par_type"),
            g4_dic.get("par_energy"),
            self.records,
            self.windows,
            parse_require(self.require, list(devices)),
            self.coincidence_window_ns,
            self.geant4_model,
            **({"particles": g4_dic["particles"]} if "particles" in g4_dic else {}),
            **(
                {"recorded_events": self.recorded_events}
                if self.recorded_events is not None
                else {}
            ),
            **(
                {
                    "nuclides": {
                        "nuclides": self.nuclides,
                        "par_in": g4_dic["par_in"],
                        "par_out": g4_dic["par_out"],
                        "radius": g4_dic.get("par_radius", 0),
                        "cone": g4_dic.get("par_cone"),
                    }
                }
                if self.nuclides is not None
                else {}
            ),
        )
        self.g4RunManager.SetUserInitialization(self.action_initialization)

        self.beam_on()

        self._closed = False

    def beam_on(self):
        UImanager = g4b.G4UImanager.GetUIpointer()
        # reduce verbose from physics list
        UImanager.ApplyCommand("/process/em/verbose %d" % (verbose))
        UImanager.ApplyCommand("/process/had/verbose %d" % (verbose))
        UImanager.ApplyCommand("/run/initialize")
        if self.picture is not None:
            self._open_picture(UImanager)
        self.g4RunManager.BeamOn(self.total_events)
        if self.picture is not None:
            self._close_picture(UImanager)
        if self.recorded_events is None:
            self.generated_events = self.total_events
            return
        counted = self.action_initialization.event_action
        self.generated_events = counted.ended
        self.recorded = counted.recorded

    def _open_picture(self, ui):
        """Draw the geometry and the recorded events the event action keeps,
        off screen, into the picture."""

        def command(text):
            status = ui.ApplyCommand(text)
            if status != 0:
                raise RuntimeError(f"Geant4 refused the command {text!r} (status {status})")

        register_driver(g4b, "TSG_OFFSCREEN")
        self.action_initialization.event_action.drawn = self.drawn
        command("/vis/open TSG_OFFSCREEN")
        command("/vis/tsg/offscreen/set/format zb_png")
        command(f"/vis/tsg/offscreen/set/file {self.picture}.png")
        command(f"/control/execute {component_path('g4macro', 'vis.mac')}")
        command("/vis/drawOnlyToBeKeptEvents")
        command(f"/vis/scene/endOfEventAction accumulate {self.drawn}")

    def _close_picture(self, ui):
        ui.ApplyCommand("/vis/viewer/flush")
        ui.ApplyCommand("/vis/viewer/rebuild")
        ui.ApplyCommand("/vis/disable")

    def deposits(self):
        """The recorded events as Deposits, each step in the coordinates of
        the device of its slot. Fewer recorded events than asked for is an
        error, raised here and not in the run, so that the caller can still
        close this interaction."""
        if self.recorded_events is not None and self.recorded < self.recorded_events:
            raise too_few(self.recorded_events, self.recorded, self.generated_events)
        records = self.records
        per_detector = []
        for slot in self.devices:
            placed = self.layout.slot(slot)
            per_detector.append(
                deposits_of_steps(
                    slot,
                    records.events,
                    [[placed.to_device(*point) for point in event] for event in records.positions[slot]],
                    records.energies[slot],
                    records.times[slot],
                    [[placed.to_device(*point) for point in event] for event in records.starts[slot]],
                )
            )
        return Deposits(
            self.generated_events,
            self.windows,
            self.require,
            self.coincidence_window_ns,
            joined(per_detector),
        )

    def close(self):
        if self._closed:
            return

        detector = self.my_g4d
        _release_cppyy_ownership(vars(detector).values())
        _release_cppyy_ownership(detector)
        _release_cppyy_ownership(self.step_limiter_physics)
        _release_cppyy_ownership(self.decay_physics)
        _release_cppyy_ownership(self.physics_list)
        for action in self.action_initialization.actions:
            _release_cppyy_ownership(vars(action).values())
            _release_cppyy_ownership(action)
        _release_cppyy_ownership(self.action_initialization)
        _release_cppyy_ownership(self.rand_engine)

        self.my_g4d = None
        self.step_limiter_physics = None
        self.physics_list = None
        self.action_initialization = None
        self.rand_engine = None
        self.g4RunManager = None
        self._closed = True

    def __del__(self):
        pass
