#!/usr/bin/env python3

from pathlib import Path

import acts
import acts.examples
from acts.examples.simulation import (
    addParticleGun,
    addDigitization,
    MomentumConfig,
    EtaConfig,
    PhiConfig,
    ParticleConfig,
    addFatras,
)

from acts.examples.reconstruction import (
    addSeeding,
    TruthSeedRanges,
    ParticleSmearingSigmas,
    SeedFinderConfigArg,
    SeedFinderOptionsArg,
    SeedingAlgorithm,
    TruthEstimatedSeedingAlgorithmConfigArg,
    addCKFTracks,
    addAmbiguityResolution,
    AmbiguityResolutionConfig,
    addVertexFitting,
    VertexFinder,
    TrackSelectorConfig,
)

u = acts.UnitConstants

if "__main__" == __name__:
    detector, trackingGeometry, decorators = acts.examples.TelescopeDetector.create(
        positions=[20, 60, 100 ,140, 180, 220],
        stereos = [0, 0, 0, 0, 0, 0],
        bounds=[200,200],
        binValue=2,
    )

    field = acts.ConstantBField(acts.Vector3(0, 0, 1 * u.T))

    outputDir = Path.cwd() / "output/telescope_simulation"
    if not outputDir.exists():
        outputDir.mkdir()
    inputDir = Path.cwd() / "setting"
    
    rnd = acts.examples.RandomNumbers(seed=42)

    s = acts.examples.Sequencer(events=1, numThreads=1, logLevel=acts.logging.INFO)
    
    postfix = "fatras"
    
    addParticleGun(
        s,
        MomentumConfig(4.0 * u.GeV, 5.0 * u.GeV, transverse=True),
        EtaConfig(0,3),
        PhiConfig(0.0, 360.0 * u.degree),
        ParticleConfig(5000, acts.PdgParticle.eMuon, False),
        multiplicity=1,
        rnd=rnd,
        outputDirRoot=outputDir / postfix,
    )
    
    #generate hits file
    addFatras(
        s,
        trackingGeometry,
        field,
        rnd=rnd,
        outputDirRoot=outputDir / postfix,
    )
    
    addDigitization(
        s,
        trackingGeometry,
        field,
        digiConfigFile= inputDir/"smear.json",
        rnd=rnd,
        outputDirRoot=outputDir / postfix,
    )
    '''
    addSeeding(
        s,
        trackingGeometry,
        field,
        geoSelectionConfigFile=inputDir/"seed.json",
        rnd=rnd,  # only used by SeedingAlgorithm.TruthSmeared
        outputDirRoot=outputDir / postfix,
    )
    
    addCKFTracks(
        s,
        trackingGeometry,
        field,
        TrackSelectorConfig(
            pt=(None, None),
            loc0=(-20.0 * u.mm, 20.0 * u.mm),
            nMeasurementsMin=5,
        ),
        outputDirRoot=outputDir / postfix,
    )
    
    
    '''
    addSeeding(
        s,
        trackingGeometry,
        field,
        TruthSeedRanges(pt=(None, None), nHits=(5, None)),
        ParticleSmearingSigmas(pRel=0.01),  # only used by SeedingAlgorithm.TruthSmeared
        SeedFinderConfigArg(
            r=(0 * u.mm, 200 * u.mm),
            deltaR=(1 * u.mm, 60 * u.mm),
            collisionRegion=(-250 * u.mm, 250 * u.mm),
            z=(-2000 * u.mm, 2000 * u.mm),
            maxSeedsPerSpM=1,
            sigmaScattering=5,
            radLengthPerSeed=0.1,
            minPt=0.0 * u.MeV,
            impactMax=3 * u.mm,
        ),
        SeedFinderOptionsArg(bFieldInZ=1 * u.T),
        TruthEstimatedSeedingAlgorithmConfigArg(deltaR=(15.0 * u.mm, None)),
        seedingAlgorithm=SeedingAlgorithm.TruthSmeared,
        geoSelectionConfigFile=inputDir/"seed.json",
        rnd=rnd,  # only used by SeedingAlgorithm.TruthSmeared
        outputDirRoot=outputDir / postfix,
    )
    
    addCKFTracks(
        s,
        trackingGeometry,
        field,
        TrackSelectorConfig(
            pt=(None, None),
            loc0=(-200.0 * u.mm, 200.0 * u.mm),
            nMeasurementsMin=5,
        ),
        outputDirRoot=outputDir / postfix,
    )
    '''
    addAmbiguityResolution(
        s,
        AmbiguityResolutionConfig(maximumSharedHits=1),
        outputDirRoot=outputDir / postfix,
    )
    '''
    s.run()