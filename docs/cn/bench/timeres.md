# 时间分辨测试（`bench/timeres`）

`timeres`（Time Resolution，时间分辨测试，`raser_bench` 包）是继承 `raser` 实验基类的测试类（见 [架构总纲](../architecture.md#实验是-python-类)），给出被测器件与参考器件的时间差分布，以及两块器件各自相对真实沉积时刻的时间差分布；也可以放三块器件，从三对时间差解出三块各自的时间分辨（见[三块器件](#三块器件)）。器件由一个器件列表给出，列几块放几块，每块都是按器件文件建成的真实器件；默认是命令行给定的被测器件加参考器件 `HPK-Si-LGAD`。β 粒子要依次穿过列表里的全部器件才能触发，所以列表不宜太长。器件放在同一个 `time_resolution` Geant4 装置里，同一个 $\beta$ 放射源（默认 `decay/Sr90`）发出的粒子先后穿过参考器件和被测器件。

`timeres` 读取 [探测器组件（`components/device`）](../components/device.md)、[能量沉积组件（`components/deposit`）](../components/deposit.md)、[前端读出电路组件（`components/readout`）](../components/readout.md)、[数字化器组件（`components/digitizer`）](../components/digitizer.md) 和 [触发组件（`components/trigger`）](../components/trigger.md)，依次走完 [`field`](../stages/field.md)、[`deposit`](../stages/deposit.md)、[`current`](../stages/current.md)、[`readout`](../stages/readout.md)、[`digitizer`](../stages/digitizer.md)、[`trigger`](../stages/trigger.md)、[`reconstruction`](../stages/reconstruction.md) 和 [`analysis`](../stages/analysis.md) 八个环节。除两块器件共用的 [`deposit`](../stages/deposit.md) 外，两块器件各自走一遍 `field`、`current`、`readout`、`digitizer`、`trigger`、`reconstruction`，其中 `trigger` 要求两块器件在同一事例里都过幅度阈值（符合）。默认每作业记录 `10000` 个有效事例并关闭逐事例绘图（`deposit.plots = 0`、`current.plots = 0`），给出被测器件在过阈定时（`ToA`）、时间重心（`CoG`）与各恒比定时分数（`CFD`）下的时间分辨。

## 装置与通用范式

### 通用做法与物理模型

实验室用 $^{90}\text{Sr}$ $\beta$ 放射源测量快速半导体探测器（如 LGAD、4H-SiC PiN 或 SiC LGAD）的时间分辨时，将被测器件（Device Under Test，DUT）与参考探测器沿粒子入射轴上下对齐，安装在中心开有准直圆孔的上下两块读出 PCB 板上，对同时穿透两块器件的 $\beta$ 电子做双器件符合触发，逐事例测量两块器件脉冲到达时刻之差。

`timeres` 对每个通过双器件符合的事例、每个定时通道（`ToA`、`CoG`、`CFD10`–`CFD90`），给出三个时间差：

$$\Delta t = t_{\text{DUT}} - t_{\text{ref}}, \qquad \Delta t_{\text{DUT}} = t_{\text{DUT}} - t_{\text{truth,DUT}}, \qquad \Delta t_{\text{ref}} = t_{\text{ref}} - t_{\text{truth,ref}} \tag{1}$$

第一个是实验里能测到的量，后两个是仿真才有的、各自相对真实沉积时刻的量。三个分布分别用同一种截断高斯迭代拟合（[`core/analysis/resolution.py`](../core/analysis.md) 的 `core_width` 与 `truncated_gaussian`）求核心宽度，在迭代收缩窗口 $[a, b]$ 内最小化负对数似然：

$$\mathcal{L}(\mu, \sigma) = \frac{1}{2}\sum_{i=1}^{n}\left(\frac{x_i - \mu}{\sigma}\right)^{2} + n\ln\sigma + n\ln\!\left[\frac{1}{2}\operatorname{erf}\!\left(\frac{b - \mu}{\sqrt{2}\sigma}\right) - \frac{1}{2}\operatorname{erf}\!\left(\frac{a - \mu}{\sqrt{2}\sigma}\right)\right] \tag{2}$$

其中：

- $t_{\text{DUT}}$、$t_{\text{ref}}$：同一符合事例中被测器件与参考器件在某一定时通道的重建定时时刻，$\text{s}$；
- $t_{\text{truth,DUT}}$、$t_{\text{truth,ref}}$：该事例在被测器件、参考器件内最早能量沉积步的真实全局时刻，$\text{s}$；
- $\Delta t$、$\Delta t_{\text{DUT}}$、$\Delta t_{\text{ref}}$：上面三个时间差，$\text{s}$；
- $x_i$：落在当前拟合窗口 $[a, b]$（单位 $\text{s}$）内的第 $i$ 个样本，取三个时间差中正在拟合的那一个，$\text{s}$；$n$ 为窗口内样本数（无量纲）；
- $\mu$、$\sigma$：截断高斯分布的均值与标准差（核心宽度），$\text{s}$；同时给出窗口内 $16\%$ 至 $84\%$ 分位数间距一半的 `sigma68`（$\text{s}$）。

式 (2) 由 [`stages/analysis`](../stages/analysis.md) 调用 [`core/analysis/resolution.py`](../core/analysis.md) 的 `core_width` 和 `truncated_gaussian` 实现。用参考器件与被测器件符合测时间差的做法见文献 [1]（N. Cartiglia et al., “Beam test results of a 16 ps timing system based on ultra-fast silicon detectors”, *Nucl. Instrum. Methods Phys. Res. A* 850 (2017) 83, doi:10.1016/j.nima.2017.01.021，这篇用的是 180 GeV/c π 束流）及 4H-SiC PIN 探测器时间分辨研究文献 [2]（T. Yang et al., “Time Resolution of the 4H-SiC PIN Detector”, *Front. Phys.* 10 (2022) 718071, doi:10.3389/fphy.2022.718071）。

### `time_resolution` 装置几何

`timeres` 默认加载 Geant4 装置 `time_resolution`（`src/raser/bench/timeres/components/g4setup/time_resolution.py`）。世界体材料为真空 `"G4_Galactic"`，默认半边长 `WORLD_HALF_SIDE = 25000` $\mu\text{m}$。默认 $\beta$ 源 `decay/Sr90` 圆盘中心位于 $z = -17000\ \mu\text{m}$（被测器件顶面上方 $17\ \text{mm}$），圆盘半径 `par_radius = 2500` $\mu\text{m}$，出射半顶角 `par_cone = 15` $\text{degree}$，瞄准原点 `towards = [0, 0, 0]` $\mu\text{m}$，入射倾角 `angle = 0` $\text{degree}$。

装置沿 $+z$ 方向依次放置铝片 `Al`、参考器件、中心开圆孔的上层 PCB 板 `pcb1`、被测器件和中心开圆孔的下层 PCB 板 `pcb2`。`Al`、`pcb1` 与 `pcb2` 沿用 `time_resolution.py` 中的尺寸、材料与位置。参考器件按它的器件文件建成实体（默认 `HPK-Si-LGAD`：材料 `"Si"`，尺寸 $1300 \times 1300 \times 50\ \mu\text{m}$），中心位于 $(0, 0, -10000)\ \mu\text{m}$；被测器件按它的器件文件建成实体，顶面中心位于原点 $(0, 0, 0)\ \mu\text{m}$，占据 $x \in [-l_x/2, l_x/2]$、$y \in [-l_y/2, l_y/2]$、$z \in [0, l_z]\ \mu\text{m}$。两块器件内最大步长均为 `maxstep = 2` $\mu\text{m}$。

Geant4 完整模拟 $\beta$ 电子穿过铝片、参考器件、上层 PCB 板、被测器件和下层 PCB 板时的能量沉积、多次散射与次级粒子产生，同时记录参考器件与被测器件内的能量沉积步。装置沿 $+z$ 方向各实体的尺寸与坐标如下表：

| 实体 | 类型 | 材料与密度 | 全尺寸 `side_x × side_y × side_z`（$\mu\text{m}$） | 中心 `position_z`（$\mu\text{m}$） | $z$ 轴覆盖范围（$\mu\text{m}$） | 中心圆孔 `tub_radius`, `tub_depth`（$\mu\text{m}$） |
| --- | --- | --- | --- | --- | --- | --- |
| `Al` | 周边物体（`elemental`） | `"G4_Al"` | $5000 \times 5000 \times 10$ | `-15000` | $[-15005,\, -14995]$ | 无 |
| 参考器件（默认 `HPK-Si-LGAD`） | 有源器件 | 取器件文件（默认 `"G4_Si"`） | 取器件文件（默认 $1300 \times 1300 \times 50$） | `-10000` | $[-10000 - l_{z,\text{ref}}/2,\, -10000 + l_{z,\text{ref}}/2]$（默认 $[-10025,\, -9975]$） | 无 |
| `pcb1` | 周边物体（`binary_compounds`） | `"SiO2"`（Si/O 原子比 `33.4:66.6`，`2.2 g/cm^3`） | $20000 \times 20000 \times 1500$ | `-8933.5` | $[-9683.5,\, -8183.5]$ | `500`, `1500` |
| 被测器件（命令行给定） | 有源器件 | 取器件文件 | $l_x \times l_y \times l_z$ | $l_z / 2$ | $[0,\, l_z]$ | 无 |
| `pcb2` | 周边物体（`binary_compounds`） | `"SiO2"`（Si/O 原子比 `33.4:66.6`，`2.2 g/cm^3`） | $20000 \times 20000 \times 1500$ | `1100` | $[350,\, 1850]$ | `500`, `1500` |

### 三块器件

器件列表里有三块器件时，三块可以是被测器件加两块参考器件，也可以三块都是被测器件，算法相同。三块器件沿 $+z$ 入射轴依次摆放，每块按自己的器件文件建成实体，周边的铝片和 PCB 板照两块器件时的写法放。三块器件在同一事例里都过幅度阈值才记录这个事例。

记三块器件为 1、2、3。对每个定时通道，[`analysis`](../stages/analysis.md) 拟合三对时间差 $\Delta t_{12} = t_1 - t_2$、$\Delta t_{13} = t_1 - t_3$、$\Delta t_{23} = t_2 - t_3$ 的分布，得到核心宽度 $\sigma_{12}$、$\sigma_{13}$、$\sigma_{23}$。三块器件的定时互相独立时：

$$\sigma_{12}^2 = \sigma_1^2 + \sigma_2^2, \qquad \sigma_{13}^2 = \sigma_1^2 + \sigma_3^2, \qquad \sigma_{23}^2 = \sigma_2^2 + \sigma_3^2 \tag{3}$$

解出三块器件各自的时间分辨：

$$\sigma_1^2 = \frac{\sigma_{12}^2 + \sigma_{13}^2 - \sigma_{23}^2}{2}, \qquad \sigma_2^2 = \frac{\sigma_{12}^2 + \sigma_{23}^2 - \sigma_{13}^2}{2}, \qquad \sigma_3^2 = \frac{\sigma_{13}^2 + \sigma_{23}^2 - \sigma_{12}^2}{2} \tag{4}$$

其中：

- $t_1$、$t_2$、$t_3$：同一事例中三块器件在某一定时通道的重建定时时刻，$\text{s}$；
- $\sigma_{12}$、$\sigma_{13}$、$\sigma_{23}$：三对时间差分布的核心宽度，用式 (2) 拟合，$\text{s}$；
- $\sigma_1$、$\sigma_2$、$\sigma_3$：三块器件各自的时间分辨，$\text{s}$。

统计涨落可能让式 (4) 右边小于 $0$。这时照样输出算出的值，并给一条警告。

三块器件各自相对自身真实沉积时刻的时间差分布照样给出，拟合方法与两块器件时相同。所以三块器件时每个定时通道共有六个分布：三对时间差 $\Delta t_{12}$、$\Delta t_{13}$、$\Delta t_{23}$，以及 $t_1 - t_{\text{truth},1}$、$t_2 - t_{\text{truth},2}$、$t_3 - t_{\text{truth},3}$。

### 执行步骤与内置常数

`timeres` 的执行步骤如下：

1. **求解或复用共享场（`field`）**：分别为被测器件和参考器件定位各自在目标偏压 `voltage`（$\text{V}$）与辐照注量 `irradiation`（$\text{neq/cm}^2$）下的电场、权重场与等效电路参数，未就绪时自动运行 `raser field` 补算。两块器件的共享场各自存放在对应器件 project 的 `field/` 下。
2. **在 `time_resolution` 装置下模拟双器件沉积（`deposit`）**：按各自器件文件同时建出参考器件与被测器件实体，并放置 `Al`、`pcb1`、`pcb2`。从 `decay/Sr90` 发射衰变产物，记录有效沉积事例直到录满默认的 `events_per_job = 10000` 个事例（最多生成 `GENERATED_LIMIT = 10000000` 个源事例），按 `ionized_pairs` 抽样电子-空穴对数写入同一份 `deposit_<job>.h5`，并以 `detector` 字段区分参考器件和被测器件的沉积步。
3. **两块器件各自漂移、读出与数字化（`current`、`readout`、`digitizer`）**：被测器件与参考器件各自在对应求解场中漂移载流子算出感应电流（默认 `current.plots = 0`，关闭逐事例绘图），经各自器件等效电路与前端放大器链（默认 `SantaCruz+Gali52+Termination50`）求解输出电压波形并叠加频域热噪声，再按数字化器的采样与量化设置生成两路数字波形。
4. **双器件符合触发（`trigger`）**：检查同一事例中参考器件与被测器件的数字波形，按触发组件里的符合条件，要求列表里全部器件在同一事例都过幅度阈值。只有通过双器件符合的事例被保留并送入下游。
5. **两块器件各自提取脉冲定时（`reconstruction`）**：对通过符合的事例，分别对被测器件与参考器件的波形扣除前 `BASELINE_POINTS = 200` 点基线并按脉冲边沿翻正，在相邻采样点间线性插值求出过阈到达时间 `ToA`、过阈时长 `ToT`、过阈区间时间重心 `CoG` 以及越过 `fractions`（默认 `0.1` 至 `0.9` 共 `9` 档）乘以峰值幅度 `amplitude` 的恒比定时时刻 `CFD10`–`CFD90`。
6. **截断高斯迭代拟合（`analysis`）**：汇总全部已完成作业的符合事例，对每个定时通道（`ToA`、`CoG`、`CFD10`–`CFD90`）分别构造式 (1) 的三套样本（三块器件时是上面列的六套）（滤除 `NaN`，样本总数少于 `MINIMUM_EVENTS = 20` 时记入 `timing.error`）。三套样本各自以中位数加减 $8$ 倍中位绝对偏差 $\text{median} \pm 8\,\text{MAD}$ 作为首轮窗口 $[a, b]$，在最多 `ROUNDS = 6` 轮迭代中执行 `core_width`：筛选窗口内样本（首轮少于 `20` 个则抛出 `TooFewValues`，后续轮次少于 `20` 个则终止并返回上一轮结果），用 `L-BFGS-B`（均值约束于 $[a, b]$）最小化式 (2) 求出 $(\mu, \sigma)$ 并由步长 `step = 1e-4` 的二阶中心差分海森矩阵求逆得到标准误；当相邻两轮 $|\sigma - \sigma_{\text{prev}}| \le 5\times 10^{-3}\,\sigma_{\text{prev}}$、新窗口 $[\mu - 2\sigma, \mu + 2\sigma]$ 超出旧窗口或窗口宽度缩减量 $\le 10^{-3}(b - a)$ 时收敛停止。三套样本各得一个核心宽度，写出 `result.json`、`events.h5` 与分布图、趋势图。

`timeres` 涉及的内置常数如下表：

| 常数名或固定项 | 取值 | 单位 | 含义 |
| --- | --- | --- | --- |
| 默认 `events_per_job`, `deposit.plots`, `current.plots` | `10000`, `0`, `0` | 事例 | `timeres` 默认每作业记录事例数与两个环节的默认画图事例数 |
| `WORLD_HALF_SIDE` | `25000` | $\mu\text{m}$ | Geant4 世界立方体默认最小半边长 |
| `maxstep` | `2` | $\mu\text{m}$ | 被测器件与参考器件逻辑体内的最大步长限制 |
| `GENERATED_LIMIT` | `10000000` | 事例 | 单作业为录满 `events_per_job` 允许生成的最大源事例数上限 |
| `BASELINE_POINTS` | `200` | 采样点 | 重建扣除基线与计算噪声的前导采样点数 |
| `MINIMUM_EVENTS` | `20` | 事例 | `core_width` 进行截断高斯拟合所需的最少有效样本数 |
| `ROUNDS` | `6` | 轮 | `core_width` 将拟合窗口更新为 $\mu \pm 2\sigma$ 的最大迭代轮数 |
| 初窗 MAD 倍数 | `8` | 无量纲 | 首轮拟合窗口取 $\text{median} \pm 8\,\text{MAD}$ |
| 拟合收敛阈值 | `5e-3`, `1e-3` | 无量纲 | $\sigma$ 相对变化收敛阈值与窗口宽度最小相对缩减量 |
| 海森差分步长 `step` | `1e-4` | 无量纲 | 归一化似然函数二阶中心差分求参数误差的步长 |

## 用到的环节和组件

### 环节

- [`field`](../stages/field.md)：分别为被测器件与参考器件求解或复用目标偏压与辐照注量下的电场、权重场与等效电路参数，各自保存在对应器件 project 的 `field/` 下。
- [`deposit`](../stages/deposit.md)：在 `time_resolution` 装置下用 Geant4 模拟粒子依次穿过铝片、参考器件、上层 PCB 板、被测器件和下层 PCB 板，同时记录两块器件内的能量沉积，默认每作业录满 `10000` 个有效事例。
- [`current`](../stages/current.md)：分别在被测器件和参考器件的求解场中漂移载流子，算出各自读出电极上的感应电流与净电荷，默认关闭单事例画图（`current.plots = 0`）。
- [`readout`](../stages/readout.md)：分别将两块器件的感应电流送入各自器件等效电路和前端放大器链，求解输出电压波形并叠加频域热噪声。
- [`digitizer`](../stages/digitizer.md)：按示波器或数字化板的采样与量化设置，将两块器件的模拟输出波形分别转换为数字波形。
- [`trigger`](../stages/trigger.md)：对两块器件的数字波形执行双器件符合触发，要求两块器件在同一事例里均超过幅度阈值才记录该事例。
- [`reconstruction`](../stages/reconstruction.md)：分别从通过符合的被测器件与参考器件波形中扣除基线并翻正，提取各自的幅度、`ToA`、`ToT`、`CoG` 与 `9` 档 `CFD` 定时时刻。
- [`analysis`](../stages/analysis.md)：对每个定时通道拟合式 (1) 的三个时间差分布，输出统计表、事例表、分布图与跨点趋势图。

### 组件

- [探测器组件（`components/device`）](../components/device.md)：提供被测器件和参考器件的几何、材料、掺杂、偏压、温度、辐照与雪崩倍增参数。参考器件默认使用 `HPK-Si-LGAD`（`HPK-Si-LGAD.json`），被测器件由命令行给定（如 `HPK-Si-PiN`、`NJU-PiN`、`SICAR-1`）。
- [能量沉积组件（`components/deposit`）](../components/deposit.md)：提供默认 Geant4 装置 `time_resolution`（`src/raser/bench/timeres/components/g4setup/time_resolution.py`）和默认 $\beta$ 放射源 `decay/Sr90`（`decay/Sr90.json`）。
- [前端读出电路组件（`components/readout`）](../components/readout.md)：提供以 `+` 串联的 SPICE 放大器级与终端负载子电路（默认 `SantaCruz+Gali52+Termination50`）。
- [数字化器组件（`components/digitizer`）](../components/digitizer.md)：提供示波器或数字化板的采样与量化设置（如 `scope`）。
- [触发组件（`components/trigger`）](../components/trigger.md)：触发条件定义；`timeres` 的触发要求两块（或三块）器件在同一事例里都过幅度阈值。

## 跑法与配置

直接对被测器件运行时间分辨测试，或用 `--scan` 扫描偏压、阈值等参数；命令行传入的器件替换被测器件角色，参考器件默认取 `HPK-Si-LGAD`：

```bash
raser timeres HPK-Si-PiN
raser timeres NJU-PiN
raser timeres NJU-PiN --scan field.voltage=-300,-500
```

实验文件夹 `<project>/timeres/config.json` 按环节分段写设置（格式见 [架构总纲](../architecture.md#project)）。器件列表写在 `timeres` 实验类里，命令行给的器件替换被测器件，参考器件默认是 `HPK-Si-LGAD`。列表里每块器件的偏压、辐照、放大器链、触发阈值和重建阈值分别设。下表是一块器件的键；多块器件时每块各有一组：

| 段.键 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `field.voltage` | 取被测器件文件 `bias.voltage` | $\text{V}$ | 被测器件偏置电压 |
| `field.irradiation` | `None`（未给定时取器件 `irradiation.irradiation_flux`，无则为 `0`） | $\text{neq/cm}^2$ | 被测器件辐照注量 |
| `deposit.source` | `"decay/Sr90"` | 无 | 放射源或束流组件名称或路径 |
| `deposit.g4setup` | `"time_resolution"` | 无 | Geant4 装置组件名称或路径 |
| `deposit.events_per_job` | `10000` | 事例 | 每作业需记录的有效沉积事例数（与 `deposit.generated_per_job` 互斥） |
| `deposit.generated_per_job` | `None` | 事例 | 每作业由源生成的总事例数（与 `deposit.events_per_job` 互斥） |
| `deposit.generated_limit` | `None`（运行时取 `10000000`） | 事例 | 为录满 `events_per_job` 允许生成的最大源事例数上限 |
| `deposit.edep_min` | `None` | $\text{MeV}$ | 记录事例的最小沉积能量下限 |
| `deposit.edep_max` | `None` | $\text{MeV}$ | 记录事例的最大沉积能量上限 |
| `deposit.fano` | `True` | 无 | 电离对数转化是否开启 Fano 涨落抽样 |
| `deposit.plots` | `0` | 事例 | 每作业画 Geant4 几何与径迹图的前若干个记录事例数 |
| `current.plots` | `0` | 事例 | 每作业画载流子漂移路径图与电流图的前若干个记录事例数 |
| `readout.amplifier` | `"SantaCruz+Gali52+Termination50"` | 无 | 以 `+` 连接的前端放大器与终端负载组件链 |
| `reconstruction.threshold` | `10.0` | $\text{mV}$ | 提取 `ToA`、`ToT`、`CoG`、`area` 及邻近电极入簇的过阈阈值 |
| `reconstruction.amplitude_threshold` | `10.0` | $\text{mV}$ | 找团簇种子的脉冲幅度阈值；事例记不记录由 `trigger` 按触发组件判定 |
| `reconstruction.fractions` | `[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]` | 无量纲 | 恒比定时（`CFD`）的幅度比例列表，每项须位于 `(0, 1)` 开区间内 |
| `reconstruction.edge` | `None`（各自沿用对应器件 `readout` 写出的 `pulse_edge`） | 无 | 阈值作用的脉冲边沿方向，可选 `"rising"` 或 `"falling"` |

其余参数（`time_resolution.py` 中 `Al`、`pcb1`、`pcb2` 的尺寸、材料与位置，参考器件中心坐标 `z = -10000 um`，世界默认半边长 `25000 um`，两器件内最大步长 `2 um`，默认最大生成事例数上限 `10000000`，材料平均电离能与 Fano 因子，漂移时间窗与时间步长档位，`ngspice` 噪声分析频率范围与 `27 °C` 温度，重建基线点数 `200`，截断高斯拟合初窗 `median ± 8 * MAD`，最少样本数 `20` 与最大迭代轮数 `6`）固定在代码与默认装置脚本中。

## 输出

结果存放在被测器件 project 下的 `<project>/timeres/`（如 `work/<被测器件>/timeres/`），存放结构见 [架构总纲](../architecture.md#结果)。各环节按输入指纹写入 `<project>/timeres/nodes/<环节>/<节点号>/`，按扫描点在 `<project>/timeres/points/<点名>/<环节>` 生成软链接视图并在 `<project>/timeres/points.json` 记录参数表，单点与跨点时间分辨统计及趋势图存放在 `<project>/timeres/analysis/` 下。被测器件与参考器件的共享场各自存放在对应器件 project 下的 `field/` 中（如 `work/<被测器件>/field/` 与 `work/HPK-Si-LGAD/field/`）。

### 数据与图像文件

上游各环节的数据文件结构与 [`signal`](signal.md#输出) 一致，两块器件各有一份；`deposit_<job>.h5` 按 `detector` 区分两块器件的沉积步。[`analysis`](../stages/analysis.md) 写出：

- `analysis/[<点名>/]result.json`：总事例数、通过符合的事例数，以及 `ToA`、`CoG`、`CFD10`–`CFD90` 每个定时通道三个时间差分布（$t_{\text{DUT}} - t_{\text{ref}}$、$t_{\text{DUT}} - t_{\text{truth,DUT}}$、$t_{\text{ref}} - t_{\text{truth,ref}}$）各自的核心宽度、`sigma68` 和拟合误差，单位 $\text{s}$。
- `analysis/[<点名>/]events.h5`：每个符合事例两块器件各自的 `ToA`、`ToT`、`amplitude`、`baseline`、`noise`、`truth`、`CoG` 和 `CFD10`–`CFD90`，电压 $\text{V}$，时间 $\text{s}$。
- `analysis/[<点名>/]time_difference.png`：各定时通道三个时间差的分布、末轮拟合窗口和截断高斯拟合曲线，横轴 $\text{ps}$。
- `analysis/[<点名>/]resolution_of_fraction.png`：各 `CFD*` 通道三个分布的核心宽度随恒比分数的变化，纵轴 $\text{ps}$。
- 三块器件时，`result.json` 里每个定时通道给出三对时间差分布的核心宽度 $\sigma_{12}$、$\sigma_{13}$、$\sigma_{23}$，按式 (4) 解出的 $\sigma_1$、$\sigma_2$、$\sigma_3$，以及三块器件各自相对真实沉积时刻的分布的核心宽度；`time_difference.png` 画出这六个分布（三对时间差加三块各自相对真实沉积时刻）。
- `analysis/points.json`、`analysis/points.png`：多扫描点下各定时通道三个分布的核心宽度对比表（$\text{s}$）和随扫描变量变化的趋势图（$\text{ps}$）。
