"""
Description:  interaction.py
@Date       : 2025
@Author     : Chenxi Fu (Original: Geant4)
@version    : 1.0
"""

from raser.core.interaction.geant4.g4ppyy_runtime import g4b

from ..deposits import deposits_of_steps
from .detector_construction import GeneralDetectorConstruction
from .action_initialization import GeneralActionInitialization

g4b.include("G4RunManager.hh")

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
        my_d,
        g4_dic,
        g4_seed,
        g4_vis=False,
        MyDetectorConstruction=GeneralDetectorConstruction,
        MyActionInitialization=GeneralActionInitialization,
    ):
        """
        Description:
            General Geant4 main process
            Simulate s_num particles through device
            Record the energy depositon in the device
        Parameters:
            g4_dic : dict
                Geant4 configuration: source, surroundings, total_events,
                edep_min and edep_max [MeV]
            energy_steps : list
                Energy deposition of each step in simulation
            edep_devices : list
                Total energy deposition in device
        @Modify:
            2025/05/15
        """
        # g4_vis keeps its place among the arguments until the callers that
        # pass it by position are gone.
        if g4_vis:
            raise ValueError(
                "GeneralG4Interaction does not draw; use "
                "raser.core.interaction.view_geometry.view_geometry"
            )

        self.geant4_model = g4_dic["geant4_model"]
        detector_material = my_d.device_dict["material"]

        if (
            self.geant4_model == "gdml_import"
            and MyDetectorConstruction is GeneralDetectorConstruction
        ):
            from .g4_gdml_import import GDMLDetectorConstruction

            MyDetectorConstruction = GDMLDetectorConstruction

        self.my_g4d = MyDetectorConstruction(
            my_d, g4_dic, detector_material, g4_dic["maxstep"]
        )

        self.g4RunManager = g4b.G4RunManager.GetRunManager() or g4b.G4RunManager()
        self.rand_engine = g4b.cppyy.gbl.CLHEP.RanecuEngine()
        g4b.cppyy.gbl.CLHEP.HepRandom.setTheEngine(self.rand_engine)
        g4b.cppyy.gbl.CLHEP.HepRandom.setTheSeed(g4_seed)
        self.g4RunManager.SetUserInitialization(self.my_g4d)

        # set physics list
        self.physics_list = g4b.FTFP_BERT()
        self.step_limiter_physics = g4b.G4StepLimiterPhysics()
        self.physics_list.RegisterPhysics(self.step_limiter_physics)
        self.g4RunManager.SetUserInitialization(self.physics_list)

        (
            self.eventIDs,
            self.edep_devices,
            self.p_steps,
            self.energy_steps,
            self.time_steps,
            self.events_angles,
        ) = [], [], [], [], [], []

        self.generated_events = int(g4_dic["total_events"])
        self.edep_window = (g4_dic.get("edep_min"), g4_dic.get("edep_max"))

        # define action
        self.action_initialization = MyActionInitialization(
            g4_dic["par_in"],
            g4_dic["par_out"],
            g4_dic.get("par_randx", 0),
            g4_dic.get("par_randy", 0),
            g4_dic["par_type"],
            g4_dic["par_energy"],
            self.eventIDs,
            self.edep_devices,
            self.p_steps,
            self.energy_steps,
            self.time_steps,
            self.events_angles,
            self.edep_window,
            self.geant4_model,
            **({"particles": g4_dic["particles"]} if "particles" in g4_dic else {}),
        )
        self.g4RunManager.SetUserInitialization(self.action_initialization)

        self.beam_on()

        self.init_tz_device = 0
        self.p_steps_current = [
            [
                [
                    single_step[0] + my_d.l_x / 2,
                    single_step[1] + my_d.l_y / 2,
                    single_step[2] - self.init_tz_device,
                ]
                for single_step in p_step
            ]
            for p_step in self.p_steps
        ]
        # change the coordinate system from Geant4 to device

        self._closed = False

    def beam_on(self):
        UImanager = g4b.G4UImanager.GetUIpointer()
        # reduce verbose from physics list
        UImanager.ApplyCommand("/process/em/verbose %d" % (verbose))
        UImanager.ApplyCommand("/process/had/verbose %d" % (verbose))
        UImanager.ApplyCommand("/run/initialize")
        self.g4RunManager.BeamOn(self.generated_events)

    def deposits(self):
        """The recorded events as Deposits in the coordinates of the device."""
        return deposits_of_steps(
            "Device",
            self.eventIDs,
            self.p_steps_current,
            self.energy_steps,
            self.time_steps,
            self.generated_events,
            *self.edep_window,
        )

    def close(self):
        if self._closed:
            return

        detector = self.my_g4d
        _release_cppyy_ownership(vars(detector).values())
        _release_cppyy_ownership(detector)
        _release_cppyy_ownership(self.step_limiter_physics)
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
