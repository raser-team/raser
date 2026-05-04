'''
Description:  detector_construction.py
@Date       : 2025
@Author     : Yuhang Tan, Chenxi Fu (Original: Geant4)
@version    : 2.0
'''

import geant4_pybind as g4b

world_size = 25000
# TODO: move this to setting

class GeneralDetectorConstruction(g4b.G4VUserDetectorConstruction):                
    "My Detector Construction"
    def __init__(self,my_d,g4_dic,detector_material,maxStep=0.5):
        g4b.G4VUserDetectorConstruction.__init__(self)
        self.solid = {}
        self.logical = {}
        self.physical = {}
        self.checkOverlaps = True
        self.create_world(g4_dic['world'])
        self.geant4_model = g4_dic['geant4_model']
        
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

        if(detector_material=='SiC' and self.geant4_model != 'cflm'):
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
        if(detector_material=='Diamond'):
            detector={
                        "name" : "Device",
                        "material" : "G4_C",
                        "density" : 3.52,
                        "side_x" : my_d.l_x,
                        "side_y" : my_d.l_y,
                        "side_z" : my_d.l_z,
                        "colour" : [1,0,0],
                        "position_x" : 0,
                        "position_y" : 0,
                        "position_z" : my_d.l_z/2.0,
                        }
            self.create_elemental(detector)  

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