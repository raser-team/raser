# 器件模型（`core/device`）

`src/raser/core/device/` 从 [探测器组件](../components/device.md) 的器件 JSON 文件（或节点记录 `node.json` 里的器件字典）读取探测器定义，按 [工程支撑](../supports/README.md) 的路径规则定位文件，并从 [材料与物理模型](model.md) 获取半导体相对介电常数。该包校验读出电极布局与雪崩倍增开关，计算器件边界、电极阵列参数与平行板结电容，在内存中构造 `Detector` 对象。生成的 `Detector` 实例交给 [器件场求解](field.md)、[能量沉积](deposit.md)、[载流子漂移与感应电流](current.md) 与 [电子学读出](readout.md)（并经这些环节服务于 [单器件信号测试](../bench/signal.md) 与 [束流望远镜测试](../bench/telescope.md)）。

## 物理

### 平行板结电容

全耗尽或给定耗尽层厚度的平面、条形和像素半导体探测器中，单个读出电极与背电极之间的耗尽区可近似为平行板电容器，结电容与单个读出电极面积成正比、与耗尽层厚度成反比。代码中单个读出电极面积 $A$ 与平行板结电容 $C$ 的计算式为：

$$A = \begin{cases} p_x p_y, & \text{strip 或 pixel} \\ l_x l_y, & \text{pad} \end{cases} \tag{1}$$

$$C = \frac{\varepsilon_0 \varepsilon_r \left(A \times 10^{-12}\right)}{d \times 10^{-6}} \times 10^{12} \tag{2}$$

其中：

- $A$：单个读出电极面积，$\mu\text{m}^2$；
- $p_x, p_y$：$x$、$y$ 方向读出电极间距，$\mu\text{m}$（`"strip"` 布局下 $p_y = l_y$）；
- $l_x, l_y$：器件在 $x$、$y$ 方向的全尺寸，$\mu\text{m}$（`"pad"` 布局下同时赋给 $p_x, p_y$）；
- $C$：单个读出电极的结电容，$\text{pF}$（式中等号右侧分式先算出单位为 $\text{F}$ 的电容 `capacitance_f`，再乘以换算因子 $10^{12}\ \text{pF/F}$）；
- $\varepsilon_0$：真空介电常数，代码中常数 `EPSILON_0_F_PER_M` 取 $8.8541878128\times 10^{-12}\ \text{F/m}$；
- $\varepsilon_r$：半导体材料相对介电常数（无量纲），$10^{-12}$ 为 $\text{m}^2/\mu\text{m}^2$ 面积换算因子；
- $d$：耗尽层厚度 `depletion_depth`，$\mu\text{m}$（$10^{-6}$ 为 $\text{m}/\mu\text{m}$ 长度换算因子）。

面积式 (1) 与电容式 (2) 分别对应 `Detector._readout_area_um2` 与缓存属性 `Detector.capacitance`。当器件 JSON 显式给出 `capacitance_pF` 时，`Detector.capacitance` 直接返回该值；当 `det_model`（转小写后）包含 `"3d"` 时返回 `None`，3D 器件的结电容由器件文件的 `capacitance_pF` 或场求得的电容给出；其余情况按式 (2) 计算，其中耗尽层厚度 `depletion_depth` 缺省取器件厚度 `l_z`（$\mu\text{m}$）。相对介电常数 $\varepsilon_r$ 由 [model.md](model.md) 的 `Material(material).permittivity` 提供（按材料名查 `RELATIVE_PERMITTIVITY`：`"Si"` 取 `11.9`，`"SiC"` 取 `9.76`，`"Diamond"` 取 `5.7`）；表中只有这三种材料，其他材料（如 `"GaN"`）的器件在器件文件里给出 `capacitance_pF`。半导体耗尽层平行板结电容与相对介电常数见文献 [1]，真空介电常数 `EPSILON_0_F_PER_M` 取值见文献 [2]。

## 算法

### 内置常数

下表列出 `build_device.py` 中的全部模块级常数、布局约束表与写死在公式中的换算系数。`EPSILON_0_F_PER_M`、`LAYOUT_KEYS` 及单位换算系数在器件或组件文件里没有对应的键；各电极布局下的派生电极数与缺省尺寸由器件文件的 `electrodes`、`read_ele_num`、`x_ele_num`、`y_ele_num`、`p_x`、`p_y`、`l_x`、`l_y` 决定：

| 常数或内置设置 | `"pad"` 档位 / 通用值 | `"strip"` 档位 | `"pixel"` 档位 | 单位 | 定义位置与含义 |
| --- | --- | --- | --- | --- | --- |
| `EPSILON_0_F_PER_M` | `8.8541878128e-12` | `8.8541878128e-12` | `8.8541878128e-12` | $\text{F/m}$ | 模块常量，平行板电容计算使用的真空介电常数 $\varepsilon_0$（器件文件无对应键） |
| `LAYOUT_KEYS` | `()` | `('read_ele_num', 'p_x')` | `('x_ele_num', 'y_ele_num', 'p_x', 'p_y')` | 无 | 模块常量，各 `electrodes` 布局在器件 JSON 中必须出现且仅能出现的专属键元组（器件文件无对应键） |
| `x_ele_num`, `y_ele_num`, `read_ele_num` 派生值 | `1, 1, 1` | `read_ele_num, 1, read_ele_num` | `x_ele_num, y_ele_num, x_ele_num * y_ele_num` | 个 | `Detector.__init__` 按布局写死的电极数派生关系 |
| `p_x`, `p_y` 派生值 | `l_x, l_y` | `p_x, l_y` | `p_x, p_y` | $\mu\text{m}$ | `Detector.__init__` 按布局写死的电极间距派生关系 |
| 面积、厚度、电容换算因子 | `1e-12`, `1e-6`, `1e12` | `1e-12`, `1e-6`, `1e12` | `1e-12`, `1e-6`, `1e12` | $\text{m}^2/\mu\text{m}^2$, $\text{m}/\mu\text{m}$, $\text{pF/F}$ | `Detector.capacitance` 中写死的单位换算系数（器件文件无对应键） |

### 器件文件查找与读取

`device_file(device_name)` 与 `device_json(device_name)` 按以下顺序定位并读取器件 JSON 文件：

1. **展开用户目录**：计算 `candidate = Path(device_name).expanduser()`。
2. **已有目录分支**：若 `candidate.is_dir()` 为真，返回该目录下的 `candidate / "device.json"`。
3. **显式路径分支**：若 `candidate.suffix` 非空（带文件后缀）或 `len(candidate.parts) > 1`（含多段路径），直接返回 `candidate`。
4. **工作区项目分支**：调用 [../supports/README.md](../supports/README.md) 的 `work_root()`，构造 `project = work_root() / str(device_name) / "device.json"`；若 `project.is_file()` 为真，返回 `project`。
5. **组件目录查找分支**：调用 `component_file_path("device", str(device_name))`，依次在项目组件目录 `<项目根>/components/device/`（项目根取环境变量 `RASER_PROJECT_PATH`，未设时为当前目录，见 [工程支撑](../supports/README.md)）、环境变量 `RASER_COMPONENT_PATH` 列出的各目录与内置 `src/raser/components/device/` 下查找 `<device_name>.json`。若所有候选目录均不存在该文件，`component_file_path` 抛出 `FileNotFoundError`（报错信息为 `Cannot find RASER component device/<device_name>.json:` 及搜索路径列表）。
6. **加载 JSON 字典**：`device_json(device_name)` 打开 `device_file(device_name)` 返回的路径并调用 `json.load` 解析。若步骤 2 或步骤 3 返回的路径在磁盘上不存在，打开文件时抛出 `FileNotFoundError`；若该路径指向目录而非文件，抛出 `IsADirectoryError`。

### `Detector` 构造、派生属性与布局校验

`Detector(device_name, device_dict=None)` 按以下严格顺序初始化实例属性：

1. **解析路径与保存字典副本**：调用 `path = device_file(device_name)`（按名称查找失败时在此步抛出 `FileNotFoundError`）。若 `device_dict is None`，调用 `device_json(device_name)` 从磁盘读取字典。将 `copy.deepcopy(device_dict)` 赋给 `self.device_dict`，使器件对象持有的字典与外部传入字典隔离；将 `path.resolve()` 赋给 `self.definition_path`。
2. **映射顶层键为同名属性**：执行 `self.__dict__.update(self.device_dict)`，将 JSON 顶层的所有键值直接写入实例属性字典。
3. **提取偏压与辐照嵌套键**：
   - 计算 `self.voltage = float(self.device_dict['bias']['voltage'])`（$\text{V}$）。若缺少 `'bias'` 或 `'voltage'`，抛出 `KeyError`；若电压值无法转换为 `float`，抛出 `TypeError` 或 `ValueError`。
   - 检查 `"irradiation" in self.device_dict`：若为真，令 `self.irradiation_model = self.device_dict['irradiation']['irradiation_model']`、`self.irradiation_flux = self.device_dict['irradiation']['irradiation_flux']`（$\text{cm}^{-2}$；若 `'irradiation'` 字典内缺少 `'irradiation_model'` 或 `'irradiation_flux'`，抛出 `KeyError`）；若为假，令 `self.irradiation_model = None`、`self.irradiation_flux = 0`。
4. **计算名称、求解维度与三维边界**：
   - 令 `self.det_name = self.device_dict.get('det_name', path.stem)`，并同时令 `self.device = self.det_name`、`self.region = self.det_name`。
   - 令 `self.dimension = self.device_dict.get('field_dimension', self.device_dict['default_dimension'])`。`default_dimension` 必填，缺少时抛出 `KeyError`。
   - 构造边界字典 `self.bound = {'x': (0, self.l_x), 'y': (0, self.l_y), 'z': (0, self.l_z)}`（$\mu\text{m}$）。若 JSON 顶层缺少 `l_x`、`l_y`、`l_z` 中任一键，此处访问同名属性时抛出 `AttributeError`。
5. **校验读出电极布局与专属键**：
   - 读取 `self.electrodes = self.device_dict.get('electrodes', 'pad')`。若 `self.electrodes not in ('pad', 'strip', 'pixel')`，抛出 `ValueError`（`` `electrodes` must be pad, strip or pixel, not <electrodes> ``）。
   - 取 `own = LAYOUT_KEYS[self.electrodes]`，构造缺失必选键列表 `missing = [key for key in own if key not in self.device_dict]`，以及混入的其他布局专属键列表 `foreign = [key for key in ('read_ele_num', 'x_ele_num', 'y_ele_num', 'p_x', 'p_y') if key in self.device_dict and key not in own]`。
   - 若 `missing` 或 `foreign` 非空，抛出 `ValueError`（``<path>: `electrodes` is <electrodes>, which takes the keys <list(own)>; missing <missing>, keys of another layout <foreign>``）。
6. **派生读出电极数量**：
   - 若 `self.is_strip`（即 `self.electrodes == 'strip'`）为真，令 `self.x_ele_num = self.read_ele_num`、`self.y_ele_num = 1`。
   - 否则若 `self.is_pixel`（即 `self.electrodes == 'pixel'`）为真，令 `self.read_ele_num = self.x_ele_num * self.y_ele_num`。
   - 否则（即 `self.electrodes == 'pad'`），令 `self.x_ele_num = 1`、`self.y_ele_num = 1`、`self.read_ele_num = 1`。
7. **校验并计算雪崩倍增开关**：
   - 读取 `self.avalanche_model = self.device_dict.get('avalanche_model')`（缺省为 `None`）与 `enable_gain = bool(self.device_dict.get('enable_gain', False))`。
   - 若 `enable_gain` 为真且 `self.avalanche_model is None`，抛出 `ValueError`（``gain is enabled but `avalanche_model` is missing in detector settings``）。
   - 令 `self.has_avalanche = self.avalanche_model is not None and enable_gain`。
8. **派生单电极间距**：
   - 若 `self.electrodes == 'pad'`，令 `self.p_x = self.device_dict['l_x']`、`self.p_y = self.device_dict['l_y']`（$\mu\text{m}$）。
   - 若 `self.is_strip` 为真，令 `self.p_x = self.device_dict['p_x']`、`self.p_y = self.device_dict['l_y']`（$\mu\text{m}$）。
   - 若 `self.is_pixel` 为真，令 `self.p_x = self.device_dict['p_x']`、`self.p_y = self.device_dict['p_y']`（$\mu\text{m}$）。

### 电容计算与辅助查询

`Detector` 实例在运行期提供以下按需计算属性与方法：

1. **结电容计算（`Detector.capacitance`，`@cached_property`）**：首次读取 `capacitance` 时按以下顺序求值并缓存到实例字典：
   - 若 `"capacitance_pF" in self.device_dict`，返回 `float(self.device_dict["capacitance_pF"])`（$\text{pF}$）。
   - 若 `"3d" in self.det_model.lower()`，返回 `None`（若 JSON 未提供 `det_model`，访问 `self.det_model` 抛出 `AttributeError`）。
   - 计算耗尽层厚度 `depletion_depth = float(self.device_dict.get("depletion_depth", self.l_z))`（$\mu\text{m}$）；若 `depletion_depth <= 0`，抛出 `ValueError`（`depletion_depth must be positive`）。
   - 调用 `Material(self.material)` 获取 `material.permittivity`（`material` 取 `"Si"`、`"SiC"` 或 `"Diamond"`；JSON 未提供 `material`，或材料不在这三种之中（如 `"GaN"`）时抛出 `AttributeError`），调用 `self._readout_area_um2()` 按式 (1) 计算 `area_um2`（$\mu\text{m}^2$），最终按式 (2) 返回结电容（$\text{pF}$）。
2. **附属文件定位（`Detector.file(name)`）**：
   - 计算 `path = Path(name).expanduser()`；若 `not path.is_absolute()`，将其拼接到器件 JSON 所在目录：`path = Path(self.definition_path).parent / path`。
   - 调用 `path = path.resolve()`。若 `not path.is_file()`，抛出 `FileNotFoundError`（`Cannot find <path>, named by <definition_path>`）；否则返回解析后的 `Path` 对象。

## 软件实现

### 模块与函数分工

- `__init__.py`：包说明文件。
- `build_device.py`：实现器件 JSON 路径定位函数 `device_file`、JSON 读取函数 `device_json` 以及探测器数据结构 `Detector`（含构造校验、电极布局判断属性 `is_strip` 与 `is_pixel`、单电极面积计算 `_readout_area_um2`、缓存结电容属性 `capacitance`与外部文件解析方法 `file`）。

### 核心数据结构

`Detector`（`build_device.py`）是使用者和下游环节直接读取的内存对象。除将 `device_dict` 的全部顶层键展开为同名属性外，`Detector` 固定提供以下派生字段与方法：

| 字段或方法 | 类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `device_dict` | `dict` | 无 | 器件 JSON 字典的深拷贝 |
| `definition_path` | `Path` | 无 | `device_file(device_name)` 解析并 `resolve()` 后的器件 JSON 绝对路径 |
| `det_name`, `device`, `region` | `str` | 无 | 探测器名称（三者同值，缺省取 `device_file(device_name)` 返回路径的 `stem`，即 `resolve()` 之前的文件名词干） |
| `dimension` | `int` | 无 | 器件场求解维度（优先取 `field_dimension`，缺省取 `default_dimension`） |
| `voltage` | `float` | $\text{V}$ | 偏置电压 `float(device_dict["bias"]["voltage"])` |
| `irradiation_model` | `str \| None` | 无 | 辐照缺陷模型名称（无 `irradiation` 块时为 `None`） |
| `irradiation_flux` | `float \| int` | $\text{cm}^{-2}$ | 辐照注量（无 `irradiation` 块时为 `0`） |
| `bound` | `dict[str, tuple]` | $\mu\text{m}$ | 器件三维坐标边界 `{'x': (0, l_x), 'y': (0, l_y), 'z': (0, l_z)}` |
| `electrodes` | `str` | 无 | 读出电极排布方式（`"pad"`、`"strip"` 或 `"pixel"`） |
| `is_strip`, `is_pixel` | `bool` | 无 | `electrodes` 是否为 `"strip"` 或 `"pixel"` |
| `x_ele_num`, `y_ele_num`, `read_ele_num` | `int` | 个 | $x$ 方向、$y$ 方向及总读出电极数 |
| `p_x`, `p_y` | `float \| int` | $\mu\text{m}$ | 单个读出电极在 $x$、$y$ 方向的间距或尺寸 |
| `avalanche_model` | `str \| None` | 无 | 碰撞电离倍增模型名称 |
| `has_avalanche` | `bool` | 无 | 是否同时满足 `avalanche_model is not None` 与 `bool(enable_gain)` |
| `capacitance` | `float \| None` | $\text{pF}$ | 单个读出电极结电容（直接指定值、平行板估算值，或 3D 模型返回 `None`） |
| `file(name)` | `Path` | 无 | 解析器件 JSON 引用的附属文件绝对路径并校验文件存在 |

## 接口

使用者能设的是下表列出的器件 JSON 键；真空介电常数 `EPSILON_0_F_PER_M`、布局专属键约束 `LAYOUT_KEYS` 及单位换算系数均写死在代码里。`core/device` 没有独立的命令行环节入口，它在各仿真环节启动时被调用，命令行用法分别见 [../stages/field.md](../stages/field.md)、[../stages/deposit.md](../stages/deposit.md)、[../stages/current.md](../stages/current.md) 与 [../stages/readout.md](../stages/readout.md)。

### 器件文件读取的键

#### 几何、材料与电极

| 键名 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `det_name` | JSON 文件名词干（`path.stem`） | 无 | 探测器名称，构造时同时赋给 `det_name`、`device`、`region` |
| `det_model` | 无（未给 `capacitance_pF` 时访问 `capacitance` 必选；下游必填） | 无 | 探测器模型标识，取 `"planar"`、`"lgad"`、`"ilgad_planar"`、`"strip"`、`"lgadstrip"`、`"pixel"`、`"lgad_pixel"`、`"lgadpixel"`、`"3D_pixel"`、`"3D_column_series"` 之一；转小写后含 `"3d"` 时平行板电容分支返回 `None` |
| `material` | 无（`capacitance` 平行板分支及下游必填） | 无 | 半导体材料，取 `"Si"`、`"SiC"`、`"Diamond"` 或 `"GaN"`；平行板电容分支传入 [model.md](model.md) 的 `Material(material)`，相对介电常数只有 `"Si"`、`"SiC"`、`"Diamond"` 三种，`"GaN"` 器件须给出 `capacitance_pF` |
| `l_x`, `l_y`, `l_z` | 无（必填） | $\mu\text{m}$ | 探测器沿 $x$、$y$、$z$ 方向的全尺寸（$z$ 为厚度方向），用于构造 `bound`、缺省电极尺寸与缺省耗尽层深度 |
| `electrodes` | `"pad"` | 无 | 读出电极排布方式，取 `"pad"`、`"strip"` 或 `"pixel"` |
| `read_ele_num` | `"pad"` 下为 `1`；`"pixel"` 下为 `x_ele_num * y_ele_num` | 个 | 读出电极总数，`"strip"` 布局必填（`"pad"` 与 `"pixel"` 布局禁止在 JSON 中出现） |
| `x_ele_num`, `y_ele_num` | `"pad"` 下为 `1, 1`；`"strip"` 下为 `read_ele_num, 1` | 个 | $x$、$y$ 方向的读出电极数，`"pixel"` 布局必填（`"pad"` 与 `"strip"` 布局禁止在 JSON 中出现） |
| `p_x` | `"pad"` 下取 `l_x` | $\mu\text{m}$ | $x$ 方向读出电极间距，`"strip"` 或 `"pixel"` 布局必填（`"pad"` 布局禁止在 JSON 中出现） |
| `p_y` | `"pad"`、`"strip"` 下取 `l_y` | $\mu\text{m}$ | $y$ 方向读出电极间距，`"pixel"` 布局必填（`"pad"` 与 `"strip"` 布局禁止在 JSON 中出现） |
| `read_out_contact` | 无（下游必填） | 无 | 读出接触电极列表，每项含 `"name"` 及可选邻近扩展单元数 `"x_span"`、`"y_span"`（原样映射为同名属性） |
| `comment` | 无（可选） | 无 | 器件说明文本（原样映射为同名属性） |

#### 偏压、掺杂、辐照与倍增

| 键名 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `bias` | 无（必填，含必填子键 `"voltage"`） | `"voltage"` 为 $\text{V}$ | 偏置对象，含加偏压电极名 `"electrode"` 和偏置电压 `"voltage"`；构造时将 `float(bias["voltage"])` 提取为 `voltage` 属性 |
| `temperature` | 无（下游必填） | $\text{K}$ | 探测器工作温度（原样映射为同名属性） |
| `doping` | 无（场求解或纯扩散收集必填） | $\text{cm}^{-3}$ | 掺杂对象，含沿深度（单位 $\text{cm}$）的 `"Acceptors"`、`"Donors"` 表达式及可选辐照掺杂项 `"Acceptors_ir"`、`"Donors_ir"`（原样映射为同名属性） |
| `irradiation` | 缺省时 `irradiation_model = None`、`irradiation_flux = 0` | `"irradiation_flux"` 为 $\text{cm}^{-2}$（`neq/cm^2`） | 辐照对象，给出时须同时含 `"irradiation_model"`（`"XingChen"`、`"Perugia"`、`"Schwandt"`、`"CommonDefect"`）和 `"irradiation_flux"`，提取为 `irradiation_model` 与 `irradiation_flux` 属性 |
| `avalanche_model` | `None` | 无 | 碰撞电离倍增模型名称，取 `"vanOverstraeten"`、`"Okuto"` 或 `"Hatakeyama"` |
| `enable_gain` | `False` | 无 | 是否启用载流子倍增；转为布尔值后为 `True` 时必须同时提供 `avalanche_model`，二者共同决定 `has_avalanche` |

#### 器件电路

| 键名 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `capacitance_pF` | 无（可选） | $\text{pF}$ | 单个读出电极的结电容；给出时 `Detector.capacitance` 直接返回 `float(capacitance_pF)`；未给定时，读出取场在运行偏压下解出的电容，场没有给出电容时取 `Detector.capacitance` 的平行板估算 |
| `depletion_depth` | `l_z` | $\mu\text{m}$ | `Detector.capacitance` 按平行板公式估算结电容时使用的耗尽层深度（必须 $> 0$） |
| `bias_resistance_ohm` | 无（下游缺省取 `None`） | $\Omega$ | 单个读出电极的偏置电阻（给出时原样映射为同名属性，由 [field.md](field.md) 读取） |
| `coupling_capacitance_pF` | 无（下游缺省取 `None`） | $\text{pF}$ | 单个读出电极的交流耦合电容，给出时须同时提供 `bias_resistance_ohm`（原样映射为同名属性） |
| `undepleted_resistance_ohm`, `undepleted_capacitance_pF` | 无（下游缺省取 `None`） | $\Omega$, $\text{pF}$ | 未耗尽体区的等效电阻与电容；通常由 [field.md](field.md) 按运行时偏压从场算出，器件文件给出时优先采用给定值，两个键须同时给出或同时省略 |
| `resistive_layer` | 无（可选） | 无 | 阻性层定义对象，含方阻 `"sheet_resistance"`（$\Omega$）或注入参数、单元跨度（`"strips"` 或 `"pads"`）及可选 `"grounded"`、`"coupling"`（原样映射为同名属性） |

#### 物理模型与求解维度

器件文件里没有 `mesh` 段：几何（各层厚度、材料、电极在哪一面）是器件的固有性质，网格属于 `field`，用哪一套网格由 `field` 段的设置指定（见 [field.md](field.md)）。物理模型按名字注册，器件文件按名字选用；每种材料有缺省选用的模型（见 [model.md](model.md)）。

| 键名 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `default_dimension` | 无（必填） | 无 | 默认场求解维度，取 `1`、`2` 或 `3` |
| `field_dimension` | `default_dimension` | 无 | 覆盖 `default_dimension` 的场求解维度，构造时赋给 `Detector.dimension` |
| `area_factor` | 无（下游 `field` 缺省取 `1.0`） | 1D 为 $\text{cm}^2$，2D 为 $\text{cm}$，3D 无量纲 | 将一维或二维求解的 IV、CV 与比阻抗换算为整块器件总值的面积或长度因子（给出时原样映射为同名属性） |

### 库中组件

`src/raser/components/device/` 包含以下 23 个探测器组件文件：

| 组件名 | 说明 |
| --- | --- |
| `3D-LGAD` | Si `lgad_pixel` 器件 |
| `3d_column_series` | Si `3D_column_series` 器件 |
| `3d_pixel` | Si `3D_pixel` 器件 |
| `AlGaN_GaN_HEMT_TRANSPORT_V1` | GaN `planar` 器件 |
| `CMOS_strip` | Si `strip` 器件 |
| `CMOS_strip_tcad` | Si `strip` 器件 |
| `DJLGAD_Ayyoub_1D_with_coefficient` | Si `lgad` 器件，一维 Ayyoub DJ-LGAD 系数版本（增益层高斯指数含 `1/2`，峰值 `3.0e16 cm^-3`，标准差 `0.17 um`） |
| `DJLGAD_Ayyoub_Table1_1D` | Si `lgad` 器件，一维 Ayyoub Table 1 文献复现版 DJ-LGAD 近似模型 |
| `general_pixel` | Si `pixel` 器件 |
| `general_strip` | Si `strip` 器件 |
| `HPK-Si-LGAD` | Si `lgad` 器件 |
| `HPK-Si-PiN` | Si `planar` 器件 |
| `iLGAD` | Si `ilgad_planar` 器件 |
| `ITk-md8` | Si `planar` 器件 |
| `ITk-Si-strip` | Si `strip` 器件 |
| `NJU-PiN` | SiC `planar` 器件 |
| `NJU-PiN-bmos` | SiC `planar` 器件 |
| `pixel_ayyouby` | Si `lgadpixel` 器件，3×3 阵列 Ayyoub 风格 DJ-LGAD 像素（间距 `20 × 20 um`） |
| `SICAR-1` | SiC `lgad` 器件 |
| `SICAR-1-PiN` | SiC `planar` 器件 |
| `SiC_LGAD_strip` | SiC `lgadstrip` 器件 |
| `strip_ayyouby` | Si `lgadstrip` 器件，三通道 Ayyoub 风格 DJ-LGAD 条形探测器（间距 `20 um`） |
| `TAICHU3` | Si `pixel` 器件 |

### 输入输出文件与绘图输出

- **输入文件**：UTF-8 编码的器件 JSON 文件（`<work_root>/<device_name>/device.json`、`components/device/<device_name>.json` 或显式路径）以及通过 `Detector.file(name)` 解析的附属文件。
- **输出文件与数据集**：无。`core/device` 仅在内存中构造 `Detector` 实例，不写出磁盘数据文件、属性或数据集。
- **绘图输出**：无。

## 参考文献

- [1] S. M. Sze, K. K. Ng, *Physics of Semiconductor Devices*, 3rd ed., Wiley-Interscience (2007), doi:10.1002/0470068329
- [2] E. Tiesinga, P. J. Mohr, D. B. Newell, B. N. Taylor, “CODATA recommended values of the fundamental physical constants: 2018”, Rev. Mod. Phys. 93 (2021) 025010, doi:10.1103/RevModPhys.93.025010
