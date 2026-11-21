# CEPC 快速亮度监测器（`apps/cflm`）

`cflm`（CEPC Fast Luminosity Monitor，CEPC 快速亮度监测器，`raser_app` 包）模拟对撞机束团中的丢失电子撞击铜束流管后，在管外壁两侧 `24` 块探测焊盘（pad）中留下的信号响应。它以单块探测焊盘器件（Si 或 4H-SiC）为主体，读取 [探测器组件（`components/device`）](../components/device.md)、包内铜束流管与丢失电子配置 `cflm_p1.json` 以及 [前端读出电路组件（`components/readout`）](../components/readout.md)，先由专用 [`deposit`](../stages/deposit.md) 片运行 Geant4 一次算出全部 `24` 块焊盘的能量沉积，再共用同一个 [`field`](../stages/field.md) 共享场，按 [`stages/chain`](../stages/README.md) 的多位置展开机制为 `24` 个焊盘位置 `<pos>`（`I_-3_0` 至 `II_2_1`）分别执行 [`current`](../stages/current.md)（`current.<pos>`）、[`readout`](../stages/readout.md)（`readout.<pos>`）、[`digitizer`](../stages/digitizer.md)、[`trigger`](../stages/trigger.md)、[`reconstruction`](../stages/reconstruction.md)（`reconstruction.<pos>`）与 [`analysis`](../stages/analysis.md)，输出各焊盘上的感应电流、读出电压波形与重建特征表。

## 装置与通用范式

### 通用做法与坐标变换

在环形正负电子对撞机（CEPC）中，对撞区附近的辐射巴巴散射或束流损失会产生偏离束流包络的高能丢失电子。这些丢失电子以小掠射角撞击铜束流管内壁并在管壁中产生电磁簇射，次级正负电子与 $\gamma$ 光子穿出铜管外壁。快速亮度监测器（CFLM）在铜束流管外壁左右两侧对称贴装快速耐辐照半导体探测焊盘阵列（如 4H-SiC PiN 二极管），逐束团测量两侧各焊盘的信号脉冲幅度与到达时刻，从而实时监测对撞亮度与束流损失空间分布。

在 RASER 的 `src/raser/apps/cflm/cflm_p1.py`（第 194–214 行）与 `deposits.py`（第 23–37 行）中，铜束流管外壁两侧共排布 `24` 块尺寸为 $l_x \times l_y \times l_z$（单位 $\mu\text{m}$）的探测焊盘，位置编号为 `<side>_<i>_<j>`。第 `(side, i, j)` 块焊盘中心在束流管全局坐标系（单位 $\mu\text{m}$）中的位置 $(x_{\text{pad}}, y_{\text{pad}}, z_{\text{pad}})$ 为：

$$x_{\text{pad}} = s_{\text{side}}\!\left(1000\,R_{\max} + \frac{l_z}{2}\right), \qquad y_{\text{pad}} = (i + 0.5)\,l_x, \qquad z_{\text{pad}} = 1000\,z_{\text{from}} + (j + 0.5)\,l_y \tag{1}$$

焊盘逻辑体绕全局 $Z$ 轴旋转 $3\pi/2\ \text{rad}$（$270^\circ$）后，紧贴铜管外壁 $|X| = 1000\,R_{\max}$ 放置。Geant4 记录的全局步起点 $(X, Y, Z)$（单位 $\mu\text{m}$）通过 `pad_frame` 变换为该焊盘局部坐标系 $(x, y, z)$（单位 $\mu\text{m}$）：

$$x = \frac{l_x}{2} - Y + (i + 0.5)\,l_x, \qquad y = \frac{l_y}{2} + Z - \bigl(1000\,z_{\text{from}} + (j + 0.5)\,l_y\bigr), \qquad z = s_{\text{side}}\,X - 1000\,R_{\max} \tag{2}$$

其中：

- $\text{side} \in \{\text{"I"}, \text{"II"}\}$：束流管两侧标识，符号因子 $s_{\text{side}}$ 在 `"I"` 侧（$-x$ 侧）取 $-1$、在 `"II"` 侧（$+x$ 侧）取 $+1$；
- $i \in \{-3, -2, -1, 0, 1, 2\}$：焊盘沿竖直方向（全局 $y$ 轴）的 `6` 行下标 `pixelAreaYIndex`（无量纲）；
- $j \in \{0, 1\}$：焊盘沿束流方向（全局 $z$ 轴）的 `2` 列下标 `pixelAreaZIndex`（无量纲）；
- $R_{\max}$：铜束流管外半径 `pipe.Rmax`，$\text{mm}$（默认 $31\ \text{mm}$，乘以 $1000$ 换算为 $31000\ \mu\text{m}$）；
- $z_{\text{from}}$：焊盘阵列沿束流方向的起始 $z$ 坐标 `pads_from_z_mm`，$\text{mm}$（默认 $225\ \text{mm}$，乘以 $1000$ 换算为 $225000\ \mu\text{m}$）；
- $l_x, l_y, l_z$：单块焊盘器件（`Detector`）的三维全尺寸，$\mu\text{m}$；在 `cflmDetectorConstruction.pads` 中，`G4Box` 半尺寸定义为 $(l_x/2,\, l_z/2,\, l_y/2)$ 并绕全局 $Z$ 轴旋转 $3\pi/2\ \text{rad}$，使焊盘的 $l_x$ 沿全局 $y$ 方向、$l_y$ 沿全局 $z$（束流）方向、厚度 $l_z$ 沿全局 $\pm x$（垂直管壁向外）方向；
- $(X, Y, Z)$：Geant4 步起点 `point_in` 在束流管全局坐标系中的位置，$\mu\text{m}$；
- $(x, y, z)$：写入 `deposit_<job>.h5` 的焊盘局部坐标，$\mu\text{m}$，其中 $x \in [0, l_x]$、$y \in [0, l_y]$，深度 $z \in [0, l_z]$ 从紧贴铜管外壁的入射面（$z = 0$）指向焊盘内部。

式 (1) 由 `cflmDetectorConstruction.pads`（`src/raser/apps/cflm/cflm_p1.py:194`）实现，式 (2) 由 `pad_frame`（`src/raser/apps/cflm/deposits.py:23`）实现。`cflm` 采用与 4H-SiC PIN 时间分辨研究相同的 UCSC（`SantaCruz`）加宽带放大器读出链，见文献 [1]（T. Yang et al., “Time Resolution of the 4H-SiC PIN Detector”, *Front. Phys.* 10 (2022) 718071, doi:10.3389/fphy.2022.718071）。

### 铜束流管、24 块焊盘与丢失电子配置（`cflm_p1.json`）

`src/raser/apps/cflm/cflm_p1.json` 与 `cflm_p1.py` 定义了 Geant4 束流管几何与丢失电子粒子枪参数：

- **世界与铜束流管（`world`、`pipe`、`vacuum`）**：
  - 世界立方体 `world`：材料 `"G4_AIR"`，半尺寸为 $2000\ \text{mm} \times 2000\ \text{mm} \times 2000\ \text{mm}$；
  - 铜束流管 `pipe`：`G4Tubs` 圆柱管，材料 `"G4_Cu"`，内半径 `Rmin = 28` $\text{mm}$，外半径 `Rmax = 31` $\text{mm}$（管壁厚 $3\ \text{mm}$），全长 `Pipe_Z = 700` $\text{mm}$（半长 $350\ \text{mm}$），起始方位角 `PipeSphi = 0` $\text{deg}$、张角 `PipeDphi = 360` $\text{deg}$，中心坐标 `[0, 0, 250]` $\text{mm}$（沿束流方向覆盖 $z \in [-100, 600]\ \text{mm}$）；
  - 管内真空 `vacuum`：`G4Tubs` 圆柱，材料 `"G4_Galactic"`，内半径 `VACmin = 0` $\text{mm}$，外半径 `VACmax = 28` $\text{mm}$，全长 `VAC_Z = 700` $\text{mm}$，中心坐标 `[0, 0, 250]` $\text{mm}$。
- **24 块探测焊盘（`detector_<side>_<i>_<j>`）**：两侧（`I` 在 $x \le -31\ \text{mm}$，`II` 在 $x \ge +31\ \text{mm}$）各排 $6\text{ 行} \times 2\text{ 列} = 12$ 块焊盘，共 `24` 块，沿束流方向从 `pads_from_z_mm = 225` $\text{mm}$ 开始排布。`pad_material` 仅支持器件材料 `material == "Si"`（取 `"G4_Si"`）或 `"SiC"`（按密度 $3.2\ \text{g/cm}^3$、Si 与 C 原子百分比 $50\% : 50\%$ 构建 `G4Material`；传入其他材料抛出 `ValueError`），焊盘内最大步长 `maxStep = 2` $\mu\text{m}$。
- **丢失电子粒子枪（`cflmPrimaryGeneratorAction`）**：每次运行模拟 `BeamOn = 1` 个束团（事例），每个束团通过 `G4ParticleGun` 同时发射 `NumofGun = 3` 个丢失电子（`par_type = "e-"`），3 个丢失电子的动能 `par_energy`（$\text{GeV}$）、起始位置 `par_in`（$\text{mm}$）与动量方向向量 `par_direct`（无量纲方向分量）如下表：

| 电子序号 | 动能 `par_energy`（$\text{GeV}$） | 起始坐标 `par_in` $[X_0, Y_0, Z_0]$（$\text{mm}$） | 动量方向向量 `par_direct` $[d_x, d_y, d_z]$ |
| --- | --- | --- | --- |
| `0` | `21.906` | `[27.913, -2.7834, 98.2917]` | `[0.0321, -0.0023, 21.906]` |
| `1` | `25.9726` | `[-27.893, 2.647, 108.2917]` | `[-0.0483, 0.003, 25.9725]` |
| `2` | `24.7832` | `[27.8585, 2.8364, 78.2917]` | `[0.0434, 0.003, 24.7832]` |

局限：`cflm_p1.py` 的 `RecordDetector` 仅记录每个沉积步的步首位置 `point_in` 与沉积能量 `edep`，不记录 Geant4 全局时刻，因此 `deposits.py` 将所有沉积步的时刻 `t` 固定写入 `0.0 s`，不反映束团内不同电子及次级簇射粒子到达不同焊盘的飞行时间差；`cflm_p1.json` 固定从包内路径读取，未接入 `--g4setup` 或 `source` 命令行选项；`raser analysis` 当前只读取无位置后缀的单位置文件，尚不能直接汇总 `cflm` 带 `.<pos>` 后缀的 24 路输出。

### 代码执行步骤与内置常数

`cflm` 通过 `DEVICES = {"pad": (None, list(PADS))}` 和 `chain.expand(DEVICES, deposit=_deposits)`（`src/raser/apps/cflm/__init__.py:15-28`）将单作业展开为 `1` 片 `deposit`、`1` 片共享 `field` 以及 `24` 个焊盘位置各自的 `current.<pos>`、`readout.<pos>`、`reconstruction.<pos>`（共 `74` 个切片），按以下顺序执行：

1. **模拟束团丢失电子并写出 24 块焊盘沉积（`deposit` 片，`deposits.deposits`）**：构造单焊盘 `Detector`，读取 `apps/cflm/cflm_p1.json`，调用 `cflm_p1.simulate_bunches(g4_dic, seed, my_d)` 运行 Geant4 `FTFP_BERT` 物理列表与 `G4StepLimiterPhysics`。在 `bunch_deposits` 中遍历每个束团和全部 `24` 块焊盘，跳过 `energy <= 0` 的占位步（无沉积焊盘在 `simulate_bunches` 中填 `[[0, 0, 0]]` 和 `[0]`），对其余有效步用式 (2) 的 `pad_frame` 转为焊盘局部坐标 $(x, y, z)$，将 `detector` 记为 `<side>_<i>_<j>`、时刻 `t` 记为 `0.0` $\text{s}$，调用 `ionized_pairs(event, my_d.material)`（默认 `fano=True`）抽样电子-空穴对数 `pairs`，写入 `batch/deposit_<job>.h5`。若所有束团在 24 块焊盘中均无有效沉积（`not found.events`），抛出 `Ended` 提前结束作业。
2. **定位单焊盘共享场（`field` 片）**：定位（未就绪时自动调用 `raser field` 求解）单焊盘器件在 `work/<det_name>/field/` 下的电场、权重场与等效电路参数，由全部 24 个焊盘位置共用。
3. **24 路载流子漂移（`current.<pos>` 片）**：对每个位置 `<pos>`（`I_-3_0` 至 `II_2_1`），先检查 `deposit_<job>.h5` 中是否存在 `detector == <pos>` 的沉积步；若该焊盘在本作业无沉积，立即返回 `{"events": 0}` 写入 `batch/current.<pos>_<job>.done` 且不写 `.h5` 文件；若有沉积，调用 `write_induced_currents(..., detector=position)` 仅漂移属于该焊盘的沉积步，写出 `batch/current.<pos>_<job>.h5`（当 `current.plots > 0` 时在 `plots/job_<job>_<pos>/event_<event>/` 下绘图）。
4. **24 路电子学读出与事件重建（`readout.<pos>`、`reconstruction.<pos>` 片）**：对每个位置 `<pos>`，若上游缺少对应的 `.h5` 文件，直接返回 `{"events": 0}` 写入 `.done`；否则依次调用 `ngspice` 求解前端放大器链输出电压波形写出 `batch/readout.<pos>_<job>.h5`，再扣除前 `200` 点基线提取幅度与定时特征写出 `batch/reconstruction.<pos>_<job>.h5`。

此外，`src/raser/apps/cflm/` 下还包含一组独立于 `raser cflm` 仿真链的次级粒子分布辅助脚本：

- `cflm_spd.py`（读取 `cflm_spd.json`：世界半边长 $6000\ \text{mm}$，铜管全长 `Pipe_Z = 6000` $\text{mm}$、中心 $z = 2000\ \text{mm}$，步长上限 $1\ \text{mm}$）：在无焊盘情况下记录从铜束流管穿出 $x = -31\ \text{mm}$ 与 $x = +31\ \text{mm}$ 平面的次级粒子名称与 $(z, y)$ 交点坐标，写出 `<PosBaseName>_nx.txt` 与 `<PosBaseName>_px.txt`；
- `data_file.py`、`p1_sample.py`、`spd_dis.py`、`spd_plot.py`：`data_file.py` 读 `lossposition_CEPC.xlsx` 并写出 `src/raser/apps/cflm/input/datafile_p1.root`（输入目录不在仓库中），其余脚本读这个 ROOT 文件或 `SecondaryParticle_*_{nx,px}.txt`，抽样泊松击中数或批量改写 `cflm_spd.json` 调用 `cflm_spd.main()` 并绘制次级 $\gamma$ 与 $e^-$ 的空间分布图。

`cflm` 中的内置常数如下表：

| 常数名或固定项 | 取值 | 单位 | 定义位置与含义 |
| --- | --- | --- | --- |
| `PADS` | `24` 个位置（`I_-3_0` 至 `II_2_1`） | 个 | `src/raser/apps/cflm/__init__.py:15`，两侧（`I`、`II`）$\times$ `6` 行（`i = -3..2`）$\times$ `2` 列（`j = 0..1`）焊盘位置元组 |
| 展开总片数 | `74`（`1` `deposit` + `1` `field` + `24 × 3`） | 片 | `src/raser/apps/cflm/__init__.py:27`，`chain.expand` 为 24 个焊盘位置展开的作业总片数 |
| 世界立方体半边长 | `2000`（`cflm_p1.py`）；`6000`（`cflm_spd.py`） | $\text{mm}$ | `src/raser/apps/cflm/cflm_p1.py:118-121`、`cflm_spd.py:43-46`，Geant4 世界体半尺寸 |
| 束流管与焊盘旋转角 | `3 * pi / 2`（`270`） | $\text{rad}$（$\text{deg}$） | `src/raser/apps/cflm/cflm_p1.py:98-99`，将焊盘局部坐标旋转贴合铜管两侧外壁的绕 $Z$ 轴旋转角 |
| Geant4 `"SiC"` 密度与配比 | `3.2`，`50 : 50` | $\text{g/cm}^3$, `%` | `src/raser/apps/cflm/cflm_p1.py:220-222`，构建碳化硅焊盘材料时的固定密度与硅、碳原子百分比 |
| 沉积步固定时刻 `t` | `0.0` | $\text{s}$ | `src/raser/apps/cflm/deposits.py:59`，`cflm_p1` 沉积步未携带时间戳时写入 `deposit_<job>.h5` 的固定时刻 |

## 用到的环节和组件

### 环节

- [`deposit`](../stages/deposit.md)：由 `src/raser/apps/cflm/deposits.py` 替换标准单器件沉积，在铜束流管几何下模拟束团丢失电子簇射并把全部 24 块焊盘的沉积步写入同一个 `deposit_<job>.h5`。
- [`field`](../stages/field.md)：在 `work/<det_name>/field/` 下求解或复用单块焊盘器件的电场、权重场与等效电路参数，供全部 24 块焊盘共用。
- [`current`](../stages/current.md)：按位置展开为 24 片 `current.<pos>`，分别筛选各焊盘的沉积步并在共享场中漂移载流子，写出各焊盘的感应电流。
- [`readout`](../stages/readout.md)：按位置展开为 24 片 `readout.<pos>`，把有沉积焊盘的感应电流送入器件等效电路与前端放大器链，求解输出电压波形并叠加频域热噪声。
- [`digitizer`](../stages/digitizer.md)、[`trigger`](../stages/trigger.md)：按顶层设计对 24 路输出波形执行数字化采样量化与触发判选。
- [`reconstruction`](../stages/reconstruction.md)：按位置展开为 24 片 `reconstruction.<pos>`，从各焊盘读出波形中提取脉冲幅度、`ToA`、`ToT`、`CoG`、`area` 与 `CFD` 特征表。
- [`analysis`](../stages/analysis.md)：按顶层设计汇总各焊盘的击中率、收集电荷与时间响应。

### 组件

- [探测器组件（`components/device`）](../components/device.md)：提供单块探测焊盘的尺寸 `l_x`、`l_y`、`l_z`（$\mu\text{m}$）、材料 `material`（`"Si"` 或 `"SiC"`）、掺杂、偏压与温度定义（如 `NJU-PiN.json`、`HPK-Si-PiN.json`）。
- [能量沉积组件（`components/deposit`）](../components/deposit.md)：由包内 `src/raser/apps/cflm/cflm_p1.json` 定义铜束流管、真空与 3 个高能丢失电子参数。
- [前端读出电路组件（`components/readout`）](../components/readout.md)：提供以 `+` 串联的 SPICE 放大器级与终端负载子电路（默认 `SantaCruz+Gali52+Termination50`）。
- [数字化器组件（`components/digitizer`）](../components/digitizer.md) 与 [触发组件（`components/trigger`）](../components/trigger.md)：提供数字化采样量化与触发阈值定义。

## 跑法与配置

按顶层设计（[命令行接口](../cli.md#命令)），运行 `cflm` 应用或扫描偏压、前端放大器与阈值参数：

```bash
raser cflm
raser cflm NJU-PiN --scan field.voltage=-300,-500
```

按 [架构总纲](../architecture.md#project) 的分段格式，实验文件夹 `work/cflm/config.json` 的配置结构为：

```json
{
  "workflow": "cflm",
  "device": "NJU-PiN",
  "field": {
    "voltage": -500.0,
    "irradiation": null
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

使用者在 `cflm` 工作流中能设的配置键及 `cflm_p1.json` 中的装置键如下表（`src/raser/apps/cflm/__init__.py:29-49`、`cflm_p1.json:1-80`）：

| 段.键（代码键名） | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `field.voltage`（等同 `field.device.bias.voltage`） | 取器件文件 `bias.voltage` | $\text{V}$ | 24 块焊盘共用的反向偏置电压（命令行 `-vol`/`--voltage`） |
| `field.irradiation`（`irradiation`） | `None`（未给定时取器件 `irradiation.irradiation_flux`，无则为 `0`） | $\text{neq/cm}^2$ | 24 块焊盘共用的辐照注量（命令行 `-irr`/`--irradiation`） |
| `current.plots` | `0` | 束团 | 每个焊盘位置画载流子漂移路径图与电流图的前若干个有沉积束团数 |
| `readout.amplifier`（`amplifier`） | `"SantaCruz+Gali52+Termination50"` | 无 | 以 `+` 连接的前端放大器与终端负载组件链（命令行 `-amp`/`--amplifier`） |
| `readout.sheet_resistance`（`sheet_resistance`） | `None` | $\Omega$ | 覆盖含 `resistive_layer` 焊盘器件的阻性层方阻（命令行 `--sheet-resistance`） |
| `reconstruction.threshold`（`threshold`） | `10.0` | $\text{mV}$ | 提取 `ToA`、`ToT`、`CoG`、`area` 及邻近电极入簇的过阈阈值（命令行 `-threshold`） |
| `reconstruction.amplitude_threshold`（`amplitude_threshold`） | `10.0` | $\text{mV}$ | 找团簇种子的脉冲幅度阈值（事例记不记录由 `trigger` 判定）（命令行 `-amplitude_threshold`） |
| `reconstruction.fractions`（`fractions`） | `[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]` | 无量纲 | 恒比定时（`CFD`）的幅度比例列表，每项须位于 `(0, 1)` 开区间内 |
| `reconstruction.edge`（`edge`） | `None`（沿用 `readout` 写出的 `pulse_edge`） | 无 | 阈值作用的脉冲边沿方向，可选 `"rising"` 或 `"falling"`（命令行 `--edge`） |
| `pipe`, `vacuum`, `world`（`cflm_p1.json`） | `G4_Cu`（$R_{\min}=28$, $R_{\max}=31$, $Z=700\ \text{mm}$）, `G4_Galactic`, `"G4_AIR"` | $\text{mm}$, $\text{deg}$ | 铜束流管、管内真空圆柱与世界材料定义 |
| `pads_from_z_mm`（`cflm_p1.json`） | `225` | $\text{mm}$ | 24 块焊盘沿束流方向的起始 $z$ 坐标 |
| `BeamOn`, `NumofGun`（`cflm_p1.json`） | `1`, `3` | 束团, 粒子 | 每作业模拟的束团数与每束团同时发射的丢失电子数 |
| `par_type`, `par_energy`, `par_in`, `par_direct`, `maxStep`（`cflm_p1.json`） | `"e-"`, `[21.906, 25.9726, 24.7832]`, 3 组起点与方向, `2` | 无, $\text{GeV}$, $\text{mm}$, 无量纲, $\mu\text{m}$ | 丢失电子粒子类型、各粒子能量、起点坐标、动量方向与焊盘内最大步长 |

其余参数（24 个焊盘位置命名 `I_-3_0` 至 `II_2_1` 及 6 行 2 列索引范围、世界立方体半边长 `2000 mm`、绕 $Z$ 轴旋转角 $3\pi/2\ \text{rad}$、沉积步固定时刻 `0.0 s`、电离对数 Fano 抽样开关 `fano = True`、漂移时间窗与时间步长档位、`ngspice` 噪声分析频率范围与 `27 °C` 温度、重建基线点数 `200`）全部写死在代码里。

## 输出

按 [架构总纲](../architecture.md#结果) 的设计，应用类的结果存放在 `work/cflm/` 下（分 `nodes/<环节>/<节点号>/`、`points/<点名>/<环节>`、`points.json` 和 `work/cflm/analysis/`）。

### 数据与图像文件

`<pos>` 取 `I_-3_0` 至 `II_2_1` 共 `24` 个焊盘位置名：

| 文件名 | 写出片 / 脚本 | 内容与主要字段 | 单位 |
| --- | --- | --- | --- |
| `batch/deposit_<job>.h5` | `deposit`（`apps/cflm/deposits.py`） | 单次 Geant4 运行记录的全部 24 块焊盘能量沉积步：属性 `generated_events`（等于 `BeamOn`）、`recorded_events`、`generated_fraction`；数据集 `event`、`count`、`detector`（取 `<side>_<i>_<j>`）、焊盘局部坐标 `x`/`y`/`z`、固定时刻 `t = 0.0`、`e`、`pairs` | 坐标 $\mu\text{m}$，时间 $\text{s}$，能量 $\text{MeV}$，`pairs` 为对 |
| `batch/current.<pos>_<job>.h5` | [`current.<pos>`](../stages/current.md) | 焊盘 `<pos>` 在有沉积束团中的感应电流与净电荷（该焊盘无沉积时不写 `.h5`，仅在 `current.<pos>_<job>.done` 中写 `{"events": 0}`）：属性 `electrodes`、`dt`；数据集 `event`、`t0`、`count`、`pairs`、`sensitive_pairs`、`carriers_without_field`、`charge`、`stored`、`index`、`current` | `dt`、`t0` 为 $\text{s}$，`charge` 为 $\text{C}$，`current` 为 $\text{A}$ |
| `batch/readout.<pos>_<job>.h5` | [`readout.<pos>`](../stages/readout.md) | 焊盘 `<pos>` 经器件等效电路与前端放大器链求解并叠加频域热噪声后的输出电压波形（无对应电流文件时不写 `.h5`，`.done` 记 `{"events": 0}`）：属性 `electrodes`、`dt`、`pulse_edge`、`device_circuit`；数据集 `event`、`t0`、`count`、`stored`、`index`、`voltage` | `dt`、`t0` 为 $\text{s}$，`voltage` 为 $\text{V}$ |
| `batch/reconstruction.<pos>_<job>.h5` | [`reconstruction.<pos>`](../stages/reconstruction.md) | 焊盘 `<pos>` 的重建事件特征表（无对应读出文件时不写 `.h5`，`.done` 记 `{"events": 0}`）：属性 `threshold`、`amplitude_threshold`、`fractions`、`edge`；数据集 `event`、`selected`、`cluster_size`、`cluster_center`、`traced`、`baseline`、`noise`、`amplitude`、`above`、`ToA`、`ToT`、`CoG`、`area`、`CFD` | 电压与阈值 $\text{V}$，时间 $\text{s}$，面积 $\text{V}\cdot\text{s}$ |
| `plots/job_<job>_<pos>/event_<event>/<det_model>_drift_path.pdf`, `.root` 与 `No_<k>electrode_basic_infor.pdf`, `.root` | [`current.<pos>`](../stages/current.md) | 当 `current.plots > 0` 时，为每个有沉积焊盘 `<pos>` 的前 `plots` 个束团绘制的三维/$x$-$z$ 载流子漂移路径图与电极感应电流波形图 | 空间坐标 $\mu\text{m}$，时间 `Time [s]`，电流 `Current [A]` |
| `<PosBaseName>_nx.txt`, `<PosBaseName>_px.txt` | 独立脚本 `cflm_spd.py` | 穿出铜束流管外壁 $x = -31\ \text{mm}$（`_nx`）与 $x = +31\ \text{mm}$（`_px`）平面的次级粒子列表，每行三列：`<粒子名> <z坐标> <y坐标>` | $z$、$y$ 坐标单位均为 $\text{mm}$ |
