# 电子学读出（`core/readout`）

`src/raser/core/readout/` 承接 [载流子漂移与感应电流](current.md) 写出的电极时域感应电流（`current.h5`）、[器件场](field.md) 构造的器件等效电路 `DeviceCircuit`、[器件定义](device.md) 的偏置与读出电极配置，以及 [前端读出电路组件](../components/readout.md) 的 SPICE 子电路文件（`.cir`）。该包将器件等效电路与前端放大器链拼入同一张 `ngspice` 网表，求解各读出通道的瞬态输出电压与频域电压噪声谱，合成时域高斯热噪声并判定脉冲边沿极性，写出 `readout.h5` 文件（多位置实验为 `readout.<位置>.h5`；另提供器件输出端对地短路电流求解与放大级原理图绘制接口）。输出的电压波形与脉冲边沿方向交给 [数字化器](digitizer.md)。

## 物理

### 电流源注入器件电路节点

载流子在器件耗尽层中漂移与倍增时，在各读出电极上产生时域分箱感应电流。在等效电路中，每个读出电极的感应电流表示为跨接在器件电路对应节点对 $(n_{\text{from},k}, n_{\text{to},k})$ 之间的独立分段线性（PWL）电流源，并在首个时间箱前补一个零电流箱使电路从静止稳态起算：

$$t_{-1} = \frac{1}{2}\Delta t, \qquad t_m = \left(m + \frac{3}{2}\right)\Delta t \quad (m = 0, 1, \dots, n_{\text{bin}} - 1) \tag{1}$$

$$I_k(t_{-1}) = 0, \qquad I_k(t_m) = \bar{I}_{k,m} \tag{2}$$

其中：

- $\Delta t$：感应电流时间箱宽度（代码变量 `dt`），$\text{s}$；
- $n_{\text{bin}}$：单个事例的时间箱数（代码变量 `bins`），箱；
- $t_{-1}$：前置静默箱中心相对于仿真起点（$t = 0$）的时刻，$\text{s}$；`ngspice` 将 PWL 源在最小时间点上的初值视为 $t \le 0$ 一直流过的稳态直流电流，故在 $t_{-1}$ 处固定置零；
- $t_m$：感应电流第 $m$ 个时间箱中心相对于仿真起点的时刻，$\text{s}$；
- $\bar{I}_{k,m}$：第 $k$ 个电极在第 $m$ 个时间箱内的平均感应电流（代码变量 `currents[k - 1, m]`），$\text{A}$；
- $I_k(t)$：注入第 $k$ 个电极电流源节点对 $(n_{\text{from},k}, n_{\text{to},k})$ 的分段线性电流，$\text{A}$；正值表示电流在电流源内部从 $n_{\text{from},k}$ 流向 $n_{\text{to},k}$（平面器件中即从耗尽层背面节点流向读出电极焊盘节点）。

时间箱中心与 PWL 电流源网表行由 `spice.py` 中的 `_bin_centres` 与 `_current_sources` 生成。器件等效电路 `DeviceCircuit` 及其电流源节点映射 `circuit.sources` 由 [器件场](field.md) 的 `planar_circuit`、`device_circuit`、`device_row` 与 `device_grid` 构建，涵盖耗尽层结电容、未耗尽层并联 RC、邻近条间互容、偏置电阻、交流耦合电容及阻性电荷共享层网络。半导体探测器等效电路与感应电流注入模型见文献 [1]，SPICE 独立分段线性源定义见文献 [2]。

### 器件电路与放大器链级联瞬态求解

感应电流注入器件电路节点后，在电极电容网络与偏置支路间分流，并经器件输出节点进入各级前端放大器子电路与末级终端负载。器件等效电路、各输出通道独立的放大级实例链与终端负载在同一张 `ngspice` 网表中联立，构成集总电路微分代数方程组，在包含前置静默箱的瞬态区间 $[0, T_{\text{tran}}]$ 上求解输出节点电压，并按分段线性插值采样回各感应电流时间箱中心：

$$T_{\text{tran}} = (n_{\text{bin}} + 1)\,\Delta t \tag{3}$$

$$V_{r,m} = V_r(t_j) + \frac{t_m - t_j}{t_{j+1} - t_j}\bigl[V_r(t_{j+1}) - V_r(t_j)\bigr] \quad (t_j \le t_m \le t_{j+1}) \tag{4}$$

其中：

- $T_{\text{tran}}$：`ngspice` 瞬态分析总时长，$\text{s}$；
- $\Delta t$：时间箱宽度及 `ngspice` `tran` 命令的步长参数，$\text{s}$；
- $t_j, t_{j+1}$：`ngspice` 瞬态求解器写出的相邻离散时刻（代码变量 `solved_times`），$\text{s}$；
- $V_r(t_j)$：第 $r$ 个读出通道输出节点（链中含放大级时为末级放大器输出与负载输入共用的节点 `out<r>`，无放大级仅含负载时为器件输出节点 `circuit.outputs`）在时刻 $t_j$ 的瞬态电压，$\text{V}$；
- $V_{r,m}$：线性插值到第 $m$ 个时间箱中心 $t_m$ 处的通道输出电压，$\text{V}$。

级联网表构建与瞬态求解由 `spice.py` 中的 `_chain`、`write_netlist`、`_transient`、`_run` 与 `solve` 实现；另由 `write_short_circuit_netlist` 与 `short_circuit_currents` 提供将器件各输出端经零电压源 `Vshort<r> <output> 0 0` 对地短路的瞬态短路电流求解。前端放大器链由 `circuit.py` 的 `named_chain` 从 [前端读出电路组件](../components/readout.md) 加载，示例 `config.json` 里 `readout.amplifier` 写的放大器链为 `"SantaCruz+Gali52+Termination50"`（见 [../stages/readout.md](../stages/readout.md)）。SPICE 改进节点分析与瞬态数值积分见文献 [2, 3]。

### 阻性层网络对一点冲击的响应

电荷 $q$（缺省 $1\ \text{fC}$）落在有阻性电荷共享层的器件上一点 $(x, y)$（单位 $\mu\text{m}$，$0 \le x \le l_x$、$0 \le y \le l_y$；只给 $x$ 一个坐标时 $y$ 取器件中线 $l_y / 2$），按这一点到相邻 RC 格点中心的距离线性分给 RC 格点； RC 格点沿 $x$ 有 $N_x$（`x_ele_num`）个、间距 $p_x$（`p_x`），沿 $y$ 有 $N_y$（`y_ele_num`）个、间距 $p_y$（`p_y`），整体在器件上居中（ RC 格点网络的电路参数见 [器件场](field.md)）。

沿单个轴（以 $x$ 为例），位置换算为以 RC 格点宽度为单位、相对首 RC 格点中心的坐标 $u$，落在两相邻 RC 格点中心之间时按距离线性分给第 $i$ 个与第 $i+1$ 个 RC 格点，超出首 RC 格点中心或末 RC 格点中心时全部分给边缘 RC 格点；两轴的份额相乘得到各二维 RC 格点的份额 $s_{ij}$，并在第一个时间箱内作为矩形电流脉冲 $\bar{I}_{n,0} = s_{ij}\, q / \Delta t$ 注入对应 RC 格点电流源，其余时间箱置零，交给上一节的瞬态求解：

$$x_0 = \frac{l_x - N_x p_x}{2}, \qquad u = \frac{x - x_0}{p_x} - \frac{1}{2} \tag{5}$$

$$s_k^{(x)} = \begin{cases} 1, & u \le 0,\ k = 0 \\ 1 - (u - i), & 0 < u < N_x - 1,\ k = i \\ u - i, & 0 < u < N_x - 1,\ k = i + 1 \\ 1, & u \ge N_x - 1,\ k = N_x - 1 \end{cases} \quad (i = \lfloor u \rfloor) \tag{6}$$

$$s_{ij} = s_i^{(x)} s_j^{(y)}, \qquad n = i N_y + j, \qquad \bar{I}_{n,m} = \begin{cases} \dfrac{s_{ij}\, q}{\Delta t}, & m = 0 \\ 0, & m > 0 \end{cases} \tag{7}$$

其中：

- $q$：注入的点电荷量（代码变量 `charge`，缺省 $10^{-15}\ \text{C}$），$\text{C}$；
- $(x, y)$：冲击点的器件平面坐标（代码变量 `point_um` 解析为 `x_um`、`y_um`），$\mu\text{m}$；
- $l_x, l_y$：器件在 $x$、$y$ 方向的尺寸（代码属性 `my_d.l_x`、`my_d.l_y`），$\mu\text{m}$；
- $N_x, N_y$： RC 格点沿 $x$、$y$ 方向的个数（代码属性 `my_d.x_ele_num`、`my_d.y_ele_num`），个；
- $p_x, p_y$： RC 格点沿 $x$、$y$ 方向的间距（代码属性 `my_d.p_x`、`my_d.p_y`），$\mu\text{m}$；
- $x_0$：居中 RC 格点阵列在 $x$ 轴上的左边界坐标（代码变量 `first_edge`，右边界为 `last_edge` $= x_0 + N_x p_x$），$\mu\text{m}$；$y$ 轴对应边界 $y_0$ 定义相同；
- $u$：以 RC 格点宽度为单位、相对首 RC 格点中心的归一化位置（代码变量 `place`），无量纲；
- $i, j$： RC 格点沿 $x$、$y$ 轴的 `0` 起下标（代码变量 `number = int(np.floor(place))`），无量纲；
- $s_k^{(x)}, s_k^{(y)}$：单轴第 $k$ 个 RC 格点分得的电荷份额（`_along` 返回字典，仅保留非零项，在 $u = i$ 时仅返回 `{i: 1.0}`），无量纲；$y$ 轴用 $l_y, N_y, p_y, y_0$ 按同一公式求得；
- $s_{ij}$：二维 RC 格点 $(i, j)$ 分得的总电荷份额（代码表达式 `part_x * part_y`），无量纲；
- $n$：二维 RC 格点在 `circuit.sources` 中的 `0` 起序号（代码变量 `number = i * y_ele_num + j`），无量纲；
- $\Delta t$：时间箱宽度（代码变量 `dt`，缺省 $10^{-11}\ \text{s}$），$\text{s}$；
- $\bar{I}_{n,m}$：第 $n$ 个 RC 格点在第 $m$ 个时间箱内的平均注入电流（代码变量 `currents[n, m]`；总时间箱数 `bins` 缺省 $2000$），$\text{A}$。

若冲击点落在 RC 格点阵列范围之外（不满足 `first_edge <= here_um <= last_edge`），`shares` 抛出 `ValueError("The point lies at <axis> = <here_um> um, and the RC nodes of the layer reach from <first_edge> to <last_edge> um")`，写明越界坐标与阵列在该轴上的范围；若电路的电流源数 `len(circuit.sources)` 与器件 RC 格点总数 `x_ele_num * y_ele_num` 不等，`impulse_response` 抛出 `ValueError("The circuit has the currents of <len(rc_nodes)> RC nodes, and <det_name> has <count>")`。

多点脉冲响应注入与 RC 格点份额分配分别由 `core/field` 的 `resistive_layer.py` 中的 `shares` 与 `network.py` 的 `impulse_response` 实现。

### 读出端口之间的导纳

器件电路各读出端口（`circuit.outputs`）之间的导纳矩阵按频率给出：第 $j$ 个读出端口加 $1\ \text{V}$ 的交流小信号电压，其余读出端口交流接地，所有感应电流源开路，由此从外面流进第 $i$ 个读出端口的电流即 $Y_{ij}$：

$$Y_{ij}(f) = \left.\frac{I_i}{V_j}\right|_{V_{k \ne j} = 0} \tag{8}$$

其中：

- $Y_{ij}$：第 $i$ 个读出端口对第 $j$ 个读出端口的导纳，$\text{S}$；
- $I_i$：流进第 $i$ 个读出端口的交流电流，$\text{A}$；
- $V_j$：第 $j$ 个读出端口上的交流电压，$\text{V}$；
- $f$：频率，$\text{Hz}$。

`network.py` 的 `admittance(circuit, frequencies_hz)` 用 `ngspice` 的交流小信号分析逐列求得：对每个 $j$，在器件电路网表上给每个读出端口 $k$ 接一个电压源 `Vport<k> <节点> 0 dc 0 ac <1 或 0>`，仅第 $j$ 个的交流幅度为 $1$，在每个给定频率上读各电压源电流的复数值，其相反数即流进器件的电流。返回形状 `(frequencies, outputs, outputs)` 的复数数组，读出端口次序同 `circuit.outputs`；`frequencies_hz` 为空、含非正数或不递增时抛出 `ValueError`。

### 给定谱的频域热噪声与时域合成

器件电路与前端放大器链中的有噪电阻及有源器件模型在工作温度下产生平稳高斯电子学噪声。代码先由 `ngspice` 小信号频域噪声分析求得输出节点在离散频率点上的单边电压噪声幅度谱密度 $S_V(f)$，再在长度为波形箱数 $M_{\text{rec}}$ 倍的扩展记录频域网格上由梯形法则积分各频带功率、独立抽取复高斯傅里叶系数，经实序列逆离散傅里叶变换（`np.fft.irfft`）截取前 $n_{\text{bin}}$ 个点合成时域噪声：

$$P(f_l) = \sum_{j=0}^{l-1} \frac{S_V^2(f_{j+1}) + S_V^2(f_j)}{2}\,(f_{j+1} - f_j) \quad (l = 0, 1, \dots, L - 1) \tag{9}$$

$$\Delta P_k = P\!\left(f_k + \frac{1}{2}\Delta f\right) - P\!\left(\max\!\left(f_k - \frac{1}{2}\Delta f,\, 0\right)\right) \quad \left(k = 0, 1, \dots, \left\lfloor \frac{N_{\text{rec}}}{2} \right\rfloor\right) \tag{10}$$

$$\sigma_k = \frac{1}{2}\,N_{\text{rec}}\sqrt{\Delta P_k} \tag{11}$$

$$X_k = \begin{cases} \mathcal{N}\!\left(0,\, N_{\text{rec}}^2 \Delta P_0\right), & k = 0 \\[4pt] \mathcal{N}(0, \sigma_k^2) + \mathrm{i}\,\mathcal{N}(0, \sigma_k^2), & 0 < k < \dfrac{N_{\text{rec}}}{2} \\[4pt] \mathcal{N}\!\left(0,\, N_{\text{rec}}^2 \Delta P_{N_{\text{rec}}/2}\right), & k = \dfrac{N_{\text{rec}}}{2}\ (\text{当 } N_{\text{rec}}\ \text{为偶数}) \end{cases} \tag{12}$$

$$v_{\text{noise}}[m] = \frac{1}{N_{\text{rec}}} \sum_{n=0}^{N_{\text{rec}}-1} \widetilde{X}_n\,\mathrm{e}^{\mathrm{i} 2\pi n m / N_{\text{rec}}} \quad (m = 0, 1, \dots, n_{\text{bin}} - 1) \tag{13}$$

其中：

- $f_0 < f_1 < \dots < f_{L-1}$：单边噪声谱的递增采样频率序列（代码变量 `frequencies_hz`），$\text{Hz}$；
- $S_V(f_l)$：频率 $f_l$ 处的单边输出电压噪声幅度谱密度（代码变量 `density`），$\text{V}/\sqrt{\text{Hz}}$；$[f_0, f_{L-1}]$ 范围外谱密度置零；
- $P(f)$：从 $0\ \text{Hz}$ 到频率 $f$ 的累积噪声功率（方差），$\text{V}^2$，在采样频率点间由 `np.interp` 线性插值，并在两端保持常数 $P(f \le f_0) = 0$、$P(f \ge f_{L-1}) = P(f_{L-1})$；
- $N_{\text{rec}} = M_{\text{rec}}\,n_{\text{bin}}$：扩展时域记录点数（代码变量 `record`），其中扩展倍数 $M_{\text{rec}} = 256$（代码常量 `RECORD`，无量纲）；
- $\Delta f = 1 / (N_{\text{rec}}\,\Delta t)$：扩展记录的傅里叶频率步长（代码变量 `step_hz`），$\text{Hz}$；$f_k = k\,\Delta f$ 为实傅里叶变换频率网格中心（代码变量 `centres`），$\text{Hz}$；
- $\Delta P_k$：频率点 $f_k$ 上下各半步频带内的噪声功率（代码变量 `in_band`），$\text{V}^2$；其中 $k = 0$ 的直流分量承接低于 $\Delta f / 2$ 的全部功率，使慢于波形时长的低频噪声表现为逐事例变化的基线偏移；
- $\sigma_k$：内部频率点复谱实部与虚部各自独立抽取零均值高斯分布的标准差（代码变量 `sigma`），$\text{V}$；在 `np.fft.irfft` 的 $1/N_{\text{rec}}$ 归一化约定下，内部频率点对时域方差的贡献为 $4\langle(\operatorname{Re} X_k)^2\rangle / N_{\text{rec}}^2 = \Delta P_k$，直流与奈奎斯特实分量的贡献为 $\langle X_k^2\rangle / N_{\text{rec}}^2 = \Delta P_k$；
- $X_k$：单边复傅里叶谱系数（代码变量 `spectrum`），$\text{V}$；$\widetilde{X}_n$ 为按共轭对称展开的双边频谱；
- $v_{\text{noise}}[m]$：第 $m$ 个时间箱中心合成的时域高斯噪声电压，$\text{V}$。

频域噪声谱由 `spice.py` 的 `output_noise_spectrum` 与 `job.py` 的 `noise_spectra` 调用 `ngspice` 在固定温度 $27\ ^\circ\text{C}$、频段 $10^3\ \text{Hz}$（`LOWEST_NOISE_HZ`）至 $0.5 / \Delta t$ 上求解；频带功率积分与时域随机合成由 `spectral_noise.py` 的 `band_power` 与 `noise_from_spectrum` 实现。`write_waveforms` 的 `noise_seed` 是必给参数，由环节传入 `readout` 自己的种子（NGspice 噪声），这个种子进 `readout` 节点的指纹；为整数时叠加噪声，为 `None` 时输出无噪声波形。导体热噪声与频域传输噪声分析见文献 [2, 4, 5]，由单边功率谱密度经复高斯频谱逆变换生成平稳高斯噪声时序的方法见文献 [6]。

### 输出脉冲的极性

读出通道输出电压脉冲相对静态基线的偏离方向（向上为正脉冲 `"rising"`，向下为负脉冲 `"falling"`）由读出电极收集的载流子电荷符号与前端放大器链的净传递极性共同决定。相对背电极处于高电势的读出电极收集电子（负电荷），处于低电势的读出电极收集空穴（正电荷）；放大器链对正输入电荷产生正响应或反相产生负响应，两者符号相乘给出输出脉冲极性：

$$V_{\text{above}} = \begin{cases} V_{\text{bias}}, & \text{若读出电极为偏置电极 } \text{bias.electrode} \\ -V_{\text{bias}}, & \text{其余读出电极（非偏置电极接地）} \end{cases} \tag{14}$$

$$s_q = \begin{cases} -1, & V_{\text{above}} > 0\ (\text{收集电子}) \\ +1, & V_{\text{above}} < 0\ (\text{收集空穴}) \end{cases}, \qquad s_{\text{chain}} = \operatorname{sgn}\!\bigl(V_{\text{probe}}(t^*) - V_{\text{probe}}(t_0)\bigr) \tag{15}$$

$$\text{edge} = \begin{cases} \text{"rising"}, & s_q \cdot s_{\text{chain}} > 0 \\ \text{"falling"}, & s_q \cdot s_{\text{chain}} < 0 \end{cases} \tag{16}$$

其中：

- $V_{\text{bias}}$：器件文件 `bias.voltage` 设定的偏置电压，$\text{V}$；
- $V_{\text{above}}$：读出电极相对于另一电极的电势差（代码变量 `above`），$\text{V}$；
- $s_q \in \{-1, +1\}$：读出电极收集的载流子电荷符号（`collected_charge_sign` 返回值，无量纲）；
- $V_{\text{probe}}(t)$：在结电容 $C_{\text{probe}} = 10^{-12}\ \text{F}$ 的探针平板电路上注入 $Q_{\text{probe}} = +10^{-15}\ \text{C}$ 正电荷时放大器链的瞬态输出电压，$\text{V}$；$V_{\text{probe}}(t_0)$ 为电荷注入前首箱（下标 `0`）的静态输出电压，$t^* = \arg\max_t |V_{\text{probe}}(t) - V_{\text{probe}}(t_0)|$ 为输出偏离静态值绝对值最大的时刻；
- $s_{\text{chain}} \in \{-1, +1\}$：放大器链对正输入电荷的净传递极性符号（`chain_sign` 返回值，同相为 $+1$，反相为 $-1$，无量纲）；
- $\text{edge}$：读出通道输出脉冲极性标识（`pulse_edges` 返回值，`"rising"` 或 `"falling"`）。

收集电荷符号判定、放大器链极性探测与各通道极性列表生成分别由 `pulse_edge.py` 中的 `collected_charge_sign`、`chain_sign` 与 `pulse_edges` 实现，探针平板电路由 [器件场](field.md) 的 `planar_circuit("probe", 1e-12)` 构造。`write_waveforms` 的 `pulse_edge` 参数缺省为 `None`（[../stages/readout.md](../stages/readout.md) 调用时传入 `pulse_edges` 的结果），写入 `readout.h5`，由 [数字化器](digitizer.md) 照抄进数字波形文件，下游据此翻转脉冲极性。探测器读出极性与前端脉冲响应见文献 [1]。

## 算法

### 内置常数

下表列出 `job.py`、`spice.py`、`spectral_noise.py`、`pulse_edge.py`、`circuit.py` 与 `schematic.py` 中的全部内置常数与写死的数值。它们是模块常量或函数内固定参数，在器件文件和 `.cir` 组件文件里都没有对应的键：

| 常数名或固定参数 | 取值 | 单位 | 定义位置与含义 |
| --- | --- | --- | --- |
| `LOWEST_NOISE_HZ` | `1e3` | $\text{Hz}$ | `job.py`，`ngspice` 频域噪声分析的起始频率下限（上限为 $0.5 / \Delta t$） |
| `PART_EDGE` | `1e-3` | 无量纲 | `job.py`，存储输出通道波形及停止条形行局部电路扩展的摆幅占当事例最大摆幅的比例阈值 |
| `PER_DECADE` | `50` | 点/十倍频程 | `spice.py`，`ngspice` `noise` 分析每十倍频程的对数采样频率点数 |
| 前置静默箱点 `(t, I)` | `(dt / 2, 0)` | $\text{s}$, $\text{A}$ | `spice.py`，`_current_sources` 在每个 PWL 电流源开头添加的零电流锚点 |
| 噪声分析交流源与温度 | `dc 0 ac 1`, `27` | $\text{A}$, $^\circ\text{C}$ | `spice.py`，`write_noise_netlist` 注入的小信号源幅值及 `ngspice` 默认噪声分析温度 |
| `RECORD` | `256` | 无量纲 | `spectral_noise.py`，`noise_from_spectrum` 频域合成记录长度相对于波形箱数 `bins` 的倍数 |
| `NO_ANSWER_V` | `1e-9` | $\text{V}$ | `pulse_edge.py`，`chain_sign` 判定放大器链对探针电荷有响应的最小输出摆幅阈值 |
| `chain_sign` 探针参数 | `dt = 10e-12`, `bins = 2000`, 第 `5` 箱注入 `1e-15` $\text{C}$, 电容 `1e-12` $\text{F}$ | $\text{s}$, 箱, $\text{C}$, $\text{F}$ | `pulse_edge.py`，测试放大器链净极性的单电极平板探针输入 |
| `SCALES` | `t`: `1e12`, `g`: `1e9`, `meg`: `1e6`, `k`: `1e3`, `m`: `1e-3`, `u`: `1e-6`, `n`: `1e-9`, `p`: `1e-12`, `f`: `1e-15` | 无量纲 | `circuit.py`，`spice_number` 解析 SPICE 元件数值词头的缩放因子 |
| `COLLECTOR`, `EMITTER` | `(2, 1)`, `(2, -1)` | 网格步 | `schematic.py`，NPN 晶体管集电极与发射极相对于基极坐标的网格偏移 |
| 原理图排布与导出参数 | 默认跨度 `2.0`, 旁路横移步距 `1.5`, `dpi = 160` | 网格步, 网格步, $\text{dpi}$ | `schematic.py`，元件默认跨度、并联支路避碰平移步长及 `savefig` 导出分辨率 |

### 子电路链解析与网表拼接

`circuit.py` 与 `spice.py` 按以下步骤解析 `.cir` 组件文件并拼接 `ngspice` 网表：

1. **解析单级 SPICE 文件（`read_subcircuit`、`spice_number`）**：
   - 以词干名 `name = Path(path).stem` 作为目标主子电路名，逐行读取文件，按 `";"` 切去行尾的原理图布局提示并去除首尾空白；忽略空行与 `"*"` 开头的注释行。
   - 处于 `.subckt <name> <ports...>` 与 `.ends` 块**之外**的所有非空、非注释原始行，按原样顺序存入列表 `models`（保存晶体管等辅助 `.subckt` 与 `.MODEL` 定义）。
   - 处于主子电路块**之内**时，按首词首字母（转大写）解析元件并存入 `elements[words[0]]`：
     - `"X"`：`{"model": words[-1], "nodes": words[1:-1]}`；
     - `"E"` 且 `len(words) == 6`：`{"between": words[1:3], "follows": words[3:5], "gain": spice_number(words[5])}`；
     - `"R"` 且 `len(words) == 5` 且 `words[4].lower() == "noisy=0"`：`{"between": words[1:3], "ohm": spice_number(words[3]), "noiseless": True}`；
     - 首字母属于 `{"R": "ohm", "C": "farad", "L": "henry", "V": "volt"}` 且 `len(words) >= 4`：`{"between": words[1:3], <quantity>: spice_number(words[-1])}`（允许电压源在数值前带 `dc`）。
     - 其余行无法识别，立即抛出 `ValueError("Cannot read the element <line> of <path>")`；若数值不匹配正则 `([-+]?\d*\.?\d+(?:e[-+]?\d+)?)(meg|[tgkmunpf])?[a-z]*`，`spice_number` 抛出 `ValueError("<text> is not a SPICE number")`。
   - 读完文件后检查主子电路端口列表 `ports`：若未找到 `.subckt <name>` 或 `len(ports) not in (1, 2)`，抛出 `ValueError("<path> has to hold .subckt <name> with the nodes in, or in and out")`。将 `ports` 映射为 `dict(zip(("in", "out"), ports))` 返回。
2. **组装放大级与末级负载链（`named_chain`、`read_chain`）**：
   - `named_chain(name)` 按 `"+"` 拆分链名，通过 `component_path("readout", f"{part}.cir")` 定位各文件路径后调用 `read_chain(paths)`。
   - `read_chain` 将路径序列拆为前序放大级 `*stage_paths` 与末项负载 `load_path`：
     - 遍历 `stage_paths`：若某级 `"out" not in stage["ports"]`，抛出 `ValueError("<path> has no output: it can only be the load, the last of the chain, not its part <place> of <len>")`。级名默认取 `path.stem`；若与前面已有的放大级重名，则从 `2` 起递增追加后缀 `f"{path.stem}_{number}"`（如 `Gali52`、`Gali52_2`）。
     - 读取 `load = read_subcircuit(load_path)`：若 `"out" in load["ports"]`，抛出 `ValueError("<load_path> is the last of the chain and has to be a load, with the node in alone")`。返回 `{"stages": stages, "load": load}`。
3. **将子电路字典还原为 SPICE 文本（`subcircuit`）**：
   - 检查端口：若 `ports.get("out") == ports["in"]`，抛出 `ValueError("The stage <name> has the node <in> as input and as output; give the output a node of its own")`。
   - 写出 `.subckt <name> <in> [<out>]`。遍历 `stage["elements"]`：
     - 含 `"model"` 时写出 `X_<designator> <nodes...> <model>`；
     - 含 `"gain"` 时写出 `E_<designator> <between...> <follows...> <gain:.9g>`；
     - 其余元件检查匹配的物理量键（`"ohm"`、`"farad"`、`"henry"`、`"volt"`）：若匹配数不等于 `1`，抛出 `ValueError("Element <designator> of <name> has to carry one of ['ohm', 'farad', 'henry', 'volt'], a gain or a model, not ...")`；若带有 `"noiseless": True` 但物理量不是 `"ohm"`，抛出 `ValueError("Element <designator> of <name> is noiseless: only a resistor can be")`。写出 `<LETTER>_<designator> <first> <second> <value:.9g>[ noisy=0]`。
   - 末尾写出 `.ends <name>`。
4. **拼接完整瞬态网表（`_chain`、`_current_sources`、`_transient`、`write_netlist`）**：`write_netlist` 先调用 `_current_sources` 生成电流源行（其校验先于阶段名校验执行），再调用 `_chain` 生成放大级、负载与器件电路行，电流源行接在 `circuit.lines` 之后。
   - **校验阶段名**：在 `_chain(chain, circuit)` 中，若 `"load" in chain["stages"]`，抛出 `ValueError('A stage cannot be named "load"')`。
   - **首行标题与外部模型去重**：首行写 `" > ".join(["device", *stages, "load"])`。按顺序收集各放大级与负载中的 `"models"` 块，完全相同的模型块只保留首次出现的一份，原样展开到网表顶部。
   - **子电路定义与通道串联实例**：依次写出各放大级的 `subcircuit(name, stage)` 与末级负载的 `subcircuit("load", chain["load"])`。随后对 `circuit.outputs.values()` 中的第 $k$ 个器件输出节点 `output`（$k = 1, \dots, N_{\text{out}}$）：
     - 若 `stages` 非空，构造节点序列 `nodes = [output, "in<k>_2", ..., "in<k>_<N_stages>", "out<k>"]`，依次实例化 `X<k>_<j> <nodes[j-1]> <nodes[j]> <stage_name>`（$j = 1, \dots, N_{\text{stages}}$）；若 `stages` 为空，`nodes = [output]`；
     - 实例化末级负载 `Xload<k> <nodes[-1]> load`，并将 `nodes[-1]` 记录为该通道待测输出节点。
   - **器件等效电路与 PWL 电流源**：`_chain` 末尾追加 `circuit.lines`，其后接 `_current_sources(electrodes, dt, currents, circuit)` 生成的电流源行（该函数在 `_chain` 之前已被调用）：
     - 若 `not dt > 0`，抛出 `ValueError("The bin width must be positive, not <dt> s")`；
     - 若 `len(electrodes) != len(currents)`，抛出 `ValueError("<len(currents)> currents for <len(electrodes)> electrodes")`；
     - 若 `sorted(electrodes) != sorted(circuit.sources)`，抛出 `ValueError("The currents are of the electrodes <electrodes>; the device has current sources for <sources>")`；
     - 按式 (1)、式 (2) 为第 $k$ 个电极（从 `1` 起）写出 `I<k> <source_from> <source_to> PWL(<dt/2:.9g> 0 <t_0:.9g> <i_0:.9g> ...)`。
   - **控制块（`_transient`）**：追加 `.save v(<node_1>) ...`（仅保存待导出的输出节点向量，避免多通道网表耗尽内存）、`.control`、`tran <dt:.9g> <dt * (bins + 1):.9g>`、`wrdata <raw> v(<node_1>) ...`、`.endc`、`.end`。

短路电流网表 `write_short_circuit_netlist` 只含器件电路与短路支路，首行写 `device > short`，在电流源后对每个器件输出节点接入零电压源 `Vshort<k> <output> 0 0`，并在 `_transient` 中保存和导出支路电流向量 `i(Vshort<k>)`。

### 调用 `ngspice`、时间步与输出采样

1. **定位可执行程序（`_ngspice`）**：调用 `shutil.which("ngspice")`。若返回 `None`，抛出 `MissingDependency("ngspice is not installed", "Install it with conda install -c conda-forge ngspice on x86 Linux, or with env/install-ngspice.sh on macOS arm64 and Linux aarch64")`。
2. **批处理求解与时间箱中心插值（`_run`、`solve`、`short_circuit_currents`）**：
   - 在 `tempfile.TemporaryDirectory()` 创建的临时目录中，将网表写入 `run.cir`，调用 `subprocess.run([_ngspice(), "-b", str(netlist)], check=True, capture_output=True, text=True)` 执行批处理仿真（`ngspice` 返回非零退出码时抛出 `subprocess.CalledProcessError`）。
   - 用 `np.loadtxt(raw, dtype=np.float64, ndmin=2)` 读取 `wrdata` 输出文件 `out.raw`。`ngspice` 的 `wrdata` 在每个导出向量前都写一列时间，因此第 `0` 列 `solved_times = data[:, 0]` 为求解时刻序列，各输出通道的电压（或短路电流）位于奇数列 `column = 1, 3, 5, ...`。
   - 对每个奇数列，调用 `np.interp(since_start, solved_times, data[:, column])` 按式 (4) 线性插值到时间箱中心 $t_m = (m + 1.5)\,\Delta t$（$m = 0, \dots, n_{\text{bin}} - 1$），返回形状为 `(outputs, bins)` 的二维 `float64` 数组。
3. **条形行局部电路自适应扩展（`_solve_part`，`job.py`）**：
   - 当 `write_waveforms` 收到非 `None` 的回调函数 `part_of(hit, margin)`（用于单接触重复条形行探测器，见 [field.md](field.md) 的 `part_of_row`）且当事例存在非零电流电极列表 `hit` 时，围绕受击条动态扩展局部电路求解：
   - 初始化边界余量 `margin = 1`，构造局部电路 `part = part_of(hit, margin)` 并调用 `_solve` 求得输出电压字典 `before`。
   - 进入循环：每步将余量倍增 `margin *= 2`，构造更宽的局部电路 `wider = part_of(hit, margin)`：
     - 若 `list(wider.outputs) == list(part.outputs)`（局部电路已到达行首与行尾、不再扩大），立即返回 `before`；
     - 求解 `after = _solve(chain, currents, event, wider)`，计算各通道最大绝对电压摆幅 $S_r = \max_m |V_{r,m}|$ 及全局最大摆幅 $V_{\max} = \max_r S_r$；
     - 在满足 $S_r \ge \text{PART\_EDGE} \cdot V_{\max}$（$\text{PART\_EDGE} = 10^{-3}$）的待存储通道中，计算相邻两次扩展间的最大电压变动（前一次未包含的新增通道按从 `0.0` 变动起算）：
       $$\Delta V_{\text{moved}} = \max_{r:\, S_r \ge 10^{-3} V_{\max}}\ \max_{m} \bigl|V^{\text{after}}_{r,m} - V^{\text{before}}_{r,m}\bigr|$$
     - 更新 `part, before = wider, after`；若 $\Delta V_{\text{moved}} < 10^{-3} V_{\max}$，收敛并返回 `after`。

### 频域噪声求解与随机流合成

`noise_seed` 是 `readout` 自己的种子（NGspice 噪声），由作业的种子派生（见[实验、扫描点与种子](../lifecycle/experiments.md#种子)）。当 `write_waveforms` 的 `noise_seed` 为整数时，按以下步骤求解噪声谱并抽取各通道时域噪声：

1. **对称通道分组与噪声网表求解（`noise_spectra`、`write_noise_netlist`、`output_noise_spectrum`）**：
   - 遍历 `circuit.alike` 中的每个对称通道组 `group`，将该组内所有输出通道映射到组内居中通道 `group[len(group) // 2]`；不在任何组内的通道映射到自身。按 `circuit.outputs` 顺序去重得到实际需要调用 `ngspice` 分析的通道列表 `analysed`。
   - `write_noise_netlist` 调用 `_chain(chain, circuit)` 写出包含**完整器件电路**与全部通道放大器链的网表，取 `circuit.sources.values()` 的第一对节点接入小信号参考源 `I1 <source_from> <source_to> dc 0 ac 1`。
   - 在 `.control` 块中，对 `analysed` 中的第 $k$ 个待分析通道（从 `1` 起）依次写入：
     - `noise v(<node>) I1 dec 50 <lowest_hz:.9g> <highest_hz:.9g>`，其中 $f_{\min} = \text{LOWEST\_NOISE\_HZ} = 10^3\ \text{Hz}$，$f_{\max} = 0.5 / \Delta t$；
     - `setplot noise<2*k - 1>`（每次 `noise` 命令生成两个 plot，奇数号为谱密度，偶数号为积分总噪声）；
     - `wrdata <raw_k> onoise_spectrum`。
   - 调用 `ngspice -b` 执行噪声网表，读取各通道的频率列（$\text{Hz}$）与单边输出电压噪声幅度谱密度列（$\text{V}/\sqrt{\text{Hz}}$），按对称映射还原为形状 `(len(circuit.outputs), frequencies)` 的谱密度数组 `densities`。
   - `ngspice` 频域噪声分析在 $27\ ^\circ\text{C}$ 下执行，噪声谱覆盖 `LOWEST_NOISE_HZ = 1e3` $\text{Hz}$ 至 $0.5 / \Delta t$；每个输出通道给出其自身的总输出噪声谱。
2. **频带功率积分与复高斯谱逆变换（`band_power`、`noise_from_spectrum`）**：
   - `band_power(frequencies_hz, density)` 计算频率步长 `steps = np.diff(frequencies_hz)`：若 `frequencies_hz.size < 2` 或 `np.any(steps <= 0)`，抛出 `ValueError("A noise spectrum needs at least two increasing frequencies")`。按式 (9) 计算梯形累积功率并返回 `np.interp` 插值函数。
   - `noise_from_spectrum(frequencies_hz, density, bins, dt, generator)` 在长度 $N_{\text{rec}} = 256\,n_{\text{bin}}$ 上生成频率网格 `centres = np.fft.rfftfreq(record, d=dt)`，按式 (10)、式 (11) 求各频带功率 `in_band` 与 `sigma`。
   - 按式 (12) 用传入的 `generator` 先对全部频率点抽取实部 `generator.normal(0.0, sigma)` 与虚部 `generator.normal(0.0, sigma)`，再用 `generator.normal(0.0, record * np.sqrt(in_band[0]))` 覆写直流项 `spectrum[0]`，且当 `record % 2 == 0` 时用 `generator.normal(0.0, record * np.sqrt(in_band[-1]))` 覆写奈奎斯特项 `spectrum[-1]`。
   - 按式 (13) 返回 `np.fft.irfft(spectrum, n=record)[:bins]`。
3. **每事例每通道独立随机流（`write_waveforms`）**：
   - 对事例 `event` 中被保留的第 `name` 号输出通道，使用三维整数种子列表构造独立的 NumPy 随机数生成器：
     $$\text{generator} = \text{np.random.default\_rng}\bigl([\text{noise\_seed},\, \text{event.event},\, \text{place}[\text{name}]]\bigr)$$
     其中 `place[name]` 是该通道在完整 `circuit.outputs` 中的固定下标（$0, 1, \dots, N_{\text{out}} - 1$）。
   - 这样任意通道在任意事例中的噪声序列仅由 `(noise_seed, event.event, place[name])` 唯一决定，与当事例保存了哪些其他通道无关，且任意两个不同通道的噪声相互统计独立。

### 脉冲极性判定与波形文件写出

1. **脉冲边沿极性判定（`pulse_edges`、`collected_charge_sign`、`chain_sign`）**：
   - 提取器件读出接触名称列表 `contacts = [contact["name"] for contact in my_d.read_out_contact]`。若 `len(contacts) == 1`，将其重复扩展为 `contacts * len(outputs)`；若扩展后 `len(contacts) != len(outputs)`，抛出 `ValueError("<det_name> lists the read-out electrodes <contacts>, not one for each of the outputs <outputs>")`。
   - `chain_sign(chain)` 构造 $\Delta t = 10^{-11}\ \text{s}$、形状 `(1, 2000)` 的全零电流数组，置 `current[0, 5] = 1e-15 / dt`（$10^{-4}\ \text{A}$），在 `planar_circuit("probe", 1e-12)` 上调用 `solve` 求输出电压 `voltage`。计算相对首箱的摆动 `swing = voltage - voltage[0]`，取最大绝对偏离处的带符号值 `largest = swing[np.argmax(np.abs(swing))]`：若 `abs(largest) < NO_ANSWER_V`（$10^{-9}\ \text{V}$），抛出 `ValueError("The chain moves its output by <largest:.3g> V for 1 fC: it does not answer, so the way its pulses go is not known")`；否则 `largest > 0` 返回 `+1`，`largest < 0` 返回 `-1`。报这条错时，检查自定义放大级的信号能否从 `in` 端口经各元件到达 `out` 端口（节点名是否接对、压控源 `E` 的跟随节点是否接在信号节点上、增益是否为 `0`、输出是否被接到地），以及输出在探针的 $2000 \times 10\ \text{ps} = 20\ \text{ns}$ 窗口内能否摆动 $10^{-9}\ \text{V}$ 以上。
   - 对每个 `contact`，`collected_charge_sign(my_d, contact)` 按式 (14) 计算 `above`：若 `above == 0`，抛出 `ValueError("<electrode> of <det_name> and its other electrode are at one potential")`；`above > 0` 返回 `-1`，`above < 0` 返回 `+1`。按式 (16) 将两者乘积大于 `0` 记为 `"rising"`、小于 `0` 记为 `"falling"`。
2. **事例循环、通道摆幅筛选与叠加噪声（`write_waveforms`）**：
   - 调用 `read_currents(currents_path)` 读入整批感应电流；若目标 `waveforms_path` 已存在，先调用 `os.remove(waveforms_path)` 删除旧文件。
   - 遍历 `currents.events` 中的每个事例 `event`：
     - 找出存在非零电流的电极列表 `hit = [name for name, current in zip(currents.electrodes, event.current, strict=True) if np.any(current)]`；
     - 若 `hit` 为空（无信号事例），令 `solved = {}`；否则当 `part_of is None` 时调用 `_solve` 求解全电路，当 `part_of` 非 `None` 时调用 `_solve_part` 求解局部扩展电路；
     - 计算已求解通道的最大绝对电压摆幅 `swing = {name: np.abs(voltage).max() for name, voltage in solved.items()}` 与最大值 `largest = max(swing.values(), default=0.0)`；
     - 按 `circuit.outputs` 的顺序筛选满足 `name in solved and largest > 0 and swing[name] >= PART_EDGE * largest` 的通道列表 `names`，组装形状为 `(len(names), bins)` 的电压矩阵 `voltage`（无信号事例时 `names = []`，`voltage` 形状为 `(0, bins)`）；
     - 若 `noise_seed is not None` 且 `names` 非空，逐通道生成 `noise_from_spectrum` 并加到 `voltage` 上；
     - 调用 `append_waveforms` 将当事例写入 HDF5 文件。
3. **波形文件校验与追加写入（`append_waveforms`、`read_waveforms`、`read_circuit_values`）**：
   - **输入参数校验**：`append_waveforms` 取 `names = electrodes if record.electrodes is None else list(record.electrodes)`。若 `names` 含有不在 `electrodes` 中的名字或存在重复名字，抛出 `ValueError("the event <event> has traces of <names>, not each once of the electrodes <electrodes>")`。将 `record.voltage` 转为 `float64` 数组：若 `voltage.ndim != 2 or voltage.shape[0] != len(names)`，抛出 `ValueError("voltage has shape <shape>, expected (<len(names)>, bins)")`。若 `pulse_edge is not None` 且（`len(pulse_edge) != len(electrodes)` 或元素不全属于 `{"rising", "falling"}`），抛出 `ValueError("pulse_edge <pulse_edge> is not one of rising and falling for each of the electrodes <electrodes>")`。
   - **建表或校验已有文件结构**：若文件尚不存在，创建 HDF5 文件，写入属性 `electrodes`、`dt`、可选 `device_circuit`（`json.dumps(circuit_values)`）和可选 `pulse_edge`，并创建一维可扩展数据集 `event`、`t0`、`count`、`stored`、`index` 与启用 `compression="gzip"` 的 `voltage`。若文件已存在，先调用 `_check_layout` 检查 `DATASETS = ("event", "t0", "count", "stored", "index", "voltage")` 是否齐全且 `file["voltage"].ndim == 1`，不满足时抛出 `ValueError("<path> is a readout file of an older layout (no ...): run the readout again")`；再核对文件属性 `electrodes` 与 `dt` 是否与本次传入一致，不一致时抛出 `ValueError("<path> holds waveforms of electrodes <in_file> with dt <dt_file> s, not of <electrodes> with dt <dt> s")`。
   - **追加数据行**：将当事例的 `event`、`t0`、`count = voltage.shape[1]`、`stored = len(names)` 追加到对应数据集末尾，将 `[electrodes.index(name) for name in names]` 追加到 `index`，将 `voltage.reshape(-1)` 展平追加到 `voltage`。
   - **读取还原（`read_waveforms`）**：先执行 `_check_layout`，若文件属性缺少 `"pulse_edge"`，抛出 `ValueError("<path> has no pulse_edge: the readout of this version did not write it; run the readout again")`。遇到这条或旧布局的报错，按[片与重跑](../lifecycle/slices.md)让 `readout` 片重算，新文件替换同路径的旧文件。随后按每个事例的 `stored` 与 `count` 游标切分一维 `index` 与 `voltage`，还原各事例的 `EventWaveforms` 列表并返回 `Waveforms`。

### 放大级原理图网格排布与绘制

`schematic.py` 中的 `draw(path, figure_path)` 从 `.cir` 文件生成放大级或负载的原理图：

1. **提取行尾布局提示（`read_hints`）**：读取主子电路 `.subckt <stem>` 块内每行 `;` 后的文本，存入字典 `hints[designator]`。
2. **自动推断未给定元件的排布提示（`arrange`、`_main_path`）**：
   - 将元件分为接地元件 `grounded` 与非接地连接 `links`（子电路实例 `X` 与压控源 `E` 标记为有源放大元件 `active = True`）。若子电路实例 `X` 未在文件中给出行尾提示，抛出 `ValueError("What <name>, an instance of <model>, is cannot be told from its nodes: say it behind the element, as in '; npn'")`；若压控源 `E` 的控制负端与输出负端不共地（节点 `"0"`），`_amplifier` 抛出 `ValueError("<name> can only be drawn as 'amp' where it is a source that follows a voltage to ground and gives one to ground")`。
   - 若子电路含 `"out"` 端口，`_main_path` 从 `"in"` 到 `"out"` 执行深度优先搜索（有源元件单向通行，无源元件双向通行），选取经过有源放大元件最多、而在有源元件数相同时总元件数最少的路径作为主通路；若无通路可达 `"out"`，抛出 `ValueError("No way leads from the input of the stage to its output")`。
   - 沿主通路从左向右依次放置元件（文件中已给定提示的保持原提示，否则有源 `E` 取 `"amp"`，无源元件取 `"right"` 或 `"left"`，并按节点挂载的接地元件与旁路分支数预留向右平移量 `room(node) = 2 * max(beside - 1, 0)`）。
   - 循环放置剩余无源元件：接地元件向 `"down"`（或 `"up"`）悬挂并按 `2 * beside` 向右错开；两端节点均已定位的元件沿两节点连线跨越，每次向旁侧步进 `1.5` 网格步直至 `_taken` 判定不与已有元件或导线重叠；一端在主通路上的分支首元件向上延伸至当前最高坐标上方 `top = ceil(max_y) + 1`（若向右避碰步数 `aside > room(node)`，抛出 `ValueError("There is no free place for <name> to go up from the node <node>: say behind it where to draw it")`），分支后续元件向右延伸。若某轮循环未能放置任何剩余元件，抛出 `ValueError("Where to draw the elements <left> cannot be told from the stage: say it behind them")`。
3. **计算网格坐标与折线连接（`layout`）**：
   - 若 `hints` 含有不在 `stage["elements"]` 中的元件名，抛出 `ValueError("The drawing hints <unknown> are of no element of the stage")`。
   - 将输入端口节点置于坐标原点 `(0.0, 0.0)`。按提示顺序解析各元件的方向与步数（`_step` 要求方向属于 `{"right", "left", "up", "down"}` 且词数不超过 2，缺省步数为 `2.0`，否则抛出 `ValueError`；逗号后的附加提示必须以 `"shift"` 开头，否则抛出 `ValueError`；子电路实例 `X` 的主提示必须为 `"npn"` 且恰好含集电极、基极、发射极 3 个节点，否则抛出 `ValueError`）。
   - 已有一个端点坐标已知的元件立即落位，未知节点由首个到达它的元件赋予坐标，非接地端若与节点已有坐标不重合则由 `_wire` 生成先直行再折弯的直角导线。若某轮循环无新元件落位，抛出 `ValueError("The elements <left> hang on no node that the input reaches: they cannot be drawn")`。
4. **符号绘制与图片导出（`draw`、`value_text`）**：
   - 使用 Matplotlib 绘制各元件符号（电阻矩形框、电容双竖线、电感四半圆弧、电压源圆圈加 `"+"`、`"amp"` 三角形放大器、`"npn"` 带发射极箭头的三极管）、接地三横线符号、文字标签 `<name>\n<value_text>`（无噪电阻追加换行 `"no noise"`）、三条及以上线段交汇处的实心黑点，以及 `"in"`、`"out"` 端口空心圆圈，按 `(0.75 * width + 1, 0.75 * height + 1)` 英寸尺寸与 `dpi=160` 保存至 `figure_path`。

## 软件实现

### 模块与函数分工

- `circuit.py`：负责前端放大器 SPICE 子电路文件的解析与重写。`spice_number` 解析带词头的 SPICE 数值；`read_subcircuit` 将单个 `.cir` 文件解析为端口、元件与外部模型字典；`read_chain` 与 `named_chain` 组装多级放大器与末级负载链；`subcircuit` 将子电路字典序列化回 SPICE `.subckt` 文本。
- `spice.py`：负责拼接完整网表并驱动 `ngspice` 批处理求解。`_bin_centres`、`_current_sources`、`_chain`、`_transient`、`write_netlist`、`write_short_circuit_netlist` 与 `write_noise_netlist` 生成瞬态、短路电流与频域噪声网表；`_ngspice` 与 `_run` 调用 `ngspice -b` 并插值采样；`solve`、`short_circuit_currents` 与 `output_noise_spectrum` 为对外求解入口。
- `spectral_noise.py`：负责由单边幅度谱密度合成时域高斯噪声。`band_power` 计算梯形累积噪声功率插值函数，`noise_from_spectrum` 在扩展频域网格上抽取复高斯频谱并经 `irfft` 生成单条时域噪声波形。
- `pulse_edge.py`：负责判定各读出通道的输出脉冲极性。`collected_charge_sign` 由器件偏压判定收集载流子符号，`chain_sign` 用 $1\ \text{pF}$ 平板探针电路测定放大器链同相或反相，`pulse_edges` 返回各通道的 `"rising"` 或 `"falling"` 列表。
- `job.py`：负责单作业从感应电流文件到读出波形文件的批处理调度。`_solve` 与 `_solve_part` 执行单事例全电路或条形行局部自适应扩展求解，`noise_spectra` 按 `circuit.alike` 复用对称通道噪声谱，`write_waveforms` 完成逐事例求解、通道筛选、独立随机流噪声叠加与写出。
- `waveforms.py`：定义 `EventWaveforms`、`Waveforms` 数据类及 `_check_layout`、`append_waveforms`、`read_waveforms`、`read_circuit_values`，负责 `readout.h5` 的稀疏追加写入与读取。
- `schematic.py`：提供 `read_hints`、`arrange`、`layout`、`value_text` 与 `draw`，将 `.cir` 子电路文件绘制为原理图图像。
- `draw.py`：提供 `draw_waveform`，使用 `raser.supports.figures` 绘制单事例的输入感应电流与放大器输出电压波形图并保存为 `.png` 与 `.pdf`。
- `network.py`：计算阻性层网络对点冲击的响应。`impulse_response(my_d, circuit, chain, points_um, dt=10e-12, bins=2000, charge=1e-15)` 逐点将各 RC 格点份额作为首箱矩形脉冲电流调用 `spice.solve`，按 `circuit.outputs` 顺序返回形状 `(points, outputs, bins)` 的输出电压（$\text{V}$）；`admittance(circuit, frequencies_hz)` 对每个读出端口加 $1\ \text{V}$ 交流小信号、其余端口交流接地、感应电流源开路，按式 (8) 返回形状 `(frequencies, outputs, outputs)` 的复数导纳矩阵（$\text{S}$）。
- `draw_network.py`：绘制阻性层网络冲击响应图与器件网络电路图。`sharing` 绘制各读出电极波形最大绝对值及积分随冲击点 $x$ 的变化，经 `raser.supports.figures.save` 在 `folder` 下存为 `network_sharing.png` 与 `.pdf`；`waveforms` 绘制单个冲击点上各读出电极的输出波形，经 `raser.supports.figures.save` 存为 `network_waveforms.png` 与 `.pdf`；`schematic` 以 `circuit.outputs` 前两个读出节点为端口生成临时 `.cir` 子电路，按元件名前缀添加布局提示（`Rxlayer_`、`Rlayer_` 标 `; right`，`Rylayer_`、`Cpad_` 标 `; up`，`Clayer_` 标 `; down`），调用 `schematic.draw` 绘成 `network_schematic.png`。

### 核心数据结构

- 子电路与放大器链字典（`circuit.py`）：`read_subcircuit` 返回 `{"ports": {"in": <str>, Optional["out"]: <str>}, "elements": {<designator>: <dict>}, Optional["models"]: list[str]}`，其中电阻值键 `"ohm"` 单位为 $\Omega$、电容值键 `"farad"` 单位为 $\text{F}$、电感值键 `"henry"` 单位为 $\text{H}$、直流电压源键 `"volt"` 单位为 $\text{V}$、压控电压源键 `"gain"` 无量纲；`read_chain` 与 `named_chain` 返回 `{"stages": {<name>: <stage_dict>}, "load": <load_dict>}`。
- `DeviceCircuit`（定义于 `src/raser/core/field/device_circuit.py`，见 [field.md](field.md)）：冻结数据类，包含器件 SPICE 元件行元组 `lines: tuple[str, ...]`、感应电流源节点对映射 `sources: dict[str, tuple[str, str]]`、读出通道输出节点映射 `outputs: dict[str, str]` 以及共享噪声谱的对称输出通道分组 `alike: tuple[tuple[str, ...], ...]`。
- `EventWaveforms`（`waveforms.py`）：单事例读出波形记录，包含事例编号 `event: int`（无量纲）、首个时间箱左边界时刻 `t0: float`（$\text{s}$）、存储通道的时间箱中心输出电压矩阵 `voltage: np.ndarray`（形状 `(stored_electrodes, bins)`，`float64`，$\text{V}$）以及与 `voltage` 各行对应的通道名称列表 `electrodes: list[str] | None`（写入时若为 `None` 表示包含文件的全部 `electrodes`）。
- `Waveforms`（`waveforms.py`）：`read_waveforms` 返回的整文件波形容器，包含全部输出通道名称列表 `electrodes: list[str]`、时间箱宽度 `dt: float`（$\text{s}$）、事例波形列表 `events: list[EventWaveforms]` 以及与 `electrodes` 顺序对应的脉冲边沿方向列表 `pulse_edge: list[str]`（每项为 `"rising"` 或 `"falling"`）。

## 接口

命令与 `readout` 段的设置（如 `readout.amplifier`、`readout.sheet_resistance`）见 [../stages/readout.md](../stages/readout.md)，器件等效电路 `DeviceCircuit` 的参数提取与构建见 [field.md](field.md)，前端读出电路组件的详细图文说明见 [../components/readout.md](../components/readout.md)。使用者能设的只有下表列出的器件文件键、`.cir` 组件文件键，以及放大级元件数值的覆盖；页内其余参数（`LOWEST_NOISE_HZ`、`PART_EDGE`、`PER_DECADE`、噪声分析温度、`RECORD`、`NO_ANSWER_V`、探针电路参数）均写死在代码里。

放大级元件数值的覆盖：`read_subcircuit` 读出的各放大级描述（元件名下的纯数值）写进 `readout` 节点的 `node.json`，实验 `config.json` 与命令行 `--set`、`--scan` 按 `readout.amplifier.<放大级名>.<元件名>` 寻址改写这些数值（`readout.amplifier` 是槽位，放大器链加一层级名），例如 `--set readout.amplifier.ChargeSensitiveCremat.Cf=2e-12`、`--scan readout.amplifier.ChargeSensitiveCremat.Cf=1.4e-12,2e-12,3e-12`。`<放大级名>` 是放大级在链中的名字，即 `.cir` 文件名词干，同一文件在链中重复出现时第二个起带后缀（`Gali52_2`）；`<元件名>` 是 `.cir` 里的元件名（如 `Cf`、`Rf`、`E1`）。值是国际单位制下的纯数字，按元件种类分别为电阻 $\Omega$、电容 $\text{F}$、电感 $\text{H}$、直流电压源 $\text{V}$、压控电压源增益（无量纲），写成 `2e-12` 这样的十进制数；SPICE 词头写法（`2p`）用在 `.cir` 文件里。改电路结构（增删元件、改节点）则复制 `.cir` 另存为新名字（文件名词干与 `.subckt` 名一致），放进 project 的 `components/readout/`，组件查找先查 project 再查库内，链名里换成新名字。换放大器链写 `--set readout.amplifier=<组件名>`，扫放大器链写 `--scan readout.amplifier=<组件名1>,<组件名2>`，这时槽位整个换成那套组件，原来覆盖的元件数值一并去掉。

### 器件文件读取的键

| 键或派生属性 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `det_name` | 器件文件名词干 | 无 | 器件名称，用于 `pulse_edge.py` 报错信息 |
| `bias.electrode` | 无（必选） | 无 | 施加偏置电压的电极名称（其余电极接地），由 `collected_charge_sign` 读取 |
| `bias.voltage` | 无（必选） | $\text{V}$ | 偏置电压，与 `bias.electrode` 共同决定读出电极收集电子（`-1`）或空穴（`+1`） |
| `read_out_contact` | 无（必选） | 无 | 读出电极字典列表，每项含 `"name"`；长度为 `1` 时扩展到全部输出通道，否则长度须等于 `len(circuit.outputs)` |
| `capacitance_pF`, `bias_resistance_ohm`, `coupling_capacitance_pF`, `undepleted_resistance_ohm`, `undepleted_capacitance_pF`, `resistive_layer` | 见 [field.md](field.md) | $\text{pF}$, $\Omega$ | 由 [field.md](field.md) 的 `circuit_parameters.py` 读取以构建传入本包的 `DeviceCircuit` 与 `circuit_values`（写入 `readout.h5` 的 `device_circuit` 属性） |

### 组件文件的键

#### 元件语法与布局提示

每个 `.cir` 组件文件须包含一个与文件名词干同名的主子电路 `.subckt <文件名> ...`（接地节点固定为 `"0"`），主子电路之外的非注释行原样存入 `"models"`。主子电路内支持的声明、元件行语法及行尾 `;` 后的原理图布局提示如下：

| 键或元件行格式 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `.subckt <文件名> in out` / `.subckt <文件名> in` | 无（必选） | 无 | 主子电路端口声明：前序放大级必须声明双端口 `in out`，末级终端负载必须仅声明单端口 `in` |
| `R<名> <节点1> <节点2> <数值>` | 无 | $\Omega$ | 含热噪声的电阻（解析为 `{"between": [n1, n2], "ohm": R}`） |
| `R<名> <节点1> <节点2> <数值> noisy=0` | 无 | $\Omega$ | 无热噪声的电阻（解析为 `{"between": [n1, n2], "ohm": R, "noiseless": True}`） |
| `C<名> <节点1> <节点2> <数值>` | 无 | $\text{F}$ | 电容（解析为 `{"between": [n1, n2], "farad": C}`） |
| `L<名> <节点1> <节点2> <数值>` | 无 | $\text{H}$ | 电感（解析为 `{"between": [n1, n2], "henry": L}`） |
| `V<名> <正节点> <负节点> [dc] <数值>` | 无 | $\text{V}$ | 直流电压源（解析为 `{"between": [n+, n-], "volt": V}`） |
| `E<名> <输出+> <输出-> <跟随+> <跟随-> <增益>` | 无 | 无量纲 | 压控电压源（解析为 `{"between": [o+, o-], "follows": [f+, f-], "gain": G}`） |
| `X<名> <节点...> <子电路模型名>` | 无 | 无 | 调用同一文件主子电路外定义的子电路实例（解析为 `{"model": <模型名>, "nodes": [...]}`） |
| `; <方向> [<步数>]` | 自动排布（给定方向时默认 `2.0`） | 网格步 | `schematic.py` 布局提示：指定从元件第一节点到第二节点的方向（`right`、`left`、`up`、`down`）与网格步数 |
| `; <主提示>, shift <方向> [<步数>]` | 无偏移（给定方向时默认 `2.0`） | 网格步 | `schematic.py` 布局提示：将元件整体平移并通过直角折线导线连回两端节点 |
| `; npn` | 无（`X` 实例绘图必选） | 无 | `schematic.py` 布局提示：将三节点（依次为集电极、基极、发射极）的 `X` 实例绘制为基极在左的 NPN 双极晶体管符号 |
| `; amp` | 主通路上共地 `E` 自动采用 | 网格步（固定向右 `2.0`） | `schematic.py` 布局提示：将控制负端与输出负端共地的压控电压源 `E` 绘制为三角形放大器符号 |

元件数值支持科学计数法与不区分大小写的 SPICE 词头：`t`（$10^{12}$）、`g`（$10^{9}$）、`meg`（$10^{6}$）、`k`（$10^{3}$）、`m`（$10^{-3}$）、`u`（$10^{-6}$）、`n`（$10^{-9}$）、`p`（$10^{-12}$）、`f`（$10^{-15}$），词头后紧跟的单位字母会被忽略。

#### 库中组件

`raser/components/readout/`（详见 [../components/readout.md](../components/readout.md)）包含以下 5 个 SPICE 组件：

| 组件名称 | 端口数 | 电路描述 |
| --- | --- | --- |
| `BroadBandCividec` | 2（放大器级：`in`, `out`） | CIVIDEC C2 宽带同相电流放大器，带宽 `1 MHz - 2 GHz`，增益 `40 dB` |
| `ChargeSensitiveCremat` | 2（放大器级：`in`, `out`） | Cremat CR-110-R2.2 电荷灵敏前放，空载增益 `1.4 V/pC`，衰减时间 `140 us` |
| `Gali52` | 2（放大器级：`in`, `out`） | Mini-Circuits GALI-52+ 反相增益模块，低频增益 `22.66 dB`，极点 `1.41 GHz` |
| `SantaCruz` | 2（放大器级：`in`, `out`） | UC Santa Cruz 单通道 LGAD 读出板，基于 `BFR840L3RHESD` 的 `475 Ohm` 反馈反相跨阻级 |
| `Termination50` | 1（终端负载：`in`） | `50 Ohm` 接地终端电阻 |

![BroadBandCividec 原理图](../../images/readout/schematic-BroadBandCividec.png)

CIVIDEC C2 宽带电流放大器，带宽 `1 MHz - 2 GHz`，增益 `40 dB`。`Rbias` 是输入端的 `1 MΩ` 直流偏置，`Cin` 是 `1 nF` 交流耦合；输入的 `50 Ohm` 拆成产生噪声的 `Rn`（`325.4 Ohm`）和无噪声的 `Rq`（`59.08 Ohm`，`noisy=0`）两个并联电阻，使 `2 GHz` 单极点带宽内的输入电流噪声等于厂家给的 `0.4 uA rms`。`E1` 的增益是 `200`，经 `50 Ohm` 输出电阻 `Rout` 与 `50 Ohm` 负载分压后为 `100`，即 `40 dB`；`Rp`（`1 Ohm`）、`Cp`（`79.58 pF`）给出 `2 GHz` 的单极点。

![ChargeSensitiveCremat 原理图](../../images/readout/schematic-ChargeSensitiveCremat.png)

Cremat CR-110-R2.2 电荷灵敏前放，空载增益 `1.4 V/pC`，衰减时间 `140 us`。输入电容 `Cin`（`12.24 pF`）与等效输入电压噪声电阻 `Rs`（`43.1 Ohm`）接在反相增益 `-3000` 的第一级 `E1` 前，跨接 `Cf`（`1.4 pF`）与 `Rf`（`100 MOhm`）并联反馈以及无噪声极点 `Rp`（`1 kOhm`，`noisy=0`）、`Cp`（`401.3 pF`），再经增益 `+2` 的第二级 `E3` 与 `50 Ohm` 输出电阻 `Rout` 输出。

### 输入与输出文件格式

`write_waveforms` 通过 [current.md](current.md) 的 `read_currents(currents_path)` 读取上游 `current.h5` 的属性 `electrodes`（字符串数组）、`dt`（`float64`，$\text{s}$）以及各事例的 `event`（`int64`）、`t0`（`float64`，$\text{s}$）和还原为全电极形状 `(len(electrodes), count)` 的时域感应电流 `current`（`float64`，$\text{A}$）。

输出文件 `readout.h5` 由 `append_waveforms` 逐事例追加写出，仅存储当事例存在非零感应电流且最大电压摆幅达到当事例最大通道摆幅 `PART_EDGE = 1e-3` 倍的输出通道；`read_waveforms` 读出时按各事例实际保存的通道列表还原为 `EventWaveforms`。直接用 h5py 读取时，第 $e$ 个事例的通道下标是 `index[a:a + stored[e]]`，其中 $a$ 为前 $e$ 个事例 `stored` 之和；其中第 $j$ 条通道的波形是 `voltage[b + j*count[e] : b + (j+1)*count[e]]`，其中 $b$ 为前 $e$ 个事例 `stored * count` 之和；某通道下标不在该事例的 `index` 段里，即该事例未存这条通道。

**`readout.h5` 文件属性（Attributes）**

| 属性名 | 类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `electrodes` | 字符串数组 | 无 | `circuit.outputs` 定义的全部读出输出通道名称列表 |
| `dt` | `float64` | $\text{s}$ | 时间箱宽度（与输入 `current.h5` 的 `dt` 相同） |
| `pulse_edge` | 字符串数组（写入时可选，读取时必选） | 无 | 与 `electrodes` 顺序一一对应的输出脉冲极性，每项为 `"rising"` 或 `"falling"` |
| `device_circuit` | JSON 字符串（可选） | $\text{F}$, $\Omega$, $\text{F/m}^2$ | 器件等效电路各元件取值及来源字典，由 `read_circuit_values` 解析返回（`write_waveforms` 收到 `circuit_values` 时写入；文件无此属性时 `read_circuit_values` 返回 `None`） |

**`readout.h5` 数据集（Datasets）**

| 数据集名 | 形状与类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `event` | `(events,)`, `int64` | 无 | 事例编号（与输入 `current.h5` 的 `event` 一致） |
| `t0` | `(events,)`, `float64` | $\text{s}$ | 该事例首个时间箱左边界时刻 |
| `count` | `(events,)`, `int64` | 箱 | 该事例中每条保存波形的时间箱数（等于 `bins`） |
| `stored` | `(events,)`, `int64` | 个 | 该事例中保存波形的输出通道数（无信号事例为 `0`） |
| `index` | `(sum(stored),)`, `int64` | 无 | 每个被保存输出通道在 `electrodes` 属性中的下标（从 `0` 起），按 `stored` 切分到各事例 |
| `voltage` | `(sum(stored * count),)`, `float64`（gzip） | $\text{V}$ | 各被保存通道在 `count` 个时间箱中心的输出电压，按事例与保存通道顺序首尾拼接 |

### 绘图输出

`write_waveforms` 有两个必给参数 `plots`（`int`，每个作业最多绘制的有电流事例数，单位为个）和 `plot_path`（`str | Path`，图片输出文件夹路径，无单位；由[电子学读出环节](../stages/readout.md)传入 `readout.plots` 与该节点内的 `plots/` 目录）。当 `plots <= 0` 时不画单事例波形图，也不使用 `plot_path`；当 `plots > 0` 时，程序为每个作业中前 `plots` 个存在非零感应电流且存有通道波形的事例各画一张 `waveform_<事例号>`（`<事例号>` 为 `event.event`，无单位）：由 `core/readout/draw.py` 中的 `draw_waveform` 绘制，并经 `raser.supports.figures` 在 `plot_path` 下同时存为 `.png`（200 dpi）和 `.pdf` 两份文件。单事例波形图包含上下两幅、共用时间轴 `Time [ns]`，横坐标取各时间箱中心时刻 `t0 + (m + 0.5) dt`（其中 `t0` 为该事例首个时间箱左边界时刻 [$\text{s}$]，`dt` 为时间箱宽度 [$\text{s}$]，`m` 为时间箱下标，从 `0` 至 `n_bin - 1`，`n_bin` 为时间箱数 [箱]，换算为 $\text{ns}$）：上幅为输入的电极感应电流 `Current [μA]`（由 $\text{A}$ 换算为 $\mu\text{A}$），下幅为放大器输出电压 `Amplitude [mV]`（含按 `noise_seed` 叠加的时域噪声，由 $\text{V}$ 换算为 $\text{mV}$）。该事例存了波形的每个通道各画一条曲线；有多个保存通道时，各通道按 Okabe–Ito 色板依次取色，并在图例中写明通道名称。

此外，`schematic.py` 中的 `draw(path, figure_path)` 将单个 `.cir` 子电路文件渲染为原理图文件：

| 文件名 | 内容 | 单位 |
| --- | --- | --- |
| `waveform_<事例号>.png`, `.pdf` | 上下两幅共用时间轴的单事例波形图：上幅为该事例各保存通道对应电极的输入感应电流，下幅为含噪声的放大器输出电压；多通道按 Okabe–Ito 依次取色并在图例标注通道名 | `Time [ns]`, `Current [μA]`, `Amplitude [mV]` |
| `draw` 传入的 `figure_path`（文档图像为 `afe-schematic-<组件名>.png`） | 子电路原理图：包含标题 `<文件名词干>`、端口圆圈（`in`、`out`）、各元件符号、元件名与格式化数值标签（`value_text`，无噪电阻标注 `no noise`）、接地符号及直角连接导线（隐藏坐标轴，`dpi=160`） | 内部排布坐标为无量纲网格步（输入端口 `in` 位于 `(0.0, 0.0)`），图像尺寸为 `(0.75 * width + 1, 0.75 * height + 1)` $\text{in}$ |
| `network_sharing.png`, `.pdf` | 左右两幅共用冲击点横坐标：左幅为各读出电极波形的最大绝对值随冲击点 $x$，右幅为各读出电极波形对时间的积分随 $x$（由 `draw_network.sharing` 经 `raser.supports.figures.save` 写出） | `x of the impulse [μm]`, `Amplitude [mV]`, `Integral of the waveform [mV ns]` |
| `network_waveforms.png`, `.pdf` | 一个冲击点上各读出电极的输出波形，时间轴取到所有电极最后一次超过全局最大绝对值 `1%` 时刻的 `1.5` 倍（不超过总窗口；全零时画满总窗口；由 `draw_network.waveforms` 经 `raser.supports.figures.save` 写出） | `Time [ns]`, `Amplitude [mV]` |
| `network_schematic.png` | 器件网络的电路图，取 `circuit.outputs` 前两个读出节点为端口，标各元件名与数值（由 `draw_network.schematic` 按元件名前缀加布局提示后调用 `schematic.draw` 绘制） | 内部排布坐标为无量纲网格步（元件数值标注 $\Omega$、$\text{F}$ 等单位） |

## 参考文献

- [1] W. Riegler, “An application of extensions of the Ramo-Shockley theorem to signals in silicon sensors”, Nucl. Instrum. Methods Phys. Res. A 940 (2019) 453, doi:10.1016/j.nima.2019.06.056
- [2] L. W. Nagel, *SPICE2: A Computer Program to Simulate Semiconductor Circuits*, Memorandum No. ERL-M520, Electronics Research Laboratory, University of California, Berkeley (1975), https://www2.eecs.berkeley.edu/Pubs/TechRpts/1975/9602.html
- [3] C.-W. Ho, A. E. Ruehli, P. A. Brennan, “The Modified Nodal Approach to Network Analysis”, IEEE Trans. Circuits Syst. 22 (1975) 504, doi:10.1109/TCS.1975.1084079
- [4] J. B. Johnson, “Thermal Agitation of Electricity in Conductors”, Phys. Rev. 32 (1928) 97, doi:10.1103/PhysRev.32.97
- [5] H. Nyquist, “Thermal Agitation of Electric Charge in Conductors”, Phys. Rev. 32 (1928) 110, doi:10.1103/PhysRev.32.110
- [6] S. O. Rice, “Mathematical Analysis of Random Noise”, Bell Syst. Tech. J. 23 (1944) 282, doi:10.1002/j.1538-7305.1944.tb00874.x
