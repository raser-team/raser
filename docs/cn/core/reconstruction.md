# 事件重建（`core/reconstruction`）

`src/raser/core/reconstruction/` 承接[触发环节](../stages/trigger.md)记录的事例：各电极经[数字化](digitizer.md)得到的时域电压波形，文件格式与[电子学读出](readout.md)的波形文件相同。该包从每条波形中扣除脉冲前基线并估计电子学基线噪声，按各电极所选触发边沿将负向脉冲翻转为正向脉冲，提取峰值幅度、前沿过阈到达时间（`ToA`）、过阈持续时间（`ToT`）、过阈区间时间重心（`CoG`）、正向主瓣积分面积（`area`）、恒比定时（`CFD`）以及跨电极团簇（cluster）大小与空间重心，并写出 `reconstruction_<job>.h5` 文件（另提供面向条形探测器的单事例独立重建类 `InputWaveform`）。输出的事件汇总表 `EventTable` 交给 [统计分析](analysis.md)。

## 物理

### 基线扣除与极性翻转

读出电子学输出的离散电压波形包含前端静态直流偏置与电子学随机噪声，且脉冲方向随收集载流子极性与放大级反相特性而呈现上升沿（正脉冲）或下降沿（负脉冲）。特征提取前，取脉冲到达前的平稳采样段计算基线均值与基线噪声（总体标准差），从原始波形中扣除基线后乘以边沿极性符号，统一转化为基线以上的正向脉冲：

$$t_i = t_0 + \left(i + \frac{1}{2}\right)\Delta t \tag{1}$$

$$B = \frac{1}{N_{\text{base}}} \sum_{i=0}^{N_{\text{base}}-1} V_i, \qquad \sigma_{\text{noise}} = \sqrt{\frac{1}{N_{\text{base}}} \sum_{i=0}^{N_{\text{base}}-1} (V_i - B)^2} \tag{2}$$

$$v_i = s_{\text{edge}}\,(V_i - B) \tag{3}$$

其中：

- $t_i$：第 $i$ 个时间箱（$i = 0, 1, \dots, N-1$）的中心时刻，$\text{s}$；
- $t_0$：事例首个时间箱的左边界时刻（`t0`），$\text{s}$；
- $\Delta t$：时间箱宽度（`dt`），$\text{s}$；
- $V_i$：第 $i$ 个时间箱中心的原始输出电压采样值（`samples`），$\text{V}$；
- $N_{\text{base}}$：脉冲前基线采样点数（无量纲），代码取固定常数 `BASELINE_POINTS = 200`；
- $B$：脉冲前基线均值（`baseline`），$\text{V}$；
- $\sigma_{\text{noise}}$：脉冲前基线噪声总体标准差（`noise`），$\text{V}$；
- $s_{\text{edge}}$：触发边沿极性系数（无量纲），由 `EDGE_SIGN` 给出，上升沿 `"rising"` 取 $+1.0$，下降沿 `"falling"` 取 $-1.0$；
- $v_i$：扣除基线并翻转为正向后的净电压采样值（`net`），$\text{V}$。

基线扣除与噪声计算对应 `event.py` 中的 `net_pulse(samples, baseline_points=BASELINE_POINTS)`，默认 `baseline_points = 200`。时间箱中心计算与极性翻转在 `event_table.py` 的 `event_table` 中执行；各电极边沿方向由 `chosen_edges` 确定，缺省沿用输入波形文件为各电极记下的 `pulse_edge`（读出链按器件与电子学派生）。所选边沿与某电极脉冲的实际方向相反时，该电极的脉冲留在基线以下：`amplitude` 是基线以上最大的采样，只有噪声或过冲的量级，通常低于 `threshold`，于是 `above = False`，定时与面积列为 `NaN`；过冲达到 `threshold` 时，定时量按过冲算出。`InputWaveform` 则假定输入 `voltage` 已为扣除基线后的正向脉冲。半导体探测器脉冲基线恢复与噪声表征见文献 [1]。

### 峰值幅度与固定阈值过零定时（ToA 与 ToT）

前沿固定阈值甄别（leading-edge discrimination）在脉冲跨越预设电压阈值 $V_{\text{th}}$ 时产生时间标记。净波形的最大采样值给出脉冲峰值幅度；从峰值所在时间箱分别向前、向后搜索首次低于阈值的时间箱，在与相邻过阈时间箱中心连线上作线性插值，得到上升沿过阈到达时间（`ToA`）与下降沿过阈时刻，两者之差即为过阈持续时间（`ToT`）：

$$A = v_{i_{\text{peak}}}, \qquad i_{\text{peak}} = \operatorname{argmax}_{0 \le i < N} v_i \tag{4}$$

$$t_{\text{cross}}(V_{\text{th}};\, i_{\text{below}},\, i_{\text{above}}) = t_{i_{\text{below}}} + \frac{V_{\text{th}} - v_{i_{\text{below}}}}{v_{i_{\text{above}}} - v_{i_{\text{below}}}}\bigl(t_{i_{\text{above}}} - t_{i_{\text{below}}}\bigr) \tag{5}$$

$$t_{\text{ToA}} = t_{\text{cross}}\bigl(V_{\text{th}};\, i_{\text{lead}},\, i_{\text{lead}} + 1\bigr) \tag{6}$$

$$t_{\text{ToT}} = t_{\text{cross}}\bigl(V_{\text{th}};\, i_{\text{trail}},\, i_{\text{trail}} - 1\bigr) - t_{\text{ToA}} \tag{7}$$

其中：

- $A$：基线以上最大脉冲幅度（`amplitude`），$\text{V}$；
- $i_{\text{peak}}$：峰值所在时间箱下标（`peak`，无量纲，存在并列最大值时取首个下标）；
- $V_{\text{th}}$：固定过阈电压阈值（`threshold`），$\text{V}$；
- $i_{\text{below}}, i_{\text{above}}$：阈值两侧相邻时间箱下标（无量纲），满足 $v_{i_{\text{below}}} < V_{\text{th}} \le v_{i_{\text{above}}}$；
- $t_{\text{cross}}$：相邻两箱中心连线越过阈值 $V_{\text{th}}$ 的线性插值时刻，$\text{s}$；
- $i_{\text{lead}}$：从 $i_{\text{peak}} - 1$ 向 $0$ 反向搜索遇到的首个满足 $v_i < V_{\text{th}}$ 的时间箱下标（无量纲）；
- $i_{\text{trail}}$：从 $i_{\text{peak}} + 1$ 向 $N - 1$ 正向搜索遇到的首个满足 $v_i < V_{\text{th}}$ 的时间箱下标（无量纲）；
- $t_{\text{ToA}}$：上升沿过阈到达时间（`ToA`），$\text{s}$；
- $t_{\text{ToT}}$：脉冲在阈值以上的持续时间（`ToT`），$\text{s}$。

峰值幅度由 `event.py` 中的 `get_amplitude` 计算，阈值过零插值、到达时间与过阈持续时间分别由 `crossing`、`get_ToA` 与 `get_ToT` 计算。仅当 $A \ge V_{\text{th}}$（`above = True`）时执行定时计算；[../stages/reconstruction.md](../stages/reconstruction.md) 中 `threshold` 缺省为 `10.0` $\text{mV}$（换算后为 $0.01\ \text{V}$）。前沿甄别与 `ToT` 测量原理见文献 [1, 2]。

### 恒比定时（CFD）

固定阈值定时会因脉冲幅度涨落引入幅度时间游走（time walk）。恒比定时（constant-fraction discrimination，`CFD`）将甄别阈值设为单个脉冲峰值幅度的固定比例 $f \in (0, 1)$，在峰值前的上升沿上寻找跨过目标高度 $f A$ 的相邻采样箱并作线性插值，从而消除同形状脉冲幅度变化引起的定时游走：

$$V_{\text{CFD}} = f\,A = f\,v_{i_{\text{peak}}} \tag{8}$$

$$t_{\text{CFD}}(f) = \begin{cases} t_{i-1}, & v_i = v_{i-1} \\ t_{i-1} + \dfrac{V_{\text{CFD}} - v_{i-1}}{v_i - v_{i-1}}\bigl(t_i - t_{i-1}\bigr), & v_i \ne v_{i-1} \end{cases} \tag{9}$$

其中：

- $f$：恒比甄别比例（`CFD` 或 `fractions` 的元素，无量纲），满足 $0 < f < 1$；
- $A = v_{i_{\text{peak}}}$：脉冲峰值幅度，$\text{V}$（要求 $A > 0$）；
- $V_{\text{CFD}}$：恒比触发目标电压（`target`），$\text{V}$；
- $i$：从 $i_{\text{peak}}$ 向 $1$ 反向搜索遇到的首个满足 $v_{i-1} \le V_{\text{CFD}} \le v_i$ 的时间箱下标（无量纲）；
- $t_{\text{CFD}}(f)$：比例 $f$ 对应的恒比定时时刻（`CFD` 或 `CFD50`），$\text{s}$。

恒比定时由 `event.py` 中的 `get_CFD50(times, samples, CFD, peak)` 计算。`InputWaveform` 缺省取模块常数 `CFD = 0.5`（对应字典键 `CFD_LABEL = "CFD50"`）；`electrode_row`（由 `event_table` 对每个已存电极调用）对 `fractions` 中的每个比例分别调用 `get_CFD50`，[../stages/reconstruction.md](../stages/reconstruction.md) 中 `fractions` 缺省为 `[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]`。恒比定时甄别原理见文献 [1, 3]。

### 时间重心（CoG）与脉冲积分（area 与 charge）

脉冲在时间轴上的能量集中时刻由过阈区间的时间重心（centre of gravity，`CoG`）表征，脉冲总强度则由主瓣面积积分（`area`）或离散采样点绝对值之和（`charge`）表征。代码从峰值下标 $i_{\text{peak}}$ 向左、右两侧分别扩展连续满足 $v_i \ge V_{\text{th}}$ 的连通区间 $[i_{\text{first}}^{\text{th}},\, i_{\text{last}}^{\text{th}}]$ 与连续满足 $v_i > 0$ 的正向主瓣区间 $[i_{\text{first}}^{0},\, i_{\text{last}}^{0}]$，按下列各式计算：

$$t_{\text{CoG}} = \frac{\sum_{i = i_{\text{first}}^{\text{th}}}^{i_{\text{last}}^{\text{th}}} t_i\,v_i}{\sum_{i = i_{\text{first}}^{\text{th}}}^{i_{\text{last}}^{\text{th}}} v_i} \tag{10}$$

$$S_{\text{area}} = \Delta t \sum_{i = i_{\text{first}}^{0}}^{i_{\text{last}}^{0}} v_i \tag{11}$$

$$Q_{\text{sum}} = \sum_{i = 0}^{N - 1} |v_i| \tag{12}$$

其中：

- $i_{\text{first}}^{\text{th}}, i_{\text{last}}^{\text{th}}$：包含 $i_{\text{peak}}$ 且连续满足 $v_i \ge V_{\text{th}}$ 的起止时间箱下标（无量纲）；
- $t_{\text{CoG}}$：过阈脉冲段按采样值加权的时间重心（`CoG`），$\text{s}$；
- $i_{\text{first}}^{0}, i_{\text{last}}^{0}$：包含 $i_{\text{peak}}$ 且连续满足 $v_i > 0$（基线以上）的正向脉冲主瓣起止时间箱下标（无量纲）；
- $S_{\text{area}}$：正向主瓣的矩形数值积分面积（`area`），$\text{V}\cdot\text{s}$；
- $Q_{\text{sum}}$：整条波形全部采样点绝对值的离散总和（`InputWaveform.charge`），$\text{V}$。

时间重心由 `event.py` 中的 `get_CoG` 计算，主瓣积分面积由 `event_table.py` 中的 `lobe_area` 计算，两者均在 $A \ge V_{\text{th}}$ 时由 `electrode_row` 调用。离散绝对值总和式 (12) 由 `event.py` 中的 `get_charge` 计算，仅用于 `InputWaveform`。脉冲积分与质心定时测量见文献 [1]。

### 跨电极团簇与空间重心（cluster）

当载流子在相邻读出电极间发生电荷共享或容性耦合时，单次入射会在多个相邻电极上产生过阈信号。跨电极成簇以幅度达到种子阈值 $V_{\text{amp}}$ 的电极为种子，将每个种子及其左右紧邻（电极列表下标相差 $1$）中达到邻近阈值的电极合并为团簇成员集合 $\mathcal{M}$，由此计算团簇电极数、总特征量、一维电极下标重心以及相对真实入射位置的空间误差：

$$N_{\text{clu}} = |\mathcal{M}|, \qquad W_{\text{clu}} = \sum_{j \in \mathcal{M}} w_j, \qquad x_{\text{clu}} = \frac{\sum_{j \in \mathcal{M}} j\,w_j}{\sum_{j \in \mathcal{M}} w_j} \tag{13}$$

$$\Delta x_{\text{clu}} = x_{\text{clu}} - \frac{x_{\text{true}}}{p_x} \tag{14}$$

其中：

- $\mathcal{M}$：并入团簇的读出电极下标集合（从 $0$ 起，无量纲）；
- $w_j$：第 $j$ 号电极的特征权重（`event_table.py` 的 `cluster` 中取峰值幅度 $A_j$ [$\text{V}$]；`event.py` 的 `InputWaveform` 中分别取 `ToT` [$\text{s}$]、`amplitude` [$\text{V}$] 或 `charge` [$\text{V}$]）；
- $N_{\text{clu}}$：团簇包含的电极个数（`cluster_size`），个；
- $W_{\text{clu}}$：团簇内各成员电极特征量之和（`InputWaveform` 中的汇总 `"ToT"`、`"amplitude"`、`"charge"`），单位与 $w_j$ 相同；
- $x_{\text{clu}}$：团簇的一维加权中心（`cluster_center` 或 `gravity_center_*`），以从 $0$ 起的电极下标为单位（无量纲）；
- $x_{\text{true}}$：入射粒子真实 $x$ 坐标（`original_x`），与电极间距 $p_x$（`pitch_x`）同单位；
- $\Delta x_{\text{clu}}$：重建电极重心与归一化真实坐标之差（`gravity_center_*_error`），以电极间距 $p_x$ 为单位（无量纲）。

作业级事件表中的成簇由 `event_table.py` 的 `cluster(amplitudes, threshold, amplitude_threshold)` 计算，只输出 $N_{\text{clu}}$ 与幅度加权的 $x_{\text{clu}}$，[../stages/reconstruction.md](../stages/reconstruction.md) 中 `amplitude_threshold` 与 `threshold` 缺省均为 `10.0` $\text{mV}$。单事例类 `InputWaveform` 则调用 `event.py` 的 `get_total_amp` 与 `get_gravity_center_and_cluster_size` 计算式 (13)，在 `get_total_data` 中按式 (14) 计算位置误差，并用 `get_conjoined_time` 取 `ToA` 与 `CFD50`；其 `data` 字典交给 [统计分析](analysis.md) 的 `WaveformStatistics.fill_data`，键与 `fill_data`、`draw` 读取的键相同。微条探测器电荷共享与重心位置重建见文献 [4]。

## 算法

### 内置常数

下表列出 `event.py` 与 `event_table.py` 中的全部内置常数与写死在代码中的数值。它们均是模块常量或函数内硬编码值，器件文件与组件文件里没有对应的键：

| 常数或硬编码名 | 取值（按情形分列） | 单位 | 定义位置与含义 |
| --- | --- | --- | --- |
| `BASELINE_POINTS` | `200` | 采样点（个） | `event.py`：`net_pulse` 计算基线均值 `baseline` 与标准差 `noise` 所取的开头采样点数 |
| `EDGE_SIGN` | `"rising"`: `1.0`；`"falling"`: `-1.0` | 无量纲 | `event_table.py`：将扣除基线后的净波形 `net` 翻转为正向脉冲的极性乘子 |
| `CFD` | `0.5` | 无量纲 | `event.py`：`InputWaveform` 构造函数的默认恒比定时分数 |
| `CFD_LABEL` | `"CFD50"` | 无 | `event.py`：`InputWaveform.data` 中存放恒比定时结果的字典键名 |
| `EVENT_COLUMNS` | `("event", "selected", "cluster_size", "cluster_center")` | 无 | `event_table.py`：`EventTable` 中按事例的一维数据集列名元组 |
| `ELECTRODE_COLUMNS` | `("traced", "baseline", "noise", "amplitude", "above", "ToA", "ToT", "CoG", "area")` | 无 | `event_table.py`：`EventTable` 中按事例与电极的二维数据集列名元组 |
| `KINDS` | `"event"`, `"cluster_size"`: `"int64"`；`"selected"`, `"traced"`, `"above"`: `"bool"`；其余列缺省: `"float64"` | 无 | `event_table.py`：`event_table` 生成各列 NumPy 数组的数据类型映射 |
| `InputWaveform` 多电极种子阈值 | `ToT` 成簇: `10e-9`；`amplitude` 成簇: `amplitude_threshold`；`charge` 成簇: `0.0` | $\text{s}$ / $\text{V}$ / $\text{V}$ | `event.py`：`InputWaveform.get_total_data` 调用 `get_total_amp` 与 `get_gravity_center_and_cluster_size` 时的硬编码阈值 |

### 每个电极的边沿确定与输入校验

构建事件表前，程序先通过 `chosen_edges` 确定每个电极的脉冲边沿，再在 `event_table` 入口校验全部输入参数：

1. **确定每个电极一个边沿（`chosen_edges(given, derived, electrodes)`）**：
   - 若 `given is None`，直接沿用读出文件为各电极记录的派生边沿列表 `list(derived)`，返回提示列表 `notes = []`。
   - 若 `given` 不为 `None` 且 `given not in EDGE_SIGN`（即既不是 `"rising"` 也不是 `"falling"`），抛出 `ValueError("edge <given!r>: the thresholds are set on a rising (positive pulses) or a falling (negative pulses) edge")`。
   - 若 `given` 为 `"rising"` 或 `"falling"`，将全部电极的边沿统一设为 `[given] * len(electrodes)`；同时按 `zip(electrodes, derived)` 逐个检查，对所有满足 `edge != given` 的电极生成提示字符串 `"edge <given> given for <name>, whose pulse is <edge>: its pulses are not seen as the readout makes them"` 并收入 `notes` 返回（环节函数 `reconstruct` 会逐条打印该提示，不终止运行）。
2. **校验电极边沿列表（`event_table`）**：检查传入的 `edges` 是否满足 `len(edges) == len(waveforms.electrodes)` 且每个元素均属于 `EDGE_SIGN`。若不满足，抛出 `ValueError("edges <edges>: one of rising or falling for each of <waveforms.electrodes>")`。校验通过后，生成各电极极性符号列表 `polarity = [EDGE_SIGN[edge] for edge in edges]` 与电极名索引字典 `place = {name: k for k, name in enumerate(waveforms.electrodes)}`。
3. **校验恒比分数范围（`event_table`）**：筛选 `wrong = [part for part in fractions if not 0 < part < 1]`。若 `wrong` 非空（含 $\le 0$、$\ge 1$ 或 `NaN` 的值），抛出 `ValueError("fractions <wrong>: a constant fraction lies between 0 and 1")`。
4. **校验非空事例列表（`event_table`）**：若 `not waveforms.events`（输入的 `Waveforms` 对象中没有任何事例），抛出 `ValueError("the readout holds no event")`。

### 单电极基线扣除、边沿搜索与插值特征提取

`event_table` 遍历 `waveforms.events` 中的每个事例 `record`（设总电极数为 $W = \text{len}(\text{waveforms.electrodes})$，当前事例时间箱数为 $N = \text{record.voltage.shape}[1]$），按以下顺序处理各电极波形：

1. **计算时间箱中心并预填未追踪电极**：按式 (1) 计算长度 $N$ 的时间箱中心数组 `times = record.t0 + (np.arange(N) + 0.5) * waveforms.dt`。为全部 $W$ 个电极初始化未追踪缺省字典 `untraced`：`traced = False`、`above = False`，其余数值列（`baseline`、`noise`、`amplitude`、`ToA`、`ToT`、`CoG`、`area`）以及 `len(fractions)` 个 `CFD` 值均填 `NaN`。不在 `record.electrodes` 中的电极（读出环节未保存波形的通道）保持该缺省状态。
2. **扣除前 200 点基线并算噪声（`net_pulse(samples, baseline_points=200)`）**：对 `zip(record.electrodes, record.voltage)` 中的每个已保存电极 `name`（对应全局列下标 $k = \text{place}[\text{name}]$）及其采样数组 `samples`：
   - 将 `samples` 转换为 `float64` 数组；
   - 若 $\text{len}(\text{samples}) \le \text{baseline\_points}$（即 $N \le 200$），抛出 `ValueError("<len(samples)> samples, not more than the <baseline_points> of the baseline")`；
   - 取前 $200$ 个点计算均值 `baseline = samples[:200].mean()` 与总体标准差 `noise = samples[:200].std()`（`ddof=0`），得到 `net = samples - baseline`。
3. **翻转脉冲极性并定位峰值（`get_amplitude`）**：将净波形乘以该电极的边沿符号 $\text{net}^{+} = \text{polarity}[k] \cdot \text{net}$ 传入 `electrode_row`。调用 `get_amplitude` 求 `peak = int(np.argmax(net+))` 与 `amplitude = net+[peak]`。
4. **过阈判定与未过阈拒绝（`electrode_row`）**：
   - 若 `amplitude < threshold`，拒绝提取该电极的定时与面积特征：返回 `above = False`、实测 `amplitude`，并将 `ToA`、`ToT`、`CoG`、`area` 及全部 `len(fractions)` 个 `CFD` 置为 `NaN`（外层合并 `traced = True`、`baseline` 与 `noise`）。
   - 否则（即 `amplitude >= threshold`；边界情形：若 `amplitude` 为 `NaN`，因 `NaN < threshold` 为假，同样进入此分支），记 `above = True`，依次执行步骤 5 至步骤 9。
5. **前沿过阈搜索与线性插值（`get_ToA` 与 `crossing`）**：
   - 从下标 $i = \text{peak} - 1$ 起按步长 $-1$ 递减至 $0$；
   - 遇到首个满足 $\text{net}^{+}[i] < \text{threshold}$ 的下标 $i$ 时，立即调用 `crossing(times, net+, threshold, below=i, above=i + 1)`：因 $i$ 是从峰值向回看的首个低于阈值点，必有 $\text{net}^{+}[i+1] \ge \text{threshold}$ 且分母 $\text{net}^{+}[i+1] - \text{net}^{+}[i] > 0$，按式 (5) 与式 (6) 线性插值返回过阈时刻；
   - **拒绝情形**：若 $\text{peak} = 0$，或直至 $i = 0$ 仍有 $\text{net}^{+}[i] \ge \text{threshold}$（脉冲在首个采样箱中心已处于阈值之上，无上升沿过零点），`get_ToA` 返回 `None`，`electrode_row` 将 `ToA` 记为 `NaN`。
6. **后沿过阈搜索与 `ToT` 计算（`get_ToT`）**：
   - 内部先调用 `start = get_ToA(times, net+, threshold, peak)`；若 `start is None`（无前沿过阈点），直接返回 `0.0`；
   - 否则从下标 $i = \text{peak} + 1$ 起按步长 $+1$ 递增至 $N - 1$；
   - 遇到首个满足 $\text{net}^{+}[i] < \text{threshold}$ 的下标 $i$ 时，调用 `crossing(times, net+, threshold, below=i, above=i - 1)` 求下降沿过阈时刻并减去 `start` 返回（此时 `below = i`、`above = i - 1`，比例因子 `part` $\in (0, 1]$，与时间差 $\text{times}[i-1] - \text{times}[i] = -\Delta t$ 相乘为负偏移，交点落在 $\text{times}[i-1]$ 与 $\text{times}[i]$ 之间）；
   - **未回落边界情形**：若 $\text{peak} = N - 1$，或直至波形末尾 $i = N - 1$ 仍未降至 `threshold` 以下，`get_ToT` 返回浮点数 `0.0`。
7. **过阈区间扩展与时间重心（`get_CoG`）**：
   - 令 `first = peak`、`last = peak`；
   - 当 $\text{first} > 0$ 且 $\text{net}^{+}[\text{first} - 1] \ge \text{threshold}$ 时循环递减 `first`；当 $\text{last} < N - 1$ 且 $\text{net}^{+}[\text{last} + 1] \ge \text{threshold}$ 时循环递增 `last`；
   - 取切片 `weights = net+[first:last + 1]`，按式 (10) 返回 `np.sum(times[first:last + 1] * weights) / np.sum(weights)`。
8. **正向主瓣扩展与积分面积（`lobe_area`）**：
   - 令 `first = peak`、`last = peak`；
   - 当 $\text{first} > 0$ 且 $\text{net}^{+}[\text{first} - 1] > 0$ 时循环递减 `first`；当 $\text{last} < N - 1$ 且 $\text{net}^{+}[\text{last} + 1] > 0$ 时循环递增 `last`；
   - 按式 (11) 返回 `float(np.sum(net+[first:last + 1]) * dt)`。
9. **恒比定时搜索与线性插值（`get_CFD50`）**：
   对 `fractions` 中的每个比例 `part`：
   - 计算目标高度 $\text{target} = \text{net}^{+}[\text{peak}] \cdot \text{part}$；
   - **非正峰值拒绝情形**：若 $\text{net}^{+}[\text{peak}] \le 0$（仅当 `threshold <= 0` 时可能出现），返回 `None`，对应 `CFD` 记为 `NaN`；
   - 否则从 $i = \text{peak}$ 起按步长 $-1$ 递减至 $1$，取相邻采样值 $\text{previous\_content} = \text{net}^{+}[i - 1]$ 与 $\text{content} = \text{net}^{+}[i]$，判断闭区间条件 $\text{previous\_content} \le \text{target} \le \text{content}$：
     - 若成立且 $\text{content} == \text{previous\_content}$，返回左箱时刻 `times[i - 1]`；
     - 若成立且 $\text{content} \ne \text{previous\_content}$，按式 (9) 线性插值返回过零时刻；
   - **未命中拒绝情形**：若遍历至 $i = 1$ 仍无相邻采样对满足 $\text{net}^{+}[i - 1] \le \text{target} \le \text{net}^{+}[i]$（例如首箱已高于 `target`），返回 `None`，对应 `CFD` 记为 `NaN`。

### 跨电极成簇与事例选中规则

单个事例的全部电极行计算完毕后，`event_table` 提取各电极幅度列表 `amplitudes = [row["amplitude"] for row in rows]`，调用 `cluster(amplitudes, threshold, amplitude_threshold)`：

1. **寻找种子电极**：收集所有满足 $\text{amplitudes}[k] \ge \text{amplitude\_threshold}$ 的电极下标 $k \in \{0, \dots, W - 1\}$ 组成列表 `seeds`（未追踪电极的 `amplitude` 为 `NaN`，比较结果为假）。
2. **并入左右紧邻过阈电极**：对每个种子 $k \in \text{seeds}$，检查下标 $j \in \{k - 1, k, k + 1\}$。若 $j = k$，或满足 $0 \le j < W$ 且 $\text{amplitudes}[j] \ge \text{threshold}$，则将 $j$ 并入集合并升序排序为 `members`。
3. **无种子拒绝与特征写出**：
   - 若 `members` 为空（`seeds` 为空），返回 `(0, NaN)`，该事例记 `selected = False`、`cluster_size = 0`、`cluster_center = NaN`；
   - 若 `members` 非空，按式 (13) 以成员电极的 `amplitudes[j]` 为权重计算幅度加权下标重心，返回 `(len(members), center)`，该事例记 `selected = True`。
4. **组装数组**：全部事例循环结束后，将各列按 `KINDS.get(name, "float64")` 转为 NumPy 数组，其中 `CFD` 重塑为三维形状 `(len(waveforms.events), W, len(fractions))`，封装为 `EventTable` 返回。

`cluster` 在一维电极列表下标上取 $k - 1$ 与 $k + 1$ 为紧邻，同一事例内所有达到 `amplitude_threshold` 的种子及其紧邻合并为一个团簇。

### 单事例独立重建类 `InputWaveform`

`InputWaveform(voltage, t0, dt, original_x, threshold, amplitude_threshold, pitch_x, pitch_y, CFD=0.5)`（`event.py`）供 Python 脚本对已扣除基线且翻正的二维电压矩阵 `voltage`（形状 `(read_ele_num, bins)`）直接提取单事例量：

1. **单电极扫描**：按式 (1) 计算 `times = t0 + (np.arange(len(voltage[0])) + 0.5) * dt`。对每个电极 $i \in \{0, \dots, \text{read\_ele\_num} - 1\}$ 调用 `get_amplitude(voltage[i])` 得 `(amplitude[i], peak_time[i])`（其中 `peak_time[i]` 存的是峰值箱整数下标 `peak`）：
   - 若 $\text{amplitude}[i] < \text{threshold}$，拒绝该电极，将 `amplitude[i]`、`ToT[i]`、`charge[i]` 置为 `0`，将 `ToA[i]`、`CFD50[i]` 置为 `None`；
   - 否则分别调用 `get_ToA`、`get_ToT`、`get_charge`（按式 (12) 计算 `np.sum(np.abs(voltage[i]))`）与 `get_CFD50`（比例为 `CFD`）。
2. **多通道特征汇总（`get_total_data`）**：初始化 `self.data = {}`，在末尾固定写入 `self.data["original_x"] = original_x`，其余 14 个键按以下三档赋值：
   - **未达种子阈值拒绝档（$\max(\text{self.amplitude}) < \text{self.amplitude\_threshold}$）**：`"cluster_size_ToT"`、`"cluster_size_amplitude"`、`"cluster_charge"` 置为 `0`，其余 11 个键（`"ToA"`、`"ToT"`、`"amplitude"`、`"charge"`、`CFD_LABEL`、3 个 `"gravity_center_*"`、3 个 `"gravity_center_*_error"`）全部置为 `None`。
   - **单电极退化档（$\max(\text{self.amplitude}) \ge \text{self.amplitude\_threshold}$ 且 $\text{read\_ele\_num} == 1$）**：`"ToA"`、`"ToT"`、`"amplitude"`、`"charge"`、`CFD_LABEL` 取第 `0` 号电极值；3 个 `"gravity_center_*"` 与 3 个 `"gravity_center_*_error"` 均置为 `0`；`"cluster_size_ToT"`、`"cluster_size_amplitude"`、`"cluster_charge"` 均置为 `1`。
   - **多电极条形档（$\text{read\_ele\_num} > 1$）**：
     - `"ToA"` 与 `CFD_LABEL` 调用 `get_conjoined_time(time_list, self.amplitude)`：在所有满足 `time_list[idx] is not None` 且 `amplitude[idx] > 0` 的电极中，返回 `amplitude[idx]` 最大的电极对应的时间（无有效电极时返回 `None`；若调用 `get_conjoined_time` 时未传 `amplitude_list`，则在 `remove_none(time_list)` 非空时返回最小值 `min`）。
     - 分别对 `(self.ToT, 10e-9)`、`(self.amplitude, self.amplitude_threshold)`、`(self.charge, 0.0)` 调用 `get_total_amp(amp_list, amp_thres)` 与 `get_gravity_center_and_cluster_size(amp_list, amp_thres)`：若 $\max(\text{amp\_list}) == 0$ 或不存在严格满足 $\text{amp\_list}[i] > \text{amp\_thres}$ 的种子电极，总和返回 `None`，重心与团簇大小返回 `(None, 0)`；否则将所有满足 $\text{amp\_list}[i] > \text{amp\_thres}$ 的种子 $i$ 及其左右满足 $\text{amp\_list}[i \pm 1] > 0$ 的紧邻并入集合 `new_seeds`，按式 (13) 计算总和、加权下标重心与成员个数（其中 `"cluster_charge"` 存的是 `charge` 团簇的成员电极数 `len(new_seeds)`）。
     - 对 `ToT`、`amplitude`、`charge` 的重心，若不为 `None`，按式 (14) 计算 `gravity_center_* - original_x / pitch_x` 存入 `"gravity_center_*_error"`，否则存 `None`。

`InputWaveform` 面向一维空间分辨的条形探测器（代码注释 `only available for strip detector`、`assume strip, one dimensional spacial resolution`）；多电极的 `ToA` 与 `CFD50` 由 `get_conjoined_time` 取最大幅度通道的定时；`ToT` 与 `charge` 成簇的种子阈值写死为 `10e-9` $\text{s}$ 与 `0.0` $\text{V}$；`threshold`、`amplitude_threshold` 与 `CFD` 由构造参数给出。

## 软件实现

### 模块与函数分工

- `event.py`：实现单电极脉冲基线扣除、阈值过零线性插值、恒比定时、时间重心计算以及单事例独立重建类。`net_pulse` 计算并扣除脉冲前 200 点基线、给出基线噪声；`get_amplitude`、`crossing`、`get_ToA`、`get_ToT`、`get_CFD50`、`get_CoG` 与 `get_charge` 提取单条正向波形的特征量；`InputWaveform` 配合 `get_conjoined_time`、`get_total_amp`、`get_gravity_center_and_cluster_size` 与 `remove_none` 汇总单事例多条形通道特征。
- `event_table.py`：实现作业级多事例特征提取、跨电极成簇与 `reconstruction_<job>.h5` 文件读写。`lobe_area` 计算包含峰值的正向主瓣积分面积；`electrode_row` 汇总单电极的过阈判定与全部特征列；`cluster` 执行跨电极一维成簇并计算幅度加权中心；`chosen_edges` 解析并校验各电极触发边沿；`event_table` 将整个作业的 `Waveforms` 重建为 `EventTable`；`write_event_table` 与 `read_event_table` 负责 HDF5 事件表文件的一次性写出与读取。

### 核心数据结构

- `EventTable`（`event_table.py`）：单作业重建结果数据类（`@dataclass`），支持 `len(table)` 返回事例行数，包含以下字段：
  - `electrodes`（`list[str]`，无单位）：读出电极名称列表，顺序与二维、三维数据集的电极列顺序一致；
  - `threshold`（`float`，$\text{V}$）：过阈时间、时间重心、主瓣面积及紧邻电极入簇的基线以上电压阈值；
  - `amplitude_threshold`（`float`，$\text{V}$）：事例选中（`selected`）与团簇种子电极的基线以上幅度阈值；
  - `fractions`（`tuple[float, ...]`，无量纲）：恒比定时的比例元组；
  - `edges`（`list[str]`，无单位）：各电极使用的触发边沿方向列表，元素为 `"rising"` 或 `"falling"`；
  - `columns`（`dict[str, np.ndarray]`）：将 `EVENT_COLUMNS`、`ELECTRODE_COLUMNS` 与 `"CFD"` 共 14 个列名映射到对应 NumPy 数组的字典，各数组形状、类型与单位见下节 `reconstruction_<job>.h5` 数据集表。
- `InputWaveform`（`event.py`）：单事例独立重建对象，包含以下属性字段：
  - `times`（`np.ndarray`，形状 `(bins,)`，$\text{s}$）：各时间箱中心时刻；
  - `waveforms`（`list[np.ndarray]`，长度为 `read_ele_num`，$\text{V}$）：各电极基线以上正向电压波形；
  - `read_ele_num`（`int`，个）：读出电极数量；
  - `pitch_x`, `pitch_y`（`float`，与 `original_x` 同单位）：$x$、$y$ 方向电极间距；
  - `CFD`（`float`，无量纲）：恒比定时比例（默认 `0.5`）；
  - `threshold`, `amplitude_threshold`（`float`，$\text{V}$）：单电极过阈阈值与团簇种子幅度阈值；
  - `original_x`（`float`，与 `pitch_x` 同单位）：入射径迹真实 $x$ 坐标；
  - `peak_time`（`list[int]`，无量纲）：各电极峰值所在的时间箱下标列表；
  - `ToA`, `ToT`, `CFD50`（`list[float | None]`，$\text{s}$）：各电极过阈到达时间、过阈持续时间与 50% 恒比定时列表；
  - `amplitude`, `charge`（`list[float]`，$\text{V}$）：各电极峰值幅度与采样点绝对值总和列表；
  - `data`（`dict[str, float | int | None]`）：单事例汇总字典，含 `"ToA"`（$\text{s}$）、`"ToT"`（$\text{s}$）、`"amplitude"`（$\text{V}$）、`"charge"`（$\text{V}$）、`"CFD50"`（$\text{s}$）、`"gravity_center_ToT"` / `"_amplitude"` / `"_charge"`（从 `0` 起的电极下标）、`"cluster_size_ToT"` / `"_amplitude"` / `"cluster_charge"`（个）、`"gravity_center_ToT_error"` / `"_amplitude_error"` / `"_charge_error"`（以 `pitch_x` 为单位的相对位置误差）及 `"original_x"`（与 `pitch_x` 同单位）。

## 接口

使用者能设的只有下表列出的 4 个重建选项键（在 `config.json`、`--set`、`--scan` 或命令行中设置）；其余参数（基线采样点数 `BASELINE_POINTS = 200`、边沿极性系数 `EDGE_SIGN` 及 `InputWaveform` 内部阈值）都写死在代码里。命令行入口与切片调度用法见 [../stages/reconstruction.md](../stages/reconstruction.md)。

### 重建配置键与函数参数

[../stages/reconstruction.md](../stages/reconstruction.md) 中的 `reconstruct` 接收以 $\text{mV}$ 为单位的 `threshold` 与 `amplitude_threshold`，乘以 `MILLIVOLT = 1.0e-3` 换算为 $\text{V}$ 后传入 `event_table`：

| 键名 / 参数名 | 默认值（`stages/chain.py`） | 单位 | 含义 |
| --- | --- | --- | --- |
| `threshold` | `10.0`（环节选项）/ 无默认（`event_table` 参数） | 环节选项：$\text{mV}$；`event_table` 与文件属性：$\text{V}$ | 单电极过阈判定（`above`）、`ToA`、`ToT`、`CoG`、`area` 计算及团簇紧邻电极并入的基线以上阈值 |
| `amplitude_threshold` | `10.0`（环节选项）/ 无默认（`event_table` 参数） | 环节选项：$\text{mV}$；`event_table` 与文件属性：$\text{V}$ | 事例选中（`selected`）与团簇种子电极筛选的基线以上峰值幅度阈值 |
| `fractions` | `[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]` | 无量纲 | 恒比定时（`CFD`）的幅度比例序列，每个元素须严格位于 $(0, 1)$ 开区间内 |
| `edge` | `None` | 无 | 触发边沿方向，取 `"rising"`、`"falling"` 或 `None`；为 `None` 时 `chosen_edges` 沿用输入波形文件的 `pulse_edge` 属性 |

### 输入波形文件属性与数据集

`event_table` 接收 `trigger` 记录事例的波形，由 [电子学读出](readout.md) 的 `read_waveforms` 读为 `Waveforms(electrodes, dt, events, pulse_edge)` 对象；事件表每一行对应其中一个事例。文件的属性与数据集如下：

**输入文件属性（Attributes）**

| 属性名 | 类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `electrodes` | 字符串数组 | 无 | 电路全部读出电极名称列表，决定 `EventTable.electrodes` 的列顺序 |
| `dt` | `float64` | $\text{s}$ | 时间箱宽度 |
| `pulse_edge` | 字符串数组 | 无 | 读出链派生的各电极脉冲边沿方向（`"rising"` 或 `"falling"`），供 `chosen_edges` 作为默认边沿与比对基准 |
| `device_circuit` | JSON 字符串（可选） | $\text{F}$, $\Omega$, $\text{F/m}^2$ | 器件等效电路参数记录 |

**输入数据集（Datasets）**

| 数据集名 | 形状与类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `event` | `(events,)`, `int64` | 无 | 事例编号，还原为 `EventWaveforms.event` |
| `t0` | `(events,)`, `float64` | $\text{s}$ | 该事例首个时间箱的左边界时刻，还原为 `EventWaveforms.t0` |
| `count` | `(events,)`, `int64` | 箱 | 该事例每条已存波形的时间箱数 $N$ |
| `stored` | `(events,)`, `int64` | 个 | 该事例保存了波形的电极数 $M$（无信号事例为 `0`） |
| `index` | `(sum(stored),)`, `int64` | 无 | 每个已存电极在 `electrodes` 中的下标（从 `0` 起），还原为 `EventWaveforms.electrodes` |
| `voltage` | `(sum(stored * count),)`, `float64`（gzip） | $\text{V}$ | 各已存电极在时间箱中心的输出电压，按事例切分重塑为 `(M, N)` 的 `EventWaveforms.voltage` |

### 输出 `reconstruction_<job>.h5` 文件格式

文件由 `write_event_table(path, table)` 一次性写出，由 `read_event_table(path)` 读回为 `EventTable` 对象。

**文件属性（Attributes）**

| 属性名 | 类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `electrodes` | 字符串数组 | 无 | 读出电极名称列表，与二维、三维数据集的电极维顺序一致 |
| `threshold` | `float64` | $\text{V}$ | 过阈定时、时间重心、主瓣面积及紧邻电极入簇阈值（基线以上） |
| `amplitude_threshold` | `float64` | $\text{V}$ | 事例选中与团簇种子电极的幅度阈值（基线以上） |
| `fractions` | `float64` 一维数组，形状 `(fractions,)` | 无量纲 | 恒比定时比例数组，与 `CFD` 数据集第 3 维顺序一致 |
| `edge` | 字符串数组 | 无 | 各电极实际使用的触发边沿方向，元素为 `"rising"` 或 `"falling"`（对应 `EventTable.edges`） |

**数据集（Datasets）**

| 数据集名 | 形状与类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `event` | `(events,)`, `int64` | 无 | Geant4 事例编号 |
| `selected` | `(events,)`, `bool` | 无 | 事例是否含有团簇（即 `cluster_size > 0`，至少一个电极 `amplitude >= amplitude_threshold`） |
| `cluster_size` | `(events,)`, `int64` | 个 | 团簇包含的电极数（无团簇时为 `0`） |
| `cluster_center` | `(events,)`, `float64` | 电极下标（从 `0` 起） | 团簇的幅度加权电极下标中心（无团簇时为 `NaN`） |
| `traced` | `(events, len(electrodes))`, `bool` | 无 | 输入 `readout` 在该事例中是否存有该电极波形；为 `False` 时该电极所有数值列为 `NaN`、`above` 为 `False` |
| `baseline` | `(events, len(electrodes))`, `float64` | $\text{V}$ | 原始波形开头 `200` 个采样点的算术平均值 |
| `noise` | `(events, len(electrodes))`, `float64` | $\text{V}$ | 原始波形开头 `200` 个采样点的总体标准差 |
| `amplitude` | `(events, len(electrodes))`, `float64` | $\text{V}$ | 扣除基线并按 `edge` 翻正后的最大采样值 |
| `above` | `(events, len(electrodes))`, `bool` | 无 | 脉冲是否达到 `threshold`（无波形或 `amplitude < threshold` 时为 `False`；为 `False` 时 `ToA`、`ToT`、`CoG`、`area`、`CFD` 均为 `NaN`） |
| `ToA` | `(events, len(electrodes))`, `float64` | $\text{s}$ | 上升沿越过 `threshold` 的线性插值时刻（未找到过零点或 `above` 为假时为 `NaN`） |
| `ToT` | `(events, len(electrodes))`, `float64` | $\text{s}$ | 从 `ToA` 到下降沿越过 `threshold` 的时间差（记录结束前未降到阈值以下或无 `ToA` 时为 `0.0`；`above` 为假时为 `NaN`） |
| `CoG` | `(events, len(electrodes))`, `float64` | $\text{s}$ | 包含峰值且连续满足净电压 $\ge \text{threshold}$ 的区间内按采样值加权的时间重心 |
| `area` | `(events, len(electrodes))`, `float64` | $\text{V}\cdot\text{s}$ | 包含峰值且连续满足净电压 $> 0$ 的正向主瓣矩形积分面积 |
| `CFD` | `(events, len(electrodes), len(fractions))`, `float64` | $\text{s}$ | 上升沿越过各 `fractions * amplitude` 的线性插值时刻（未找到过零点、峰值 $\le 0$ 或 `above` 为假时为 `NaN`） |

第 $k$ 号电极（按属性 `electrodes` 的顺序，从 `0` 起）比例 $f$ 的恒比时刻是 `CFD[:, k, j]`，$j$ 为 $f$ 在属性 `fractions` 中的下标。`ToA`、`CoG`、`CFD` 与输入事例的 `t0` 在同一时间轴上（式 (1)），`t0` 留在输入波形文件里。

### 绘图输出

`InputWaveform.data` 汇总后由 [统计分析](analysis.md) 的 `WaveformStatistics.draw` 画图：时间分辨高斯拟合图、幅度与电荷朗道拟合图、团簇大小分布图、空间重心误差图及 $\eta$ 校准图。

## 参考文献

- [1] H. Spieler, *Semiconductor Detector Systems*, Oxford University Press (2005)，出处待补
- [2] I. Kipnis, T. Collins, J. DeWitt, S. Dow, A. Frey, A. Grillo, R. Johnson, W. Kroeger, A. Leona, L. Luo, et al., “A time-over-threshold machine: the readout integrated circuit for the BABAR Silicon Vertex Tracker”, IEEE Trans. Nucl. Sci. 44 (1997) 289, doi:10.1109/23.603658
- [3] D. A. Gedcke, W. J. McDonald, “Design of the Constant Fraction of Pulse Height Trigger for Optimum Time Resolution”, Nucl. Instrum. Methods 58 (1968) 253, doi:10.1016/0029-554X(68)90473-4
- [4] R. Turchetta, “Spatial resolution of silicon microstrip detectors”, Nucl. Instrum. Methods Phys. Res. A 335 (1993) 44, doi:10.1016/0168-9002(93)90255-G
