#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
'''
Description: 
    geat4_pybind simulation   
@Date       : 2021/09/02 12:46:27
@Author     : tanyuhang
@version    : 1.0
   
@Date       : 2023/04/18
@Author     : xingchenli
@version    : 2.0
'''

import geant4_pybind as g4b
import sys
import numpy as np
import random

import json

# Geant4 main process
class Particles:
    #model name for other class to use
    _model = None
    #other pars may use in other class define here
    #use in pixel_detector
    _randx = None
    _randy = None
    def __init__(self, my_d, absorber, g4_seed):
        """
        Description:
            Geant4 main process
            Simulate s_num particles through device
            Record the energy depositon in the device
        Parameters:
        ---------
        energy_steps : list
            Energy deposition of each step in simulation
        edep_devices : list
            Total energy deposition in device          
        @Modify:
        ---------
            2023/04/18
        """	
        geant4_json = "./setting/absorber/" + absorber + ".json"
        with open(geant4_json) as f:
            g4_dic = json.load(f)

        self.geant4_model = g4_dic['geant4_model']
        detector_material=my_d.device_dict['material']
        if(self.geant4_model=='pixel_detector'):
            my_g4d = PixelDetectorConstruction(g4_dic,g4_dic['maxstep'])
            Particles._model = self.geant4_model
            Particles._randx = g4_dic['par_randx']
            Particles._randy = g4_dic['par_randy']
            #there's some parameter only use by this model
            global s_devicenames,s_localposition
            s_devicenames,s_localposition=[],[]
            print("end g4")
        else:
            my_g4d = MyDetectorConstruction(my_d,g4_dic,detector_material,g4_dic['maxstep'])		
        if g4_dic['g4_vis']: 
            ui = None
            ui = g4b.G4UIExecutive(len(sys.argv), sys.argv)
        g4RunManager = g4b.G4RunManagerFactory.CreateRunManager(g4b.G4RunManagerType.Default)
        rand_engine= g4b.RanecuEngine()
        g4b.HepRandom.setTheEngine(rand_engine)
        g4b.HepRandom.setTheSeed(g4_seed)
        g4RunManager.SetUserInitialization(my_g4d)
        # set physics list
        physics_list =  g4b.FTFP_BERT()
        physics_list.SetVerboseLevel(1)
        physics_list.RegisterPhysics(g4b.G4StepLimiterPhysics())
        g4RunManager.SetUserInitialization(physics_list)
        # define global parameter
        global s_eventIDs,s_edep_devices,s_p_steps,s_energy_steps,s_events_angle
        s_eventIDs,s_edep_devices,s_p_steps,s_energy_steps,s_events_angle=[],[],[],[],[]

        #define action
        g4RunManager.SetUserInitialization(MyActionInitialization(
                                          g4_dic['par_in'],
                                          g4_dic['par_out'],
                                          g4_dic['par_type'],
                                          g4_dic['par_energy'],
                                          self.geant4_model))
        if g4_dic['g4_vis']:    
            visManager = g4b.G4VisExecutive()
            visManager.Initialize()
            UImanager = g4b.G4UImanager.GetUIpointer()
            UImanager.ApplyCommand('/control/execute init_vis.mac')
        else:
            UImanager = g4b.G4UImanager.GetUIpointer()
            UImanager.ApplyCommand('/run/initialize')
            
        g4RunManager.BeamOn(int(g4_dic['total_events']))
        if g4_dic['g4_vis']:  
            ui.SessionStart()
        self.p_steps=s_p_steps
        self.init_tz_device = 0    
        self.p_steps_current=[[[single_step[0]+my_d.l_x/2,
                                single_step[1]+my_d.l_y/2,
                                single_step[2]-self.init_tz_device]\
            for single_step in p_step] for p_step in self.p_steps]
        self.energy_steps=s_energy_steps
        self.edep_devices=s_edep_devices
        self.events_angle=s_events_angle

        if(self.geant4_model=='pixel_detector'):
            #record localpos in logicvolume
            self.devicenames = s_devicenames
            self.localposition = s_localposition
            for i in range (0,len(s_devicenames)):
                #print("eventID:",i)
                #print("totalhits:",len(s_localposition[i]))
                pass
            del s_devicenames,s_localposition
                
        if(self.geant4_model=="beam_monitor"):
            hittotal=0
            for particleenergy in s_edep_devices:
                if(particleenergy>0):
                    hittotal=hittotal+1
            self.hittotal=hittotal      #count the numver of hit particles

            number=0
            total_steps=0
            for step in s_p_steps:
                total_steps=len(step)+total_steps
            average_steps=total_steps/len(s_p_steps)
            for step in s_p_steps:
                if(len(step)>=average_steps*0.9):
                    break
                number=number+1
            newtype_step=s_p_steps[number]      #new particle's step
            self.p_steps_current=[[[single_step[0]+my_d.l_x/2,
                                    single_step[1]+my_d.l_y/2,
                                    single_step[2]-self.init_tz_device]\
                for single_step in newtype_step]]
        
            newtype_energy=[0 for i in range(len(newtype_step))]
            for energy in s_energy_steps:
                for i in range(len(newtype_step)):
                    if(len(energy)>i):
                        newtype_energy[i]+=energy[i]
            self.energy_steps=[newtype_energy]      #new particle's every step energy

        del s_eventIDs,s_edep_devices,s_p_steps,s_energy_steps,s_events_angle
        
    def __del__(self):
        pass
#Geant4 for pixel_detector
class PixelDetectorConstruction(g4b.G4VUserDetectorConstruction):                
    "Pixel Detector Construction"
    def __init__(self,g4_dic,maxStep=0.5):
        g4b.G4VUserDetectorConstruction.__init__(self)
        self.g4_dic = g4_dic
        self.solid = {}
        self.logical = {}
        self.physical = {}
        self.checkOverlaps = True
        self.maxStep = maxStep*g4b.um
        self.fStepLimit = g4b.G4UserLimits(self.maxStep)
        self.create_world(g4_dic['world'])
        
        if(g4_dic['object']):
            for object_type in g4_dic['object']:#build all pixel first before build layer
                if(object_type=="pixel"):
                    for every_object in g4_dic['object'][object_type]:
                        self.create_pixel(g4_dic['object'][object_type][every_object])
            print("end pixel constrution")
            for object_type in g4_dic['object']:
                if(object_type=="layer"):
                    for every_object in g4_dic['object'][object_type]:
                        self.create_layer(g4_dic['object'][object_type][every_object])

        
        

    def create_world(self,world_type):

        self.nist = g4b.G4NistManager.Instance()
        material = self.nist.FindOrBuildMaterial(world_type)  
        self.solid['world'] = g4b.G4Box("world",
                                        25000*g4b.um,
                                        25000*g4b.um,
                                        50*g4b.cm)
        self.logical['world'] = g4b.G4LogicalVolume(self.solid['world'], 
                                                    material, 
                                                    "world")
        self.physical['world'] = g4b.G4PVPlacement(None, 
                                                   g4b.G4ThreeVector(0,0,0), 
                                                   self.logical['world'], 
                                                   "world", None, False, 
                                                   0,self.checkOverlaps)
        visual = g4b.G4VisAttributes()
        #visual.SetVisibility(False)
        self.logical['world'].SetVisAttributes(visual)
    
    def create_pixel(self,object):#build pixel 
        #pixel logicvolumn
        name = object['name']
        material_type = self.nist.FindOrBuildMaterial(object['material'],
                                                      False)
        print(type(material_type))
        visual = g4b.G4VisAttributes(g4b.G4Color(object['colour'][0],object['colour'][1],object['colour'][2]))
        sidex = object['side_x']*g4b.um
        sidey = object['side_y']*g4b.um
        sidez = object['side_z']*g4b.um
        self.solid[name] = g4b.G4Box(name, sidex/2., sidey/2., sidez/2.)
        
        self.logical[name] = g4b.G4LogicalVolume(self.solid[name], 
                                                 material_type, 
                                                 name)
        #different part define
        for every_object in object:
                if(every_object.startswith("part")):
                    part = object[every_object]
                    p_name = part['name']
                    p_element_1 = self.nist.FindOrBuildElement(part['element_1'],False)
                    p_element_2 = self.nist.FindOrBuildElement(part['element_2'],False)
                    p_natoms_1 = part['natoms_1']
                    p_natoms_2 = part['natoms_2']
                    p_density = part['density']*g4b.g/g4b.cm3
                    p_mixture=g4b.G4Material(part['mixture_name'],p_density,2) 
                    p_mixture.AddElement(p_element_1,p_natoms_1*g4b.perCent)
                    p_mixture.AddElement(p_element_2,p_natoms_2*g4b.perCent)
                    p_translation = g4b.G4ThreeVector(part['position_x']*g4b.um, part['position_y']*g4b.um, part['position_z']*g4b.um)
                    p_visual = g4b.G4VisAttributes(g4b.G4Color(part['colour'][0],part['colour'][1],part['colour'][2]))
                    
                    p_sidex = part['side_x']*g4b.um
                    p_sidey = part['side_y']*g4b.um
                    p_sidez = part['side_z']*g4b.um
                    p_mother = self.logical[name]
                    self.solid[p_name] = g4b.G4Box(p_name, p_sidex/2., p_sidey/2., p_sidez/2.)
                    self.logical[p_name] = g4b.G4LogicalVolume(self.solid[p_name], 
                                                 p_mixture, 
                                                 p_name)
                    
                    g4b.G4PVPlacement(None, p_translation, 
                                self.logical[p_name],p_name,
                                p_mother, False,
                                0,self.checkOverlaps)
                    p_visual.SetVisibility(False)
                    self.logical[p_name].SetVisAttributes(p_visual)    
                    
                     
        visual.SetVisibility(True)           
        self.logical[name].SetVisAttributes(visual)     
        self.logical[name].SetUserLimits(self.fStepLimit)  
        
    def create_layer(self,object):#build layer
        name = object['name']#temp use,muti layer need change Stepaction
        material_type = self.nist.FindOrBuildMaterial("G4_Galactic",
                                                      False)
        pixel_type = object['pixel_type']
        row = object['row']
        column = object['column']
        mother = self.physical['world']
        translation = g4b.G4ThreeVector(object['position_x']*g4b.um, object['position_y']*g4b.um, object['position_z']*g4b.um)
        rotation = g4b.G4RotationMatrix()
        rotation.rotateX(object['rotation_xyz'][0]*g4b.degree)
        rotation.rotateY(object['rotation_xyz'][1]*g4b.degree)
        rotation.rotateZ(object['rotation_xyz'][2]*g4b.degree)
        visual = g4b.G4VisAttributes(g4b.G4Color(object['colour'][0],object['colour'][1],object['colour'][2]))
        motherBox = g4b.G4Box("MotherBox", 1.0 * g4b.cm, 1.0 * g4b.cm, 250 * g4b.um)

        self.logical[name] = g4b.G4LogicalVolume(motherBox, 
                                                 material_type, 
                                                 name)
        for i in range(0,int(row)):
            for j in range(0,int(column)):
                pixel = self.g4_dic['object']['pixel'][pixel_type]
                t_translation = g4b.G4ThreeVector((pixel['side_x']*(j+1/2-column/2))*g4b.um, (pixel['side_y']*(i+1/2-row/2))*g4b.um,0.0*g4b.um)
                t_pixelname = pixel_type+'_'+str(i)+'_'+str(j)+'_'+name
                g4b.G4PVPlacement(None, t_translation, 
                                self.logical[pixel_type],t_pixelname,
                                self.logical[name], False,
                                i*int(column)+j,self.checkOverlaps)
                
        self.physical[name] = g4b.G4PVPlacement(rotation,translation,                                                
                                                name,self.logical[name],
                                                mother, False, 
                                                0,True)
        visual.SetVisibility(False)
        self.logical[name].SetVisAttributes(visual)   
        self.logical[name].SetUserLimits(self.fStepLimit)  
        
    def Construct(self): # return the world volume
        self.fStepLimit.SetMaxAllowedStep(self.maxStep)
        return self.physical['world']
        
#Geant4 for object
class MyDetectorConstruction(g4b.G4VUserDetectorConstruction):                
    "My Detector Construction"
    def __init__(self,my_d,g4_dic,detector_material,maxStep=0.5):
        g4b.G4VUserDetectorConstruction.__init__(self)
        self.solid = {}
        self.logical = {}
        self.physical = {}
        self.checkOverlaps = True
        self.create_world(g4_dic['world'])
        
        if(detector_material=='Si'):
            detector={
                        "name" : "Device",
                        "material" : "G4_Si",
                        "side_x" : my_d.l_x,
                        "side_y" : my_d.l_y,
                        "side_z" : my_d.l_z,
                        "colour" : [1,0,0],
                        "position_x" : 0,
                        "position_y" : 0,
                        "position_z" : my_d.l_z/2.0
                        }
            self.create_elemental(detector)

        if(detector_material=='SiC'):
            detector={
                        "name" : "Device",
                        "material_1" : "Si",
                        "material_2" : "C",
                        "compound_name" :"SiC",
                        "density" : 3.2,
                        "natoms_1" : 50,
                        "natoms_2" : 50,
                        "side_x" : my_d.l_x,
                        "side_y" : my_d.l_y,
                        "side_z" : my_d.l_z,
                        "colour" : [1,0,0],
                        "position_x" : 0,
                        "position_y" : 0,
                        "position_z" : my_d.l_z/2.0,
                        "tub" : {}
                        }
            self.create_binary_compounds(detector)
            
        if(g4_dic['object']):
            for object_type in g4_dic['object']:
                if(object_type=="elemental"):
                    for every_object in g4_dic['object'][object_type]:
                        self.create_elemental(g4_dic['object'][object_type][every_object])
                if(object_type=="binary_compounds"):
                    for every_object in g4_dic['object'][object_type]:
                        self.create_binary_compounds(g4_dic['object'][object_type][every_object])
       
        self.maxStep = maxStep*g4b.um
        self.fStepLimit = g4b.G4UserLimits(self.maxStep)
        self.logical["Device"].SetUserLimits(self.fStepLimit)

    def create_world(self,world_type):

        self.nist = g4b.G4NistManager.Instance()
        material = self.nist.FindOrBuildMaterial(world_type)  
        self.solid['world'] = g4b.G4Box("world",
                                        25000*g4b.um,
                                        25000*g4b.um,
                                        25000*g4b.um)
        self.logical['world'] = g4b.G4LogicalVolume(self.solid['world'], 
                                                    material, 
                                                    "world")
        self.physical['world'] = g4b.G4PVPlacement(None, 
                                                   g4b.G4ThreeVector(0,0,0), 
                                                   self.logical['world'], 
                                                   "world", None, False, 
                                                   0,self.checkOverlaps)
        visual = g4b.G4VisAttributes()
        visual.SetVisibility(False)
        self.logical['world'].SetVisAttributes(visual)

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
        if not(object['tub']):
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


    

    def Construct(self): # return the world volume
        self.fStepLimit.SetMaxAllowedStep(self.maxStep)
        return self.physical['world']


class MyPrimaryGeneratorAction(g4b.G4VUserPrimaryGeneratorAction):
    "My Primary Generator Action"
    def __init__(self,par_in,par_out,par_type,par_energy,geant4_model):
        g4b.G4VUserPrimaryGeneratorAction.__init__(self)
        self.geant4_model=geant4_model
        par_direction = [ par_out[i] - par_in[i] for i in range(3) ]  
        particle_table = g4b.G4ParticleTable.GetParticleTable()
        particle = particle_table.FindParticle(par_type) # define particle
        beam = g4b.G4ParticleGun(1)
        beam.SetParticleEnergy(par_energy*g4b.MeV)
        beam.SetParticleMomentumDirection(g4b.G4ThreeVector(par_direction[0],
                                                            par_direction[1],
                                                            par_direction[2]))
        beam.SetParticleDefinition(particle)
        beam.SetParticlePosition(g4b.G4ThreeVector(par_in[0]*g4b.um,
                                                   par_in[1]*g4b.um,
                                                   par_in[2]*g4b.um))  
        self.particleGun = beam
        self.position = par_in
        if(self.geant4_model=="time_resolution"):
            beam2 = g4b.G4ParticleGun(1)
            beam2.SetParticleEnergy(0.546*g4b.MeV)
            beam2.SetParticleMomentumDirection(g4b.G4ThreeVector(par_direction[0],
                                                                par_direction[1],
                                                                par_direction[2]))
            beam2.SetParticleDefinition(particle)
            beam2.SetParticlePosition(g4b.G4ThreeVector(par_in[0]*g4b.um,
                                                        par_in[1]*g4b.um,
                                                        par_in[2]*g4b.um))  
            self.particleGun2 = beam2
        if(self.geant4_model=="pixel_detector"):
            self.directionx = par_direction[0]
            self.directiony = par_direction[1]
            self.directionz = par_direction[2]

    def GeneratePrimaries(self, event):
        if(self.geant4_model=="time_resolution"):
            self.particleGun.GeneratePrimaryVertex(event)
            self.particleGun2.GeneratePrimaryVertex(event)
            pass
        elif(self.geant4_model=="pixel_detector"):
            randx = Particles._randx
            randy = Particles._randy
            rdo_x = random.uniform(-randx,randx)
            rdo_y = random.uniform(-randy,randy)
            rdi_x = random.uniform(-randx,randx)
            rdi_y = random.uniform(-randy,randy)
            direction = g4b.G4ThreeVector(rdo_x,rdo_y,self.directionz)
            self.particleGun.SetParticleMomentumDirection(direction)
            self.particleGun.SetParticlePosition(g4b.G4ThreeVector(self.position[0]*g4b.um,
                                                   self.position[1]*g4b.um,
                                                   self.position[2]*g4b.um))  
            self.particleGun.GeneratePrimaryVertex(event)
            #print("direction:",rdo_x-rdi_x,rdo_y-rdi_y,self.directionz)
            #print(rdi_x,rdi_y,self.position[2])
        else:
            self.particleGun.GeneratePrimaryVertex(event)
            
        


class MyRunAction(g4b.G4UserRunAction):
    def __init__(self):
        g4b.G4UserRunAction.__init__(self)
        milligray = 1.e-3*g4b.gray
        microgray = 1.e-6*g4b.gray
        nanogray = 1.e-9*g4b.gray
        picogray = 1.e-12*g4b.gray

        g4b.G4UnitDefinition("milligray", "milliGy", "Dose", milligray)
        g4b.G4UnitDefinition("microgray", "microGy", "Dose", microgray)
        g4b.G4UnitDefinition("nanogray", "nanoGy", "Dose", nanogray)
        g4b.G4UnitDefinition("picogray", "picoGy", "Dose", picogray)
      
    def BeginOfRunAction(self, run):
        g4b.G4RunManager.GetRunManager().SetRandomNumberStore(False)
   
    def EndOfRunAction(self, run):
        nofEvents = run.GetNumberOfEvent()
        if nofEvents == 0:
            print("nofEvents=0")
            return

class MyEventAction(g4b.G4UserEventAction):
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

    def EndOfEventAction(self, event):
        eventID = event.GetEventID()
        #print("eventID:%s"%eventID)
        if len(self.p_step):
            point_a = [ b-a for a,b in zip(self.point_in,self.point_out)]
            point_b = [ c-a for a,c in zip(self.point_in,self.p_step[-1])]
            self.event_angle = cal_angle(point_a,point_b)
        else:
            self.event_angle = None
        save_geant4_events(eventID,self.edep_device,
                           self.p_step,self.energy_step,self.event_angle)
        if(Particles._model == "pixel_detector"):
            save_pixel_detector_events(self.volume_name,self.localposition)

    def RecordDevice(self, edep,point_in,point_out):
        self.edep_device += edep
        self.p_step.append([point_in.getX()*1000,
                           point_in.getY()*1000,point_in.getZ()*1000])
        self.energy_step.append(edep)
    
    def RecordPixel(self,step):
        edep = step.GetTotalEnergyDeposit()
        point_pre  = step.GetPreStepPoint()
        point_post = step.GetPostStepPoint() 
        point_in   = point_pre.GetPosition()
        point_out  = point_post.GetPosition()
        if(edep<=0.0):
            return
        touchable = point_pre.GetTouchable()
        volume = touchable.GetVolume()
            
        transform = touchable.GetHistory().GetTopTransform()
        localpos = transform.TransformPoint(point_in)
        
        self.edep_device += edep
        self.p_step.append([point_in.getX()*1000,
                           point_in.getY()*1000,point_in.getZ()*1000])
        self.energy_step.append(edep)   
        #save only in RecordPixel
        self.volume_name.append(volume.GetName())
        self.localposition.append([localpos.getX()/g4b.um,localpos.getY()/g4b.um,localpos.getZ()/g4b.um])
        
        #print("edep:", edep)
        #print("Volume Name:", volume.GetName())
        #print("Global Position in Worlds Volume:",point_in/g4b.um)
        #print("Local Position in Pixel:", localpos/g4b.um)

def save_geant4_events(eventID,edep_device,p_step,energy_step,event_angle):
    if(len(p_step)>0):
        s_eventIDs.append(eventID)
        s_edep_devices.append(edep_device)
        s_p_steps.append(p_step)
        s_energy_steps.append(energy_step)
        s_events_angle.append(event_angle)
    else:
        s_eventIDs.append(eventID)
        s_edep_devices.append(edep_device)
        s_p_steps.append([[0,0,0]])
        s_energy_steps.append([0])
        s_events_angle.append(event_angle)
        
def save_pixel_detector_events(volume_name,localposition):
        global s_devicenames,s_localposition
        s_devicenames.append(volume_name)
        s_localposition.append(localposition)
        #print("volume_name len:",len(volume_name))
        #print("localposition len: ",len(localposition))
        
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
        if(volume_name == "Device"):
            self.fEventAction.RecordDevice(edep,point_in,point_out)
        if(volume_name.startswith("Taichu")):
            self.fEventAction.RecordPixel(step)
            return

class MyActionInitialization(g4b.G4VUserActionInitialization):
    def __init__(self,par_in,par_out,par_type,par_energy,geant4_model):
        g4b.G4VUserActionInitialization.__init__(self)
        self.par_in = par_in
        self.par_out = par_out
        self.par_type=par_type
        self.par_energy=par_energy
        self.geant4_model=geant4_model

    def Build(self):
        self.SetUserAction(MyPrimaryGeneratorAction(self.par_in,
                                                    self.par_out,
                                                    self.par_type,
                                                    self.par_energy,
                                                    self.geant4_model))
        # global myRA_action
        myRA_action = MyRunAction()
        self.SetUserAction(myRA_action)
        myEA = MyEventAction(myRA_action,self.par_in,self.par_out)
        self.SetUserAction(myEA)
        self.SetUserAction(MySteppingAction(myEA))

