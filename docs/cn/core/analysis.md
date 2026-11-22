# 统计分析（`core/analysis`）

`src/raser/core/analysis/` 承接 [载流子输运](current.md) 写出的各读出电极净感应电荷与初始电子-空穴对数、[事件重建](reconstruction.md) 提取的脉冲定时特征与单事例字典 `InputWaveform.data`、[能量沉积](deposit.md) 记录的最早沉积时刻，以及 [器件定义](device.md) 提供的 `Detector` 几何属性。该包计算逐事例电荷收集效率，使用无分箱截断高斯最大似然迭代拟合提取分布核心宽度作为分辨率，并通过 PyROOT 对单事例波形特征做分箱高斯拟合、朗道拟合及 $\eta$ 位置校准绘图。算出的逐事例收集效率与分布核心宽度交由 [统计分析环节](../stages/analysis.md) 汇总写出单扫描点与跨扫描点结果文件及分布图，`WaveformStatistics` 则直接向磁盘输出 `.pdf`、`.C` 与可选 `.png` 统计图像。

## 物理

### 电荷收集效率

半导体探测器在单个事例中的电荷收集效率（Charge Collection Efficiency, CCE）定义为全部读出电极收集到的带符号净感应电荷代数和的绝对值与雪崩倍增前初始电离电子-空穴对总电荷量之比。该定义不区分电极所收集载流子的极性；当器件存在雪崩倍增时，收集效率可大于 $1$：

$$\eta = \frac{\left|\sum_{j=1}^{N_{\text{ele}}} Q_j\right|}{N_{\text{pairs}}\,e} \tag{1}$$

其中：

- $\eta$：单个事例的电荷收集效率（无量纲）；
- $Q_j$：第 $j$ 个读出电极在该事例中的带符号净感应电荷，$\text{C}$（由 [current.md](current.md) 写出）；
- $N_{\text{ele}}$：读出电极总数（无量纲）；
- $N_{\text{pairs}}$：该事例在雪崩倍增前产生的初始电子-空穴对总数，对（由 [deposit.md](deposit.md) 电离产生并经 [current.md](current.md) 记录）；
- $e$：元电荷，代码中常数 `ELEMENTARY_CHARGE` 取 $1.602176634\times 10^{-19}\ \text{C}$。

式 (1) 由 `collection.py` 中的 `collection_efficiency(charge, pairs)` 计算。半导体辐射探测器的电荷收集效率定义见文献 [1]，元电荷 SI 定值见文献 [2]。

### 分布核心宽度与截断高斯拟合

探测器定时残差（如重建时刻减最早沉积时刻 $t_{\text{reco}} - t_{\text{truth}}$）的分布常带有非高斯长尾，时间分辨率由分布核心区（core）的宽度表征。代码先围绕样本中位数构建鲁棒初始窗口，再在有限窗口 $[a, b]$ 内仅利用落在窗内的样本，将条件概率密度建模为在 $[a, b]$ 上归一化的截断高斯分布，通过无分箱最大似然估计还原完整高斯分布的均值 $\mu$ 与标准差 $\sigma$，并同时以窗口内样本的 $16\%$ 与 $84\%$ 分位数间距之半给出非参数核心半宽 $\sigma_{68}$：

$$m = \operatorname{median}(X), \qquad \text{MAD} = \operatorname{median}\bigl(|X - m|\bigr), \qquad [a_1, b_1] = [m - 8\,\text{MAD},\, m + 8\,\text{MAD}] \tag{2}$$

$$p(x \mid \mu, \sigma; a, b) = \frac{1}{\sqrt{2\pi}\,\sigma\,P_{\text{in}}(\mu, \sigma; a, b)}\exp\!\left(-\frac{(x - \mu)^2}{2\sigma^2}\right), \qquad x \in [a, b] \tag{3}$$

$$P_{\text{in}}(\mu, \sigma; a, b) = \frac{1}{2}\left[\operatorname{erf}\!\left(\frac{b - \mu}{\sqrt{2}\,\sigma}\right) - \operatorname{erf}\!\left(\frac{a - \mu}{\sqrt{2}\,\sigma}\right)\right] \tag{4}$$

$$\mathcal{L}(\tilde{\mu}, \ln\tilde{\sigma}) = \frac{1}{2}\sum_{i=1}^{n}\left(\frac{\tilde{x}_i - \tilde{\mu}}{\tilde{\sigma}}\right)^2 + n\bigl(\ln\tilde{\sigma} + \ln P_{\text{in}}(\tilde{\mu}, \tilde{\sigma}; \tilde{a}, \tilde{b})\bigr) \tag{5}$$

$$\sigma_{\mu} = s\sqrt{\bigl(H^{-1}\bigr)_{00}}, \qquad \sigma_{\sigma} = \sigma\sqrt{\bigl(H^{-1}\bigr)_{11}} \tag{6}$$

$$\sigma_{68} = \frac{q_{0.84}(X_{\text{in}}) - q_{0.16}(X_{\text{in}})}{2} \tag{7}$$

其中：

- $X$：输入的全体一维观测样本序列，与输入量同单位（在 [../stages/analysis.md](../stages/analysis.md) 中为时间差 $t_{\text{reco}} - t_{\text{truth}}$，单位 $\text{s}$）；
- $m, \text{MAD}$：全体样本 $X$ 的中位数与中位绝对偏差，与输入量同单位；$[a_1, b_1]$ 为首轮默认窗口边界；
- $a, b$：当前拟合窗口的下界 `low` 与上界 `high`，与输入量同单位；
- $X_{\text{in}} = \{x_1, \dots, x_n\}$：落在闭区间 $[a, b]$ 内的窗口子样本，$n$ 为窗口内样本数（无量纲）；
- $s$：窗口内子样本 $X_{\text{in}}$ 的总体标准差 `np.std(values)`（`ddof=0`），与输入量同单位；$\tilde{x}_i = x_i / s$、$\tilde{a} = a / s$、$\tilde{b} = b / s$ 为按 $s$ 缩放的无量纲量；
- $\mu, \sigma$：截断前完整高斯分布的均值与标准差（核心宽度），与输入量同单位；$\tilde{\mu} = \mu / s$、$\tilde{\sigma} = \sigma / s = \exp(\ln\tilde{\sigma})$ 为缩放后的无量纲拟合参数；
- $P_{\text{in}}$：完整高斯分布在窗口 $[a, b]$ 内的累积概率（无量纲，代码中记为 `inside`），$\operatorname{erf}$ 为误差函数；
- $\mathcal{L}(\tilde{\mu}, \ln\tilde{\sigma})$：略去与参数无关常数项的无分箱负对数似然函数（无量纲）；
- $H$：$\mathcal{L}$ 在极小值点处关于 $(\tilde{\mu}, \ln\tilde{\sigma})$ 的 $2\times 2$ 海森矩阵（曲率矩阵，无量纲）；$\sigma_{\mu}$ 与 $\sigma_{\sigma}$ 分别为由逆海森矩阵和指数误差传递还原的均值标准误 `mean_error` 与核心宽度标准误 `sigma_error`，与输入量同单位；
- $q_{0.16}(X_{\text{in}}), q_{0.84}(X_{\text{in}})$：窗口内子样本 $X_{\text{in}}$ 的 $16\%$ 与 $84\%$ 分位数，与输入量同单位；$\sigma_{68}$ 为分位数半宽，与输入量同单位（理想未截断高斯分布下等于 $\sigma$）。

单轮截断高斯最大似然拟合由 `resolution.py` 中的 `truncated_gaussian(values, low, high)` 调用 `scipy.optimize.minimize` 的 `"L-BFGS-B"` 算法求解；多轮缩窗迭代由 `core_width(values, window=None)` 执行，缺省 `window=None` 时取式 (2) 为初窗，每轮拟合后将窗口收缩为 $[\mu - 2\sigma,\, \mu + 2\sigma]$，最多迭代 `ROUNDS = 6` 轮。双侧截断正态分布的最大似然参数估计见文献 [3]，无分箱似然拟合与曲率协方差估计见文献 [4]，有界限内存拟牛顿算法 L-BFGS-B 见文献 [5]。

### 直线径迹与残差

几块器件沿束流排成望远镜时（见 [束流望远镜](../bench/telescope.md)），各槽位的团簇位置（[事件重建](reconstruction.md) 的 `cluster_x`、`cluster_y`）按槽位的摆放换到全局坐标（[能量沉积与电离](deposit.md#多块器件的放置) 的式 (17)，取器件坐标 $z = l_z/2$ 的中面）：

$$\begin{pmatrix} X \\ Y \end{pmatrix} = \begin{pmatrix} P_x \\ P_y \end{pmatrix} + \begin{pmatrix} \cos\phi & -\sin\phi \\ \sin\phi & \cos\phi \end{pmatrix}\begin{pmatrix} \bar{x}_c - l_x/2 \\ \bar{y}_c - l_y/2 \end{pmatrix}, \qquad Z = P_z + \frac{l_z}{2} \tag{12}$$

对每个槽位都恰有一个团簇的事例，用参考层集合 $\mathcal{R}$ 的 $(Z_j, X_j)$ 与 $(Z_j, Y_j)$ 各做一次不加权的最小二乘直线拟合，再求各槽位的残差和参考径迹的卡方：

$$k_x = \frac{\sum_{j \in \mathcal{R}}(Z_j - \bar{Z})(X_j - \bar{X})}{\sum_{j \in \mathcal{R}}(Z_j - \bar{Z})^2}, \qquad b_x = \bar{X} - k_x \bar{Z} \tag{13}$$

$$r_{x,s} = k_x Z_s + b_x - X_s, \qquad r_{y,s} = k_y Z_s + b_y - Y_s, \qquad \chi^2 = \sum_{j \in \mathcal{R}}\left(\frac{r_{x,j}^2}{q_{x,j}^2/12} + \frac{r_{y,j}^2}{q_{y,j}^2/12}\right) \tag{14}$$

其中：

- $(\bar{x}_c, \bar{y}_c)$：团簇在槽位器件坐标中的位置，$\mu\text{m}$；
- $\mathbf{P}$、$\phi$：槽位的 `position`（$\mu\text{m}$）与 `rotation_z`（度）；$l_x, l_y, l_z$：该槽位器件的尺寸，$\mu\text{m}$；
- $(X, Y, Z)$：团簇的全局坐标，$\mu\text{m}$；$\bar{X}, \bar{Z}$：参考层上 $X_j$、$Z_j$ 的算术平均；$k_y$、$b_y$ 把式 (13) 的 $X$ 换成 $Y$；
- $k_x, k_y$：径迹斜率，无量纲；$b_x, b_y$：径迹截距，$\mu\text{m}$；
- $r_{x,s}, r_{y,s}$：槽位 $s$（参考层或被测器件）上径迹位置减团簇位置的残差，$\mu\text{m}$；
- $q_{x,j}, q_{y,j}$：参考层 $j$ 的像素间距在全局 $x$、$y$ 方向的取值，$\mu\text{m}$：$\phi$ 为 $0$ 或 $180$ 时是 $(p_x, p_y)$，为 $90$ 或 $270$ 时是 $(p_y, p_x)$；
- $\chi^2$：参考层残差按像素均匀分布方差归一化的和，无量纲。

被测器件 $x$、$y$ 方向残差分布的宽度用上一节的截断高斯拟合求，得到残差标准差 $\sigma_{\text{Tol}}$。由 `tracking.py` 实现。束流望远镜的径迹拟合与残差见文献 [9]。

### 波形统计量与位置校准

面向单事例重建类 `InputWaveform`（定义与特征提取算法见 [reconstruction.md](reconstruction.md)）产出的多事例特征集合，`core/analysis` 对分箱直方图分别采用高斯分布拟合定时量与空间重心残差、采用朗道分布拟合脉冲电荷与幅度及过阈持续时间，并计算真实入射位置相对电极间距的单元内偏移量与重建重心单元内偏移量的二维 $\eta$ 位置校准关系：

$$f_{\text{gaus}}(x) = C \exp\!\left(-\frac{(x - \mu)^2}{2\sigma^2}\right) \tag{8}$$

$$\sigma_{\text{ps}} = 10^{12}\,\sigma, \qquad \sigma_{\sigma,\text{ps}} = 10^{12}\,\sigma_{\sigma} \tag{9}$$

$$f_{\text{landau}}(x) = C\,\phi_{\text{Landau}}\!\left(\frac{x - \text{MPV}}{\xi}\right) \tag{10}$$

$$\delta x_{\text{orig},i} = \frac{x_{\text{orig},i}}{p_x} - \operatorname{round}\!\left(\frac{x_{\text{orig},i}}{p_x}\right), \qquad \delta g_i = g_i - \operatorname{round}(g_i) \tag{11}$$

其中：

- $f_{\text{gaus}}(x), f_{\text{landau}}(x)$：分箱直方图的高斯拟合函数与朗道拟合函数（事例数/箱，无量纲）；
- $C$：直方图拟合幅度常数（ROOT 参数 `0`，无量纲）；
- $\mu, \sigma$：分箱高斯拟合均值（ROOT 参数 `1`）与标准差（ROOT 参数 `2`），单位与被拟合量一致（`ToA` 与 `CFD50` 为 $\text{s}$；重心残差 `gravity_center_*_error` 为电极间距倍数，无量纲）；
- $\sigma_{\text{ps}}, \sigma_{\sigma,\text{ps}}$：`time_resolution_fit` 中将定时标准差 $\sigma$ 及其拟合误差 $\sigma_\sigma$ 由 $\text{s}$ 乘以 $10^{12}$ 换算至图注显示的数值，$\text{ps}$；
- $\text{MPV}, \xi$：朗道分布的位置参数（最可几值参数，ROOT 参数 `1`，代码打印为 `mpv` 并赋给变量 `mean`）与尺度宽度参数（ROOT 参数 `2`，代码中记为 `sigma`），图注统一标为 `a.u.`（其中 `ToT` 输入单位为 $\text{s}$，`amplitude` 与 `charge` 随 `InputWaveform` 输入电压单位）；$\phi_{\text{Landau}}$ 为标准朗道核函数；
- $x_{\text{orig},i}$：第 $i$ 个事例的真实径迹横坐标 `original_x`，$\mu\text{m}$；
- $p_x$：器件 $x$ 方向读出电极有效间距 `pitch_x`，$\mu\text{m}$；
- $g_i$：第 $i$ 个事例由 `ToT`、`amplitude` 或 `charge` 加权求得的一维团簇重心 `gravity_center_*`（从 `0` 起的连续电极下标，无量纲，由 [reconstruction.md](reconstruction.md) 的 `get_gravity_center_and_cluster_size` 给出）；
- $\delta x_{\text{orig},i}, \delta g_i$：真实位置与重建重心各自相对最近整数电极中心的单元内归一化偏移量（无量纲，范围 $[-0.5, 0.5]$）。

式 (8) 与式 (10) 分别由 `waveform_stats.py` 中的 `fit_data_normal` 与 `fit_data_landau` 调用 `ROOT.TF1` 内置模型 `'gaus'` 与 `'landau'`（配合 `TH1.Fit` 的 `"ROQ+"` 选项）拟合；式 (9) 与式 (11) 分别由 `WaveformStatistics.time_resolution_fit` 与 `WaveformStatistics.ita_calibration` 实现。薄层电离能损的朗道分布见文献 [6]，半导体条形探测器电荷共享重心与 $\eta$ 位置校准方法见文献 [7]，ROOT 数据分析与拟合框架见文献 [8]。

## 算法

### 内置常数

下表列出 `collection.py`、`resolution.py` 与 `waveform_stats.py` 中的全部内置物理常数与写死的算法数值。它们均为模块常量或函数内字面量，在器件文件或组件文件中没有对应的配置键：

| 常数或写死数值 | 取值 | 单位 | 定义位置与含义 |
| --- | --- | --- | --- |
| `ELEMENTARY_CHARGE` | `1.602176634e-19` | $\text{C}$ | `collection.py` 中换算初始电离总电荷使用的元电荷 $e$ |
| `ROUNDS` | `6` | 轮 | `resolution.py` 中 `core_width` 缩窗拟合的最大迭代轮数 |
| `MINIMUM_EVENTS` | `20` | 个 | `resolution.py` 中 `core_width` 要求的最小总样本数与单轮窗口内最小样本数 |
| 初窗半宽倍数 | `8` | 无量纲 | `core_width` 在 `window=None` 时围绕中位数 `median` 展开 `deviation`（$\text{MAD}$）的倍数 |
| 缩窗半宽倍数 | `2` | 无量纲 | `core_width` 每轮拟合后围绕 `mean` 更新下一轮窗口边界 `mean ± 2 * sigma` 的倍数 |
| `sigma` 收敛容差 | `5e-3` | 无量纲 | `core_width` 判定相邻两轮 `sigma` 相对变化已收敛的阈值（$0.5\%$） |
| 窗口收缩容差 | `1e-3` | 无量纲 | `core_width` 判定新窗口相对当前窗口宽度不再显著收缩的阈值（$0.1\%$） |
| 分位数区间 | `[0.16, 0.84]` | 无量纲 | `core_width` 计算窗口内样本 `sigma68` 所取的分位数端点 |
| `step` | `1e-4` | 无量纲 | `truncated_gaussian` 计算负对数似然二阶中心差分海森矩阵的无量纲参数步长 |
| `CFD_LABEL` | `"CFD50"` | 无 | `waveform_stats.py` 自 `raser.core.reconstruction.event` 导入的恒比定时通道键名 |
| 波形绘制上限 | `100`（`count > 100`） | 条 | `WaveformStatistics.draw(vis=True)` 为每个读出电极叠加绘制的最大波形条数（最多加入 `101` 条） |
| `n2_bin`（常规 / `CFD50`） | `100` / `30` | 箱 | `time_resolution_fit`（常规 `100` 箱；`model == "CFD50"` 且样本数 $\ge 20$ 时在 `[2%, 98%]` 排序分位区间分 `30` 箱）、`amplitude_fit`（`100` 箱）与 `gravity_center_error_fit`（`100` 箱）的 `TH1F` 箱数 |
| `n2_bin`（重心分布） | `400`（`10*40`） | 箱 | `gravity_center_fill` 中一维重心直方图 `TH1F` 的固定箱数 |
| 团簇大小分箱 | `11`, `[0, 11)` | 箱, 个 | `cluster_size_fill` 中整型直方图 `TH1I` 的箱数与上下界 |
| 重心残差半窗宽 | `1` | 电极间距倍数 | `gravity_center_error_fit` 围绕中位样本 `mid` 构建拟合区间 `[mid - 1, mid + 1]` 的半宽 |
| `n_x`, `n_y`, `[x_min, x_max]`, `[y_min, y_max]` | `20`, `20`, `[-0.5, 0.5]`, `[0.5, -0.5]` | 箱, 电极间距倍数 | `ita_calibration` 中二维直方图 `TH2F` 的箱数与横纵轴范围 |

### 电荷收集效率计算与少事例处理

`collection_efficiency(charge, pairs)`（`collection.py`）按以下步骤执行：

1. **数组转换与维度核对**：将输入转为双精度数组 `charge = np.asarray(charge, dtype="float64")`、`pairs = np.asarray(pairs, dtype="float64")`。若 `charge.ndim != 2` 或 `pairs.shape != charge.shape[:1]`，抛出 `ValueError: charge has shape <charge.shape> and pairs <pairs.shape>, expected (events, electrodes) and (events,)`。
2. **初始对数正值检查**：检查 `np.any(pairs <= 0)`。若存在 `pairs <= 0` 的事例，提取全部零或负对数事例下标 `np.flatnonzero(pairs <= 0).tolist()`，抛出 `ValueError: events <indices> have no pairs`。
3. **计算逐事例收集效率**：按式 (1) 返回 `np.abs(charge.sum(axis=1)) / (pairs * ELEMENTARY_CHARGE)`，输出形状为 `(events,)`。
4. **扫描点汇总与少事例处理**：在下游 [../stages/analysis.md](../stages/analysis.md) 的 `efficiency_spread(efficiencies)` 中，当扫描点汇总的记录事例数 `count = len(efficiencies) < 2` 时，抛出 `TooFewValues: <count> events in the point, a mean and a spread need at least 2`；环节入口 `write_point` 捕获该异常后，在 `result.json` 的 `"collection"` 段记录 `{"events": count, "error": str(too_few)}` 并跳过生成 `efficiency.png`。当 `count >= 2` 时，计算无偏样本标准差 `spread = float(np.std(efficiencies, ddof=1))` 与均值标准误 `spread / np.sqrt(count)`。

### 单轮截断高斯拟合与拟合失败处理

`truncated_gaussian(values, low, high)`（`resolution.py`）对已筛入窗口 `[low, high]` 的样本数组 `values` 按以下顺序拟合：

1. **尺度归一化与等值样本检查**：计算窗口内样本的总体标准差 `scale = float(np.std(values))`。若 `scale == 0`，抛出 `ValueError: all values in the window are equal`。否则令 `x = np.asarray(values, dtype="float64") / scale`、`a = low / scale`、`b = high / scale`、`n = len(x)`。
2. **有界负对数似然最小化**：定义参数向量 `parameters = [mean, ln_sigma]`，其中 $\tilde{\sigma} = \exp(\text{parameters}[1])$。在每次求值时计算标准化残差 `z = (x - mean) / sigma` 与式 (4) 的窗口累积概率 `inside`，按式 (5) 返回 `float(0.5 * np.dot(z, z) + n * (parameters[1] + math.log(inside)))`。调用 `scipy.optimize.minimize`，初值取 `[float(x.mean()), 0.0]`，算法设为 `method="L-BFGS-B"`，参数边界设为 `bounds=[(a, b), (None, None)]` 以强制均值留在窗口 `[a, b]` 内。
3. **未收敛抛错**：若优化器返回 `not fit.success`，立即抛出 `ArithmeticError: the fit in [<low>, <high>] did not converge: <fit.message>`。
4. **中心差分海森矩阵求逆与量纲还原**：在最优参数 `fit.x` 处取步长 `step = 1e-4`，遍历对称指标 `(i, j) in ((0, 0), (0, 1), (1, 1))`，以 $\mathbf{d}_i = \text{step}\cdot\mathbf{e}_i$、$\mathbf{d}_j = \text{step}\cdot\mathbf{e}_j$ 按四点二阶中心差分公式计算 $2\times 2$ 曲率矩阵 `curvature`：
   $$\text{curvature}[i, j] = \text{curvature}[j, i] = \frac{\mathcal{L}(\hat{\boldsymbol{\theta}} + \mathbf{d}_i + \mathbf{d}_j) - \mathcal{L}(\hat{\boldsymbol{\theta}} + \mathbf{d}_i - \mathbf{d}_j) - \mathcal{L}(\hat{\boldsymbol{\theta}} - \mathbf{d}_i + \mathbf{d}_j) + \mathcal{L}(\hat{\boldsymbol{\theta}} - \mathbf{d}_i - \mathbf{d}_j)}{4 \times (10^{-4})^2}$$
   计算逆矩阵对角线平方根 `mean_error, ln_sigma_error = np.sqrt(np.diag(np.linalg.inv(curvature)))`，令 `mean = fit.x[0]`、`sigma = math.exp(fit.x[1])`，返回还原量纲后的 `(mean * scale, mean_error * scale, sigma * scale, sigma * ln_sigma_error * scale)`。

### 核心宽度多轮缩窗迭代与事例不足处理

`core_width(values, window=None)`（`resolution.py`）按以下步骤迭代提取分布核心宽度：

1. **输入维度与总样本数检查**：将 `values` 转为 `float64` 数组。若 `values.ndim != 1`，抛出 `ValueError: values have shape <values.shape>, expected (events,)`。若总样本数 `len(values) < MINIMUM_EVENTS`（`20`），抛出 `TooFewValues: <len(values)> values, fewer than 20`。
2. **设定并校验初始窗口**：
   - 若 `window is None`，计算 `median = np.median(values)` 与 `deviation = np.median(np.abs(values - median))`，按式 (2) 令 `low = median - 8 * deviation`、`high = median + 8 * deviation`（代码注释说明：初窗不截断到样本最小/最大值，避免少样本时以极值点为端点的窗口对拟合呈现平坦分布）；
   - 若 `window` 非 `None`，解包 `low, high = window`。
   - 若 `not low < high`（含 `low >= high` 或存在 `NaN`），抛出 `ValueError: the window [<low>, <high>] is empty`。
3. **迭代缩窗拟合（最多 `ROUNDS = 6` 轮）**：初始化 `fit = None`，对 `round_ = 1, ..., 6` 依次执行：
   - **取窗口内样本**：筛出闭区间子集 `inside = values[(values >= low) & (values <= high)]`。
   - **判断窗口内样本数是否足够**：若 `len(inside) < MINIMUM_EVENTS`（`20`）：
     - 若 `fit is None`（首轮窗口内样本数即少于 `20`），抛出 `TooFewValues: <len(inside)> of <len(values)> values are inside [<low>, <high>], fewer than 20`；
     - 若 `fit is not None`（后续轮次缩窗后样本数少于 `20`），立即 `break` 终止循环，返回上一轮已完成的 `fit`。
   - **单轮拟合与统计记录**：令 `previous = fit`，调用 `truncated_gaussian(inside, low, high)` 获取 `mean, mean_error, sigma, sigma_error`，并按式 (7) 计算 `sigma68 = float(np.diff(np.quantile(inside, [0.16, 0.84]))[0] / 2)`，写入本轮结果字典 `fit`（含 `"events"`、`"window"`、`"window_events"`、`"rounds"`、`"mean"`、`"mean_error"`、`"sigma"`、`"sigma_error"`、`"sigma68"`）。
   - **检查三项收敛与终止条件**：
     1. 若 `previous is not None` 且 `abs(sigma - previous["sigma"]) <= 5e-3 * previous["sigma"]`，`break` 停止迭代；
     2. 计算下一轮候选窗口 `new_low = mean - 2 * sigma`、`new_high = mean + 2 * sigma`，若 `new_low < low` 或 `new_high > high`（新窗口任一端超出旧窗口），`break` 停止迭代；
     3. 若 `(high - low) - (new_high - new_low) <= 1e-3 * (high - low)`（窗口宽度缩减量不超过旧宽度的 $0.1\%$），`break` 停止迭代。
   - **更新窗口**：令 `low, high = new_low, new_high`，进入下一轮。
4. **返回与下游异常分流**：循环结束后返回 `fit`。在 [../stages/analysis.md](../stages/analysis.md) 的 `time_widths` 与 `write_point` 中，对每个时间通道先剔除 `NaN` 样本再调用 `core_width`：若抛出 `TooFewValues`，`write_point` 捕获异常并将原因记入 `result.json` 的 `timing.error`，跳过绘制时间分布图；若样本已满 `20` 个但 `truncated_gaussian` 抛出 `ArithmeticError` 或 `ValueError`，或样本的 MAD 为 `0` 使 `core_width` 自己抛出 `ValueError: the window [...] is empty`，异常向上抛出并中止作业。MAD 为 `0` 即该通道一半以上的 `time - truth` 取同一个值，报错中的窗口上下界就是这个值；此时 `events.h5` 与 `amplitude.png` 已经写出，可从 `events.h5` 中该通道与 `truth` 之差查看这些相同的值，再在 Python 中以 `core_width(values, window=(low, high))` 手给首轮窗口拟合。

### 径迹拟合与被测器件残差宽度（`tracking.py`）

`track_events(hits, placements, roles)` 把一个作业各槽位的重建结果拼成径迹。三个参数都是按槽位名取值的字典，槽位顺序取 `placements` 的顺序；函数只用传入的数据。`hits[槽位]` 是 `SlotHits(event, clusters, cluster_x, cluster_y)`，取自该槽位事件表的同名列。`placements[槽位]` 是 `Placement(position, rotation_z, l_x, l_y, l_z, p_x, p_y)`。`roles[槽位]` 是 `"reference"` 或 `"dut"`。

1. **输入检查**：三个字典的槽位名不相同时抛 `ValueError`（`the slots of hits, placements and roles differ`）；参考层少于 `2` 个，或参考层的 $Z$ 全相同时抛 `ValueError`（`a track needs reference layers at two or more z`）；`rotation_z` 不是 `0`、`90`、`180`、`270` 时抛 `ValueError`。
2. **事例对齐**：全部槽位事例号的并集升序排列，作为结果的行；某槽位没有记录的事例，该槽位团簇数记 `0`。
3. **选中**：每个槽位都恰有 `1` 个团簇的事例记 `selected = True`。
4. **坐标变换与拟合**：团簇数为 `1` 的槽位按式 (12) 求 $(X, Y)$，否则为 `NaN`。选中的事例按式 (13) 求 $k_x, b_x, k_y, b_y$，按式 (14) 求全部槽位的残差与 $\chi^2$；未选中的事例这些量为 `NaN`。
5. 返回 `TrackEvents`：`slots`、`roles`、`z`（各槽位的 $Z$）与各列 `event`、`selected`、`x`、`y`（`(events, slots)`）、`kx`、`bx`、`ky`、`by`、`chi2`（`(events,)`）、`residual_x`、`residual_y`（`(events, slots)`）。

`residual_widths(tracks)` 读一个扫描点各作业的 `TrackEvents`。各作业的 `slots`、`roles` 不相同时抛 `ValueError`。对每个角色为 `"dut"` 的槽位，把各作业选中事例的 `residual_x`、`residual_y` 分别接成一列，各调用一次 `core_width`，返回 `{槽位: {"x": 结果, "y": 结果}}`，结果是 `core_width` 的返回字典，单位 $\mu\text{m}$，其中 `"sigma"` 就是该方向的 $\sigma_{\text{Tol}}$。`core_width` 抛 `TooFewValues` 时，该方向的结果换成 `{"events": 样本数, "error": 报错文字}`。

### 波形统计累积与 ROOT 直方图拟合

`WaveformStatistics`（`waveform_stats.py`）按以下步骤处理 `InputWaveform.data` 单事例字典并生成 ROOT 统计图：

1. **按器件模型设定电极数与间距（`__init__`）**：读取 `det_model = my_d.det_model.lower()`：
   - 若 `det_model == 'planar'` 或 `det_model == 'lgad'`：将 `my_d.read_ele_num` 设为 `1`，令 `self.pitch_x = my_d.l_x`、`self.pitch_y = my_d.l_y`；
   - 若 `'strip' in det_model`：保持 `my_d.read_ele_num` 不变，令 `self.pitch_x = my_d.p_x`、`self.pitch_y = my_d.l_y`；
   - 若 `'pixel' in det_model`：将 `my_d.read_ele_num` 设为 `my_d.x_ele_num * my_d.y_ele_num`，令 `self.pitch_x = my_d.p_x`、`self.pitch_y = my_d.p_y`；
   - 否则抛出 `ValueError: Unsupported detector model for waveform statistics: <my_d.det_model>`。
   随后初始化 `self.data = {}` 与 `self.waveforms = [[] for i in range(my_d.read_ele_num)]`。
2. **追加单事例特征（`fill_data`）**：遍历传入字典 `data` 的每个键 `key`，将 `data[key]` 追加至 `self.data[key]`。
3. **校验输出标签并可选绘制叠加波形（`draw(output_path, tag, vis=False)`）**：
   - 若 `tag is None`，抛出 `ValueError: Waveform statistics output tag must be explicit`。
   - 创建目录 `Path(output_path).mkdir(parents=True, exist_ok=True)`。
   - 若 `vis == True`，对每个电极 $j \in [0, \text{read\_ele\_num} - 1]$ 遍历 `self.waveforms[j]`，以计数器 `count` 控制当 `count > 100` 时跳出循环（每电极最多绘制前 `101` 条波形），构造 `ROOT.TMultiGraph` 并保存 `waveform_electrode_<j>.pdf` 与 `.png`。
4. **定时分布分箱高斯拟合（`time_resolution_fit`）**：依次对 `self.data["ToA"]` 与 `self.data["CFD50"]` 调用 `remove_none` 滤除 `None`：
   - 取 `x2_min = min(data)`、`x2_max = sorted(data)[len(data) - 1]`（若 `data` 为空触发 `ValueError`，打印 `"No valid data for <model>"` 并取 `x2_min = 0`、`x2_max = 0`），默认 `n2_bin = 100`。
   - 若 `model == "CFD50"` 且 `len(data) >= 20`，在排序列表 `sorted_data` 中取下标 `int(0.02 * (len(sorted_data) - 1))` 与 `int(0.98 * (len(sorted_data) - 1))` 对应的值作为 `x2_min` 与 `x2_max`，并改取 `n2_bin = 30`。
   - 填充 `ROOT.TH1F("", "", n2_bin, x2_min, x2_max)`，调用 `fit_data_normal` 在 `[x2_min, x2_max]` 上用 `'gaus'`（选项 `"ROQ+"`）拟合，按式 (9) 将 `sigma` 与 `sigma_error` 乘以 `1e12` 换算为 $\text{ps}$，写出 `<tag>_<model>.pdf` 与 `.C`。拟合的输入与返回值单位均为 $\text{s}$，乘以 `1e12` 后为 $\text{ps}$。
5. **电荷、幅度与过阈时间分箱朗道拟合（`amplitude_fit`）**：依次对 `self.data["charge"]`、`self.data["amplitude"]`、`self.data["ToT"]` 滤除 `None`，取全范围 `[min(data), max(data)]`（空列表捕获 `ValueError` 时置 `[0, 0]`）分 `100` 箱填充 `ROOT.TH1F`，调用 `fit_data_landau` 在 `[x2_min, x2_max]` 上用 `'landau'`（选项 `"ROQ+"`）拟合，在图注打印 `%.3g #pm %.3g a.u.`（分别为朗道 `mpv` 与 `sigma`），写出 `<tag>_<model>.pdf` 与 `.C`。
6. **团簇重心与团簇大小直方图（`gravity_center_fill`、`cluster_size_fill`）**：
   - `gravity_center_fill` 依次对 `"gravity_center_ToT"`、`"gravity_center_amplitude"`、`"gravity_center_charge"` 滤除 `None` 后取 `[min(data), max(data)]`；若为空触发 `IndexError` 或 `ValueError`，打印 `"No valid data for <model>"` 并直接返回。非空时分 `400` 箱填充 `ROOT.TH1F` 并写出 `<tag>_<model>.pdf` 与 `.C`。箱数 `n2_bin = 10*40` 按条形探测器取值，写死在代码里。
   - `cluster_size_fill` 依次对 `self.data["cluster_size_ToT"]`、`self.data["cluster_size_amplitude"]` 与 `self.data["cluster_charge"]`（输出文件名标签为 `"cluster_size_charge"`）滤除 `None`，填入固定区间 `[0, 11)` 共 `11` 箱的 `ROOT.TH1I`，写出 `<tag>_<model>.pdf` 与 `.C`。
7. **重心位置残差分箱高斯拟合（`gravity_center_error_fit`）**：依次对 `"gravity_center_ToT_error"`、`"gravity_center_amplitude_error"`、`"gravity_center_charge_error"` 滤除 `None`，取排序中位值 `mid = sorted(data)[int(len(data) / 2)]`；若为空触发 `IndexError`，打印 `"No valid data for <model>"` 并直接返回。非空时在 `[mid - 1, mid + 1]` 内分 `100` 箱填充 `ROOT.TH1F`，调用 `fit_data_normal` 拟合 `'gaus'`，写出 `<tag>_<model>.pdf` 与 `.C`。
8. **$\eta$ 位置校准二维直方图（`ita_calibration`）**：依次将 `"gravity_center_ToT"`、`"gravity_center_amplitude"`、`"gravity_center_charge"` 与 `self.data["original_x"]` 配对，滤除重心为 `None` 的事例后，按式 (11) 填入 `20 × 20` 箱的 `ROOT.TH2F("", "", 20, -0.5, 0.5, 20, 0.5, -0.5)`，以 `"COLZ"` 绘制并写出 `<tag>_<model>.pdf` 与 `.C`。纵轴参数为 `y_min = 0.5`、`y_max = -0.5`。

## 软件实现

### 模块与函数分工

- `collection.py`：定义元电荷常数 `ELEMENTARY_CHARGE`，实现逐事例电荷收集效率计算函数 `collection_efficiency`。
- `resolution.py`：定义常数 `ROUNDS`、`MINIMUM_EVENTS` 与样本不足异常类 `TooFewValues`，实现单窗口无分箱截断高斯最大似然拟合函数 `truncated_gaussian` 与多轮缩窗迭代求核心宽度函数 `core_width`。
- `tracking.py`：实现望远镜的实验级统计。`track_events` 把各槽位的团簇换到全局坐标、拟合直线径迹并求残差；`residual_widths` 求各被测器件残差的核心宽度；`draw_track`、`draw_residual` 画图。
- `waveform_stats.py`：实现基于 PyROOT 的分箱高斯拟合函数 `fit_data_normal`、分箱朗道拟合函数 `fit_data_landau` 以及面向单事例重建字典的统计绘图类 `WaveformStatistics`。

### 核心数据结构

- `core_width` 返回字典（`resolution.py`）：单通道分布核心宽度的拟合结果字典，包含输入总样本数 `"events"`（个）、末轮拟合窗口 `"window"`（`(low, high)` 二元浮点元组，与输入 `values` 同单位）、末轮窗口内样本数 `"window_events"`（个）、实际执行的拟合轮数 `"rounds"`（轮）、截断高斯拟合均值 `"mean"` 及标准误 `"mean_error"`（与输入同单位）、截断高斯拟合标准差 `"sigma"` 及标准误 `"sigma_error"`（与输入同单位），以及末轮窗口内样本 $16\%$ 至 $84\%$ 分位数间距之半 `"sigma68"`（与输入同单位）。
- `TooFewValues`（`resolution.py`）：继承自 `ValueError` 的异常类，表示样本总数或首轮窗口内样本数低于统计下限（`core_width` 中为 `< 20` 个，`stages/analysis` 的 `efficiency_spread` 中为 `< 2` 个），属于样本统计量的结果状态而非拟合算法崩溃。
- `WaveformStatistics`（`waveform_stats.py`）：多事例波形特征累积与 ROOT 绘图实例，包含器件对象 `detector`（`Detector`）、读出电极有效间距 `pitch_x` 与 `pitch_y`（$\mu\text{m}$）、过阈阈值 `threshold` 与幅度阈值 `amplitude_threshold`（与 `InputWaveform` 输入电压同单位）、输出目录路径字符串 `output_path`（调用 `draw` 后生成）、按特征名汇集各事例数值的字典 `data`（含 `"ToA"`、`"CFD50"`、`"ToT"`［$\text{s}$］，`"amplitude"`、`"charge"`［随输入电压单位］，`"gravity_center_*"`、`"gravity_center_*_error"`［电极间距倍数，无量纲］，`"cluster_size_*"`、`"cluster_charge"`［个］，`"original_x"`［$\mu\text{m}$］），以及按读出电极存放 `(t, v)` 轨迹的列表 `waveforms`（时间为 $\text{s}$，电压随输入波形单位）。

## 接口

命令行入口与实验多扫描点汇总流程见 [../stages/analysis.md](../stages/analysis.md)。`collection_efficiency` 与 `core_width` 的输入全部来自函数参数，统计分析环节以缺省 `window=None` 调用 `core_width`，首轮窗口只能在 Python 中直接调用时给定（[../stages/analysis.md](../stages/analysis.md) 所需的重建阈值、恒比比例与边沿方向均从上游 `reconstruction.h5` 的属性中读取）；在 Python 中调用 `WaveformStatistics(my_d, threshold, amplitude_threshold)` 时从 `Detector` 实例读取下表中的器件键，其余拟合轮数、最小事例数、窗口倍数、海森差分步长与直方图分箱参数全部写死在代码里。

### 器件文件读取的键

| 键或派生属性 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `det_model` | 无（`WaveformStatistics` 必选） | 无 | 器件模型标识；转小写后须为 `'planar'`、`'lgad'` 或包含 `'strip'`、`'pixel'`，决定读出电极数与 `pitch_x`、`pitch_y` |
| `l_x`, `l_y` | 无（必选） | $\mu\text{m}$ | `'planar'` 或 `'lgad'` 下分别作为 `pitch_x`、`pitch_y`；`'strip'` 下 `l_y` 作为 `pitch_y` |
| `p_x`, `p_y` | 见 [device.md](device.md) | $\mu\text{m}$ | `'strip'` 或 `'pixel'` 下 `p_x` 作为 `pitch_x`；`'pixel'` 下 `p_y` 作为 `pitch_y` |
| `read_ele_num` | 见 [device.md](device.md) | 个 | 读出电极总数；`WaveformStatistics.__init__` 在 `'planar'`/`'lgad'` 下将其原地覆写为 `1`，在 `'pixel'` 下原地覆写为 `x_ele_num * y_ele_num` |
| `x_ele_num`, `y_ele_num` | 见 [device.md](device.md) | 个 | `'pixel'` 模式下用于计算读出电极总数 `x_ele_num * y_ele_num` |

### 输入与输出文件

[../stages/analysis.md](../stages/analysis.md) 调用 `collection_efficiency` 与 `core_width` 时读取同一扫描点上 `deposit`、`current`、`reconstruction` 三个节点里的 HDF5 文件，分别从 `points/<点名>/deposit/`、`points/<点名>/current/`、`points/<点名>/reconstruction/` 查看。单点结果 `events.h5` 与 `result.json` 写在这个点的 `analysis` 节点里，从 `points/<点名>/analysis/` 查看；跨点结果 `points.json` 写在 `<实验文件夹>/analysis/` 下。

#### 上游输入文件的属性与数据集

| 来源文件 | 名称与类别 | 形状与类型 | 单位 | 用途 |
| --- | --- | --- | --- | --- |
| `current.h5`（[current.md](current.md)） | 数据集 `event` | `(events,)`, `int64` | 无 | 与 `reconstruction.h5` 的 `event` 核对事例号集合完全一致 |
| `current.h5`（[current.md](current.md)） | 数据集 `charge` | `(events, len(electrodes))`, `float64` | $\text{C}$ | 作为 `collection_efficiency(charge, pairs)` 的 `charge` 输入 |
| `current.h5`（[current.md](current.md)） | 数据集 `pairs` | `(events,)`, `float64` | 对 | 作为 `collection_efficiency(charge, pairs)` 的 `pairs` 输入 |
| `reconstruction.h5`（[reconstruction.md](reconstruction.md)） | 属性 `electrodes` | 字符串数组 | 无 | 校验单电极约束（`len(electrodes) == 1`） |
| `reconstruction.h5`（[reconstruction.md](reconstruction.md)） | 属性 `threshold`, `amplitude_threshold`, `fractions`, `edge` | `float64`, `float64`, `float64[]`, 字符串数组 | $\text{V}$, $\text{V}$, 无量纲, 无 | 校验同扫描点各作业重建参数一致，并将两个阈值除以 `1e-3` 换算为 $\text{mV}$ 写入 `result.json` |
| `reconstruction.h5`（[reconstruction.md](reconstruction.md)） | 数据集 `event`, `selected` | `(events,)`, `int64` / `bool` | 无 | 筛选满足 `selected == True` 的选中事例 |
| `reconstruction.h5`（[reconstruction.md](reconstruction.md)） | 数据集 `ToA`, `ToT`, `CoG`, `amplitude`, `baseline`, `noise` | `(events, electrodes)`, `float64` | 前三项 $\text{s}$，后三项 $\text{V}$ | 提取选中事例在第 `0` 号电极上的定时量与波形电压量 |
| `reconstruction.h5`（[reconstruction.md](reconstruction.md)） | 数据集 `CFD` | `(events, electrodes, fractions)`, `float64` | $\text{s}$ | 提取选中事例在第 `0` 号电极上各恒比分数 `part` 对应的 `CFD<round(100*part)>` 时刻 |
| `deposit.h5`（[deposit.md](deposit.md)） | 数据集 `event`, `count`, `t` | `(recorded_events,)`, `int64` / `(sum(count),)`, `float64` | 无, 步, $\text{s}$ | 取每个事例所有沉积步的最小 `t` 作为真实参考时刻 `truth`（$\text{s}$），将 `time - truth` 传入 `core_width` |

局限：`analysis` 对单槽位实验现在只统计单电极的结果，多电极的统计（例如 cflm 各焊盘的汇总）还没做。

多槽位的望远镜读同一扫描点各作业 `reconstruction` 节点里每个槽位的 `reconstruction.<槽位>.h5`，取 `event`、`clusters`、`cluster_x`、`cluster_y` 四列交给 `track_events`；种子和各层的击中时刻由 `reconstruction` 给出，这里只读。这时 `events.h5` 每个选中事例一行，数据集为 `job`、`event`、`kx`、`ky`（无量纲）、`bx`、`by`（$\mu\text{m}$）、`chi2`（无量纲），以及每个槽位的 `x.<槽位>`、`y.<槽位>`、`residual_x.<槽位>`、`residual_y.<槽位>`（$\mu\text{m}$）；`result.json` 的 `residual.<槽位>.x`、`residual.<槽位>.y` 是 `residual_widths` 对各被测器件给出的结果。

#### 输出文件 `events.h5`

当扫描点总记录事例数 $\ge 1$ 时，写出 `points/<点名>/analysis/events.h5`。文件无 HDF5 属性，包含以下长度等于选中事例数 `selected` 的一维数据集：

| 数据集名 | 形状与类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `job` | `(selected,)`, `int64` | 无 | 事例所属作业在该扫描点作业列表 `jobs` 中的下标（从 `0` 起） |
| `event` | `(selected,)`, `int64` | 无 | 事例在所属作业中的 Geant4 事例编号 |
| `ToA` | `(selected,)`, `float64` | $\text{s}$ | 脉冲越过 `threshold` 的到达时刻（未找到时为 `NaN`） |
| `ToT` | `(selected,)`, `float64` | $\text{s}$ | 脉冲在 `threshold` 以上的持续时间 |
| `amplitude` | `(selected,)`, `float64` | $\text{V}$ | 基线以上的最大脉冲幅度 |
| `baseline` | `(selected,)`, `float64` | $\text{V}$ | 波形开头 `200` 个采样点的算术平均值 |
| `noise` | `(selected,)`, `float64` | $\text{V}$ | 波形开头 `200` 个采样点的总体标准差 |
| `truth` | `(selected,)`, `float64` | $\text{s}$ | 事例在 `deposit.h5` 中最早沉积步的时刻 |
| `CoG` | `(selected,)`, `float64` | $\text{s}$ | 过阈区间内按采样值加权的时间重心 |
| `CFD<percent>` | `(selected,)`, `float64` | $\text{s}$ | 恒比定时时刻，`<percent>` 为 `round(100 * part)`（未找到时为 `NaN`） |

#### 输出文件 `result.json` 与 `points.json` 中的统计量

下表中 `result.json` 指 `points/<点名>/analysis/result.json`，`points.json` 指 `<实验文件夹>/analysis/points.json`。

| 文件与键路径 | 类型或形状 | 单位 | 含义 |
| --- | --- | --- | --- |
| `result.json`: `reconstruction.threshold`, `amplitude_threshold` | `float` | $\text{mV}$ | 重建过阈阈值与团簇种子通道的幅度阈值（有记录事例时写入） |
| `result.json`: `reconstruction.fractions`, `edge` | `list[float]`, `list[str]` | 无量纲, 无 | 恒比定时比例列表与各电极脉冲边沿方向（有记录事例时写入） |
| `result.json`: `collection.events` | `int` | 个 | 该扫描点的记录事例总数 |
| `result.json`: `collection.mean`, `mean_error`, `spread` | `float` | 无量纲 | 全部记录事例 `collection_efficiency` 的均值、均值标准误与样本标准差（`ddof=1`；`events >= 2` 时写入） |
| `result.json`: `collection.error` | `str` | 无 | `events < 2` 时替代 `mean`、`mean_error`、`spread` 写入的 `TooFewValues` 信息 |
| `result.json`: `timing.events`, `selected` | `int` | 个 | 该扫描点的记录事例总数与选中事例数 |
| `result.json`: `timing.polarity` | `float` | 无量纲 | 脉冲边沿极性符号，`"rising"` 为 `1.0`，`"falling"` 为 `-1.0`（有记录事例时写入） |
| `result.json`: `timing.times.<channel>` | `dict` | 见右 | `<channel>` 为 `"ToA"`、`"CoG"` 及各 `"CFD<percent>"`；含 `core_width` 对非 `NaN` 的 `time - truth` 算出的 `"events"`（个）、`"window"`（`[low, high]`，$\text{s}$）、`"window_events"`（个）、`"rounds"`（轮）、`"mean"`、`"mean_error"`、`"sigma"`、`"sigma_error"`、`"sigma68"`（均为 $\text{s}$），以及该通道值为 `NaN` 的选中事例数 `"missing"`（个） |
| `result.json`: `timing.error` | `str` | 无 | 全点 `0` 事例或任一时间通道触发 `TooFewValues` 时替代 `timing.times` 写入的说明 |
| `points.json`: `[i].point`, `[i].<scanned_key>` | `str`, 随选项 | 无, 随选项 | 有结果的扫描点多于 `1` 个时写出；点名与在各点间取值变化的扫描选项键值 |
| `points.json`: `[i].events`, `efficiency`, `efficiency_error`, `selected` | `int`, `float \| null` | 个, 无量纲 | 该点的总记录事例数、平均电荷收集效率及标准误（无结果时为 `null`）与选中事例数 |
| `points.json`: `[i].<channel>` | `dict` | $\text{s}$ | 该点各时间通道的 `{"sigma68", "sigma", "sigma_error"}`（该点无时间分辨结果时省略） |

### 绘图输出

下表列出 `WaveformStatistics.draw(output_path, tag, vis)` 直接生成的 ROOT 统计图，以及 [../stages/analysis.md](../stages/analysis.md) 基于 `collection_efficiency` 与 `core_width` 输出生成的 Matplotlib 统计图；后者中 `points.png` 写在 `<实验文件夹>/analysis/` 下，其余写在 `points/<点名>/analysis/` 下：

| 文件名 | 内容 | 坐标单位 |
| --- | --- | --- |
| `waveform_electrode_<j>.pdf`, `.png` | `WaveformStatistics.draw(vis=True)` 绘制第 $j$ 号电极最多前 `101` 条叠加波形（`TMultiGraph`） | 横轴 $\text{s}$，纵轴随输入波形电压单位 |
| `<tag>_ToA.pdf`, `.C`；`<tag>_CFD50.pdf`, `.C` | `WaveformStatistics.time_resolution_fit` 绘制定时量一维直方图（`ToA` `100` 箱；`CFD50` 在样本数 $\ge 20$ 时取 `[2%, 98%]` 分位区间 `30` 箱）与 `'gaus'` 拟合曲线，图注标出 $\sigma \pm \sigma_\sigma$（$\text{ps}$） | 横轴 `<model> [s]`，纵轴 `Events`（个） |
| `<tag>_charge.pdf`, `.C`；`<tag>_amplitude.pdf`, `.C`；`<tag>_ToT.pdf`, `.C` | `WaveformStatistics.amplitude_fit` 绘制 `100` 箱一维直方图与 `'landau'` 拟合曲线，图注标出 `mpv ± sigma a.u.` | 横轴 `<model> [a.u.]`（`ToT` 填入值单位为 $\text{s}$），纵轴 `Events`（个） |
| `<tag>_gravity_center_ToT.pdf`, `.C`；`..._amplitude.pdf`, `.C`；`..._charge.pdf`, `.C` | `WaveformStatistics.gravity_center_fill` 在非空数据下绘制 `400` 箱一维团簇重心直方图 | 横轴 `<model>`（电极下标，无量纲），纵轴 `Events`（个） |
| `<tag>_cluster_size_ToT.pdf`, `.C`；`..._amplitude.pdf`, `.C`；`..._charge.pdf`, `.C` | `WaveformStatistics.cluster_size_fill` 在 `[0, 11)` 区间绘制 `11` 箱团簇大小整型直方图 `TH1I` | 横轴 `<model>`（电极数，个），纵轴 `Events`（个） |
| `<tag>_gravity_center_ToT_error.pdf`, `.C`；`..._amplitude_error.pdf`, `.C`；`..._charge_error.pdf`, `.C` | `WaveformStatistics.gravity_center_error_fit` 在非空数据下围绕中位点 `mid ± 1` 绘制 `100` 箱一维位置残差直方图与 `'gaus'` 拟合曲线 | 横轴 `<model>`（电极间距倍数，无量纲），纵轴 `Events`（个） |
| `<tag>_ita_calibration_ToT.pdf`, `.C`；`..._amplitude.pdf`, `.C`；`..._charge.pdf`, `.C` | `WaveformStatistics.ita_calibration` 绘制 `20 × 20` 箱二维 $\eta$ 位置校准图 `TH2F`（`"COLZ"`） | 横轴 `Original x`（`[-0.5, 0.5]`，电极间距倍数），纵轴 `Reconstructed x`（`[0.5, -0.5]`，电极间距倍数） |
| `track_<事例号>` | `tracking.py` 的 `draw_track` 对前 `analysis.plots` 个选中事例各画一张：左 $X$-$Z$、右 $Y$-$Z$，参考层实心点、被测器件空心点与式 (13) 的直线 | 横轴 `z [mm]`，纵轴 `x [μm]`、`y [μm]` |
| `residual_<槽位>` | `tracking.py` 的 `draw_residual` 对每块被测器件画一张：左 `residual_x`、右 `residual_y`，`mean ± 8 * sigma` 内 `64` 箱的直方图、末轮窗口阴影与截断高斯曲线，图例标 $\sigma_{\text{Tol}}$ | 横轴 `Residual x [μm]`、`Residual y [μm]`，纵轴 `Events` |
| `efficiency.png` | `stages/analysis` 在记录事例数 $\ge 2$ 时绘制全部记录事例的电荷收集效率 `60` 箱直方图与均值竖虚线 | 横轴 `charge collection efficiency`（无量纲），纵轴 `events`（个） |
| `amplitude.png` | `stages/analysis` 在记录事例数 $\ge 1$ 时绘制选中事例脉冲幅度 `60` 箱直方图与 `amplitude_threshold` 竖虚线 | 横轴 `amplitude above the baseline [mV]`，纵轴 `events`（个） |
| `time_difference.png` | `stages/analysis` 在时间通道拟合成功时以 `3 × 4` 子图绘制 `ToA`、`CoG` 及前 `10` 个 `CFD*` 通道在 `mean ± 8 * sigma` 内的 `64` 箱时间差直方图、末轮窗口阴影与截断高斯曲线 | 横轴 `<channel> - truth [ps]`，纵轴事例数（个） |
| `resolution_of_fraction.png` | `stages/analysis` 绘制各 `CFD*` 通道的截断高斯 `sigma`（带误差棒）与 `sigma68` 随恒比比例变化图 | 横轴 `fraction of the CFD`（无量纲），纵轴 `width of time - truth [ps]` |
| `points.png` | `stages/analysis` 在多扫描点且唯一变化扫描项为数值时，绘制收集效率（左）与各 `CFD*` 通道 `sigma`（右）随扫描变量的变化曲线 | 横轴 `<scanned_key>`，左纵轴 `charge collection efficiency`（无量纲），右纵轴 `sigma of time - truth [ps]` |

## 参考文献

- [1] H. Spieler, *Semiconductor Detector Systems*, Oxford University Press (2005), ISBN 978-0-19-852784-8, doi:10.1093/acprof:oso/9780198527848.001.0001
- [2] E. Tiesinga, P. J. Mohr, D. B. Newell, B. N. Taylor, “CODATA recommended values of the fundamental physical constants: 2018”, Rev. Mod. Phys. 93 (2021) 025010, doi:10.1103/RevModPhys.93.025010
- [3] A. C. Cohen, “Estimating the Mean and Variance of Normal Populations from Singly Truncated and Doubly Truncated Samples”, Ann. Math. Statist. 21 (1950) 557, doi:10.1214/aoms/1177729751
- [4] F. James, *Statistical Methods in Experimental Physics*, 2nd ed., World Scientific (2006), doi:10.1142/6096
- [5] R. H. Byrd, P. Lu, J. Nocedal, C. Zhu, “A Limited Memory Algorithm for Bound Constrained Optimization”, SIAM J. Sci. Comput. 16 (1995) 1190, doi:10.1137/0916069
- [6] L. D. Landau, “On the energy loss of fast particles by ionisation”, in *Collected Papers of L. D. Landau*, Elsevier (1965) 417, doi:10.1016/B978-0-08-010586-4.50061-4
- [7] E. Belau, R. Klanner, G. Lutz, E. Neugebauer, H. J. Seebrunner, A. Wylie, T. Böhringer, L. Hubbeling, P. Weilhammer, J. Kemmer, U. Kötz, M. Riebesell, “Charge collection in silicon strip detectors”, Nucl. Instrum. Methods Phys. Res. 214 (1983) 253, doi:10.1016/0167-5087(83)90591-4
- [8] R. Brun, F. Rademakers, “ROOT — An object oriented data analysis framework”, Nucl. Instrum. Methods Phys. Res. A 389 (1997) 81, doi:10.1016/S0168-9002(97)00048-X
- [9] H. Jansen et al., “Performance of the EUDET-type beam telescopes”, EPJ Tech. Instrum. 3 (2016) 7, doi:10.1140/epjti/s40485-016-0033-2
