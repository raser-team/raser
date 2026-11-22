# 数字化器（`core/digitizer`）

`src/raser/core/digitizer/` 是[数字化环节（`stages/digitizer`）](../stages/digitizer.md)的底层模块。它接[电子学读出](readout.md)给出的各电极放大后电压波形，按[数字化器组件](../components/digitizer.md)里示波器或数字化板的设置，依次做模拟带宽滤波、采样和量化，得到每个事例的码和每个电极被截的点数。数字化环节把结果写成数字波形文件，交给[触发环节（`stages/trigger`）](../stages/trigger.md)。

## 物理

### 带宽

设备的模拟前端有有限的带宽，会把波形的快沿变慢。本模块用高斯响应的低通代表它，幅频响应为：

$$|H(f)| = \exp\!\left(-\frac{\ln 2}{2}\left(\frac{f}{B}\right)^2\right) \tag{1}$$

对应的冲激响应是高斯函数，其时间宽度与阶跃响应的上升时间为：

$$\sigma_t = \frac{\sqrt{\ln 2}}{2\pi B} \tag{2}$$

$$t_r^{10\text{–}90} \approx \frac{0.34}{B} \tag{3}$$

其中：

- $f$：频率，$\text{Hz}$；
- $B$：模拟带宽，即 $|H(B)| = 1/\sqrt{2}$（$-3\ \text{dB}$）的频率，$\text{Hz}$，取组件的 `bandwidth_GHz`（乘 $10^9$）；
- $H(f)$：滤波器的频率响应（无量纲）；
- $\sigma_t$：冲激响应 $h(t) \propto \exp(-t^2 / 2\sigma_t^2)$ 的标准差，$\text{s}$；
- $t_r^{10\text{–}90}$：阶跃响应从终值的 $10\%$ 升到 $90\%$ 的时间，$\text{s}$。

响应形状固定为高斯。放大器与本模块的带宽是串联的：波形先经 `readout` 的放大器链，再经本模块的高斯滤波，输出的上升时间由这两次滤波共同决定。高斯响应与上升时间 $0.34/B$ 见文献 [3]。

### 采样

设备的采样时钟自由运行，和信号没有同步关系，所以每个事例第一个采样点相对信号的相位是随机的；每个采样时刻还带孔径抖动。第 $k$ 个采样时刻为：

$$t_k = t_0 + \varphi + k\,T_s + \delta_k,\qquad \varphi \sim U[0, T_s),\qquad \delta_k \sim \mathcal{N}(0, \sigma_a^2) \tag{4}$$

其中：

- $t_k$：第 $k$ 个采样时刻（$k = 0, 1, \dots$），$\text{s}$；
- $t_0$：`readout` 波形里该事例的起始时刻 `t0`，$\text{s}$；
- $T_s$：采样间隔，$T_s = 10^{-9}/$`sampling_rate_GSps`，$\text{s}$，`sampling_rate_GSps` 为组件的采样率（$\text{GS/s}$）；
- $\varphi$：该事例、该台设备的时钟相位，$\text{s}$，在 $[0, T_s)$ 上均匀分布；
- $\delta_k$：第 $k$ 个采样点的孔径抖动，$\text{s}$，零均值高斯分布；
- $\sigma_a$：孔径抖动的均方根，$\text{s}$，取组件的 `aperture_jitter_ps`（乘 $10^{-12}$）。

同一台设备的各通道共用 $\varphi$。孔径抖动对采样系统的影响见文献 [1]。

### 量化

$N$ 位 ADC 把满量程分成 $2^N$ 档，超出满量程的点截在最大或最小码：

$$\text{LSB} = \frac{V_{\text{FS}}}{2^N} \tag{5}$$

$$c = \min\!\left(\max\!\left(\left\lfloor \frac{V - V_{\text{off}}}{\text{LSB}} \right\rfloor + 2^{N-1},\ 0\right),\ 2^N - 1\right) \tag{6}$$

$$\hat V = \left(c - 2^{N-1} + 0.5\right)\text{LSB} + V_{\text{off}} \tag{7}$$

$$\sigma_q = \frac{\text{LSB}}{\sqrt{12}} \tag{8}$$

其中：

- $V_{\text{FS}}$：满量程，$\text{V}$，取组件的 `full_scale_V`；
- $N$：ADC 位数（无量纲），取组件的 `bits`；
- $\text{LSB}$：每档电压，$\text{V}$；
- $V$：采样时刻的电压，$\text{V}$；
- $V_{\text{off}}$：量程中心，$\text{V}$，取组件的 `offset_V`；
- $c$：码，取值 $0, 1, \dots, 2^N - 1$ 的整数；
- $\hat V$：由码换回的电压，$\text{V}$，取该档的中点；
- $\sigma_q$：未被截的点上量化误差 $V - \hat V$ 的均方根，$\text{V}$。

式 (8) 见文献 [2]。

## 算法

单个事例按以下顺序处理：

1. **读入**：取该事例各存了波形的电极的电压序列（`readout` 文件的 `voltage`，时间步 `dt`）、事例起始时刻 `t0`，以及组件的各键。
2. **带宽**：每个电极的电压序列按式 (1) 过高斯低通，$B = $`bandwidth_GHz`$\times 10^9\ \text{Hz}$。
3. **采样**：
   1. `readout` 文件属性 `electrodes` 里的读出通道数多于 `channels` 时，按 `electrodes` 的顺序每 `channels` 个分为一组，每组一台同型号设备。
   2. 每台设备从 $U[0, T_s)$ 抽一个时钟相位 $\varphi$，$T_s = 10^{-9}/$`sampling_rate_GSps` $\text{s}$。
   3. 按式 (4) 得各采样时刻，每个采样点从 $\mathcal{N}(0, \sigma_a^2)$ 抽一个孔径抖动。
   4. 在滤波后的电压序列上线性插值，取各采样时刻的电压。
4. **量化**：按式 (5)、(6) 把每个采样电压变成码；式 (6) 截断前码 $< 0$ 或 $> 2^N - 1$ 的点数逐电极记为被截点数。
5. **写出**：码、被截点数和每台设备的第一个采样时刻 $t_0 + \varphi$ 交给数字化环节写进数字波形文件。

随机量 $\varphi$、$\delta_k$ 由 `digitizer` 自己的种子抽取。这个种子由作业的种子派生（见[实验、扫描点与种子](../lifecycle/experiments.md#种子)），进 `digitizer` 节点的指纹，和 `readout` 的种子各自独立。

## 软件实现

### 模块与函数分工

- `__init__.py`：包文档字符串，声明本包用于带宽滤波、采样和量化。
- 带宽、采样与量化的函数（用 `numpy` 实现）：输入为一个事例的电压波形、组件设置和 `digitizer` 的种子，输出码、被截点数和各台设备的第一个采样时刻。

## 接口

### 设置

本模块用到的设置都来自[数字化器组件](../components/digitizer.md)：`channels`、`bits`、`bandwidth_GHz`、`aperture_jitter_ps`、`sampling_rate_GSps`、`full_scale_V`、`offset_V`，各键的单位与含义见该页的“键的含义”。带宽响应的形状固定为高斯。用 `raser digitizer` 跑时，由数字化环节读入组件并交给本模块；设法见[数字化环节](../stages/digitizer.md#设置)。

### 输入

`readout` 节点的 `readout.h5`（多位置实验为同节点下的 `readout.<位置>.h5`），由[电子学读出环节（`stages/readout`）](../stages/readout.md)写出：本模块用到属性 `electrodes`、`dt`（$\text{s}$）、`pulse_edge`，数据集 `event`、`t0`（$\text{s}$）、`count`、`stored`、`index`、`voltage`（$\text{V}$）。格式见[电子学读出（`core/readout`）](readout.md)。

### 输出：`digitizer.h5`

数字化环节把本模块的结果写进 `nodes/digitizer/<节点号>/digitizer.h5`（多位置实验为同节点下的 `digitizer.<位置>.h5`），沿用 `readout` 波形文件的稀疏存法，只存 `readout` 文件里存了波形的电极。

**文件属性（Attributes）**

| 属性名 | 类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `electrodes` | 变长字符串数组 | 无 | 读出通道名，照抄 `readout` 文件 |
| `sampling_period` | `float64` | $\text{s}$ | 采样间隔 $T_s$ |
| `lsb_V` | `float64` | $\text{V}$ | 每档电压 $\text{LSB}$ |
| `offset_V` | `float64` | $\text{V}$ | 量程中心 $V_{\text{off}}$ |
| `bits` | 整数 | 位 | ADC 位数 $N$ |
| `pulse_edge` | 变长字符串数组 | 无 | 与 `electrodes` 一一对应的脉冲方向，照抄 `readout` 文件 |
| `device` | 字符串 | 无 | 所用的数字化器组件名 |

**数据集（Datasets）**

| 数据集名 | 形状与类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `event` | `(events,)`, `int64` | 无 | 事例编号 |
| `count` | `(events,)`, `int64` | 点 | 该事例每个电极的采样点数 |
| `stored` | `(events,)`, `int64` | 个 | 该事例存了数字波形的电极数 |
| `index` | `(sum(stored),)`, `int64` | 无 | 存了的电极在 `electrodes` 中从 `0` 起的下标，按 `stored` 切分到各事例 |
| `t0` | `(sum(stored),)`, `float64` | $\text{s}$ | 该电极第一个采样点的时刻 $t_0 + \varphi$，已含所属设备的时钟相位，按 `stored` 切分到各事例；同一台设备上的电极取值相同 |
| `clipped` | `(sum(stored),)`, `int64` | 点 | 该电极被截在最大或最小码的点数 |
| `code` | `(sum(stored * count),)`, `int16` | 无 | 码 $c$，按事例与存了的电极依次展开，每个电极占所属事例的 `count` 个点 |

码按式 (7) 换回电压：$\hat V = (\texttt{code} - 2^{N-1} + 0.5)\cdot\texttt{lsb\_V} + \texttt{offset\_V}$（$\text{V}$），$N$ 取属性 `bits`；每个电极第 $k$ 个点（从 `0` 起）的标称时刻是该电极的 `t0` $+ k\cdot$`sampling_period`（$\text{s}$）。

## 参考文献

- [1] M. Shinagawa, Y. Akazawa, T. Wakimoto, “Jitter analysis of high-speed sampling systems”, IEEE J. Solid-State Circuits 25 (1990) 220, doi:10.1109/4.50307
- [2] W. R. Bennett, “Spectra of Quantized Signals”, Bell Syst. Tech. J. 27 (1948) 446, doi:10.1002/j.1538-7305.1948.tb01340.x
- [3] Keysight Technologies, “Understanding Oscilloscope Frequency Response and Its Effect on Rise-Time Accuracy”, Application Note 5988-8008EN
