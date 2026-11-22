# 束流望远镜空间分辨测试（`bench/telescope`）

`telescope`（`raser_bench` 包）是继承 `raser` 实验基类的测试类（见[架构总纲](../architecture.md#实验是-python-类)），用束流望远镜测量位置灵敏被测器件（DUT）在 $x$、$y$ 方向的空间分辨。望远镜由沿束流方向排布的一串探测平面组成，用一个器件列表给出，列几块放几块，每块都是按器件文件建成的真实器件：前面若干层参考层、中间被测器件、后面若干层参考层。参考层默认是 `TAICHU3`（太初 3 号 CMOS 像素探测器），中间被测器件默认放两块，命令行给定的器件替换中间的两块被测器件，两块都换成它。望远镜的总层数任意，每一层的器件都可以换成别的器件，每一层的板子可以朝 $x$-$y$ 平面内四个方向之一摆放。

`telescope` 读取[探测器组件（`components/device`）](../components/device.md)、[能量沉积组件（`components/deposit`）](../components/deposit.md)、[前端读出电路组件（`components/readout`）](../components/readout.md)、[数字化器组件（`components/digitizer`）](../components/digitizer.md)和[触发组件（`components/trigger`）](../components/trigger.md)，依次走完 [`field`](../stages/field.md)、[`deposit`](../stages/deposit.md)、[`current`](../stages/current.md)、[`readout`](../stages/readout.md)、[`digitizer`](../stages/digitizer.md)、[`trigger`](../stages/trigger.md)、[`reconstruction`](../stages/reconstruction.md) 和 [`analysis`](../stages/analysis.md) 八个环节。全部探测平面共用同一次 [`deposit`](../stages/deposit.md) 模拟高能粒子束流依次穿过各层。每一层各自走一遍 `field`、`current`、`readout`、`digitizer`、`trigger`、`reconstruction`，其中 `reconstruction` 在每层做团簇聚类求击中位置。`analysis` 把各层的击中拼成径迹，求被测器件的残差并拟合宽度，给出残差标准差 $\sigma_{\text{Tol}}$。

## 装置与通用范式

### 通用做法与物理模型

学术界在束流测试中测量位置灵敏探测器的空间分辨时，将被测器件放置在由前后各若干层高精度像素参考探测器（如 `TAICHU3`、MIMOSA26 或 ALPIDE）组成的束流望远镜中间。高能粒子束穿过全部探测平面后，各层对过阈击中像素做连通团簇聚类（clustering）求出击中重心；用参考层上的击中位置拟合直线径迹并外推到被测器件所在平面，统计被测器件击中位置相对外推位置的残差（residual），残差分布的高斯标准差反映被测器件的空间分辨。

望远镜由前 $N_{\text{front}}$ 层参考层、中间 $N_{\text{DUT}}$ 块被测器件与后 $N_{\text{back}}$ 层参考层组成，默认 3 + 2 + 3（前后各 3 层 `TAICHU3`，中间 2 块被测器件），参考层总数为 $N_{\text{ref}} = N_{\text{front}} + N_{\text{back}}$（参考层索引集合记为 $\mathcal{R}$），望远镜总层数为 $N = N_{\text{front}} + N_{\text{DUT}} + N_{\text{back}}$。在每层的局部坐标系中，[`reconstruction`](../stages/reconstruction.md) 按像素几何中心坐标、八邻域连通判据与算术平均重心对过阈击中像素做团簇聚类：

$$(x_{p}, y_{p}) = \bigl((i_x + 0.5)\,p_x,\; (i_y + 0.5)\,p_y\bigr), \qquad \Delta x^{2} + \Delta y^{2} \le p_x^{2} + p_y^{2} + \epsilon, \qquad (\bar{x}_{c}, \bar{y}_{c}) = \frac{1}{n_c}\sum_{m=1}^{n_c}(x_{p,m}, y_{p,m}) \tag{1}$$

各层的局部团簇重心按该层板子在 $x$-$y$ 平面内的摆放朝向变换到望远镜全局 $(x, y)$ 坐标系，第 $j$ 层参考层（$j \in \mathcal{R}$）与第 $d$ 块被测器件（$d = 1, \dots, N_{\text{DUT}}$）的击中位置分别记为 $(\bar{x}_{c,j}, \bar{y}_{c,j})$ 与 $(\bar{x}_{c,d}, \bar{y}_{c,d})$。[`analysis`](../stages/analysis.md) 选取参考层与被测器件均给出单团簇的事例，用全部 $N_{\text{ref}}$ 层参考层的灵敏层中面坐标 $z_j + l_{z,j}/2$ 与击中位置 $(\bar{x}_{c,j}, \bar{y}_{c,j})$ 分别对 $x$-$z$ 和 $y$-$z$ 做最小二乘直线拟合：

$$\hat{x}(z) = k_x z + b_x, \qquad \hat{y}(z) = k_y z + b_y \tag{2}$$

将参考径迹外推到第 $d$ 块被测器件的中面 $z_d + l_{z,d}/2$，计算被测器件与各参考层上的残差 $(r_{x,d}, r_{y,d})$、$(r_{x,j}, r_{y,j})$，并以 $N_{\text{ref}}$ 层参考层上的拟合残差计算参考径迹卡方 $\chi^2$：

$$\begin{aligned}
r_{x,d} &= \hat{x}\!\left(z_d + \frac{l_{z,d}}{2}\right) - \bar{x}_{c,d}, & r_{y,d} &= \hat{y}\!\left(z_d + \frac{l_{z,d}}{2}\right) - \bar{y}_{c,d}, \\
r_{x,j} &= \hat{x}\!\left(z_j + \frac{l_{z,j}}{2}\right) - \bar{x}_{c,j}, & r_{y,j} &= \hat{y}\!\left(z_j + \frac{l_{z,j}}{2}\right) - \bar{y}_{c,j}, & \chi^{2} &= \sum_{j \in \mathcal{R}}\left(\frac{r_{x,j}^{2}}{p_{x,j}^{2}/12} + \frac{r_{y,j}^{2}}{p_{y,j}^{2}/12}\right)
\end{aligned} \tag{3}$$

对第 $d$ 块被测器件在 $x$、$y$ 方向的残差分布分别做高斯拟合，得到残差标准差 $\sigma_{\text{Tol},d}$（$\mu\text{m}$）。$\sigma_{\text{Tol},d}$ 包含被测器件自身的分辨和望远镜外推的不确定度，`telescope` 给出的就是这个分布和它的宽度。

各符号的含义与单位如下：

| 符号 | 含义 | 单位 |
| --- | --- | --- |
| $N_{\text{front}}, N_{\text{back}}$ | 被测器件之前与之后的参考层数（默认各 `3`） | 无量纲 |
| $N_{\text{ref}}$ | 参考层总层数，$N_{\text{ref}} = N_{\text{front}} + N_{\text{back}}$（$N_{\text{ref}} \ge 2$）；$\mathcal{R}$ 为全部参考层的索引集合 | 无量纲 |
| $N_{\text{DUT}}$ | 望远镜中间的被测器件层数（默认 `2`）；$d = 1, \dots, N_{\text{DUT}}$ 为被测器件索引 | 无量纲 |
| $N$ | 望远镜总层数，$N = N_{\text{front}} + N_{\text{DUT}} + N_{\text{back}}$ | 无量纲 |
| $i_x, i_y$ | 像素在所属器件阵列中的列、行下标（从 `0` 起） | 无量纲 |
| $p_x, p_y$ | 像素在层局部 $x$、$y$ 方向的间距（pitch） | $\mu\text{m}$ |
| $p_{x,j}, p_{y,j}$ | 第 $j$ 层参考层按其朝向映射到望远镜全局 $x$、$y$ 方向后的像素间距 | $\mu\text{m}$ |
| $(x_p, y_p)$ | 像素几何中心在层局部坐标系中的坐标；$(x_{p,m}, y_{p,m})$ 为团簇内第 $m$ 个像素的中心坐标 | $\mu\text{m}$ |
| $\Delta x, \Delta y$ | 同一层两击中像素中心在局部 $x$、$y$ 方向的距离 | $\mu\text{m}$ |
| $\epsilon$ | 连通判据浮点容差，取 $10^{-7}$，使八邻域内四正交与四对角紧邻像素均判为连通 | $\mu\text{m}^2$ |
| $n_c$ | 单个连通团簇包含的像素数 | 个 |
| $(\bar{x}_c, \bar{y}_c)$ | 团簇在层局部坐标系中的算术平均重心坐标 | $\mu\text{m}$ |
| $(\bar{x}_{c,j}, \bar{y}_{c,j}), (\bar{x}_{c,d}, \bar{y}_{c,d})$ | 第 $j$ 层参考层、第 $d$ 块被测器件变换到望远镜全局坐标后的团簇重心坐标 | $\mu\text{m}$ |
| $z_j, z_d$ | 第 $j$ 层参考层、第 $d$ 块被测器件沿束流轴的前表面位置坐标 | $\mu\text{m}$ |
| $l_{z,j}, l_{z,d}$ | 第 $j$ 层参考层、第 $d$ 块被测器件的灵敏层厚度 | $\mu\text{m}$ |
| $k_x, k_y$ | 由参考层拟合得到的直线径迹在 $x$-$z$、$y$-$z$ 平面的斜率 | 无量纲 |
| $b_x, b_y$ | 由参考层拟合得到的直线径迹在 $x$-$z$、$y$-$z$ 平面的截距 | $\mu\text{m}$ |
| $\hat{x}(z), \hat{y}(z)$ | 直线径迹外推到束流轴位置 $z$（$\mu\text{m}$）处的全局横坐标 | $\mu\text{m}$ |
| $r_{x,d}, r_{y,d}$ | 第 $d$ 块被测器件中面 $z_d + l_{z,d}/2$ 处外推位置与实测重心的 $x$、$y$ 残差 | $\mu\text{m}$ |
| $r_{x,j}, r_{y,j}$ | 第 $j$ 层参考层（$j \in \mathcal{R}$）中面 $z_j + l_{z,j}/2$ 处的径迹拟合 $x$、$y$ 残差 | $\mu\text{m}$ |
| $\chi^2$ | 按各参考层像素均匀分布方差 $p_{x,j}^2/12$、$p_{y,j}^2/12$ 归一化的参考径迹拟合卡方 | 无量纲 |
| $\sigma_{\text{Tol},d}$ | 第 $d$ 块被测器件在 $x$ 或 $y$ 方向残差分布的高斯拟合总标准差 | $\mu\text{m}$ |

束流望远镜径迹拟合与空间分辨提取的通用范式见文献 [1]（H. Jansen et al., “Performance of the EUDET-type beam telescopes”, *EPJ Tech. Instrum.* 3 (2016) 7, doi:10.1140/epjti/s40485-016-0033-2），太初（TaichuPix）CMOS 像素传感器束流测试见文献 [2]（T. Wu et al., “Beam test of a 180 nm CMOS pixel sensor for the CEPC vertex detector”, *Nucl. Instrum. Methods Phys. Res. A* 1059 (2024) 168945, doi:10.1016/j.nima.2023.168945）。

### 望远镜装置几何

望远镜由沿 $+z$ 方向依次排布的 $N$ 层探测平面组成：前 $N_{\text{front}}$ 层参考层、中间 $N_{\text{DUT}}$ 块被测器件、后 $N_{\text{back}}$ 层参考层，默认 3 + 2 + 3。整套望远镜完全由配置控制：器件列表、层数、每层的器件和板子朝向都写在配置里。整套望远镜用一个器件列表给出，列几块放几块，每块按对应器件文件在 Geant4 装置中建成实体。命令行给定的器件替换中间的两块被测器件，两块都换成它；除被测器件外，前后任意参考层也可替换为其他器件，各段层数按器件列表自由增减。

参考层默认使用 `TAICHU3`（`TAICHU3.json`）：硅（`"Si"`）像素探测器，全尺寸 $l_x = 1500\ \mu\text{m}$、$l_y = 1500\ \mu\text{m}$、$l_z = 20\ \mu\text{m}$，阵列 $60 \times 60$ 像素（共 `3600` 个），像素间距 $p_x = p_y = 25.0\ \mu\text{m}$，单像素中心矩形收集区 $10.0 \times 10.0\ \mu\text{m}$，工作温度 $300.0\ \text{K}$，默认偏压 `-1.8` $\text{V}$，受主浓度 `1e12` $\text{cm}^{-3}$、施主浓度 `0` $\text{cm}^{-3}$。

示例配置用的装置是 [能量沉积组件](../components/deposit.md#库中-geant4-装置) 里的 `telescope`：真空中沿 $+z$ 等间距 $40\ \text{mm}$ 排布 8 个槽位，槽位前表面中心都在束流轴上，`rotation_z` 都为 `0`。

| 槽位 | 角色 | 默认器件 | 前表面 $z$（$\text{mm}$） | `rotation_z`（度） |
| --- | --- | --- | --- | --- |
| `ref1` | 参考层 | `TAICHU3` | `-140` | `0` |
| `ref2` | 参考层 | `TAICHU3` | `-100` | `0` |
| `ref3` | 参考层 | `TAICHU3` | `-60` | `0` |
| `dut1` | 被测器件 | 命令行给定的器件 | `-20` | `0` |
| `dut2` | 被测器件 | 命令行给定的器件 | `20` | `0` |
| `ref4` | 参考层 | `TAICHU3` | `60` | `0` |
| `ref5` | 参考层 | `TAICHU3` | `100` | `0` |
| `ref6` | 参考层 | `TAICHU3` | `140` | `0` |

示例配置用的束流是 `beam/electron_5GeV_spread`：$5\ \text{GeV}$ 电子从 $z = -400\ \text{mm}$ 沿 $+z$ 射出，方向在 $x$、$y$ 上各有 $\pm 750\ \mu\text{m}$ 的均匀瞄准展宽（瞄准点在 $z = 100\ \text{mm}$），覆盖参考层 $1.5 \times 1.5\ \text{mm}$ 的灵敏面。

每一层的探测器板子都垂直于束流轴 $z$ 摆放，并可在 $x$-$y$ 平面内朝四个方向之一摆放（绕 $z$ 轴旋转 $0^\circ$、$90^\circ$、$180^\circ$ 或 $270^\circ$）。按学术界束流望远镜的通用做法，这一自由度用于两类需求：

- **测量 $x$、$y$ 两个方向的空间分辨**：条形（strip）探测器或非方形像素探测器（$p_x \ne p_y$）只在单一敏感方向或短边方向具备高位置分辨。将板子旋转 $90^\circ$（例如把两块被测器件分别按 $0^\circ$ 与 $90^\circ$ 正交摆放，或将部分参考层旋转 $90^\circ$），即可在同一望远镜坐标系下测出 $x$、$y$ 两个方向的空间分辨，或为两个正交坐标同时提供高精度径迹约束。
- **匹配束流实验中的机械安装与出线方向**：实验现场受支架、冷却接口与读出 PCB 引线位置限制，相邻探测板常旋转 $90^\circ$、$180^\circ$ 或 $270^\circ$ 安装以错开读出芯片与线缆。指定各层板子朝向后，各层局部像素坐标即可正确变换到统一的望远镜全局 $(x, y)$ 坐标系。

### 执行步骤

`telescope` 按八环节链条依次执行：

1. **求解或复用各层共享场（[`field`](../stages/field.md)）**：为器件列表中的每一层器件定位其在目标偏压 `voltage`（$\text{V}$）与辐照注量 `irradiation_flux`（$\text{cm}^{-2}$，$1\ \text{MeV}$ 中子等效注量）下的电场、权重场与等效电路参数，未就绪时在作业开始前补算。各层器件的共享场节点各自存放在对应器件 project 下的 `field/<节点号>/` 中。
2. **全望远镜能量沉积（[`deposit`](../stages/deposit.md)）**：在 Geant4 望远镜装置中按器件列表与各层板子朝向建出前 $N_{\text{front}}$ 层参考层、中间 $N_{\text{DUT}}$ 块被测器件与后 $N_{\text{back}}$ 层参考层的实体。高能粒子束流沿 $+z$ 方向依次穿过全部 $N$ 层平面，统一记录各层内的能量沉积步并转化为初始电子-空穴对，写入 `deposit` 节点的 `deposit.h5`，按层区分归属。
3. **逐层漂移、读出、数字化与触发（[`current`](../stages/current.md)、[`readout`](../stages/readout.md)、[`digitizer`](../stages/digitizer.md)、[`trigger`](../stages/trigger.md)）**：每一层各自在对应的求解场中漂移载流子，计算各像素电极的感应电流与净电荷，经各自的器件等效电路与前端放大器链求解模拟电压波形并按由作业种子派生的 `readout` 噪声种子叠加电路热噪声。随后各层分别按数字化器的模拟带宽、采样率与量化位数（时钟相位与孔径抖动由作业种子派生的 `digitizer` 种子抽取）生成量化码数字波形写入 `digitizer` 节点，并经触发判选将被记录事例的事例号数据集 `event`（`int64`）写入 `trigger` 节点的 `trigger.h5`。
4. **团簇聚类（[`reconstruction`](../stages/reconstruction.md)）**：读取 `digitizer.h5` 中被 `trigger.h5` 记录的事例，按 `lsb_V`、`offset_V` 将量化码换回电压（$\text{V}$），采样时刻为 `t0 + k·sampling_period`；在每一层上提取像素信号特征，以 `amplitude_threshold` 找团簇种子并将找到种子的事例记为 `selected`，按式 (1) 对过阈击中像素做连通团簇聚类，求出该层在局部坐标系中的击中位置 $(\bar{x}_c, \bar{y}_c)$（$\mu\text{m}$）与团簇大小 $n_c$（个）。
5. **径迹拟合与空间分辨提取（[`analysis`](../stages/analysis.md)）**：读各作业每一层的击中位置，按各层朝向变换到望远镜全局坐标系，用全部 $N_{\text{ref}}$ 层参考层的击中位置按式 (2) 拟合直线径迹并外推到各块被测器件所在平面，按式 (3) 求残差；对每块被测器件 $x$、$y$ 方向的残差分布各做一次截断高斯拟合（[统计分析](../core/analysis.md) 的 `residual_widths`），得到残差标准差 $\sigma_{\text{Tol}}$（$\mu\text{m}$）。

### 快速跑法

`reconstruction.hits = "deposit"` 时，`telescope` 不跑 `field`、`current`、`readout`、`digitizer`、`trigger`，[`reconstruction`](../stages/reconstruction.md) 直接读 `deposit` 节点：一层上沉积了电子-空穴对的像素记为过阈击中像素，其余照第 4、5 步。配合直线 MIP 源 `toy/MIP_telescope`（不启动 Geant4，无多次散射），残差只来自像素的离散化，可以很快地扫被测器件的像素间距、层间距和朝向，看几何本身给出的分辨。

## 用到的环节和组件

### 环节

- [`field`](../stages/field.md)：分别为每一层器件求解或复用目标偏压与辐照注量下的电场、权重场与等效电路参数，存放在对应器件 project 的 `field/<节点号>/` 下。
- [`deposit`](../stages/deposit.md)：在束流望远镜装置中用 Geant4 模拟高能粒子束依次穿过前 $N_{\text{front}}$ 层参考层、中间 $N_{\text{DUT}}$ 块被测器件与后 $N_{\text{back}}$ 层参考层，统一记录全部层的能量沉积步并转化为初始电子-空穴对，写入 `deposit.h5`。
- [`current`](../stages/current.md)：在每一层各自的求解场中模拟载流子漂移、扩散与收集，计算该层各电极上的感应电流与净感应电荷。
- [`readout`](../stages/readout.md)：将每一层的电极感应电流分别送入对应器件等效电路与前端放大器链，求解输出模拟电压波形并叠加电路热噪声。
- [`digitizer`](../stages/digitizer.md)：按数字化器的模拟带宽、采样率与量化位数，将每一层的模拟输出波形分别转换为量化码数字波形。
- [`trigger`](../stages/trigger.md)：对每一层的数字波形按触发条件判选需要记录的事例，将被记录事例的事例号写入 `trigger.h5`。
- [`reconstruction`](../stages/reconstruction.md)：读取 `digitizer.h5` 中被 `trigger` 记录的事例，按 `lsb_V`、`offset_V` 将量化码换回电压（$\text{V}$），在每一层上对过阈击中像素按式 (1) 做团簇聚类求击中位置并将找到种子的事例记为 `selected`。
- [`analysis`](../stages/analysis.md)：用参考层的击中位置按式 (2) 拟合直线径迹并外推到被测器件所在平面，按式 (3) 求残差，对每块被测器件 $x$、$y$ 方向的残差分布各做一次截断高斯拟合，输出单点的 $\sigma_{\text{Tol}}$。

### 组件

- [探测器组件（`components/device`）](../components/device.md)：提供望远镜参考层像素探测器（默认 `TAICHU3`，尺寸 $1500 \times 1500 \times 20\ \mu\text{m}$，间距 $25.0 \times 25.0\ \mu\text{m}$）和放在中间的被测器件定义；列表内每一层都可以选用组件库或用户 project 中的任意器件。
- [能量沉积组件（`components/deposit`）](../components/deposit.md)：提供高能粒子束流组件与按器件列表排布多层探测平面的束流望远镜 Geant4 装置。
- [前端读出电路组件（`components/readout`）](../components/readout.md)：提供各层探测器使用的前端放大器与终端负载 SPICE 子电路链。
- [数字化器组件（`components/digitizer`）](../components/digitizer.md)：提供各层读出波形的模拟带宽、采样率与量化位数设置（如 `MXR608A`）。
- [触发组件（`components/trigger`）](../components/trigger.md)：提供望远镜事例记录使用的触发条件定义。

## 跑法与配置

命令行传入放在望远镜中间的被测器件名称即可运行空间分辨测试（见[命令行接口](../cli.md#命令)），也可以用 `--set`、`--scan` 修改或扫描偏压（$\text{V}$）、阈值（$\text{mV}$）等配置项：

```bash
raser telescope <器件>
raser telescope <器件> --scan field.voltage=-100,-200
raser telescope <器件> --set deposit.g4setup.devices.dut2.rotation_z=90
raser telescope <器件> --set deposit.source=toy/MIP_telescope --set reconstruction.hits=deposit
```

第三行把第二块被测器件转 $90^\circ$，第四行是快速跑法。

实验文件夹 `<project>/telescope/config.json` 按环节分段记录配置（格式见[架构总纲](../architecture.md#project)）。望远镜的器件列表写在 `telescope` 实验类里，前后各 3 层默认取 `TAICHU3`，中间默认放两块被测器件，命令行给定的器件替换被测器件。器件列表、每层朝向和每层器件各自的偏压等设置分别设。

下表列出 `telescope` 与其他测试页共用的环节配置键；`deposit` 段由全部层共用，其余各段在多层望远镜中按层分别设置。“示例里的值”是示例 project 里 `telescope/config.json` 写的值；`config.json` 缺了要用的键时报错，指出缺的“段.键”：

| 段.键 | 示例里的值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `field.voltage` | `null`（取对应器件文件里的偏压） | $\text{V}$ | 该层器件偏置电压 |
| `field.irradiation_flux` | `null`（取器件文件里的辐照注量，器件文件没有辐照块时为 `0`） | $\text{cm}^{-2}$ | 该层器件辐照注量（$1\ \text{MeV}$ 中子等效注量） |
| `deposit.source` | 束流组件名 | 无 | 入射粒子束流组件名称或路径 |
| `deposit.g4setup` | `"telescope"` | 无 | Geant4 束流望远镜装置组件名称或路径 |
| `deposit.events_per_job` | `1000` | 事例 | 每作业需记录的有效沉积事例数（与 `deposit.generated_per_job` 互斥） |
| `deposit.generated_per_job` | `null`（不用） | 事例 | 每作业由束流源生成的总事例数（与 `deposit.events_per_job` 互斥） |
| `deposit.generated_limit` | `10000000` | 事例 | 为录满 `events_per_job` 允许生成的最大源事例数上限 |
| `deposit.edep_min` | `null`（不设下限） | $\text{MeV}$ | 记录事例的最小沉积能量下限 |
| `deposit.edep_max` | `null`（不设上限） | $\text{MeV}$ | 记录事例的最大沉积能量上限 |
| `deposit.fano` | `true` | 无 | 电离对数转化是否开启 Fano 涨落抽样 |
| `deposit.plots` | `100` | 事例 | 每作业画 Geant4 几何与径迹图的前若干个记录事例数 |
| `current.plots` | `100` | 事例 | 每作业画载流子漂移路径与电流图的前若干个记录事例数 |
| `readout.amplifier` | `"SantaCruz+Gali52+Termination50"` | 无 | 以 `+` 连接的前端放大器与终端负载组件链 |
| `readout.sheet_resistance` | `null`（取器件文件里阻性层的方块电阻） | $\Omega$ | 覆盖含 `resistive_layer` 器件的阻性层方阻 |
| `reconstruction.threshold` | `10.0` | $\text{mV}$ | 像素信号过阈与邻近像素入簇阈值 |
| `reconstruction.amplitude_threshold` | `10.0` | $\text{mV}$ | 团簇种子像素的脉冲幅度阈值；在 `trigger` 记录的事例里找到种子的记为 `selected`（事例记不记录由 `trigger` 按触发条件决定） |
| `reconstruction.fractions` | `[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]` | 无量纲 | 恒比定时（`CFD`）的幅度比例列表，每项须位于 `(0, 1)` 开区间内 |
| `reconstruction.edge` | `null`（沿用对应层 `readout` 写出的 `pulse_edge`） | 无 | 阈值作用的脉冲边沿方向，可选 `"rising"` 或 `"falling"` |
| `reconstruction.hits` | `"signal"` | 无 | 击中像素从哪里来：`"signal"` 为 `trigger` 记录的数字波形过 `reconstruction.threshold`，`"deposit"` 为沉积了电子-空穴对的像素（快速跑法） |
| `analysis.plots` | `10` | 事例 | 每个扫描点画径迹拟合图的前若干个选中事例数 |

装置槽位 `deposit.g4setup` 里各槽位的位置和朝向是组件内部键，地址为 `deposit.g4setup.devices.<槽位>.position`（$\mu\text{m}$）与 `deposit.g4setup.devices.<槽位>.rotation_z`（度）。

## 输出

测试结果存放在被测器件 project 下的 `<project>/telescope/`（如 `work/<被测器件>/telescope/`），存放结构见[架构总纲](../architecture.md#结果)。各环节按输入指纹写入底层节点 `<project>/telescope/nodes/<环节>/<节点号>/`（内含该环节输出文件、本环节图像与 `node.json`；`deposit` 到 `reconstruction` 每个作业一个节点，`analysis` 每个扫描点一个节点），上层按扫描点在 `<project>/telescope/points/<点名>/<环节>/<作业号>` 生成软链接视图（`points/<点名>/field`、`points/<点名>/analysis` 各是一个软链接），并在 `<project>/telescope/points.json` 记录参数表；各扫描点的单点统计汇总与分布图存放在各自的 `analysis` 节点（视图 `<project>/telescope/points/<点名>/analysis/`）中，跨扫描点汇总与趋势图存放在 `<project>/telescope/analysis/` 下，每个环节自己的图放在该环节各自的节点输出里。

望远镜各层器件的共享场节点各自存放在对应器件 project 下的 `field/<节点号>/` 中（如 `work/<被测器件>/field/<节点号>/` 与 `work/TAICHU3/field/<节点号>/`）。

各环节与统计分析写出的主要内容如下：

- **上游各环节节点（[`deposit`](../stages/deposit.md) 至 [`reconstruction`](../stages/reconstruction.md)）**：`deposit` 节点的 `deposit.h5` 记录全部 $N$ 层平面的能量沉积步与电离对（坐标 $\mu\text{m}$、时间 $\text{s}$、能量 $\text{MeV}$、电离对数 对）。各层在作业节点里分别保存对应的感应电流与净收集电荷（`current.<位置>.h5`，时间 $\text{s}$、电流 $\text{A}$、电荷 $\text{C}$）、前端读出模拟电压波形（`readout.<位置>.h5`，时间 $\text{s}$、电压 $\text{V}$）、数字化量化码波形（`digitizer.<位置>.h5`，量化整型码 `code`［`int16`，无量纲］与换算属性 `lsb_V`［$\text{V}$］、`offset_V`［$\text{V}$］、`sampling_period`［$\text{s}$］、`bits`［位］，格式见 [`stages/digitizer.md`](../stages/digitizer.md)）、触发记录事例（`trigger.h5`，被记录事例的事例号数据集 `event`［`int64`］），以及逐事例团簇聚类得到的击中位置（$\mu\text{m}$）、团簇大小（个）与直线径迹拟合结果（`reconstruction.<位置>.h5`）。
- **空间分辨统计与图像（[`analysis`](../stages/analysis.md)）**：`events.h5` 每个选中事例一行，记径迹参数与各层的全局击中位置、残差；`result.json` 的 `residual.<槽位>.x`、`residual.<槽位>.y` 给出各块被测器件 $x$、$y$ 方向残差的截断高斯拟合结果，其中 `sigma` 为残差标准差 $\sigma_{\text{Tol}}$（$\mu\text{m}$）；`residual_<槽位>` 图画出残差分布与拟合曲线。

各环节节点的 `plots/` 里画下面这些图（规矩见[出图](../supports/figures.md)）：

| 环节 | 图名 | 画的是 | 张数 |
| --- | --- | --- | --- |
| deposit | `geometry` | 望远镜的 Geant4 几何和前 `deposit.plots` 个事例的径迹 | 每个节点一张 |
| reconstruction | `hitmap_<槽位>` | 该层恰有一个团簇的记录事例的团簇重心在层局部坐标中的二维分布（`x [μm]`、`y [μm]`，色标为团簇数） | 每层一张 |
| analysis | `track_<事例号>` | 左：$x$-$z$；右：$y$-$z$。各层团簇重心（参考层实心、被测器件空心）与式 (2) 的拟合直线（`z [mm]`、`x [μm]`、`y [μm]`） | 前 `analysis.plots` 个选中事例 |
| analysis | `residual_<槽位>` | 左：$r_x$；右：$r_y$。被测器件残差分布（`Residual x [μm]`、`Events`）与高斯拟合曲线，标出 $\sigma_{\text{Tol}}$ | 每块被测器件一张 |

![一层 TAICHU3 的像素收集电子数](../images/telescope-pixel-charge.png)

一层 `TAICHU3` 上一个事例各像素收集到的电子数（$60 \times 60$ 像素阵列，横轴 `X` 为像素列编号，纵轴 `Y` 为像素行编号，竖轴为收集电子数，单位：个）。
