"""
Description: Import external GDML geometry for RASER.
Version 1.4: adds an assembly-visualization mode on top of the stable world-as-world
implementation. It can separately style the imported PCB geometry and the RASER
Device volume so both can be inspected together in Geant4.
"""

import os
import xml.etree.ElementTree as ET

import g4ppyy as g4b

from .detector_construction import GeneralDetectorConstruction
from raser.supports.paths import component_candidates

WRAPPER_WORLD_NAME = 'RASER_GDML_WRAPPER_WORLD'
WRAPPER_BOX_NAME = 'RASER_GDML_WRAPPER_BOX'
WRAPPER_IMPORTED_PV_NAME = 'RASER_GDML_IMPORTED_ASSEMBLY_PV'


def _as_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {'1', 'true', 'yes', 'y', 'on'}:
        return True
    if text in {'0', 'false', 'no', 'n', 'off'}:
        return False
    return default


def _resolve_gdml_path(path_text: str) -> str:
    if not path_text:
        raise ValueError('g4experiment json is missing gdml.file')
    if os.path.isabs(path_text) and os.path.exists(path_text):
        return path_text
    candidates = []
    candidates.extend(str(path) for path in component_candidates(path_text))
    candidates.extend(str(path) for path in component_candidates('g4experiment', path_text))
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    candidates.append(os.path.join(repo_root, path_text))

    for candidate in candidates:
        if os.path.exists(candidate):
            return os.path.abspath(candidate)

    searched = '\n  - '.join(candidates)
    raise FileNotFoundError(
        f"Cannot find GDML file: {path_text}\nSearched:\n  - {searched}")

def _gdml_structure_has_volume_name(gdml_path: str, name: str) -> bool:
    if not name:
        return False
    try:
        # 分块读取，每次 1MB，彻底防止单行巨型文件撑爆内存
        with open(gdml_path, 'r', encoding='utf-8') as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                if f'name="{name}"' in chunk or f"name='{name}'" in chunk:
                    return True
    except Exception:
        return False
    return False


def _gdml_setup_world_ref(gdml_path: str) -> str:
    try:
        with open(gdml_path, 'r', encoding='utf-8') as f:
            # 查找 setup world 的引用通常在文件尾部，但以防万一还是分块读
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                if '<world' in chunk and 'ref=' in chunk:
                    # 粗略提取 ref 名字
                    parts = chunk.split('ref="')
                    if len(parts) > 1:
                        return parts[1].split('"')[0]
    except Exception:
        return ''
    return ''


def _gdml_has_wrapper_world(gdml_path: str) -> bool:
    try:
        with open(gdml_path, 'r', encoding='utf-8') as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                if WRAPPER_WORLD_NAME in chunk:
                    return True
    except Exception:
        return False
    return False

def _estimate_geometry_center_um(gdml_path: str):
    try:
        tree = ET.parse(gdml_path)
        root = tree.getroot()
    except Exception:
        return [0.0, 0.0, 0.0]

    coords = {'x': [], 'y': [], 'z': []}
    for position in root.findall('.//position'):
        unit = (position.get('unit') or 'mm').strip().lower()
        if unit == 'mm':
            scale = 1000.0
        elif unit == 'cm':
            scale = 10000.0
        elif unit == 'um':
            scale = 1.0
        elif unit == 'nm':
            scale = 1e-3
        else:
            scale = 1000.0
        for axis in ('x', 'y', 'z'):
            value = position.get(axis)
            if value is None:
                continue
            try:
                coords[axis].append(float(value) * scale)
            except ValueError:
                pass

    center = []
    for axis in ('x', 'y', 'z'):
        if coords[axis]:
            center.append((min(coords[axis]) + max(coords[axis])) / 2.0)
        else:
            center.append(0.0)
    return center


class GDMLDetectorConstruction(GeneralDetectorConstruction):
    """
    Stable external-GDML detector construction for RASER, with two modes:

    1) Production-stable mode (default)
       - For wrapper-patched GDML, use the imported GDML world directly as the
         Geant4 world. This removes the sibling-overlap warning that happens when
         a wrapper G4Box is placed next to Device:0.

    2) Assembly-visualization mode
       - Still uses the stable world-as-world behaviour, but additionally:
         * recursively forces imported GDML geometry to be visible
         * separately styles or hides the RASER Device volume
       - This is intended for joint Device+PCB geometry inspection in OpenGL,
         not for final physics production.
    """

    def __init__(self, my_d, g4_dic, detector_material, maxStep=0.5):
        g4b.G4VUserDetectorConstruction.__init__(self)
        self.solid = {}
        self.logical = {}
        self.physical = {}
        self.checkOverlaps = False
        self.g4_dic = g4_dic
        self.gdml_cfg = g4_dic.get('gdml', {})
        self.visual_cfg = g4_dic.get('visualization', {})
        self.imported_parser = None
        self.nist = g4b.G4NistManager.Instance()
        self.geant4_model = g4_dic['geant4_model']

        self.gdml_path = _resolve_gdml_path(self.gdml_cfg.get('file', ''))
        self._world_from_gdml = False

        if _gdml_has_wrapper_world(self.gdml_path):
            self._use_imported_world_as_world()
        else:
            self.create_world(g4_dic['world'])
            if 'world_half_size_um' in g4_dic:
                half_size = float(g4_dic['world_half_size_um']) * g4b.um
                self.solid['world'].SetXHalfLength(half_size)
                self.solid['world'].SetYHalfLength(half_size)
                self.solid['world'].SetZHalfLength(half_size)
            self._import_gdml_geometry_as_placement()

        self._build_raser_detector_and_objects(my_d, g4_dic, detector_material)
        self._configure_visualization()

        self.maxStep = maxStep * g4b.um
        self.fStepLimit = g4b.G4UserLimits(self.maxStep)
        if 'Device' in self.logical:
            self.logical['Device'].SetUserLimits(self.fStepLimit)

    def _build_raser_detector_and_objects(self, my_d, g4_dic, detector_material):
        if detector_material == 'Si':
            detector = {
                'name': 'Device',
                'material': 'G4_Si',
                'side_x': my_d.l_x,
                'side_y': my_d.l_y,
                'side_z': my_d.l_z,
                'colour': [1, 0, 0],
                'position_x': 0,
                'position_y': 0,
                'position_z': my_d.l_z / 2.0,
            }
            self.create_elemental(detector)

        if detector_material == 'SiC' and self.geant4_model != 'cflm':
            detector = {
                'name': 'Device',
                'material_1': 'Si',
                'material_2': 'C',
                'compound_name': 'SiC',
                'density': 3.2,
                'natoms_1': 50,
                'natoms_2': 50,
                'side_x': my_d.l_x,
                'side_y': my_d.l_y,
                'side_z': my_d.l_z,
                'colour': [1, 0, 0],
                'position_x': 0,
                'position_y': 0,
                'position_z': my_d.l_z / 2.0,
                'tub': {},
            }
            self.create_binary_compounds(detector)

        if g4_dic['object']:
            for object_type in g4_dic['object']:
                if object_type == 'elemental':
                    for every_object in g4_dic['object'][object_type]:
                        self.create_elemental(g4_dic['object'][object_type][every_object])
                if object_type == 'binary_compounds':
                    for every_object in g4_dic['object'][object_type]:
                        self.create_binary_compounds(g4_dic['object'][object_type][every_object])

    def _make_vis_attr(self, rgba, wireframe=False, solid=False):
        if rgba is None or len(rgba) != 4:
            rgba = [0.20, 0.85, 0.25, 1.00]
        colour = g4b.G4Colour(float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3]))
        attr = g4b.G4VisAttributes(colour)
        attr.SetVisibility(True)
        if wireframe:
            attr.SetForceWireframe(True)
        if solid:
            attr.SetForceSolid(True)
        return attr

    def _apply_vis_recursive(self, logical_volume, vis_attr, visited=None, include_root=True):
        if logical_volume is None:
            return
        if visited is None:
            visited = set()
        key = ( int(logical_volume.__hash__()) if hasattr(logical_volume, '__hash__') else id(logical_volume))
        if key in visited:
            return
        visited.add(key)

        if include_root:
            try:
                logical_volume.SetVisAttributes(vis_attr)
            except Exception:
                pass

        try:
            n = logical_volume.GetNoDaughters()
        except Exception:
            n = 0
        for i in range(int(n)):
            try:
                daughter = logical_volume.GetDaughter(i)
                child_logical = daughter.GetLogicalVolume()
            except Exception:
                continue
            try:
                child_logical.SetVisAttributes(vis_attr)
            except Exception:
                pass
            self._apply_vis_recursive(child_logical, vis_attr, visited, include_root=False)

    def _configure_visualization(self):
        if not self.visual_cfg:
            return

        imported_visible = _as_bool(self.visual_cfg.get('imported_visible', True), True)
        imported_wireframe = _as_bool(self.visual_cfg.get('imported_force_wireframe', True), True)
        imported_solid = _as_bool(self.visual_cfg.get('imported_force_solid', not imported_wireframe), not imported_wireframe,)
        imported_rgba = self.visual_cfg.get('imported_colour_rgba', [0.20, 0.85, 0.85, 1.00])

        device_visible = _as_bool(self.visual_cfg.get('device_visible', True), True)
        hide_device = _as_bool(self.visual_cfg.get('hide_device', False), False)
        device_wireframe = _as_bool(self.visual_cfg.get('device_force_wireframe', False), False)
        device_solid = _as_bool(self.visual_cfg.get('device_force_solid', not device_wireframe), not device_wireframe,)
        device_rgba = self.visual_cfg.get('device_colour_rgba', [1.00, 0.10, 0.10, 0.35])

        if imported_visible:
            imported_attr = self._make_vis_attr(imported_rgba, wireframe=imported_wireframe, solid=imported_solid)
            if 'world' in self.logical and self.logical['world'] is not None:
                # Keep the wrapper world itself invisible, but force all imported daughters visible.
                try:
                    self.logical['world'].SetVisAttributes(g4b.G4VisAttributes.GetInvisible())
                except Exception:
                    pass
                self._apply_vis_recursive(self.logical['world'], imported_attr, include_root=False)
                print('[RASER][GDML][VIS] Forced imported GDML geometry to be visible for assembly inspection.')

        if 'Device' in self.logical:
            if hide_device or not device_visible:
                try:
                    self.logical['Device'].SetVisAttributes(g4b.G4VisAttributes.GetInvisible())
                    print('[RASER][GDML][VIS] Device volume hidden.')
                except Exception:
                    pass
            else:
                try:
                    device_attr = self._make_vis_attr(device_rgba, wireframe=device_wireframe, solid=device_solid)
                    self.logical['Device'].SetVisAttributes(device_attr)
                    print('[RASER][GDML][VIS] Device volume styled for joint Device+PCB inspection.')
                except Exception:
                    pass

    def _use_imported_world_as_world(self):
        validate = _as_bool(self.gdml_cfg.get('validate', False), False)
        parser = g4b.G4GDMLParser()
        parser.SetOverlapCheck(False)
        parser.Read(self.gdml_path, validate)
        self.imported_parser = parser

        imported_world = parser.GetWorldVolume()
        if imported_world is None:
            raise RuntimeError('GDML wrapper world mode selected, but parser.GetWorldVolume() returned None.')

        self.physical['world'] = imported_world
        self.logical['world'] = imported_world.GetLogicalVolume()

        try:
            self.solid['world'] = self.logical['world'].GetSolid()
        except Exception:
            self.solid['world'] = None
        self.logical['world'].SetVisAttributes(g4b.G4VisAttributes.GetInvisible())
        self._world_from_gdml = True
        print('[RASER][GDML] Using imported GDML wrapper world as the main Geant4 world. '
              'This avoids placing PCB_Readout as a sibling G4Box around Device:0.')

    def _build_rotation(self):
        rotation_xyz = self.gdml_cfg.get('rotation_xyz', [0.0, 0.0, 0.0])
        if len(rotation_xyz) != 3:
            rotation_xyz = [0.0, 0.0, 0.0]
        if all(abs(float(v)) < 1e-12 for v in rotation_xyz):
            return None
        rotation = g4b.G4RotationMatrix()
        rotation.rotateX(float(rotation_xyz[0]) * g4b.degree)
        rotation.rotateY(float(rotation_xyz[1]) * g4b.degree)
        rotation.rotateZ(float(rotation_xyz[2]) * g4b.degree)
        return rotation

    def _import_gdml_geometry_as_placement(self):
        validate = _as_bool(self.gdml_cfg.get('validate', False), False)
        parser = g4b.G4GDMLParser()
        parser.SetOverlapCheck(False)
        parser.Read(self.gdml_path, validate)
        self.imported_parser = parser

        top_volume_name = self.gdml_cfg.get('top_volume')
        imported_world = None
        imported_logical = None

        if top_volume_name and _gdml_structure_has_volume_name(self.gdml_path, top_volume_name):
            imported_logical = parser.GetVolume(top_volume_name)

        if imported_logical is None:
            imported_world = parser.GetWorldVolume()
            if imported_world is None:
                raise RuntimeError('GDML file was read, but parser.GetWorldVolume() returned None.')
            imported_logical = imported_world.GetLogicalVolume()

        position_um = list(self.gdml_cfg.get('position_um', [0.0, 0.0, 0.0]))
        if len(position_um) != 3:
            position_um = [0.0, 0.0, 0.0]
        position_um = [float(v) for v in position_um]

        if _as_bool(self.gdml_cfg.get('auto_center', True), True):
            center_um = _estimate_geometry_center_um(self.gdml_path)
            position_um[0] -= center_um[0]
            position_um[1] -= center_um[1]
            position_um[2] -= center_um[2]

        translation = g4b.G4ThreeVector(position_um[0] * g4b.um,
                                        position_um[1] * g4b.um,
                                        position_um[2] * g4b.um)
        rotation = self._build_rotation()
        placement_name = self.gdml_cfg.get('placement_name', 'ImportedGDML')

        self.logical[placement_name] = imported_logical
        self.physical[placement_name] = g4b.G4PVPlacement(
            rotation,
            translation,
            placement_name,
            imported_logical,
            self.physical['world'],
            False,
            0,
            self.checkOverlaps,
        )

    def Construct(self):
        if hasattr(self, 'fStepLimit'):
            self.fStepLimit.SetMaxAllowedStep(self.maxStep)
        return self.physical['world']
