#!/usr/bin/env python3 
import geant4_pybind as g4b
import sys
import os

G4AnalysisManager = g4b.G4RootAnalysisManager

class cflmDetectorConstruction(g4b.G4VUserDetectorConstruction):

    def __init__(self):
        super().__init__()
        self.fCheckOverlaps = True

    def DefineMaterials(self):

        nistManager = g4b.G4NistManager.Instance()
        nistManager.FindOrBuildMaterial("G4_Cu")

        g4b.G4Material("Galactic", z=1, a=1.01*g4b.g/g4b.mole, density=g4b.universe_mean_density,
                   state=g4b.kStateGas, temp=2.73*g4b.kelvin, pressure=3e-18*g4b.pascal)


        print(g4b.G4Material.GetMaterialTable())

    def DefineVolumes(self):

        pipeRmin = 28*g4b.mm
        pipeRmax = 30*g4b.mm
        pipeDz = 100*g4b.mm
        pipeSphi = 0*g4b.deg
        pipeDphi = 180*g4b.deg
        detectorSizeX = 50*g4b.mm
        detectorSizeY = 0.5*g4b.mm
        detectorSizeZ = 100*g4b.mm

        worldSizeXY = 200 * g4b.mm
        worldSizeZ = 200 * g4b.mm

        defaultMaterial = g4b.G4Material.GetMaterial("Galactic")
        pipeMaterial = g4b.G4Material.GetMaterial("G4_Cu")

        if defaultMaterial == None or pipeMaterial == None:
            msg = "Cannot retrieve materials already defined."
            g4b.G4Exception("cflmDetectorConstruction::DefineVolumes()",
                        "MyCode0001", g4b.FatalException, msg)

        # World
        worldS = g4b.G4Box("World",                                     # its name
                       worldSizeXY/2, worldSizeXY/2, worldSizeZ/2)  # its size

        worldLV = g4b.G4LogicalVolume(worldS,           # its solid
                                  defaultMaterial,  # its material
                                  "World")          # its name

        worldPV = g4b.G4PVPlacement(None,                 # no rotation
                                g4b.G4ThreeVector(),      # at (0,0,0)
                                worldLV,              # its logical volume
                                "World",              # its name
                                None,                 # its mother  volume
                                False,                # no boolean operation
                                0,                    # copy number
                                self.fCheckOverlaps)  # checking overlaps


        # Pipe
        pipeS = g4b.G4Tubs("Pipe",                                         # its name
                          pipeRmin, pipeRmax, pipeDz/2,pipeSphi,pipeDphi)  # its size

        pipeLV = g4b.G4LogicalVolume(pipeS,         # its solid
                                     pipeMaterial,  # its material
                                     "Pipe")            # its name

        self.fpipePV = g4b.G4PVPlacement(None,                                  # no rotation
                                         g4b.G4ThreeVector(0, 0, 0),  # its position
                                         pipeLV,                            # its logical volume
                                         "Pipe",                                # its name
                                         worldLV,                               # its mother  volume
                                         False,                                 # no boolean operation
                                         0,                                     # copy number
                                         self.fCheckOverlaps)                   # checking overlaps

        # detector
        self.nist = g4b.G4NistManager.Instance()
        silicon_carbide={
                "material_1" : "Si",
                "material_2" : "C",
                "compound_name" :"SiC",
                "density" : 3.2,
                "natoms_1" : 50,
                "natoms_2" : 50,
                }
        material_1 = self.nist.FindOrBuildElement(silicon_carbide['material_1'],False)
        material_2 = self.nist.FindOrBuildElement(silicon_carbide['material_2'],False)
        material_density = silicon_carbide['density']*g4b.g/g4b.cm3
        detectorMaterial = g4b.G4Material(silicon_carbide['compound_name'],material_density,2) 
        detectorMaterial.AddElement(material_1,silicon_carbide['natoms_1']*g4b.perCent)
        detectorMaterial.AddElement(material_2,silicon_carbide['natoms_2']*g4b.perCent)

        detectorS = g4b.G4Box("Detector",                                         # its name
                     detectorSizeX/2, detectorSizeY/2, detectorSizeZ/2)  # its size

        detectorLV = g4b.G4LogicalVolume(detectorS,         # its solid
                                detectorMaterial,  # its material
                                "Detector")        # its name

        self.fdetectorPV = g4b.G4PVPlacement(None,                                  # no rotation
                                    g4b.G4ThreeVector(0, 30*g4b.mm, 0),  # its position
                                    detectorLV,                                 # its logical volume
                                    "Detector",                                 # its name
                                    worldLV,                               # its mother volume
                                    False,                                 # no boolean operation
                                    0,                                     # copy number
                                    self.fCheckOverlaps)                   # checking overlaps

        worldLV.SetVisAttributes(g4b.G4VisAttributes.GetInvisible())

        pipeVisAtt = g4b.G4VisAttributes(g4b.G4Colour(1, 1, 0))
        detectorVisAtt = g4b.G4VisAttributes(g4b.G4Colour(1, 1, 1))

        pipeLV.SetVisAttributes(pipeVisAtt)
        detectorLV.SetVisAttributes(detectorVisAtt)

        return worldPV

    def Construct(self):
        self.DefineMaterials()
        return self.DefineVolumes()

    def ConstructSDandField(self):

        fieldValue = g4b.G4ThreeVector()
        self.fMagFieldMessenger = g4b.G4GlobalMagFieldMessenger(fieldValue)
        self.fMagFieldMessenger.SetVerboseLevel(1)

class cflmPrimaryGeneratorAction(g4b.G4VUserPrimaryGeneratorAction):

    def __init__(self):
        super().__init__()
        nofParticles = 1
        self.fParticleGun = g4b.G4ParticleGun(nofParticles)

        particleDefinition = g4b.G4ParticleTable.GetParticleTable().FindParticle("e-")
        self.fParticleGun.SetParticleDefinition(particleDefinition)
        self.fParticleGun.SetParticleMomentumDirection(g4b.G4ThreeVector(0, 0.01, 1))
        self.fParticleGun.SetParticleEnergy(24*g4b.GeV)

    def GeneratePrimaries(self, anEvent):

        self.fParticleGun.SetParticlePosition(g4b.G4ThreeVector(0, 26.9*g4b.mm, -100*g4b.mm))
        self.fParticleGun.GeneratePrimaryVertex(anEvent)

class cflmaEventAction(g4b.G4UserEventAction):

    def BeginOfEventAction(self, event):

        self.fEnergyPipe = 0
        self.fEnergyDetector = 0
        self.fTrackLPipe = 0
        self.fTrackLDetector = 0

    def EndOfEventAction(self, event):

        analysisManager = g4b.G4AnalysisManager.Instance()

        analysisManager.FillH1(0, self.fEnergyPipe)
        analysisManager.FillH1(1, self.fEnergyDetector)
        analysisManager.FillH1(2, self.fTrackLPipe)
        analysisManager.FillH1(3, self.fTrackLDetector)

        analysisManager.FillNtupleDColumn(0, self.fEnergyPipe)
        analysisManager.FillNtupleDColumn(1, self.fEnergyDetector)
        analysisManager.FillNtupleDColumn(2, self.fTrackLPipe)
        analysisManager.FillNtupleDColumn(3, self.fTrackLDetector)
        analysisManager.AddNtupleRow()

        eventID = event.GetEventID()
        printModulo = g4b.G4RunManager.GetRunManager().GetPrintProgress()
        if printModulo > 0 and eventID % printModulo == 0:
            print("---> End of event:", eventID)
            print("Pipe: total energy:", g4b.G4BestUnit(self.fEnergyPipe, "Energy"), end="")
            print("total track length:", g4b.G4BestUnit(self.fTrackLPipe, "Length"))
            print("Detector: total energy:", g4b.G4BestUnit(self.fEnergyDetector, "Energy"), end="")
            print("total track length:", g4b.G4BestUnit(self.fTrackLDetector, "Length"))

    def AddPipe(self, de,  dl):
        self.fEnergyPipe += de
        self.fTrackLPipe += dl

    def AddDetector(self, de, dl):
        self.fEnergyDetector += de
        self.fTrackLDetector += dl

class cflmaSteppingAction(g4b.G4UserSteppingAction):

    def __init__(self, detectorConstruction, eventAction):
        super().__init__()
        self.fDetConstruction = detectorConstruction
        self.fEventAction = eventAction

    def UserSteppingAction(self, step):

        volume = step.GetPreStepPoint().GetTouchable().GetVolume()

        edep = step.GetTotalEnergyDeposit()

        stepLength = 0
        if step.GetTrack().GetDefinition().GetPDGCharge() != 0:
            stepLength = step.GetStepLength()

        if volume == self.fDetConstruction.fpipePV:
            self.fEventAction.AddPipe(edep, stepLength)

        if volume == self.fDetConstruction.fdetectorPV:
            self.fEventAction.AddDetector(edep, stepLength)

class cflmRunAction(g4b.G4UserRunAction):

    def __init__(self):
        super().__init__()

        g4b.G4RunManager.GetRunManager().SetPrintProgress(1)

        analysisManager = g4b.G4AnalysisManager.Instance()
        print("Using", analysisManager.GetType())

        analysisManager.SetVerboseLevel(1)
        analysisManager.SetNtupleMerging(True)

        analysisManager.CreateH1("Epipe", "Energy deposition in pipe", 100, 0, 1000*g4b.MeV)
        analysisManager.CreateH1("Edetector", "Energy deposition in detector", 100, 0, 100*g4b.MeV)

        analysisManager.CreateNtuple("cflm", "Edep")
        analysisManager.CreateNtupleDColumn("Epipe")
        analysisManager.CreateNtupleDColumn("Edetector")
        analysisManager.FinishNtuple()

    def BeginOfRunAction(self, run):

        analysisManager = g4b.G4AnalysisManager.Instance()
        try:
            os.mkdir('output/cflm')
        except:
            print('path already exist')

        fileName = "output/cflm/energy_deposition.root"
        analysisManager.OpenFile(fileName)

    def EndOfRunAction(self, run):

        analysisManager = g4b.G4AnalysisManager.Instance()
        if analysisManager.GetH1(1) != None:
            print("\n ----> print histograms statistic ", end="")

            if self.IsMaster():
                print("for the entire run \n")
            else:
                print("for the local thread \n")

            print(" EPipe : mean =", g4b.G4BestUnit(analysisManager.GetH1(0).mean(), "Energy"), end="")
            print(" rms =", g4b.G4BestUnit(analysisManager.GetH1(0).rms(),  "Energy"))

            print(" EDetector : mean =", g4b.G4BestUnit(analysisManager.GetH1(1).mean(), "Energy"), end="")
            print(" rms =", g4b.G4BestUnit(analysisManager.GetH1(1).rms(),  "Energy"))

        # save histograms & ntuple
        analysisManager.Write()

class cflmaActionInitialization(g4b.G4VUserActionInitialization):

    def __init__(self, detConstruction):
        super().__init__()
        self.fDetConstruction = detConstruction

    def BuildForMaster(self):
        self.SetUserAction(cflmRunAction())

    def Build(self):
        self.SetUserAction(cflmPrimaryGeneratorAction())
        self.SetUserAction(cflmRunAction())
        eventAction = cflmaEventAction()
        self.SetUserAction(eventAction)
        self.SetUserAction(cflmaSteppingAction(self.fDetConstruction, eventAction))

def main():

    runManager = g4b.G4RunManagerFactory.CreateRunManager(g4b.G4RunManagerType.Serial)

    detConstruction = cflmDetectorConstruction()
    runManager.SetUserInitialization(detConstruction)

    physicsList = g4b.FTFP_BERT()
    runManager.SetUserInitialization(physicsList)

    actionInitialization = cflmaActionInitialization(detConstruction)
    runManager.SetUserInitialization(actionInitialization)

    visManager = g4b.G4VisExecutive()
    visManager.Initialize()

    UImanager = g4b.G4UImanager.GetUIpointer()

    UImanager.ApplyCommand("/control/execute cfg/init_vis.mac")

    UImanager.ApplyCommand('/run/initialize')
    UImanager.ApplyCommand('/tracking/verbose 2')
    UImanager.ApplyCommand('/run/beamOn 1')
    UImanager.ApplyCommand('/vis/ogl/set/printMode vectored')
    UImanager.ApplyCommand('/vis/ogl/set/printSize 2000 2000')
    UImanager.ApplyCommand('/vis/ogl/set/printFilename output/cflm/image.pdf')
    UImanager.ApplyCommand('/vis/ogl/export')

if __name__ == '__main__':
    main()
