#!/usr/bin/env python3 

'''
@Description:
    Geant4 simulation for bmos detector
@Date       : 2024
@Author     : Ye He, Kaibo Xie
@version    : 2.0
'''

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
import numpy as np
import time

#G4AnalysisManager = g4b.G4RootAnalysisManager

X_position = []
Z_position = []
Y_position = []
Particle = []


class bmosG4Interaction:

    def __init__(self, my_d):

        global s_eventIDs, s_edep_devices, s_p_steps, s_energy_steps
        s_eventIDs, s_edep_devices, s_p_steps, s_energy_steps = [], [], [], []

        geant4_json = os.getenv("RASER_SETTING_PATH")+"/g4experiment/bmos.json"
        with open(geant4_json) as f:
             g4_dic = json.load(f)

        self.geant4_model = g4_dic["geant4_model"]

        runManager = g4b.G4RunManager.GetRunManager() or g4b.G4RunManager()
        UImanager = g4b.G4UImanager.GetUIpointer()

        physicsList = g4b.FTFP_BERT()
        physicsList.SetVerboseLevel(1)
        physicsList.RegisterPhysics(g4b.G4StepLimiterPhysics())
        runManager.SetUserInitialization(physicsList)

        detConstruction = DetectorConstruction(g4_dic)
        runManager.SetUserInitialization(detConstruction)

        actionInitialization = ActionInitialization(detConstruction,
                                                    g4_dic['par_in'],
                                                    g4_dic['par_direction'],
                                                    g4_dic['par_type'],
                                                    g4_dic['par_energy'],
                                                    g4_dic['par_num'],
                                                    )

        runManager.SetUserInitialization(actionInitialization)

        UImanager = g4b.G4UImanager.GetUIpointer()
        UImanager.ApplyCommand('/run/initialize')

        runManager.BeamOn(int(g4_dic['BeamOn']))

        self.p_steps = s_p_steps
        self.init_tz_device = 0
        self.p_steps_current = [[[single_step[0]+my_d.l_x/2,
                                  single_step[1]+my_d.l_y/2,
                                  single_step[2]-self.init_tz_device]\
                for single_step in p_step] for p_step in self.p_steps]

        self.energy_steps = s_energy_steps
        self.edep_devices = s_edep_devices

        print("sum edep = ", sum(s_energy_steps[0]))
        # time.sleep(10)

        del s_eventIDs,s_edep_devices,s_p_steps,s_energy_steps
 

class DetectorConstruction(g4b.G4VUserDetectorConstruction):

    def __init__(self,g4_dic):
        g4b.G4VUserDetectorConstruction.__init__(self)
        self.solid = {}
        self.logical = {}
        self.physical = {}
        self.checkOverlaps = True
        self.create_world(g4_dic['world_type'], g4_dic['world_size'])

        self.maxStep = g4_dic['maxStep']*g4b.um

        # self.rotation = g4b.G4RotationMatrix()
        # self.rotation.rotateZ(3*math.pi/2)

        for object_type in g4_dic['object']:
            if(object_type=="elemental"):
                for every_object in g4_dic['object'][object_type]:
                    self.create_elemental(g4_dic['object'][object_type][every_object])
            if(object_type=="binary_compounds"):
                for every_object in g4_dic['object'][object_type]:
                    self.create_binary_compounds(g4_dic['object'][object_type][every_object])

        self.fStepLimit = g4b.G4UserLimits(self.maxStep)
        self.logical["detector"].SetUserLimits(self.fStepLimit)

    def create_world(self, world_type, world_size):

        self.nist = g4b.G4NistManager.Instance()
        material = self.nist.FindOrBuildMaterial(world_type)  
        self.solid['world'] = g4b.G4Box("world",
                                        world_size*g4b.um,
                                        world_size*g4b.um,
                                        world_size*g4b.um)
        self.logical['world'] = g4b.G4LogicalVolume(self.solid['world'], 
                                                    material, 
                                                    "world")
        self.physical['world'] = g4b.G4PVPlacement(None, 
                                                   g4b.G4ThreeVector(0,0,0), 
                                                   self.logical['world'], 
                                                   "world", None, False, 
                                                   0,self.checkOverlaps)
        
        self.logical['world'].SetVisAttributes(g4b.G4VisAttributes.GetInvisible())

    def create_elemental(self,object): 
        name = object['name']
        material_type = self.nist.FindOrBuildMaterial(object['material'],
                                                    False)
        translation = g4b.G4ThreeVector(object['position_x']*g4b.um, object['position_y']*g4b.um, object['position_z']*g4b.um)
        visual = g4b.G4VisAttributes(g4b.G4Color(object['colour'][0],object['colour'][1],object['colour'][2]))
        mother = self.physical['world']
        sidex = object['side_x']*g4b.um
        sidey = object['side_y']*g4b.um
        sidez = object['side_z']*g4b.um
        self.solid[name] = g4b.G4Box(name, sidex/2., sidey/2., sidez/2.)
        
        self.logical[name] = g4b.G4LogicalVolume(self.solid[name], 
                                                material_type, 
                                                name)
        self.physical[name] = g4b.G4PVPlacement(None,translation,                                                
                                                name,self.logical[name],
                                                mother, False, 
                                                0,self.checkOverlaps)
        self.logical[name].SetVisAttributes(visual)     

    def create_binary_compounds(self,object):
        name = object['name']
        material_1 = self.nist.FindOrBuildElement(object['material_1'],False)
        material_2 = self.nist.FindOrBuildElement(object['material_2'],False)
        material_density = object['density']*g4b.g/g4b.cm3
        compound=g4b.G4Material(object['compound_name'],material_density,2) 
        compound.AddElement(material_1,object['natoms_1']*g4b.perCent)
        compound.AddElement(material_2,object['natoms_2']*g4b.perCent)
        translation = g4b.G4ThreeVector(object['position_x']*g4b.um, object['position_y']*g4b.um, object['position_z']*g4b.um)
        visual = g4b.G4VisAttributes(g4b.G4Color(object['colour'][0],object['colour'][1],object['colour'][2]))
        mother = self.physical['world']
        sidex = object['side_x']*g4b.um
        sidey = object['side_y']*g4b.um
        sidez = object['side_z']*g4b.um

        if not 'tub' in object:
            self.solid[name] = g4b.G4Box(name, sidex/2., sidey/2., sidez/2.)
        else:
            self.solid[name+"box"] = g4b.G4Box(name+"box", 
                                           sidex/2., sidey/2., sidez/2.)
            self.solid[name+"tub"] = g4b.G4Tubs(name+"tub", 0,object['tub']['tub_radius']*g4b.um,
                                                object['tub']['tub_depth']*g4b.um, 0,360*g4b.deg)
            self.solid[name] = g4b.G4SubtractionSolid(name,
                                                    self.solid[name+"box"],
                                                    self.solid[name+"tub"])
            
        self.logical[name] = g4b.G4LogicalVolume(self.solid[name], 
                                                 compound, 
                                                 name)
        self.physical[name] = g4b.G4PVPlacement(None,translation,                                                
                                                name,self.logical[name],
                                                mother, False, 
                                                0,self.checkOverlaps)
        self.logical[name].SetVisAttributes(visual)

    def Construct(self): 
        return self.physical['world']

class ActionInitialization(g4b.G4VUserActionInitialization):
    def __init__(self, detConstruction, par_in, par_direction, par_type, par_energy, par_num):
        super().__init__()
        self.fDetConstruction = detConstruction
        self.par_in = par_in
        self.par_direction = par_direction
        self.par_type = par_type
        self.par_energy = par_energy
        self.par_num = par_num

        self.par_out = [0, 0, 0]

    def Build(self):
        self.SetUserAction(PrimaryGeneratorAction(self.par_in,
                                                  self.par_direction,
                                                  self.par_type,
                                                  self.par_energy,
                                                  self.par_num))
                                                    
        myRA_action = MyRunAction()
        self.SetUserAction(myRA_action)
        myEA = EventAction(myRA_action, self.par_in, self.par_out)
        self.SetUserAction(myEA)
        self.SetUserAction(MySteppingAction(myEA))

class PrimaryGeneratorAction(g4b.G4VUserPrimaryGeneratorAction):
    "My Primary Generator Action"
    def __init__(self, par_in, par_direction, par_type, par_energy, par_num):
        g4b.G4VUserPrimaryGeneratorAction.__init__(self)
        self.par_num = par_num
        self.par_direction = par_direction
        self.par_energy = par_energy
        self.par_in = par_in
        particle_table = g4b.G4ParticleTable.GetParticleTable()
        self.particle = particle_table.FindParticle(par_type) # define particle
        
    def GeneratePrimaries(self, event):
        for i in range(self.par_num):
            par_direction = self.par_direction[i]
            par_in = self.par_in[i]
            beam = g4b.G4ParticleGun(1)
            beam.SetParticleEnergy(self.par_energy*g4b.MeV)
            beam.SetParticleMomentumDirection(g4b.G4ThreeVector(par_direction[0],
                                                                par_direction[1],
                                                                par_direction[2]))
            beam.SetParticleDefinition(self.particle)
            beam.SetParticlePosition(g4b.G4ThreeVector(par_in[0]*g4b.um,
                                                       par_in[1]*g4b.um,
                                                       par_in[2]*g4b.um))
            self.particleGun = beam

            self.particleGun.GeneratePrimaryVertex(event)

class MyRunAction(g4b.G4UserRunAction):
    def __init__(self):
        g4b.G4UserRunAction.__init__(self)
      
    def BeginOfRunAction(self, run):
        g4b.G4RunManager.GetRunManager().SetRandomNumberStore(False)
   
    def EndOfRunAction(self, run):
        nofEvents = run.GetNumberOfEvent()
        if nofEvents == 0:
            print("nofEvents=0")
            return
        
class EventAction(g4b.G4UserEventAction):
    "My Event Action"
    def __init__(self, runAction, point_in, point_out):
        g4b.G4UserEventAction.__init__(self)
        self.fRunAction = runAction
        self.point_in = point_in
        self.point_out = point_out

    def BeginOfEventAction(self, event):
        self.edep_device=0.
        self.event_angle = 0.
        self.p_step = []
        self.energy_step = []
        #use in pixel_detector
        self.volume_name = []
        self.localposition = []
        global eventID
        eventID = event.GetEventID()

    def EndOfEventAction(self, event):
        eventID = event.GetEventID()
        print("eventID:%s end"%eventID)
        # if len(self.p_step):
        #     point_a = [ b-a for a,b in zip(self.point_in,self.point_out)]
        #     point_b = [ c-a for a,c in zip(self.point_in,self.p_step[-1])]
        #     self.event_angle = cal_angle(point_a, point_b)
        # else:
        #     self.event_angle = None

        # save_geant4_events(eventID, self.edep_device, self.p_step, self.energy_step, self.event_angle)
        save_geant4_events(eventID, self.edep_device, self.p_step, self.energy_step)

    def RecordDevice(self, edep, point_in, point_out):
        self.edep_device += edep
        self.p_step.append([point_in.getX()*1000,
                           point_in.getY()*1000,point_in.getZ()*1000])
        self.energy_step.append(edep)

        
def cal_angle(point_a,point_b):
    "Calculate the angle between point a and b"
    x=np.array(point_a)
    y=np.array(point_b)
    l_x=np.sqrt(x.dot(x))
    l_y=np.sqrt(y.dot(y))
    dot_product=x.dot(y)
    if l_x*l_y > 0:
        cos_angle_d=dot_product/(l_x*l_y)
        angle_d=np.arccos(cos_angle_d)*180/np.pi
    else:
        angle_d=9999
    return angle_d
    
def save_geant4_events(eventID, edep_device, p_step, energy_step):
    print("save")
    time.sleep(1)

    if(len(p_step)>0):
        s_eventIDs.append(eventID)
        s_edep_devices.append(edep_device)
        s_p_steps.append(p_step)
        s_energy_steps.append(energy_step)
        # s_events_angle.append(event_angle)
    else:
        s_eventIDs.append(eventID)
        s_edep_devices.append(edep_device)
        s_p_steps.append([[0,0,0]])
        s_energy_steps.append([0])
        # s_events_angle.append(event_angle)
        
class MySteppingAction(g4b.G4UserSteppingAction):
    "My Stepping Action"
    def __init__(self, eventAction):
        g4b.G4UserSteppingAction.__init__(self)
        self.fEventAction = eventAction

    def UserSteppingAction(self, step):
        edep = step.GetTotalEnergyDeposit()
        point_pre  = step.GetPreStepPoint()
        point_post = step.GetPostStepPoint() 
        point_in   = point_pre.GetPosition()
        point_out  = point_post.GetPosition()
        volume = step.GetPreStepPoint().GetTouchable().GetVolume().GetLogicalVolume()
        volume_name = volume.GetName()
        # print(volume_name)
        # time.sleep(0.5)

        if(volume_name == "detector"): # important, no if => no signal
            self.fEventAction.RecordDevice(edep, point_in, point_out)
