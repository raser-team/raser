# 单器件信号测试（`bench/signal`）

`signal`（`raser_bench` 包）是单器件的基准全链路测试，以命令行给定的被测器件为主体。它从 [探测器组件（`components/device`）](../components/device.md)、[能量沉积组件（`components/deposit`）](../components/deposit.md)、[前端读出电路组件（`components/readout`）](../components/readout.md)、[数字化器组件（`components/digitizer`）](../components/digitizer.md) 和 [触发组件（`components/trigger`）](../components/trigger.md) 读入单块器件与单个源、装置、电子学配置，依次走完 [`field`](../stages/field.md)、[`deposit`](../stages/deposit.md)、[`current`](../stages/current.md)、[`readout`](../stages/readout.md)、[`digitizer`](../stages/digitizer.md)、[`trigger`](../stages/trigger.md)、[`reconstruction`](../stages/reconstruction.md) 和 [`analysis`](../stages/analysis.md) 八个环节，输出被测器件的电荷收集效率，以及各定时量相对真实沉积时刻的时间差分布与时间分辨。相对真实沉积时刻的时间分辨在实验里不可观测，要测实验可观测的时间分辨用 [`timeres`](timeres.md)。

## 装置与通用范式

### 通用做法与物理定义

学术界测试单块半导体探测器的信号响应与电荷收集效率（Charge Collection Efficiency，CCE）时，用放射源（$\beta$ 源、$\alpha$ 源）、单能粒子束流或脉冲激光照射施加反向偏压的被测器件，读出电极上的感应电流经前端放大器、数字化器与触发判选记录为电压波形，由收集到的电荷与入射粒子在灵敏区电离产生的初始电荷之比给出电荷收集效率。

在 RASER 中，单个事例的电荷收集效率 $\eta$ 与重建定时时刻相对真实沉积时刻的时间差 $\Delta t$ 分别为：

$$\eta = \frac{\left|\sum_{j} Q_{j}\right|}{N_{\text{pairs}}\,e_0} \tag{1}$$

$$\Delta t = t_{\text{reco}} - t_{\text{truth}}, \qquad t_{\text{truth}} = \min_{k} t_{k} \tag{2}$$

其中：

- $\eta$：单事例电荷收集效率（无量纲；存在雪崩倍增时 $\eta > 1$）；
- $Q_j$：第 $j$ 个读出电极的带符号净感应电荷，$\text{C}$（由 `current` 节点的 `current.h5` 的 `charge` 数据集给出，含时间窗前后的欠流箱与溢流箱）；
- $N_{\text{pairs}}$：该事例在器件内电离产生的初始电子-空穴对总数（倍增前），对（由 `current` 节点的 `current.h5` 的 `pairs` 数据集给出）；
- $e_0$：元电荷，代码中常数 `ELEMENTARY_CHARGE` 取 $1.602176634\times 10^{-19}\ \text{C}$；
- $t_{\text{reco}}$：由重建波形提取的脉冲定时时刻（过阈时刻 `ToA`、时间重心 `CoG` 或各恒比分数时刻 `CFD10`–`CFD90`），$\text{s}$；
- $t_k$：该事例在 `deposit` 节点的 `deposit.h5` 中第 $k$ 个能量沉积步的全局时刻，$\text{s}$，$t_{\text{truth}}$ 为该事例最早沉积步的时刻 `truth`，$\text{s}$；
- $\Delta t$：重建时刻相对真实最早沉积时刻的时间差，$\text{s}$。

式 (1) 由 [`core/analysis/collection.py`](../core/analysis.md) 的 `collection_efficiency(charge, pairs)` 对 `current` 节点里的全部事例计算，并由 [`stages/analysis/collection.py`](../stages/analysis.md) 的 `efficiency_spread` 汇总样本均值 `mean`、均值标准误 `mean_error` 与样本标准差 `spread`（自由度修正 `ddof=1`）。式 (2) 由 [`stages/analysis/timing.py`](../stages/analysis.md) 的 `event_times` 与 `time_widths` 计算，对 `trigger` 记录下来且在 `reconstruction` 中找到团簇种子的 `selected` 事例调用 [`core/analysis/resolution.py`](../core/analysis.md) 的 `core_width` 做截断高斯最大似然迭代拟合，给出核心宽度 `sigma` 与 `sigma68`（单位 $\text{s}$）。半导体探测器信号形成与电荷收集测量原理见文献 [1]（G. Lutz, *Semiconductor Radiation Detectors: Device Physics*, Springer (2007), doi:10.1007/978-3-540-71679-2）。

局限：式 (2) 直接以仿真记录的真实最早沉积时刻 $t_{\text{truth}}$ 为参考，不含参考探测器时间抖动与符合触发，在真实实验中不可直接观测。

### Geant4 装置几何

默认装置为 `device_alone`（`raser/components/deposit/device_alone.py`，见 [`../components/deposit.md`](../components/deposit.md)）：世界立方体材料为真空 `"G4_Galactic"`（默认半边长 `WORLD_HALF_SIDE = 25000` $\mu\text{m}$），被测器件逻辑体 `"Device"` 单独置于世界中心，顶面中心位于原点 $(0, 0, 0)\ \mu\text{m}$，占据 $x \in [-l_x/2, l_x/2]$、$y \in [-l_y/2, l_y/2]$、$z \in [0, l_z]\ \mu\text{m}$，器件内最大步长 `maxstep = 2` $\mu\text{m}$；放射源或束流起点位于顶面上方 $17\ \text{mm}$ 处（`at = [0, 0, -17000]` $\mu\text{m}$），瞄准原点 `towards = [0, 0, 0]` $\mu\text{m}$，入射倾角 `angle = 0` $\text{degree}$。

电荷收集效率就由这个装置给出，和时间分辨用同一批事例，测效率不另换装置。

此外，`signal` 组件目录（`src/raser_bench/signal/components/deposit/`，见 [`../components/deposit.md`](../components/deposit.md)）还提供 `Sr90_collimator`（空气 `"G4_AIR"` 中在 $z = -14000\ \mu\text{m}$ 处放置 $10000 \times 10000 \times 5000\ \mu\text{m}$、中心圆孔半径 `tub_radius = 500` $\mu\text{m}$、半深 `tub_depth = 2600` $\mu\text{m}$ 的黄铜 `"G4_BRASS"` 准直器，跨越 $z \in [-16500, -11500]\ \mu\text{m}$）和 `pcb_readout_gdml`（`"geant4_model": "gdml_import"`，导入外部 `pcb_readout.gdml`，世界半边长 `world_half_size_um = 2000000` $\mu\text{m}$）。

### 四类信号源

换源就是换 `deposit` 环节读的源组件，链和输出不变：

- **$\beta$ 源**：默认是 `decay/Sr90`（`raser/components/deposit/decay/Sr90.json`，`"kind": "decay_source"`）。每个事例在半径 `par_radius = 2500` $\mu\text{m}$（直径 $5\ \text{mm}$）的圆盘上等概率抽取 $^{90}\text{Sr}$（`[38, 90]`）或子核 $^{90}\text{Y}$（`[39, 90]`）静止衰变一次，衰变产物在围绕轴线半顶角 `par_cone = 15` $\text{degree}$ 的圆锥内各向同性出射（立体角占比 $f_{\text{gen}} = (1 - \cos 15^\circ)/2 \approx 0.017037$）。电子穿透器件，整条径迹穿过灵敏区，近似最小电离粒子。
- **$\alpha$ 源**：例如 `decay/Am241`（`raser/components/deposit/decay/Am241.json`，`"kind": "decay_source"`，`par_type = "alpha"`，单能动能 `par_energy = 5.54` $\text{MeV}$）。$\alpha$ 粒子在器件表层很浅的深度内停下，能量沉积集中在入射面附近。
- **激光**：单光子吸收（`"SPA"`）或双光子吸收（`"TPA"`），从顶面、底面或侧面（`"top"`、`"bottom"`、`"edge"`）入射，在焦点 $(x_{\text{focus}}, y_{\text{focus}}, z_{\text{focus}}) = (\text{fx\_rel}\cdot l_x,\, \text{fy\_rel}\cdot l_y,\, \text{fz\_rel}\cdot l_z)$（单位 $\mu\text{m}$）附近产生载流子。激光组件的键见 [`../components/deposit.md`](../components/deposit.md)。

- **束流**：单能粒子束（`"kind": "beam"`），例如质子束 `beam/proton`（`raser/components/deposit/beam/proton.json`，`par_type = "proton"`，动能 `par_energy = 1000.0` $\text{MeV}$，横向随机偏移半宽 `par_randx = par_randy = 0` $\mu\text{m}$）。一个事例里可以发射单个粒子，也可以通过 `particles` 列表同时发射多个粒子（见 [`../apps/bmos.md`](../apps/bmos.md)）。

![HPK-Si-PiN 单事例载流子漂移路径](../images/current-drift-path-HPK-Si-PiN.png)

`HPK-Si-PiN` 在默认 `decay/Sr90` 源下一个事例的电子和空穴漂移路径：$\beta$ 电子穿透整个器件，沿径迹产生的载流子分别向两极漂移。

![HPK-Si-PiN 单事例感应电流](../images/current-event-HPK-Si-PiN.png)

同一个 Sr90 $\beta$ 电子事例在读出电极上的感应电流：电子分量、空穴分量和总电流。

### 代码执行步骤与内置常数

单个 `signal` 作业按以下顺序执行：

1. **检查与求解共享场（`field`）**：主命令在作业开始前检查 `<project>/field/` 下是否存在匹配当前器件、偏压 `voltage`（$\text{V}$）与辐照注量 `irradiation_flux`（$\text{cm}^{-2}$，$1\ \text{MeV}$ 中子等效注量）的场节点；未就绪则在作业开始前补算，存进 `<project>/field/<节点号>/`（写入期间带 `.part` 后缀，完成后落盘并含 `node.json`）。实验在 `points.json` 中记录该节点号，并用视图软链接 `points/<点名>/field` 指向它。
2. **能量沉积与电离对生成（`deposit`）**：`stages/deposit.py` 调用 `write_simulated_deposits` 运行 Geant4（或 `toy_mip`）。仅保留在 `"Device"` 内总沉积能量 $E_{\text{tot}} > 0$ 且满足 $\text{edep\_min} \le E_{\text{tot}} \le \text{edep\_max}$（单位 $\text{MeV}$，未设上下限时仅要求 $E_{\text{tot}} > 0$）的事例，直至录满 `events_per_job` 个事例（最多生成 `generated_limit` 个源事例，超过仍未录满则抛出 `RuntimeError`）或生成满 `generated_per_job` 个源事例。每步沉积能量 $E_k$（$\text{MeV}$）在 `ionized_pairs` 中除以材料平均电离能 $\varepsilon_{\text{pair}}\times 10^{-6}$（$\text{MeV}$）并按 `fano` 开关抽样电子-空穴对数，将坐标从 Geant4 中心坐标系平移 $+l_x/2, +l_y/2$ 到 $[0, l_x] \times [0, l_y] \times [0, l_z]\ \mu\text{m}$ 写入 `deposit` 节点的 `deposit.h5`，并按 `deposit.plots` 在节点内绘制几何与径迹图。若录得 `0` 个事例，抛出 `Ended` 提前结束作业。
3. **载流子漂移与感应电流分箱（`current`）**：`stages/current.py` 加载 `DevsimField`，调用 `write_induced_currents`（默认开启热扩散 `diffusion=True`）对每个记录事例在器件与电极阵列边界内推进电子、空穴漂移（含辐照俘获与雪崩倍增），按 Shockley-Ramo 定理在时间箱宽 `t_bin`（1D 为 $5\ \text{ps}$，2D/3D 为 $50\ \text{ps}$）上分箱累加感应电流并写出 `current` 节点的 `current.h5`，同时在节点内为前 `current.plots` 个事例绘制漂移路径与电流图。
4. **等效电路与前端放大器读出（`readout`）**：`stages/readout.py` 构建器件等效电路 `DeviceCircuit` 并按 `+` 拆分加载 `amplifier` 指定的 SPICE 子电路链，调用 `ngspice` 求解瞬态响应与频域热噪声谱（以由作业种子派生的 `readout` 噪声种子独立合成时域高斯热噪声叠入波形），仅保存最大电压摆幅 $\ge 10^{-3} V_{\max}$ 的通道写入 `readout` 节点的 `readout.h5`。
5. **数字化与触发（`digitizer`、`trigger`）**：`digitizer` 按数字化器组件（默认 `MXR608A`）的模拟带宽、采样和量化（时钟相位与孔径抖动由作业种子派生的 `digitizer` 种子抽取）把模拟波形转为量化码写入 `digitizer` 节点的 `digitizer.h5`；`trigger` 按触发条件判定记录哪些事例，将被记录事例的事例号数据集 `event`（`int64`）写入 `trigger` 节点的 `trigger.h5`。
6. **波形特征提取与成簇（`reconstruction`）**：`stages/reconstruction.py` 读取 `digitizer.h5` 中被 `trigger.h5` 记录的事例，按 `lsb_V`、`offset_V` 把量化码换回电压（$\text{V}$），采样时刻为 `t0 + k·sampling_period`；将 `threshold` 与 `amplitude_threshold` 从 $\text{mV}$ 乘以 $10^{-3}$ 换为 $\text{V}$，扣除波形开头 `BASELINE_POINTS = 200` 个采样点的均值基线并按脉冲边沿 `edge` 翻正，提取幅度、`ToA`、`ToT`、`CoG`、`area` 及各 `fractions` 对应的 `CFD` 时刻，以幅度不低于 `amplitude_threshold` 的电极为种子跨电极成簇并将找到种子的事例记为 `selected`，写入 `reconstruction` 节点的 `reconstruction.h5`。
7. **收集效率与时间分辨统计（`analysis`）**：`stages/analysis` 汇总各扫描点所有已完成作业，用 `current` 节点里的全部事例按式 (1) 计算收集效率分布，用 `selected` 事例按式 (2) 计算时间分辨，在各扫描点的 `analysis` 节点（`nodes/analysis/<节点号>/`，视图 `points/<点名>/analysis/`）写出单点 `result.json`、`events.h5` 与分布图，并在 `<实验>/analysis/` 下写出多扫描点对比文件 `points.json`、`points.png`。

全链路涉及的内置常数如下表：

| 常数名 | 取值 | 单位 | 定义位置与含义 |
| --- | --- | --- | --- |
| `WORLD_HALF_SIDE` | `25000` | $\mu\text{m}$ | `src/raser/core/deposit/simulate_deposits.py`，Geant4 世界立方体默认最小半边长 |
| `PAIR_ENERGY_EV` | `"Si": 3.6`, `"SiC": 7.83`, `"Diamond": 13.1` | $\text{eV}$ | `src/raser/core/deposit/ionization.py`，各材料产生一对电子-空穴对的平均电离能；Si 取 PDG 第 35.8 节表 35.10 的 $3.65\ \text{eV}$ 的近似（S. Navas et al., Phys. Rev. D 110 (2024) 030001, doi:10.1103/PhysRevD.110.030001），4H-SiC 取 $(7.83 \pm 0.02)\ \text{eV}$（A. Gsponer et al., NIM A 1064 (2024) 169412, doi:10.1016/j.nima.2024.169412） |
| `FANO_FACTOR` | `"Si": 0.115`, `"SiC": 0.128`, `"Diamond": 0.382` | 无量纲 | `src/raser/core/deposit/ionization.py`，各材料电离对数涨落的 Fano 因子；Si 取渐近值 0.115（K. Ramanathan, N. Kurinsky, Phys. Rev. D 102 (2020) 063026, doi:10.1103/PhysRevD.102.063026；实测 0.1161 见 B. G. Lowe, NIM A 399 (1997) 354, doi:10.1016/S0168-9002(97)00965-0），4H-SiC 取 0.128（S. K. Chaudhuri, K. J. Zavalla, K. C. Mandal, Appl. Phys. Lett. 102 (2013) 031109, doi:10.1063/1.4776703） |
| `t_bin`, `delta_t` | 1D: `5e-12`, `2e-12`；2D/3D: `50e-12`, `20e-12` | $\text{s}$ | `src/raser/core/current/cal_current.py`，感应电流时间箱宽与单步漂移时间步长 |
| `PART_EDGE` | `1e-3` | 无量纲 | `src/raser/core/readout/job.py`，保存输出波形通道所需的最小电压摆幅占最大通道摆幅比例 |
| `MILLIVOLT` | `1.0e-3` | $\text{V/mV}$ | `src/raser/stages/reconstruction.py`，将 `threshold` 与 `amplitude_threshold` 从 $\text{mV}$ 换算为 $\text{V}$ 的系数 |
| `BASELINE_POINTS` | `200` | 采样点 | `src/raser/core/reconstruction/event.py`，波形开头用于计算基线均值与噪声标准差的固定采样点数 |
| `ELEMENTARY_CHARGE` | `1.602176634e-19` | $\text{C}$ | `src/raser/core/analysis/collection.py`，式 (1) 计算电荷收集效率使用的元电荷 |
| `MINIMUM_EVENTS`, `ROUNDS` | `20`, `6` | 事例, 轮 | `src/raser/core/analysis/resolution.py`，截断高斯时间分辨拟合所需最少样本数与最大窗口收缩迭代轮数 |
| `PICOSECOND` | `1.0e-12` | $\text{s/ps}$ | `src/raser/stages/analysis/plots.py`，时间差与时间分辨作图的秒到皮秒换算系数 |

## 用到的环节和组件

### 环节

- [`field`](../stages/field.md)：求解或复用被测器件在目标偏压与辐照注量下的电场、权重场、导电区标志及结电容/未耗尽层参数，存放在 `<project>/field/<节点号>/`。
- [`deposit`](../stages/deposit.md)：根据所选源与 Geant4 装置模拟粒子在被测器件内的能量沉积步并转化为初始电子-空穴对，写入 `deposit.h5`。
- [`current`](../stages/current.md)：将沉积产生的电子-空穴对放入求解场中漂移、扩散与倍增，算出各读出电极上的时域感应电流与净感应电荷，写入 `current.h5`。
- [`readout`](../stages/readout.md)：把感应电流送入器件等效电路与 SPICE 前端放大器链，求解输出电压波形并叠加电路热噪声，写入 `readout.h5`。
- [`digitizer`](../stages/digitizer.md)：按数字化器模拟带宽、采样率与量化位数把模拟输出波形转换为量化码数字波形，写入 `digitizer.h5`。
- [`trigger`](../stages/trigger.md)：按触发设备判选条件筛选记录事例，将被记录事例的事例号写入 `trigger.h5`。
- [`reconstruction`](../stages/reconstruction.md)：读取 `digitizer.h5` 中被 `trigger` 记录的事例，按 `lsb_V`、`offset_V` 把量化码换回电压（$\text{V}$），扣除前 `200` 点基线，提取脉冲幅度、`ToA`、`ToT`、`CoG`、`area`、`CFD` 与多电极团簇特征，将找到种子的事例记为 `selected`，写入 `reconstruction.h5`。
- [`analysis`](../stages/analysis.md)：汇总各扫描点的已完成作业，拟合电荷收集效率与相对真实沉积时刻的时间分辨，在各扫描点的 `analysis` 节点写出单点结果和分布图，并在 `<实验>/analysis/` 下写出跨点统计和趋势图。

### 组件

- [探测器组件（`components/device`）](../components/device.md)：提供被测器件的尺寸、材料、掺杂、偏压、温度、辐照模型、雪崩模型与等效电路参数（如 `HPK-Si-PiN.json`、`NJU-PiN.json`）。
- [能量沉积组件（`components/deposit`）](../components/deposit.md)：提供放射源与束流（如默认 `decay/Sr90.json`、`decay/Am241.json`、`beam/proton.json`）、激光（如 `PIL037_top_SiC.json`）及 Geant4 装置（如默认 `device_alone.py`、`Sr90_collimator.py`）。
- [前端读出电路组件（`components/readout`）](../components/readout.md)：提供以 `+` 串联的 SPICE 放大器级与终端负载子电路（默认 `SantaCruz+Gali52+Termination50`）。
- [数字化器组件（`components/digitizer`）](../components/digitizer.md)：提供示波器或数字化板的采样和量化设置；兼管触发的设备（如示波器 `MXR608A`），它的触发条件也写在这里。
- [触发组件（`components/trigger`）](../components/trigger.md)：提供独立触发设备的触发判选条件定义。

## 跑法与配置

直接对被测器件运行 `signal`（快速入门示例，链上每一步的结果和图见[快速入门第 4 节](../getting-started.md#4-链上每一步的结果)）；`work/` 下没有 `HPK-Si-PiN` 时就地运行 `examples/HPK-Si-PiN/`，结果存在 `examples/HPK-Si-PiN/` 下：

```bash
raser signal HPK-Si-PiN
```

在 `config.json` 的 `deposit` 段里设置 `source` 或在命令行用 `--set` 切换信号源（例如换为 $\alpha$ 源 `decay/Am241`）：

```bash
raser signal HPK-Si-PiN --set deposit.source=decay/Am241
```

用 `--scan` 扫描偏压、扫描源的能量或扫描激光脉冲能量与波长都在 `signal` 里做；当激光相对器件的位置作为扫描轴时，改用 [`tct`](tct.md)：

```bash
raser signal HPK-Si-PiN --scan field.voltage=100,200
```

按 [架构总纲](../architecture.md#project) 的分段格式，实验文件夹 `examples/HPK-Si-PiN/signal/config.json` 按环节分段记录配置。下面只摘和本页有关的段；`examples/HPK-Si-PiN/signal/config.json` 里八段都写全。

```json
{
  "workflow": "signal",
  "device": "HPK-Si-PiN",
  "field": {
    "voltage": 200.0,
    "irradiation_flux": null
  },
  "deposit": {
    "source": "decay/Sr90",
    "g4setup": "device_alone",
    "events_per_job": 200,
    "fano": true,
    "plots": 100
  },
  "current": {
    "plots": 100
  },
  "readout": {
    "amplifier": "SantaCruz+Gali52+Termination50",
    "sheet_resistance": null
  },
  "reconstruction": {
    "threshold": 10.0,
    "amplitude_threshold": 10.0,
    "fractions": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9],
    "edge": null
  }
}
```

使用者在 `signal` 中能设的配置键如下表（`digitizer`、`trigger` 等各段其余设置见 [仿真链与环节入口（`stages`）](../stages/README.md)）。“示例里的值”是 `examples/HPK-Si-PiN/signal/config.json` 写的值；`config.json` 缺了要用的键时报错，指出缺的“段.键”。

| 段.键 | 示例里的值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `field.voltage` | `200.0`（写 `null` 时取器件文件里的偏压） | $\text{V}$ | 被测器件反向偏置电压 |
| `field.irradiation_flux` | `null`（取器件文件里的辐照注量，器件文件没有辐照块时为 `0`） | $\text{cm}^{-2}$ | 被测器件辐照注量（$1\ \text{MeV}$ 中子等效注量） |
| `deposit.source` | `"decay/Sr90"` | 无 | 放射源或束流组件名称或路径 |
| `deposit.g4setup` | `"device_alone"` | 无 | Geant4 装置组件名称或路径 |
| `deposit.events_per_job` | `200` | 事例 | 每作业需记录的有效沉积事例数（与 `deposit.generated_per_job` 互斥） |
| `deposit.generated_per_job` | `null`（不用） | 事例 | 每作业由源生成的总事例数（与 `deposit.events_per_job` 互斥） |
| `deposit.generated_limit` | `10000000` | 事例 | 为录满 `events_per_job` 允许生成的最大源事例数上限 |
| `deposit.edep_min` | `null`（不设下限） | $\text{MeV}$ | 记录事例在器件内总沉积能量下限 |
| `deposit.edep_max` | `null`（不设上限） | $\text{MeV}$ | 记录事例在器件内总沉积能量上限 |
| `deposit.fano` | `true` | 无 | 电离对数转化是否开启 Fano 涨落抽样 |
| `deposit.plots` | `100` | 事例 | 每作业画 Geant4 几何与径迹图的前若干个记录事例数 |
| `current.plots` | `100` | 事例 | 每作业画载流子漂移路径图与电流图的前若干个记录事例数 |
| `readout.amplifier` | `"SantaCruz+Gali52+Termination50"` | 无 | 以 `+` 连接的前端放大器与终端负载组件链 |
| `readout.sheet_resistance` | `null`（取器件文件里阻性层的方块电阻） | $\Omega$ | 覆盖含 `resistive_layer` 器件的阻性层方阻 |
| `reconstruction.threshold` | `10.0` | $\text{mV}$ | 提取 `ToA`、`ToT`、`CoG`、`area` 及邻近电极入簇的过阈阈值 |
| `reconstruction.amplitude_threshold` | `10.0` | $\text{mV}$ | 团簇种子通道的脉冲幅度阈值；在 `trigger` 记录的事例里找到种子的记为 `selected`（事例记不记录由 `trigger` 按触发条件决定） |
| `reconstruction.fractions` | `[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]` | 无量纲 | 恒比定时（`CFD`）的幅度比例列表，每项须位于 `(0, 1)` 开区间内 |
| `reconstruction.edge` | `null`（沿用 `readout` 写出的 `pulse_edge`） | 无 | 阈值作用的脉冲边沿方向，可选 `"rising"` 或 `"falling"` |

其余参数（Geant4 世界默认半边长 `WORLD_HALF_SIDE = 25000 um`、材料平均电离能 `PAIR_ENERGY_EV` 与 Fano 因子 `FANO_FACTOR`、漂移时间窗与时间步长档位 `t_bin`/`delta_t`、热扩散开关 `diffusion = True`、`ngspice` 频域噪声起始频率 `1e3 Hz` 与温度 `27 °C`、保存波形通道最小摆幅比 `PART_EDGE = 1e-3`、重建基线点数 `BASELINE_POINTS = 200`、截断高斯拟合初窗 `median ± 8 * MAD`、最少样本数 `MINIMUM_EVENTS = 20` 与最大迭代轮数 `ROUNDS = 6`）全部写死在代码里。

## 输出

结果存放在被测器件 project 下的 `<project>/signal/`（上例就地运行在 `examples/HPK-Si-PiN/signal/`，自建 project 在 `work/<器件>/signal/`），存放结构见 [架构总纲](../architecture.md#结果)：底层按各环节输入指纹存入 `<project>/signal/nodes/<环节>/<节点号>/`（内含该环节输出文件、本环节图像与 `node.json`；`deposit` 到 `reconstruction` 每个作业一个节点，`analysis` 每个扫描点一个节点），上层在 `<project>/signal/points/<点名>/<环节>/<作业号>` 生成软链接视图（`points/<点名>/field`、`points/<点名>/analysis` 各是一个软链接）并在 `<project>/signal/points.json` 记录参数表，跨点统计与趋势图存放在 `<project>/signal/analysis/` 下，器件共享场节点存放在 `<project>/field/<节点号>/` 下。

### 数据文件

| 路径 | 写出环节 | 内容与主要字段 | 单位 |
| --- | --- | --- | --- |
| `nodes/deposit/<节点号>/deposit.h5` | [`deposit`](../stages/deposit.md) | 沉积步数据：属性 `generated_events`、`recorded_events`、`generated_fraction`、`edep_min`/`edep_max`；数据集 `event`、`count`、`detector`、`x`/`y`/`z`、`t`、`e`、`pairs` | 坐标 $\mu\text{m}$，时间 $\text{s}$，能量 $\text{MeV}$，`pairs` 为对 |
| `nodes/current/<节点号>/current.h5` | [`current`](../stages/current.md) | 感应电流与净电荷：属性 `electrodes`、`dt`；数据集 `event`、`t0`、`count`、`pairs`、`sensitive_pairs`、`carriers_without_field`、`charge`、`stored`、`index`、`current` | `dt`、`t0` 为 $\text{s}$，`charge` 为 $\text{C}$，`current` 为 $\text{A}$ |
| `nodes/readout/<节点号>/readout.h5` | [`readout`](../stages/readout.md) | 前端读出电压波形：属性 `electrodes`、`dt`、`pulse_edge`、`device_circuit`；数据集 `event`、`t0`、`count`、`stored`、`index`、`voltage` | `dt`、`t0` 为 $\text{s}$，`voltage` 为 $\text{V}$ |
| `nodes/digitizer/<节点号>/digitizer.h5` | [`digitizer`](../stages/digitizer.md) | 数字化量化码波形：属性 `electrodes`、`sampling_period`、`lsb_V`、`offset_V`、`bits`、`pulse_edge`、`device`；数据集 `event`、`t0`、`count`、`stored`、`index`、`clipped`、`code`（`int16`） | `sampling_period`、`t0` 为 $\text{s}$，`lsb_V`、`offset_V` 为 $\text{V}$，`bits` 为位，`code` 无量纲 |
| `nodes/trigger/<节点号>/trigger.h5` | [`trigger`](../stages/trigger.md) | 触发记录事例：数据集 `event`（`int64`，被记录事例的事例号） | 无量纲 |
| `nodes/reconstruction/<节点号>/reconstruction.h5` | [`reconstruction`](../stages/reconstruction.md) | 重建事件特征表：属性 `electrodes`、`threshold`、`amplitude_threshold`、`fractions`、`edge`；数据集 `event`、`selected`、`cluster_size`、`cluster_center`、`traced`、`baseline`、`noise`、`amplitude`、`above`、`ToA`、`ToT`、`CoG`、`area`、`CFD` | 电压与阈值 $\text{V}$，时间 $\text{s}$，面积 $\text{V}\cdot\text{s}$ |
| `nodes/analysis/<节点号>/result.json`（视图 `points/<点名>/analysis/result.json`） | [`analysis`](../stages/analysis.md) | 单扫描点汇总：含 `reconstruction` 设置、`collection`（`events`、`mean`、`mean_error`、`spread`）和 `timing`（`events`、`selected`、`polarity` 及 `ToA`、`CoG`、`CFD*` 的 `mean`、`sigma`、`sigma_error`、`sigma68`、`window`） | 阈值 $\text{mV}$，效率无量纲，时间与分辨 $\text{s}$ |
| `nodes/analysis/<节点号>/events.h5`（视图 `points/<点名>/analysis/events.h5`） | [`analysis`](../stages/analysis.md) | 单扫描点全部 `selected` 事例的一维数据集：`job`、`event`、`ToA`、`ToT`、`amplitude`、`baseline`、`noise`、`truth`、`CoG`、`CFD<percent>` | 电压 $\text{V}$，时间 $\text{s}$ |
| `analysis/points.json` | [`analysis`](../stages/analysis.md) | 多扫描点（已完成点数 $> 1$）对比表：每点一行，含 `"point"`、扫描键值、`"events"`、`"efficiency"`、`"efficiency_error"`、`"selected"` 及各定时通道的 `"sigma68"`、`"sigma"`、`"sigma_error"` | 效率无量纲，时间分辨 $\text{s}$ |

### 图像文件

| 路径 | 写出环节 | 内容 | 坐标与物理量单位 |
| --- | --- | --- | --- |
| `nodes/deposit/<节点号>/plots/g4_geometry.png` | [`deposit`](../stages/deposit.md) | `deposit.plots > 0` 且使用 Geant4 源时离屏绘出的装置几何与前 `deposit.plots` 个记录事例径迹图 | 空间尺寸 $\mu\text{m}$ |
| `nodes/current/<节点号>/plots/event_<event>/<det_model>_drift_path.pdf`, `.root` | [`current`](../stages/current.md) | 前 `current.plots` 个记录事例的三维器件边界与载流子漂移轨迹图（上）及 $x$-$z$ 平面投影图（下） | 空间轴 $\mu\text{m}$ |
| `nodes/current/<节点号>/plots/event_<event>/No_<k>electrode_basic_infor.pdf`, `.root` | [`current`](../stages/current.md) | 前 `current.plots` 个记录事例中非零电流电极 $k$ 的 `electron`、`hole`、`total`（及雪崩增益）感应电流波形 | 横轴 `Time [s]`，纵轴 `Current [A]` |
| `nodes/current/<节点号>/plots/event_<event>/cce.pdf`, `.root` | [`current`](../stages/current.md) | 条形（`strip`）或像素（`pixel`）器件在前 `current.plots` 个记录事例中各电极收集到的电子数分布 | 电极编号（无量纲），收集电子数（个） |
| `nodes/analysis/<节点号>/efficiency.png`（视图 `points/<点名>/analysis/efficiency.png`） | [`analysis`](../stages/analysis.md) | 扫描点 `current` 节点全部事例（事例数 $\ge 2$）的电荷收集效率 `60` 箱直方图，虚线标出均值 | 横轴无量纲效率，纵轴 `events` |
| `nodes/analysis/<节点号>/amplitude.png`（视图 `points/<点名>/analysis/amplitude.png`） | [`analysis`](../stages/analysis.md) | 扫描点全部 `selected` 事例基线以上脉冲幅度的 `60` 箱直方图，虚线标出 `amplitude_threshold` | 横轴 `amplitude above the baseline [mV]`，纵轴 `events` |
| `nodes/analysis/<节点号>/time_difference.png`（视图 `points/<点名>/analysis/time_difference.png`） | [`analysis`](../stages/analysis.md) | `3 × 4` 子图展示 `ToA`、`CoG` 与各 `CFD*` 通道的 `time - truth` 分布（`mean ± 8 * sigma` 内 `64` 箱）、末轮拟合窗口阴影与截断高斯拟合曲线 | 横轴 `<通道> - truth [ps]`，纵轴事例数 |
| `nodes/analysis/<节点号>/resolution_of_fraction.png`（视图 `points/<点名>/analysis/resolution_of_fraction.png`） | [`analysis`](../stages/analysis.md) | 各 `CFD*` 通道的时间分辨 `sigma`（带误差棒）与 `sigma68` 随恒比分数变化的曲线 | 横轴 `fraction of the CFD`（无量纲），纵轴 `width of time - truth [ps]` |
| `analysis/points.png` | [`analysis`](../stages/analysis.md) | 单一数值扫描轴下多扫描点的电荷收集效率（左）与各 `CFD*` 通道时间分辨 `sigma`（右）随扫描变量的变化曲线 | 横轴为扫描变量，左纵轴无量纲效率，右纵轴 `sigma of time - truth [ps]` |
