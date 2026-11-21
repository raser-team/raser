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
    def __init__(self,par_in,par_out,par_randx,par_randy,par_type,par_energy,geant4_model,particles=None):
        super().__init__()
        self.geant4_model=geant4_model
        # Every event fires all the particles; without `particles` there is the
        # one the other arguments describe. A particle has par_in and par_out
        # [um], par_randx and par_randy [um], par_type and par_energy [MeV].
        if particles is None:
            particles = [{
                "par_in": par_in, "par_out": par_out,
                "par_randx": par_randx, "par_randy": par_randy,
                "par_type": par_type, "par_energy": par_energy,
            }]
        self.shots = [self._shot(particle) for particle in particles]

    @staticmethod
    def _shot(particle):
        par_in, par_out = particle["par_in"], particle["par_out"]
        par_type, par_energy = particle["par_type"], particle["par_energy"]
        # par_type and par_energy are one particle, or lists of the same
        # length: every event fires one of them, each with the same chance.
        types = par_type if isinstance(par_type, list) else [par_type]
        energies = par_energy if isinstance(par_energy, list) else [par_energy]
        if len(types) != len(energies):
            raise ValueError(
                f"par_type has {len(types)} particles and par_energy {len(energies)}"
            )
        particle_table = g4b.G4ParticleTable.GetParticleTable()
        guns = []
        for one_type, one_energy in zip(types, energies):
            beam = g4b.G4ParticleGun(1)
            beam.SetParticleEnergy(one_energy*g4b.MeV)
            beam.SetParticleDefinition(particle_table.FindParticle(one_type))
            guns.append(beam)
        return {
            "guns": guns,
            "position": par_in,
            "direction": [par_out[i] - par_in[i] for i in range(3)],
            "randx": particle.get("par_randx", 0),
            "randy": particle.get("par_randy", 0),
        }

    def GeneratePrimaries(self, event):
        generator = stream("source")
        for shot in self.shots:
            rdo_x = generator.Uniform(-shot["randx"],shot["randx"])
            rdo_y = generator.Uniform(-shot["randy"],shot["randy"])
            generator.Uniform(-shot["randx"],shot["randx"])
            generator.Uniform(-shot["randy"],shot["randy"])
            direction = g4b.G4ThreeVector(shot["direction"][0]+rdo_x,shot["direction"][1]+rdo_y,shot["direction"][2],)
            beam = shot["guns"][0]
            if len(shot["guns"]) > 1:
                beam = shot["guns"][generator.Integer(len(shot["guns"]))]
            beam.SetParticleMomentumDirection(direction)
            beam.SetParticlePosition(g4b.G4ThreeVector(shot["position"][0]*g4b.um,
                                                    shot["position"][1]*g4b.um,
                                                    shot["position"][2]*g4b.um,))
            beam.GeneratePrimaryVertex(event)
