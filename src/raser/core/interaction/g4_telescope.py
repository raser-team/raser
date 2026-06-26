#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""
Description:
    geat4_pybind simulation
@Date       : 2021/09/02 12:46:27
@Author     : Yuhang Tan
@version    : 1.0

@Date       : 2023/04/18
@Author     : xingchenli
@version    : 2.0
"""

import sys
import random
import math
import json
import os

import numpy as np
import g4ppyy as g4b

g4b.include("G4VUserDetectorConstruction.hh")
g4b.include("G4UserLimits.hh")

from .interaction import GeneralG4Interaction
from .action_initialization import GeneralActionInitialization
from .detector_construction import GeneralDetectorConstruction
from .primary_generator_action import GeneralPrimaryGeneratorAction
from .event_action import GeneralEventAction
from .stepping_action import GeneralSteppingAction
from .run_action import GeneralRunAction
from raser.supports.paths import component_path

verbose = 0
flag = 0


# Geant4 main process
class TelescopeG4Interaction(GeneralG4Interaction):
    def __init__(
        self, my_d, g4experiment, g4_seed=random.randint(0, 1e7), g4_vis=False
    ):
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
        geant4_json = component_path("g4experiment", g4experiment + ".json")
        with open(geant4_json) as f:
            g4_dic = json.load(f)
        # my_g4d = PixelDetectorConstruction(g4_dic,g4_dic['maxstep'])

        devicenames, localpositions = [], []
        self.devicenames = devicenames
        self.localpositions = localpositions
        self.ltz = g4_dic["ltz"]
        self.seedcharge = g4_dic["seedcharge"]

        class WrappedTelescopeActionInitialization(TelescopeActionInitialization):
            # make sure the class has the same parameters as the original class
            def __init__(
                self,
                par_in,
                par_out,
                par_randx,
                par_randy,
                par_type,
                par_energy,
                eventIDs,
                edep_devices,
                p_steps,
                energy_steps,
                events_angles,
                geant4_model,
            ):
                super().__init__(
                    par_in,
                    par_out,
                    par_randx,
                    par_randy,
                    par_type,
                    par_energy,
                    eventIDs,
                    edep_devices,
                    p_steps,
                    energy_steps,
                    events_angles,
                    devicenames,
                    localpositions,
                    geant4_model,
                )

        super().__init__(
            my_d,
            g4experiment,
            g4_seed,
            g4_vis,
            PixelDetectorConstruction,
            WrappedTelescopeActionInitialization,
        )
        print("end g4")

        # record localpos in logicvolume
        for i in range(0, len(self.devicenames)):
            # print("eventID:",i)
            # print("totalhits:",len(self.localpositions[i]))
            pass

    def __del__(self):
        pass


# Geant4 for telescope
class PixelDetectorConstruction(g4b.G4VUserDetectorConstruction):
    "Pixel Detector Construction"

    def __init__(self, my_d, g4_dic, detector_material, maxStep=0.5):
        g4b.G4VUserDetectorConstruction.__init__(self)
        self.g4_dic = g4_dic
        self.solid = {}
        self.logical = {}
        self.physical = {}
        self.checkOverlaps = True
        self.maxStep = maxStep * g4b.um
        self.fStepLimit = g4b.G4UserLimits(self.maxStep)
        self.create_world(g4_dic["world"])

        if g4_dic["object"]:
            for object_type in g4_dic[
                "object"
            ]:  # build all pixel first before build layer
                if object_type == "pixel":
                    for every_object in g4_dic["object"][object_type]:
                        self.create_pixel(g4_dic["object"][object_type][every_object])
            print("end pixel constrution")
            for object_type in g4_dic["object"]:
                if object_type == "layer":
                    for every_object in g4_dic["object"][object_type]:
                        self.create_layer(g4_dic["object"][object_type][every_object])

    def create_world(self, world_type):

        self.nist = g4b.G4NistManager.Instance()
        material = self.nist.FindOrBuildMaterial(world_type)
        self.solid["world"] = g4b.G4Box(
            "world", 25000 * g4b.um, 25000 * g4b.um, 50 * g4b.cm
        )
        self.logical["world"] = g4b.G4LogicalVolume(
            self.solid["world"], material, "world"
        )
        self.physical["world"] = g4b.G4PVPlacement(
            None,
            g4b.G4ThreeVector(0, 0, 0),
            self.logical["world"],
            "world",
            None,
            False,
            0,
            self.checkOverlaps,
        )
        visual = g4b.G4VisAttributes()
        # visual.SetVisibility(False)
        self.logical["world"].SetVisAttributes(visual)

    def create_pixel(self, object):  # build pixel
        # pixel logicvolume
        name = object["name"]
        material_type = self.nist.FindOrBuildMaterial(object["material"], False)
        print(type(material_type))
        visual = g4b.G4VisAttributes(
            g4b.G4Color(object["colour"][0], object["colour"][1], object["colour"][2])
        )
        sidex = object["side_x"] * g4b.um
        sidey = object["side_y"] * g4b.um
        sidez = object["side_z"] * g4b.um
        self.solid[name] = g4b.G4Box(name, sidex / 2.0, sidey / 2.0, sidez / 2.0)

        self.logical[name] = g4b.G4LogicalVolume(self.solid[name], material_type, name)
        # different part define
        for every_object in object:
            if every_object.startswith("part"):
                part = object[every_object]
                p_name = part["name"]
                p_element_1 = self.nist.FindOrBuildElement(part["element_1"], False)
                p_element_2 = self.nist.FindOrBuildElement(part["element_2"], False)
                p_natoms_1 = part["natoms_1"]
                p_natoms_2 = part["natoms_2"]
                p_density = part["density"] * g4b.g / g4b.cm3
                p_mixture = g4b.G4Material(part["mixture_name"], p_density, 2)
                p_mixture.AddElement(p_element_1, p_natoms_1 * g4b.perCent)
                p_mixture.AddElement(p_element_2, p_natoms_2 * g4b.perCent)
                p_translation = g4b.G4ThreeVector(
                    part["position_x"] * g4b.um,
                    part["position_y"] * g4b.um,
                    part["position_z"] * g4b.um,
                )
                p_visual = g4b.G4VisAttributes(
                    g4b.G4Color(part["colour"][0], part["colour"][1], part["colour"][2])
                )

                p_sidex = part["side_x"] * g4b.um
                p_sidey = part["side_y"] * g4b.um
                p_sidez = part["side_z"] * g4b.um
                p_mother = self.logical[name]
                self.solid[p_name] = g4b.G4Box(
                    p_name, p_sidex / 2.0, p_sidey / 2.0, p_sidez / 2.0
                )
                self.logical[p_name] = g4b.G4LogicalVolume(
                    self.solid[p_name], p_mixture, p_name
                )

                g4b.G4PVPlacement(
                    None,
                    p_translation,
                    self.logical[p_name],
                    p_name,
                    p_mother,
                    False,
                    0,
                    self.checkOverlaps,
                )
                p_visual.SetVisibility(False)
                self.logical[p_name].SetVisAttributes(p_visual)

        visual.SetVisibility(True)
        self.logical[name].SetVisAttributes(visual)
        self.logical[name].SetUserLimits(self.fStepLimit)

    def create_layer(self, object):  # build layer
        name = object["name"]  # temp use,muti layer need change Stepaction
        material_type = self.nist.FindOrBuildMaterial("G4_Galactic", False)
        pixel_type = object["pixel_type"]
        row = object["row"]
        column = object["column"]
        mother = self.physical["world"]
        translation = g4b.G4ThreeVector(
            object["position_x"] * g4b.um,
            object["position_y"] * g4b.um,
            object["position_z"] * g4b.um,
        )
        rotation = g4b.G4RotationMatrix()
        rotation.rotateX(object["rotation_xyz"][0] * g4b.degree)
        rotation.rotateY(object["rotation_xyz"][1] * g4b.degree)
        rotation.rotateZ(object["rotation_xyz"][2] * g4b.degree)
        visual = g4b.G4VisAttributes(
            g4b.G4Color(object["colour"][0], object["colour"][1], object["colour"][2])
        )
        motherBox = g4b.G4Box("MotherBox", 1.0 * g4b.cm, 1.0 * g4b.cm, 250 * g4b.um)

        self.logical[name] = g4b.G4LogicalVolume(motherBox, material_type, name)
        for i in range(0, int(row)):
            for j in range(0, int(column)):
                pixel = self.g4_dic["object"]["pixel"][pixel_type]
                t_translation = g4b.G4ThreeVector(
                    (pixel["side_x"] * (j + 1 / 2 - column / 2)) * g4b.um,
                    (pixel["side_y"] * (i + 1 / 2 - row / 2)) * g4b.um,
                    0.0 * g4b.um,
                )
                t_pixelname = pixel_type + "_" + str(i) + "_" + str(j) + "_" + name
                g4b.G4PVPlacement(
                    None,
                    t_translation,
                    self.logical[pixel_type],
                    t_pixelname,
                    self.logical[name],
                    False,
                    i * int(column) + j,
                    self.checkOverlaps,
                )

        self.physical[name] = g4b.G4PVPlacement(
            rotation, translation, name, self.logical[name], mother, False, 0, True
        )
        visual.SetVisibility(False)
        self.logical[name].SetVisAttributes(visual)
        self.logical[name].SetUserLimits(self.fStepLimit)

    def Construct(self):  # return the world volume
        self.fStepLimit.SetMaxAllowedStep(self.maxStep)
        return self.physical["world"]


class TelescopeEventAction(GeneralEventAction):
    "My Event Action"

    def __init__(
        self,
        runAction,
        point_in,
        point_out,
        eventIDs,
        edep_devices,
        p_steps,
        energy_steps,
        events_angles,
        devicenames,
        localpositions,
    ):
        super().__init__(
            runAction,
            point_in,
            point_out,
            eventIDs,
            edep_devices,
            p_steps,
            energy_steps,
            events_angles,
        )
        # use in pixel_detector
        self.devicenames = devicenames
        self.localpositions = localpositions

    def BeginOfEventAction(self, event):
        super().BeginOfEventAction(event)
        self.volume_name = []
        self.localposition = []

    def EndOfEventAction(self, event):
        super().EndOfEventAction(event)
        self.save_telescope_events(self.volume_name, self.localposition)

    def RecordPixel(self, step):
        edep = step.GetTotalEnergyDeposit()
        point_pre = step.GetPreStepPoint()
        point_post = step.GetPostStepPoint()
        point_in = point_pre.GetPosition()
        point_out = point_post.GetPosition()
        if edep <= 0.0:
            return
        touchable = point_pre.GetTouchable()
        volume = touchable.GetVolume()

        transform = touchable.GetHistory().GetTopTransform()
        localpos = transform.TransformPoint(point_in)

        self.edep_device += edep
        self.p_step.append(
            [point_in.getX() * 1000, point_in.getY() * 1000, point_in.getZ() * 1000]
        )
        self.energy_step.append(edep)
        # save only in RecordPixel
        self.volume_name.append(volume.GetName())
        self.localposition.append(
            [
                localpos.getX() / g4b.um,
                localpos.getY() / g4b.um,
                localpos.getZ() / g4b.um,
            ]
        )

        # print("edep:", edep)
        # print("Volume Name:", volume.GetName())
        # print("Global Position in Worlds Volume:",point_in/g4b.um)
        # print("Local Position in Pixel:", localpos/g4b.um)

    def save_telescope_events(self, volume_name, localposition):
        self.devicenames.append(volume_name)
        self.localpositions.append(localposition)
        # print("volume_name len:",len(volume_name))
        # print("localposition len: ",len(localposition))


class TelescopeSteppingAction(GeneralSteppingAction):
    "My Stepping Action"

    def __init__(self, eventAction):
        super().__init__(eventAction)

    def UserSteppingAction(self, step):
        super().UserSteppingAction(step)
        if self.volume_name.startswith("Taichu"):
            self.fEventAction.RecordPixel(step)


class TelescopeActionInitialization(g4b.G4VUserActionInitialization):
    def __init__(
        self,
        par_in,
        par_out,
        par_randx,
        par_randy,
        par_type,
        par_energy,
        eventIDs,
        edep_devices,
        p_steps,
        energy_steps,
        events_angles,
        devicenames,
        localpositions,
        geant4_model,
    ):
        g4b.G4VUserActionInitialization.__init__(self)
        self.par_in = par_in
        self.par_out = par_out
        self.par_type = par_type
        self.par_energy = par_energy
        self.geant4_model = geant4_model
        self.par_randx = par_randx
        self.par_randy = par_randy

        self.eventIDs = eventIDs
        self.edep_devices = edep_devices
        self.p_steps = p_steps
        self.energy_steps = energy_steps
        self.events_angles = events_angles
        self.devicenames = devicenames
        self.localpositions = localpositions

    def Build(self):
        self.SetUserAction(
            GeneralPrimaryGeneratorAction(
                self.par_in,
                self.par_out,
                self.par_randx,
                self.par_randy,
                self.par_type,
                self.par_energy,
                self.geant4_model,
            )
        )
        # global myRA_action
        myRA_action = GeneralRunAction()
        self.SetUserAction(myRA_action)
        myEA = TelescopeEventAction(
            myRA_action,
            self.par_in,
            self.par_out,
            self.eventIDs,
            self.edep_devices,
            self.p_steps,
            self.energy_steps,
            self.events_angles,
            self.devicenames,
            self.localpositions,
        )
        self.SetUserAction(myEA)
        self.SetUserAction(TelescopeSteppingAction(myEA))
