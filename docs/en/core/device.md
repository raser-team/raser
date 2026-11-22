# Device Model (`core/device`)

`src/raser/core/device/` reads detector definitions from device JSON files in [detector components](../components/device.md) (or from device dicts stored in node records `node.json`), locates files using the path rules in [engineering infrastructure](../supports/README.md), and obtains semiconductor relative permittivities from [materials and physical models](model.md). This package validates the readout electrode layout and avalanche multiplication switch, computes device bounds, electrode-array parameters, and parallel-plate junction capacitance, and builds a `Detector` object in memory. The resulting `Detector` instance is passed to [device field solving](field.md), [energy deposition](deposit.md), [carrier drift and induced current](current.md), and [electronics readout](readout.md) (and through these stages supports [single-device signal benchmark](../bench/signal.md) and [beam telescope benchmark](../bench/telescope.md)).

## Physics

### Parallel-Plate Junction Capacitance

In a fully depleted planar, strip, or pixel semiconductor detector (or one with a specified depletion depth), the depleted region between a single readout electrode and the back electrode can be approximated as a parallel-plate capacitor whose junction capacitance is proportional to the area of a single readout electrode and inversely proportional to the depletion depth. In code, the single readout electrode area $A$ and parallel-plate junction capacitance $C$ are computed as:

$$A = \begin{cases} p_x p_y, & \text{strip or pixel} \\ l_x l_y, & \text{pad} \end{cases} \tag{1}$$

$$C = \frac{\varepsilon_0 \varepsilon_r \left(A \times 10^{-12}\right)}{d \times 10^{-6}} \times 10^{12} \tag{2}$$

where:

- $A$: area of a single readout electrode, $\mu\text{m}^2$;
- $p_x, p_y$: readout electrode pitch along $x$ and $y$, $\mu\text{m}$ (under `"strip"` layout, $p_y = l_y$);
- $l_x, l_y$: full device dimensions along $x$ and $y$, $\mu\text{m}$ (under `"pad"` layout, also assigned to $p_x, p_y$);
- $C$: junction capacitance of a single readout electrode, $\text{pF}$ (the fraction on the right first yields `capacitance_f` in $\text{F}$, then multiplies by $10^{12}\ \text{pF/F}$);
- $\varepsilon_0$: vacuum permittivity, defined in code as constant `EPSILON_0_F_PER_M` = $8.8541878128\times 10^{-12}\ \text{F/m}$;
- $\varepsilon_r$: dimensionless relative permittivity of the semiconductor material, where $10^{-12}$ is the $\text{m}^2/\mu\text{m}^2$ area conversion factor;
- $d$: depletion depth `depletion_depth`, $\mu\text{m}$ ($10^{-6}$ is the $\text{m}/\mu\text{m}$ length conversion factor).

Area Eq. (1) and capacitance Eq. (2) correspond respectively to `Detector._readout_area_um2` and the cached property `Detector.capacitance`. When the device JSON explicitly provides `capacitance_pF`, `Detector.capacitance` returns that value directly; when `det_model` (lowercased) contains `"3d"`, it returns `None`, and the junction capacitance of a 3D device is supplied either by `capacitance_pF` in the device file or by the field solve; otherwise it computes Eq. (2) with `depletion_depth` defaulting to device thickness `l_z` ($\mu\text{m}$). The relative permittivity $\varepsilon_r$ is supplied by `Material(material).permittivity` in [model.md](model.md) (looking up `RELATIVE_PERMITTIVITY` by material name: `11.9` for `"Si"`, `9.76` for `"SiC"`, `5.7` for `"Diamond"`); only these three materials are in the table, so devices of other materials (such as `"GaN"`) specify `capacitance_pF` in the device file. Parallel-plate depletion-layer capacitance and relative permittivity of semiconductors are from Ref. [1], and the value of vacuum permittivity `EPSILON_0_F_PER_M` is from Ref. [2].

## Algorithms

### Built-in Constants

The table below lists all module-level constants, layout constraint tables, and hardcoded unit conversion factors in `build_device.py`. `EPSILON_0_F_PER_M`, `LAYOUT_KEYS`, and the unit conversion factors have no corresponding keys in device or component files; derived electrode counts and default pitches under each layout are determined by `electrodes`, `read_ele_num`, `x_ele_num`, `y_ele_num`, `p_x`, `p_y`, `l_x`, and `l_y` in the device file:

| Constant or Built-in Setting | `"pad"` Profile / Common Value | `"strip"` Profile | `"pixel"` Profile | Unit | Location and Meaning |
| --- | --- | --- | --- | --- | --- |
| `EPSILON_0_F_PER_M` | `8.8541878128e-12` | `8.8541878128e-12` | `8.8541878128e-12` | $\text{F/m}$ | Module constant, vacuum permittivity $\varepsilon_0$ used in parallel-plate capacitance calculation (no key in device file) |
| `LAYOUT_KEYS` | `()` | `('read_ele_num', 'p_x')` | `('x_ele_num', 'y_ele_num', 'p_x', 'p_y')` | None | Module constant, tuple of exclusive keys that must appear—and only those may appear—in the device JSON for each `electrodes` layout (no key in device file) |
| Derived `x_ele_num`, `y_ele_num`, `read_ele_num` | `1, 1, 1` | `read_ele_num, 1, read_ele_num` | `x_ele_num, y_ele_num, x_ele_num * y_ele_num` | count | Hardcoded electrode-count derivation by layout in `Detector.__init__` |
| Derived `p_x`, `p_y` | `l_x, l_y` | `p_x, l_y` | `p_x, p_y` | $\mu\text{m}$ | Hardcoded electrode-pitch derivation by layout in `Detector.__init__` |
| Area, thickness, capacitance conversion factors | `1e-12`, `1e-6`, `1e12` | `1e-12`, `1e-6`, `1e12` | `1e-12`, `1e-6`, `1e12` | $\text{m}^2/\mu\text{m}^2$, $\text{m}/\mu\text{m}$, $\text{pF/F}$ | Hardcoded unit conversion factors in `Detector.capacitance` (no key in device file) |

### Device File Lookup and Reading

`device_file(device_name)` and `device_json(device_name)` locate and read a device JSON file in the following order:

1. **Expand user directory**: compute `candidate = Path(device_name).expanduser()`.
2. **Existing directory branch**: if `candidate.is_dir()` is true, return `candidate / "device.json"` inside that directory.
3. **Explicit path branch**: if `candidate.suffix` is non-empty (has a file extension) or `len(candidate.parts) > 1` (contains multiple path segments), return `candidate` directly.
4. **Workspace project branch**: call `work_root()` from [../supports/README.md](../supports/README.md) and form `project = work_root() / str(device_name) / "device.json"`; if `project.is_file()` is true, return `project`.
5. **Component directory lookup branch**: call `component_file_path("device", str(device_name))` to search in order for `<device_name>.json` under the project component directory `<project_root>/components/device/` (where `<project_root>` is environment variable `RASER_PROJECT_PATH`, defaulting to the current directory; see [engineering infrastructure](../supports/README.md)), each directory listed in `RASER_COMPONENT_PATH`, and the built-in `src/raser/components/device/`. If none of the candidate directories contains the file, `component_file_path` raises `FileNotFoundError` (message `Cannot find RASER component device/<device_name>.json:` followed by the search path list).
6. **Load JSON dict**: `device_json(device_name)` opens the path returned by `device_file(device_name)` and parses it with `json.load`. If a path returned by step 2 or step 3 does not exist on disk, opening raises `FileNotFoundError`; if it points to a directory rather than a file, opening raises `IsADirectoryError`.

### `Detector` Construction, Derived Attributes, and Layout Validation

`Detector(device_name, device_dict=None)` initializes instance attributes in the following strict order:

1. **Resolve path and copy dictionary**: call `path = device_file(device_name)` (raising `FileNotFoundError` here if lookup by name fails). If `device_dict is None`, read the dict from disk with `device_json(device_name)`. Assign `copy.deepcopy(device_dict)` to `self.device_dict` to isolate the detector's dict from the caller's dict, and assign `path.resolve()` to `self.definition_path`.
2. **Map top-level keys to attributes**: execute `self.__dict__.update(self.device_dict)` to write every top-level JSON key-value pair directly into the instance attribute dict.
3. **Extract nested bias and irradiation keys**:
   - Compute `self.voltage = float(self.device_dict['bias']['voltage'])` ($\text{V}$). Raises `KeyError` if `'bias'` or `'voltage'` is missing, or `TypeError`/`ValueError` if the value cannot be converted to `float`.
   - Check `"irradiation" in self.device_dict`: if true, set `self.irradiation_model = self.device_dict['irradiation']['irradiation_model']` and `self.irradiation_flux = self.device_dict['irradiation']['irradiation_flux']` ($\text{cm}^{-2}$; raises `KeyError` if `'irradiation_model'` or `'irradiation_flux'` is missing from `'irradiation'`); if false, set `self.irradiation_model = None` and `self.irradiation_flux = 0`.
4. **Compute name, solve dimension, and 3D bounds**:
   - Set `self.det_name = self.device_dict.get('det_name', path.stem)`, and also set `self.device = self.det_name` and `self.region = self.det_name`.
   - Set `self.dimension = self.device_dict.get('field_dimension', self.device_dict['default_dimension'])`. `default_dimension` is required and raises `KeyError` if absent.
   - Build bounds dict `self.bound = {'x': (0, self.l_x), 'y': (0, self.l_y), 'z': (0, self.l_z)}` ($\mu\text{m}$). If any of `l_x`, `l_y`, `l_z` is missing from the JSON top level, accessing the attribute raises `AttributeError`.
5. **Validate readout electrode layout and exclusive keys**:
   - Read `self.electrodes = self.device_dict.get('electrodes', 'pad')`. If `self.electrodes not in ('pad', 'strip', 'pixel')`, raise `ValueError` (`` `electrodes` must be pad, strip or pixel, not <electrodes> ``).
   - Take `own = LAYOUT_KEYS[self.electrodes]` and build the list of missing required keys `missing = [key for key in own if key not in self.device_dict]` and the list of mixed-in keys belonging to other layouts `foreign = [key for key in ('read_ele_num', 'x_ele_num', 'y_ele_num', 'p_x', 'p_y') if key in self.device_dict and key not in own]`.
   - If either `missing` or `foreign` is non-empty, raise `ValueError` (``<path>: `electrodes` is <electrodes>, which takes the keys <list(own)>; missing <missing>, keys of another layout <foreign>``).
6. **Derive readout electrode counts**:
   - If `self.is_strip` (`self.electrodes == 'strip'`) is true, set `self.x_ele_num = self.read_ele_num` and `self.y_ele_num = 1`.
   - Else if `self.is_pixel` (`self.electrodes == 'pixel'`) is true, set `self.read_ele_num = self.x_ele_num * self.y_ele_num`.
   - Else (`self.electrodes == 'pad'`), set `self.x_ele_num = 1`, `self.y_ele_num = 1`, and `self.read_ele_num = 1`.
7. **Validate and compute the avalanche multiplication switch**:
   - Read `self.avalanche_model = self.device_dict.get('avalanche_model')` (default `None`) and `enable_gain = bool(self.device_dict.get('enable_gain', False))`.
   - If `enable_gain` is true and `self.avalanche_model is None`, raise `ValueError` (``gain is enabled but `avalanche_model` is missing in detector settings``).
   - Set `self.has_avalanche = self.avalanche_model is not None and enable_gain`.
8. **Derive single-electrode pitch**:
   - If `self.electrodes == 'pad'`, set `self.p_x = self.device_dict['l_x']` and `self.p_y = self.device_dict['l_y']` ($\mu\text{m}$).
   - If `self.is_strip` is true, set `self.p_x = self.device_dict['p_x']` and `self.p_y = self.device_dict['l_y']` ($\mu\text{m}$).
   - If `self.is_pixel` is true, set `self.p_x = self.device_dict['p_x']` and `self.p_y = self.device_dict['p_y']` ($\mu\text{m}$).

### Capacitance Calculation and Helper Queries

A `Detector` instance provides the following on-demand properties and methods at runtime:

1. **Junction capacitance (`Detector.capacitance`, `@cached_property`)**: evaluated in the following order on first access and cached in the instance dict:
   - If `"capacitance_pF" in self.device_dict`, return `float(self.device_dict["capacitance_pF"])` ($\text{pF}$).
   - If `"3d" in self.det_model.lower()`, return `None` (if `det_model` is omitted in JSON, accessing `self.det_model` raises `AttributeError`).
   - Compute `depletion_depth = float(self.device_dict.get("depletion_depth", self.l_z))` ($\mu\text{m}$); if `depletion_depth <= 0`, raise `ValueError` (`depletion_depth must be positive`).
   - Call `Material(self.material)` to obtain `material.permittivity` (`material` must be `"Si"`, `"SiC"`, or `"Diamond"`; omitting `material` or using another material such as `"GaN"` raises `AttributeError`), call `self._readout_area_um2()` to compute `area_um2` ($\mu\text{m}^2$) via Eq. (1), and return the junction capacitance ($\text{pF}$) via Eq. (2).
2. **Auxiliary file resolution (`Detector.file(name)`)**:
   - Compute `path = Path(name).expanduser()`; if `not path.is_absolute()`, join it relative to the directory containing the device JSON: `path = Path(self.definition_path).parent / path`.
   - Call `path = path.resolve()`. If `not path.is_file()`, raise `FileNotFoundError` (`Cannot find <path>, named by <definition_path>`); otherwise return the resolved `Path` object.

## Software Implementation

### Module and Function Responsibilities

- `__init__.py`: package docstring file.
- `build_device.py`: implements device JSON path resolution `device_file`, JSON loader `device_json`, and the detector data structure `Detector` (including construction validation, electrode-layout properties `is_strip` and `is_pixel`, single-electrode area calculation `_readout_area_um2`, cached junction capacitance property `capacitance`, and external file resolution method `file`).

### Core Data Structures

`Detector` (`build_device.py`) is the in-memory object read directly by users and downstream stages. Beyond exposing all top-level keys of `device_dict` as attributes of the same name, `Detector` always provides the following derived fields and methods:

| Field or Method | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `device_dict` | `dict` | None | Deep copy of the device JSON dict |
| `definition_path` | `Path` | None | Absolute path of the device JSON returned by `device_file(device_name)` after `resolve()` |
| `det_name`, `device`, `region` | `str` | None | Detector name (all three equal; defaults to `stem` of the path returned by `device_file(device_name)`, i.e. filename stem before `resolve()`) |
| `dimension` | `int` | None | Device field solving dimension (`field_dimension` if present, otherwise `default_dimension`) |
| `voltage` | `float` | $\text{V}$ | Bias voltage `float(device_dict["bias"]["voltage"])` |
| `irradiation_model` | `str \| None` | None | Irradiation defect model name (`None` if no `irradiation` block) |
| `irradiation_flux` | `float \| int` | $\text{cm}^{-2}$ | Irradiation fluence (`0` if no `irradiation` block) |
| `bound` | `dict[str, tuple]` | $\mu\text{m}$ | 3D coordinate bounds `{'x': (0, l_x), 'y': (0, l_y), 'z': (0, l_z)}` |
| `electrodes` | `str` | None | Readout electrode layout (`"pad"`, `"strip"`, or `"pixel"`) |
| `is_strip`, `is_pixel` | `bool` | None | Whether `electrodes` is `"strip"` or `"pixel"` |
| `x_ele_num`, `y_ele_num`, `read_ele_num` | `int` | count | Readout electrode counts along $x$, $y$, and total |
| `p_x`, `p_y` | `float \| int` | $\mu\text{m}$ | Pitch or dimension of a single readout electrode along $x$ and $y$ |
| `avalanche_model` | `str \| None` | None | Impact ionization multiplication model name |
| `has_avalanche` | `bool` | None | Whether both `avalanche_model is not None` and `bool(enable_gain)` hold |
| `capacitance` | `float \| None` | $\text{pF}$ | Single-electrode junction capacitance (explicit value, parallel-plate estimate, or `None` for 3D models) |
| `file(name)` | `Path` | None | Resolves the absolute path of an auxiliary file referenced by the device JSON and verifies it exists |

## Interface

Users can configure the device JSON keys listed in the tables below; vacuum permittivity `EPSILON_0_F_PER_M`, layout key constraints `LAYOUT_KEYS`, and unit conversion factors are hardcoded. `core/device` has no standalone command-line stage entry point and is invoked at the start of each simulation stage; see [../stages/field.md](../stages/field.md), [../stages/deposit.md](../stages/deposit.md), [../stages/current.md](../stages/current.md), and [../stages/readout.md](../stages/readout.md) for command-line usage.

### Keys Read from the Device File

#### Geometry, Material, and Electrodes

| Key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `det_name` | JSON filename stem (`path.stem`) | None | Detector name, assigned to `det_name`, `device`, and `region` on construction |
| `det_model` | None (required when accessing `capacitance` without `capacitance_pF`; required downstream) | None | Detector model identifier, one of `"planar"`, `"lgad"`, `"ilgad_planar"`, `"strip"`, `"lgadstrip"`, `"pixel"`, `"lgad_pixel"`, `"lgadpixel"`, `"3D_pixel"`, `"3D_column_series"`; when lowercased string contains `"3d"`, parallel-plate capacitance returns `None` |
| `material` | None (required for parallel-plate `capacitance` branch and downstream) | None | Semiconductor material: `"Si"`, `"SiC"`, `"Diamond"`, or `"GaN"`; the parallel-plate branch passes it to `Material(material)` in [model.md](model.md), where relative permittivity is defined only for `"Si"`, `"SiC"`, and `"Diamond"`, so `"GaN"` devices must provide `capacitance_pF` |
| `l_x`, `l_y`, `l_z` | None (required) | $\mu\text{m}$ | Full detector dimensions along $x$, $y$, and $z$ ($z$ is thickness), used to construct `bound`, default electrode sizes, and default depletion depth |
| `electrodes` | `"pad"` | None | Readout electrode layout: `"pad"`, `"strip"`, or `"pixel"` |
| `read_ele_num` | `1` for `"pad"`; `x_ele_num * y_ele_num` for `"pixel"` | count | Total number of readout electrodes; required for `"strip"` layout (forbidden in JSON for `"pad"` and `"pixel"` layouts) |
| `x_ele_num`, `y_ele_num` | `1, 1` for `"pad"`; `read_ele_num, 1` for `"strip"` | count | Number of readout electrodes along $x$ and $y$; required for `"pixel"` layout (forbidden in JSON for `"pad"` and `"strip"` layouts) |
| `p_x` | `l_x` for `"pad"` | $\mu\text{m}$ | Readout electrode pitch along $x$; required for `"strip"` or `"pixel"` layout (forbidden in JSON for `"pad"` layout) |
| `p_y` | `l_y` for `"pad"`, `"strip"` | $\mu\text{m}$ | Readout electrode pitch along $y$; required for `"pixel"` layout (forbidden in JSON for `"pad"` and `"strip"` layouts) |
| `read_out_contact` | None (required downstream) | None | List of readout contact electrodes, each with `"name"` and optional neighbor span `"x_span"`, `"y_span"` (mapped verbatim as an attribute) |
| `comment` | None (optional) | None | Descriptive text for the device (mapped verbatim as an attribute) |

#### Bias, Doping, Irradiation, and Multiplication

| Key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `bias` | None (required, with required subkey `"voltage"`) | `"voltage"` in $\text{V}$ | Bias object containing biased electrode name `"electrode"` and bias voltage `"voltage"`; `float(bias["voltage"])` is extracted as attribute `voltage` on construction |
| `temperature` | None (required downstream) | $\text{K}$ | Detector operating temperature (mapped verbatim as an attribute) |
| `doping` | None (required for field solving or diffusion-only collection) | $\text{cm}^{-3}$ | Doping object containing `"Acceptors"` and `"Donors"` expressions along depth (in $\text{cm}$) and optional irradiation doping terms `"Acceptors_ir"`, `"Donors_ir"` (mapped verbatim as an attribute) |
| `irradiation` | When absent, `irradiation_model = None`, `irradiation_flux = 0` | `"irradiation_flux"` in $\text{cm}^{-2}$ (`neq/cm^2`) | Irradiation object; when present, must contain both `"irradiation_model"` (`"XingChen"`, `"Perugia"`, `"Schwandt"`, `"CommonDefect"`) and `"irradiation_flux"`, extracted as `irradiation_model` and `irradiation_flux` |
| `avalanche_model` | `None` | None | Impact ionization multiplication model name: `"vanOverstraeten"`, `"Okuto"`, or `"Hatakeyama"` |
| `enable_gain` | `False` | None | Whether carrier multiplication is enabled; when truthy, `avalanche_model` must also be given, and both together determine `has_avalanche` |

#### Device Circuit

| Key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `capacitance_pF` | None (optional) | $\text{pF}$ | Junction capacitance of a single readout electrode; when given, `Detector.capacitance` returns `float(capacitance_pF)` directly; otherwise readout uses the capacitance solved by the field at the operating bias, or falls back to the parallel-plate estimate of `Detector.capacitance` if the field provides none |
| `depletion_depth` | `l_z` | $\mu\text{m}$ | Depletion depth used by `Detector.capacitance` when estimating junction capacitance via the parallel-plate formula (must be $> 0$) |
| `bias_resistance_ohm` | None (downstream default `None`) | $\Omega$ | Bias resistance of a single readout electrode (mapped verbatim as an attribute when given, read by [field.md](field.md)) |
| `coupling_capacitance_pF` | None (downstream default `None`) | $\text{pF}$ | AC coupling capacitance of a single readout electrode; requires `bias_resistance_ohm` when given (mapped verbatim as an attribute) |
| `undepleted_resistance_ohm`, `undepleted_capacitance_pF` | None (downstream default `None`) | $\Omega$, $\text{pF}$ | Equivalent resistance and capacitance of the undepleted bulk; normally computed by [field.md](field.md) from the field at runtime bias, overridden when specified in the device file; both keys must be given together or both omitted |
| `resistive_layer` | None (optional) | None | Resistive layer definition object containing `"sheet_resistance"` ($\Omega$) or implant parameters, cell spans (`"strips"` or `"pads"`), and optional `"grounded"` and `"coupling"` (mapped verbatim as an attribute) |

#### Physical Models and Solving Dimension

The device file has no `mesh` section: geometry (layer thicknesses, materials, and which face each electrode lies on) is an intrinsic property of the device, whereas meshes belong to `field`, and which mesh to use is specified by the `field` section settings (see [field.md](field.md)). Physical models are registered by name and selected by name in the device file; each material has a default model (see [model.md](model.md)).

| Key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `default_dimension` | None (required) | None | Default field solving dimension: `1`, `2`, or `3` |
| `field_dimension` | `default_dimension` | None | Field solving dimension overriding `default_dimension`, assigned to `Detector.dimension` on construction |
| `area_factor` | None (downstream `field` defaults to `1.0`) | 1D $\text{cm}^2$, 2D $\text{cm}$, 3D dimensionless | Area or length factor converting 1D or 2D IV, CV, and specific impedance to whole-device totals (mapped verbatim as an attribute when given) |

### Library Components

`src/raser/components/device/` contains the following 23 detector component files:

| Component Name | Description |
| --- | --- |
| `3D-LGAD` | Si `lgad_pixel` device |
| `3d_column_series` | Si `3D_column_series` device |
| `3d_pixel` | Si `3D_pixel` device |
| `AlGaN_GaN_HEMT_TRANSPORT_V1` | GaN `planar` device |
| `CMOS_strip` | Si `strip` device |
| `CMOS_strip_tcad` | Si `strip` device |
| `DJLGAD_Ayyoub_1D_with_coefficient` | Si `lgad` device, 1D Ayyoub DJ-LGAD coefficient version (gain-layer Gaussian exponent includes `1/2`, peak `3.0e16 cm^-3`, standard deviation `0.17 um`) |
| `DJLGAD_Ayyoub_Table1_1D` | Si `lgad` device, 1D Ayyoub Table 1 literature reproduction DJ-LGAD approximate model |
| `general_pixel` | Si `pixel` device |
| `general_strip` | Si `strip` device |
| `HPK-Si-LGAD` | Si `lgad` device |
| `HPK-Si-PiN` | Si `planar` device |
| `iLGAD` | Si `ilgad_planar` device |
| `ITk-md8` | Si `planar` device |
| `ITk-Si-strip` | Si `strip` device |
| `NJU-PiN` | SiC `planar` device |
| `NJU-PiN-bmos` | SiC `planar` device |
| `pixel_ayyouby` | Si `lgadpixel` device, 3×3 array of Ayyoub-style DJ-LGAD pixels (pitch `20 × 20 um`) |
| `SICAR-1` | SiC `lgad` device |
| `SICAR-1-PiN` | SiC `planar` device |
| `SiC_LGAD_strip` | SiC `lgadstrip` device |
| `strip_ayyouby` | Si `lgadstrip` device, 3-channel Ayyoub-style DJ-LGAD strip detector (pitch `20 um`) |
| `TAICHU3` | Si `pixel` device |

### Input/Output Files and Plot Outputs

- **Input files**: UTF-8 encoded device JSON file (`<work_root>/<device_name>/device.json`, `components/device/<device_name>.json`, or an explicit path) and auxiliary files resolved through `Detector.file(name)`.
- **Output files and datasets**: None. `core/device` only constructs `Detector` instances in memory and writes no disk data files, attributes, or datasets.
- **Plot outputs**: None.

## References

- [1] S. M. Sze, K. K. Ng, *Physics of Semiconductor Devices*, 3rd ed., Wiley-Interscience (2007), doi:10.1002/0470068329
- [2] E. Tiesinga, P. J. Mohr, D. B. Newell, B. N. Taylor, “CODATA recommended values of the fundamental physical constants: 2018”, Rev. Mod. Phys. 93 (2021) 025010, doi:10.1103/RevModPhys.93.025010
