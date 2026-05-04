#!/usr/bin/env python3 

'''
Description:  g4_diamond_energy_deposition.py
@Date       : 2025
@Author     : Peiyao Wang (Original: Geant4)
@version    : 2.0
'''

import sys
import os
import array
import random
import math

import geant4_pybind as g4b
import ROOT
ROOT.gROOT.SetBatch(True)
import numpy as np

from ..current.model import Material
from ..current.model import Vector

G4AnalysisManager = g4b.G4RootAnalysisManager
class Diamond_DetectorConstruction(g4b.G4VUserDetectorConstruction):#是g4b.G4VUserDetectorConstruction的子类
  
   
    def __init__(self):
        super().__init__()#调用父类的构造函数
        self.fCheckOverlaps = True#检查器件构造是否重叠
    def DefineMaterials(self):
        nistManager = g4b.G4NistManager.Instance()#访问核素和元素
        nistManager.FindOrBuildMaterial("G4_C")  # 添加金刚石材料
        air = nistManager.FindOrBuildMaterial("G4_AIR")
        print(g4b.G4Material.GetMaterialTable())
    def DefineVolumes(self):
        worldsize_x = 50*g4b.mm
        worldsize_y = 50*g4b.mm
        worldsize_z = 50*g4b.mm
        detectorSizeX = 4.5*g4b.mm
        detectorSizeY = 4.5*g4b.mm
        detectorSizeZ = 1.5*g4b.mm
        nistManager = g4b.G4NistManager.Instance()
        defaultMaterial = nistManager.FindOrBuildMaterial("G4_AIR")
        if defaultMaterial == None:
            msg = "Cannot retrieve materials already defined."
            g4b.G4Exception("Diamond_DetectorConstruction::DefineVolumes()",
                        "MyCode0001", g4b.FatalException, msg)
        #创造世界的第一天，定义世界大小^~^!!!
        worldS = g4b.G4Box("World", worldsize_x/2, worldsize_y/2, worldsize_z/2)
        #创造世界的第二天，给世界里充满空气@~@！！！
        worldLV = g4b.G4LogicalVolume(worldS, defaultMaterial, "World")
        #创造世界第三天，把世界放在哪里#……#,这个世界不旋转，放在000，这个世界是带有空气的逻辑世界，世界叫做world，没有比他还大的世界
        #没有在别的世界里创建这一个世界，没有布尔操作，不复制，检查有没有覆盖
        worldPV = g4b.G4PVPlacement(None, g4b.G4ThreeVector(0,0,0), worldLV, "World", None, False, 0, self.fCheckOverlaps)
        
        # 创建金刚石探测器材料
        self.nist = g4b.G4NistManager.Instance()
        diamondMaterial = self.nist.FindOrBuildMaterial("G4_C")
        
        # 创建探测器几何体
        detectorS = g4b.G4Box("Detector", detectorSizeX/2, detectorSizeY/2, detectorSizeZ/2)
        detectorLV = g4b.G4LogicalVolume(detectorS, diamondMaterial, "Detector")     
        self.fdetectorPV = g4b.G4PVPlacement(None, g4b.G4ThreeVector(0,0,0), detectorLV, "Detector", worldLV, False, 0, self.fCheckOverlaps)
        
        # 添加铝（Al）金属
        metal_Al_out = {
            "material": "Al",  # 金属的元素
            "density": 2.7,   # 金属的密度，单位为 g/cm3
        }
        metal_element_Al_out = self.nist.FindOrBuildElement(metal_Al_out['material'], False)
        metal_density_Al_out = metal_Al_out['density'] * g4b.g / g4b.cm3
        metal_material_Al_out = g4b.G4Material("Metal_Al", metal_density_Al_out, 1)
        metal_material_Al_out.AddElement(metal_element_Al_out, 1)
        
        Al_box = g4b.G4Box("Al_box", detectorSizeX/2, detectorSizeY/2, 500*g4b.nm)
        Al_logic = g4b.G4LogicalVolume(Al_box, metal_material_Al_out, "Al_out")
        self.fAl_PV = g4b.G4PVPlacement(None, g4b.G4ThreeVector(0, 0, 36*g4b.mm+500*g4b.nm), Al_logic, "metal_Al_out", worldLV, False, 0, self.fCheckOverlaps)

        # 添加镍（Ni）金属
        metal_Ni = {
            "material" : "Ni",  # 金属的元素
            "density" : 8.9,   # 金属的密度，单位为 g/cm3
        }
        metal_element_Ni = self.nist.FindOrBuildElement(metal_Ni['material'], False)
        metal_density_Ni = metal_Ni['density'] * g4b.g / g4b.cm3
        metal_material_Ni = g4b.G4Material("Metal_Ni", metal_density_Ni, 1)
        metal_material_Ni.AddElement(metal_element_Ni, 100 * g4b.perCent) 

        # 添加钛（Ti）金属
        metal_Ti = {
            "material" : "Ti",  # 金属的元素
            "density" : 4.5,   # 金属的密度，单位为 g/cm3
        }
        metal_element_Ti = self.nist.FindOrBuildElement(metal_Ti['material'], False)
        metal_density_Ti = metal_Ti['density'] * g4b.g / g4b.cm3
        metal_material_Ti = g4b.G4Material("Metal_Ti", metal_density_Ti, 1)
        metal_material_Ti.AddElement(metal_element_Ti, 100 * g4b.perCent) 
 

        # 添加铝（Al）金属
        metal_Al = {
            "material" : "Al",  # 金属的元素
            "density" : 2.7,   # 金属的密度，单位为 g/cm3
        }
        metal_element_Al = self.nist.FindOrBuildElement(metal_Al['material'], False)
        metal_density_Al = metal_Al['density'] * g4b.g / g4b.cm3
        metal_material_Al = g4b.G4Material("Metal_Al", metal_density_Al, 1)
        metal_material_Al.AddElement(metal_element_Al, 100 * g4b.perCent) 
   
        # 添加包含镍、钛和铝的组合材料
        composite_material = g4b.G4Material("Composite_Material", (metal_density_Ni + metal_density_Ti + metal_density_Al), 3)
        composite_material.AddMaterial(metal_material_Ni, 33.3 * g4b.perCent)
        composite_material.AddMaterial(metal_material_Ti, 20.8 * g4b.perCent)
        composite_material.AddMaterial(metal_material_Al, 45.9 * g4b.perCent)

        # 创建包含镍、钛和铝的逻辑体
        composite_tube = g4b.G4Tubs("Composite_Tube", 0, detectorSizeX/2, 240*g4b.nm, 0, 360*g4b.degree)
        composite_logical = g4b.G4LogicalVolume(composite_tube, composite_material, "Composite_Material")
        self.fcontactPV_composite = g4b.G4PVPlacement(None, g4b.G4ThreeVector(0, 0, 35*g4b.mm+400*g4b.nm), composite_logical, "Composite_Material", worldLV, False, 0, self.fCheckOverlaps)

        # 添加二氧化硅（SiO2）材料
        SiO2 = {
            "material" : "SiO2",  # 材料名称
            "density" : 2.2,   # 材料密度，单位为 g/cm3
        }
        material_element_Si = self.nist.FindOrBuildElement("Si", False)
        material_element_O = self.nist.FindOrBuildElement("O", False)
        material_density_SiO2 = SiO2['density'] * g4b.g / g4b.cm3
        material_material_SiO2 = g4b.G4Material("SiO2", material_density_SiO2, 2)
        material_material_SiO2.AddElement(material_element_Si, 33.33 * g4b.perCent)
        material_material_SiO2.AddElement(material_element_O, 66.66 * g4b.perCent)
        
        # 创建二氧化硅层的逻辑体
        SiO2_layer = g4b.G4Box("SiO2_Layer", detectorSizeX/2, detectorSizeY/2, 150*g4b.nm) # 假设二氧化硅层厚度为1微米
        SiO2_logical = g4b.G4LogicalVolume(SiO2_layer, material_material_SiO2, "SiO2_Layer")
        self.SiO2_PV = g4b.G4PVPlacement(None, g4b.G4ThreeVector(0, 0, 34*g4b.mm+160*g4b.nm), SiO2_logical, "SiO2_Layer", worldLV, False, 0, self.fCheckOverlaps)
        
        pcb1 = g4b.G4Box("pcb1", detectorSizeX, detectorSizeY, 1*g4b.mm)
        pcb1_logical = g4b.G4LogicalVolume(pcb1, material_material_SiO2, "pcb1")
        self.pcb1_PV = g4b.G4PVPlacement(None, g4b.G4ThreeVector(0, 0, 35*g4b.mm), pcb1_logical, "pcb1", worldLV, False, 0, self.fCheckOverlaps)
        
        #创造世界第五天，给这个世界加入色彩
        worldLV.SetVisAttributes(g4b.G4VisAttributes.GetInvisible())
        detectorVisAtt = g4b.G4VisAttributes(g4b.G4Colour(0.5, 0.8, 1.0))  # 修改颜色为淡蓝色表示金刚石
        WorldVisAtt = g4b.G4VisAttributes(g4b.G4Colour(1, 0, 1))
        MetalVisAtt_composite = g4b.G4VisAttributes(g4b.G4Colour(1, 0, 0))
        
        # 为二氧化硅层添加可视化属性
        SiO2VisAtt = g4b.G4VisAttributes(g4b.G4Colour(0, 1, 0))  # 使用绿色表示二氧化硅层
        SiO2_logical.SetVisAttributes(SiO2VisAtt)
        AlVisAtt = g4b.G4VisAttributes(g4b.G4Colour(0.5, 0.5, 0.5))  # 以灰色表示Al_out
        Al_logic.SetVisAttributes(AlVisAtt)
        PCB1VisAtt = g4b.G4VisAttributes(g4b.G4Colour(0, 0.4, 0.4))
        pcb1_logical.SetVisAttributes(PCB1VisAtt)
        composite_logical.SetVisAttributes(MetalVisAtt_composite)
        detectorLV.SetVisAttributes(detectorVisAtt)
        worldLV.SetVisAttributes(WorldVisAtt)
        return worldPV
        
    def Construct(self):
        self.DefineMaterials()
        return self.DefineVolumes()
        
    def ConstructSDandField(self):#创建敏感探测器和磁场
        fieldValue = g4b.G4ThreeVector()
        self.fMagFieldMessenger = g4b.G4GlobalMagFieldMessenger(fieldValue)
        self.fMagFieldMessenger.SetVerboseLevel(1)


class Diamond_PrimaryGeneratorAction(g4b.G4VUserPrimaryGeneratorAction):

    def __init__(self):
        super().__init__()
        particleTable = g4b.G4ParticleTable.GetParticleTable()
        ionTable = particleTable.GetIonTable()

        # 定义 alpha 粒子
        alpha = ionTable.GetIon(2, 4, 0.0)  # Z=2, A=4, Q=0.0

        if alpha is None:
            print("Alpha particle definition not found!")   
        nofParticles=1
        self.fParticleGun=g4b.G4ParticleGun(nofParticles)#初始化为1个粒子的粒子枪
        particleDefinition=g4b.G4ParticleTable.GetParticleTable().FindParticle("alpha")
        self.fParticleGun.SetParticleDefinition(particleDefinition)
        self.fParticleGun.SetParticleMomentumDirection(g4b.G4ThreeVector(0,0,-1))
        self.fParticleGun.SetParticleEnergy(500*g4b.MeV)
        
    def GeneratePrimaries(self, anEvent):
        self.fParticleGun.SetParticlePosition(g4b.G4ThreeVector(0, 0, 60*g4b.mm))
        self.fParticleGun.GeneratePrimaryVertex(anEvent)


class Diamond_aEventAction(g4b.G4UserEventAction):
    
    def BeginOfEventAction(self, event):
        self.fEnergyDetector = 0
        self.fTrackLDetector = 0
        
    def EndOfEventAction(self, event):
        analysisManager = g4b.G4AnalysisManager.Instance()#调用分析管理实例
        analysisManager.FillH1(0, self.fEnergyDetector)
        analysisManager.FillH1(1, self.fTrackLDetector)
        analysisManager.FillNtupleDColumn(0, self.fEnergyDetector)
        analysisManager.FillNtupleDColumn(1, self.fTrackLDetector)
        analysisManager.AddNtupleRow()
        eventID = event.GetEventID()
        printModulo = g4b.G4RunManager.GetRunManager().GetPrintProgress()
        if printModulo > 0 and eventID % printModulo == 0:
            print("---> End of event:", eventID)
            print("Detector: total energy:", g4b.G4BestUnit(self.fEnergyDetector, "Energy"), end="")
            print("total track length:", g4b.G4BestUnit(self.fTrackLDetector, "Length"))
            
    def AddDetector(self, de, dl):
        self.fEnergyDetector += de
        self.fTrackLDetector += dl


class Diamond_aSetppingAction(g4b.G4UserSteppingAction):
    def __init__(self, detectorConstruction, eventAction):
        super().__init__()
        self.fDetConstruction = detectorConstruction
        self.fEventAction = eventAction

    def UserSteppingAction(self, step):
        track = step.GetTrack()
        position = track.GetPosition()
        # 将位置信息写入文件
        with open('./output/Diamond/trajectory.txt', 'a') as file:
            file.write(f"{position.x} {position.y} {position.z}\n")
     
        volume = step.GetPreStepPoint().GetTouchable().GetVolume()#获取粒子所处的体积
        edep = step.GetTotalEnergyDeposit()#获取粒子能量沉积

        stepLength = 0
        if step.GetTrack().GetDefinition().GetPDGCharge() != 0:
            stepLength = step.GetStepLength()
        if volume == self.fDetConstruction.fdetectorPV:
            print("=========================================================\n============================")
            self.fEventAction.AddDetector(edep, stepLength)


class Diamond_RunAction(g4b.G4UserRunAction):
    def __init__(self):
        super().__init__()
        g4b.G4RunManager.GetRunManager().SetPrintProgress(1)#设置打印进度，每个时间后都打印模拟运行结果
        analysisManager = g4b.G4AnalysisManager.Instance()
        print("Using", analysisManager.GetType())
        analysisManager.SetVerboseLevel(1)
        analysisManager.SetNtupleMerging(True)#设置详细的信息输出
        analysisManager.CreateH1("Edetector", "Energy deposition in detector", 500, 0, 2*g4b.MeV)#最后的参数是最大值
        analysisManager.CreateNtupleDColumn("Edetector")
        analysisManager.CreateNtuple("Diamond", "Edep")
        analysisManager.CreateNtupleDColumn("Edetector")
        analysisManager.FinishNtuple()#创建了用于存储能量沉积数据的一维直方图和Ntuple，以便在模拟过程中对能量沉积的情况进行记录和分析

    def BeginOfRunAction(self, run):
        analysisManager = g4b.G4AnalysisManager.Instance()
        try:
            os.mkdir('output/Diamond')
        except:
            print('path already exist')

        fileName = "output/Diamond/energy_deposition.root"
        analysisManager.OpenFile(fileName)
        
    def EndOfRunAction(self, run):
        analysisManager = g4b.G4AnalysisManager.Instance()
        if analysisManager.GetH1(1) != None:
            print("\n ----> print histograms statistic ", end="")

            if self.IsMaster():
                print("for the entire run \n")
            else:
                print("for the local thread \n")

            print(" EDetector : mean =", g4b.G4BestUnit(analysisManager.GetH1(1).mean(), "Energy"), end="")
            print(" rms =", g4b.G4BestUnit(analysisManager.GetH1(1).rms(),  "Energy"))

        # save histograms & ntuple
        analysisManager.Write()


class Diamond_aActionInitialization(g4b.G4VUserActionInitialization):
    def __init__(self, detConstruction):
        super().__init__()
        self.fDetConstruction = detConstruction

    def BuildForMaster(self):
        self.SetUserAction(Diamond_RunAction())

    def Build(self):
        self.SetUserAction(Diamond_PrimaryGeneratorAction())
        self.SetUserAction(Diamond_RunAction())
        eventAction = Diamond_aEventAction()
        self.SetUserAction(eventAction)
        self.SetUserAction(Diamond_aSetppingAction(self.fDetConstruction, eventAction))


def main():
    runManager = g4b.G4RunManagerFactory.CreateRunManager(g4b.G4RunManagerType.Serial)

    detConstruction = Diamond_DetectorConstruction()
    runManager.SetUserInitialization(detConstruction)

    physicsList = g4b.FTFP_BERT()
    runManager.SetUserInitialization(physicsList)

    actionInitialization = Diamond_aActionInitialization(detConstruction)
    runManager.SetUserInitialization(actionInitialization)

    visManager = g4b.G4VisExecutive()
    visManager.Initialize()

    UImanager = g4b.G4UImanager.GetUIpointer()

    UImanager.ApplyCommand("/control/execute setting/g4macro/init_vis.mac")#初始化可视化配置

    UImanager.ApplyCommand('/run/initialize')#初始化运行，准备开始模拟
    UImanager.ApplyCommand("/gun/particle ion")
    UImanager.ApplyCommand("/gun/ion 2 4 0 ")
    UImanager.ApplyCommand("/gun/energy 5.4 MeV")
    UImanager.ApplyCommand('/tracking/verbose 2')#分总详细级别为2
    UImanager.ApplyCommand('/run/beamOn 500')#运行模拟，进行一次事例
    UImanager.ApplyCommand("/vis/geometry/set/visibility World 0 false")
    UImanager.ApplyCommand("/vis/geometry/set/forceSolid World")

    UImanager.ApplyCommand('/vis/ogl/set/printMode vectored')#设置可视化打印尺寸为矢量模式
    UImanager.ApplyCommand('/vis/ogl/set/printSize 2000 2000')#可视化打印尺寸为2000*2000
    UImanager.ApplyCommand("/vis/geometry/set/visibility World 1 true")
    UImanager.ApplyCommand('/vis/ogl/set/printFilename ./output/Diamond/image.pdf')#打印文件
    
    UImanager.ApplyCommand('/vis/ogl/export')#导出可视化


if __name__ == '__main__':
    main()