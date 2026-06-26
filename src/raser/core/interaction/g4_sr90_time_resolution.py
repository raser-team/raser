'''
Description:  g4_sr90_time_resolution.py
@Date       : 2025
@Author     : Yuhang Tan, Tao Yang, Chenxi Fu (Original: Geant4)
@version    : 2.0
'''

import g4ppyy as g4b

from .primary_generator_action import GeneralPrimaryGeneratorAction

class Sr90PrimaryGeneratorAction(GeneralPrimaryGeneratorAction):
    "My Primary Generator Action"
    def __init__(self,par_in,par_out,par_type,par_energy,geant4_model):
        super().__init__(par_in,par_out,par_type,par_energy,geant4_model)
        beam2 = g4b.G4ParticleGun(1)
        beam2.SetParticleEnergy(0.546*g4b.MeV)
        beam2.SetParticleMomentumDirection(g4b.G4ThreeVector(self.par_direction[0],
                                                            self.par_direction[1],
                                                            self.par_direction[2]))
        beam2.SetParticleDefinition("e-")
        beam2.SetParticlePosition(g4b.G4ThreeVector(par_in[0]*g4b.um,
                                                    par_in[1]*g4b.um,
                                                    par_in[2]*g4b.um))  
        self.particleGun2 = beam2

    def GeneratePrimaries(self, event):
        super().GeneratePrimaries(event)
        self.particleGun2.GeneratePrimaryVertex(event)        
