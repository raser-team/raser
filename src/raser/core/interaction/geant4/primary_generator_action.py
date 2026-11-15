'''
Description:  primary_generator_action.py
@Date       : 2025
@Author     : Yuhang Tan, Chenxi Fu (Original: Geant4)
@version    : 2.0
'''

from raser.core.seeding import stream

from raser.core.interaction.geant4.g4ppyy_runtime import g4b

g4b.include("G4VUserPrimaryGeneratorAction.hh")

class GeneralPrimaryGeneratorAction(g4b.G4VUserPrimaryGeneratorAction):
    "My Primary Generator Action"
    def __init__(self,par_in,par_out,par_randx,par_randy,par_type,par_energy,geant4_model):
        super().__init__()
        self.geant4_model=geant4_model
        self.par_direction = [ par_out[i] - par_in[i] for i in range(3) ]  
        # par_type and par_energy [MeV] are one particle, or lists of the same
        # length: every event fires one of them, each with the same chance.
        types = par_type if isinstance(par_type, list) else [par_type]
        energies = par_energy if isinstance(par_energy, list) else [par_energy]
        if len(types) != len(energies):
            raise ValueError(
                f"par_type has {len(types)} particles and par_energy {len(energies)}"
            )
        particle_table = g4b.G4ParticleTable.GetParticleTable()
        self.particleGuns = []
        for one_type, one_energy in zip(types, energies):
            beam = g4b.G4ParticleGun(1)
            beam.SetParticleEnergy(one_energy*g4b.MeV)
            beam.SetParticleDefinition(particle_table.FindParticle(one_type))
            self.particleGuns.append(beam)
        self.position = par_in
        self.randx = par_randx
        self.randy = par_randy

    def GeneratePrimaries(self, event):
        generator = stream("source")
        rdo_x = generator.Uniform(-self.randx,self.randx)
        rdo_y = generator.Uniform(-self.randy,self.randy)
        rdi_x = generator.Uniform(-self.randx,self.randx)
        rdi_y = generator.Uniform(-self.randy,self.randy)
        direction = g4b.G4ThreeVector(self.par_direction[0]+rdo_x,self.par_direction[1]+rdo_y,self.par_direction[2],)
        beam = self.particleGuns[0]
        if len(self.particleGuns) > 1:
            beam = self.particleGuns[generator.Integer(len(self.particleGuns))]
        beam.SetParticleMomentumDirection(direction)
        beam.SetParticlePosition(g4b.G4ThreeVector(self.position[0]*g4b.um,
                                                self.position[1]*g4b.um,
                                                self.position[2]*g4b.um,))
        beam.GeneratePrimaryVertex(event)
        #print("direction:",rdo_x-rdi_x,rdo_y-rdi_y,self.par_direction[2])
        #print(rdi_x,rdi_y,self.position[2])
