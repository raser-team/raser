# 在线束流监测系统（`apps/bmos`）

`bmos`（Beam Monitor Online System，在线束流监测系统，`raser_app` 包）是 [`signal`](../bench/signal.md) 换用多粒子束团源 `bunch`（每个事例代表一个束团，同时发射 `3` 个 `80 MeV` 质子）并默认关闭逐事例绘图（`deposit.plots = 0`、`current.plots = 0`）的一份配置。它以束流路径上的监测器件为主体，读取 [探测器组件（`components/device`）](../components/device.md)、[能量沉积组件（`components/deposit`）](../components/deposit.md)、[前端读出电路组件（`components/readout`）](../components/readout.md)、[数字化器组件（`components/digitizer`）](../components/digitizer.md) 和 [触发组件（`components/trigger`）](../components/trigger.md)，依次走完 [`field`](../stages/field.md)、[`deposit`](../stages/deposit.md)、[`current`](../stages/current.md)、[`readout`](../stages/readout.md)、[`digitizer`](../stages/digitizer.md)、[`trigger`](../stages/trigger.md)、[`reconstruction`](../stages/reconstruction.md) 和 [`analysis`](../stages/analysis.md) 八个环节，输出束团在监测器件上产生的叠加电流脉冲、读出电压波形、电荷收集效率与时间分辨。

## 装置与通用范式

### 通用做法与物理定义

学术界在质子或重离子加速器束流线上做在线束流监测（Beam Monitor Online System）时，将耐辐照宽禁带半导体探测器（如 4H-SiC PiN 二极管 `NJU-PiN-bmos`）直接放置在束流路径上，逐束团（bunch）测量束团内多个带电粒子同时穿过探测器时叠加产生的瞬态感应电流脉冲与总收集电荷，从而在线监测每个束团的流强（粒子数）、到达时刻与脉冲幅度分布。

在 RASER 中，单个束团作为单个 Geant4 事例模拟。设一个束团同时发射 $M$ 个粒子，第 $m$ 个粒子及其次级产物在器件内留下的沉积步集合为 $\mathcal{S}_m$，第 $k$ 个沉积步转化的初始电子-空穴对数为 $N_{\text{pairs}, k}$，则单个束团在器件内产生的总初始电子-空穴对数 $N_{\text{bunch}}$ 与束团电荷收集效率 $\eta$ 为：

$$N_{\text{bunch}} = \sum_{m=1}^{M}\sum_{k \in \mathcal{S}_m} N_{\text{pairs}, k}, \qquad \eta = \frac{\left|\sum_{j} Q_{j}\right|}{N_{\text{bunch}}\,e_0} \tag{1}$$

其中：

- $M$：单个束团（单个事例）同时发射的初级粒子数，个（默认 `bunch.json` 中 $M = 3$）；
- $N_{\text{pairs}, k}$：第 $k$ 个沉积步由沉积能量 $E_k$（$\text{MeV}$）除以平均电离能 $\varepsilon_{\text{pair}}\times 10^{-6}$ 并经 Fano 抽样得到的电子-空穴对数，对；
- $N_{\text{bunch}}$：单束团在器件内产生的总初始电子-空穴对数（写入 `current_<job>.h5` 的 `pairs` 数据集），对；
- $Q_j$：第 $j$ 个读出电极在该束团全部载流子漂移过程中感应的带符号净电荷，$\text{C}$；
- $e_0$：元电荷，代码中常数 `ELEMENTARY_CHARGE` 取 $1.602176634\times 10^{-19}\ \text{C}$；
- $\eta$：单束团电荷收集效率（无量纲）。

式 (1) 由 [`core/deposit/ionization.py`](../core/deposit.md) 的 `ionized_pairs` 与 [`core/analysis/collection.py`](../core/analysis.md) 的 `collection_efficiency` 计算；束团到达时间差 $\Delta t = t_{\text{reco}} - t_{\text{truth}}$ 及截断高斯时间分辨拟合与 [`signal`](../bench/signal.md#通用做法与物理定义) 的式 (2) 完全一致。用碳化硅半导体探测器进行带电粒子束流监测的综述见文献 [1]（M. De Napoli, “SiC detectors: A review on the use of silicon carbide as radiation detection material”, *Front. Phys.* 10 (2022) 898833, doi:10.3389/fphy.2022.898833）。

### 束团源 `bunch` 与装置几何

`bmos` 默认使用 `device_alone` Geant4 装置（`src/raser/components/g4setup/device_alone.py`）和专属束团源 `bunch`（`src/raser_app/bmos/components/source/bunch.json`）：

- **Geant4 装置（`device_alone`）**：世界立方体材料为真空 `"G4_Galactic"`（默认半边长 `WORLD_HALF_SIDE = 25000` $\mu\text{m}$），监测器件逻辑体 `"Device"` 顶面中心位于原点 $(0, 0, 0)\ \mu\text{m}$、占据 $x \in [-l_x/2, l_x/2]$、$y \in [-l_y/2, l_y/2]$、$z \in [0, l_z]\ \mu\text{m}$，器件内最大步长 `maxstep = 2` $\mu\text{m}$；源基准位置 `at = [0, 0, -17000]` $\mu\text{m}$（顶面上方 $17\ \text{mm}$），瞄准点 `towards = [0, 0, 0]` $\mu\text{m}$，入射倾角 `angle = 0` $\text{degree}$。
- **束团源（`bunch.json`）**：源类型 `"kind": "beam"`，粒子种类 `"par_type": "proton"`（质子），单粒子动能 `"par_energy": 80` $\text{MeV}$，横向方向随机偏移半宽 `par_randx = 0`、`par_randy = 0` $\mu\text{m}$。`"particles"` 列表包含 `3` 个同时发射的质子项，相对于基准起点 `at` 和瞄准点 `towards` 的平移向量 `"offset"` 依次为：
  - 质子 1：`offset = [-1, 1, 0]` $\mu\text{m}$（从 `[-1, 1, -17000]` $\mu\text{m}$ 沿 $+z$ 射向 `[-1, 1, 0]` $\mu\text{m}$）；
  - 质子 2：`offset = [0, 1, 0]` $\mu\text{m}$（从 `[0, 1, -17000]` $\mu\text{m}$ 沿 $+z$ 射向 `[0, 1, 0]` $\mu\text{m}$）；
  - 质子 3：`offset = [1, 1, 0]` $\mu\text{m}$（从 `[1, 1, -17000]` $\mu\text{m}$ 沿 $+z$ 射向 `[1, 1, 0]` $\mu\text{m}$）。

  三个 $80\ \text{MeV}$ 质子在 $y = +1\ \mu\text{m}$ 平面内沿 $x$ 方向以 $1\ \mu\text{m}$ 间距并排同时射入器件。

局限：`bunch.json` 中同一束团的 `3` 个质子在完全相同的初始时刻（`0.0 s`）沿平行方向发射，不含真实加速器束团的纵向时间宽度（bunch length）与横向束斑高斯角散；`current` 环节将同一束团内 `3` 个质子产生的载流子团簇在静态外加电场中各自独立漂移并线性叠加感应电流，不计高密度径迹之间的等离子体与空间电荷互屏蔽效应。

### 代码执行步骤与内置常数

`bmos` 的工作流定义（`src/raser_app/bmos/__init__.py:11-28`）直接复用 `stages.chain` 的全部切片与执行函数，仅将 `defaults` 中的 `"source"` 覆盖为 `"bunch"`、`"plots"` 覆盖为 `0` 并挂载组件路径 `"raser_app/bmos"`：

1. **共享场检查与求解（`field`）**：定位或自动调用 `raser field` 求解监测器件在目标偏压 `voltage`（$\text{V}$）与辐照注量 `irradiation`（$\text{neq/cm}^2$）下的共享场。
2. **单束团多粒子Geant4沉积（`deposit`）**：`GeneralPrimaryGeneratorAction` 在每个 Geant4 事例中循环遍历 `bunch.json` 的 `particles` 列表，对每个粒子调用 `beam.GeneratePrimaryVertex(event)`（`beam` 取自 `shot["guns"]`），同时发射 `3` 个 `80 MeV` 质子；汇总整个束团在 `"Device"` 内的全部沉积步，当束团总沉积能量满足能量窗时记为 `1` 个有效束团事例，直至录满 `events_per_job`（默认 `1`）个束团并写入 `deposit_<job>.h5`。
3. **漂移、读出、重建与统计（`current`、`readout`、`reconstruction`、`analysis`）**：将同一束团的全部电子-空穴对团簇在求解场中漂移并累加为单条束团感应电流写入 `current_<job>.h5`（默认 `plots = 0` 不画单束团漂移图），随后经 [`readout`](../stages/readout.md)、[`reconstruction`](../stages/reconstruction.md) 和 [`analysis`](../stages/analysis.md) 求出束团输出电压波形、脉冲特征、电荷收集效率与时间分辨，步骤及内置常数（`WORLD_HALF_SIDE = 25000 um`、`GENERATED_LIMIT = 10000000`、`t_bin`/`delta_t`、`PART_EDGE = 1e-3`、`BASELINE_POINTS = 200`、`ELEMENTARY_CHARGE = 1.602176634e-19 C`、`MINIMUM_EVENTS = 20`、`ROUNDS = 6`）与 [`signal`](../bench/signal.md#代码执行步骤与内置常数) 完全相同。

## 用到的环节和组件

### 环节

- [`field`](../stages/field.md)、[`deposit`](../stages/deposit.md)、[`current`](../stages/current.md)、[`readout`](../stages/readout.md)、[`digitizer`](../stages/digitizer.md)、[`trigger`](../stages/trigger.md)、[`reconstruction`](../stages/reconstruction.md)、[`analysis`](../stages/analysis.md)：与 [`signal`](../bench/signal.md#用到的环节和组件) 完全相同，其中 [`deposit`](../stages/deposit.md) 每事例同时输运一个束团内的 `3` 个 `80 MeV` 质子，[`current`](../stages/current.md) 默认关闭逐束团绘图（`plots = 0`）。

### 组件

- [探测器组件（`components/device`）](../components/device.md)：提供在线束流监测器件定义（如专用的 4H-SiC PiN 器件 `NJU-PiN-bmos.json`，尺寸 $5000 \times 5000 \times 100\ \mu\text{m}$，默认偏压 `-500.0 V`）。
- [能量沉积组件（`components/deposit`）](../components/deposit.md)：提供默认多粒子束团源 `bunch.json`（`src/raser_app/bmos/components/source/bunch.json`）及默认 Geant4 装置 `device_alone.py`。
- [前端读出电路组件（`components/readout`）](../components/readout.md)、[数字化器组件（`components/digitizer`）](../components/digitizer.md)、[触发组件（`components/trigger`）](../components/trigger.md)：提供 SPICE 前端放大器链（默认 `SantaCruz+Gali52+Termination50`）、数字化采样量化与触发阈值定义。

## 跑法与配置

按顶层设计（[架构总纲](../architecture.md#实验是-python-类)、[命令行接口](../cli.md#命令)），运行 `bmos` 应用或用 `--set`、`--scan` 扫描偏压、器件与束流参数：

```bash
raser bmos
raser bmos --scan field.voltage=-300,-500
```

按 [架构总纲](../architecture.md#project) 的分段格式，实验文件夹 `work/bmos/config.json` 的配置结构为：

```json
{
  "workflow": "bmos",
  "device": "NJU-PiN-bmos",
  "field": {
    "voltage": -500.0,
    "irradiation": null
  },
  "deposit": {
    "source": "bunch",
    "g4setup": "device_alone",
    "events_per_job": 1,
    "fano": true,
    "plots": 0
  },
  "current": {
    "plots": 0
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

使用者在 `bmos` 中能设的配置键如下表（`src/raser_app/bmos/__init__.py:11-21` 与 `src/raser/stages/chain.py:14-106`）：

| 段.键（代码键名） | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `field.voltage`（等同 `field.device.bias.voltage`） | 取器件文件 `bias.voltage` | $\text{V}$ | 监测器件反向偏置电压（命令行 `-vol`/`--voltage`） |
| `field.irradiation`（`irradiation`） | `None`（未给定时取器件 `irradiation.irradiation_flux`，无则为 `0`） | $\text{neq/cm}^2$ | 监测器件辐照注量（命令行 `-irr`/`--irradiation`） |
| `deposit.source`（`source`） | `"bunch"` | 无 | 信号源组件名称或路径（命令行可选位置参数 `source`） |
| `deposit.g4setup`（`g4setup`） | `"device_alone"` | 无 | Geant4 装置组件名称或路径（命令行 `--g4setup`） |
| `deposit.events_per_job`（`events_per_job`） | `1` | 事例（束团） | 每作业需记录的有效沉积束团数（命令行 `-evt`/`--events-per-job`，与 `generated_per_job` 互斥） |
| `deposit.generated_per_job`（`generated_per_job`） | `None` | 事例（束团） | 每作业由源生成的总束团数（命令行 `-gen`/`--generated-per-job`，与 `events_per_job` 互斥） |
| `deposit.generated_limit`（`generated_limit`） | `None`（运行时取 `10000000`） | 事例（束团） | 为录满 `events_per_job` 允许生成的最大束团数上限（命令行 `--generated-limit`） |
| `deposit.edep_min`（`edep_min`） | `None` | $\text{MeV}$ | 记录束团在器件内总沉积能量下限（命令行 `--edep-min`） |
| `deposit.edep_max`（`edep_max`） | `None` | $\text{MeV}$ | 记录束团在器件内总沉积能量上限（命令行 `--edep-max`） |
| `deposit.fano`（`fano`） | `True` | 无 | 电离对数转化是否开启 Fano 涨落抽样 |
| `deposit.plots` | `0` | 事例（束团） | 每作业画 Geant4 几何与径迹图的前若干个记录束团数 |
| `current.plots` | `0` | 事例（束团） | 每作业画载流子漂移路径图与电流图的前若干个记录束团数 |
| `readout.amplifier`（`amplifier`） | `"SantaCruz+Gali52+Termination50"` | 无 | 以 `+` 连接的前端放大器与终端负载组件链（命令行 `-amp`/`--amplifier`） |
| `readout.sheet_resistance`（`sheet_resistance`） | `None` | $\Omega$ | 覆盖含 `resistive_layer` 器件的阻性层方阻（命令行 `--sheet-resistance`） |
| `reconstruction.threshold`（`threshold`） | `10.0` | $\text{mV}$ | 提取 `ToA`、`ToT`、`CoG`、`area` 及邻近电极入簇的过阈阈值（命令行 `-threshold`） |
| `reconstruction.amplitude_threshold`（`amplitude_threshold`） | `10.0` | $\text{mV}$ | 找团簇种子的脉冲幅度阈值（事例记不记录由 `trigger` 判定）（命令行 `-amplitude_threshold`） |
| `reconstruction.fractions`（`fractions`） | `[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]` | 无量纲 | 恒比定时（`CFD`）的幅度比例列表，每项须位于 `(0, 1)` 开区间内 |
| `reconstruction.edge`（`edge`） | `None`（沿用 `readout` 写出的 `pulse_edge`） | 无 | 阈值作用的脉冲边沿方向，可选 `"rising"` 或 `"falling"`（命令行 `--edge`） |

其余参数（Geant4 世界默认半边长 `25000 um`、默认最大生成束团数上限 `10000000`、材料平均电离能与 Fano 因子、漂移时间窗与时间步长档位、热扩散开关 `diffusion = True`、`ngspice` 噪声分析频率范围与 `27 °C` 温度、重建基线点数 `200`、截断高斯拟合最少样本数 `20` 与最大迭代轮数 `6`）全部写死在代码里。

## 输出

按 [架构总纲](../architecture.md#实验是-python-类) 与 [结果](../architecture.md#结果) 的设计，应用类的结果存放在 `work/bmos/` 下（底层节点在 `work/bmos/nodes/<环节>/<节点号>/`，按扫描点视图在 `work/bmos/points/<点名>/<环节>`，参数表为 `work/bmos/points.json`，跨点统计与趋势图在 `work/bmos/analysis/`）。

每个作业写出的数据文件（`deposit_<job>.h5`、`current_<job>.h5`、`readout_<job>.h5`、`reconstruction_<job>.h5`）以及 [`analysis`](../stages/analysis.md) 写出的统计结果（`result.json`、`events.h5`、`points.json`）和图像文件（`efficiency.png`、`amplitude.png`、`time_difference.png`、`resolution_of_fraction.png`、`points.png`，以及 `plots > 0` 时的 `g4_geometry.png`、`<det_model>_drift_path.pdf`/`.root`、`No_<k>electrode_basic_infor.pdf`/`.root`）的文件名、字段与单位同 [`signal`](../bench/signal.md#输出)，其中每个记录事例对应一个束团。
