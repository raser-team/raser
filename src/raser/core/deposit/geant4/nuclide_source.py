"""A source of nuclides at rest: Geant4 decays them."""

import math

from raser.core.deposit.geant4.g4ppyy_runtime import g4b
from raser.core.seeding import stream

g4b.include("G4VUserPrimaryGeneratorAction.hh")
g4b.include("G4UserStackingAction.hh")
g4b.include("G4GeneralParticleSource.hh")
g4b.include("G4IonTable.hh")

RADIOACTIVE_DECAY = 210  # G4ProcessSubType of G4RadioactiveDecay


def axis_and_plane(par_in, par_out):
    """The unit vector from par_in to par_out, and two unit vectors that
    span the plane across it."""
    axis = [par_out[i] - par_in[i] for i in range(3)]
    length = math.sqrt(sum(a * a for a in axis))
    axis = [a / length for a in axis]
    helper = [1.0, 0.0, 0.0] if abs(axis[0]) < 0.9 else [0.0, 1.0, 0.0]
    first = _cross(axis, helper)
    length = math.sqrt(sum(a * a for a in first))
    first = [a / length for a in first]
    return axis, first, _cross(axis, first)


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


class NuclideGeneratorAction(g4b.G4VUserPrimaryGeneratorAction):
    """Every event is one nuclide at rest, each of `nuclides` ([Z, A]) with
    the same chance, uniformly on the disk of `radius` [um] around par_in
    [um] across the axis from par_in to par_out. `cone` is of the
    DecayStackingAction."""

    def __init__(self, nuclides, par_in, par_out, radius, cone=None):
        super().__init__()
        self.nuclides = nuclides
        self.par_in = par_in
        self.radius = radius
        _, self.first, self.second = axis_and_plane(par_in, par_out)
        self.source = g4b.G4GeneralParticleSource()
        self.ready = False

    def _prepare(self):
        # the ions exist only once the physics is initialised
        ions = g4b.G4IonTable.GetIonTable()
        for k, (z, a) in enumerate(self.nuclides):
            if k:
                self.source.AddaSource(1.0)
            one = self.source.GetCurrentSource()
            one.SetParticleDefinition(ions.GetIon(int(z), int(a), 0.0))
            one.SetParticleCharge(0.0)
            one.GetEneDist().SetEnergyDisType("Mono")
            one.GetEneDist().SetMonoEnergy(0.0)
            position = one.GetPosDist()
            position.SetCentreCoords(g4b.G4ThreeVector(*[c * g4b.um for c in self.par_in]))
            if self.radius > 0:
                position.SetPosDisType("Plane")
                position.SetPosDisShape("Circle")
                position.SetRadius(self.radius * g4b.um)
                position.SetPosRot1(g4b.G4ThreeVector(*self.first))
                position.SetPosRot2(g4b.G4ThreeVector(*self.second))
            else:
                position.SetPosDisType("Point")
        self.ready = True

    def GeneratePrimaries(self, event):
        if not self.ready:
            self._prepare()
        self.source.GeneratePrimaryVertex(event)


class DecayStackingAction(g4b.G4UserStackingAction):
    """What a radioactive decay leaves starts at the time 0, and the nucleus
    it leaves is not followed: an event is one decay, not the chain.

    With `cone` [degree], what the decay emits goes isotropically within the
    cone around `axis`: a fraction (1 - cos cone) / 2 of all directions.
    Geant4's own /process/had/rdm/decayHalfAngle does this only around z."""

    def __init__(self, axis=None, first=None, second=None, cone=None):
        super().__init__()
        self.axis, self.first, self.second = axis, first, second
        self.cos_cone = None if cone is None else math.cos(math.radians(cone))

    def ClassifyNewTrack(self, track):
        process = track.GetCreatorProcess()
        if process and process.GetProcessSubType() == RADIOACTIVE_DECAY:
            if track.GetDefinition().GetParticleType() == "nucleus":
                return g4b.fKill
            track.SetGlobalTime(0.0)
            if self.cos_cone is not None:
                generator = stream("source")
                cos_theta = 1 - generator.Uniform(0, 1) * (1 - self.cos_cone)
                sin_theta = math.sqrt(max(0.0, 1 - cos_theta * cos_theta))
                turn = 2 * math.pi * generator.Uniform(0, 1)
                track.SetMomentumDirection(g4b.G4ThreeVector(*[
                    cos_theta * self.axis[i]
                    + sin_theta * (math.cos(turn) * self.first[i] + math.sin(turn) * self.second[i])
                    for i in range(3)
                ]))
        return g4b.fUrgent
