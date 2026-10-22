# Device

_RASER 5.0 传感器定义与项目布局_

Device 描述一个传感器。其项目包含 `device.json`，其中保存传感器默认状态，以及为该探测器生成的可复用数据。Field 数据保存在此项目中。依赖粒子源、扫描或其他应用场景的结果归属相应应用。

---

## 📋 职责

Device 负责传感器标识。其定义包含判断两次计算是否采用同一传感器所需的信息，以及应用解析所用的默认值。加载时校验坐标映射、接触、读出阵列、电学量与模型绑定之间的关系。自洽集合构成运行时传感器定义；缺失内容在 Device 边界触发失败。

修改 Device 定义会产生新的定义版本。选择另一工作状态会产生与现有定义版本关联的已解析项目或运行状态。Component 与 Runs 契约解析这些值，Device 根据 `device.json` 校验结果。

Device 将模型绑定保存为传感器定义的一部分。绑定指定的 Core 模块解释相应配置、执行计算并持有所得数值状态。

Device 可直接采用其默认值，也可由应用项目中的 [Device 组件](../components/device.md)引用。组件提供该项目采用的 Device 状态与 Field 值，`device.json` 保留规范定义与默认值。

## 🗂️ 项目布局

```text
<device>/
├── device.json
└── field/
    ├── <field-config-hash>/
    └── ...
```

`device.json` 是 Device 项目的规范定义。`field/` 下每个目录以完整 Field 配置的哈希命名，并保存其可复用资产。配置与哈希规则见 [Field](field.md#配置)。应用运行保存在应用项目中，并引用其采用的 Device 与 Field 配置。

## 📥 定义契约

`device.json` 提供自包含的传感器定义。各声明彼此闭合：灵敏体映射到探测器坐标域，Field 接触名称对应 Device 接触，读出电极遵循声明的二维阵列与电极顺序。每个模型绑定对应完整配置。声明的坐标映射联系独立的 Geant4 包络与运行时区域。

该文件还提供配置解析的默认值。解析从这些默认值开始，随后应用 Component 与调用替换值。`field/` 保留为 Device 产生或导入的完整配置。`device.json` 是 Field 生成与加载期间的默认值来源。

[Device 组件](../components/device.md)为应用项目替换默认值。[运行记录](../supports/runs.md)解析更具体的调用值并保存结果。[Field](field.md) 随后将解析值转为配置，其哈希用于寻址可复用数据。

## 🔲 读出几何

读出表面采用两个正交索引轴。Pad、strip 与 pixel 布局共享一项二维阵列契约：

| 读出布局 | 阵列契约 |
| --- | --- |
| Pad | `1 × 1` 阵列 |
| Strip | `read_ele_num × 1` 或 `1 × read_ele_num` 阵列，在分段轴上设置 pitch |
| Pixel | `x_ele_num × y_ele_num` 阵列，pitch 为 `p_x` 和 `p_y` |

增益器件加入明确的雪崩模型与增益区定义。采用多维 Field 数据的器件加入接触几何与对应网格。它们采用相同的有序 `(x, y)` 读出阵列。

## 📐 几何、单位与坐标

| 值 | 单位或约定 |
| --- | --- |
| `l_x`、`l_y`、`l_z`、pitch、增益边界 | µm |
| 偏压 | V |
| 温度 | K |
| 电容 | pF |
| 运行时点 | 以 µm 表示的探测器坐标 `(x, y, z)` |
| 运行时边界 | `0 ≤ x ≤ l_x`、`0 ≤ y ≤ l_y`、`0 ≤ z ≤ l_z`；显式映射可采用其他范围 |

运行时边界是 Field 与载流子输运接受的传感器区域。Geant4 设计具有独立包络与放置，并可包含非灵敏层、支撑结构或导入的装配体。

Geant4 契约标识灵敏体，并将其坐标映射到探测器坐标。载流子输运接收运行时区域内映射后的沉积。映射明确陈述 Geant4 包络与运行时边界的关系，二者相同时也予以记录。

求解器原生单位与坐标轴可以采用不同约定。转换属于 Field 契约；下游输运接收探测器坐标。

## ⚙️ 运行时 Device 契约

Device 从 `device.json` 开始。应用按照 [Runs](../supports/runs.md) 解析组件值与运行级值，再由 Device 校验结果。运行时 Device 将传感器定义与已解析状态组合。

[Field 配置](field.md#配置)将解析值写入 `config.json`，并以其哈希作为数据目录名。应用在 [run.json](../supports/runs.md) 中记录相同配置与哈希。Device 将解析值传给 Field。Field 根据配置哈希得到资产目录并恢复其中的文件。

Device 可声明作为传感器建模预输入的传感器电学值。Field AC 结果提供与已计算 Field 配置关联的数值。[Frontend](frontend.md) 使用所选数值构建传感器网表。

<!-- TODO: 定义 Device 电学值与 Field AC 结果之间的解析方式。 -->

启用增益需要雪崩模型绑定及其增益区几何。

## 🔗 下游契约

| 使用者 | 使用的 Device 数值 |
| --- | --- |
| [Field](field.md) | 结构、材料、掺杂、接触、网格、工作条件，以及 Field 与 Damage 选择 |
| [Interaction](interaction.md) | Geant4 几何、灵敏体映射、材料与运行时区域 |
| [Carrier 与 current](current.md) | 运行时区域、材料、温度、接触、读出阵列，以及 Gain 与 Transport 选择 |
| [Frontend](frontend.md) | 传感器电学定义、读出电极与 Readout 选择 |
| [Metrics](metrics.md) | Device 标识、几何、pitch 与电极数 |

## ✍️ 扩展契约

1. 定义运行时区域与探测器坐标约定。
2. 定义 Geant4 几何及其到运行时区域的映射。
3. 声明两个读出轴的数量、pitch 与接触。
4. 声明 `field_source`、`field_dimension`，以及 Damage、Transport、Gain 与 Readout 模型选择。
5. 以 pF 明确声明电容。
6. 提供默认 Device 状态与 Field 值。
