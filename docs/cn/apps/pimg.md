# 质子成像（`apps/pimg`）

`pimg`（Proton Imaging，质子成像，在 `raser_app` 包里）是面向质子束流照相与断层成像的专用应用。它的探测器布局类似 [`telescope`](../bench/telescope.md)，在前后跟踪像素探测器层中间放置一个人头模型（从简化几何体 toy 模型起，可替换为细化解剖体模），读取 [探测器组件（`components/device`）](../components/device.md)、[能量沉积组件（`components/deposit`）](../components/deposit.md)、[前端读出电路组件（`components/readout`）](../components/readout.md)、[数字化器组件（`components/digitizer`）](../components/digitizer.md) 和 [触发组件（`components/trigger`）](../components/trigger.md)，依次走完 [`field`](../stages/field.md)、[`deposit`](../stages/deposit.md)、[`current`](../stages/current.md)、[`readout`](../stages/readout.md)、[`digitizer`](../stages/digitizer.md)、[`trigger`](../stages/trigger.md)、[`reconstruction`](../stages/reconstruction.md) 和 [`analysis`](../stages/analysis.md) 八个环节，输出质子穿过人头模型后的径迹位置、能量损失与水等效路径长度（WEPL）二维成像图。

## 装置与通用范式

学术界做单粒子跟踪质子成像（Proton Radiography / Proton CT）时，采用与束流望远镜一致的前后双臂位置灵敏跟踪探测器（front/rear trackers）加末端残余能量/射程探测器（energy/range detector），把被成像物体（如人头模型）放在前后跟踪臂之间。高能质子束（动能通常为 $150\ \text{MeV}$ 至 $250\ \text{MeV}$）穿过人头模型时，由上游跟踪层测出每个质子的入射位置 $\mathbf{r}_{\text{in}}$ 与方向，由下游跟踪层测出出射位置 $\mathbf{r}_{\text{out}}$ 与散射角以估计最可能路径（Most Likely Path，MLP），同时由残余能量探测器测出质子出射动能 $E_{\text{out}}$；对路径上的能量损失求积分即可重建出被测物体在投影平面 $(x, y)$ 上的水等效路径长度（Water Equivalent Path Length，WEPL）：

$$\Delta E = E_{\text{in}} - E_{\text{out}}, \qquad \text{WEPL}(x, y) = \int_{\text{MLP}} \rho_{s}(\mathbf{r})\,dl = \int_{E_{\text{out}}}^{E_{\text{in}}} \frac{dE}{S_{\text{water}}(E)} \tag{1}$$

其中：

- $E_{\text{in}}$、$E_{\text{out}}$：质子进入人头模型前的入射动能与穿出后的残余动能，$\text{MeV}$；$\Delta E$ 为质子穿过模型损失的能量，$\text{MeV}$；
- $dl$：沿最可能路径（MLP）的路径微元，$\text{mm}$；
- $\rho_{s}(\mathbf{r}) = S(\mathbf{r}, E) / S_{\text{water}}(E)$：位置 $\mathbf{r}$ 处组织材料相对于液态水的相对阻止本领（Relative Stopping Power，RSP，无量纲），其中 $S(\mathbf{r}, E)$ 为该处组织材料的线阻止本领，$\text{MeV/mm}$；
- $S_{\text{water}}(E) = -(dE/dl)_{\text{water}}$：质子在液态水中的线阻止本领，$\text{MeV/mm}$；
- $\text{WEPL}(x, y)$：投影坐标 $(x, y)$（单位 $\mu\text{m}$ 或 $\text{mm}$）处沿质子路径积分的水等效路径长度，$\text{mm}$。

在 RASER 的 `pimg` 中，Geant4 装置沿用 [`telescope`](../bench/telescope.md) 的多层像素跟踪平面排布（如前后各若干层 `TAICHU3` 或 SiC 像素层），在望远镜中心区域放置一个人头模型（默认提供由同心球壳或椭球构成的颅骨加脑组织简化 `toy` 模型，并支持通过 `gdml_import` 导入细化的头部几何或医学体模），从而在同一套仿真链中同时评估跟踪探测器空间分辨、多次库仑散射和能量分辨对成像质量的影响。质子照相与断层成像的物理范式与探测器系统见文献 [1]（R. P. Johnson, “Review of medical radiography and tomography with proton beams”, *Rep. Prog. Phys.* 81 (2018) 016701, doi:10.1088/1361-6633/aa8b1d）。

## 用到的环节和组件

### 环节

- [`field`](../stages/field.md)：复用各跟踪层与能量测量器件在工作偏压下的场节点；找不到场时在作业开始前补算，存进 `work/<器件>/field/nodes/<节点号>/`。
- [`deposit`](../stages/deposit.md)：用 Geant4 模拟质子束依次穿过上游跟踪层、中间人头模型（`toy` 几何或导入的细化模型）、下游跟踪层与末端能量探测器的能量沉积步。
- [`current`](../stages/current.md)：计算各像素跟踪层与能量探测器上的载流子收集电荷和感应电流。
- [`readout`](../stages/readout.md)、[`digitizer`](../stages/digitizer.md)、[`trigger`](../stages/trigger.md)：求解各层探测器的前端放大波形、数字化采样量化与符合触发。
- [`reconstruction`](../stages/reconstruction.md)：读 `digitizer` 节点里被 `trigger` 记录的事例，把量化码换回电压（$\text{V}$），在上下游像素跟踪层上做击中团簇聚类，重建单质子入射与出射径迹。
- [`analysis`](../stages/analysis.md)：局限：`analysis` 现在只统计单电极的结果，多电极、多位置的统计（例如 telescope 的残差、cflm 各焊盘的汇总）还没做。

### 组件

- [探测器组件（`components/device`）](../components/device.md)：提供上下游像素跟踪探测器（如 `TAICHU3.json`）及被测/能量探测器定义。
- [能量沉积组件（`components/deposit`）](../components/deposit.md)：提供面照明质子束流组件以及在望远镜中间放置人头模型（`toy` 头部模型或 GDML 细化头部模型）的 Geant4 装置脚本。
- [前端读出电路组件（`components/readout`）](../components/readout.md)、[数字化器组件（`components/digitizer`）](../components/digitizer.md)、[触发组件（`components/trigger`）](../components/trigger.md)：提供读出放大器链、数字化采样和触发配置。

## 跑法与配置

直接运行 `pimg` 应用，或用 `--set`、`--scan` 扫描跟踪层器件参数（器件写在 `config.json` 中，可作扫描轴；命令行用法见[命令行接口](../cli.md#命令)）：

```bash
raser pimg
```

实验配置写在 `work/pimg/config.json` 中，按环节分段。这个情景需要两类能量沉积组件：质子束流源 `beam/proton`，以及前后望远镜层中间放 toy 人头的装置 `head_phantom`，在 `deposit` 段里选装置 `head_phantom`，它的 `source` 块写 `{"name": "beam/proton", "angle": 0}`；跟踪层器件默认是 `TAICHU3`。下面只摘和本页有关的段；`examples/pimg/config.json` 里八段都写全。

```json
{
  "workflow": "pimg",
  "field": {
    "voltage": null
  },
  "deposit": {
    "g4setup": "head_phantom"
  },
  "readout": {
    "amplifier": "SantaCruz+Gali52+Termination50"
  },
  "reconstruction": {
    "threshold": 10.0,
    "amplitude_threshold": 10.0
  }
}
```

使用者能设的配置键如下表。“示例里的值”是 `examples/pimg/config.json` 写的值；`config.json` 缺了要用的键时报错，指出缺的“段.键”：

| 段.键 | 示例里的值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `field.voltage` | `null`（取器件文件里的偏压） | $\text{V}$ | 探测器偏置电压 |
| `readout.amplifier` | `"SantaCruz+Gali52+Termination50"` | 无 | 前端放大器与终端负载组件链 |
| `reconstruction.threshold`, `reconstruction.amplitude_threshold` | `10.0`, `10.0` | $\text{mV}$ | 像素过阈阈值与团簇种子通道幅度阈值（在被 `trigger` 记录的事例里找到种子的记为 `selected`） |

其余底层物理与数值参数（材料平均电离能与 Fano 因子、2D/3D 感应电流时间箱宽 `50e-12 s` 与漂移时间步长 `20e-12 s`、聚类邻域距离容差 `1e-7 um^2`）写死在代码里。

## 输出

结果存放在 `work/pimg/` 下（存放结构见[架构总纲](../architecture.md#结果)）：各环节节点按输入指纹存放在 `work/pimg/nodes/<环节>/<节点号>/`（各带一份 `node.json`；`deposit` 到 `reconstruction` 每个作业一个节点，`analysis` 每个扫描点一个节点），按扫描点命名的软链接视图位于 `work/pimg/points/<点名>/<环节>/<作业号>`（`points/<点名>/field` 和 `points/<点名>/analysis` 各是一个软链接），参数表为 `work/pimg/points.json`，所用器件的场节点存放在 `work/<器件>/field/nodes/<节点号>/`，跨点统计与对比图存放在 `work/pimg/analysis/` 下。

输出的数据文件与图像如下表：

| 文件名 | 写出环节 | 内容 | 单位 |
| --- | --- | --- | --- |
| `deposit.h5`, `current.<layer>.h5`, `readout.<layer>.h5`, `digitizer.<layer>.h5`, `trigger.<layer>.h5`, `reconstruction.h5` | `deposit` 至 `reconstruction` | 各作业节点内全层能量沉积步、各层像素感应电流与收集电荷、前端读出电压波形、数字化量化码（格式见[`stages/digitizer`](../stages/digitizer.md)）、被触发记录的事例号 `event`（`int64`）以及逐质子入射/出射团簇位置重建表 | 坐标 $\mu\text{m}$，时间 $\text{s}$，能量 $\text{MeV}$，电荷 $\text{C}$，电流 $\text{A}$，电压 $\text{V}$ |
| `points/<点名>/analysis/` | [`analysis`](../stages/analysis.md) | 局限：`analysis` 现在只统计单电极的结果，多电极、多位置的统计（例如 telescope 的残差、cflm 各焊盘的汇总）还没做。 | 无 |
