#!/usr/bin/env python3 
import os
import math
import array
import ROOT
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

pixelAreaZIndex = []
for i in range(2):
    pixelAreaZIndex.append(i)
pixelAreaYIndex = []
for y in range(-3, 3):
    pixelAreaYIndex.append(y) 

output_path = output(__file__, "N0_3_4")

class cflmPixelG4Particles:

    def __init__(self, my_d, i, j, l):

        global s_eventIDs,s_edep_devices,s_p_steps,s_energy_steps
        s_eventIDs,s_edep_devices,s_p_steps,s_energy_steps = {}, {}, {}, {}

        global detectorID, pixelAreaEdep
        detectorID, pixelAreaEdep = [], []

        self.geant4_model = "cflm"

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
        
        json_s_p_steps_path = os.path.join(output_path, "s_p_steps.json")                        
        json_s_energy_steps_path = os.path.join(output_path, "s_energy_steps.json")           
        json_s_edep_devices_path = os.path.join(output_path, "s_edep_devices.json")          
                                        
        if os.path.exists(json_s_p_steps_path) and os.path.exists(json_s_energy_steps_path) and os.path.exists(json_s_edep_devices_path):
           if l=='I':
              with open(json_s_p_steps_path, 'r') as step_file:
                   step = json.load(step_file)
                   self.p_steps = step['detector_I'][f'{i}_{j}']
              with open(json_s_energy_steps_path, 'r') as step_energy_file:
                   step_energy = json.load(step_energy_file)
                   self.energy_steps = step_energy['detector_I'][f'{i}_{j}']
              with open(json_s_edep_devices_path, 'r') as edep_device_file: 
                   edep_device = json.load(edep_device_file)
                   self.edep_devices = edep_device['detector_I'][f'{i}_{j}']
                
              self.init_tz_device = -31
              if i>=0:
                 y_position = (i * 5 + 2.5)
              elif i<0:
                 y_position = ((i + 1) * 5 - 2.5)
                    
              z_position = (j * 5 + 2.5 + 225)

              self.HitFlag = 0  
              if len(self.p_steps[0]) != 1:
                 self.HitFlag = 1
                    
              self.p_steps_current=[[[my_d.l_x/2 - single_step[1] + y_position*1000,   ### *1000: mm---->um
                                      my_d.l_y/2 + single_step[2] - z_position*1000,
                                      self.init_tz_device*1000 - single_step[0]]\
                              for single_step in p_step] for p_step in self.p_steps]
           elif l=='II':
              with open(json_s_p_steps_path, 'r') as step_file:
                   step = json.load(step_file)
                   self.p_steps = step['detector_II'][f'{i}_{j}']
              with open(json_s_energy_steps_path, 'r') as step_energy_file:
                   step_energy = json.load(step_energy_file)
                   self.energy_steps = step_energy['detector_II'][f'{i}_{j}']
              with open(json_s_edep_devices_path, 'r') as edep_device_file:
                   edep_device = json.load(edep_device_file)
                   self.edep_devices = edep_device['detector_II'][f'{i}_{j}']
                
              self.init_tz_device = 31
              if i>=0:
                 y_position = (i * 5 + 2.5)
              elif i<0:
                 y_position = ((i + 1) * 5 - 2.5)
                    
              z_position = (j * 5 + 2.5 + 225)
                    
              self.HitFlag = 0  
              if len(self.p_steps[0]) != 1:
                 self.HitFlag = 1

              self.p_steps_current=[[[my_d.l_x/2 - single_step[1] + y_position*1000,   ### *1000: mm---->um
                                      my_d.l_y/2 + single_step[2] - z_position*1000,
                                      single_step[0] - self.init_tz_device*1000]\
                              for single_step in p_step] for p_step in self.p_steps]
        
        else:       
            geant4_json = app_file_path("lumi", "cflm_p1.json")
            with open(geant4_json) as f:
                g4_dic = json.load(f)

            runManager = g4b.G4RunManager.GetRunManager() or g4b.G4RunManager()
            rand_engine= g4b.cppyy.gbl.CLHEP.RanecuEngine()
            g4b.cppyy.gbl.CLHEP.HepRandom.setTheEngine(rand_engine)
            g4b.cppyy.gbl.CLHEP.HepRandom.setTheSeed(3020122)
            UImanager = g4b.G4UImanager.GetUIpointer()

            physicsList = g4b.FTFP_BERT()
            physicsList.SetVerboseLevel(0)
            physicsList.RegisterPhysics(g4b.G4StepLimiterPhysics())
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

            SaveJson(s_p_steps, json_s_p_steps_path)
            SaveJson(s_energy_steps, json_s_energy_steps_path)
            SaveJson(s_edep_devices, json_s_edep_devices_path)
        def __del__(self):
            pass


class cflmDetectorConstruction(g4b.G4VUserDetectorConstruction):

    def __init__(self,g4_dic):
        g4b.G4VUserDetectorConstruction.__init__(self)
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
            print("Pipe: total energy:", g4b.G4BestUnit(self.fEnergyPipe, "Energy"))
            for k in ('I', 'II'):
                for i in pixelAreaYIndex:
                    for j in pixelAreaZIndex:
                        detectorID.append([k,[i, j]])
                        pixelAreaEdep.append(self.edepPixelArea[f'detector_{k}'][f'{i}_{j}'])
                        self.totalDetectEdep += self.edepPixelArea[f'detector_{k}'][f'{i}_{j}']
                        print(f"Detector_{k}_{i}_{j}: total energy:", g4b.G4BestUnit(self.edepPixelArea[f'detector_{k}'][f'{i}_{j}'], "Energy"))
            print('total energy deposition of detect area:', g4b.G4BestUnit(self.totalDetectEdep, "Energy"))

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

        dividedAreaEdep(detectorID, pixelAreaEdep)

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
        self.SetUserAction(cflmPrimaryGeneratorAction(self.par_in,
                                                      self.par_direct,
                                                      self.par_type,
                                                      self.par_energy,
                                                      self.numofgun))
        self.SetUserAction(cflmRunAction())
        eventAction = cflmaEventAction()
        self.SetUserAction(eventAction)
        self.SetUserAction(cflmaSteppingAction(self.fDetConstruction, eventAction))

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

def dividedAreaEdep(detectorID, pixelAreaEdep): 
   
    i_value, j_value, valueEdep = array.array('d',[999.]), array.array('d',[999.]), array.array('d',[999.])
    
    file_I = ROOT.TFile(os.path.join(output_path, " detector_I_pixelEdep.root"), "RECREATE") 
    tree_I = ROOT.TTree("DetectorID", "DetectorID")
    file_II = ROOT.TFile(os.path.join(output_path, " detector_II_pixelEdep.root"), "RECREATE")
    tree_II = ROOT.TTree("DetectorID", "DetectorID")

    tree_I.Branch("i", i_value, 'i/D')
    tree_I.Branch("j", j_value, 'j/D')
    tree_I.Branch("Edep", valueEdep, 'valueEdep/D')
    tree_II.Branch("i", i_value, 'i/D')
    tree_II.Branch("j", j_value, 'j/D')
    tree_II.Branch("Edep", valueEdep, 'valueEdep/D')
    for m in range(len(detectorID)):      
        if detectorID[m][0]=='I':
            i_value[0] = float(detectorID[m][1][0])
            j_value[0] = float(detectorID[m][1][1])
            valueEdep[0] = float(pixelAreaEdep[m])
            tree_I.Fill()
        elif detectorID[m][0]=='II':
            i_value[0] = float(detectorID[m][1][0])
            j_value[0] = float(detectorID[m][1][1])
            valueEdep[0] = float(pixelAreaEdep[m])
            tree_II.Fill()

    file_I.Write()
    file_I.Close()
    file_II.Write()
    file_II.Close()

def SaveJson(dic, dicFile):
    with open(dicFile, 'w') as dic_file:
        json.dump(dic, dic_file)
    print(f'{dicFile} has been created successfully!')

def main():
        
    geant4_json = app_file_path("lumi", "cflm_p1.json")
    with open(geant4_json) as f:
         g4_dic = json.load(f)
    
    if g4_dic['vis']:
        runManager = g4b.G4RunManager.GetRunManager() or g4b.G4RunManager()

        physicsList = g4b.FTFP_BERT()
        physicsList.RegisterPhysics(g4b.G4StepLimiterPhysics())
        runManager.SetUserInitialization(physicsList)

        detConstruction = cflmDetectorConstruction(g4_dic)
        runManager.SetUserInitialization(detConstruction)

        visManager = g4b.G4VisExecutive()
        visManager.Initialize()
        UImanager = g4b.G4UImanager.GetUIpointer()

        UImanager.ApplyCommand("/control/execute {}".format(component_path("g4macro", "init_vis.mac")))
        UImanager.ApplyCommand('/run/initialize')
        UImanager.ApplyCommand('/tracking/verbose 0')
        UImanager.ApplyCommand("/vis/viewer/set/background 1 1 1")
        
        UImanager.ApplyCommand('/vis/ogl/set/printMode vectored')
        UImanager.ApplyCommand('/vis/ogl/export')

        for i in range(1000):
            UImanager.ApplyCommand("/vis/viewer/refresh") 
    else:
        
        from raser.core.device import build_device as bdv
        detector_json = component_path('detector', g4_dic['DetModule'])
        with open(detector_json) as q:
             det_dic = json.load(q)

        det_name = det_dic['det_name']
        my_d = bdv.Detector(det_name)
   
        my_g4p = cflmPixelG4Particles(my_d, i=0, j=0, l="I")  

if __name__ == '__main__':
    main()       
