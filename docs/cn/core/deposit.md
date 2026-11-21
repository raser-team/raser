# 能量沉积与电离（`core/deposit`）

`src/raser/core/deposit/` 从 [器件模型](device.md) 取器件的尺寸与材料，从 [能量沉积组件](../components/deposit.md) 取装置脚本、放射源或束流、激光的定义。它用 Geant4 或直线 toy MIP 模型算出粒子在器件里的沉积步，把每步沉积能量换成电子-空穴对，写成 `deposit_<job>.h5`；激光则按吸收系数直接给出载流子群。沉积文件交给 [载流子漂移与感应电流](current.md) 做漂移，事例最早沉积时刻交给 [统计分析](analysis.md) 作 `truth`，[望远镜](../bench/telescope.md) 也读这个文件；激光载流子群由 [TCT](../bench/tct.md) 交给电流计算。命令行入口见 [能量沉积环节](../stages/deposit.md)。

## 物理

### 电离能与电子-空穴对数

带电粒子在半导体里损失的能量，平均每 $\varepsilon$ 产生一对电子-空穴。对数的涨落小于泊松涨落，方差是均值的 $F$ 倍（Fano 因子）。每个沉积步的平均对数与抽样对数为：

$$\bar{N} = \frac{E}{\varepsilon \times 10^{-6}} \tag{1}$$

$$N = \max\bigl(0,\ X\bigr), \qquad X \sim \mathcal{N}\bigl(\bar{N},\ F\bar{N}\bigr) \tag{2}$$

其中：

- $E$：该步沉积能量，$\text{MeV}$；
- $\varepsilon$：材料的平均电离能，$\text{eV}$（`PAIR_ENERGY_EV`，$10^{-6}$ 把它换成 $\text{MeV}$）；
- $\bar{N}$：平均电子-空穴对数，对；
- $F$：Fano 因子，无量纲（`FANO_FACTOR`）；
- $\mathcal{N}(\mu, \sigma^2)$：均值 $\mu$、方差 $\sigma^2$ 的高斯分布；
- $N$：写入文件的对数，对。

两式由 `ionized_pairs(event, material, fano)` 实现。`fano=True`（缺省）时按式 (2) 抽样，否则取 $N = \bar{N}$，此时材料不需要 Fano 因子。各材料的取值：

| 材料 | `PAIR_ENERGY_EV`（$\text{eV}$） | `FANO_FACTOR` | 出处 |
| --- | --- | --- | --- |
| `"Si"` | `3.6` | `0.115` | 出处待补 |
| `"SiC"` | `8.4` | `0.128` | 出处待补 |
| `"Diamond"` | `13.1` | `0.382` | CVD 金刚石对 Am-241 的 $5.486\ \text{MeV}$ α 粒子的测量值，Fano 因子为 $0.382 \pm 0.007$ [2] |

Fano 涨落见文献 [1]。

### Geant4 的能损

`beam` 与 `decay_source` 两类源由 Geant4 [3, 4] 输运。物理表是 `FTFP_BERT` 加 `G4StepLimiterPhysics`；源含 `nuclides` 时再加 `G4RadioactiveDecayPhysics` [5]，并把放射性衰变的时间阈值设为 $10^{60}$ 年，使任何寿命的核素都衰变。产生阈沿用物理表的缺省值。器件逻辑体 `"Device"` 带 `G4UserLimits`，步长上限是装置的 `maxstep`。Geant4 在体积边界和物理过程处也会截断步。每个前点在 `"Device"` 内的步记为一个沉积步：

$$E_k = \texttt{GetTotalEnergyDeposit}, \qquad \mathbf{r}_k = \tfrac{1}{2}\bigl(\mathbf{r}_k^{\text{pre}} + \mathbf{r}_k^{\text{post}}\bigr), \qquad \ell_k \le s_{\max} \tag{3}$$

其中：

- $E_k$：第 $k$ 步在器件内的总沉积能量，$\text{MeV}$；
- $\mathbf{r}_k^{\text{pre}}, \mathbf{r}_k^{\text{post}}$：该步前点与后点，$\mu\text{m}$；
- $\mathbf{r}_k$：沉积步位置，取步中点，$\mu\text{m}$（代码注释说明：步的两端在器件表面上，舍入误差可能把端点落到器件外）；
- $\ell_k$：步长，$\mu\text{m}$；$s_{\max}$：装置的 `maxstep`，$\mu\text{m}$。

器件材料在 Geant4 里按 `material` 建：`"Si"` 用 NIST 的 `G4_Si`；`"Diamond"` 用密度改为 $3.52\ \text{g/cm}^3$ 的 `G4_C`（代码注释：NIST 的 `G4_C` 是 $2.0\ \text{g/cm}^3$ 的石墨）；`"SiC"` 是 Si、C 原子数各占一半、密度 $3.2\ \text{g/cm}^3$ 的化合物。两个密度的出处待补。

### toy MIP 径迹

toy MIP 是一条穿过器件的直线径迹，单位长度的能损固定，分段后每段可以按 Landau 分布涨落 [6]。单位长度平均能损与每段能量为：

$$\frac{dE}{dx} = n_{\text{MIP}}\,\varepsilon \times 10^{-6} \tag{4}$$

$$E_k = \begin{cases} \max\bigl(0,\ Y\bigr),\quad Y \sim \text{Landau}\Bigl(\dfrac{dE}{dx}\,\Delta l,\ w\,\Delta l\Bigr), & \texttt{landau\_sampling} = \texttt{true} \\[2ex] \dfrac{dE}{dx}\,\Delta l, & \texttt{landau\_sampling} = \texttt{false} \end{cases} \tag{5}$$

$$p(Y) = \frac{1}{\pi \sigma}\int_0^\infty e^{-t \ln t - \lambda t}\sin(\pi t)\,dt, \qquad \lambda = \frac{Y - \mu}{\sigma} \tag{6}$$

其中：

- $n_{\text{MIP}}$：每 $\mu\text{m}$ 径迹的平均对数，$\mu\text{m}^{-1}$（`PAIRS_PER_UM`）；
- $\varepsilon$：式 (1) 的平均电离能，$\text{eV}$；
- $dE/dx$：单位长度平均能损，$\text{MeV}/\mu\text{m}$；
- $\Delta l = L / n$：每段长度，$\mu\text{m}$，$L$ 为径迹长度，$n$ 为段数；
- $w$：Landau 宽度，$\text{MeV}/\mu\text{m}$（`LANDAU_WIDTH_MEV_PER_UM`）；
- $\mu = (dE/dx)\,\Delta l$、$\sigma = w\,\Delta l$：ROOT `TRandom::Landau` 的位置参数与尺度参数，$\text{MeV}$；
- $E_k$：第 $k$ 段沉积能量，$\text{MeV}$。

由 `mip_deposits` 实现。随后每段的对数仍按式 (1)、(2) 由 `ionized_pairs` 给出，所以 `landau_sampling` 为 `false`、`fano` 为 `false` 时每 $\mu\text{m}$ 恰好 $n_{\text{MIP}}$ 对。只支持两种材料：

| 材料 | `PAIRS_PER_UM`（$\mu\text{m}^{-1}$） | $dE/dx$（$\text{MeV}/\mu\text{m}$） | `LANDAU_WIDTH_MEV_PER_UM`（$\text{MeV}/\mu\text{m}$） |
| --- | --- | --- | --- |
| `"Si"` | `80.0` | `2.88e-4` | `2.0e-5` |
| `"SiC"` | `55.0` | `4.62e-4` | `3.2e-5` |

`PAIRS_PER_UM` 与 `LANDAU_WIDTH_MEV_PER_UM` 的出处待补。

### 激光的单光子与双光子吸收

激光脉冲在器件里按吸收产生载流子。单光子吸收（SPA）每吸收一个光子产生一对，强度沿光路按 $e^{-\alpha s}$ 衰减。双光子吸收（TPA）的产生率正比于光强平方，集中在焦点附近。光束是高斯光束，横向半径随离焦距离展宽。

吸收系数 $\alpha$ 在激光文件未给 `alpha` 时由 `absorption_coefficient` 查表：

$$\alpha(\lambda) = 100\,\exp\Bigl[\operatorname{interp}\bigl(10^{3}\lambda;\ \lambda_i,\ \ln \alpha_i\bigr)\Bigr] \tag{7}$$

光子能量、光子数与高斯光束半径为：

$$h\nu = \frac{h c}{\lambda \times 10^{-6}}, \qquad N_\gamma = \frac{E_p}{h\nu} \tag{8}$$

$$w_0 = \frac{\text{FWHM}_s}{\sqrt{2\ln 2}}, \qquad z_R = \frac{\pi w_0^2 n}{\lambda}, \qquad w^2(s) = w_0^2\left[1 + \left(\frac{s - s_f}{z_R}\right)^2\right] \tag{9}$$

沿光路单位长度的产生对数（已对横截面积分）为：

$$\left.\frac{dN}{ds}\right|_{\text{SPA}} = \alpha\, N_\gamma\, e^{-\alpha s \times 10^{-6}} \tag{10}$$

$$\left.\frac{dN}{ds}\right|_{\text{TPA}} = \frac{\beta_2\, E_p^2\, e^{-2\alpha s \times 10^{-6}}}{2\,h\nu\,\pi\, w^2(s) \times 10^{-12}} \cdot \frac{\sqrt{2\ln 2}}{\sqrt{\pi}\,\tau} \tag{11}$$

横向分布与产生时刻的分布为：

$$\frac{dN}{dA} \propto \exp\!\left(-\frac{k\, r^2}{w^2(s)}\right), \qquad k = \begin{cases} 2, & \text{SPA} \\ 4, & \text{TPA} \end{cases} \tag{12}$$

$$P(t) = \frac{2\sqrt{2\ln 2}}{\sqrt{2\pi}\,\tau}\exp\!\left(-\frac{4\ln 2\; t^2}{\tau^2}\right) \tag{13}$$

其中：

- $\lambda$：波长，$\mu\text{m}$（激光文件的 `wavelength` 以 $\text{nm}$ 给出，乘 $10^{-3}$）；
- $\lambda_i, \alpha_i$：吸收系数表的波长（$\text{nm}$）与吸收系数（$\text{cm}^{-1}$），`interp` 为相邻行间的线性插值，$100$ 把 $\text{cm}^{-1}$ 换成 $\text{m}^{-1}$；
- $\alpha$：吸收系数，$\text{m}^{-1}$；
- $h = 6.626\times10^{-34}\ \text{J}\cdot\text{s}$，$c = 2.998\times10^{8}\ \text{m/s}$；$h\nu$：光子能量，$\text{J}$；
- $E_p$：脉冲能量 `pulse_energy`，$\text{J}$；$N_\gamma$：脉冲光子数；
- $\text{FWHM}_s$：焦点处光斑的空间半高全宽 `spacial_FWHM`，$\mu\text{m}$；$w_0$：束腰半径，$\mu\text{m}$；
- $n$：折射率 `refractionIndex`；$z_R$：瑞利长度，$\mu\text{m}$（激光文件给了 `l_Rayleigh` 时用给定值）；
- $s$：从入射面沿光路的距离，$\mu\text{m}$；$s_f$：焦点在光路上的位置，$\mu\text{m}$；$w(s)$：$s$ 处光束半径，$\mu\text{m}$；
- $\beta_2$：双光子吸收系数 `beta_2`，$\text{m/W}$；
- $\tau$：脉冲时间半高全宽 `temporal_FWHM`，$\text{s}$；
- $dN/ds$：每米光路产生的对数，$\text{m}^{-1}$（$10^{-6}$、$10^{-12}$ 把 $\mu\text{m}$、$\mu\text{m}^2$ 换成 $\text{m}$、$\text{m}^2$）；
- $r$：到光轴的距离，$\mu\text{m}$；
- $P(t)$：离脉冲中心 $t$（$\text{s}$）处的归一化时间分布，$\text{s}^{-1}$（`timePulse`）。

式 (11) 中第二个因子是高斯脉冲时间分布平方的积分。光强沿光路只按 $\alpha$ 衰减。$\alpha \ne 0$ 时按式 (10) 加 SPA 载流子群，`tech` 为 `"TPA"` 时再按式 (11) 加 TPA 载流子群；双光子激光的 $\alpha$ 是缺陷对带隙以下光子的吸收（代码注释）。每个群的产生时刻以 `central_time` 为中心展宽：SPA 群的半高全宽为 $\tau$，TPA 群为 $\tau/\sqrt{2}$，因为 $P^2(t)$ 是宽度缩小 $\sqrt{2}$ 的高斯。由 `LaserInjection` 实现。吸收系数表 `Si.txt` 取自文献 [7]；式 (9)–(13) 的出处待补。

### 放射源

放射源每个事例是一个静止核素的一次衰变。核素在 `nuclides` 中等概率抽取，位置在垂直于发射轴的圆盘上均匀分布。衰变产物的起始时刻置零，衰变留下的子核在此截断，一个事例是一次衰变。给了 `par_cone` 时，衰变产物的方向在绕发射轴的圆锥内各向同性重抽：

$$\hat{\mathbf{a}} = \frac{\mathbf{r}_{\text{out}} - \mathbf{r}_{\text{in}}}{|\mathbf{r}_{\text{out}} - \mathbf{r}_{\text{in}}|}, \qquad |\mathbf{r}_0 - \mathbf{r}_{\text{in}}| \le R, \quad (\mathbf{r}_0 - \mathbf{r}_{\text{in}}) \perp \hat{\mathbf{a}} \tag{14}$$

$$\cos\theta = 1 - u_1\,(1 - \cos\theta_c), \qquad \varphi = 2\pi u_2, \qquad \hat{\mathbf{d}} = \cos\theta\,\hat{\mathbf{a}} + \sin\theta\,(\cos\varphi\,\hat{\mathbf{e}}_1 + \sin\varphi\,\hat{\mathbf{e}}_2) \tag{15}$$

$$f = \frac{1 - \cos\theta_c}{2} \tag{16}$$

其中：

- $\mathbf{r}_{\text{in}}, \mathbf{r}_{\text{out}}$：源位置与瞄准点（装置的 `source.at`、`source.towards`），$\mu\text{m}$；$\hat{\mathbf{a}}$：发射轴单位矢量；
- $\mathbf{r}_0$：核素位置，$\mu\text{m}$；$R$：圆盘半径 `par_radius`，$\mu\text{m}$（$R = 0$ 时为点源）；
- $\hat{\mathbf{e}}_1, \hat{\mathbf{e}}_2$：与 $\hat{\mathbf{a}}$ 正交的单位矢量；
- $\theta_c$：半锥角 `par_cone`，度；$u_1, u_2$：$[0, 1)$ 上的均匀随机数；
- $\hat{\mathbf{d}}$：衰变产物的出射方向；
- $f$：圆锥占全部方向的比例，写作文件属性 `generated_fraction`。

核素由 `NuclideGeneratorAction`（`G4GeneralParticleSource`，动能 $0$）产生，时间置零、子核截断和圆锥方向由 `DecayStackingAction` 完成，判据是轨迹的产生过程子类型为 `RADIOACTIVE_DECAY = 210`。代码注释说明：Geant4 自带的 `/process/had/rdm/decayHalfAngle` 只能绕 $z$ 轴，所以自己实现。Geant4 放射性衰变见文献 [5]。

## 算法

### 内置常数

| 常数 | 取值 | 单位 | 位置与含义 | 文件里的键 |
| --- | --- | --- | --- | --- |
| `PAIR_ENERGY_EV` | Si `3.6`，SiC `8.4`，Diamond `13.1` | $\text{eV}$ | `ionization.py`，式 (1) 的 $\varepsilon$ | 无 |
| `FANO_FACTOR` | Si `0.115`，SiC `0.128`，Diamond `0.382` | 无 | `ionization.py`，式 (2) 的 $F$ | 无（开关 `fano` 是环节选项） |
| `PAIRS_PER_UM` | Si `80.0`，SiC `55.0` | $\mu\text{m}^{-1}$ | `mip_track.py`，式 (4) 的 $n_{\text{MIP}}$ | 无 |
| `LANDAU_WIDTH_MEV_PER_UM` | Si `2.0e-5`，SiC `3.2e-5` | $\text{MeV}/\mu\text{m}$ | `mip_track.py`，式 (5) 的 $w$ | 无 |
| `GENERATED_LIMIT` | `10_000_000` | 事例 | `generation.py`，按记录数运行时最多生成的事例数 | 无（环节选项 `--generated-limit`） |
| `DEVICE_ALONE` | 见下文“装置” | — | `simulate_deposits.py`，未给装置时的装置 | 由 `g4setup` 整体替换 |
| `WORLD_HALF_SIDE` | `25000` | $\mu\text{m}$ | `simulate_deposits.py`，世界立方体的缺省半边长 | `gdml_import` 下的 `world_half_size_um` |
| 物理表 | `FTFP_BERT` + `G4StepLimiterPhysics` | — | `geant4/interaction.py` | 无 |
| 放射性衰变时间阈值 | `1.0e60` | 年 | `geant4/interaction.py` | 无 |
| 随机引擎 | `CLHEP::RanecuEngine`，种子为作业的 `seed` | — | `geant4/interaction.py` | 无 |
| 器件密度 | Diamond `3.52`，SiC `3.2`（Si:C 原子数 `50:50`） | $\text{g/cm}^3$ | `geant4/detector_construction.py` | 无 |
| `RADIOACTIVE_DECAY` | `210` | — | `geant4/nuclide_source.py`，放射性衰变的过程子类型 | 无 |
| $h$, $c$ | `6.626e-34`, `2.998e8` | $\text{J}\cdot\text{s}$, $\text{m/s}$ | `laser.py`，式 (8) | 无 |
| 环数、扇区数 | `4`, `8` | 个 | `laser.py`，激光横截面的划分 | 无 |
| 光路采样密度 | 每个最细尺度 `50` 点 | — | `laser.py`，见“激光载流子群” | 无 |

### `simulate_deposits` 的分支

`simulate_deposits(my_d, source, g4setup, events, g4_seed, edep_min, edep_max, fano, generated, generated_limit, picture, drawn)` 按以下顺序执行：

1. **检查源的类型**：`source["kind"]` 不是 `"toy_mip"`、`"beam"`、`"decay_source"` 之一时抛 `ValueError`（`no simulation of deposits for a source of kind ...`）。
2. **检查事例数**：`asked(events, generated, generated_limit)` 要求 `events`（要记录的事例数）与 `generated`（要生成的事例数）恰好给一个，否则抛 `ValueError`；给出的数和 `generated_limit` 小于 `1` 时抛 `ValueError`（`the <name> asked for are <number>: at least 1`）。
3. **toy MIP 分支**（`kind == "toy_mip"`）：取 `g4setup["maxstep"]`（`g4setup` 为 `None` 时取 `DEVICE_ALONE["maxstep"] = 2`），调用 `mip_deposits`，见下节。这一支由 Python 完成，随机数取自流 `stream("toy_mip")`。
4. **Geant4 分支**（`kind` 为 `"beam"` 或 `"decay_source"`）：
   1. 导入 `geant4.interaction`。缺 `g4ppyy` 时抛 `MissingDependency`（`Geant4's Python bindings, g4ppyy, are not installed in this Python`）。
   2. `g4_configuration` 合成运行配置：源或其 `particles` 中出现 `par_in`、`par_out`、`par_angle` 时抛 `ValueError`（源的位置属于装置）；取 `g4setup`（`None` 时取 `DEVICE_ALONE`）的深拷贝，弹出 `"source"`，没有时抛 `ValueError`（`the g4setup ... does not place the source`）；用源的键覆盖装置的同名键，删去 `name`、`kind`、`description`；令 `par_in = source.at`、`par_out = source.towards`、`par_angle = source.angle`（缺省 `0`）。有 `particles` 时，每项先取配置里的 `par_randx`、`par_randy`、`par_type`、`par_energy`，再用自己的键覆盖，发射点与瞄准点各加 `offset`（缺省 `[0, 0, 0]` $\mu\text{m}$）。最后写入 `recorded_events = events`、`total_events = generated`（按记录数运行时为 `generated_limit`）、`edep_min`、`edep_max`。
   3. `tilted` 按入射角转动源：`par_angle` 为 `0` 时不变。否则记 $\mathbf{r}_{\text{in}} = (x_0, y_0, z_0)$、$\mathbf{r}_{\text{out}} = (x_1, y_1, z_1)$；若 $0 \le z_0 \le l_z$ 或 $z_1 = z_0$，抛 `ValueError`（源连线不从任一面进入器件）。取入射面 $z_f = l_z$（$z_0 > l_z$）或 $z_f = 0$，转轴平行于 $y$ 轴、过 $x_p = x_0 + \frac{z_f - z_0}{z_1 - z_0}(x_1 - x_0)$，对配置及各 `particles` 的 `par_in`、`par_out` 作
      $$x' = (x - x_p)\cos\vartheta + (z - z_f)\sin\vartheta + x_p, \qquad z' = -(x - x_p)\sin\vartheta + (z - z_f)\cos\vartheta + z_f$$
      其中 $\vartheta$ 为 `par_angle`（度）。$\vartheta > 0$ 时，顶面上方的源转到 $-x$ 一侧，粒子带 $+x$ 分量射向入射点。$y$、`par_randx`、`par_randy` 不变，装置里的物体不动。
   4. 构建几何（`GeneralDetectorConstruction`；`geant4_model == "gdml_import"` 时用 `GDMLDetectorConstruction`）。世界是 `world` 材料的立方体，中心在器件 $z = 0$ 面的中点，半边长由 `world_half_side` 给出：令 $\rho = \max\bigl(l_x/2,\ l_y/2,\ l_z,\ \max_{\text{物体},u}(|p_u| + a_u/2),\ \max_{\text{发射点},u}(|r_{\text{in},u}| + R)\bigr)$，其中 $p_u$、$a_u$ 是物体的 `position_<u>`、`side_<u>`，$R$ 为 `par_radius`；$\rho \le 25000\ \mu\text{m}$ 时取 `25000`，否则取 $2\rho$。器件是 $l_x \times l_y \times l_z$ 的长方体，中心在 $(0, 0, l_z/2)$，即占据 $x \in [-l_x/2, l_x/2]$、$y \in [-l_y/2, l_y/2]$、$z \in [0, l_z]$。随后按 `object` 建周边物体。同一 `compound_name` 的二元化合物组分或密度不一致时抛 `ValueError`（`Conflicting Geant4 material definition for ...`）。二元化合物按原子数份额换算质量份额 $m_i = n_i A_i / (n_1 A_1 + n_2 A_2)$。
   5. 设置随机引擎、物理表与用户动作。源含 `nuclides` 时用 `NuclideGeneratorAction` 与 `DecayStackingAction`，否则用 `GeneralPrimaryGeneratorAction`。后者每事例对每个粒子从流 `stream("source")` 抽 $\delta_x \sim U(-\texttt{par\_randx}, \texttt{par\_randx})$、$\delta_y \sim U(-\texttt{par\_randy}, \texttt{par\_randy})$，方向取 $\mathbf{d} = \mathbf{r}_{\text{out}} - \mathbf{r}_{\text{in}} + (\delta_x, \delta_y, 0)$，从 $\mathbf{r}_{\text{in}}$ 发射；`par_type` 为列表时再抽一个等概率的下标。`par_type` 与 `par_energy` 列表长度不等时抛 `ValueError`。
   6. 执行 `/run/initialize`；给了 `picture` 且 `drawn > 0` 时打开离屏绘图（见“图”）；`BeamOn(total_events)`。
   7. 事例记录：事例结束时，若器件内总沉积 $E_{\text{tot}} > 0$ 且 $E_{\text{tot}} \ge$ `edep_min`、$E_{\text{tot}} \le$ `edep_max`（未给的界不检查），记下该事例。按记录数运行时，记录数达到 `recorded_events` 即 `AbortRun`；生成事例数 `generated_events` 取已结束的事例数。按生成数运行时 `generated_events = total_events`。
   8. `deposits()`：按记录数运行而记录数仍少于 `recorded_events` 时抛 `RuntimeError`（`... events asked for were recorded when the limit of ... generated events was reached ...`）。否则把各步位置由 Geant4 坐标换到器件坐标 $\mathbf{r}_{\text{dev}} = \mathbf{r}_{\text{G4}} + (l_x/2,\ l_y/2,\ 0)$，用 `deposits_of_steps("Device", ...)` 去掉 $E_k \le 0$ 的步和没有剩余步的事例。事例号是 Geant4 的 `eventID`。
   9. 无论是否出错，最后调用 `close()` 释放 Geant4 对象。
5. **写入源发射比例**：`generated_fraction(source)`：源含 `nuclides` 且 `par_cone` 非 `None` 时为式 (16)，否则为 `1.0`。
6. **电离**：对每个事例调用 `ionized_pairs(event, my_d.material, fano)`。材料不在 `PAIR_ENERGY_EV` 中时抛 `ValueError`；`fano=True` 而材料不在 `FANO_FACTOR` 中时抛 `ValueError`。每个事例从自己的流 `stream(f"ionization/{event.event}")` 抽样，所以一个事例的对数与其前记录了哪些事例无关。

`write_simulated_deposits` 调用 `simulate_deposits` 后用 `write_deposits` 写文件，返回记录事例数。

GDML 导入模式按 `material` 为 `"Si"`（`G4_Si`）和 `"SiC"`（Si、C 原子数各半，$3.2\ \text{g/cm}^3$）建器件逻辑体 `"Device"`。

### 能损线切成沉积步

**Geant4**：步长由 Geant4 决定，器件内不超过 `maxstep`（式 (3)）。`GeneralSteppingAction` 对前点逻辑体名为 `"Device"` 的每一步调用 `RecordDevice`：累加 $E_{\text{tot}}$，记下步中点 $\frac{1}{2}(\mathbf{r}^{\text{pre}} + \mathbf{r}^{\text{post}}) \times 1000$（Geant4 的 $\text{mm}$ 换成 $\mu\text{m}$）、前点 $\mathbf{r}^{\text{pre}} \times 1000$（写作 `x_start` 等）、沉积能量（$\text{MeV}$）和前点的全局时间（$\text{s}$）。

**toy MIP**（`mip_deposits`）：

1. 源含 `_SOURCE_KEYS`（`name`、`kind`、`description`、`start`、`end`、`position_range_um`、`direction_sigma_mrad`、`packets`、`landau_sampling`）以外的键时抛 `ValueError`；缺 `landau_sampling` 时抛 `ValueError`；材料不在 `PAIRS_PER_UM` 中时抛 `ValueError`。
2. 由 `generation(events, generated, generated_limit, recorded)` 给出事例号 $0, 1, \dots$：按生成数运行时共 `generated` 个；按记录数运行时生成到记录数等于 `events` 为止，生成数达到 `generated_limit` 仍不够时抛 `RuntimeError`。全部抽样用同一条流 `stream("toy_mip")`。
3. 每个事例的径迹端点（`_track_ends`）：起点缺省 $(l_x/2, l_y/2, 0)$，终点缺省 $(l_x/2, l_y/2, l_z)$。有 `position_range_um` 时依次抽 $x_s \sim U(x_{\text{lo}}, x_{\text{hi}})$、$y_s \sim U(y_{\text{lo}}, y_{\text{hi}})$（`"x"`、`"y"` 两项都要给）。有 `direction_sigma_mrad` 时，对 `"x"`、`"y"` 中 $\sigma > 0$ 的分量抽斜率 $k_u \sim \mathcal{N}(0, (10^{-3}\sigma_u)^2)$。抽过起点或斜率时，终点横坐标改为 $u_e = u_s + k_u (z_e - z_s)$。
4. 段数 $n$：给了 `packets` 时取 `int(packets)`，否则 $n = \lceil L / \texttt{maxstep} \rceil$，$L$ 为起点到终点的距离（$\mu\text{m}$）。每段长度 $\Delta l = L/n$，按式 (5) 依次抽各段能量。
5. 事例总能量 $\sum_k E_k$ 小于 `edep_min` 或大于 `edep_max` 时不记录。toy MIP 保留能量为 $0$ 的段。
6. 第 $k$ 段（$k = 0, \dots, n-1$）的位置取段中点 $\mathbf{r}_s + \frac{k + 0.5}{n}(\mathbf{r}_e - \mathbf{r}_s)$，起点 $\mathbf{r}_s + \frac{k}{n}(\mathbf{r}_e - \mathbf{r}_s)$，时刻 $0.0\ \text{s}$，探测器名 `"Device"`。
7. 返回 `Deposits(generated_events = 最后一个事例号 + 1, ...)`。

### 激光载流子群

`LaserInjection(my_d, laser_dic)` 读入激光键（见“接口”）。未给 `alpha` 时按式 (7) 查表：组件里没有 `laser/absorption/<material>.txt` 时抛 `ValueError`；$10^3\lambda$ 小于表的最短波长时抛 `ValueError`；大于最长波长时 $\alpha = 0$。然后先在 $\alpha \ne 0$ 时用 $k = 2$、展宽 $\tau$ 加 SPA 群，再在 `tech == "TPA"` 时用 $k = 4$、展宽 $\tau/\sqrt{2}$ 加 TPA 群。`tech` 不是 `"SPA"`、`"TPA"` 时在加完 SPA 群之后抛 `NameError(tech)`。每次加群（`_add_groups`）的步骤：

1. **光路坐标**（`_beam_frame`）：`"top"` 从 $z = 0$ 沿 $+z$，光路长 $l_z$，焦点 $s_f = f_z l_z$，横向坐标 $(u, v) = (x, y)$，中心 $(f_x l_x, f_y l_y)$；`"bottom"` 从 $z = l_z$ 沿 $-z$，光路长 $l_z$，$s_f = l_z - f_z l_z$，$z = l_z - s$；`"edge"` 从 $x = 0$ 沿 $+x$，光路长 $l_x$，$s_f = f_x l_x$，$(u, v) = (y, z)$，中心 $(f_y l_y, f_z l_z)$。其中 $f_x, f_y, f_z$ 为 `fx_rel`、`fy_rel`、`fz_rel`。其他 `direction` 抛 `NameError(direction)`。
2. **光路采样**：最细尺度 $d = \min\bigl(L_{\text{beam}},\ z_R,\ 10^{6}/\alpha\bigr)$（$\alpha = 0$ 时第三项取 $L_{\text{beam}}$），在 $[0, L_{\text{beam}}]$ 上取 $\lceil 50 L_{\text{beam}}/d \rceil + 1$ 个等距点，按式 (10) 或 (11) 求 $dN/ds$，用梯形法累积得 $M(s)$（乘 $10^{-6}$ 换成每 $\mu\text{m}$），总对数 $N_{\text{tot}} = M(L_{\text{beam}})$。
3. **分群**：横截面分 $4$ 环 $\times$ $8$ 扇区，光路分 $n_s = \bigl\lceil \max(N_{\text{tot}}/\texttt{pairs\_per\_group},\ \texttt{groups}) / 32 \bigr\rceil$ 段。第 $i$ 段的位置 $s_i$ 由 $M(s_i) = \frac{i + 0.5}{n_s} N_{\text{tot}}$ 反插值得到；第 $j$ 环的相对半径 $\rho_j = \sqrt{-\ln\bigl(1 - \frac{j + 0.5}{4}\bigr)/k}$；第 $m$ 扇区的方位角 $\varphi_m = \frac{m + 0.5}{8}\,2\pi$。群位于 $r = \rho_j\,w(s_i)$，$u = u_c + r\cos\varphi_m$，$v = v_c + r\sin\varphi_m$。每个群等分对数 $N_{\text{tot}}/(32 n_s)$。
4. **去掉器件外的群**：只保留 $0 \le u \le$ 横向尺寸、$0 \le v \le$ 横向尺寸的群。近似：器件外的光不穿过器件（代码注释），去掉的群所带的对数随之舍去。
5. 每个群记下位置与时刻 `central_time`（写入 `track_position`）、对数（`ionized_pairs`）、时间展宽（`time_FWHM`）。

`laser_deposits(my_d, laser_dic)` 把这些群写成事例号 `0` 的一个事例：探测器名 `"Device"`，对数取上面的均值，能量取 $N \cdot \varepsilon \times 10^{-6}$（$\text{MeV}$，由对数按电离能折算），起点等于位置，`t_fwhm` 取 `time_FWHM`；`generated_events = 1`，没有群时事例列表为空。

### 文件的写出与读入

`write_deposits(path, deposits)` 先检查，后写文件：

1. 某可选列（`x_start`、`y_start`、`z_start`、`t_fwhm`）有的事例有、有的事例没有时抛 `ValueError`（`some events have <name> and some do not`）。所有事例都有的可选列才写出。
2. 某事例的 `pairs` 为 `None` 时抛 `ValueError`（只写电离已抽样的沉积）。
3. 某事例的 `detector`、`x`、`y`、`z`、`t`、`e`、`pairs` 或要写的可选列的长度不等于沉积步数时抛 `ValueError`。
4. 检查都通过后以 `"w"` 打开文件（覆盖旧文件），写属性和数据集；各事例的沉积步首尾相接，由 `count` 切分。检查失败时文件保持原样。

`read_deposits(path)` 按 `count` 把各列切回事例，可选列存在才读，返回 `Deposits`。

### 几何查看

`view_geometry(my_d, source, g4setup, events, g4_seed, driver, output)` 不写沉积文件：

1. 记 `tsg` 为 `driver.upper()` 属于 `{"TSG", "TSG_FILE", "TSG_OFFSCREEN"}`。给了 `output` 而驱动既不是 TSG 也不以 `"OGL"` 开头时抛 `ValueError`。
2. 驱动不在 `DAWNFILE`、`HEPREPFILE`、`K3DJUPYTER`、`MPLJUPYTER`、`TSG`、`TSG_FILE`、`TSG_OFFSCREEN`、`VRML2FILE` 中时，先建 `G4UIExecutive` 会话。
3. 以 `generated = events`、无能量窗合成配置并转动，构建与“Geant4 分支”相同的几何和动作。
4. 打开驱动（`register_driver` 为 g4ppyy 补注册 `TSG_OFFSCREEN`、`TSG_QT_GLES`、`OGL`、`VRML2FILE`、`ATREE`）。TSG 且给了 `output` 时设 PNG 输出 `<output>.png`。`gdml_import` 执行组件 `g4macro/vis_pcb.mac`，否则执行 `g4macro/init_vis.mac` 与 `g4macro/vis.mac`；宏不在组件路径中时抛 `FileNotFoundError`。OGL 且给了 `output` 时设白底、矢量打印、`2000 × 2000`、文件名 `output`。
5. `BeamOn(events)`，然后刷新视图并导出图片。有会话时进入交互，关窗后返回。任一 Geant4 命令返回非零状态时抛 `RuntimeError`（`Geant4 refused the command ...`）。

## 软件实现

### 各文件的分工

- `simulate_deposits.py`：环节入口 `simulate_deposits`、`write_simulated_deposits`，缺省装置 `DEVICE_ALONE`，配置合成 `g4_configuration`，入射角 `tilted`，世界大小 `world_half_side`，发射比例 `generated_fraction`。
- `generation.py`：事例数检查 `asked`、生成循环 `generation`、`GENERATED_LIMIT` 与生成不足时的错误 `too_few`。
- `mip_track.py`：toy MIP 的径迹与分段 `mip_deposits`。
- `ionization.py`：`PAIR_ENERGY_EV`、`FANO_FACTOR` 与 `ionized_pairs`。
- `deposits.py`：数据结构 `EventDeposits`、`Deposits`，以及 `deposits_of_steps`、`write_deposits`、`read_deposits`。
- `laser.py`：`absorption_coefficient`、`LaserInjection`（载流子群、`timePulse`、两张群分布图）与 `laser_deposits`。
- `view_geometry.py`：`view_geometry`。
- `geant4/interaction.py`：`GeneralG4Interaction`，一次 Geant4 运行的建立、运行、记录与释放。
- `geant4/detector_construction.py`、`geant4/g4_gdml_import.py`：几何与材料；后者导入外部 GDML。
- `geant4/action_initialization.py`、`primary_generator_action.py`、`nuclide_source.py`、`event_action.py`、`stepping_action.py`、`run_action.py`：Geant4 用户动作，分别负责组装、束流发射、核素与衰变产物、事例记录、步记录和运行设置。
- `geant4/drivers.py`：为 g4ppyy 注册可视化驱动。`geant4/g4ppyy_runtime.py`：导入 g4ppyy，进程结束时先释放可视化管理器再释放运行管理器。
- `toy_mip.py`：`ToyMIPLineSource`、`ToyMIPInteraction`，供算法测试用的直线 toy MIP 载流子团。`energy_loss.py`：Fano 抽样 `sample_fano_pairs` 与 Landau 抽样 `sample_landau_energy_loss`。`carrier_list.py`：`CarrierListFromG4P`、`PixelCarrierListFromG4P`，把 Geant4 的步换成载流子列表，交给 [载流子漂移与感应电流](current.md) 的 `CalCurrentG4P`。

### 核心数据结构

- `EventDeposits`：一个事例的沉积。`event`（事例号）；每步一项的列表 `detector`（探测器名）、`x`、`y`、`z`（器件坐标中的步中点，$\mu\text{m}$）、`t`（$\text{s}$）、`e`（$\text{MeV}$）；`pairs`（对，电离抽样前为 `None`）；`x_start`、`y_start`、`z_start`（步起点，$\mu\text{m}$，未知时为 `None`）；`t_fwhm`（产生时刻围绕 `t` 的高斯展宽 FWHM，$\text{s}$，`None` 表示都在 `t` 产生）。
- `Deposits`：一个作业的沉积。`generated_events`（源生成的事例数）、`edep_min`、`edep_max`（$\text{MeV}$，可为 `None`）、`events`（`EventDeposits` 列表）、`generated_fraction`（缺省 `1.0`）。
- `LaserInjection`：`track_position`（每群 `[x, y, z, t]`，$\mu\text{m}$、$\text{s}$）、`ionized_pairs`（每群对数）、`time_FWHM`（每群时间展宽，$\text{s}$），以及 `temporal_FWHM`、`timePulse` 等供电流卷积使用的属性。

## 接口

使用者能设的是下表中器件文件、装置脚本、放射源和束流文件、激光文件里的键；页内其余参数写死在代码里。事例数、能量窗、`fano` 与绘图事例数 `deposit.plots` 是环节选项，命令行用法见 [能量沉积环节](../stages/deposit.md)。

### 器件文件读取的键

| 键 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `l_x`, `l_y`, `l_z` | 无（必选） | $\mu\text{m}$ | 器件尺寸，见 [器件模型](device.md) |
| `material` | 无（必选） | 无 | `"Si"`、`"SiC"` 或 `"Diamond"`；决定 Geant4 材料、电离能与 Fano 因子；toy MIP 只支持 `"Si"`、`"SiC"` |

### 装置

装置是 `g4setup/<名称>.py` 脚本里的字典 `G4SETUP`，未给装置时用 `DEVICE_ALONE`（除 `name`、`description` 外与 `device_alone.py` 相同）。

#### `G4SETUP` 顶层键

| 键 | 默认值（`DEVICE_ALONE`） | 单位 | 含义 |
| --- | --- | --- | --- |
| `name`, `description` | 无（可选） | 无 | 装置名与说明；`name` 只出现在报错信息里 |
| `geant4_model` | `"device"` | 无 | Geant4 源必填；取 `"gdml_import"` 时导入外部 GDML，其他取值只作标识 |
| `world` | `"G4_Galactic"` | 无 | Geant4 源必填；世界体的 NIST 材料名 |
| `maxstep` | `2` | $\mu\text{m}$ | 必填；器件内 Geant4 的最大步长，也是 toy MIP 未给 `packets` 时的分段长度上限 |
| `source` | `{"at": [0, 0, -17000], "towards": [0, 0, 0], "angle": 0}` | $\mu\text{m}$, 度 | Geant4 源必填；`at` 为源位置，`towards` 为瞄准点（Geant4 坐标），`angle` 为入射角（缺省 `0`），非零时按“`simulate_deposits` 的分支”第 4.3 步转动 |
| `object` | `{}` | 无 | Geant4 源必填；周边物体，可含 `"elemental"` 和 `"binary_compounds"` 两类 |
| `par_type`, `par_energy`, `par_randx`, `par_randy` | 无 | 见源 | 可选；装置可给这些束流键，源里的同名键覆盖它们 |

Geant4 坐标中器件占据 $x \in [-l_x/2, l_x/2]$、$y \in [-l_y/2, l_y/2]$、$z \in [0, l_z]$，顶面 $z = 0$ 之上为 $z < 0$。

#### `object` 两类几何体键

`object["elemental"]` 和 `object["binary_compounds"]` 都是以几何体名为键的字典，每一项是一个长方体：前者用 Geant4 NIST 材料，后者由两种元素组成。例如器件顶面上方的一层铝：

```python
"object": {
    "elemental": {
        "Al": {
            "name": "Al",
            "material": "G4_Al",
            "side_x": 5000,
            "side_y": 5000,
            "side_z": 0.08,
            "colour": [1, 0.1, 0.8],
            "position_x": 0,
            "position_y": 0,
            "position_z": -89.3,
        },
    },
},
```

这是一块 $5\ \text{mm} \times 5\ \text{mm} \times 0.08\ \mu\text{m}$ 的铝片，中心在器件顶面上方 $89.3\ \mu\text{m}$。`position_x`、`position_y`、`position_z` 给的是长方体中心；要让下表面离器件顶面 $d$，就写 `position_z = -(d + side_z / 2)`。

下表各键对其适用的分类都必填，只有 `elemental` 的 `tub` 可以省去。

| 键 | 适用分类 | 单位 | 含义 |
| --- | --- | --- | --- |
| `name` | 两者 | 无 | 几何体名称 |
| `material` | `elemental` | 无 | Geant4 NIST 材料名，如 `"G4_Al"`、`"G4_Ni"`、`"G4_Ti"`、`"G4_Si"`、`"G4_BRASS"` |
| `material_1`, `material_2` | `binary_compounds` | 无 | 两种元素的符号，如 `"Si"`、`"C"`、`"N"`、`"O"` |
| `compound_name` | `binary_compounds` | 无 | 化合物材料名；同名化合物的组分与密度须一致 |
| `density` | `binary_compounds` | $\text{g/cm}^3$ | 化合物密度 |
| `natoms_1`, `natoms_2` | `binary_compounds` | 无 | 两种元素的原子数份额，按原子量换成质量份额 |
| `side_x`, `side_y`, `side_z` | 两者 | $\mu\text{m}$ | 长方体沿 $x$、$y$、$z$ 的全尺寸 |
| `position_x`, `position_y`, `position_z` | 两者 | $\mu\text{m}$ | 长方体中心在 Geant4 坐标中的位置 |
| `colour` | 两者 | 无 | 可视化 RGB 颜色 `[r, g, b]` |
| `tub` | `elemental` 可选，`binary_compounds` 必填（无孔填 `{}`） | $\mu\text{m}$ | 从长方体中心沿 $z$ 轴减去的圆柱孔，含半径 `"tub_radius"` 和半长 `"tub_depth"` |

#### `"gdml_import"` 附加键

GDML 文件中含字符串 `RASER_GDML_WRAPPER_WORLD` 时，GDML 的世界体直接作 Geant4 世界体，世界的大小、材料与导入几何体的放置都由 GDML 文件给出；下表中起作用的是 `gdml.file`、`gdml.validate` 与 `visualization`。

| 键 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `world_half_size_um` | 由 `world_half_side` 计算 | $\mu\text{m}$ | 覆盖世界立方体的半边长 |
| `gdml.file` | 无（必填） | 无 | GDML 文件路径；依次按绝对路径、各组件根下的该路径、各组件根下 `g4experiment/<file>`、`src/raser/<file>` 查找；为空抛 `ValueError`，找不到抛 `FileNotFoundError` |
| `gdml.top_volume` | `None` | 无 | 要放置的逻辑体名；文件中没有该名字或未给时放置 GDML 的世界体 |
| `gdml.validate` | `False` | 无 | 读取时是否校验 GDML schema |
| `gdml.auto_center` | `True` | 无 | 是否减去 GDML 中全部 `<position>` 坐标包围盒的中心 |
| `gdml.position_um` | `[0.0, 0.0, 0.0]` | $\mu\text{m}$ | 导入几何体的平移；长度不为 `3` 时按零处理 |
| `gdml.rotation_xyz` | `[0.0, 0.0, 0.0]` | 度 | 依次绕 $x$、$y$、$z$ 轴的转角 |
| `gdml.placement_name` | `"ImportedGDML"` | 无 | 导入几何体的物理体名 |
| `visualization` | `{}` | 无 | 可视化样式：`imported_visible`（`True`）、`imported_force_wireframe`（`True`）、`imported_force_solid`（与线框相反）、`imported_colour_rgba`（`[0.20, 0.85, 0.85, 1.00]`）、`device_visible`（`True`）、`hide_device`（`False`）、`device_force_wireframe`（`False`）、`device_force_solid`（与线框相反）、`device_colour_rgba`（`[1.00, 0.10, 0.10, 0.35]`） |

#### 库中装置

| 组件 | 位置 | 说明 |
| --- | --- | --- |
| `device_alone` | `components/g4setup/` | 器件单独放在真空里，源在顶面上方 $17\ \text{mm}$ |
| `Sr90_collimator` | `bench/signal/components/g4setup/` | 空气中的黄铜准直器（见 [信号](../bench/signal.md)） |
| `pcb_readout_gdml` | `bench/signal/components/g4setup/` | 导入 `pcb_readout.gdml` 的 PCB 读出板（见 [信号](../bench/signal.md)） |
| `time_resolution` | `bench/timeres/components/g4setup/` | 参考硅器件与两块开孔 PCB 板（见 [时间分辨](../bench/timeres.md)） |

### 放射源和束流

#### 公共键

| 键 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `name` | 无（可选） | 无 | 源名称 |
| `kind` | 无（必填） | 无 | `"beam"`、`"decay_source"` 或 `"toy_mip"` |
| `description` | 无（可选） | 无 | 文字说明 |

源里不能有 `par_in`、`par_out`、`par_angle`：源的位置与方向由装置的 `source` 给出。

#### `beam` 与 `decay_source` 键

`"beam"` 与 `"decay_source"` 走同一条 Geant4 分支；是否按核素衰变只看源里有没有 `nuclides`。

| 键 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `par_type` | 无（无 `nuclides` 时必填） | 无 | Geant4 粒子名（如 `"e-"`、`"proton"`、`"alpha"`），或等概率抽取的粒子名列表 |
| `par_energy` | 无（无 `nuclides` 时必填） | $\text{MeV}$ | 粒子动能，或与 `par_type` 等长的列表 |
| `par_randx`, `par_randy` | `0`, `0` | $\mu\text{m}$ | 发射方向 `towards - at` 的 $x$、$y$ 分量上均匀随机偏移的半宽 |
| `particles` | 无（可选） | 无 | 每事例同时发射的粒子列表；每项可覆盖 `par_type`、`par_energy`、`par_randx`、`par_randy`，并用 `offset`（缺省 `[0, 0, 0]`，$\mu\text{m}$）平移发射点与瞄准点 |
| `nuclides` | 无（可选） | 无 | 静止核素 `[[Z, A], ...]`；给出时每事例等概率取一种衰变一次，发射的粒子由衰变给出 |
| `par_radius` | `0` | $\mu\text{m}$ | 核素所在圆盘的半径，圆盘垂直于发射轴 |
| `par_cone` | `None` | 度 | 衰变产物绕发射轴各向同性出射的半锥角，只在有 `nuclides` 时起作用 |

#### `toy_mip` 键

源里只能有下表的键和公共键。

| 键 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `landau_sampling` | 无（必填） | 无 | 为 `true` 时每段能量按式 (5) 的 Landau 分布抽样，为 `false` 时取平均能损 |
| `start` | `[l_x / 2, l_y / 2, 0.0]` | $\mu\text{m}$ | 径迹在器件坐标中的起点 |
| `end` | `[l_x / 2, l_y / 2, l_z]` | $\mu\text{m}$ | 径迹在器件坐标中的终点 |
| `position_range_um` | 无（可选） | $\mu\text{m}$ | 起点横坐标的均匀抽样范围 `{"x": [lo, hi], "y": [lo, hi]}`，两项都要给 |
| `direction_sigma_mrad` | 无（可选） | mrad | 斜率 $dx/dz$、$dy/dz$ 的高斯抽样标准差 `{"x": sigma_x, "y": sigma_y}`，两项都要给 |
| `packets` | $\lceil L / \texttt{maxstep} \rceil$ | 段 | 一条径迹切成的沉积段数 |

#### 库中放射源和束流

| 组件 | 类型 | 说明 |
| --- | --- | --- |
| `beam/electron`、`beam/muon`、`beam/pion`、`beam/proton` | `beam` | `e-`、`mu-`、`pi-`、`proton`，$1000\ \text{MeV}$ |
| `beam/proton_3GeV_spread` | `beam` | $3000\ \text{MeV}$ 质子，`par_randx = par_randy = 728.6` $\mu\text{m}$ |
| `decay/Sr90` | `decay_source` | 核素 Sr-90 与 Y-90 等概率，`par_radius = 2500` $\mu\text{m}$，`par_cone = 15` 度 |
| `decay/Am241` | `decay_source` | 由 `par_type`、`par_energy` 发射 $5.54\ \text{MeV}$ 的 `alpha` |
| `toy/MIP` | `toy_mip` | 缺省径迹，`landau_sampling = true` |
| `toy/MIP_pixel_edge`、`toy/MIP_pixel_edge_fast` | `toy_mip` | 从 $(600, 450, 0)$ 到 $(600, 450, 300)$ $\mu\text{m}$，`packets` 为 `50` 与 `5`，后者不做 Landau 抽样 |
| `toy/MIP_strip_edge` | `toy_mip` | 起点 $x$ 在 $[150, 270]$ $\mu\text{m}$ 内抽样，$dx/dz$ 的标准差 $10$ mrad |
| `bunch`（`apps/bmos/components/source/`） | `beam` | 三个 $80\ \text{MeV}$ 质子并排同时发射（见 [`bmos`](../apps/bmos.md)） |

### 激光

| 键 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `description` | 无（可选） | 无 | 激光器型号与参数说明 |
| `tech` | 无（必填） | 无 | `"SPA"`（单光子吸收）或 `"TPA"`（双光子吸收） |
| `direction` | 无（必填） | 无 | `"top"`（从 $z = 0$ 沿 $+z$）、`"bottom"`（从 $z = l_z$ 沿 $-z$）或 `"edge"`（从 $x = 0$ 沿 $+x$） |
| `refractionIndex` | 无（必填） | 无 | 器件材料在该波长的折射率 $n$ |
| `wavelength` | 无（必填） | $\text{nm}$ | 激光波长 |
| `alpha` | 按式 (7) 查表 | $\text{m}^{-1}$ | 吸收系数；给 `0` 时没有单光子吸收，`"TPA"` 激光只有 TPA 群 |
| `beta_2` | 无（`"TPA"` 必填） | $\text{m/W}$ | 双光子吸收系数 |
| `temporal_FWHM` | 无（必填） | $\text{s}$ | 脉冲时间半高全宽 $\tau$ |
| `pulse_energy` | 无（必填） | $\text{J}$ | 脉冲能量 $E_p$ |
| `spacial_FWHM` | 无（必填） | $\mu\text{m}$ | 焦点处光斑的空间半高全宽 |
| `l_Rayleigh` | 按式 (9) 计算 | $\mu\text{m}$ | 器件内的瑞利长度 |
| `central_time` | 无（必填） | $\text{s}$ | 脉冲中心时刻 |
| `pairs_per_group` | 无（必填） | 对 | 每个载流子群的对数上限 |
| `groups` | 无（必填） | 群 | 每种吸收至少分出的群数（去掉器件外的群之前） |
| `fx_rel`, `fy_rel`, `fz_rel` | 无（必填） | 无 | 焦点的相对坐标，绝对位置为 $(f_x l_x,\ f_y l_y,\ f_z l_z)$ |

#### 吸收系数表（`laser/absorption/<material>.txt`）

空白分隔的两列文本，`#` 开头为注释：第一列波长（$\text{nm}$），第二列 $300\ \text{K}$ 下的带间吸收系数（$\text{cm}^{-1}$），按波长升序。库中只有 `Si.txt`，波长 $250$ 至 $1450\ \text{nm}$，取自文献 [7]。

#### 库中激光

| 组件 | `tech` | 说明 |
| --- | --- | --- |
| `LA01IR_top_Si`、`LA01IR_edge_Si` | `"SPA"` | $1064\ \text{nm}$，硅，查表取 $\alpha$ |
| `LA01R_top_Si`、`LA01R_bottom_Si` | `"SPA"` | $660\ \text{nm}$，硅，查表取 $\alpha$ |
| `PIL037_top_SiC`、`PIL037_edge_SiC` | `"SPA"` | $375\ \text{nm}$，碳化硅，`alpha` 分别为 `1000`、`21000` $\text{m}^{-1}$ |
| `TPA1550_top_Si`、`TPA1550_edge_Si` | `"TPA"` | $1550\ \text{nm}$，硅，长于表的上限，$\alpha = 0$，只有 TPA 群 |

### `deposit_<job>.h5` 文件格式

#### 文件属性

| 属性 | 类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `generated_events` | `int` | 事例 | 源生成的事例数 |
| `recorded_events` | `int` | 事例 | 文件里的事例数 |
| `generated_fraction` | `float` | 无 | 源发射中被生成的部分；带 `par_cone` 的核素源为式 (16)，其余为 `1.0` |
| `edep_min`, `edep_max` | `float` | $\text{MeV}$ | 器件内总沉积能量窗的下限、上限，给了才写 |

生成事例中被记录的比例是 `recorded_events / generated_events`；每次源发射记录的事例数是 `recorded_events / generated_events * generated_fraction`。

#### 数据集

| 数据集 | 形状与类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `event` | `(recorded_events,)`, `int64` | 无 | 事例号：Geant4 的 `eventID`，toy MIP 的生成序号，激光为 `0` |
| `count` | `(recorded_events,)`, `int64` | 步 | 每个事例的沉积步数 |
| `detector` | `(sum(count),)`, 变长 `str` | 无 | 沉积步所在的探测器名，本包写 `"Device"` |
| `x`, `y`, `z` | `(sum(count),)`, `float64` | $\mu\text{m}$ | 器件坐标中的步中点 |
| `t` | `(sum(count),)`, `float64` | $\text{s}$ | 自初级粒子产生起的时间；Geant4 取步前点的全局时间，toy MIP 为 `0.0`，激光为 `central_time` |
| `e` | `(sum(count),)`, `float64` | $\text{MeV}$ | 沉积能量；激光为对数乘电离能 |
| `pairs` | `(sum(count),)`, `float64` | 对 | 电子-空穴对数 |
| `x_start`, `y_start`, `z_start` | `(sum(count),)`, `float64`（可选） | $\mu\text{m}$ | 步起点，所有事例都有时写；步终点为 `2 * (x, y, z) - start` |
| `t_fwhm` | `(sum(count),)`, `float64`（可选） | $\text{s}$ | 产生时刻围绕 `t` 的高斯展宽 FWHM，所有事例都有时写（`laser_deposits`） |

### 图

| 文件 | 写出者 | 内容 | 坐标单位 |
| --- | --- | --- | --- |
| `<picture>.png` | `simulate_deposits`（`picture` 非空且 `drawn > 0`，仅 Geant4 源） | `TSG_OFFSCREEN` 画的几何（`vis.mac`：体积、坐标轴、按电荷着色的径迹与步点）与前 `drawn` 个记录事例；环节写作 `deposit` 节点里的 `g4_geometry.png` | Geant4 坐标 |
| `<output>.png` | `view_geometry`（TSG 驱动） | 几何与生成事例的径迹 | Geant4 坐标 |
| `<output>` 矢量图 | `view_geometry`（OGL 驱动） | 同上，`2000 × 2000`，白底 | Geant4 坐标 |
| `nocarrier_<fx>_<fy>_<fz>.pdf` | `LaserInjection.draw_nocarrier3D` | 载流子群按对数加权的 `TH3D`，$50^3$ 箱，范围为各群的包围盒；轴标题 `Depth`、`Width`、`Thick`（即 $x$、$y$、$z$）；文件名中的相对坐标保留 5 位小数 | $\mu\text{m}$ |
| `nocarrier2D_<fx>_<fy>_<fz>.pdf` | `LaserInjection.draw_nocarrier2D` | $x$-$z$ 平面的 `TH2D`（`COLZ`），$50 \times 50$ 箱，颜色为对数（`Carriers`） | $\mu\text{m}$ |

## 参考文献

- [1] U. Fano, “Ionization Yield of Radiations. II. The Fluctuations of the Number of Ions”, Phys. Rev. 72 (1947) 26, doi:10.1103/PhysRev.72.26
- [2] T. Shimaoka et al., “Fano factor evaluation of diamond detectors for alpha particles”, Phys. Status Solidi A 213 (2016) 2629, doi:10.1002/pssa.201600195
- [3] S. Agostinelli et al. (GEANT4 Collaboration), “GEANT4—a simulation toolkit”, Nucl. Instrum. Methods Phys. Res. A 506 (2003) 250, doi:10.1016/S0168-9002(03)01368-8
- [4] J. Allison et al., “Recent developments in Geant4”, Nucl. Instrum. Methods Phys. Res. A 835 (2016) 186, doi:10.1016/j.nima.2016.06.125
- [5] S. Hauf et al., “Radioactive Decays in Geant4”, IEEE Trans. Nucl. Sci. 60 (2013) 2966, doi:10.1109/TNS.2013.2270894
- [6] L. Landau, “On the energy loss of fast particles by ionization”, J. Phys. (USSR) 8 (1944) 201
- [7] M. A. Green, “Self-consistent optical parameters of intrinsic silicon at 300 K including temperature coefficients”, Sol. Energy Mater. Sol. Cells 92 (2008) 1305, doi:10.1016/j.solmat.2008.06.009
