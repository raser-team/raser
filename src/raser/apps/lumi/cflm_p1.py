#!/usr/bin/env python3 
import math
from raser.core.interaction.geant4.g4ppyy_runtime import g4b
g4b.include("G4VUserDetectorConstruction.hh")
g4b.include("G4UserLimits.hh")
g4b.include("G4VUserActionInitialization.hh")
g4b.include("G4VUserPrimaryGeneratorAction.hh")
g4b.include("G4UserRunAction.hh")
g4b.include("G4UserEventAction.hh")
g4b.include("G4UserSteppingAction.hh")

pixelAreaZIndex = []
for i in range(2):
    pixelAreaZIndex.append(i)
pixelAreaYIndex = []
for y in range(-3, 3):
    pixelAreaYIndex.append(y) 

def simulate_bunches(g4_dic, seed):
    """Shoot the bunches of g4_dic and give the steps in every pad.

    Three dicts, [detector_I or detector_II][i_j] -> one entry per bunch:
    the positions of the steps [um, in the frame of the beam pipe], their
    energies [MeV], and the energy left in the pad [MeV]. A bunch without a
    step in a pad holds [[0, 0, 0]] and [0] there.
    """
    global s_eventIDs,s_edep_devices,s_p_steps,s_energy_steps
    s_eventIDs,s_edep_devices,s_p_steps,s_energy_steps = {}, {}, {}, {}


    for k  in ('I', 'II'):
        s_eventIDs[f'detector_{k}'] = {}
        s_edep_devices[f'detector_{k}'] = {}
        s_p_steps[f'detector_{k}'] = {}
        s_energy_steps[f'detector_{k}'] = {}
        for m in pixelAreaYIndex:
            for n in pixelAreaZIndex:
                s_eventIDs[f'detector_{k}'][f'{m}_{n}'] = []
                s_edep_devices[f'detector_{k}'][f'{m}_{n}'] = []
                s_p_steps[f'detector_{k}'][f'{m}_{n}'] = []
                s_energy_steps[f'detector_{k}'][f'{m}_{n}'] = []
        
    runManager = g4b.G4RunManager.GetRunManager() or g4b.G4RunManager()
    rand_engine= g4b.cppyy.gbl.CLHEP.RanecuEngine()
    g4b.cppyy.gbl.CLHEP.HepRandom.setTheEngine(rand_engine)
    g4b.cppyy.gbl.CLHEP.HepRandom.setTheSeed(seed)
    UImanager = g4b.G4UImanager.GetUIpointer()

    physicsList = g4b.FTFP_BERT()
    physicsList.SetVerboseLevel(0)
    # the physics list deletes what is registered in it: python must not
    stepLimiterPhysics = g4b.G4StepLimiterPhysics()
    stepLimiterPhysics.__python_owns__ = False
    physicsList.RegisterPhysics(stepLimiterPhysics)
    runManager.SetUserInitialization(physicsList)

    detConstruction = cflmDetectorConstruction(g4_dic)
    runManager.SetUserInitialization(detConstruction)

    actionInitialization = cflmaActionInitialization(detConstruction,
                                                    g4_dic['par_in'],
                                                    g4_dic['par_direct'],
                                                    g4_dic['par_type'],
                                                    g4_dic['par_energy'],
                                                    g4_dic['NumofGun']
                                                    )
    runManager.SetUserInitialization(actionInitialization)
            
    UImanager = g4b.G4UImanager.GetUIpointer()
    UImanager.ApplyCommand('/run/initialize')
    UImanager.ApplyCommand('/tracking/verbose 0')

    runManager.BeamOn(int(g4_dic['BeamOn']))

    # g4ppyy ends the detector with the run manager: an action that Geant4 deletes
    # later must not be the last to hold it
    actionInitialization.fDetConstruction = None
    actionInitialization.actions[3].fDetConstruction = None

    return s_p_steps, s_energy_steps, s_edep_devices


class cflmDetectorConstruction(g4b.G4VUserDetectorConstruction):

    def __init__(self,g4_dic):
        super().__init__()
        self.solid = {}
        self.logical = {}
        self.physical = {}
        self.checkOverlaps = True
        self.create_world(g4_dic['world'])
        self.detector_list = []
        self.detector_pos_list = []

        self.maxStep = g4_dic['maxStep']*g4b.um

        self.rotation = g4b.G4RotationMatrix()
        self.rotation.rotateZ(3*math.pi/2)
        
        self.create_pipe(g4_dic['pipe'])

        self.detMaterial()
        self.SiCdetector()
        self.create_vacuum(g4_dic['vacuum'])

        self.fStepLimit = g4b.G4UserLimits(self.maxStep)
        
        for i in pixelAreaYIndex:  
            for j in pixelAreaZIndex:
                for k in ('I', 'II'):
                    self.logical[f'detector_{k}_{i}_{j}'].SetUserLimits(self.fStepLimit)
        
    def create_world(self,world_type):

        self.nist = g4b.G4NistManager.Instance()
        material = self.nist.FindOrBuildMaterial(world_type)
        self.solid['world'] = g4b.G4Box("world",
                                        2000*g4b.mm,
                                        2000*g4b.mm,
                                        2000*g4b.mm)
        self.logical['world'] = g4b.G4LogicalVolume(self.solid['world'],
                                                    material,
                                                    "world")
        self.physical['world'] = g4b.G4PVPlacement(g4b.cppyy.nullptr,
                                                   g4b.G4ThreeVector(0,0,0),
                                                   self.logical['world'],
                                                   "world", 
                                                   g4b.cppyy.nullptr, 
                                                   False,
                                                   0,
                                                   self.checkOverlaps)

        self.logical['world'].SetVisAttributes(g4b.G4VisAttributes.GetInvisible())

    
    def create_pipe(self,object):
        
        pipe_name = object['name']
        material_type = self.nist.FindOrBuildMaterial(object['material'],
                                                    False)

        translation = g4b.G4ThreeVector(object['position_x']*g4b.mm, object['position_y']*g4b.mm, object['position_z']*g4b.mm)
        visual = g4b.G4VisAttributes(g4b.G4Color(0, 0, 0, 0.1))
        visual.SetForceWireframe(True)
        visual.SetForceAuxEdgeVisible(True)
        mother = self.physical['world']

        Rmin = object['Rmin']*g4b.mm
        Rmax = object['Rmax']*g4b.mm
        Pipe_Z = object['Pipe_Z']*g4b.mm
        PipeSphi = object['PipeSphi']*g4b.deg
        PipeDphi = object['PipeDphi']*g4b.deg

        self.solid[pipe_name] = g4b.G4Tubs("Pipe", Rmin, Rmax, Pipe_Z/2,PipeSphi,PipeDphi)

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
        material_type = self.nist.FindOrBuildMaterial("G4_Galactic")

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
        
    def SiCdetector(self):
        for k in (-31.05, 31.05):
            for i in pixelAreaYIndex: 
                for j in pixelAreaZIndex:
                    if k==-31.05:
                       name = f"detector_I_{i}_{j}"
                       print(name)
                    else:
                        name = f"detector_II_{i}_{j}"
                        print(name)
                    if i>=0:
                        y_position = (i * 5 + 2.5) * g4b.mm
                        z_position = (j * 5 + 2.5 + 225) * g4b.mm
                        translation = g4b.G4ThreeVector(k * g4b.mm, y_position, z_position)
                        visual = g4b.G4VisAttributes(g4b.G4Color(1, 0.6, 0))
                        mother = self.physical['world']
                        sidex = 5 * g4b.mm
                        sidey = 0.1 * g4b.mm
                        sidez = 5 * g4b.mm

                        self.solid[name] = g4b.G4Box(name, sidex / 2., sidey / 2., sidez / 2.)

                        self.logical[name] = g4b.G4LogicalVolume(self.solid[name], self.compound, name)
                        self.physical[name] = g4b.G4PVPlacement(self.rotation, translation, name, self.logical[name], mother, False, 0, self.checkOverlaps)
                        self.logical[name].SetVisAttributes(visual)
                    if i<0:
                        y_position = ((i + 1) * 5 - 2.5) * g4b.mm
                        z_position = (j * 5 + 2.5 + 225) * g4b.mm
                        translation = g4b.G4ThreeVector(k * g4b.mm, y_position, z_position)
                        visual = g4b.G4VisAttributes(g4b.G4Color(1, 0.6, 0))
                        mother = self.physical['world']
                        sidex = 5 * g4b.mm
                        sidey = 0.1 * g4b.mm
                        sidez = 5 * g4b.mm

                        self.solid[name] = g4b.G4Box(name, sidex / 2., sidey / 2., sidez / 2.)

                        self.logical[name] = g4b.G4LogicalVolume(self.solid[name], self.compound, name)
                        self.physical[name] = g4b.G4PVPlacement(self.rotation, translation, name, self.logical[name], mother, False, 0, self.checkOverlaps)
                        self.logical[name].SetVisAttributes(visual)

    def detMaterial(self):
        material_1 = self.nist.FindOrBuildElement("Si", False)
        material_2 = self.nist.FindOrBuildElement("C", False)
        material_density = 3.2*g4b.g/g4b.cm3
        self.compound = g4b.G4Material("SiC", material_density, 2)
        self.compound.AddElement(material_1, 50*g4b.perCent)
        self.compound.AddElement(material_2, 50*g4b.perCent)

        return self.compound
    
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

    def __init__(self, detectorConstruction, eventAction):
        super().__init__()
        self.fDetConstruction = detectorConstruction
        self.fEventAction = eventAction

    def UserSteppingAction(self, step):
        volume_pre = step.GetPreStepPoint().GetTouchable().GetVolume()
        edep = step.GetTotalEnergyDeposit()
        point_in = step.GetPreStepPoint().GetPosition()

        if volume_pre == self.fDetConstruction.physical['pipe']:
            self.fEventAction.AddPipe(edep)
        
        for k in ('I', 'II'):
            for i in pixelAreaYIndex:
                for j in pixelAreaZIndex:
                    if volume_pre == self.fDetConstruction.physical[f'detector_{k}_{i}_{j}']:
                        self.fEventAction.RecordDetector(edep, point_in, k, i, j) 

class cflmaEventAction(g4b.G4UserEventAction):

    def BeginOfEventAction(self, event):
        self.edepPixelArea = {}
        self.p_stepPixelArea = {}
        self.edepStepPixelArea = {}
        for k in ('I', 'II'):
            self.edepPixelArea[f'detector_{k}'] = {}
            self.p_stepPixelArea[f'detector_{k}'] = {}
            self.edepStepPixelArea[f'detector_{k}'] = {}
            for m in pixelAreaYIndex:
                for n in pixelAreaZIndex:
                    self.edepPixelArea[f'detector_{k}'][f'{m}_{n}'] = 0
                    self.p_stepPixelArea[f'detector_{k}'][f'{m}_{n}'] = []
                    self.edepStepPixelArea[f'detector_{k}'][f'{m}_{n}'] = []
        self.totalDetectEdep = 0
        self.fEnergyPipe = 0       
        self.dividedAreaIndex = []

    def EndOfEventAction(self, event):
        
        eventID = event.GetEventID()
        for k in ('I', 'II'):  
            for i in pixelAreaYIndex:
                for j in pixelAreaZIndex:
                    save_geant4_events(eventID, self.edepPixelArea[f'detector_{k}'][f'{i}_{j}'], self.p_stepPixelArea[f'detector_{k}'][f'{i}_{j}'], self.edepStepPixelArea[f'detector_{k}'][f'{i}_{j}'], i, j, k)
        printModulo = g4b.G4RunManager.GetRunManager().GetPrintProgress()
        if printModulo > 0 and eventID % printModulo == 0:
            print("---> End of event:", eventID)
            print("Pipe: total energy:", self.fEnergyPipe / g4b.MeV, "MeV")
            for k in ('I', 'II'):
                for i in pixelAreaYIndex:
                    for j in pixelAreaZIndex:
                        self.totalDetectEdep += self.edepPixelArea[f'detector_{k}'][f'{i}_{j}']
                        print(f"Detector_{k}_{i}_{j}: total energy:", self.edepPixelArea[f'detector_{k}'][f'{i}_{j}'] / g4b.MeV, "MeV")
            print('total energy deposition of detect area:', self.totalDetectEdep / g4b.MeV, "MeV")

    def AddPipe(self, de):
        self.fEnergyPipe += de

    def RecordDetector(self, edep, point_in, k, i, j):
        self.edepPixelArea[f'detector_{k}'][f'{i}_{j}'] += edep 
        self.p_stepPixelArea[f'detector_{k}'][f'{i}_{j}'].append([point_in.getX()*1000,
                                              point_in.getY()*1000,
                                              point_in.getZ()*1000])
        self.edepStepPixelArea[f'detector_{k}'][f'{i}_{j}'].append(edep)
        
class cflmRunAction(g4b.G4UserRunAction):

    def __init__(self):
        super().__init__()

        g4b.G4RunManager.GetRunManager().SetPrintProgress(1)

        analysisManager = g4b.G4AnalysisManager.Instance()
        print("Using", analysisManager.GetType())


        analysisManager.SetVerboseLevel(1)
        
    def BeginOfRunAction(self, run):
        if self.IsMaster():
            print("Begin of run for the entire run \n")
        else:
            print("Begin of run for the local thread \n")

    def EndOfRunAction(self, run):
        if self.IsMaster():
            print("End of run for the entire run \n")
        else:
            print("End of run for the local thread \n")


class cflmaActionInitialization(g4b.G4VUserActionInitialization):

    def __init__(self, detConstruction, par_in, par_direct, par_type, par_energy, numofgun):
        super().__init__()
        self.fDetConstruction = detConstruction
        self.par_in = par_in
        self.par_direct = par_direct
        self.par_type=par_type
        self.par_energy=par_energy
        self.numofgun = numofgun

    def BuildForMaster(self):
        self.SetUserAction(cflmRunAction())
    def Build(self):
        # Geant4 holds bare pointers to the actions: they are kept here
        self.actions = [
            cflmPrimaryGeneratorAction(self.par_in,
                                       self.par_direct,
                                       self.par_type,
                                       self.par_energy,
                                       self.numofgun),
            cflmRunAction(),
            cflmaEventAction(),
        ]
        self.actions.append(cflmaSteppingAction(self.fDetConstruction, self.actions[2]))
        for action in self.actions:
            self.SetUserAction(action)

def save_geant4_events(eventID,edep_device,p_step,energy_step, i, j, k):
    key = f'{i}_{j}'
    if(len(p_step)>0):
        s_eventIDs[f'detector_{k}'][key].append(eventID)
        s_edep_devices[f'detector_{k}'][key].append(edep_device)
        s_p_steps[f'detector_{k}'][key].append(p_step)
        s_energy_steps[f'detector_{k}'][key].append(energy_step)
    else:
        s_eventIDs[f'detector_{k}'][key].append(eventID)
        s_edep_devices[f'detector_{k}'][key].append(edep_device)
        s_p_steps[f'detector_{k}'][key].append([[0,0,0]])
        s_energy_steps[f'detector_{k}'][key].append([0]) 
