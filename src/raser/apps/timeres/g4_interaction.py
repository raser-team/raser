"""
Description:  g4_sr90_time_resolution.py
@Date       : 2025
@Author     : Yuhang Tan, Tao Yang, Chenxi Fu (Original: Geant4)
@version    : 2.0
"""

import g4ppyy as g4b

from raser.core.interaction.primary_generator_action import (
    GeneralPrimaryGeneratorAction,
)
from raser.core.interaction.event_action import GeneralEventAction
from raser.core.interaction.run_action import GeneralRunAction
from raser.core.interaction.stepping_action import GeneralSteppingAction
from raser.core.interaction.action_initialization import GeneralActionInitialization


class Sr90PrimaryGeneratorAction(GeneralPrimaryGeneratorAction):
    "My Primary Generator Action"

    def __init__(
        self,
        par_in,
        par_out,
        par_randx,
        par_randy,
        par_type,
        par_energy,
        geant4_model,
    ):
        super().__init__(
            par_in,
            par_out,
            par_randx,
            par_randy,
            par_type,
            par_energy,
            geant4_model,
        )
        beam2 = g4b.G4ParticleGun(1)
        beam2.SetParticleEnergy(0.546 * g4b.MeV)
        beam2.SetParticleMomentumDirection(
            g4b.G4ThreeVector(
                self.par_direction[0], self.par_direction[1], self.par_direction[2]
            )
        )
        particle = g4b.G4ParticleTable.GetParticleTable().FindParticle("e-")
        beam2.SetParticleDefinition(particle)
        beam2.SetParticlePosition(
            g4b.G4ThreeVector(
                par_in[0] * g4b.um, par_in[1] * g4b.um, par_in[2] * g4b.um
            )
        )
        self.particleGun2 = beam2

    def GeneratePrimaries(self, event):
        super().GeneratePrimaries(event)
        self.particleGun2.GeneratePrimaryVertex(event)


class TimeresActionInitialization(GeneralActionInitialization):
    def Build(self):
        primary_action = Sr90PrimaryGeneratorAction(
            self.par_in,
            self.par_out,
            self.par_randx,
            self.par_randy,
            self.par_type,
            self.par_energy,
            self.geant4_model,
        )
        self.actions.append(primary_action)
        self.SetUserAction(primary_action)

        run_action = GeneralRunAction()
        self.actions.append(run_action)
        self.SetUserAction(run_action)
        event_action = GeneralEventAction(
            run_action,
            self.par_in,
            self.par_out,
            self.eventIDs,
            self.edep_devices,
            self.p_steps,
            self.energy_steps,
            self.events_angles,
        )
        self.actions.append(event_action)
        self.SetUserAction(event_action)
        stepping_action = GeneralSteppingAction(event_action)
        self.actions.append(stepping_action)
        self.SetUserAction(stepping_action)
