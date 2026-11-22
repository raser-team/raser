# 数字化器（`core/digitizer`）

`src/raser/core/digitizer/` 是[数字化环节（`stages/digitizer`）](../stages/digitizer.md)的底层模块。它接[电子学读出](readout.md)给出的各电极放大后电压波形，按[数字化器组件](../components/digitizer.md)里示波器或数字化板的设置，依次做模拟带宽、采样和量化，得到每个事例的码和每个电极被截的点数。数字化环节把结果写成数字波形文件，交给[触发环节（`stages/trigger`）](../stages/trigger.md)。

## 物理

### 带宽

组件的 `response` 选带宽的响应：

$$|H(f)| = \begin{cases} 1, & f \le B \\ 0, & f > B \end{cases}\quad(\texttt{"brickwall"}),\qquad |H(f)| = 1\quad(\texttt{"none"}) \tag{1}$$

其中：

- $f$：频率，$\text{Hz}$；
- $B$：模拟带宽，$\text{Hz}$，取组件的 `bandwidth_GHz`（乘 $10^9$）；
- $H(f)$：响应（无量纲），零相位。

`"brickwall"` 是理想砖墙，阶跃响应的 $10\%$–$90\%$ 上升时间为 $0.446/B$（$B = 6\ \text{GHz}$ 时 $74\ \text{ps}$），前后各有约 $9\%$ 的振铃。`MXR608A` 用砖墙滤波，数据手册给上升时间 $71.7\ \text{ps}$（$0.43/B$）[1]。理想砖墙是待核的近似：过渡带的形状待按数据手册核定。`"none"` 不限带宽，用于 toy 设备。

### 采样

设备的采样时钟自由运行，和信号没有同步关系，所以每个事例第一个采样点相对信号的相位是随机的；每个采样时刻还带孔径抖动。第 $k$ 个采样时刻为：

$$t_k = t_0 + \varphi + k\,T_s + \delta_k,\qquad \varphi \sim U[0, T_s),\qquad \delta_k \sim \mathcal{N}(0, \sigma_a^2),\qquad k = 0, 1, \dots, K-1,\qquad K = \left\lfloor \frac{n_{\text{bin}}\,\Delta t}{T_s} \right\rfloor \tag{2}$$

其中：

- $t_0$：`readout` 波形里该事例第一个时间箱的左沿 `t0`，$\text{s}$；`readout` 的电压取在各时间箱的中心 $t_0 + (i + \tfrac12)\Delta t$；
- $T_s$：采样间隔，$T_s = 10^{-9}/$`sampling_rate_GSps`，$\text{s}$；
- $\varphi$：该事例、该台设备的时钟相位，$\text{s}$；同一台设备的各通道共用；
- $\delta_k$：第 $k$ 个采样点的孔径抖动，$\text{s}$；$\sigma_a$ 取组件的 `aperture_jitter_ps`（乘 $10^{-12}$），见文献 [2]；
- $n_{\text{bin}}$、$\Delta t$：该事例 `readout` 波形的时间箱数和箱宽（$\text{s}$）；
- $K$：每个电极的采样点数，同一事例各电极相同。

记录窗由上游的波形长度决定。

### 量化

$N$ 位 ADC 把满量程分成 $2^N$ 档，超出满量程的点截在最大或最小码：

$$\text{LSB} = \frac{V_{\text{FS}}}{2^N} \tag{3}$$

$$c = \min\!\left(\max\!\left(\left\lfloor \frac{V - V_{\text{off}}}{\text{LSB}} \right\rfloor + 2^{N-1},\ 0\right),\ 2^N - 1\right) \tag{4}$$

$$\hat V = \left(c - 2^{N-1} + 0.5\right)\text{LSB} + V_{\text{off}} \tag{5}$$

其中：

- $V_{\text{FS}}$：满量程，$\text{V}$，取组件的 `full_scale_V`；
- $N$：ADC 位数，取组件的 `bits`；
- $V$：采样时刻的电压，$\text{V}$；
- $V_{\text{off}}$：量程中心，$\text{V}$，取组件的 `offset_V`；
- $c$：码，取值 $0, 1, \dots, 2^N - 1$；
- $\hat V$：由码换回的电压，$\text{V}$，取该档的中点。

未被截的点上，量化误差 $V - \hat V$ 的均方根为 $\text{LSB}/\sqrt{12}$（文献 [3]）。

### 纯噪声道

`readout` 的噪声是平稳高斯噪声，按单边幅度谱密度 $S_V(f)$ 抽取，和信号线性相加，各输出之间互不相关（见[电子学读出](readout.md#给定谱的频域热噪声与时域合成)）。只有噪声的道经带宽和采样后仍是平稳高斯序列，它的谱是：

$$S_d^2(f) = \sum_{m=-\infty}^{\infty} S_V^2\!\left(|f + m f_s|\right)\,\bigl|H(f + m f_s)\bigr|^2,\qquad 0 \le f \le \frac{f_s}{2} \tag{6}$$

其中：

- $f_s = 1/T_s$：采样率，$\text{Hz}$；
- $S_V(f)$：该道的噪声谱资产（见“接口”），$\text{V}/\sqrt{\text{Hz}}$，资产频段之外取零；
- $S_d(f)$：采样后序列的单边幅度谱密度，$\text{V}/\sqrt{\text{Hz}}$。

纯噪声道用 `readout` 同一个合成方法（[电子学读出](readout.md#给定谱的频域热噪声与时域合成)的式 (5)–(9)），以 $S_d$ 为谱、$T_s$ 为步长直接抽出 $K$ 个采样电压，再按式 (4) 量化；孔径抖动不改变平稳噪声的统计，这里不加。一条道走不走纯噪声道，由上游在 `current` 之前决定，判断函数见“接口”。

## 算法

单个事例按以下顺序处理：

1. **读入**：该事例各存了波形的电极的电压序列（`readout` 文件的 `voltage`，时间步 `dt`）、`t0`，以及组件的各键。
2. **分组与相位**：`readout` 文件属性 `electrodes` 里的通道数多于 `channels` 时，按 `electrodes` 的顺序每 `channels` 个分为一组，每组一台同型号设备。每台设备从 $U[0, T_s)$ 抽一个 $\varphi$，每个电极的每个采样点从 $\mathcal{N}(0, \sigma_a^2)$ 抽一个 $\delta_k$。
3. **带宽与采样**：每个电极的电压序列减去连接首末两点的直线 $l(t)$，余下部分做离散傅里叶变换得 $X_j$，在式 (2) 的各采样时刻求

   $$V(t) = l(t) + \frac{1}{n_{\text{bin}}}\operatorname{Re}\sum_{j} w_j\,X_j\,|H(f_j)|\,\mathrm{e}^{\mathrm{i}2\pi f_j (t - t_{c})} \tag{7}$$

   其中 $f_j = j/(n_{\text{bin}}\Delta t)$，$t_c = t_0 + \Delta t/2$，$w_0 = 1$、内部频点 $w_j = 2$、$n_{\text{bin}}$ 为偶数时奈奎斯特频点 $w = 1$。式 (7) 是带限插值：`readout` 的波形只含其奈奎斯特频率以下的成分，带限插值对它是精确的。
4. **量化**：按式 (3)、(4) 得码；截断前码 $< 0$ 或 $> 2^N - 1$ 的点数逐电极记为被截点数。
5. **纯噪声道**：该事例列为纯噪声的各道，按式 (6) 由它的噪声谱资产得 $S_d$，抽 $K$ 个电压再量化；$K$、$\varphi$ 与同一事例的其他道相同。同一条谱的 $S_d$ 只算一次。
6. **写出**：码、被截点数和各电极第一个采样点的时刻 $t_0 + \varphi$ 交给数字化环节写进数字波形文件。

$\varphi$、$\delta_k$ 和纯噪声由 `digitizer` 自己的种子抽取。这个种子由作业的种子派生（见[实验、扫描点与种子](../lifecycle/experiments.md#种子)），进 `digitizer` 节点的指纹，和 `readout` 的种子各自独立。每台设备的 $\varphi$ 由种子、事例号和设备号决定；每个电极的 $\delta_k$ 和纯噪声由种子、事例号和该电极在 `electrodes` 里的下标决定。

## 软件实现

### 模块与函数分工

- `__init__.py`：包文档字符串。
- `settings.py`：`DigitizerSettings`，由组件字典建成，缺键、多键或取值越界时报错。
- `bandwidth.py`：式 (1) 的响应与式 (7) 的带限插值。
- `sampling.py`：分组、相位与式 (2)。
- `quantize.py`：式 (3)–(5)。
- `noise_only.py`：式 (6)、纯噪声道的码，以及判断函数 `noise_only_channels`。
- `digital_waveforms.py`：数字波形文件的写与读。
- `job.py`：`write_digitized`，一个作业从 `readout` 文件到数字波形文件。
- `draw.py`：本环节的图。
- `regincr.py`、`regincr_sim.py`：legacy：`pymtl3` 的 8 位寄存器自增器示例，留作将来纯数字逻辑的参考，和采样量化无关。

## 接口

### 设置

本模块用到组件里触发条件以外的键：`channels`、`bits`、`max_sampling_rate_GSps`、`response`、`bandwidth_GHz`、`aperture_jitter_ps`、`sampling_rate_GSps`、`full_scale_V`、`offset_V`，单位与含义见[数字化器组件](../components/digitizer.md#键的含义)。

### 输入

`readout` 节点的 `readout.h5`（多位置实验为同节点下的 `readout.<位置>.h5`），由[电子学读出环节（`stages/readout`）](../stages/readout.md)写出：本模块用到属性 `electrodes`、`dt`（$\text{s}$）、`pulse_edge`，数据集 `event`、`t0`（$\text{s}$）、`count`、`stored`、`index`、`voltage`（$\text{V}$）。

纯噪声道另需：

- **噪声谱资产**：一种器件、偏压和放大器链唯一确定各输出的噪声谱 $S_V(f)$，由 `readout` 算出，实验通用；本模块只读。
- **纯噪声道列表**：每个事例列为纯噪声的电极下标，由上游给出。
- **`noise_only_channels(deposited_keV, trigger_places, cut_keV)`**：`deposited_keV` 为该事例每个电极对应区域里的沉积能量（$\text{keV}$，按电极下标），`trigger_places` 为触发用到的电极下标，`cut_keV` 为使用者给的能量 cut；返回沉积能量低于 cut、且不在 `trigger_places` 里的电极下标。

### 输出：`digitizer.h5`

数字化环节把本模块的结果写进 `nodes/digitizer/<节点号>/digitizer.h5`（多位置实验为同节点下的 `digitizer.<位置>.h5`），沿用 `readout` 波形文件的稀疏存法：存 `readout` 文件里存了波形的电极和纯噪声道。

**文件属性（Attributes）**

| 属性名 | 类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `electrodes` | 变长字符串数组 | 无 | 读出通道名，照抄 `readout` 文件 |
| `sampling_period` | `float64` | $\text{s}$ | 采样间隔 $T_s$ |
| `lsb_V` | `float64` | $\text{V}$ | 每档电压 $\text{LSB}$ |
| `offset_V` | `float64` | $\text{V}$ | 量程中心 $V_{\text{off}}$ |
| `bits` | 整数 | 位 | ADC 位数 $N$ |
| `channels` | 整数 | 个 | 一台设备的通道数 |
| `pulse_edge` | 变长字符串数组 | 无 | 与 `electrodes` 一一对应的脉冲方向，照抄 `readout` 文件 |
| `device` | 字符串 | 无 | 所用的数字化器组件名 |

**数据集（Datasets）**

| 数据集名 | 形状与类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `event` | `(events,)`, `int64` | 无 | 事例编号 |
| `count` | `(events,)`, `int64` | 点 | 该事例每个电极的采样点数 $K$ |
| `stored` | `(events,)`, `int64` | 个 | 该事例存了数字波形的电极数 |
| `index` | `(sum(stored),)`, `int64` | 无 | 存了的电极在 `electrodes` 中从 `0` 起的下标，按 `stored` 切分到各事例 |
| `t0` | `(sum(stored),)`, `float64` | $\text{s}$ | 该电极第一个采样点的时刻 $t_0 + \varphi$；同一台设备上的电极取值相同 |
| `noise_only` | `(sum(stored),)`, `bool` | 无 | 该电极是纯噪声道 |
| `clipped` | `(sum(stored),)`, `int64` | 点 | 该电极被截在最大或最小码的点数 |
| `code` | `(sum(stored * count),)`, `int16` | 无 | 码 $c$，按事例与存了的电极依次展开，每个电极占所属事例的 `count` 个点 |

码按式 (5) 换回电压；电极第 $k$ 点的时刻为该电极的 `t0` $+ k\cdot$`sampling_period`。

## 参考文献

- [1] Keysight Technologies, “Infiniium MXR-Series Oscilloscopes (A-Series)”, Data Sheet 7120-1115.EN, https://www.keysight.com/us/en/assets/7120-1115/data-sheets/Infiniium-MXR-Series.pdf
- [2] M. Shinagawa, Y. Akazawa, T. Wakimoto, “Jitter analysis of high-speed sampling systems”, IEEE J. Solid-State Circuits 25 (1990) 220, doi:10.1109/4.50307
- [3] W. R. Bennett, “Spectra of Quantized Signals”, Bell Syst. Tech. J. 27 (1948) 446, doi:10.1002/j.1538-7305.1948.tb01340.x
