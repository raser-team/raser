# 瞬态电流技术测试（`bench/tct`）

`tct`（Transient Current Technique，瞬态电流技术，`raser_bench` 包）以命令行给定的被测器件为主体，把固定激光相对器件的焦点位置作为扫描轴。它从 [探测器组件（`components/device`）](../components/device.md)、[能量沉积组件（`components/deposit`）](../components/deposit.md) 中的激光定义、[前端读出电路组件（`components/readout`）](../components/readout.md)、[数字化器组件（`components/digitizer`）](../components/digitizer.md) 和 [触发组件（`components/trigger`）](../components/trigger.md) 读入器件、激光与电子学配置，逐点移动激光相对器件的位置，在每个位置上走完与 [`signal`](signal.md) 相同的八个环节，输出各焦点位置下的初始载流子分布、感应电流波形、读出电压波形、数字波形、重建特征以及收集电荷和信号随位置变化的曲线。

## 装置与通用范式

### 通用做法与物理模型

学术界做瞬态电流技术（TCT）测量时，将聚焦皮秒或飞秒脉冲激光从半导体探测器的顶面（Top-TCT）、底面（Bottom-TCT）或抛光侧面（Edge-TCT）射入器件，通过三维精密平移台逐点改变激光焦点相对器件的坐标，记录不同空间位置激发的电子-空穴对在电场中漂移产生的瞬态感应电流波形与积分电荷，从而测出器件内部的电场剖面、耗尽层厚度、载流子漂移速度以及电荷收集随位置的变化。

在 RASER 中，激光焦点在器件坐标系 $[0, l_x] \times [0, l_y] \times [0, l_z]$（单位 $\mu\text{m}$）中的绝对坐标 $(x_{\text{focus}}, y_{\text{focus}}, z_{\text{focus}})$ 与高斯光束沿光路坐标 $s$（单位 $\mu\text{m}$）的光斑半径 $w(s)$ 为：

$$(x_{\text{focus}},\, y_{\text{focus}},\, z_{\text{focus}}) = \bigl(\text{fx\_rel}\cdot l_x,\; \text{fy\_rel}\cdot l_y,\; \text{fz\_rel}\cdot l_z\bigr) \tag{1}$$

$$w_0 = \frac{\text{FWHM}_{\text{sp}}}{\sqrt{2\ln 2}}, \qquad l_R = \frac{\pi w_0^2 n}{\lambda}, \qquad w^2(s) = w_0^2\!\left[1 + \left(\frac{s - s_{\text{focus}}}{l_R}\right)^2\right] \tag{2}$$

单光子吸收（`"SPA"`）与双光子吸收（`"TPA"`）在光路位置 $s$ 处单位长度（每米）经横截面积分产生的电子-空穴对线密度分别为：

$$\left(\frac{dN}{ds_{\text{m}}}\right)_{\text{SPA}} = \alpha\,\frac{E_{\text{pulse}}}{E_{\text{ph}}}\,\exp\!\left(-\alpha\,s \times 10^{-6}\right), \qquad E_{\text{ph}} = \frac{h c}{\lambda \times 10^{-6}} \tag{3}$$

$$\left(\frac{dN}{ds_{\text{m}}}\right)_{\text{TPA}} = \frac{\beta_2\,E_{\text{pulse}}^2\,\exp\!\left(-2\alpha\,s \times 10^{-6}\right)}{2\,E_{\text{ph}}\,\pi\,w^2(s)\times 10^{-12}}\sqrt{\frac{2\ln 2}{\pi}}\,\frac{1}{\text{FWHM}_t} \tag{4}$$

瞬时注入下漂移算出的第 $e$ 号电极第 $a$ 个时间箱感应电流 $I_{e,a}$（单位 $\text{A}$）与归一化高斯激光时间脉冲 $P(t)$ 离散卷积后，得到输出电流波形 $I^{\text{conv}}_{e,b}$：

$$P(t) = \frac{2\sqrt{\ln 2}}{\sqrt{\pi}\,\text{FWHM}_t}\exp\!\left(-\frac{4\ln 2\,t^2}{\text{FWHM}_t^2}\right), \qquad I^{\text{conv}}_{e, b} = \sum_{a=0}^{n_{\text{bin}}-1} I_{e, a}\,p_{a - b} \tag{5}$$

其中：

- $l_x, l_y, l_z$：被测器件沿 $x$、$y$、$z$ 方向的全尺寸，$\mu\text{m}$；
- $\text{fx\_rel}, \text{fy\_rel}, \text{fz\_rel}$：焦点相对器件尺寸的无量纲归一化坐标；
- $\text{FWHM}_{\text{sp}}$：焦点处高斯光斑的空间半高全宽 `spacial_FWHM`，$\mu\text{m}$；
- $w_0$、$w(s)$：焦点处光斑束腰半径与光路位置 $s$ 处的光斑半径，$\mu\text{m}$；
- $n$：器件材料在该激光波长下的折射率 `refractionIndex`（无量纲）；
- $\lambda$：激光波长，$\mu\text{m}$（由组件文件的 `wavelength` [$\text{nm}$] 乘以 $10^{-3}$ 换算）；
- $l_R$：介质内的瑞利长度 `l_Rayleigh`，$\mu\text{m}$（组件文件未显式给出时按式 (2) 计算）；
- $s_{\text{focus}}$：焦点沿光束传播方向距入射面的距离，$\mu\text{m}$；
- $\alpha$：线性（单光子）吸收系数 `alpha`，$\text{m}^{-1}$（组件文件未给出时：硅查 `raser/components/deposit/absorption/Si.txt` 对数插值并乘以 $100$ 换算，碳化硅按器件温度由 4H-SiC 间接吸收模型计算，见 [`core/deposit`](../core/deposit.md) 式 (7a)、(7b)）；
- $\beta_2$：双光子吸收系数 `beta_2`，$\text{m/W}$；
- $E_{\text{pulse}}$：单次激光脉冲能量 `pulse_energy`，$\text{J}$；$E_{\text{ph}}$ 为单光子能量，$\text{J}$（$h = 6.626\times 10^{-34}\ \text{J}\cdot\text{s}$，$c = 2.998\times 10^{8}\ \text{m/s}$）；
- $\text{FWHM}_t$：激光脉冲时间半高全宽 `temporal_FWHM`，$\text{s}$；
- $(dN/ds_{\text{m}})_{\text{SPA}}$、$(dN/ds_{\text{m}})_{\text{TPA}}$：单光子与双光子吸收在光路位置 $s$ 处每米产生的电子-空穴对数，$\text{m}^{-1}$；
- $P(t)$：激光时间脉冲包络 `timePulse(t)`，$\text{s}^{-1}$；$p_k$ 为 `pulse_in_bins` 在第 $k$ 个整数时间箱偏移上积分得到的无量纲脉冲权重；
- $I_{e,a}$、$I^{\text{conv}}_{e,b}$：卷积前后的第 $e$ 号电极第 $a$、$b$ 个时间箱平均感应电流，$\text{A}$，$n_{\text{bin}}$ 为时间窗总箱数（无量纲）。

式 (1)–(4) 由 [`core/deposit/laser.py`](../core/deposit.md) 的 `LaserInjection` 与 `absorption_coefficient` 实现；式 (5) 由 [`core/current/cal_current.py`](../core/current.md) 的 `pulse_in_bins`、`CalCurrentLaser` 与 `write_laser_currents` 实现。TCT 与 Edge-TCT 测量半导体探测器内部电场与电荷收集的通用方法见文献 [1]（V. Eremin, N. Strokan, E. Verbitskaya, Z. Li, “Development of transient current and charge techniques for the measurement of effective net concentration of ionized charges (Neff) in the space charge region of p-n junction detectors”, *Nucl. Instrum. Methods Phys. Res. A* 372 (1996) 388, doi:10.1016/0168-9002(95)01295-8）与文献 [2]（G. Kramberger et al., “Investigation of Irradiated Silicon Detectors by Edge-TCT”, *IEEE Trans. Nucl. Sci.* 57 (2010) 2294, doi:10.1109/TNS.2010.2051957）。

### 入射方向与光路几何

`LaserInjection._beam_frame` 支持三种激光入射方向，不启动 Geant4，直接在器件坐标系 $[0, l_x] \times [0, l_y] \times [0, l_z]$（单位 $\mu\text{m}$）内建立光路：

- **顶面入射（`"direction": "top"`）**：光束从顶面 $z = 0$ 沿 $+z$ 方向射入，器件内光路总长 $L = l_z$（$\mu\text{m}$），焦点距入射面距离 $s_{\text{focus}} = z_{\text{focus}}$，光束横截面中心位于 $(x_{\text{focus}}, y_{\text{focus}})$，通常扫描横向位置 `fx_rel`、`fy_rel` 和焦点深度 `fz_rel`。
- **底面入射（`"direction": "bottom"`）**：光束从底面 $z = l_z$ 沿 $-z$ 方向射入，器件内光路总长 $L = l_z$（$\mu\text{m}$），焦点距入射面距离 $s_{\text{focus}} = l_z - z_{\text{focus}}$，横截面中心位于 $(x_{\text{focus}}, y_{\text{focus}})$，光路距离 $s$ 对应器件坐标 $z = l_z - s$。
- **侧面入射（`"direction": "edge"`）**：光束从侧面 $x = 0$ 沿 $+x$ 方向射入，器件内光路总长 $L = l_x$（$\mu\text{m}$），焦点距入射面距离 $s_{\text{focus}} = x_{\text{focus}}$，横截面中心位于 $(y_{\text{focus}}, z_{\text{focus}})$，主要扫描光束所在的深度 `fz_rel`（或沿光束方向的焦深 `fx_rel`）。

局限：`write_laser_currents` 调用 `CalCurrentLaser` 时固定传入 `diffusion=False` 关闭载流子热扩散；`"TPA"` 模式下双光子吸收载流子群的时间展宽虽为 $\text{FWHM}_t / \sqrt{2}$，但 `CalCurrentLaser` 仍统一用单光子脉宽 `temporal_FWHM` 的 `timePulse` 对总电流做卷积；不计入高密度光生载流子对局部电场的等离子体屏蔽效应。

### 代码执行步骤与内置常数

单个 `tct` 扫描点的作业按以下顺序走完八个环节：

1. **检查与求解共享场（`field`）**：主命令在作业开始前检查 `<project>/field/` 下是否存在匹配当前器件、偏压 `voltage`（$\text{V}$）与辐照注量 `irradiation_flux`（$\text{cm}^{-2}$，$1\ \text{MeV}$ 中子等效注量）的场节点；未就绪则在作业开始前补算，存进 `<project>/field/<节点号>/`（写入期间带 `.part` 后缀，含 `node.json`）。
2. **生成激光载流子群（`deposit`）**：`deposit` 环节按器件文件构造 `Detector`，按激光组件构造 `LaserInjection`。对生效的每种吸收机制（$\alpha \ne 0$ 时算单光子，`tech == "TPA"` 时加双光子），沿光路总长 $L$ 取 $\lceil 50 L / \min(L, l_R, 10^6/\alpha) \rceil + 1$ 个采样点梯形积分求出总对数 $N_{\text{tot}}$；将横截面按 `4` 个等份额同心环（归一化半径 $\rho_r = \sqrt{-\ln(1 - (r + 0.5)/4)/k}$，$r = 0, 1, 2, 3$，单光子 $k = 2$、双光子 $k = 4$）和 `8` 个等角扇区（$\phi_m = (m + 0.5)\pi/4$，$m = 0, \dots, 7$）切分为 `32` 个单元，沿光路按等份额切分为 $N_{\text{slab}} = \lceil \max(N_{\text{tot}} / \text{pairs\_per\_group},\, \text{groups}) / 32 \rceil$ 层，在每个位于器件横向边界内的单元中心放置一个携带 $N_{\text{tot}} / (32 N_{\text{slab}})$ 对电子-空穴、时刻为 `central_time`（$\text{s}$）的载流子群，经 `laser_deposits` 写入 `deposit` 节点的 `deposit.h5`，并在节点内绘制 `draw_nocarrier3D`、`draw_nocarrier2D` 初始载流子分布图。
3. **无扩散漂移、脉冲卷积与画图（`current`）**：`current` 环节读取 `deposit` 节点的 `deposit.h5` 并加载共享场 `DevsimField`，在 `CalCurrentLaser`（`diffusion=False`）中完成全部载流子群的漂移、雪崩倍增与 Shockley-Ramo 感应电流分箱，再按单箱采样数 $S = \max(1, \lceil 20\,\Delta t_{\text{bin}} / \text{FWHM}_t \rceil)$ 算出式 (5) 的脉冲权重矩阵右乘电流波形，写入 `current` 节点的 `current.h5`，并在节点内绘制非零电极感应电流波形图。
4. **前端电路读出（`readout`）**：`readout` 环节读取 `current` 节点的 `current.h5`，组装器件等效电路与 `amplifier` 子电路链，调用 `ngspice` 求解输出电压波形并按由作业种子派生的 `readout` 噪声种子叠加频域热噪声，写入 `readout` 节点的 `readout.h5`。
5. **数字化与触发（`digitizer`、`trigger`）**：`digitizer` 按数字化器组件（默认 `MXR608A`）的模拟带宽、采样和量化（时钟相位与孔径抖动由作业种子派生的 `digitizer` 种子抽取）把模拟波形转为量化码写入 `digitizer` 节点的 `digitizer.h5`；`trigger` 按触发条件判定记录哪些事例，将被记录事例的事例号数据集 `event`（`int64`）写入 `trigger` 节点的 `trigger.h5`。
6. **波形特征提取（`reconstruction`）**：`reconstruction` 环节读取 `digitizer.h5` 中被 `trigger.h5` 记录的事例，按 `lsb_V`、`offset_V` 把量化码换回电压（$\text{V}$），采样时刻为 `t0 + k·sampling_period`，扣除基线、翻正脉冲并提取幅度、定时量、面积与团簇特征，将找到种子的事例记为 `selected`，写入 `reconstruction` 节点的 `reconstruction.h5`。
7. **单点与位置扫描汇总（`analysis`）**：`analysis` 环节汇总每个焦点扫描点的结果，在各扫描点的 `analysis` 节点（`nodes/analysis/<节点号>/`，视图 `points/<点名>/analysis/`）写出单点 `result.json`、`events.h5` 与分布图，并在 `<project>/tct/analysis/` 下写出跨焦点位置的汇总表 `points.json` 和收集电荷、信号随焦点位置变化的趋势图 `points.png`。

`tct` 涉及的内置常数如下表：

| 常数名或固定项 | 取值 | 单位 | 定义位置与含义 |
| --- | --- | --- | --- |
| 光子能量常数 $h$, $c$ | `6.626e-34`, `2.998e8` | $\text{J}\cdot\text{s}$, $\text{m/s}$ | `src/raser/core/deposit/laser.py`，计算单光子能量 $E_{\text{ph}} = h c / \lambda$ 使用的普朗克常数与光速 |
| 光路积分细分倍数 | `50` | 步 | `src/raser/core/deposit/laser.py`，光路总长除以最小特征尺度 $\min(L, l_R, 10^6/\alpha)$ 后的积分采样倍数 |
| `rings`, `sectors` | `4`, `8` | 环, 扇区 | `src/raser/core/deposit/laser.py`，激光横截面等份额切分的同心环数与扇区数（每层 `32` 群） |
| 载流子分布图箱数 | `50 × 50 × 50`（3D） | 箱 | `src/raser/core/deposit/laser.py`，`draw_nocarrier3D` 直方图分箱数 |
| 载流子密度图网格与横向范围 | `200 × 200`，光轴两侧各 `2` 倍最大光斑半径 | 点, 无量纲 | `src/raser/core/deposit/laser.py`，`draw_nocarrier2D` 计算体密度的网格点数与横向画图范围 |
| 脉冲卷积单箱采样倍数 | `20` | 点 | `src/raser/core/current/cal_current.py`，`pulse_in_bins` 要求单箱内中点矩形积分采样间距不超过 $\text{FWHM}_t / 20$ |
| `t_bin`, `delta_t` | 1D: `5e-12`, `2e-12`；2D/3D: `50e-12`, `20e-12` | $\text{s}$ | `src/raser/core/current/cal_current.py`，感应电流时间箱宽与单步漂移步长 |
| `diffusion` | `False` | 无 | `src/raser/core/current/cal_current.py`，`write_laser_currents` 固定关闭载流子热扩散 |

## 用到的环节和组件

### 环节

- [`field`](../stages/field.md)：在 `<project>/field/<节点号>/` 下求解或复用被测器件在目标偏压与辐照注量下的电场、权重场与器件等效电路参数。
- [`deposit`](../stages/deposit.md)：读取激光组件，按式 (1)–(4) 生成各焦点位置下激光注入的电子-空穴对载流子群，写入 `deposit.h5` 并绘制初始载流子分布图。
- [`current`](../stages/current.md)：读取 `deposit.h5` 中的激光载流子群，在求解场中无扩散漂移并与激光高斯时间包络按式 (5) 卷积，写出 `current.h5` 与电流波形图。
- [`readout`](../stages/readout.md)：将卷积后的感应电流送入器件等效电路与前端放大器链，用 `ngspice` 求解输出电压波形并叠加电路热噪声，写出 `readout.h5`。
- [`digitizer`](../stages/digitizer.md)：按数字化器组件（默认 `MXR608A`）的模拟带宽、采样率与量化位数把模拟波形转为量化码数字波形，写出 `digitizer.h5`。
- [`trigger`](../stages/trigger.md)：按触发条件判选被记录的事例，将事例号数据集 `event`（`int64`）写入 `trigger.h5`。
- [`reconstruction`](../stages/reconstruction.md)：读取 `digitizer.h5` 中被 `trigger` 记录的事例，按 `lsb_V`、`offset_V` 把量化码换回电压（$\text{V}$），提取脉冲幅度、定时量、面积与团簇特征，将找到种子的事例记为 `selected`，写出 `reconstruction.h5`。
- [`analysis`](../stages/analysis.md)：汇总各焦点扫描点结果写入各自的 `analysis` 节点，并在 `<project>/tct/analysis/` 下写出跨焦点位置的汇总表和收集电荷、信号随焦点位置变化的趋势图。

### 组件

- [探测器组件（`components/device`）](../components/device.md)：提供被测器件的尺寸 `l_x`、`l_y`、`l_z`（$\mu\text{m}$）、材料 `material`、掺杂、偏压、温度、辐照与雪崩参数（如 `HPK-Si-PiN.json`、`NJU-PiN.json`）。
- [能量沉积组件（`components/deposit`）](../components/deposit.md)：提供激光组件 JSON（如默认硅顶面红外激光 `LA01IR_top_Si.json`、侧面 `LA01IR_edge_Si.json`、红光 `LA01R_top_Si.json` / `LA01R_bottom_Si.json`、碳化硅紫外激光 `PIL037_top_SiC.json` / `PIL037_edge_SiC.json`、硅双光子激光 `TPA1550_top_Si.json` / `TPA1550_edge_Si.json`）及本征硅带间吸收系数表 `raser/components/deposit/absorption/Si.txt`。
- [前端读出电路组件（`components/readout`）](../components/readout.md)：提供以 `+` 串联的 SPICE 放大器级与终端负载子电路（默认 `SantaCruz+Gali52+Termination50`）。
- [数字化器组件（`components/digitizer`）](../components/digitizer.md)：提供示波器或数字化板的采样与量化设置（默认 `MXR608A`）。
- [触发组件（`components/trigger`）](../components/trigger.md)：提供独立触发设备的触发判选条件定义。

## 跑法与配置

`tct` 和 [`signal`](signal.md) 按扫描轴分界：扫的是激光相对器件的位置（`fx_rel`、`fy_rel`、`fz_rel`），用 `tct`；扫的是激光本身的性质（脉冲能量 `pulse_energy`、波长 `wavelength`）或器件的设置（偏压 `voltage`、辐照注量 `irradiation_flux`），用 [`signal`](signal.md)。

对被测器件运行 `tct`，位置扫描轴写在 `config.json` 的 `deposit` 段里，或在命令行用 `--scan` 给出位置列表（例如扫描激光焦点深度相对器件厚度的比例 `fz_rel`）：

```bash
raser tct <器件>
raser tct NJU-PiN --set deposit.laser=PIL037_top_SiC --scan deposit.laser.fz_rel=0.1,0.3,0.5,0.7,0.9
```

按 [架构总纲](../architecture.md#project) 的分段格式，实验文件夹 `<project>/tct/config.json` 的配置结构如下。下面只摘和本页有关的段；`examples/NJU-PiN/tct/config.json` 里八段都写全。

```json
{
  "workflow": "tct",
  "device": "NJU-PiN",
  "field": {
    "voltage": -500.0
  },
  "deposit": {
    "laser": {
      "name": "PIL037_top_SiC",
      "fx_rel": 0.5,
      "fy_rel": 0.5,
      "fz_rel": [0.1, 0.3, 0.5, 0.7, 0.9]
    }
  },
  "readout": {
    "amplifier": "SantaCruz+Gali52+Termination50"
  }
}
```

`deposit` 段里的 `laser` 写成带 `name` 的对象时，`name` 选用激光组件，其余键覆盖这个组件文件里的同名键，和命令行的 `deposit.laser.fz_rel` 一一对应；只选组件、不改键时写成字符串 `"laser": "PIL037_top_SiC"`。

使用者在 `tct` 中能设的配置键如下表（激光组件各键定义见 [能量沉积组件（`components/deposit`）](../components/deposit.md#激光与吸收系数表)，其余各环节设置写在各自的段里，见 [仿真链与环节入口（`stages`）](../stages/README.md)）。“示例里的值”是 `examples/NJU-PiN/tct/config.json` 写的值；`config.json` 缺了要用的键时报错，指出缺的“段.键”：

| 段.键 | 示例里的值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `deposit.laser` | `{"name": "PIL037_top_SiC", …}` | 无 | 激光组件名称或路径；写成带 `name` 的对象时其余键覆盖组件文件里的同名键 |
| `deposit.laser.fx_rel` | `0.5` | 无量纲 | 激光焦点在器件 $x$ 方向的相对坐标，绝对位置 $x_{\text{focus}} = \text{fx\_rel}\cdot l_x$（$\mu\text{m}$） |
| `deposit.laser.fy_rel` | `0.5` | 无量纲 | 激光焦点在器件 $y$ 方向的相对坐标，绝对位置 $y_{\text{focus}} = \text{fy\_rel}\cdot l_y$（$\mu\text{m}$） |
| `deposit.laser.fz_rel` | `[0.1, 0.3, 0.5, 0.7, 0.9]`（扫描轴） | 无量纲 | 激光焦点在器件深度 $z$ 方向的相对坐标，绝对位置 $z_{\text{focus}} = \text{fz\_rel}\cdot l_z$（$\mu\text{m}$） |
| `field.voltage` | `-500.0`（写 `null` 时取器件文件里的偏压） | $\text{V}$ | 被测器件反向偏置电压 |
| `readout.amplifier` | `"SantaCruz+Gali52+Termination50"` | 无 | 以 `+` 连接的前端放大器与终端负载组件链 |
| `deposit.laser.<激光键>` | 不写（用激光组件文件里的值） | 依键而定 | 覆写激光组件中的 `direction`、`tech`、`wavelength`（$\text{nm}$）、`refractionIndex`、`alpha`（$\text{m}^{-1}$）、`beta_2`（$\text{m/W}$）、`temporal_FWHM`（$\text{s}$）、`pulse_energy`（$\text{J}$）、`spacial_FWHM`（$\mu\text{m}$）、`l_Rayleigh`（$\mu\text{m}$）、`central_time`（$\text{s}$）、`pairs_per_group`（对）、`groups`（群） |

其余参数（激光横截面切分的 `4` 同心环 $\times$ `8` 扇区、光路积分 `50` 倍细分、脉冲卷积单箱 `20` 倍中点采样、载流子漂移时间窗与时间步长档位 `t_bin`/`delta_t`、关闭载流子热扩散 `diffusion = False`、初始载流子三维分布图的 `50` 箱划分与二维密度图的 `200 × 200` 网格）全部写死在代码里。

## 输出

每个激光位置是一个扫描点，各环节结果和 [`signal`](signal.md) 一样存放在 `<project>/tct/` 下（见 [架构总纲](../architecture.md#结果)）：底层存放在 `<project>/tct/nodes/<环节>/<节点号>/`（内含该环节输出文件、本环节图像与 `node.json`；`deposit` 到 `reconstruction` 每个作业一个节点，`analysis` 每个扫描点一个节点），上层通过 `<project>/tct/points/<点名>/<环节>/<作业号>` 软链接视图（`points/<点名>/field`、`points/<点名>/analysis` 各是一个软链接）和 `<project>/tct/points.json` 访问，[`analysis`](../stages/analysis.md) 在各点 `analysis` 节点写出单点结果和分布图，并在 `<project>/tct/analysis/` 下写出跨焦点位置汇总表和收集电荷、信号随焦点位置变化的趋势图。器件共享场节点存放在 `<project>/field/<节点号>/` 下。

### 数据文件

| 路径 | 写出环节 | 内容与主要字段 | 单位 |
| --- | --- | --- | --- |
| `nodes/deposit/<节点号>/deposit.h5` | [`deposit`](../stages/deposit.md) | 激光注入载流子群（记录为事例 `event = 0`）：属性 `generated_events`、`recorded_events`、`emission_probability`（没有出射分布的源为 `1.0`）；数据集 `event`、`count`、`detector`、`x`/`y`/`z`、`x_start`/`y_start`/`z_start`、`t`、`t_fwhm`、`e`、`pairs` | 坐标 $\mu\text{m}$，时间 $\text{s}$，能量 $\text{MeV}$，`pairs` 为对 |
| `nodes/current/<节点号>/current.h5` | [`current`](../stages/current.md) | 卷积脉冲时间包络后的感应电流文件：属性 `electrodes`、`dt`；数据集 `event`、`t0`、`count`、`pairs`、`sensitive_pairs`、`carriers_without_field`、`charge`、`stored`、`index`、`current` | `dt`、`t0` 为 $\text{s}$，`charge` 为 $\text{C}$，`current` 为 $\text{A}$，`pairs` 为对 |
| `nodes/readout/<节点号>/readout.h5` | [`readout`](../stages/readout.md) | 经器件等效电路与前端放大器链求解的输出电压波形：属性 `electrodes`、`dt`、`pulse_edge`、`device_circuit`；数据集 `event`、`t0`、`count`、`stored`、`index`、`voltage` | `dt`、`t0` 为 $\text{s}$，`voltage` 为 $\text{V}$ |
| `nodes/digitizer/<节点号>/digitizer.h5` | [`digitizer`](../stages/digitizer.md) | 数字化量化码波形：属性 `electrodes`、`sampling_period`、`lsb_V`、`offset_V`、`bits`、`pulse_edge`、`device`；数据集 `event`、`t0`、`count`、`stored`、`index`、`clipped`、`code`（`int16`） | `sampling_period`、`t0` 为 $\text{s}$，`lsb_V`、`offset_V` 为 $\text{V}$，`bits` 为位，`code` 无量纲 |
| `nodes/trigger/<节点号>/trigger.h5` | [`trigger`](../stages/trigger.md) | 触发记录事例：数据集 `event`（`int64`，被记录事例的事例号） | 无量纲 |
| `nodes/reconstruction/<节点号>/reconstruction.h5` | [`reconstruction`](../stages/reconstruction.md) | 重建事件特征表：属性 `electrodes`、`threshold`、`amplitude_threshold`、`fractions`、`edge`；数据集 `event`、`selected`、`cluster_size`、`cluster_center`、`traced`、`baseline`、`noise`、`amplitude`、`above`、`ToA`、`ToT`、`CoG`、`area`、`CFD` | 电压与阈值 $\text{V}$，时间 $\text{s}$，面积 $\text{V}\cdot\text{s}$ |
| `nodes/analysis/<节点号>/result.json`、`events.h5`（视图 `points/<点名>/analysis/`） | [`analysis`](../stages/analysis.md) | 单焦点扫描点汇总结果与 `selected` 事例特征表 | 电压 $\text{V}$，阈值 $\text{mV}$，时间 $\text{s}$，效率无量纲 |
| `analysis/points.json` | [`analysis`](../stages/analysis.md) | 跨焦点位置扫描的汇总表，记录各焦点位置下的收集电荷与信号特征 | 相对坐标无量纲，电荷 $\text{C}$，电压 $\text{V}$，时间 $\text{s}$ |

### 图像文件

| 路径 | 写出环节 / 函数 | 内容 | 坐标与物理量单位 |
| --- | --- | --- | --- |
| `nodes/deposit/<节点号>/nocarrier_<fx_rel>_<fy_rel>_<fz_rel>.pdf` | [`deposit`](../stages/deposit.md)（`LaserInjection.draw_nocarrier3D`） | 激光脉冲在器件内生成的初始载流子群三维对数分布直方图（`TH3D`，`50 × 50 × 50` 箱，文件名中相对坐标四舍五入至 `5` 位小数） | 三轴 `Depth [um]`、`Width [um]`、`Thick [um]`，箱权重为电子-空穴对数 |
| `nodes/deposit/<节点号>/nocarrier2D_<fx_rel>_<fy_rel>_<fz_rel>.pdf` | [`deposit`](../stages/deposit.md)（`LaserInjection.draw_nocarrier2D`） | $y = \text{fy\_rel}\cdot l_y$ 的 $x$-$z$ 面（过光轴）上初始电子-空穴对的体密度，按吸收公式在 `200 × 200` 网格上算出（`TH2D`，`COLZ` 色标） | 横轴 `x axis [um]`，纵轴 `z axis [um]`，色标 `Pairs [um^-3]` |
| `nodes/current/<节点号>/No_<k>electrode_basic_infor.pdf`, `.root` | [`current`](../stages/current.md)（`draw_currents`） | 第 $k$ 号非零电流电极（从 `1` 起）经激光时间脉冲卷积后的 `electron`、`hole`、`total`（开启雪崩时含 `electron gain`、`hole gain`）感应电流波形 | 横轴 `Time [s]`，纵轴 `Current [A]` |
| `analysis/points.png` | [`analysis`](../stages/analysis.md) | 跨焦点位置扫描的收集电荷与信号随焦点位置变化曲线 | 横轴相对焦点位置（无量纲），纵轴按对应物理量标注单位 |

![NJU-PiN 激光注入二维载流子分布](../images/tct-carriers-2d-NJU-PiN.png)

`NJU-PiN` 在顶面紫外激光 `PIL037_top_SiC` 照射下由 `draw_nocarrier2D` 输出的过光轴 $x$-$z$ 面上初始电子-空穴对的体密度。

![NJU-PiN TCT 感应电流波形](../images/tct-current-NJU-PiN.png)

`NJU-PiN` 在 `tct` 测试中由 `write_laser_currents` 输出的读出电极电子分量、空穴分量与总感应电流波形。
