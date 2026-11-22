# 载流子漂移与感应电流（`core/current`）

`src/raser/core/current/` 承接 [能量沉积](deposit.md) 给出的电子-空穴对及产生坐标、时刻，以及 [器件场](field.md) 提供的电场、掺杂、导电标志、俘获率与权重电势。该包模拟载流子团簇的漂移、扩散、俘获与雪崩倍增，计算各读出电极上的时域感应电流与净感应电荷，并写出 `current.h5` 文件（多位置实验为 `current.<位置>.h5`；另提供激光脉冲卷积与无场像素纯扩散收集接口）。输出的电流波形交给 [电子学读出](readout.md)，净感应电荷与初始对数交给 [统计分析](analysis.md)。

## 物理

### 漂移

半导体中的电子和空穴在电场作用下获得与电场共线的平均漂移速度，空穴沿电场方向运动，电子逆电场方向运动。代码中按局部场强、温度与净掺杂浓度求取迁移率，漂移速度为：

$$\mathbf{v}(\mathbf{r}) = \pm \mu\bigl(T,\, N_{\text{eff}}(\mathbf{r}),\, E(\mathbf{r})\bigr)\,\mathbf{E}(\mathbf{r}) \tag{1}$$

其中：

- $\mathbf{v}$：载流子漂移速度，$\text{cm/s}$（推进位置坐标 $\mathbf{r}$ [$\mu\text{m}$] 时乘以换算因子 $10^4\ \mu\text{m/cm}$）；
- 正号对应空穴，负号对应电子；
- $\mathbf{E}(\mathbf{r})$：位置 $\mathbf{r}=(x, y, z)$（$\mu\text{m}$）处的电场强度矢量，$\text{V/cm}$，$E = |\mathbf{E}|$ 为其模长；
- $T$：器件温度，$\text{K}$；
- $N_{\text{eff}}(\mathbf{r})$：位置 $\mathbf{r}$ 处的有效净掺杂浓度，$\text{cm}^{-3}$；
- $\mu$：载流子迁移率，$\text{cm}^2/(\text{V}\cdot\text{s})$。

迁移率由 `Material(material).cal_mobility` 计算，具体参数化见 [model.md](model.md)。迁移率模型按名字注册，器件文件按名字选用；每种材料有缺省选用的模型：Si 为 `"Selberherr"`，SiC（4H-SiC）为 `"Das"`，Diamond 为 `"Pernegger"`。`core/current` 用器件选用的模型求迁移率。半导体载流子漂移输运见文献 [1]。

### 扩散

载流子在晶格热运动中发生随机散射，在空间产生扩散展宽。扩散系数由非简并条件下的 Einstein 关系给出，时间间隔 $\Delta t$ 内每个坐标轴上的位移服从零均值高斯分布：

$$D = \frac{\mu k_B T}{e} \tag{2}$$

$$\sigma = 10^{4}\sqrt{2 D \Delta t} \tag{3}$$

其中：

- $D$：扩散系数，$\text{cm}^2/\text{s}$；
- $\mu$：载流子迁移率，$\text{cm}^2/(\text{V}\cdot\text{s})$（有场漂移中为当前场强下的迁移率；无场纯扩散收集中为零场电子迁移率 $\mu_n(T, N_{\text{eff}}, 0)$）；
- $k_B/e$：玻尔兹曼常数与元电荷之比，取 CODATA 2018 值 $8.617333262\times 10^{-5}\ \text{eV/K}$（数值上等于 $k_B/e$，单位 $\text{V/K}$）；
- $T$：器件温度，$\text{K}$；
- $\Delta t$：时间步长，$\text{s}$；
- $\sigma$：单步内每个坐标轴方向高斯随机位移的标准差，$\mu\text{m}$（$10^4$ 为 $\mu\text{m/cm}$ 换算因子）。

局限：在有场漂移（`drift.py`）和无场纯扩散（`diffusion.py`）中，整个载流子团簇均作为单个载流子施加同一随机位移，不展开团簇内部的扩散展宽。Einstein 关系见文献 [2]。

### 俘获

受辐照半导体中的深能级缺陷在载流子输运过程中俘获自由载流子，使团簇中仍参与感应的存活载流子数按指数衰减。沿漂移轨迹 $\mathbf{r}(t')$ 积分局部俘获率，时刻 $t$ 的存活载流子数为：

$$N(t) = N_0 \exp\!\left(-\int_{t_0}^{t} \Gamma\bigl(\mathbf{r}(t')\bigr)\,dt'\right) \tag{4}$$

其中：

- $N(t)$：时刻 $t$（$\text{s}$）团簇尚未被俘获的带符号载流子数（无量纲）；
- $N_0$：初始时刻 $t_0$（$\text{s}$）的带符号载流子数（无量纲）；
- $\Gamma(\mathbf{r})$：位置 $\mathbf{r}$（$\mu\text{m}$）处的载流子俘获率，$\text{s}^{-1}$，由 [field.md](field.md) 的 `DevsimField.get_trap_e`（电子）与 `DevsimField.get_trap_h`（空穴）提供。

仅当器件配置了非空的 `irradiation_model` 时计算俘获衰减；否则不计俘获（等效 $\Gamma = 0$）。深能级缺陷俘获动力学见文献 [3]，辐照硅探测器中有效俘获率与指数存活模型见文献 [4]。

### Shockley-Ramo 感应

运动电荷在任一读出电极上感应的瞬时电流由 Shockley-Ramo 定理给出。将目标电极电势置 $1$、其余电极置 $0$ 并去除空间电荷所得的无量纲解为该电极的权重电势 $\phi_w(\mathbf{r})$，对应权重电场 $\mathbf{E}_w = -\nabla \phi_w$，瞬时感应电流与步间感应电荷为：

$$i(t) = -q\,\mathbf{v}(t)\cdot\mathbf{E}_w\bigl(\mathbf{r}(t)\bigr) \tag{5}$$

$$\Delta Q = \int_{t_1}^{t_2} i(t)\,dt = q\,\bigl[\phi_w(\mathbf{r}_2) - \phi_w(\mathbf{r}_1)\bigr] \tag{6}$$

其中：

- $i(t)$：电极上的瞬时感应电流，$\text{A}$；
- $q = N e_0$：团簇所带电荷，$\text{C}$（$N$ 为带符号载流子数，空穴取正、电子取负；元电荷取 CODATA 2018 值 $e_0 = 1.602176634\times 10^{-19}\ \text{C}$）；
- $\mathbf{v}(t)$：载流子速度，$\text{cm/s}$；
- $\mathbf{E}_w(\mathbf{r})$：权重电场，$\text{cm}^{-1}$；
- $\phi_w(\mathbf{r})$：无量纲权重电势（代码注释中亦记为 $U_w$），由 `DevsimField.get_w_p` 给出并截断于 $[0, 1]$；
- $\Delta Q$：团簇在 $[t_1, t_2]$（$\text{s}$）内由 $\mathbf{r}_1$ 移动至 $\mathbf{r}_2$（$\mu\text{m}$）在该电极上感应的电荷，$\text{C}$。

代码实际采用电势差形式式 (6) 逐计算步累加感应电荷。Shockley-Ramo 定理见文献 [5, 6]。

### 碰撞电离倍增

在高电场区域，载流子获得足够动能通过碰撞电离产生次级电子-空穴对。沿漂移方向单位路程上的载流子数增长率由局部碰撞电离系数决定：

$$\frac{dN}{ds} = \alpha(E, T)\,N \tag{7}$$

其中：

- $N$：载流子数（无量纲）；
- $s$：载流子沿电场漂移方向经过的路程，$\text{cm}$（由位置坐标 $\mu\text{m}$ 乘以 $10^{-4}\ \text{cm}/\mu\text{m}$ 换算）；
- $\alpha(E, T)$：碰撞电离系数，$\text{cm}^{-1}$（电子记 $\alpha_n$，空穴记 $\alpha_p$）；
- $E$：局部电场模长，$\text{V/cm}$；$T$：器件温度，$\text{K}$。

多维场（`local_path`）直接沿原生载流子漂移路径积分式 (7)。一维平板器件（`planar_integral`）同时计入电子与空穴的双向电离反馈。以电子出射面为起点 $b$（峰值场强处 $E_z > 0$ 时取前表面 $z_0$，$E_z < 0$ 时取后表面 $z_M$），沿从 $b$ 指向对面的深度坐标 $z \in [0, W]$（$\text{cm}$，$W$ 为网格深度跨度），在深度 $z$ 处产生一对电子-空穴所对应的稳态倍增因子 $M(z)$ 与净增对数（净增益）$G(z)$ 为：

$$K(z) = \exp\!\left(\int_{0}^{z} \bigl[\alpha_n(z') - \alpha_p(z')\bigr]\,dz'\right) \tag{8}$$

$$G(z) = M(z) - 1 = \frac{K(z)}{1 - \int_{0}^{W} \alpha_p(z')\,K(z')\,dz'} - 1 \tag{9}$$

其中：

- $K(z)$：无量纲深度因子；
- $\alpha_n(z'), \alpha_p(z')$：深度 $z'$ 处的电子与空穴碰撞电离系数，$\text{cm}^{-1}$；
- $\int_{0}^{W} \alpha_p(z')\,K(z')\,dz'$：击穿积分（无量纲），当该值 $\ge 1$ 时器件雪崩击穿；
- $M(z)$：总倍增因子（无量纲），$G(z)$ 为每对原生电子-空穴额外产生的次级对数（`planar_gain_at` 返回值）。

一维稳态双载流子倍增积分见文献 [7]。碰撞电离系数由 `Material(material, avalanche_model=avalanche_model).cal_coefficient` 提供，具体公式与参数见 [model.md](model.md)，支持三种模型：

- `"vanOverstraeten"`（Si 缺省）：van Overstraeten–de Man 分段 Chynoweth 定律，场强低于 $1.75\times 10^5\ \text{V/cm}$ 时置零 [8]；经光学声子能量 $\hbar\omega = 0.063\ \text{eV}$ 引入的温度因子，物理来源见 [12]，这种写法取自 [13]。
- `"Okuto"`（Si）：Okuto–Crowell 模型，场强不高于 $1.0\times 10^5\ \text{V/cm}$ 时置零 [9]。
- `"Hatakeyama"`（4H-SiC 缺省）：Hatakeyama 各向异性模型，按相对 $\langle 0001\rangle$ 偏向 $\langle 11\bar{2}0\rangle$ 的 $4^\circ$ 偏轴角计算，场强不高于 $10^4\ \text{V/cm}$ 时置零 [10, 11]；经光学声子能量 $\hbar\omega = 0.19\ \text{eV}$ 引入的温度因子，物理来源见 [12]，取值见 [14]（原文只对电子给出，代码对空穴也取这个值）。

## 算法

### 内置常数

下表列出 `drift.py`、`cal_current.py` 与 `diffusion.py` 中的全部内置物理常数与数值步长参数。它们是模块常量，器件文件里没有对应的键；时间窗、步长和 `max_drift_time` 都按器件维度取表中的值：

| 常数名 | 1D（或所选二维网格在横向 $x$-$y$ 平面） | 2D / 3D | 单位 | 定义位置与含义 |
| --- | --- | --- | --- | --- |
| `t_bin` | `5e-12` | `50e-12` | $\text{s}$ | current 的输出时间步：感应电流时间箱宽度（文件属性 `dt`） |
| `t_start`（相对值） | `-1.25e-9` | `-12.5e-9` | $\text{s}$ | 相对事例最早产生时刻的起始偏移（`-0.25 * t_end`） |
| `t_end`（相对值） | `5e-9` | `50e-9` | $\text{s}$ | 相对事例最晚产生时刻的最小结束偏移 |
| `delta_t` | `2e-12` | `20e-12` | $\text{s}$ | 载流子单步漂移时间步长 $\Delta t$ |
| `min_intensity` | `1` | `1` | $\text{V/cm}$ | 停止漂移的最低场强阈值（`"low_field"`） |
| `max_drift_time` | `100e-9` | `100e-9` | $\text{s}$ | 单团簇最大漂移时长上限（`"time_out"`） |
| `kboltz` | `8.617333262e-5` | `8.617333262e-5` | $\text{eV/K}$ | `drift.py` 中热扩散使用的 CODATA 2018 玻尔兹曼常数（数值等于 $k_B/e$ [$\text{V/K}$]） |
| `e0` | `1.602176634e-19` | `1.602176634e-19` | $\text{C}$ | `drift.py` 中 Shockley-Ramo 感应电荷使用的 CODATA 2018 元电荷 |
| `edge_sampling` | `0.05` | `0.05` | $\mu\text{m}$ | `split_at_conductor_edges` 探测导电边界的默认采样间距 |
| `edge_tolerance` | `1e-4` | `1e-4` | $\mu\text{m}$ | `split_at_conductor_edges` 二分定位导电边界的默认容差 |
| `BOLTZMANN` | `8.617333262e-5` | `8.617333262e-5` | $\text{eV/K}$ | `diffusion.py` 中纯扩散使用的 CODATA 2018 玻尔兹曼常数 |
| `ELEMENTARY_CHARGE` | `1.602176634e-19` | `1.602176634e-19` | $\text{C}$ | `diffusion.py` 中换算电流与电荷使用的 CODATA 2018 元电荷 |

### 时间窗、时间箱与初始团簇筛选

单个事例进入 `CalCurrent` 后按以下步骤初始化：

1. **选取档位**：若 `field` 段选用的二维网格在横向 $x$-$y$ 平面，取 `t_bin[1]`、`t_end[1]`、`t_start[1]`、`delta_t[1]`；否则按 `my_d.dimension` 取对应档位。
2. **确定时间窗与箱数**：取所有输入沉积步产生时刻 $t_m$（$\text{s}$）的最小值 $t_{\min}$ 与最大值 $t_{\max}$（无输入时均取 $0.0$）。令首个时间箱左边界 $t_{\text{start}} = t_{\min} + \text{relative\_start}$，初始箱数 $n_{\text{bin}} = \lceil (t_{\max} + \text{relative\_end} - t_{\text{start}}) / t_{\text{bin}} \rceil$。若浮点误差导致 $t_{\text{start}} + n_{\text{bin}} t_{\text{bin}} < t_{\max} + \text{relative\_end}$，则递增 $n_{\text{bin}}$ 直至满足覆盖条件，最终令 $t_{\text{end}} = t_{\text{start}} + n_{\text{bin}} t_{\text{bin}}$。
3. **确定读出电极名**：调用 `electrode_names(read_out_contact, read_ele_num)`。若 `read_out_contact` 长度等于 `read_ele_num`，取各项 `"name"`；若长度为 `1`，生成 `"<name>1"` 至 `"<name><read_ele_num>"`；其余情况抛出 `ValueError`。
4. **统计总对数并筛选空间位置**：将全部输入 `ionized_pairs` 之和记为 `pairs`。随后仅保留同时满足以下条件的沉积步 $(x, y, z, t)$：
   - 位于器件边界内：$0 \le x \le l_x$、$0 \le y \le l_y$、$0 \le z \le l_z$；
   - 位于居中电极阵列投影范围内：对 $x$、$y$ 轴分别令首电极左边界 $u_{\text{first}} = (l_u - N_u p_u)/2$，计算电极索引 $i_u = \lfloor (u - u_{\text{first}})/p_u \rfloor$（右边界 $u = u_{\text{first}} + N_u p_u$ 归入 $N_u - 1$），要求 $0 \le i_x < N_x$ 且 $0 \le i_y < N_y$。
5. **统计灵敏对数并启动漂移**：在通过筛选的沉积步中，将满足 `not my_f.get_conductive(x, y, z)` 的对数之和记为 `sensitive_pairs`。将通过筛选的各步分别以 `-n_pairs` 与 `+n_pairs` 构造电子与空穴团簇，先将全部电子团簇逐个完整漂移至停止，再将全部空穴团簇逐个完整漂移至停止（固定随机流抽取顺序）。

对于横跨导电区与耗尽区边界的粒子步，模块另提供辅助函数 `split_at_conductor_edges(start, middle, pairs, conducts, spacing, tolerance)`：先还原步末点 $\mathbf{r}_{\text{end}} = 2\mathbf{r}_{\text{mid}} - \mathbf{r}_{\text{start}}$，以不大于 `spacing`（默认 `0.05` $\mu\text{m}$）的间距采样 `conducts(x, y, z)`，对导电状态发生跳变的相邻采样区间用二分法细化至长度 $\le$ `tolerance`（默认 `1e-4` $\mu\text{m}$），将整步切分为若干子段并按各段长度比例分配对数、置于子段中点。局限：厚度小于 `spacing` 的导电层可能未被采样命中而漏检。

### 单步推进与停止条件

单个团簇从 $(\mathbf{r}_0, t_0)$ 出发，在 `drift` 循环中反复调用 `advance` 直至 `reason` 非空。每一步按以下严格顺序执行：

1. **超时判定（`"time_out"`）**：若 $t - t_0 \ge \text{max\_drift\_time}$，立即停止并记 `reason = "time_out"`。
2. **导电区判定（`"collected"`）**：若 `my_f.get_conductive(x, y, z)` 为真，立即停止并记 `reason = "collected"`。哪里算导电区由场模块在该偏压下划分：所在网格单元的节点全都导电才算，见 [field.md](field.md)。
3. **无场判定（`"no_field"`）**：调用 `my_f.get_e_field_cached(x, y, z)` 获取 $\mathbf{E} = (E_x, E_y, E_z)$（$\text{V/cm}$）。若抛出 `ValueError`，立即停止并记 `reason = "no_field"`；若任一分量非有限数（`NaN` 或 `Inf`），抛出 `ValueError`。
4. **低场判定（`"low_field"`）**：计算场强模长 $E = \sqrt{E_x^2 + E_y^2 + E_z^2}$。若 $E \le \text{min\_intensity}$，立即停止并记 `reason = "low_field"`。
5. **计算漂移步**：读取局部掺杂 $N_{\text{eff}} = \text{my\_f.get\_doping\_cached}(x, y, z)$（$\text{cm}^{-3}$），调用 `mobility(T, N_eff, carriers, E)` 得 $\mu$（$\text{cm}^2/(\text{V}\cdot\text{s})$），取极性符号 $s = +1$（`carriers > 0`）或 $-1$，计算固定步长 $\Delta t$ 的漂移位移：
   $$\Delta \mathbf{r} = s\,\mu\,\mathbf{E}\,\Delta t \times 10^4 \quad [\mu\text{m}]$$
6. **叠加高斯热扩散步**：若 `diffusion=True`，计算式 (3) 给出的各轴标准差 $\sigma$（$\mu\text{m}$），从独立随机流 `stream("drift")` 对 $x, y, z$ 三个方向各独立抽取一个 $\mathcal{N}(0, \sigma^2)$ 样本加到 $\Delta \mathbf{r}$ 上。若 `diffusion=False`，不请求随机流。`diffusion` 是 `CalCurrent` 的构造参数，器件文件里没有对应的键：`write_induced_currents` 总用默认值 `True`，`write_laser_currents` 总用 `False`。
7. **穿出器件表面截断（`"left_device"`）**：初始化步内保留比例 $f = 1.0$。对每个坐标轴 $u \in \{x, y, z\}$（对应器件尺寸 $L_u$）：
   - 若 $u + \Delta u < 0$，更新 $f \leftarrow \min(f, -u / \Delta u)$；
   - 若 $u + \Delta u > L_u$，更新 $f \leftarrow \min(f, (L_u - u) / \Delta u)$。

   若 $f > 0$，更新 $\mathbf{r} \leftarrow \mathbf{r} + f\,\Delta\mathbf{r}$、$t \leftarrow t + f\,\Delta t$，并将 $(\mathbf{r}, t)$ 追加到轨迹 `path`。若 $f < 1$，停止并记 `reason = "left_device"`。

### 俘获存活数计算

`drift_all` 在同号团簇全部漂移完成后一次性计算俘获存活数。当 `my_d.irradiation_model is None` 时跳过俘获，`remaining` 置为 `None`。否则对每条含 $M$ 个点（$M - 1$ 步）的路径 $\{(\mathbf{r}_k, t_k)\}_{k=0}^{M-1}$：

1. 按团簇电荷符号选用 `my_f.get_trap_h_cached`（空穴）或 `my_f.get_trap_e_cached`（电子），在每一步的**步首**位置 $\mathbf{r}_k$ 读取俘获率 $\Gamma_k$（$\text{s}^{-1}$，$k = 0, \dots, M - 2$），并在整步 $[t_k, t_{k+1}]$ 内视为常数。
2. 计算各步衰减量 $d_k = \Gamma_k (t_{k+1} - t_k)$。
3. 在各步**步中点**取存活载流子数（`surviving`），用于感应电荷与局部雪崩计算：
   $$N_{k + 1/2} = N_0 \exp\!\left(-\sum_{j=0}^{k-1} d_j - \frac{1}{2} d_k\right)$$
4. 若需要求某步内任意比例 $\eta \in [0, 1]$ 处的存活数（`surviving_at`，用于一维平板增益穿层计算），则取：
   $$N_{k + \eta} = N_0 \exp\!\left(-\sum_{j=0}^{k-1} d_j - \eta\, d_k\right)$$

`count_ends` 汇总各停止原因对应的载流子数时，取无符号值；若开启俘获且路径至少走了一步，取最后一步中点的存活数 $|N_{M - 3/2}|$，否则取初始数 $|N_0|$。

### 感应电荷分箱

`CalCurrent.binned` 为每个电极分配长度为 $n_{\text{bin}} + 2$ 的浮点数组 `bins`（$\text{A}$），下标 `0` 为欠流箱（$t < t_{\text{start}}$），下标 `1` 至 `n_bin` 为时间窗内各箱，下标 `n_bin + 1` 为溢流箱（$t \ge t_{\text{end}}$）。对每条点数 $\ge 2$ 的路径：

1. **确定待算电极与权重势平移量（`electrodes_near`）**：
   - 若 `len(read_out_contact) != 1`，计算所有读出电极，权重势偏移量均为 $(0, 0)$。
   - 若 `len(read_out_contact) == 1`（单个重复电极），由路径起点 $(x_0, y_0)$ 求所在电极编号 $(i_x, i_y)$，仅计算满足 $i \in [\max(i_x - s_x, 0),\, \min(i_x + s_x, N_x - 1)]$、$j \in [\max(i_y - s_y, 0),\, \min(i_y + s_y, N_y - 1)]$ 的近邻电极，其中 $s_x = \text{my\_f.cells\_either\_side}$，$s_y = \text{read\_out\_contact}[0].\text{get}(\text{"y\_span"}, 0)$。电极序号为 $i \cdot N_y + j$，查询场中第 `0` 号权重势，平移偏移量为：
     $$\Delta x_{\text{off}} = x_{\text{first}} + (i - s_x)\,p_x, \qquad \Delta y_{\text{off}} = y_{\text{first}} + (j - s_y)\,p_y$$
     范围外的电极忽略为零。
   - 若器件有 `resistive_layer`，读出电极是阻性层的 RC 格点，权重势只有阻性层这一个平面电极的（见 [field.md](field.md) 的“权重势”），偏移量为 $(0, 0)$。每一步按第 2 步算出这个平面电极上的感应电荷 $\Delta Q_k$，再按这一步中点的横向位置 $\bigl(\tfrac{x_k + x_{k+1}}{2}, \tfrac{y_k + y_{k+1}}{2}\bigr)$ 分给 RC 格点：第 $n$ 个格点得 $s_n\,\Delta Q_k$，份额 $s_n$ 即 [readout.md](readout.md) 式 (5)–(7) 按到相邻格点中心的距离线性分配的份额，各格点之和为 $\Delta Q_k$。中点落在格点阵列之外时抛出 `ValueError`，写明坐标和阵列的范围。
2. **计算每步感应电荷（`induced_charges`）**：对每个待算电极，在路径各点查询 $\phi_{w,k} = \text{my\_f.get\_w\_p}(x_k - \Delta x_{\text{off}},\, y_k - \Delta y_{\text{off}},\, z_k,\, e_{\text{field}})$，计算第 $k$ 步感应电荷 $\Delta Q_k = N_k e_0 (\phi_{w,k+1} - \phi_{w,k})$（$\text{C}$），其中未开启俘获时 $N_k = N_0$，开启俘获时 $N_k = N_{k + 1/2}$。
3. **按时间占比分配到各箱（`spread_over_bins`）**：令箱宽 $\Delta t_{\text{bin}} = (t_{\text{end}} - t_{\text{start}}) / n_{\text{bin}}$（按第 2 步的取法即等于 $t_{\text{bin}}$），等效单箱电流 $v_k = \Delta Q_k / t_{\text{bin}}$。计算该步 $[t_k, t_{k+1}]$ 覆盖的逻辑箱号范围 $m_{\text{first}} = \lfloor (t_k - t_{\text{start}}) / \Delta t_{\text{bin}} \rfloor$ 至 $m_{\text{last}} = \lfloor (t_{k+1} - t_{\text{start}}) / \Delta t_{\text{bin}} \rfloor$。对每个 $m \in [m_{\text{first}}, m_{\text{last}}]$：
   - 重叠区间为 $[a_m, b_m] = \bigl[\max(t_k,\, t_{\text{start}} + m\,\Delta t_{\text{bin}}),\, \min(t_{k+1},\, t_{\text{start}} + (m + 1)\,\Delta t_{\text{bin}})\bigr]$；
   - 时间占比 $w_m = \max(b_m - a_m,\, 0) / (t_{k+1} - t_k)$；
   - 将 $v_k w_m$ 累加到 `bins[e, clamp(m + 1, 0, n_bin + 1)]`，从而 $m < 0$ 全部计入欠流箱 `0`，$m \ge n_{\text{bin}}$ 全部计入溢流箱 `n_bin + 1`。
4. **合成总电流与净电荷**：将原生空穴箱、原生电子箱（以及开启雪崩后的增益空穴箱与增益电子箱）逐元素相加得 `sum_bins`。时间窗内的电极电流取切片 `[:, 1:-1]`，而各电极净感应电荷 `charge = sum_bins.sum(axis=1) * t_bin`（$\text{C}$）包含欠流箱与溢流箱中的全部感应电荷。

### 雪崩倍增算法

当 `my_d.has_avalanche` 为真时，`CalCurrent` 构造 `CalCurrentGain`。`gain_algorithm(my_f)` 按场轴维数选择算法：一维场（`len(my_f.axes) == 1`）用 `"planar_integral"`，多维场用 `"local_path"`（此时强制 `keep_drift_paths = True`）。两种算法分别生成增益电子-空穴对起点与对数后，调用 `drift_all` 漂移并按 `binned` 分箱，合并到总电流、`ends` 与 `without_field` 中。

局限：`"local_path"` 只沿原生载流子的路径算一次增益，增益团簇只漂移、不再倍增。`"planar_integral"` 的式 (9) 已含电子、空穴的相互反馈，不受此限。

#### 一维平板积分（`planar_integral`）

1. **一次剖面积分（`DevsimField._integrate_planar_gain`，首次调用后缓存）**：
   - 检查 `"z"` 位于 `my_f.axes` 中，否则抛出 `ValueError`。沿器件中心线 $(x, y) = (0.5 l_x, 0.5 l_y)$ 取出电势网格的唯一深度节点 $z_0 < z_1 < \dots < z_M$（$\text{cm}$），查询各点电势 $U_m$（$\text{V}$）。
   - 在每个网格区间 $[z_m, z_{m+1}]$（宽度 $\Delta z_m = z_{m+1} - z_m$）内取分段常数电场 $E_m = -(U_{m+1} - U_m) / \Delta z_m$（$\text{V/cm}$），调用 `cal_coefficient(|E_m|, ±1, T)` 得 $\alpha_{n,m}$、$\alpha_{p,m}$（$\text{cm}^{-1}$）。
   - 取 $|E_m|$ 最大的区间 $m^*$，令增益层中心深度 $z_{\text{gain}} = 0.5(z_{m^*} + z_{m^*+1})\times 10^4$（$\mu\text{m}$）。由 $E_{m^*} > 0$ 判断电子是否向前表面 $z_0$ 漂移，由 $z_{m^*} + z_{m^*+1} \le z_0 + z_M$ 判断增益层是否位于前半侧，从而确定从体区向增益层漂移的载流子极性 `planar_gain_carrier`（电子 `-1`，空穴 `+1`）。
   - 令 $r_m = \alpha_{n,m} - \alpha_{p,m}$。从电子出射面出发累积各节点 $\ln K(z_m) = \sum r_m \Delta z_m$，并按分段常数精确积分求击穿积分：
     $$I_{\text{bd}} = \sum_{m=0}^{M-1} \alpha_{p,m}\,K_{\text{near},m} \cdot \begin{cases} \Delta z_m, & r_m = 0 \\ \dfrac{e^{r_m \Delta z_m} - 1}{r_m}, & r_m \ne 0 \end{cases}$$
     其中 $K_{\text{near},m}$ 为区间靠近电子出射面一端的 $K$ 值。若 $I_{\text{bd}} \ge 1$，抛出 `ValueError`。
   - 对任意产生深度 $z$（$\mu\text{m}$），`planar_gain_at(my_d, z)` 将 $z \times 10^{-4}$ 在网格节点上线性插值求 $\ln K$，返回净增益 $G(z) = \exp(\ln K) / (1 - I_{\text{bd}}) - 1$。`planar_gain(my_d)` 返回体区远端表面处的净增益。
2. **生成增益团簇（`_build_planar_gain_carriers`）**：
   - 取 `planar_gain_carrier` 对应的原生载流子系统作为 `source_system`。
   - 对 `source_system` 中每条点数 $\ge 2$ 的路径，计算各点相对增益层深度的偏移 $d_k = z_k - z_{\text{gain}}$：
     - 若存在 $d_k d_{k+1} \le 0$（穿过增益层），取首次穿越步 $k$，按线性插值比例 $\eta = d_k / (d_k - d_{k+1})$（$d_k = d_{k+1}$ 时取 $0$）用 `surviving_at` 求穿层时刻的存活载流子数 $N_{\text{arr}}$（无俘获时取 $N_0$）；
     - 若未穿越且 $|d_{\text{end}}| < |d_0|$（朝向增益层移动但未到达），不产生倍增，跳过；
     - 若未穿越且 $|d_{\text{end}}| \ge |d_0|$（产生于增益层前侧并背离增益层运动，另一极性载流子立即穿过增益层），取完整初始数 $N_{\text{arr}} = N_0$。
   - 在 $(x_{\text{end}}, y_{\text{end}}, z_{\text{gain}}, t_{\text{end}})$ 生成一对增益电子、空穴团簇，其中 $x_{\text{end}}, y_{\text{end}}, t_{\text{end}}$ 是原生团簇停止漂移时的横向位置和时刻（不是它穿过增益层的时刻），对数为 $|N_{\text{arr}}| \cdot G(z_0)$，其中 $z_0$ 为原生团簇起始深度。

#### 多维沿路径局部积分（`local_path`）

1. 读取配置参数：`min_pairs = max(gain_pair_threshold, 0.0)`（默认 `0.05`）、`max_carriers = gain_max_carriers`（默认 `50000`）、`emit_slices = max(1, local_gain_emit_slices)`（默认 `1`）、`samples = max(1, local_gain_integration_steps)`（默认 `3`）。
2. 遍历原生电子和空穴系统的每条点数 $\ge 2$ 的路径。初始化未计俘获的累积有效载流子数 $N_{\text{act}} = |N_0|$、待发射对数 $N_{\text{pend}} = 0$ 与待发射段列表 `pending = []`。对每一步 $k$，未俘获比例为 $u_k = 1$（无俘获）或 $u_k = N_{k + 1/2} / N_0$（有俘获）。
3. 对路径的每一步 $(\mathbf{r}_k, t_k) \to (\mathbf{r}_{k+1}, t_{k+1})$（跳过零空间位移步）：
   - 在步长上取 `samples` 个等分中点 $\mathbf{r}_{k,s} = \mathbf{r}_k + \frac{s + 0.5}{\text{samples}}(\mathbf{r}_{k+1} - \mathbf{r}_k)$（$s = 0, \dots, \text{samples}-1$），查询 $\mathbf{E}(\mathbf{r}_{k,s})$ 与模长 $E$（查询异常时累计告警计数并跳过该采样点；$E \le 0$ 跳过）。
   - 计算位移沿该载流子漂移方向的投影 $\Delta s_{\mu\text{m}} = \text{sign} \cdot (\Delta\mathbf{r} \cdot \mathbf{E}) / E$；仅当 $\Delta s_{\mu\text{m}} > 0$ 时，查 $\alpha = \max(\text{cal\_coefficient}(E, \text{sign}, T), 0)$（非有限值取 $0$），累加单步指数：
     $$\eta_{\text{step}} = \sum_{s} \alpha_s \cdot \frac{\Delta s_{\mu\text{m}}}{\text{samples}} \times 10^{-4}$$
   - 将 $\eta_{\text{step}}$ 截断于上限 `50.0`，计算未计俘获增长 $\Delta N_{\text{grow}} = N_{\text{act}}(\exp(\eta_{\text{step}}) - 1)$ 与计入俘获比例的新增对数 $\Delta N_{\text{new}} = \Delta N_{\text{grow}} \cdot u_k$。
   - 若 $\Delta N_{\text{new}} \le 0$：若当前已有 $N_{\text{pend}} > 0$，立即发射并清空 `pending`，然后进入下一步。
   - 否则更新 $N_{\text{act}} \leftarrow N_{\text{act}} + \Delta N_{\text{grow}}$、$N_{\text{pend}} \leftarrow N_{\text{pend}} + \Delta N_{\text{new}}$，将当前步段与 $\Delta N_{\text{new}}$ 记入 `pending`；一旦 $N_{\text{pend}} \ge \text{min\_pairs}$，立即发射并清空 `pending`。
4. 路径结束时若仍有 $N_{\text{pend}} > 0$，再发射一次。
5. **发射规则**：若 `pending` 仅含一个步段，发射区间为该步段本身；若跨多个步段，取各步段时空中心点 $(x, y, z, t)$ 按 $\Delta N_{\text{new}}$ 加权的质心作为单点发射区间。在发射区间上按 `emit_slices` 等分中点 $\frac{m + 0.5}{\text{emit\_slices}}$ 生成 `emit_slices` 个增益对起点，每份携带 $N_{\text{pend}} / \text{emit\_slices}$ 对。若 `max_carriers > 0` 且发射后总增益团簇数超过 `max_carriers`，抛出 `ValueError`。

### 激光时间脉冲卷积

`CalCurrentLaser` 将瞬时产生假设下算出的时域感应电流与激光时间脉冲形状 $P(t)$（$\text{s}^{-1}$，满足 $\int P(t)\,dt = 1$）卷积：

1. 调用父类 `CalCurrent` 对激光注入 `my_l` 生成的初始电子-空穴对完成漂移、倍增与分箱（`CalCurrentLaser` 默认 `diffusion=True`，而 `write_laser_currents` 显式传入 `diffusion=False`）。
2. 调用 `pulse_in_bins(my_l.timePulse, my_l.temporal_FWHM, n_bin, bin_width)` 计算脉冲在各整数箱偏移 $k \in [-(n_{\text{bin}} - 1),\, n_{\text{bin}} - 1]$ 处的离散权重：
   - 确定单箱中点采样数 $S = \max\!\left(1,\, \lceil 20\,\Delta t_{\text{bin}} / \text{FWHM} \rceil\right)$（采样间距不大于 $\text{FWHM}/20$）；
   - 按中点矩形法则积分得：
     $$p_k = \frac{\Delta t_{\text{bin}}}{S} \sum_{s=0}^{S-1} P\!\left(\left(k + \frac{s + 0.5}{S} - 0.5\right)\Delta t_{\text{bin}}\right)$$
3. 构造 $n_{\text{bin}} \times n_{\text{bin}}$ 矩阵 $M_{a,b} = p_{a - b}$，对时间窗内的 `hole_current`、`electron_current`、`current`（开启雪崩时含 `gain_current.hole_bins[:, 1:-1]` 与 `gain_current.electron_bins[:, 1:-1]`）依次执行矩阵右乘：
   $$I^{\text{conv}}_{e, b} = \sum_{a=0}^{n_{\text{bin}}-1} I_{e, a}\,p_{a - b}$$
4. 用卷积后的波形两端补零（欠流/溢流箱置零）重新填充对应的 ROOT 直方图。

### 纯扩散收集

`collect_by_diffusion(my_d, pairs, positions, window, step)`（`diffusion.py`）模拟低偏压无场像素传感器中电子的纯扩散收集：

1. **校验与几何预计算**：要求 `my_d.is_pixel` 为真且器件定义了 `e_width_x`、`e_width_y`（$\mu\text{m}$）。计算像素内收集区边缘留白 `low_x = (p_x - e_width_x)/2`、`low_y = (p_y - e_width_y)/2`，以及居中像素阵列起点 `first_x = (l_x - x_ele_num * p_x)/2`、`first_y = (l_y - y_ele_num * p_y)/2`。
2. **零场迁移率与步长标准差**：取有效掺杂 $N_{\text{eff}} = \text{Donors} - \text{Acceptors}$（$\text{cm}^{-3}$），调用 `Material(material).cal_mobility(T, N_eff, -1, 0)` 求零场电子迁移率 $\mu_n(0)$，按式 (3) 计算单步时间 `step`（$\text{s}$）的高斯位移标准差 $\sigma$（$\mu\text{m}$）。
3. **时间箱划分**：令步数上限 $K = \text{round}(\text{window} / \text{step})$，首箱左边界 $t_0 = \min_m t_m$，最晚产生时刻 $t_{\max} = \max_m t_m$（无沉积时取 $0.0$）。辅助函数 `time_bin(t, t0, step)` 计算 $q = (t - t_0)/\text{step}$ 的下取整 $k = \lfloor q \rfloor$，当 $q - k > 1 - 10^{-9}$ 时进位加 $1$ 以消除浮点整步边界误差。总箱数 $n_{\text{bin}} = \text{time\_bin}(t_{\max}, t_0, \text{step}) + K + 1$。
4. **二维随机游走**：从独立随机流 `stream("diffusion")` 抽取随机数，遍历每个满足 $0 \le z \le l_z$ 的沉积团簇 $(x, y, z, t, n_{\text{pairs}})$，记初始箱号 $k_0 = \text{time\_bin}(t, t_0, \text{step})$，循环 $k = 0, 1, \dots, K$：
   - 若不满足 $0 < x < l_x$ 且 $0 < y < l_y$，判定从器件侧面逸出并终止；
   - 计算像素索引 $i = \lfloor (x - \text{first\_x}) / p_x \rfloor$、$j = \lfloor (y - \text{first\_y}) / p_y \rfloor$，检查是否严格落入像素中心矩形收集区（$\text{low\_x} < x - \text{first\_x} - i p_x < p_x - \text{low\_x}$，$y$ 向同理，且 $0 \le i < N_x$、$0 \le j < N_y$）；若命中，立即将 $n_{\text{pairs}}$ 累加至像素 $i N_y + j$ 的第 $k_0 + k$ 箱并终止；
   - 否则执行 $x \leftarrow x + \mathcal{N}(0, \sigma^2)$、$y \leftarrow y + \mathcal{N}(0, \sigma^2)$。
5. **返回电流与净电荷**：各像素净电荷 `charge = -e * electrons.sum(axis=1)`（$\text{C}$），各箱平均电流 `current = -e * electrons / step`（$\text{A}$），电子取负号。

局限：该模型不含结区电场与漂移、不含 $z$ 向运动、不含载流子复合与空穴贡献，也不计算电子到达收集区之前的感应电流，仅以每时间箱到达的电荷给出电流。

## 软件实现

### 模块与函数分工

- `drift.py`：实现单团簇输运与单步物理量计算。`advance` 执行单步推进与停止判定，`drift` 循环推进单团簇至停止；`induced_charges` 计算路径各步在指定电极上的 Shockley-Ramo 感应电荷；`surviving` 与 `surviving_at` 计算俘获后的存活载流子数。
- `cal_current.py`：实现事例级输运调度、分箱、雪崩倍增、激光卷积与批处理写出。`CalCurrent` 完成时间窗设定、空间筛选、载流子漂移与分箱；`CalCurrentGain` 继承 `CalCurrent`，按 `gain_algorithm` 执行 `"planar_integral"` 或 `"local_path"` 倍增；`CalCurrentLaser` 结合 `pulse_in_bins` 执行激光脉冲卷积；`spread_over_bins`、`fill_histogram`、`electrode_names`、`split_at_conductor_edges`、`deposits_in` 与 `log_ends` 为支撑函数；`write_induced_currents` 与 `write_laser_currents` 负责将事例结果写出到 HDF5 文件并触发绘图。
- `diffusion.py`：提供 `time_bin` 与 `collect_by_diffusion`，实现无场像素传感器的二维纯扩散收集。
- `currents.py`：定义 `EventCurrents`、`Currents` 以及 `append_currents`、`read_currents`，负责 `current.h5` 的稀疏追加写入与全电极还原读取。
- `draw.py` 与 `draw_drift_path.py`：使用 PyROOT 并经[出图（`supports/figures`）](../supports/figures.md)取样式、存图，绘制感应电流波形（`draw_currents`）、条形/像素收集电荷（`charge_collection_strip`、`charge_collection_pixel`）与三维/$x$-$z$ 漂移路径（`draw_drift_path`）。

### 核心数据结构

- `Cluster`（`drift.py`）：表示漂移中的单个载流子团簇，包含带符号载流子数 `carriers`、当前坐标 `position`（$\mu\text{m}$）、当前时刻 `t`（$\text{s}$）、出发时刻 `start`（$\text{s}$）、轨迹点列表 `path` 与停止原因 `reason`（漂移中为 `None`），由 `Cluster.starting(x, y, z, t, carriers)` 构造。
- `Drifted`（`drift.py`）：保存同号载流子全部团簇漂移后的结果，包含四个等长列表：`carriers`（初始带符号载流子数）、`paths`（各团簇形状为 `(points, 4)` 的 `(x, y, z, t)` 数组）、`reasons`（停止原因）与 `remaining`（各步中点带符号存活数数组，未开启俘获时为 `None`）；当 `keep_drift_paths=False` 时，计算结束后会清空 `paths` 与 `remaining` 以释放内存。
- `EventCurrents`（`currents.py`）：单事例电流输出记录，包含事例号 `event`、首箱左边界 `t0`（$\text{s}$）、时域电流矩阵 `current`（形状 `(electrodes, bins)`，$\text{A}$）、各电极净电荷 `charge`（形状 `(electrodes,)`，$\text{C}$）、初始对数 `pairs`，以及求解场漂移时附带的可选字段 `sensitive_pairs` 与 `carriers_without_field`。`read_currents` 返回封装整文件的 `Currents(electrodes, dt, events)`。

## 接口

命令与 `current` 段的设置见 [../stages/current.md](../stages/current.md)。构建 `DevsimField` 所用的偏压、辐照注量与 3D 插值配置见 [field.md](field.md)。

### 器件文件读取的键

使用者能设的只有下表这些键；迁移率模型由器件文件按名字选用（见 [model.md](model.md)）。页内其他参数（时间窗、步长、扩散开关）都写死在代码里。

| 键或派生属性 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `default_dimension`, `field_dimension` | 见 [device.md](device.md) | 无 | 映射为 `dimension`，与 `field` 段选用的网格（二维网格是否在横向 $x$-$y$ 平面）一起决定时间窗与步长档位 |
| `l_x`, `l_y`, `l_z` | 无（必选） | $\mu\text{m}$ | 器件边界 $[0, l_x] \times [0, l_y] \times [0, l_z]$ |
| `electrodes`, `p_x`, `p_y`, `x_ele_num`, `y_ele_num`, `read_ele_num` | 见 [device.md](device.md) | $\mu\text{m}$ / 个 | 居中读出电极布局、间距与数量；`electrodes` 为 `"strip"`/`"pixel"` 时同时决定绘图类型，`"pixel"` 为 `collect_by_diffusion` 前提 |
| `read_out_contact` | 无（必选） | 无 | 读出电极字典列表，每项含 `"name"`；单电极重复排布时可选 `"y_span"`（默认 `0`，控制 `y` 向近邻跨度；`x` 向跨度取场对象 `cells_either_side`） |
| `det_name`, `det_model` | `det_name` 默认文件名词干；`det_model` 无（绘图必选） | 无 | 器件名称（用于报错信息）与模型标识（用于 `<det_model>_drift_path` 文件名） |
| `material`, `temperature` | 无（必选） | 无, $\text{K}$ | 材料名称（传入 [model.md](model.md) 的 `Material`）与器件温度 $T$ |
| `irradiation.irradiation_model` | 无 `irradiation` 块时为 `None` | 无 | 映射为 `irradiation_model`；非 `None` 时开启载流子俘获衰减 |
| `enable_gain`, `avalanche_model` | `False`, `None` | 无 | 同时有效时 `has_avalanche` 为真并启用 `CalCurrentGain`；支持 `"vanOverstraeten"`、`"Okuto"`、`"Hatakeyama"` |
| `gain_pair_threshold` | `0.05` | 对 | `"local_path"` 模式下触发发射新增益团簇的最小累积对数（负值截断为 `0.0`） |
| `gain_max_carriers` | `50000` | 团簇 | `"local_path"` 模式下单事例允许生成的最大增益团簇数；$\le 0$ 时不设上限 |
| `local_gain_emit_slices` | `1` | 团簇 | `"local_path"` 模式下每次发射沿步段等分生成的子团簇数（至少 `1`） |
| `local_gain_integration_steps` | `3` | 步 | `"local_path"` 模式下单漂移步内积分电离系数的采样点数（至少 `1`） |
| `e_width_x`, `e_width_y` | 无（`collect_by_diffusion` 必选） | $\mu\text{m}$ | 纯扩散收集模式下每个像素中心矩形收集区尺寸 |
| `doping.Donors`, `doping.Acceptors` | 无（`collect_by_diffusion` 必选） | $\text{cm}^{-3}$ | 纯扩散收集模式下用于求零场电子迁移率的施主、受主浓度数值 |

### `current.h5` 文件格式

文件由 `append_currents` 逐事例追加写入，仅存储电流非全零的电极；`read_currents` 读出时将未存储电极还原为全零数组。

**文件属性（Attributes）**

| 属性名 | 类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `electrodes` | 字符串数组 | 无 | 读出电极名称列表，顺序与 `charge` 列顺序一致 |
| `dt` | `float64` | $\text{s}$ | 时间箱宽度（等于 `t_bin`） |

**数据集（Datasets）**

| 数据集名 | 形状与类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `event` | `(events,)`, `int64` | 无 | 事例编号（`write_laser_currents` 写入时为 `0`） |
| `t0` | `(events,)`, `float64` | $\text{s}$ | 该事例首个时间箱左边界时刻（等于 `t_start`） |
| `count` | `(events,)`, `int64` | 箱 | 该事例的时间箱数（等于 `n_bin`） |
| `pairs` | `(events,)`, `float64` | 对 | 该事例输入的电子-空穴对总数（雪崩倍增前） |
| `sensitive_pairs` | `(events,)`, `float64`（可选） | 对 | 器件内且电极阵列上方、产生于非导电区的电子-空穴对数（求解场漂移写出时存在） |
| `carriers_without_field` | `(events,)`, `float64`（可选） | 个 | 因 `"no_field"` 停止的团簇（含增益团簇）在停止时尚未被俘获的载流子总数（求解场漂移写出时存在） |
| `charge` | `(events, len(electrodes))`, `float64`（gzip） | $\text{C}$ | 各读出电极的带符号净感应电荷（含时间窗前后的欠流箱与溢流箱） |
| `stored` | `(events,)`, `int64` | 个 | 该事例中电流非全零而被存入 `current` 的电极数 |
| `index` | `(sum(stored),)`, `int64` | 无 | 每个被存储电极在 `electrodes` 中的下标（从 `0` 起），按 `stored` 切分到各事例 |
| `current` | `(sum(stored * count),)`, `float64`（gzip） | $\text{A}$ | 各被存储电极在 `count` 个时间箱内的平均感应电流，按事例与存储电极顺序首尾拼接 |

### 绘图输出

`write_induced_currents(deposits_path, currents_path, my_d, my_f, plots=0, plot_path=None, detector=None)` 读 `deposits_path` 的沉积文件，把电流写进 `currents_path`；缺省 `plots=0` 时不画图，`plot_path` 不用给。`plots > 0` 时先删掉 `<plot_path>` 里以 `current_`、`drift_path_`、`charge_per_electrode_` 开头的旧图，再为前 `plots` 个事例在 `<plot_path>` 下生成漂移路径图、电流波形图及（条形/像素布局下的）收集电荷图，图名后接事例号 `<event>`，环节传入的 `plots` 是 `current.plots`，`plot_path` 在 `current` 自己的节点里；`write_laser_currents` 在提供 `plot_path` 时仅生成电流波形图，事例号为 `0`。

| 文件名 | 内容 | 单位 |
| --- | --- | --- |
| `drift_path_<event>.png`, `.pdf`, `.root` | 上半图为三维器件边界框与沉积点（灰）、空穴（红）、电子（蓝）、增益空穴（橙）、增益电子（浅蓝）路径；下半图为 $x$-$z$ 平面投影 | 空间轴 $\mu\text{m}$ |
| `current_<event>.png`, `.pdf`, `.root`（多个读出电极时为 `current_<event>_electrode_<k>`） | 仅对存在非零电流分量的第 $k$ 号电极（从 `1` 起）绘制 `electrons`、`holes`、`total`（开启雪崩时含 `gain electrons`、`gain holes`）波形 | `Time [ns]`, `Current [μA]` |
| `charge_per_electrode_<event>.png`, `.pdf`, `.root` | `is_strip` 为真时绘各条收集电荷折线图（`TGraph`）；`is_pixel` 为真时绘二维像素分布（`TH2D`）；数值为各电极的净电荷，纵轴（二维像素图为色轴）标题为 `Charge [fC]` | $\text{fC}$ |

## 参考文献

- [1] S. M. Sze, K. K. Ng, *Physics of Semiconductor Devices*, 3rd ed., Wiley-Interscience (2007), doi:10.1002/0470068329
- [2] A. Einstein, “Über die von der molekularkinetischen Theorie der Wärme geforderte Bewegung von in ruhenden Flüssigkeiten suspendierten Teilchen”, Ann. Phys. 322 (1905) 549, doi:10.1002/andp.19053220806
- [3] W. Shockley, W. T. Read, Jr., “Statistics of the Recombinations of Holes and Electrons”, Phys. Rev. 87 (1952) 835, doi:10.1103/PhysRev.87.835
- [4] G. Kramberger, V. Cindro, I. Mandić, M. Mikuž, M. Zavrtanik, “Effective trapping time of electrons and holes in different silicon materials irradiated with neutrons, protons and pions”, Nucl. Instrum. Methods Phys. Res. A 481 (2002) 297, doi:10.1016/S0168-9002(01)01263-3
- [5] W. Shockley, “Currents to Conductors Induced by a Moving Point Charge”, J. Appl. Phys. 9 (1938) 635, doi:10.1063/1.1710367
- [6] S. Ramo, “Currents Induced by Electron Motion”, Proc. IRE 27 (1939) 584, doi:10.1109/JRPROC.1939.228757
- [7] R. J. McIntyre, “Multiplication Noise in Uniform Avalanche Diodes”, IEEE Trans. Electron Devices 13 (1966) 164, doi:10.1109/T-ED.1966.15651
- [8] R. van Overstraeten, H. de Man, “Measurement of the ionization rates in diffused silicon p-n junctions”, Solid-State Electronics 13 (1970) 583, doi:10.1016/0038-1101(70)90139-5
- [9] Y. Okuto, C. R. Crowell, “Threshold energy effect on avalanche breakdown voltage in semiconductor junctions”, Solid-State Electronics 18 (1975) 161, doi:10.1016/0038-1101(75)90099-4
- [10] T. Hatakeyama, T. Watanabe, T. Shinohe, K. Kojima, K. Arai, N. Sano, “Impact ionization coefficients of 4H silicon carbide”, Appl. Phys. Lett. 85 (2004) 1380, doi:10.1063/1.1784520
- [11] T. Hatakeyama, J. Nishio, C. Ota, T. Shinohe, “Physical modeling and scaling properties of 4H-SiC power devices”, Proc. Int. Conf. Simulation of Semiconductor Processes and Devices (SISPAD) (2005) 171, doi:10.1109/SISPAD.2005.201500
- [12] C. R. Crowell, S. M. Sze, “Temperature dependence of avalanche multiplication in semiconductors”, Appl. Phys. Lett. 9 (1966) 242, doi:10.1063/1.1754731
- [13] Synopsys, *Sentaurus Device User Guide*, Synopsys Inc., 碰撞电离的 van Overstraeten–de Man 模型一节
- [14] T. Hatakeyama, “Measurements of impact ionization coefficients of silicon carbide for high voltage power devices”, Phys. Status Solidi A 206 (2009) 2284, doi:10.1002/pssa.200925213
