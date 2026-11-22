"""
Description:  detector_construction.py
@Date       : 2025
@Author     : Yuhang Tan, Chenxi Fu (Original: Geant4)
@version    : 2.0
"""

from raser.core.deposit.geant4.g4ppyy_runtime import g4b

from ..along_beam import objects_of
from ..simulate_deposits import world_half_side

g4b.include("G4VUserDetectorConstruction.hh")
g4b.include("G4UserLimits.hh")


class GeneralDetectorConstruction(g4b.G4VUserDetectorConstruction):
    "My Detector Construction"

    def __init__(self, devices, layout, g4_dic, maxStep=0.5):
        """The world, the objects and one logical volume for each slot, laid
        out as `layout` says (raser.core.deposit.along_beam): the slot is
        named as its logical volume and holds the active layer of its device,
        whose step is limited to maxStep [um]."""
        super().__init__()
        self.solid = {}
        self.logical = {}
        self.physical = {}
        self.compound_materials = {}
        self.diamond_built = False
        # a placement keeps a pointer to its rotation
        self.rotations = []
        # Geant4 keeps only a pointer to each G4VisAttributes; they live as
        # long as the geometry does.
        self.visuals = []
        self.checkOverlaps = True
        self.create_world(g4_dic["world"], world_half_side(layout, g4_dic))
        self.geant4_model = g4_dic["geant4_model"]
        self.maxStep = maxStep * g4b.um
        self.fStepLimit = g4b.G4UserLimits(self.maxStep)

        for slot in layout.slots:
            self.create_slot(slot, devices[slot.name])
            self.logical[slot.name].SetUserLimits(self.fStepLimit)

        table = objects_of(g4_dic)
        for placed in layout.objects:
            body = {
                **table[placed.name],
                "position_x": placed.offset[0],
                "position_y": placed.offset[1],
                "position_z": placed.z + placed.thickness / 2.0,
            }
            if "compound_name" in body:
                self.create_binary_compounds(body)
            else:
                self.create_elemental(body)

    def create_slot(self, slot, my_d):
        """The active layer of the device of `slot`: a box l_x x l_y x l_z
        of the material of the device, its front face z = 0 at the front
        point of the slot, turned as the slot is (equation (18))."""
        material = my_d.material
        # the centre of the layer in the world: half a thickness behind the
        # front face along the +z of the device, which faces downstream or
        # upstream
        sign = 1 if slot.facing == "upstream" else -1
        centre = (slot.front[0], slot.front[1], slot.front[2] + sign * slot.l_z / 2.0)
        body = {
            "name": slot.name,
            "side_x": slot.l_x,
            "side_y": slot.l_y,
            "side_z": slot.l_z,
            "colour": list(slot.colour),
            "position_x": centre[0],
            "position_y": centre[1],
            "position_z": centre[2],
        }
        # the active rotation of the device is Rz(rotation_z) * Ry(180 deg
        # if downstream); a placement takes the rotation of the frame, its inverse
        rotation = g4b.G4RotationMatrix()
        if slot.facing == "downstream":
            rotation.rotateY(180 * g4b.deg)
        rotation.rotateZ(slot.rotation_z * g4b.deg)
        rotation.invert()
        self.rotations.append(rotation)
        if material == "Si":
            self.create_elemental({**body, "material": "G4_Si"}, rotation)
        elif material == "Diamond":
            # Diamond is carbon at 3.52 g/cm3; NIST's G4_C is graphite (2.0 g/cm3).
            if not self.diamond_built:
                self.nist.BuildMaterialWithNewDensity("Diamond", "G4_C", 3.52 * g4b.g / g4b.cm3)
                self.diamond_built = True
            self.create_elemental({**body, "material": "Diamond"}, rotation)
        elif material == "SiC":
            self.create_binary_compounds(
                {
                    **body,
                    "material_1": "Si",
                    "material_2": "C",
                    "compound_name": "SiC",
                    "density": 3.2,
                    "natoms_1": 50,
                    "natoms_2": 50,
                    "tub": {},
                },
                rotation,
            )
        else:
            raise ValueError(
                f"no Geant4 material for the device of slot {slot.name!r}: "
                f"its material is {material!r}; known: ['Diamond', 'Si', 'SiC']"
            )

    def create_world(self, world_type, half_side):
        """The world: a cube of world_type, half_side [um] from the centre."""

        self.nist = g4b.G4NistManager.Instance()
        material = self.nist.FindOrBuildMaterial(world_type)
        self.solid["world"] = g4b.G4Box(
            "world", half_side * g4b.um, half_side * g4b.um, half_side * g4b.um
        )
        self.logical["world"] = g4b.G4LogicalVolume(
            self.solid["world"], material, "world"
        )
        self.physical["world"] = g4b.G4PVPlacement(
            g4b.cppyy.nullptr,
            g4b.G4ThreeVector(0, 0, 0),
            self.logical["world"],
            "world",
            g4b.cppyy.nullptr,
            False,
            0,
            self.checkOverlaps,
        )

        self.logical["world"].SetVisAttributes(g4b.G4VisAttributes.GetInvisible())

    def create_elemental(self, object, rotation=None):
        name = object["name"]
        material_type = self.nist.FindOrBuildMaterial(object["material"], False)
        translation = g4b.G4ThreeVector(
            object["position_x"] * g4b.um,
            object["position_y"] * g4b.um,
            object["position_z"] * g4b.um,
        )
        visual = g4b.G4VisAttributes(
            g4b.G4Color(object["colour"][0], object["colour"][1], object["colour"][2])
        )
        mother = self.physical["world"]
        sidex = object["side_x"] * g4b.um
        sidey = object["side_y"] * g4b.um
        sidez = object["side_z"] * g4b.um
        self.solid[name] = g4b.G4Box(name, sidex / 2.0, sidey / 2.0, sidez / 2.0)
        if object.get("tub"):
            # a hole along z through the middle: tub_radius, and tub_depth half its length [um]
            self.solid[name + "box"] = self.solid[name]
            self.solid[name + "tub"] = g4b.G4Tubs(
                name + "tub",
                0,
                object["tub"]["tub_radius"] * g4b.um,
                object["tub"]["tub_depth"] * g4b.um,
                0,
                360 * g4b.deg,
            )
            self.solid[name] = g4b.G4SubtractionSolid(
                name, self.solid[name + "box"], self.solid[name + "tub"]
            )

        self.logical[name] = g4b.G4LogicalVolume(self.solid[name], material_type, name)
        self.physical[name] = g4b.G4PVPlacement(
            g4b.cppyy.nullptr if rotation is None else rotation,
            translation,
            name,
            self.logical[name],
            mother,
            False,
            0,
            self.checkOverlaps,
        )
        self.visuals.append(visual)
        self.logical[name].SetVisAttributes(visual)

    def create_binary_compounds(self, object, rotation=None):
        name = object["name"]
        material_1 = self.nist.FindOrBuildElement(object["material_1"], False)
        material_2 = self.nist.FindOrBuildElement(object["material_2"], False)
        material_density = object["density"] * g4b.g / g4b.cm3
        compound_name = object["compound_name"]
        compound_signature = (
            object["material_1"],
            object["material_2"],
            object["density"],
            object["natoms_1"],
            object["natoms_2"],
        )
        if compound_name in self.compound_materials:
            compound, existing_signature = self.compound_materials[compound_name]
            if compound_signature != existing_signature:
                raise ValueError(
                    f"Conflicting Geant4 material definition for {compound_name}"
                )
        else:
            # natoms_1 and natoms_2 are shares of the atoms; Geant4 takes a
            # fraction given as a number as a share of the mass.
            mass_1 = object["natoms_1"] * material_1.GetA()
            mass_2 = object["natoms_2"] * material_2.GetA()
            compound = g4b.G4Material(compound_name, material_density, 2)
            compound.AddElement(material_1, mass_1 / (mass_1 + mass_2))
            compound.AddElement(material_2, mass_2 / (mass_1 + mass_2))
            self.compound_materials[compound_name] = (compound, compound_signature)
        translation = g4b.G4ThreeVector(
            object["position_x"] * g4b.um,
            object["position_y"] * g4b.um,
            object["position_z"] * g4b.um,
        )
        visual = g4b.G4VisAttributes(
            g4b.G4Color(object["colour"][0], object["colour"][1], object["colour"][2])
        )
        mother = self.physical["world"]
        sidex = object["side_x"] * g4b.um
        sidey = object["side_y"] * g4b.um
        sidez = object["side_z"] * g4b.um
        if not (object["tub"]):
            self.solid[name] = g4b.G4Box(name, sidex / 2.0, sidey / 2.0, sidez / 2.0)
        else:
            self.solid[name + "box"] = g4b.G4Box(
                name + "box", sidex / 2.0, sidey / 2.0, sidez / 2.0
            )
            self.solid[name + "tub"] = g4b.G4Tubs(
                name + "tub",
                0,
                object["tub"]["tub_radius"] * g4b.um,
                object["tub"]["tub_depth"] * g4b.um,
                0,
                360 * g4b.deg,
            )
            self.solid[name] = g4b.G4SubtractionSolid(
                name, self.solid[name + "box"], self.solid[name + "tub"]
            )

        self.logical[name] = g4b.G4LogicalVolume(self.solid[name], compound, name)
        self.physical[name] = g4b.G4PVPlacement(
            g4b.cppyy.nullptr if rotation is None else rotation,
            translation,
            name,
            self.logical[name],
            mother,
            False,
            0,
            self.checkOverlaps,
        )
        self.visuals.append(visual)
        self.logical[name].SetVisAttributes(visual)

    def Construct(self):  # return the world volume
        self.fStepLimit.SetMaxAllowedStep(self.maxStep)
        return self.physical["world"]
