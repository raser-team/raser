# 氢硼聚变（`apps/hbf`）

`hbf`（Hydrogen–Boron Fusion，氢硼聚变 $\text{p}\text{–}{}^{11}\text{B}$，在 `raser_app` 包里）是面向激光或加速器驱动氢硼聚变 $\alpha$ 粒子诊断的专用应用。它以 SiC AC-LGAD（碳化硅交流耦合低增益雪崩探测器）像素器件为主体，读取 [探测器组件（`components/device`）](../components/device.md)、[能量沉积组件（`components/deposit`）](../components/deposit.md)、[前端读出电路组件（`components/readout`）](../components/readout.md)、[数字化器组件（`components/digitizer`）](../components/digitizer.md) 和 [触发组件（`components/trigger`）](../components/trigger.md)，依次走完 [`field`](../stages/field.md)、[`deposit`](../stages/deposit.md)、[`current`](../stages/current.md)、[`readout`](../stages/readout.md)、[`digitizer`](../stages/digitizer.md)、[`trigger`](../stages/trigger.md)、[`reconstruction`](../stages/reconstruction.md) 和 [`analysis`](../stages/analysis.md) 八个环节，输出聚变 $\alpha$ 粒子在像素阵列上的击中时间和流强分布。

## 装置与通用范式

学术界在激光或质子束驱动的氢硼无中子聚变（$\text{p} + {}^{11}\text{B} \to 3\alpha + 8.68\ \text{MeV}$）实验中，在靶室周围布置耐强电磁脉冲、抗辐照且对可见光盲的宽禁带碳化硅（4H-SiC）探测器，利用飞行时间法（Time-of-Flight，ToF）与像素化空间读出同时测量聚变产生的几 $\text{MeV}$ $\alpha$ 粒子的到达时刻与角分布流强，以标定聚变反应产额与能谱。

在 RASER 的 `hbf` 中，聚变反应产生的 $\alpha$ 粒子（主峰动能约 $2.9\ \text{MeV}$ 至 $4.0\ \text{MeV}$）从聚变靶源射向距离为 $L_{\text{ToF}}$ 的 SiC AC-LGAD 像素器件。单个像素 $(i_x, i_y)$ 测得的 $\alpha$ 粒子击中时间 $t_{\text{hit}}$ 与时间箱 $[t, t + \Delta t]$ 内的粒子流强 $\Phi_{i_x, i_y}(t)$ 为：

$$\text{p} + {}^{11}\text{B} \longrightarrow 3\,{}^{4}\text{He} + 8.68\ \text{MeV}, \qquad t_{\text{hit}} = t_{0} + L_{\text{ToF}}\sqrt{\frac{m_{\alpha}}{2 E_{\alpha}}}, \qquad \Phi_{i_x, i_y}(t) = \frac{N_{i_x, i_y}(t,\, t + \Delta t)}{p_x p_y \times 10^{-8}\,\Delta t} \tag{1}$$

其中：

- $t_0$：聚变反应发生时刻，$\text{s}$；$L_{\text{ToF}}$ 为靶源到像素器件入射面的飞行距离，$\text{m}$；
- $m_{\alpha}$、$E_{\alpha}$：$\alpha$ 粒子静止质量与动能，换算为国际单位后为 $\text{kg}$ 与 $\text{J}$（源配置中动能以 $\text{MeV}$ 给出）；
- $t_{\text{hit}}$：$\alpha$ 粒子到达像素器件并由重建波形提取的击中时刻（`ToA` 或 `CFD`），$\text{s}$；
- $N_{i_x, i_y}(t, t + \Delta t)$：像素 $(i_x, i_y)$ 在时间区间 $[t, t + \Delta t]$ 内记录到的 $\alpha$ 粒子击中数（高通量下由像素收集电荷除以单粒子平均倍增电荷折算），个；
- $p_x, p_y$：SiC AC-LGAD 像素在 $x$、$y$ 方向的间距，$\mu\text{m}$（乘以 $10^{-8}\ \text{cm}^2/\mu\text{m}^2$ 换算为单像素面积 $\text{cm}^2$）；
- $\Delta t$：流强统计时间箱宽度，$\text{s}$；
- $\Phi_{i_x, i_y}(t)$：像素 $(i_x, i_y)$ 在时刻 $t$ 测得的 $\alpha$ 粒子流强，$\text{cm}^{-2}\cdot\text{s}^{-1}$。

SiC AC-LGAD 器件中的雪崩倍增由 [`core/current`](../core/current.md) 的 `CalCurrentGain`（配合 4H-SiC `"Hatakeyama"` 碰撞电离模型）计算，阻性层与介电耦合层的电荷共享网络由 [`core/field/circuit_parameters.py`](../core/field.md) 的 `device_grid` 构建。氢硼聚变 $\alpha$ 粒子产生与飞行时间诊断的通用实验方法见文献 [1]（L. Giuffrida et al., “High-current stream of energetic $\alpha$ particles from laser-driven proton-boron fusion”, *Phys. Rev. E* 101 (2020) 013204, doi:10.1103/PhysRevE.101.013204）。

## 用到的环节和组件

### 环节

- [`field`](../stages/field.md)：复用 SiC AC-LGAD 像素器件在工作偏压下的电场、增益层分布与权重场节点；找不到场时在作业开始前补算，存进 `work/<器件>/field/<节点号>/`。
- [`deposit`](../stages/deposit.md)：用 Geant4 模拟氢硼聚变源发出的 $\alpha$ 粒子在靶室几何与 SiC AC-LGAD 像素器件表层的能量沉积与电离对生成。
- [`current`](../stages/current.md)：模拟电子和空穴在 SiC 倍增场中的漂移与 `"Hatakeyama"` 雪崩倍增，计算各 RC 格点的感应电流。
- [`readout`](../stages/readout.md)：将感应电流送入 AC-LGAD 的二维阻性层与交流耦合电容网格（`device_grid`）及前端放大器链，求解各像素通道的输出电压波形。
- [`digitizer`](../stages/digitizer.md) 与 [`trigger`](../stages/trigger.md)：对各像素通道波形做数字化采样量化与过阈触发判选。
- [`reconstruction`](../stages/reconstruction.md)：读 `digitizer.h5` 里被 `trigger` 记录的事例，把量化码换回电压（$\text{V}$），从像素波形中提取每个击中的到达时刻（`ToA`、`CFD`）、幅度与像素团簇位置。
- [`analysis`](../stages/analysis.md)：局限：`analysis` 现在只统计单电极的结果，多电极、多位置的统计（例如 telescope 的残差、cflm 各焊盘的汇总）还没做。

### 组件

- [探测器组件（`components/device`）](../components/device.md)：提供配置了 `"material": "SiC"`、`"electrodes": "pixel"`、`"enable_gain": true`、`"avalanche_model": "Hatakeyama"` 与 `"resistive_layer"`（含 `"coupling"` 介电层）的 SiC AC-LGAD 像素器件定义。
- [能量沉积组件（`components/deposit`）](../components/deposit.md)：提供氢硼聚变 $\alpha$ 粒子源与飞行时间靶室 Geant4 装置定义。
- [前端读出电路组件（`components/readout`）](../components/readout.md)、[数字化器组件（`components/digitizer`）](../components/digitizer.md)、[触发组件（`components/trigger`）](../components/trigger.md)：提供多通道前端放大器链、数字化采样和触发阈值配置。

## 跑法与配置

直接运行 `hbf` 应用，或用 `--set`、`--scan` 扫描器件偏压和阻性层方阻（器件写在 `config.json` 中，可作扫描轴；命令行用法见[命令行接口](../cli.md#命令)）：

```bash
raser hbf
raser hbf --scan field.voltage=400,500
```

实验配置写在 `work/hbf/config.json` 中，按环节分段。这个情景需要三类组件：SiC AC-LGAD 像素器件（器件组件），氢硼聚变产生的 α 粒子源 `fusion/pB11_alpha` 和靶室到器件的飞行距离装置 `target_chamber`（都是能量沉积组件），在 `deposit` 段里选装置 `target_chamber`，它的 `source` 块写 `{"name": "fusion/pB11_alpha", "angle": 0}`。下面只摘和本页有关的段；`examples/hbf/config.json` 里八段都写全。

```json
{
  "workflow": "hbf",
  "field": {
    "voltage": null,
    "irradiation_flux": null
  },
  "deposit": {
    "g4setup": "target_chamber"
  },
  "readout": {
    "amplifier": "SantaCruz+Gali52+Termination50",
    "sheet_resistance": null
  },
  "reconstruction": {
    "threshold": 10.0,
    "amplitude_threshold": 10.0
  }
}
```

使用者能设的配置键如下表。“示例里的值”是 `examples/hbf/config.json` 写的值；`config.json` 缺了要用的键时报错，指出缺的“段.键”：

| 段.键 | 示例里的值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `field.voltage` | `null`（取器件文件里的偏压） | $\text{V}$ | SiC AC-LGAD 像素器件反向偏置电压 |
| `field.irradiation_flux` | `null`（取器件文件里的辐照注量，器件文件没有辐照块时为 `0`） | $\text{cm}^{-2}$ | 器件辐照注量（$1\ \text{MeV}$ 中子等效注量） |
| `readout.amplifier` | `"SantaCruz+Gali52+Termination50"` | 无 | 以 `+` 连接的前端放大器与终端负载组件链 |
| `readout.sheet_resistance` | `null`（取器件文件里阻性层的方块电阻） | $\Omega$ | 覆盖 AC-LGAD 阻性电荷共享层的方块电阻 |
| `reconstruction.threshold`, `reconstruction.amplitude_threshold` | `10.0`, `10.0` | $\text{mV}$ | 像素波形过阈定时阈值与团簇种子通道幅度阈值（在被 `trigger` 记录的事例里找到种子的记为 `selected`） |

其余底层物理与数值参数（4H-SiC 电子-空穴对产生能 `7.83 eV`（A. Gsponer et al., NIM A 1064 (2024) 169412, doi:10.1016/j.nima.2024.169412）与 Fano 因子 `0.128`（S. K. Chaudhuri, K. J. Zavalla, K. C. Mandal, Appl. Phys. Lett. 102 (2013) 031109, doi:10.1063/1.4776703）、漂移时间窗与时间步长档位、`ngspice` 噪声分析频率下限 `1e3 Hz` 与温度 `27 °C`、重建基线采样点数 `200`）写死在 `core` 各模块代码里。迁移率模型按名字注册，器件文件按名字选用；4H-SiC 缺省选用 `"Das"`。

## 输出

结果存放在 `work/hbf/` 下（存放结构见[架构总纲](../architecture.md#结果)）：各环节节点按输入指纹存放在 `work/hbf/nodes/<环节>/<节点号>/`（各带一份 `node.json`；`deposit` 到 `reconstruction` 每个作业一个节点，`analysis` 每个扫描点一个节点），按扫描点命名的软链接视图位于 `work/hbf/points/<点名>/<环节>/<作业号>`（`points/<点名>/field` 和 `points/<点名>/analysis` 各是一个软链接），参数表为 `work/hbf/points.json`，器件场节点存放在 `work/<器件>/field/<节点号>/`，跨点统计与趋势图存放在 `work/hbf/analysis/` 下。

输出的数据文件与图像如下表：

| 文件名 | 写出环节 | 内容 | 单位 |
| --- | --- | --- | --- |
| `deposit.h5`, `current.h5`, `readout.h5`, `digitizer.h5`, `trigger.h5`, `reconstruction.h5` | `deposit` 至 `reconstruction` | 各作业节点内记录的 $\alpha$ 粒子沉积步、AC-LGAD 各像素感应电流、耦合读出电压波形、数字化量化码（格式见[`stages/digitizer`](../stages/digitizer.md)）、被触发记录的事例号 `event`（`int64`）与逐事例像素定时/幅度重建表 | 坐标 $\mu\text{m}$，时间 $\text{s}$，能量 $\text{MeV}$，电流 $\text{A}$，电压 $\text{V}$ |
| `points/<点名>/analysis/` | [`analysis`](../stages/analysis.md) | 局限：`analysis` 现在只统计单电极的结果，多电极、多位置的统计（例如 telescope 的残差、cflm 各焊盘的汇总）还没做。 | 无 |
