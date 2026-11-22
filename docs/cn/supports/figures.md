# 出图（`supports/figures`）

RASER 画的每一张图，不论出自哪个环节、实验还是资产，也不论用 matplotlib 还是 ROOT 画，都经 `raser.supports.figures` 取样式、存文件。这一页规定图的格式、尺寸与字体、坐标轴、颜色、文件名和存放位置，并列出每个环节至少要画的图。图归谁、放在哪个节点见[架构总纲](../architecture.md#结果)。

## 格式

每张图同时存两份：

- `.png`：200 dpi，给文档和快速查看；
- `.pdf`：矢量图，给细看和放进文章。

用 ROOT 画的图再多存一份 `.root`，里面是画布本身，可以在 ROOT 里重新打开、改坐标范围或取数据。Geant4 离屏画出的几何与径迹图只有 `.png`。

## 尺寸与字体

- 单幅图 6 × 4 英寸，png 为 1200 × 800 像素；ROOT 画布同为 1200 × 800 像素。几幅并排时每幅仍是 6 × 4 英寸，整张图按行列放大。
- 无衬线字体：matplotlib 用默认的 DejaVu Sans，ROOT 用 Helvetica（字体号 43，字号按像素计）。轴标题 12 pt，刻度和图例 10 pt。
- 图上不写总标题，图是什么由文件名和文档里的图注说明。几幅并排时，每幅可以有一行小标题，只写区分这几幅的量，例如 `CFD 30%`。
- 刻度朝内，四边都有刻度；图例无边框；ROOT 不画统计框。
- 二维分布用 viridis 色表（ROOT 为 `kViridis`）。

## 坐标轴与单位

轴标题用英文，写成 `量名 [单位]`：量名首字母大写、用完整的词；无量纲量不加方括号，例如 `Charge collection efficiency`。直方图纵轴写 `Events`。

画图时把数据换算成下表的单位：先把数据化成国际单位制（场求解给出的长度是 cm、电场是 V/cm、掺杂是 cm⁻³，要先化成 m、V/m、m⁻³），再除以 `UNIT[<单位>]`。刻度上不出现 `×10⁻⁹` 这类公共乘子；跨好几个数量级的量（漏电流、掺杂浓度、俘获率）用对数轴。

| 量 | 单位 | 轴标题示例 |
| --- | --- | --- |
| 单事例波形的时间 | ns | `Time [ns]` |
| 时间差、时间分辨 | ps | `CFD 30% - truth [ps]` |
| 感应电流 | μA | `Current [μA]` |
| 漏电流 | A，对数轴 | `Leakage current [A]` |
| 偏压 | V，取绝对值 | `Reverse bias [V]` |
| 放大器输出、数字化后的电压 | mV | `Amplitude [mV]` |
| 器件内的位置、深度 | μm | `Depth [μm]` |
| 装置的尺寸 | mm | `x [mm]` |
| 电场 | kV/cm | `Electric field [kV/cm]` |
| 电势、权重势 | V，权重势无量纲 | `Weighting potential` |
| 掺杂浓度 | cm⁻³，对数轴 | `Doping [cm⁻³]` |
| 俘获率 | s⁻¹，对数轴 | `Trapping rate [s⁻¹]` |
| 电容 | pF | `Capacitance [pF]` |
| 电荷 | fC | `Charge [fC]` |
| 沉积能量 | keV | `Deposited energy [keV]` |

μ 写成 Unicode 字符 `μ`，在 ROOT 里写成 `#mu`。

## 颜色

同一种东西在所有图里用同一种颜色：

| 画的是 | 颜色 |
| --- | --- |
| 电子 | 蓝 `#1f6fb4` |
| 空穴 | 红 `#d1352b` |
| 雪崩倍增产生的电子 | 浅蓝 `#5bb6e8` |
| 雪崩倍增产生的空穴 | 橙 `#f08a3c` |
| 总和（总电流、总电荷） | 黑 |
| 初始沉积点 | 灰 `#808080` |
| 阈值、均值等参考线 | 黑色虚线 |
| 拟合曲线 | 黑色实线 |
| 直方图 | 灰蓝 `#6c8ebf` 填充 |

一张图里画几条同类曲线时：按数值排列的（扫描点的偏压、CFD 分数）从 viridis 色表等距取色；没有先后的（几块器件、几种定时方法）按 Okabe–Ito 八色依次取。ROOT 用同一组颜色，由 `root_color` 换成颜色号。

## 文件名

- 小写英文，词之间用 `_`，说清画的是什么，例如 `electric_field`、`drift_path`。
- 不写器件名、实验名和节点号：图所在的节点已经说明这些。
- 单事例的图在图名后接事例号：`current_17` 是事例 17 的感应电流。事例号与本节点数据文件里的 `event` 一致。
- 同一节点里按偏压、电极等区分的图，在图名后接带单位的取值或编号：`electric_field_200V`、`current_17_electrode_2`。数值写成最短形式：`200.0` 写作 `200`，`0.5` 写作 `0.5`，负数保留负号：`electric_field_-200V`。单位照它本来的大小写。

## 放在哪

| 图 | 位置 |
| --- | --- |
| 环节的图 | 本环节节点里的 `plots/`：`<实验>/nodes/<环节>/<节点号>/plots/` |
| 器件的场的图 | `work/<器件>/field/<节点号>/plots/` |
| 单个扫描点的统计图 | 这个点的 `analysis` 节点里的 `plots/` |
| 跨扫描点的趋势图 | `<实验>/analysis/` |
| 前端电路的原理图和冲击响应 | 电路资产 `work/<电路名>/plots/` |
| `raser <环节> --draw <对象>` 只画对象本身的图 | 该对象的文件夹里的 `plots/`，例如 `work/<器件>/plots/` |

按扫描点看图时，从视图 `<实验>/points/<点名>/<环节>/plots/` 进去，它指向的就是上表的节点。

## 各环节的图

每个环节至少画下面这些图。“单事例”的图画前 `<环节>.plots` 个记录事例，这个选项和它的默认值写在各环节页里；其余每个节点画一张。实验和应用（telescope、tct、bmos、cflm 等）自己特有的图照同样的规矩画，放在它们读写的那个环节的节点里。

| 环节 | 图名 | 画的是 | 张数 |
| --- | --- | --- | --- |
| field | `doping` | 掺杂浓度沿深度的剖面 | 每个节点一张 |
| field | `iv` | 漏电流随反向偏压 | 每个节点一张 |
| field | `cv` | 左：电容随反向偏压；右：$1/C^2$ 随反向偏压 | 每个节点一张 |
| field | `electric_field_<V>V`、`potential_<V>V` | 电场、电势沿深度的剖面；二维、三维器件再加一条横向剖面和一张二维切面 | 每个偏压一张 |
| field | `weighting_potential_<电极>` | 权重势沿深度的剖面，二维、三维同上 | 每个读出电极一张 |
| field | `trapping_rate_<V>V` | 电子和空穴的俘获率沿深度的剖面 | 有辐照时每个偏压一张 |
| field | `device_circuit_<V>V` | 器件参数电路图：结电容、耦合电容、未耗尽层，标上数值 | 每个偏压一张 |
| deposit | `geometry` | Geant4 装置几何和前若干个事例的径迹，白底 | 每个节点一张 |
| deposit | `deposited_energy` | 本节点全部事例在器件里的沉积能量分布 | 每个节点一张 |
| current | `drift_path_<事例号>` | 上：器件三维边界和电子、空穴的漂移轨迹；下：在 $x$-$z$ 平面的投影 | 单事例 |
| current | `current_<事例号>` | 读出电极上电子、空穴、雪崩倍增载流子和总的感应电流；多个电极时每个电极一张，后接 `_electrode_<编号>` | 单事例 |
| current | `charge_per_electrode_<事例号>` | 条形、像素器件各电极收集的电荷 | 单事例 |
| current | `collected_charge` | 本节点全部事例收集的总电荷分布 | 每个节点一张 |
| readout | `waveform_<事例号>` | 上：输入的感应电流；下：放大器输出的电压波形（含噪声） | 单事例 |
| readout | `schematic`、`impulse_response` | 前端电路的原理图和冲击响应，存进电路资产 | 每个电路一张 |
| digitizer | `samples_<事例号>` | 模拟波形叠上数字化后的样点 | 单事例 |
| trigger | `trigger_amplitude` | 记录与丢弃的事例的幅度分布，画出触发阈值 | 每个节点一张 |
| reconstruction | `features_<事例号>` | 数字波形上标出基线、幅度、ToA、各 CFD 时刻 | 单事例 |
| analysis | `efficiency` | 电荷收集效率分布，虚线为均值 | 每个扫描点一张 |
| analysis | `amplitude` | 记录事例的幅度分布，虚线为幅度阈值 | 每个扫描点一张 |
| analysis | `time_difference` | 每种定时方法的时刻减真实时刻的分布和截断高斯拟合，一种方法一幅 | 每个扫描点一张 |
| analysis | `resolution_of_fraction` | 时间分辨随 CFD 分数 | 每个扫描点一张 |
| analysis | `trend` | 左：电荷收集效率随扫描量；右：各定时方法的时间分辨随扫描量 | 每个实验一张，只扫一个数值量时画 |

## 用法

```python
from raser.supports import figures

figure, axis = figures.new()                       # 单幅，6 × 4 英寸，样式已设好
axis.step(time / figures.UNIT["ns"], current / figures.UNIT["uA"], color=figures.ELECTRON, label="electrons")
axis.set_xlabel(figures.label("Time", "ns"))       # "Time [ns]"
axis.set_ylabel(figures.label("Current", "uA"))    # "Current [μA]"
figures.save(figure, folder, "current", 17)        # folder/current_17.png、current_17.pdf
```

用 ROOT 画时：

```python
canvas = figures.canvas()                          # 1200 × 800 像素，gStyle 已设好
graph.SetLineColor(figures.root_color(figures.HOLE))
graph.GetXaxis().SetTitle(figures.label("Depth", "um", root=True))   # "Depth [#mum]"
figures.save_canvas(canvas, folder, "drift_path", 17)   # drift_path_17.png、.pdf、.root
```

| 名字 | 作用 |
| --- | --- |
| `new(rows=1, columns=1)` | 新建 matplotlib 图，每幅 6 × 4 英寸，返回图和轴（多幅时为轴的数组） |
| `canvas(columns=1, rows=1)` | 新建 ROOT 画布，每幅 1200 × 800 像素，并设好 `gStyle` |
| `save(figure, folder, name, *suffixes)` | 存 `<名字>.png` 和 `<名字>.pdf`，返回 png 的路径；`folder` 不存在时建好 |
| `save_canvas(canvas, folder, name, *suffixes)` | 存 `.png`、`.pdf`、`.root` 三份，返回 png 的路径 |
| `file_name(name, *suffixes)` | 按上面的规则拼出文件名（不含扩展名）。后缀可以是数、小写词，或“数和单位”的二元组：`file_name("electric_field", (200.0, "V"))` 为 `electric_field_200V`，`file_name("current", 17, "electrode", 2)` 为 `current_17_electrode_2` |
| `label(quantity, unit=None, root=False)` | 拼轴标题：`label("Depth", "um")` 为 `Depth [μm]`，不给单位时只有量名 |
| `UNIT` | 单位到国际单位制的倍数，例如 `UNIT["ns"] == 1e-9`；画图时用国际单位制的数据除以它。键为单位表里的全部单位，用 ASCII 写：`ns`、`ps`、`uA`、`A`、`V`、`mV`、`um`、`mm`、`kV/cm`、`cm-3`、`s-1`、`pF`、`fC`、`keV` |
| `ELECTRON`、`HOLE`、`GAIN_ELECTRON`、`GAIN_HOLE`、`TOTAL`、`DEPOSIT`、`HISTOGRAM` | 上面颜色表里的颜色 |
| `series(count, ordered)` | 一张图里几条同类曲线的颜色：`ordered=True` 从 viridis 等距取，否则按 Okabe–Ito 依次取 |
| `root_color(color)` | 把上面的颜色换成 ROOT 颜色号 |

出错时：

- 图名或作后缀的词含大写字母、空格或 `_` 以外的符号，`file_name` 抛 `ValueError: figure name must be lowercase words joined by _: <名字>`；
- 单位不在 `UNIT` 里，`label` 抛 `ValueError: unknown unit: <单位>`。
