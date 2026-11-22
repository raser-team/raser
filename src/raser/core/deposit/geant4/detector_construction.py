"""
Description:  detector_construction.py
@Date       : 2025
@Author     : Yuhang Tan, Chenxi Fu (Original: Geant4)
@version    : 2.0
"""

from raser.core.deposit.geant4.g4ppyy_runtime import g4b

from ..along_beam import check_materials, check_objects, objects_of
from ..simulate_deposits import world_half_side

g4b.include("G4VUserDetectorConstruction.hh")
g4b.include("G4UserLimits.hh")

# Colour of an object that gives none.
OBJECT_COLOUR = (0.7, 0.7, 0.7)
# The material of a SiC device: shares of atoms, density [g/cm3].
SIC = {"density": 3.2, "elements": {"Si": 50, "C": 50}}


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
        # the G4Material of every material built here, by name
        self.materials = {}
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

        check_materials(g4_dic)
        check_objects(g4_dic)
        for name, material in (g4_dic.get("materials") or {}).items():
            self.create_material(name, material["density"], material["elements"])

        for slot in layout.slots:
            self.create_slot(slot, devices[slot.name])
            self.logical[slot.name].SetUserLimits(self.fStepLimit)

        table = objects_of(g4_dic)
        for placed in layout.objects:
            self.create_object(
                placed.name,
                table[placed.name],
                (placed.offset[0], placed.offset[1], placed.z + placed.thickness / 2.0),
            )

    def create_material(self, name, density, elements):
        """The material `name` of `density` [g/cm3] from `elements`, the
        shares of atoms by symbol; Geant4 takes the shares of the mass, which
        are n_i A_i / sum_j n_j A_j (equation (25))."""
        if name in list(self.nist.GetNistMaterialNames()):
            raise ValueError(f"material {name!r} conflicts with a NIST material name")
        found = {}
        for symbol in elements:
            element = self.nist.FindOrBuildElement(symbol, False)
            if not element:
                raise ValueError(f"unknown Geant4 element {symbol!r} in material {name!r}")
            found[symbol] = element
        masses = {symbol: share * found[symbol].GetA() for symbol, share in elements.items()}
        total = sum(masses.values())
        material = g4b.G4Material(name, density * g4b.g / g4b.cm3, len(elements))
        for symbol, element in found.items():
            material.AddElement(element, float(masses[symbol] / total))
        self.materials[name] = material
        return material

    def create_slot(self, slot, my_d):
        """The active layer of the device of `slot`: a box l_x x l_y x l_z
        of the material of the device, its front face z = 0 at the front
        point of the slot, turned as the slot is (equation (18))."""
        # the centre of the layer in the world: half a thickness behind the
        # front face along the +z of the device, which faces downstream or
        # upstream
        sign = 1 if slot.facing == "upstream" else -1
        centre = (slot.front[0], slot.front[1], slot.front[2] + sign * slot.l_z / 2.0)
        # the active rotation of the device is Rz(rotation_z) * Ry(180 deg
        # if downstream); a placement takes the rotation of the frame, its inverse
        rotation = g4b.G4RotationMatrix()
        if slot.facing == "downstream":
            rotation.rotateY(180 * g4b.deg)
        rotation.rotateZ(slot.rotation_z * g4b.deg)
        rotation.invert()
        self.rotations.append(rotation)
        self.create_box(
            slot.name,
            self.device_material(my_d.material, slot.name),
            (slot.l_x, slot.l_y, slot.l_z),
            centre,
            slot.colour,
            rotation,
        )

    def device_material(self, material, slot_name="Device"):
        """The Geant4 material of the active layer of a device whose
        material is "Si", "Diamond" or "SiC"."""
        if material == "Si":
            return self.nist.FindOrBuildMaterial("G4_Si", False)
        if material == "Diamond":
            # Diamond is carbon at 3.52 g/cm3; NIST's G4_C is graphite (2.0 g/cm3).
            if not self.diamond_built:
                self.nist.BuildMaterialWithNewDensity("Diamond", "G4_C", 3.52 * g4b.g / g4b.cm3)
                self.diamond_built = True
            return self.nist.FindOrBuildMaterial("Diamond", False)
        if material == "SiC":
            if "SiC" not in self.materials:
                self.create_material("SiC", SIC["density"], SIC["elements"])
            return self.materials["SiC"]
        raise ValueError(
            f"no Geant4 material for the device of slot {slot_name!r}: "
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

    def create_object(self, name, body, position):
        """The object `name` of the g4setup, described by `body` (shape,
        sizes [um], material, colour), its centre at `position` [um]."""
        if body["material"] in self.materials:
            material = self.materials[body["material"]]
        else:
            material = self.nist.FindOrBuildMaterial(body["material"], False)
        colour = body.get("colour", OBJECT_COLOUR)
        if body["shape"] == "box":
            size = body["size"]
            self.create_box(name, material, size, position, colour, hole=body.get("hole"))
        else:
            solid = g4b.G4Tubs(
                name,
                body.get("inner_radius", 0) * g4b.um,
                body["outer_radius"] * g4b.um,
                body["length"] / 2.0 * g4b.um,
                0,
                360 * g4b.deg,
            )
            self.place(name, solid, material, position, colour)

    def create_box(self, name, material, size, position, colour, rotation=None, hole=None):
        """A box of the full `size` [um] along x, y and z, of `material`, its
        centre at `position`. With a `hole` [um], a cylinder of that radius
        along z through the middle and the whole thickness is cut out."""
        half = [side / 2.0 * g4b.um for side in size]
        solid = g4b.G4Box(name, *half)
        if hole:
            # the cylinder is twice as long as the box, so that it goes through
            self.solid[name + "box"] = solid
            self.solid[name + "hole"] = g4b.G4Tubs(
                name + "hole", 0, hole * g4b.um, size[2] * g4b.um, 0, 360 * g4b.deg
            )
            solid = g4b.G4SubtractionSolid(
                name, self.solid[name + "box"], self.solid[name + "hole"]
            )
        self.place(name, solid, material, position, colour, rotation)

    def place(self, name, solid, material, position, colour, rotation=None):
        """The logical volume `name` of `solid` and `material` in the world,
        its centre at `position` [um], turned by `rotation` if given."""
        self.solid[name] = solid
        self.logical[name] = g4b.G4LogicalVolume(solid, material, name)
        self.physical[name] = g4b.G4PVPlacement(
            g4b.cppyy.nullptr if rotation is None else rotation,
            g4b.G4ThreeVector(*(c * g4b.um for c in position)),
            name,
            self.logical[name],
            self.physical["world"],
            False,
            0,
            self.checkOverlaps,
        )
        visual = g4b.G4VisAttributes(g4b.G4Color(colour[0], colour[1], colour[2]))
        self.visuals.append(visual)
        self.logical[name].SetVisAttributes(visual)

    def Construct(self):  # return the world volume
        self.fStepLimit.SetMaxAllowedStep(self.maxStep)
        return self.physical["world"]
