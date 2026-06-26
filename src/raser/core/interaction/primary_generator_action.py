'''
Description:  primary_generator_action.py
@Date       : 2025
@Author     : Yuhang Tan, Chenxi Fu (Original: Geant4)
@version    : 2.0
'''

import random

import g4ppyy as g4b

g4b.include("G4VUserPrimaryGeneratorAction.hh")

class GeneralPrimaryGeneratorAction(g4b.G4VUserPrimaryGeneratorAction):
    "My Primary Generator Action"
    def __init__(self,par_in,par_out,par_randx,par_randy,par_type,par_energy,geant4_model):
        super().__init__()
        self.geant4_model=geant4_model
        self.par_direction = [ par_out[i] - par_in[i] for i in range(3) ]  
        particle_table = g4b.G4ParticleTable.GetParticleTable()
        particle = particle_table.FindParticle(par_type) # define particle
        beam = g4b.G4ParticleGun(1)
        beam.SetParticleEnergy(par_energy*g4b.MeV)
        beam.SetParticleMomentumDirection(g4b.G4ThreeVector(self.par_direction[0],
                                                            self.par_direction[1],
                                                            self.par_direction[2]))
        beam.SetParticleDefinition(particle)
        beam.SetParticlePosition(g4b.G4ThreeVector(par_in[0]*g4b.um,
                                                   par_in[1]*g4b.um,
                                                   par_in[2]*g4b.um))  
        self.particleGun = beam
        self.position = par_in
        self.randx = par_randx
        self.randy = par_randy

    def GeneratePrimaries(self, event):
        rdo_x = random.uniform(-self.randx,self.randx)
        rdo_y = random.uniform(-self.randy,self.randy)
        rdi_x = random.uniform(-self.randx,self.randx)
        rdi_y = random.uniform(-self.randy,self.randy)
        direction = g4b.G4ThreeVector(self.par_direction[0]+rdo_x,self.par_direction[1]+rdo_y,self.par_direction[2],)
        self.particleGun.SetParticleMomentumDirection(direction)
        self.particleGun.SetParticlePosition(g4b.G4ThreeVector(self.position[0]*g4b.um,
                                                self.position[1]*g4b.um,
                                                self.position[2]*g4b.um,))  
        self.particleGun.GeneratePrimaryVertex(event)
        #print("direction:",rdo_x-rdi_x,rdo_y-rdi_y,self.par_direction[2])
        #print(rdi_x,rdi_y,self.position[2])
