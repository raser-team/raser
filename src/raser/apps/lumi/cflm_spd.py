#!/usr/bin/env python3 
import os
import math
import g4ppyy as g4b
g4b.include("G4VUserDetectorConstruction.hh")
g4b.include("G4VUserActionInitialization.hh")
g4b.include("G4VUserPrimaryGeneratorAction.hh")
g4b.include("G4UserRunAction.hh")
g4b.include("G4UserEventAction.hh")
g4b.include("G4UserSteppingAction.hh")
import json
from raser.supports.paths import app_file_path
from raser.supports.output import output

nz_position,  ny_position, nparticle = [], [], []
pz_position,  py_position, pparticle = [], [], []

class cflmDetectorConstruction(g4b.G4VUserDetectorConstruction):

    def __init__(self,g4_dic):
        g4b.G4VUserDetectorConstruction.__init__(self)
        self.solid = {}
        self.logical = {}
        self.physical = {}
        self.checkOverlaps = True
        self.create_world(g4_dic['world'])

        self.maxStep = g4_dic['maxStep']*g4b.mm

        self.rotation = g4b.G4RotationMatrix()
        self.rotation.rotateZ(3*math.pi/2)
   
        self.create_pipe(g4_dic['pipe'])
        self.create_vacuum(g4_dic['vacuum'])

        self.fStepLimit = g4b.G4UserLimits(self.maxStep)
        self.logical["world"].SetUserLimits(self.fStepLimit)

    def create_world(self,world_type):

        self.nist = g4b.G4NistManager.Instance()
        material = self.nist.FindOrBuildMaterial(world_type)
        self.solid['world'] = g4b.G4Box("world",
                                        6000*g4b.mm,
                                        6000*g4b.mm,
                                        6000*g4b.mm)
        self.logical['world'] = g4b.G4LogicalVolume(self.solid['world'],
                                                    material,
                                                    "world")
        self.physical['world'] = g4b.G4PVPlacement(None,
                                                   g4b.G4ThreeVector(0,0,0),
                                                   self.logical['world'],
                                                   "world", 
                                                   None, 
                                                   False,
                                                   0,
                                                   self.checkOverlaps)

        self.logical['world'].SetVisAttributes(g4b.G4VisAttributes.GetInvisible())


    def create_pipe(self,object):
        
        pipe_name = object['name']
        material_type = self.nist.FindOrBuildMaterial(object['material'],
                                                    False)

        translation = g4b.G4ThreeVector(object['position_x']*g4b.mm, object['position_y']*g4b.mm, object['position_z']*g4b.mm)
        visual = g4b.G4VisAttributes(g4b.G4Color(object['colour'][0],object['colour'][1],object['colour'][2]))
        mother = self.physical['world']

        Rmin = object['Rmin']*g4b.mm
        Rmax = object['Rmax']*g4b.mm
        Pipe_Z = object['Pipe_Z']*g4b.mm
        PipeSphi = object['PipeSphi']*g4b.deg
        PipeDphi = object['PipeDphi']*g4b.deg

        self.solid[pipe_name] = g4b.G4Tubs("Pipe",
                                        Rmin, Rmax, Pipe_Z/2,PipeSphi,PipeDphi)

        self.logical[pipe_name] = g4b.G4LogicalVolume(self.solid[pipe_name],
                                                    material_type,
                                                    pipe_name)
        self.physical[pipe_name] = g4b.G4PVPlacement(self.rotation,
                                                    translation,
                                                    pipe_name,
                                                    self.logical[pipe_name],
                                                    mother, 
                                                    False,
                                                    0,
                                                    self.checkOverlaps)
        self.logical[pipe_name].SetVisAttributes(visual)

    def create_vacuum(self, object):

        vacuum_name = object['name']
        material_type = g4b.G4Material("Galactic", z=1, a=1.01*g4b.g/g4b.mole, density=g4b.universe_mean_density, state=g4b.kStateGas, temp=2.73*g4b.kelvin, pressure=3e-18*g4b.pascal)

        translation = g4b.G4ThreeVector(object['position_x']*g4b.mm, object['position_y']*g4b.mm, object['position_z']*g4b.mm)
        visual = g4b.G4VisAttributes(g4b.G4Color(object['colour'][0],object['colour'][1],object['colour'][2]))
        mother = self.physical['world']

        VACmin =  object['VACmin']*g4b.mm
        VACmax = object['VACmax']*g4b.mm
        VAC_Z = object['VAC_Z']*g4b.mm
        VACSphi = object['VACSphi']*g4b.mm
        VACDphi = object['VACDphi']*g4b.mm

        self.solid[vacuum_name] = g4b.G4Tubs(vacuum_name, VACmin, VACmax, VAC_Z/2, VACSphi, VACDphi)

        self.logical[vacuum_name] = g4b.G4LogicalVolume(self.solid[vacuum_name], material_type, vacuum_name)
        self.physical[vacuum_name] = g4b.G4PVPlacement(self.rotation, translation, vacuum_name, self.logical[vacuum_name], mother, False, 0, self.checkOverlaps)

    def Construct(self): 
        self.fStepLimit.SetMaxAllowedStep(self.maxStep)       
        return self.physical['world']

class cflmPrimaryGeneratorAction(g4b.G4VUserPrimaryGeneratorAction):

    def __init__(self, par_in, par_direct, par_type, par_energy, numofgun):
        super().__init__()
        self.nofParticles = numofgun
        self.fParticleGun = g4b.G4ParticleGun(1)
        particleDefinition = g4b.G4ParticleTable.GetParticleTable().FindParticle(par_type)
        self.fParticleGun.SetParticleDefinition(particleDefinition)
        self.directions = []
        self.par_in = []
        self.energy = []    

        self.directions = [g4b.G4ThreeVector(direction[0], direction[1], direction[2]) for direction in par_direct]
        self.par_in = [g4b.G4ThreeVector(position[0], position[1], position[2]) for position in par_in]
        self.energy = par_energy

    def GeneratePrimaries(self, anEvent):
        
        for i in range(self.nofParticles):
       
            self.fParticleGun.SetParticlePosition(self.par_in[i])
            self.fParticleGun.SetParticleMomentumDirection(self.directions[i])
            self.fParticleGun.SetParticleEnergy(self.energy[i]*g4b.GeV) 
            
            self.fParticleGun.GeneratePrimaryVertex(anEvent)

class cflmaSteppingAction(g4b.G4UserSteppingAction):

    def __init__(self, detectorConstruction, eventAction, nz_position, ny_position, nparticle,
                                                          pz_position, py_position, pparticle
                ):
        
        super().__init__()
        self.fDetConstruction = detectorConstruction
        self.fEventAction = eventAction
        
        self.nzposition = nz_position
        self.nyposition = ny_position
        self.nparticle = nparticle

        self.pzposition = pz_position
        self.pyposition = py_position
        self.pparticle = pparticle

    def UserSteppingAction(self, step):

        volume_pre = step.GetPreStepPoint().GetTouchable().GetVolume()
        
        edep = step.GetTotalEnergyDeposit()

        postPosition = step.GetPostStepPoint().GetPosition()
        prePosition = step.GetPreStepPoint().GetPosition()

        if volume_pre == self.fDetConstruction.physical['pipe']:
           self.fEventAction.AddPipe(edep) 
 
        if prePosition.getX() > -31*g4b.mm and postPosition.getX() < -31*g4b.mm:
            nyPosition = prePosition.getY() + (-31*g4b.mm - prePosition.getX()) * (postPosition.getY() - prePosition.getY()) / (postPosition.getX() - prePosition.getX())
            nzPosition = prePosition.getZ() + (-31*g4b.mm - prePosition.getX()) * (postPosition.getZ() - prePosition.getZ()) / (postPosition.getX() - prePosition.getX())

            self.nyposition.append(nyPosition)
            self.nzposition.append(nzPosition)
            self.nparticle.append(step.GetTrack().GetDefinition().GetParticleName())

        if prePosition.getX() < 31*g4b.mm and postPosition.getX() > 31*g4b.mm:
            pyPosition = prePosition.getY() + (31*g4b.mm - prePosition.getX()) * (postPosition.getY() - prePosition.getY()) / (postPosition.getX() - prePosition.getX())
            pzPosition = prePosition.getZ() + (31*g4b.mm - prePosition.getX()) * (postPosition.getZ() - prePosition.getZ()) / (postPosition.getX() - prePosition.getX())

            self.pyposition.append(pyPosition)
            self.pzposition.append(pzPosition)
            self.pparticle.append(step.GetTrack().GetDefinition().GetParticleName())
 
class cflmaEventAction(g4b.G4UserEventAction):

    def BeginOfEventAction(self, event):

        self.fEnergyPipe = 0

    def EndOfEventAction(self, event):
        eventID = event.GetEventID()
        printModulo = g4b.G4RunManager.GetRunManager().GetPrintProgress()
        if printModulo > 0 and eventID % printModulo == 0:
            print("---> End of event:", eventID)
            print("Pipe: total energy:", g4b.G4BestUnit(self.fEnergyPipe, "Energy"), end="")

    def AddPipe(self, de):
        self.fEnergyPipe += de

class cflmRunAction(g4b.G4UserRunAction):

    def __init__(self, PosBaseName):
        super().__init__()

        self.PosBaseName = PosBaseName

        g4b.G4RunManager.GetRunManager().SetPrintProgress(1)

        analysisManager = g4b.G4AnalysisManager.Instance()
        print("Using", analysisManager.GetType())

    def BeginOfRunAction(self, run):

        if self.IsMaster():
            print("Begin of run for the entire run \n")
        else:
            print("Begin of run for the local thread \n")
        
    def EndOfRunAction(self, run):

        if self.IsMaster():
            print("for the entire run \n")
        
        else:
            print("for the local thread \n")
        
        PosName = output(__file__, self.PosBaseName)
        
        with open(f"{PosName}_nx.txt", 'w') as file:  
             for i in range(len(nparticle)):
                file.write(f"{nparticle[i]} {nz_position[i]} {ny_position[i]}\n")
        
        with open(f"{PosName}_px.txt", 'w') as file:  
             for i in range(len(pparticle)):
                file.write(f"{pparticle[i]} {pz_position[i]} {py_position[i]}\n")
        
class cflmaActionInitialization(g4b.G4VUserActionInitialization):

    def __init__(self, detConstruction, par_in, par_direct, par_type, par_energy, numofgun, PosBaseName):
        super().__init__()
        self.fDetConstruction = detConstruction
        self.par_in = par_in
        self.par_direct = par_direct
        self.par_type=par_type
        self.par_energy=par_energy
        self.numofgun = numofgun
        self.PosBaseName = PosBaseName

    def BuildForMaster(self):
        self.SetUserAction(cflmRunAction(self.PosBaseName))

    def Build(self):
        self.SetUserAction(cflmPrimaryGeneratorAction(self.par_in,
                                                      self.par_direct,
                                                      self.par_type,
                                                      self.par_energy,
                                                      self.numofgun))
        self.SetUserAction(cflmRunAction(self.PosBaseName))
        eventAction = cflmaEventAction()
        self.SetUserAction(eventAction)
        self.SetUserAction(cflmaSteppingAction(self.fDetConstruction, eventAction, nz_position,  ny_position, nparticle,
                                                                                   pz_position,  py_position, pparticle
                                              )
                          )

def main():

    geant4_json = app_file_path("lumi", "cflm_spd.json")
    with open(geant4_json) as f:
        g4_dic = json.load(f)

    runManager = g4b.G4RunManager.GetRunManager() or g4b.G4RunManager()
    
    physicsList = g4b.FTFP_BERT()
    physicsList.RegisterPhysics(g4b.G4StepLimiterPhysics())
    runManager.SetUserInitialization(physicsList)
    
    detConstruction = cflmDetectorConstruction(g4_dic)
    runManager.SetUserInitialization(detConstruction)

    visManager = g4b.G4VisExecutive()
    visManager.Initialize()
    UImanager = g4b.G4UImanager.GetUIpointer()
    
    if g4_dic['vis']:

       UImanager.ApplyCommand("/control/execute {}".format(component_path("g4macro", "init_vis.mac")))
       UImanager.ApplyCommand('/run/initialize')    
       UImanager.ApplyCommand('/tracking/verbose 0')
       UImanager.ApplyCommand("/vis/viewer/set/background 0 0 0")
         
       for i in range(1000):
           print(i)
           UImanager.ApplyCommand("/vis/viewer/refresh")
    
    else:
    
        actionInitialization = cflmaActionInitialization(detConstruction,
                                                            g4_dic['par_in'],
                                                            g4_dic['par_direct'],
                                                            g4_dic['par_type'],
                                                            g4_dic['par_energy'],
                                                            g4_dic['NumofGun'],
                                                            g4_dic['PosBaseName']
                                                        )
        runManager.SetUserInitialization(actionInitialization)
        
        UImanager.ApplyCommand('/run/initialize')    
        UImanager.ApplyCommand('/tracking/verbose 2')
        UImanager.ApplyCommand(f"/run/beamOn {g4_dic['BeamOn']}")
    

if __name__ == '__main__':
    main()
