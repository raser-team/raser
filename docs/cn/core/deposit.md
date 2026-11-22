# 能量沉积与电离（`core/deposit`）

`src/raser/core/deposit/` 从 [器件模型](device.md) 取器件的尺寸与材料，从 [能量沉积组件](../components/deposit.md) 取装置脚本、放射源或束流、激光的定义。它用 Geant4 或直线 toy MIP 模型算出粒子在器件里的沉积步（装置通过 `along_beam` 给出多个槽位时，一次算出多块器件各自的沉积步），把每步沉积能量换成电子-空穴对，写成 `deposit.h5`；激光则按吸收系数直接给出载流子群，同样写成 `deposit.h5`。沉积文件交给 [载流子漂移与感应电流](current.md) 做漂移，事例最早沉积时刻交给 [统计分析](analysis.md) 作 `truth`，[望远镜](../bench/telescope.md) 也读这个文件。命令与 `deposit` 段的设置见 [能量沉积环节](../stages/deposit.md)。

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

两式由 `ionized_pairs(event, material, fano)` 实现。`fano=True` 时按式 (2) 抽样，否则取 $N = \bar{N}$，此时材料不需要 Fano 因子。各材料的取值：

| 材料 | `PAIR_ENERGY_EV`（$\text{eV}$） | `FANO_FACTOR` | 出处 |
| --- | --- | --- | --- |
| `"Si"` | `3.6` | `0.115` | 电离能是 PDG 第 35.8 节表 35.10 所给 $3.65\ \text{eV}$ 的近似 [8]；Fano 因子取渐近值 $0.115$ [9]，实测 $0.1161$ [10] |
| `"SiC"` | `7.83` | `0.128` | 4H-SiC 的电子-空穴对产生能 $(7.83 \pm 0.02)\ \text{eV}$ [11]；Fano 因子 $0.128$ [12] |
| `"Diamond"` | `13.1` | `0.382` | CVD 金刚石对 Am-241 的 $5.486\ \text{MeV}$ α 粒子的测量值，Fano 因子为 $0.382 \pm 0.007$ [2] |

Fano 涨落见文献 [1]。

### Geant4 的能损

`beam` 与 `decay_source` 两类源由 Geant4 [3, 4] 输运。物理表是 `FTFP_BERT` 加 `G4StepLimiterPhysics`；源含 `nuclides` 时再加 `G4RadioactiveDecayPhysics` [5]，并把放射性衰变的时间阈值设为 $10^{60}$ 年，使任何寿命的核素都衰变。产生阈沿用物理表的缺省值。每块器件的逻辑体（单器件为 `"Device"`，多器件为槽位名）带 `G4UserLimits`，步长上限是装置的 `maxstep`。Geant4 在体积边界和物理过程处也会截断步。每个前点在器件逻辑体内的步记为该器件的一个沉积步：

$$E_k = \texttt{GetTotalEnergyDeposit}, \qquad \mathbf{r}_k = \tfrac{1}{2}\bigl(\mathbf{r}_k^{\text{pre}} + \mathbf{r}_k^{\text{post}}\bigr), \qquad \ell_k \le s_{\max} \tag{3}$$

其中：

- $E_k$：第 $k$ 步在器件内的总沉积能量，$\text{MeV}$；
- $\mathbf{r}_k^{\text{pre}}, \mathbf{r}_k^{\text{post}}$：该步前点与后点，$\mu\text{m}$；
- $\mathbf{r}_k$：沉积步位置，取步中点，$\mu\text{m}$（代码注释说明：步的两端在器件表面上，舍入误差可能把端点落到器件外）；
- $\ell_k$：步长，$\mu\text{m}$；$s_{\max}$：装置的 `maxstep`，$\mu\text{m}$。

器件材料在 Geant4 里按 `material` 建：`"Si"` 用 NIST 的 `G4_Si`；`"Diamond"` 用密度改为 $3.52\ \text{g/cm}^3$ 的 `G4_C`（代码注释：NIST 的 `G4_C` 是 $2.0\ \text{g/cm}^3$ 的石墨）；`"SiC"` 是 Si、C 原子数各占一半、密度 $3.21\ \text{g/cm}^3$ 的化合物。金刚石密度取自 PDG 的原子与核性质表 [8]，4H-SiC 密度取自文献 [13]。

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
| `"Si"` | `80.0` | `2.88e-4` | `1.78e-5` |
| `"SiC"` | `55.0` | `4.31e-4` | `2.46e-5` |

Si 每 $\mu\text{m}$ 约 $80$ 对：$300\ \mu\text{m}$ 硅的最可几电荷约 $23\,000\ e$，即约 $77\ e/\mu\text{m}$ [8, 14]。SiC 约 $55$ 对$/\mu\text{m}$，按 $7.83\ \text{eV}$ 与 MIP 能损换算。Landau 宽度按 PDG 第 34 章 [8] 的

$$w = \frac{K}{2}\left\langle\frac{Z}{A}\right\rangle\frac{\rho}{\beta^2} \times 10^{-4} \tag{4a}$$

取 $\beta = 1$，其中 $K/2 = 0.1535\ \text{MeV cm}^2/\text{g}$，$\rho$ 为密度（$\text{g/cm}^3$），$10^{-4}$ 把每 $\text{cm}$ 换成每 $\mu\text{m}$：Si（$\langle Z/A\rangle = 0.4985$，$\rho = 2.329$）为 $1.78\times10^{-5}\ \text{MeV}/\mu\text{m}$，4H-SiC（$\langle Z/A\rangle = 0.4988$，$\rho = 3.21$）为 $2.46\times10^{-5}\ \text{MeV}/\mu\text{m}$。

### 激光的单光子与双光子吸收

激光脉冲在器件里按吸收产生载流子。单光子吸收（SPA）每吸收一个光子产生一对，强度沿光路按 Beer–Lambert 定律 $e^{-\alpha s}$ 衰减。双光子吸收（TPA）按 $dI/dz = -\alpha I - \beta_2 I^2$ [15]，产生率正比于光强平方，集中在焦点附近。光束是高斯光束，横向半径随离焦距离展宽。

激光文件未给 `alpha` 时，吸收系数 $\alpha$ 由 `absorption_coefficient` 按器件材料给出。硅查表：

$$\alpha(\lambda) = 100\,\exp\Bigl[\operatorname{interp}\bigl(10^{3}\lambda;\ \lambda_i,\ \ln \alpha_i\bigr)\Bigr] \tag{7}$$

4H-SiC 是间接带隙，带边附近的吸收要声子参与。按声子辅助间接跃迁的半经验模型 [16] 计算，带器件温度 $T$：

$$\alpha(\lambda, T) = 100 \sum_{p=1}^{7} \sum_{\pm} \Bigl(n_p + \tfrac{1}{2} \pm \tfrac{1}{2}\Bigr) \Bigl\{ A_p \bigl[\hbar\omega - (E_{GX} \pm \hbar\Omega_p)\bigr]_+^{1/2} + B A_p \bigl[\hbar\omega - (E_{GX} \pm \hbar\Omega_p + E_{\text{ex}})\bigr]_+^{2} \Bigr\} \tag{7a}$$

$$\hbar\omega = \frac{h c}{e\,\lambda \times 10^{-6}}, \qquad n_p = \frac{1}{\exp(\hbar\Omega_p / k_B T) - 1}, \qquad E_{GX}(T) = E_{GX}(0) - \frac{\varepsilon\,\Theta}{2}\left[\bigl(1 + (2T/\Theta)^{q}\bigr)^{1/q} - 1\right] \tag{7b}$$

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
- $\hbar\omega$：光子能量，$\text{eV}$（$e$ 为元电荷）；$T$：器件文件的 `temperature`，$\text{K}$；$k_B = 8.617\times10^{-5}\ \text{eV/K}$；
- $\hbar\Omega_p$、$A_p$：第 $p$ 个声子的能量（$\text{eV}$）与跃迁系数（$\text{eV}^{-1/2}\,\text{cm}^{-1}$），取文献 [16] 表 I（$E \perp c$，$E$ 为光的电场）：$\hbar\Omega_p$ = 32.4、45.7、50.8、67.8、76.3、95.8、106.2 meV，$A_p$ = 0.5、4、7、3.5、23、23、40.5；
- $\pm$：上号为放出声子，下号为吸收声子；$n_p$：声子的玻色占据数；$[x]_+ = \max(x, 0)$；
- $B = 60\ \text{eV}^{-3/2}$：连续态与激子基态跃迁系数之比；$E_{\text{ex}} = 20\ \text{meV}$：激子结合能；
- $E_{GX}(T)$：激子带隙，$\text{eV}$；$E_{GX}(0) = 3.267\ \text{eV}$，$\varepsilon = 3\times10^{-4}\ \text{eV/K}$，$\Theta = 450\ \text{K}$，$q = 2.9$（文献 [16] 式 (5)），$300\ \text{K}$ 时 $E_{GX} = 3.233\ \text{eV}$；
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

式 (11) 中第二个因子是高斯脉冲时间分布平方的积分。光强沿光路只按 $\alpha$ 衰减。$\alpha \ne 0$ 时按式 (10) 加 SPA 载流子群，`tech` 为 `"TPA"` 时再按式 (11) 加 TPA 载流子群；双光子激光的 $\alpha$ 是缺陷对带隙以下光子的吸收（代码注释）。每个群的产生时刻以 `central_time` 为中心展宽：SPA 群的半高全宽为 $\tau$，TPA 群为 $\tau/\sqrt{2}$，因为 $P^2(t)$ 是宽度缩小 $\sqrt{2}$ 的高斯。由 `LaserInjection` 实现。吸收系数表 `Si.txt` 取自文献 [7]。

式 (7a) 与文献 [16] 的式 (3) 差一个因子：原文在求和之外除以 $\hbar\omega$，按原文的参数算出的吸收比原文自己的图 4（$75\ \text{K}$）低 $\hbar\omega \approx 3.3$ 倍，去掉这个除数后与图 4 一致，与文献 [17] 的 $300\ \text{K}$ 实测相比，$353$–$364\ \text{nm}$ 相差不到 $10\%$（$355\ \text{nm}$：$225$ 对 $210\ \text{cm}^{-1}$），$336\ \text{nm}$ 高 $21\%$，$369\ \text{nm}$ 低 $26\%$；更长的波长上文献 [17] 停在约 $13\ \text{cm}^{-1}$ 的测量下限，文献 [16] 测到 $0.02\ \text{cm}^{-1}$。原文参数只拟合到 $\hbar\omega = 3.8\ \text{eV}$，波长短于 $326\ \text{nm}$ 时 `absorption_coefficient` 报错，要求在激光文件里给 `alpha`。$300\ \text{K}$ 下 $375\ \text{nm}$ 的 $\alpha = 9.05\ \text{cm}^{-1}$；最低阈值 $E_{GX} - \hbar\Omega_7 = 3.126\ \text{eV}$（约 $397\ \text{nm}$），更长的波长没有带间吸收，$\alpha = 0$，缺陷的吸收须在激光文件里给 `alpha`。

局限：只用了 $E \perp c$ 的一组参数，适用于在 $c$ 面晶圆上从顶面或底面入射；侧面入射时偏振可能平行于 $c$ 轴，文献 [16] 表 II 的那组参数没有接入。不计掺杂对带边的影响，文献 [16] 测的是名义未掺杂的外延层。

### 放射源

放射源每个事例是一个静止核素的一次衰变。核素在 `nuclides` 中等概率抽取，位置在垂直于发射轴的圆盘上均匀分布。衰变产物的起始时刻置零，衰变留下的子核在此截断，一个事例是一次衰变。给了 `par_cone` 时，衰变产物的方向在绕发射轴的圆锥内各向同性重抽：

$$\hat{\mathbf{a}} = \frac{\mathbf{r}_{\text{out}} - \mathbf{r}_{\text{in}}}{|\mathbf{r}_{\text{out}} - \mathbf{r}_{\text{in}}|}, \qquad |\mathbf{r}_0 - \mathbf{r}_{\text{in}}| \le R, \quad (\mathbf{r}_0 - \mathbf{r}_{\text{in}}) \perp \hat{\mathbf{a}} \tag{14}$$

$$\cos\theta = 1 - u_1\,(1 - \cos\theta_c), \qquad \varphi = 2\pi u_2, \qquad \hat{\mathbf{d}} = \cos\theta\,\hat{\mathbf{a}} + \sin\theta\,(\cos\varphi\,\hat{\mathbf{e}}_1 + \sin\varphi\,\hat{\mathbf{e}}_2) \tag{15}$$

$$f = \frac{1 - \cos\theta_c}{2} \tag{16}$$

其中：

- $\mathbf{r}_{\text{in}}, \mathbf{r}_{\text{out}}$：源位置与沿发射轴的瞄准点（世界坐标原点在源上，未转动时 $\mathbf{r}_{\text{in}} = (0, 0, 0)$，发射轴 $\hat{\mathbf{a}}$ 沿 $+z$ 指向下游），$\mu\text{m}$；$\hat{\mathbf{a}}$：发射轴单位矢量；
- $\mathbf{r}_0$：核素位置，$\mu\text{m}$；$R$：圆盘半径 `par_radius`，$\mu\text{m}$（$R = 0$ 时为点源）；
- $\hat{\mathbf{e}}_1, \hat{\mathbf{e}}_2$：与 $\hat{\mathbf{a}}$ 正交的单位矢量；
- $\theta_c$：半锥角 `par_cone`，度；$u_1, u_2$：$[0, 1)$ 上的均匀随机数；
- $\hat{\mathbf{d}}$：衰变产物的出射方向；
- $f$：圆锥占全部方向的比例，写作文件属性 `generated_fraction`。

核素由 `NuclideGeneratorAction`（`G4GeneralParticleSource`，动能 $0$）产生，时间置零、子核截断和圆锥方向由 `DecayStackingAction` 完成，判据是轨迹的产生过程子类型为 `RADIOACTIVE_DECAY = 210`。代码注释说明：Geant4 自带的 `/process/had/rdm/decayHalfAngle` 只能绕 $z$ 轴，所以自己实现。Geant4 放射性衰变见文献 [5]。

### 沿束流的一列

装置用 `along_beam` 描述沿束流方向的一列几何：第一项必须是 `"source"`，世界坐标原点 $(0, 0, 0)$ 在源上，$z$ 轴沿束流指向下游。列中其余项依次为间隔 `{"gap": d}`（$d \ge 0$，$\mu\text{m}$）、`object` 中的物体（`"<物体名>"` 或 `{"object": "<物体名>", "offset": [o_x, o_y]}`，沿 $z$ 占 `side_z`）、器件槽位 `{"slot": "<槽位名>", ...}`（沿 $z$ 占器件几何全部层的总厚度 $l_z + t$，见 [探测器组件](../components/device.md)，没有灵敏层以外各层时 $t = 0$），或前端面对齐在同一个 $z$、靠各自 `offset` 横向错开的并排列表 `[项, 项, ...]`（沿 $z$ 占其中最厚一项的厚度）。相邻两项之间不写 `gap` 就是贴在一起；源的厚度为 $0$，第 $i$ 项的前端面 $z_i$ 等于它前面所有项的厚度与间隔之和，槽位前表面中心 $\mathbf{P} = (P_x, P_y, P_z)$ 与器件坐标 $(x, y, z)$（原点在器件前表面一角，有源层占据 $[0, l_x] \times [0, l_y] \times [0, l_z]$）到 Geant4 世界坐标 $\mathbf{r}_{\text{G4}}$ 的变换为：

$$z_i = \sum_{j < i} d_j, \qquad \mathbf{P} = \begin{cases} \bigl(o_x,\ o_y,\ z_i\bigr), & \texttt{facing} = \texttt{"upstream"} \\ \bigl(o_x,\ o_y,\ z_i + l_z + t\bigr), & \texttt{facing} = \texttt{"downstream"} \end{cases} \tag{17}$$

$$\mathbf{r}_{\text{G4}} = \begin{cases} \mathbf{P} + \begin{pmatrix} \cos\phi & -\sin\phi & 0 \\ \sin\phi & \cos\phi & 0 \\ 0 & 0 & 1 \end{pmatrix} \begin{pmatrix} x - l_x/2 \\ y - l_y/2 \\ z \end{pmatrix}, & \texttt{facing} = \texttt{"upstream"} \\[4ex] \mathbf{P} + \begin{pmatrix} \cos\phi & -\sin\phi & 0 \\ \sin\phi & \cos\phi & 0 \\ 0 & 0 & 1 \end{pmatrix} \begin{pmatrix} -(x - l_x/2) \\ y - l_y/2 \\ -z \end{pmatrix}, & \texttt{facing} = \texttt{"downstream"} \end{cases} \tag{18}$$

其中：

- $d_j$：第 $j$ 项沿 $z$ 轴占据的厚度或间隔（`"source"` 取 $0$，`{"gap": d}` 取 $d$，物体取 `side_z`，槽位取 $l_z + t$，并排列表取其中各项厚度的最大值），$\mu\text{m}$；$z_i$：第 $i$ 项前端面的世界 $z$ 坐标，$\mu\text{m}$；
- $o_x, o_y$：槽位的 `offset`（缺省 `[0, 0]`），$\mu\text{m}$；
- $l_z$：该槽位器件的有源层厚度，$\mu\text{m}$；$t$：灵敏层以外各层的总厚度，$\mu\text{m}$（没有这些层时 $t = 0$）；
- $\mathbf{P} = (P_x, P_y, P_z)$：器件前表面（器件坐标 $z = 0$ 的面）中心的世界坐标，$\mu\text{m}$；
- $\phi$：槽位的 `rotation_z`，度，只取 `0`、`90`、`180`、`270`；$l_x, l_y$：该槽位器件的横向尺寸，$\mu\text{m}$。

`facing` 为 `"upstream"`（缺省）时，有源层占 $[z_i,\ z_i + l_z]$、灵敏层以外的各层占 $[z_i + l_z,\ z_i + l_z + t]$，器件前表面在 $P_z = z_i$ 朝源，器件坐标的 $z$ 轴沿 $+z$；把槽位写在板前面且中间不留间隔，器件的衬底等外层就贴在板朝源的一面、有源层在外侧。`facing` 为 `"downstream"` 时，器件绕 $y$ 轴翻转 $180^\circ$（$\phi = 0$ 时即 $x_{\text{G4}} = P_x - (x - l_x/2)$、$y_{\text{G4}} = P_y + (y - l_y/2)$、$z_{\text{G4}} = P_z - z$），灵敏层以外的各层占 $[z_i,\ z_i + t]$、有源层占 $[z_i + t,\ z_i + t + l_z]$，器件前表面在 $P_z = z_i + l_z + t$ 朝下游；把槽位写在板后面并写 `"facing": "downstream"`，衬底就贴在板背源的一面、有源层在外侧。两块板相对的两面各贴一块器件时（前一块板后写 `"downstream"` 槽位、后一块板前写 `"upstream"` 槽位，中间用 `{"gap": g}` 分隔），两块器件的有源层相向，间距就是中间那个 `gap`。世界立方体以这一列的中点为中心，半边长取这一列总长的一半、各项横向半尺寸加偏移、源圆盘半径中的最大值 $\rho$ 在 $\rho \le 25000\ \mu\text{m}$ 时为 `25000` $\mu\text{m}$，否则为 $2\rho$。

### 多器件的记录条件

多器件实验中，粒子未必击中所有需要触发的器件。在 `timeres` 默认装置（Sr-90 源，被测器件 `HPK-Si-PiN`）上，每次 Geant4 衰变约 `0.18 ms`；下游漂移、读出、重建每个记录事例约 `0.2 s`；被测器件有沉积的事例里约四分之三参考器件没有沉积，真实测量中不触发。因此在 `deposit` 阶段就按符合条件预筛选，只记录满足条件的有效事例，避免为不触发的事例运行耗时的下游环节。

槽位 $s$ 在一个事例里“命中”定义为该槽位有源层内总沉积能量 $E_s > 0$ 且落在它的能量窗 $[E_{s,\min},\ E_{s,\max}]$ 内（`None` 表示该侧不检查），命中时刻 $t_s$ 取该槽位有源层内最早一个沉积步的全局时间；逻辑式 `require` 的语法与求值定义见 [符合条件](../components/trigger.md#符合条件)——操作数是槽位名，运算是 `AND`、`OR` 和括号，`"all"` 是全部槽位相与的简写，`"any"` 是全部槽位相或的简写，`deposit` 的命中判据是上面的能量判据，`trigger` 的命中判据是过幅度阈值。加上符合时间窗 `coincidence_window_ns`（记为 $W$）后，存在某个时刻 $t_0$，只把命中时刻落在 $[t_0,\ t_0 + W]$ 内的槽位算作命中时逻辑式为真，事例才记录：

$$h_s = \mathbb{I}\bigl(E_s > 0,\ E_{s,\min} \le E_s \le E_{s,\max}\bigr), \qquad t_s = \min_{k \in \mathcal{K}_s} t_{s,k} \tag{19}$$

$$h_s(t_0) = h_s \cdot \mathbb{I}\bigl(t_0 \le t_s \le t_0 + W\bigr), \qquad \exists\, t_0 \in \mathbb{R}:\ \mathcal{F}\bigl(\{h_s(t_0)\}_{s \in \mathcal{S}}\bigr) = \texttt{true} \tag{20}$$

其中：

- $s \in \mathcal{S}$：槽位名，$\mathcal{S}$ 为装置全部槽位集合；
- $\mathcal{K}_s$：槽位 $s$ 有源层内的沉积步集合，$E_s = \sum_{k \in \mathcal{K}_s} E_{s,k}$ 为总沉积能量，$\text{MeV}$；
- $E_{s,\min}, E_{s,\max}$：槽位 $s$ 能量窗的下限与上限，$\text{MeV}$（未给的一侧不检查）；
- $h_s \in \{0, 1\}$：不计时间窗时槽位 $s$ 的命中标志；
- $t_{s,k}$：槽位 $s$ 第 $k$ 个沉积步的全局时间，$\text{s}$；$t_s$：槽位 $s$ 最早一个沉积步的全局时间，$\text{s}$；
- $W$：符合时间窗 `coincidence_window_ns`，输入单位 $\text{ns}$（与 $t_s$ 比较时换算为 $W \times 10^{-9}\ \text{s}$；为 `None` 时不卡时间，直接令 $h_s(t_0) = h_s$）；
- $t_0$：时间窗左端点，$\text{s}$；
- $h_s(t_0) \in \{0, 1\}$：在时间窗 $[t_0,\ t_0 + W]$ 内槽位 $s$ 的命中标志；
- $\mathcal{F}$：由 `require` 解析得到的布尔函数。

`deposit` 的 `coincidence_window_ns` 不得窄于 `trigger` 的符合窗加上漂移与成形的时间，否则会筛掉 `trigger` 本会留下的事例。单槽位时条件就是器件内总沉积 $> 0$ 且在窗内。某槽位在某事例里没有命中时，这个槽位在该事例里没有沉积步；下游 `current.<槽位>` 不为它写这个事例。

## 算法

### 内置常数

| 常数 | 取值 | 单位 | 位置与含义 | 文件里的键 |
| --- | --- | --- | --- | --- |
| `PAIR_ENERGY_EV` | Si `3.6`，SiC `7.83`，Diamond `13.1` | $\text{eV}$ | `ionization.py`，式 (1) 的 $\varepsilon$ | 无 |
| `FANO_FACTOR` | Si `0.115`，SiC `0.128`，Diamond `0.382` | 无 | `ionization.py`，式 (2) 的 $F$ | 无（开关 `deposit.fano` 是环节设置） |
| `PAIRS_PER_UM` | Si `80.0`，SiC `55.0` | $\mu\text{m}^{-1}$ | `mip_track.py`，式 (4) 的 $n_{\text{MIP}}$ | 无 |
| `LANDAU_WIDTH_MEV_PER_UM` | Si `1.78e-5`，SiC `2.46e-5` | $\text{MeV}/\mu\text{m}$ | `mip_track.py`，式 (5) 的 $w$ | 无 |
| `GENERATED_LIMIT` | `10_000_000` | 事例 | `generation.py`，按记录数运行时最多生成的事例数 | 无（环节设置 `deposit.generated_limit`） |
| `DEVICE_ALONE` | 见下文“装置” | — | `simulate_deposits.py`，未给装置时的装置 | 由 `deposit.g4setup` 整体替换 |
| `WORLD_HALF_SIDE` | `25000` | $\mu\text{m}$ | `simulate_deposits.py`，世界立方体的缺省半边长 | `gdml_import` 下的 `world_half_size_um` |
| 物理表 | `FTFP_BERT` + `G4StepLimiterPhysics` | — | `geant4/interaction.py` | 无 |
| 放射性衰变时间阈值 | `1.0e60` | 年 | `geant4/interaction.py` | 无 |
| 随机引擎 | `CLHEP::RanecuEngine`，种子为 `deposit` 环节的种子（由作业的种子派生） | — | `geant4/interaction.py` | 无 |
| 器件密度 | Diamond `3.52`，SiC `3.21`（Si:C 原子数 `50:50`） | $\text{g/cm}^3$ | `geant4/detector_construction.py` | 无 |
| `RADIOACTIVE_DECAY` | `210` | — | `geant4/nuclide_source.py`，放射性衰变的过程子类型 | 无 |
| $h$, $c$ | `6.626e-34`, `2.998e8` | $\text{J}\cdot\text{s}$, $\text{m/s}$ | `laser.py`，式 (8) | 无 |
| 4H-SiC 吸收模型参数 | 见式 (7a)、(7b) 的变量说明 | — | `laser.py`，文献 [16] 表 I 与式 (5) | 无 |
| 环数、扇区数 | `4`, `8` | 个 | `laser.py`，激光横截面的划分 | 无 |
| 光路采样密度 | 每个最细尺度 `50` 点 | — | `laser.py`，见“激光载流子群” | 无 |

### `simulate_deposits` 的分支

`simulate_deposits(devices, source, g4setup, events, g4_seed, windows, require, coincidence_window_ns, fano, generated, generated_limit, picture, drawn)` 按以下顺序执行。`devices` 是槽位名到器件的有序字典；`windows` 是槽位名到 `(下限, 上限)`（$\text{MeV}$，`None` 表示该侧不检查）的映射；`require` 是符合条件的逻辑式字符串；`coincidence_window_ns` 是符合时间窗（$\text{ns}$，`None` 表示不卡时间）。未给装置时取 `DEVICE_ALONE`，等同于 `"along_beam": ["source", {"gap": 17000}, {"slot": "Device"}]`；只有一块器件的装置槽位名写 `"Device"`、传 `{"Device": my_d}`。装置的槽位名与 `devices` 参数的槽位名必须一一对上，多了、少了都抛 `ValueError`（`the g4setup places <装置的槽位>, the devices are <给的槽位>`）；各槽位在输出中的顺序以 `devices` 参数为准。

1. **检查源的类型**：`source["kind"]` 不是 `"toy_mip"`、`"beam"`、`"decay_source"` 之一时抛 `ValueError`（`no simulation of deposits for a source of kind ...`）。
2. **检查事例数与记录条件**：
   - `asked(events, generated, generated_limit)` 要求 `events`（要记录的事例数）与 `generated`（要生成的事例数）恰好给一个，否则抛 `ValueError`；给出的数和 `generated_limit` 小于 `1` 时抛 `ValueError`（`the <name> asked for are <number>: at least 1`）。
   - 校验记录条件参数，任一不合法即抛 `ValueError`：`windows` 的槽位名与 `devices` 不一致（`the energy windows are for <windows 的槽位>, the devices are <给的槽位>`）；某槽位下限大于上限（`slot '<槽位>' has edep_min (<lo> MeV) > edep_max (<hi> MeV)`）；`require` 语法错误或出现不是槽位名的操作数（`invalid require expression '<require>'` 或 `require '<require>' names unknown slot '<操作数>'`）；`coincidence_window_ns` 非 `None` 且不大于 `0`（`coincidence_window_ns must be positive, got <值> ns`）。
3. **toy MIP 分支**（`kind == "toy_mip"`）：取 `g4setup["maxstep"]`（`g4setup` 为 `None` 时取 `DEVICE_ALONE["maxstep"] = 2`），调用 `mip_deposits(devices, source, g4setup, ...)`，见下节。这一支由 Python 完成，随机数取自流 `stream("toy_mip")`。
4. **Geant4 分支**（`kind` 为 `"beam"` 或 `"decay_source"`）：
   1. 导入 `geant4.interaction`。缺 `g4ppyy` 时抛 `MissingDependency`（`Geant4's Python bindings, g4ppyy, are not installed in this Python`）。
   2. `g4_configuration` 合成运行配置：源或其 `particles` 中出现 `par_in`、`par_out`、`par_angle` 时抛 `ValueError`（源的位置属于装置）；取 `g4setup`（`None` 时取 `DEVICE_ALONE`）的深拷贝，取出可选的 `"source"` 块（缺省 `{}`）；用源的键覆盖装置的同名键，删去 `name`、`kind`、`description`；源在世界坐标原点且沿 $+z$ 指向下游，令 `par_in = [0, 0, 0]`、`par_out` 为第一个槽位前表面所在的 $z$ 处、轴上的点 `[0, 0, z_i]`、`par_angle = source.get("angle", 0)`。有 `particles` 时，每项先取配置里的 `par_randx`、`par_randy`、`par_type`、`par_energy`，再用自己的键覆盖，发射点与瞄准点各加 `offset`（缺省 `[0, 0, 0]` $\mu\text{m}$）。最后写入 `recorded_events = events`、`total_events = generated`（按记录数运行时为 `generated_limit`）、`windows`、`require`、`coincidence_window_ns`。
   3. `tilted` 按入射角转动源：`par_angle` 为 `0` 时不变。多槽位装置而 `par_angle` 不为 `0` 时抛 `ValueError`（`a multi-slot g4setup tilts no source`）。否则只用于单槽位装置：记 $\mathbf{r}_{\text{in}} = (x_0, y_0, z_0)$、$\mathbf{r}_{\text{out}} = (x_1, y_1, z_1)$；若 $z_f \le z_0 \le z_f + l_z + t$ 或 $z_1 = z_0$，抛 `ValueError`（源连线不从器件表面进入）。取转轴在单槽位器件前表面中心 $(x_p, P_y, z_f) = (P_x, P_y, P_z)$ 且平行于 $y$ 轴，对配置及各 `particles` 的 `par_in`、`par_out` 作
      $$x' = (x - x_p)\cos\vartheta + (z - z_f)\sin\vartheta + x_p, \qquad z' = -(x - x_p)\sin\vartheta + (z - z_f)\cos\vartheta + z_f$$
      其中 $\vartheta$ 为 `par_angle`（度）。$\vartheta > 0$ 时，上游的源转到 $-x$ 一侧，粒子带 $+x$ 分量射向器件前表面中心。$y$、`par_randx`、`par_randy` 不变，装置里的槽位与物体不动。
   4. 构建几何（`GeneralDetectorConstruction`；`geant4_model == "gdml_import"` 时用 `GDMLDetectorConstruction`，几何由 GDML 给出，不用 `along_beam`）。先校验 `along_beam` 与 `object`（不合法均抛 `ValueError`）：第一项不是 `"source"`（`the first item of along_beam must be 'source'`）；`gap` 为负（`gap must be non-negative`）；物体名不在 `object` 里（`object '<物体>' is not in object`）；同一物体或槽位出现两次（`duplicate '<名称>' in along_beam`）；`facing` 取值不是 `"upstream"` 或 `"downstream"`（`slot '<槽位>' has facing <值>: expected 'upstream' or 'downstream'`）；`rotation_z` 不是 `0`、`90`、`180`、`270`；并排的几项横向重叠（`side-by-side items overlap`）；槽位名与 `devices` 参数对不上（`the g4setup places <装置的槽位>, the devices are <给的槽位>`）。世界是 `world` 材料的立方体，中心在 `along_beam` 一列的中点 $(0, 0, L_{\text{col}}/2)$，半边长由 `world_half_side` 给出：令 $\rho = \max\bigl(L_{\text{col}}/2,\ \max_{\text{项}}(|o_x| + w_x/2,\ |o_y| + w_y/2),\ R\bigr)$，其中 $L_{\text{col}} = \sum_j d_j$ 为这一列的总长度，$w_x, w_y$ 为各项（物体或槽位旋转后的）横向全尺寸，$o_x, o_y$ 为 `offset`，$R$ 为 `par_radius`；$\rho \le 25000\ \mu\text{m}$ 时取 `25000`，否则取 $2\rho$。从 `"source"`（$z = 0$）起按式 (17) 算出各项前端面位置 $z_i$：每个槽位建一个以槽位名命名、材料按该槽位器件 `material` 取的有源层长方体逻辑体（$l_x \times l_y \times l_z$），按式 (17)–(18) 放置；器件的各层厚度和材料是器件的固有性质，写在器件文件里，Geant4 用同一份几何（见 [架构总纲](../architecture.md#组件)），参考器件的衬底在射线路径上，它引起的多次散射决定有多少粒子能到达下游器件。器件几何按深度分层，灵敏层以外的各层（衬底等）见 [探测器组件](../components/device.md)；Geant4 按器件几何建出全部层，灵敏层以外的各层各建一个逻辑体，其中的沉积不记录，只记录灵敏层里的沉积。随后按 `along_beam` 放置引用的 `object` 物体（中心横向在 `offset`，中心 $z$ 在 $z_i + \texttt{side\_z}/2$）。同一 `compound_name` 的二元化合物组分或密度不一致时抛 `ValueError`（`Conflicting Geant4 material definition for ...`）。二元化合物按原子数份额换算质量份额 $m_i = n_i A_i / (n_1 A_1 + n_2 A_2)$。
   5. 设置随机引擎、物理表与用户动作。源含 `nuclides` 时用 `NuclideGeneratorAction` 与 `DecayStackingAction`，否则用 `GeneralPrimaryGeneratorAction`。后者每事例对每个粒子从流 `stream("source")` 抽 $\delta_x \sim U(-\texttt{par\_randx}, \texttt{par\_randx})$、$\delta_y \sim U(-\texttt{par\_randy}, \texttt{par\_randy})$，方向取 $\mathbf{d} = \mathbf{r}_{\text{out}} - \mathbf{r}_{\text{in}} + (\delta_x, \delta_y, 0)$，从 $\mathbf{r}_{\text{in}}$ 发射；`par_type` 为列表时再抽一个等概率的下标。`par_type` 与 `par_energy` 列表长度不等时抛 `ValueError`。
   6. 执行 `/run/initialize`；给了 `picture` 且 `drawn > 0` 时打开离屏绘图（见“图”）；`BeamOn(total_events)`。
   7. 事例记录：事例结束时，按式 (19) 对每个槽位 $s$ 计算有源层内总沉积 $E_s$：若 $E_s > 0$ 且满足 `windows[s]`（`None` 一侧不检查），记该槽位命中（$h_s = 1$）并取该槽位最早一个沉积步的全局时间为 $t_s$；否则未命中（$h_s = 0$）。不卡时间窗（`coincidence_window_ns` 为 `None`）时直接用 $\{h_s\}$ 对 `require` 求值；否则依次以各命中槽位的 $t_s$ 作左端点 $t_0$，按式 (20) 将命中时刻落在 $[t_0, t_0 + W]$ 内的槽位算作命中并对 `require` 求值，存在令 `require` 为真的 $t_0$ 时记下该事例。对该事例内未命中的槽位不保留其沉积步。按记录数运行时，记录数达到 `recorded_events` 即 `AbortRun`；生成事例数 `generated_events` 取已结束的事例数。按生成数运行时 `generated_events = total_events`。
   8. `deposits()`：按记录数运行而记录数仍少于 `recorded_events` 时抛 `RuntimeError`（`... events asked for were recorded when the limit of ... generated events was reached ...`）。否则把各步位置由 Geant4 世界坐标按所在槽位式 (18) 的逆变换换到该槽位器件的器件坐标；对每块器件用 `deposits_of_steps(<槽位名>, ...)` 去掉 $E_k \le 0$ 的步（未命中的槽位在该事例里没有沉积步），一个事例的各器件沉积步按 `devices` 的顺序首尾相接，去掉没有剩余步的事例。事例号是 Geant4 的 `eventID`。
   9. 无论是否出错，最后调用 `close()` 释放 Geant4 对象。
5. **写入源发射比例**：`generated_fraction(source)`：源含 `nuclides` 且 `par_cone` 非 `None` 时为式 (16)，否则为 `1.0`。
6. **电离**：对每个事例调用 `ionized_pairs(event, material, fano)`，每一步的 `material` 取它所在槽位器件的 `material`。材料不在 `PAIR_ENERGY_EV` 中时抛 `ValueError`；`fano=True` 而材料不在 `FANO_FACTOR` 中时抛 `ValueError`。每个事例从自己的流 `stream(f"ionization/{event.event}")` 抽样，所以一个事例的对数与其前记录了哪些事例无关。

`write_simulated_deposits` 与 `simulate_deposits` 接收同样的 `devices`、`source`、`g4setup`、`events`、`g4_seed`、`windows`、`require`、`coincidence_window_ns` 等参数，调用 `simulate_deposits` 后用 `write_deposits` 写文件，返回记录事例数。

GDML 导入模式按 `material` 为 `"Si"`（`G4_Si`）和 `"SiC"`（Si、C 原子数各半，$3.21\ \text{g/cm}^3$）建器件逻辑体 `"Device"`。

### 能损线切成沉积步

**Geant4**：步长由 Geant4 决定，器件内不超过 `maxstep`（式 (3)）。`GeneralSteppingAction` 对前点逻辑体名为槽位名（单器件为 `"Device"`）的每一步调用 `RecordDevice`：按逻辑体名分开记录，累加 $E_{\text{tot}}$，记下步中点 $\frac{1}{2}(\mathbf{r}^{\text{pre}} + \mathbf{r}^{\text{post}}) \times 1000$（Geant4 的 $\text{mm}$ 换成 $\mu\text{m}$）、前点 $\mathbf{r}^{\text{pre}} \times 1000$（写作 `x_start` 等）、沉积能量（$\text{MeV}$）和前点的全局时间（$\text{s}$）。

**toy MIP**（`mip_deposits`）：

1. 源含 `_SOURCE_KEYS`（`name`、`kind`、`description`、`start`、`end`、`position_range_um`、`direction_sigma_mrad`、`packets`、`landau_sampling`）以外的键时抛 `ValueError`；缺 `landau_sampling` 时抛 `ValueError`；材料不在 `PAIRS_PER_UM` 中时抛 `ValueError`。
2. 由 `generation(events, generated, generated_limit, recorded)` 给出事例号 $0, 1, \dots$：按生成数运行时共 `generated` 个；按记录数运行时生成到记录数等于 `events` 为止，生成数达到 `generated_limit` 仍不够时抛 `RuntimeError`。全部抽样用同一条流 `stream("toy_mip")`。
3. 每个事例的径迹端点（`_track_ends`）：起点缺省 $(l_x/2, l_y/2, 0)$，终点缺省 $(l_x/2, l_y/2, l_z)$。有 `position_range_um` 时依次抽 $x_s \sim U(x_{\text{lo}}, x_{\text{hi}})$、$y_s \sim U(y_{\text{lo}}, y_{\text{hi}})$（`"x"`、`"y"` 两项都要给）。有 `direction_sigma_mrad` 时，对 `"x"`、`"y"` 中 $\sigma > 0$ 的分量抽斜率 $k_u \sim \mathcal{N}(0, (10^{-3}\sigma_u)^2)$。抽过起点或斜率时，终点横坐标改为 $u_e = u_s + k_u (z_e - z_s)$。
4. 段数 $n$：给了 `packets` 时取 `int(packets)`，否则 $n = \lceil L / \texttt{maxstep} \rceil$，$L$ 为起点到终点的距离（$\mu\text{m}$）。每段长度 $\Delta l = L/n$，按式 (5) 依次抽各段能量。
5. 事例总能量 $\sum_k E_k$ 不大于 `0` 或不在 `windows["Device"]` 内时不记录。toy MIP 保留能量为 $0$ 的段。
6. 第 $k$ 段（$k = 0, \dots, n-1$）的位置取段中点 $\mathbf{r}_s + \frac{k + 0.5}{n}(\mathbf{r}_e - \mathbf{r}_s)$，起点 $\mathbf{r}_s + \frac{k}{n}(\mathbf{r}_e - \mathbf{r}_s)$，时刻 $0.0\ \text{s}$，探测器名 `"Device"`。
7. 返回 `Deposits(generated_events = 最后一个事例号 + 1, ...)`。

多槽位装置时，径迹在 Geant4 世界坐标中穿过全部槽位，第 3、4、6 步换成下面的做法，其余不变：

- 源含 `start`、`end`、`position_range_um` 时抛 `ValueError`（多槽位时径迹从装置的源出发）。
- 起点 $\mathbf{r}_s$ 取源所在的世界原点 $(0, 0, 0)$，方向沿 $+z$（`[0, 0, 1]`）；有 `direction_sigma_mrad` 时按第 3 步抽斜率，作为方向的 $dx/dz$、$dy/dz$（方向向量为 $(k_x, k_y, 1)$）。
- 对 `devices` 的每个槽位，取径迹在槽位有源层 $z$ 区间（`"upstream"` 时为 $[P_z,\ P_z + l_z]$，`"downstream"` 时为 $[P_z - l_z,\ P_z]$）内的一段，长度 $L$ 按第 4 步分段，每段中点和起点按式 (18) 的逆变换换到该槽位的器件坐标，横向落在 $[0, l_x] \times [0, l_y]$ 以外的段舍去，探测器名为槽位名，时刻 $0.0\ \text{s}$。
- 第 5 步按式 (19)–(20) 对各槽位能量窗 `windows`、`require` 与 `coincidence_window_ns` 判选记录（所有命中槽位时刻均为 $0.0\ \text{s}$）；只保留命中槽位的段并按 `devices` 的顺序首尾相接，未命中槽位在该事例里没有沉积步。

### 激光载流子群

`LaserInjection(my_d, laser_dic)` 读入激光键（见“接口”）。未给 `alpha` 时：器件材料为 `"SiC"` 时按式 (7a)、(7b) 以器件的 `temperature` 计算，$\hbar\omega > 3.8\ \text{eV}$ 时抛 `ValueError`；其他材料按式 (7) 查表，组件里没有 `deposit/absorption/<material>.txt` 时抛 `ValueError`，$10^3\lambda$ 小于表的最短波长时抛 `ValueError`，大于最长波长时 $\alpha = 0$。然后先在 $\alpha \ne 0$ 时用 $k = 2$、展宽 $\tau$ 加 SPA 群，再在 `tech == "TPA"` 时用 $k = 4$、展宽 $\tau/\sqrt{2}$ 加 TPA 群。`tech` 不是 `"SPA"`、`"TPA"` 时在加完 SPA 群之后抛 `NameError(tech)`。每次加群（`_add_groups`）的步骤：

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
4. 打开驱动（`register_driver` 为 g4ppyy 补注册 `TSG_OFFSCREEN`、`TSG_QT_GLES`、`OGL`、`VRML2FILE`、`ATREE`）。TSG 且给了 `output` 时设 PNG 输出 `<output>.png`。`gdml_import` 执行组件 `deposit/vis_pcb.mac`，否则执行 `deposit/init_vis.mac` 与 `deposit/vis.mac`；宏不在组件路径中时抛 `FileNotFoundError`。OGL 且给了 `output` 时设白底、矢量打印、`2000 × 2000`、文件名 `output`。
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
- `Deposits`：一个作业的沉积。`generated_events`（源生成的事例数）、`windows`（槽位名到 `(edep_min, edep_max)` 的字典，$\text{MeV}$，各侧可为 `None`）、`require`（符合条件逻辑式字符串）、`coincidence_window_ns`（符合时间窗，$\text{ns}$，可为 `None`）、`events`（`EventDeposits` 列表）、`generated_fraction`（缺省 `1.0`）。
- `LaserInjection`：`track_position`（每群 `[x, y, z, t]`，$\mu\text{m}$、$\text{s}$）、`ionized_pairs`（每群对数）、`time_FWHM`（每群时间展宽，$\text{s}$），以及 `temporal_FWHM`、`timePulse` 等供电流卷积使用的属性。

## 接口

使用者能设的是下表中器件文件、装置脚本、放射源和束流文件、激光文件里的键；页内其余参数写死在代码里。事例数、能量窗、`deposit.fano` 与绘图事例数 `deposit.plots` 是 `deposit` 段的设置，见 [能量沉积环节](../stages/deposit.md)。

### 器件文件读取的键

| 键 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `l_x`, `l_y`, `l_z` | 无（必选） | $\mu\text{m}$ | 器件有源层尺寸，见 [器件模型](device.md) |
| `material` | 无（必选） | 无 | `"Si"`、`"SiC"` 或 `"Diamond"`；决定 Geant4 材料、电离能与 Fano 因子；toy MIP 只支持 `"Si"`、`"SiC"` |
| `temperature` | 无（`"SiC"` 器件的激光未给 `alpha` 时必选） | $\text{K}$ | 式 (7b) 的 $T$ |

器件几何按深度分层，灵敏层以外的各层（衬底等）见 [探测器组件](../components/device.md)；Geant4 按器件几何建出全部层，只记录灵敏层里的沉积。

### 装置

装置是 `components/deposit/` 下 `<名称>.py` 脚本里的字典 `G4SETUP`，未给装置时用 `DEVICE_ALONE`（除 `name`、`description` 外与 `device_alone.py` 相同）。

#### `G4SETUP` 顶层键

| 键 | 默认值（`DEVICE_ALONE`） | 单位 | 含义 |
| --- | --- | --- | --- |
| `name`, `description` | 无（可选） | 无 | 装置名与说明；`name` 只出现在报错信息里 |
| `geant4_model` | `"device"` | 无 | Geant4 源必填；取 `"gdml_import"` 时导入外部 GDML，其他取值只作标识 |
| `world` | `"G4_Galactic"` | 无 | Geant4 源必填；世界体的 NIST 材料名 |
| `maxstep` | `2` | $\mu\text{m}$ | 必填；器件内 Geant4 的最大步长，也是 toy MIP 未给 `packets` 时的分段长度上限 |
| `source` | `{"angle": 0}` | 度 | 可选；只留 `angle`（入射角，缺省 `0`），只用于单槽位装置：绕器件前表面中心按“`simulate_deposits` 的分支”第 4.3 步转动源；束流源发射方向为 $+z$ |
| `object` | `{}` | 无 | Geant4 源必填；周边物体，可含 `"elemental"` 和 `"binary_compounds"` 两类，各物体只定义材料、尺寸、孔与颜色，在 `along_beam` 中放置 |
| `par_type`, `par_energy`, `par_randx`, `par_randy` | 无 | 见源 | 可选；装置可给这些束流键，源里的同名键覆盖它们 |
| `along_beam` | `["source", {"gap": 17000}, {"slot": "Device"}]` | 无 | 必填（`gdml_import` 除外）；从 `"source"` 开始沿 $+z$ 指向下游的一列，按式 (17)–(18) 放置器件槽位与周边物体，见下表 |

Geant4 世界坐标原点 $(0, 0, 0)$ 在源上，$+z$ 沿束流指向下游；各槽位前表面中心 $\mathbf{P}$ 与有源层、灵敏层以外各层（见 [探测器组件](../components/device.md)）所占的 $z$ 区间由它在 `along_beam` 中的位置与 `facing` 按式 (17)–(18) 定出。

#### `along_beam` 的各项

`along_beam` 是从 `"source"` 出发、沿 $+z$ 依次排列的列表，各项的种类与键如下表。槽位名同时是有源层 Geant4 逻辑体名（灵敏层以外的各层各建一个逻辑体，其中的沉积不记录）和沉积文件的探测器名，只用 `[A-Za-z0-9_-]` 中的字符，不能与 `object` 里的名字或 [能量沉积环节](../stages/deposit.md) 的配置键重名（槽位名会出现在 `deposit.<槽位>.<键>` 这样的地址里）；只有一块器件的装置，槽位名写 `"Device"`。每个槽位放哪块器件不由装置给，由调用方的 `devices` 参数给，装置的槽位名与 `devices` 一一对上（见“`simulate_deposits` 的分支”）。

```python
"along_beam": [
    "source",
    {"gap": 1995}, "Al",
    {"gap": 4978.5},
    {"slot": "ref"}, "pcb1",
    {"gap": 8183.5},
    {"slot": "dut"}, "pcb2",
]
```

| 项的种类 | 键 | 缺省 | 单位 | 含义 |
| --- | --- | --- | --- | --- |
| `"source"` | 无（字符串） | 无（首项必填） | 无 | 源，必须位于 `along_beam` 第一项，厚度为 `0`，世界坐标原点在其上 |
| `{"gap": d}` | `gap` | 无 | $\mu\text{m}$ | 间隔，沿 $z$ 占长度 $d \ge 0$；相邻两项之间不写 `gap` 即紧贴在一起 |
| `"<物体名>"` 或 `{"object": "<物体名>", ...}` | `object`、`offset` | `offset` 缺省 `[0, 0]` | `offset` 为 $\mu\text{m}$ | `object` 中的一个物体，沿 $z$ 占其厚度 `side_z`，横向中心位于 `offset`；简写为 `"<物体名>"` 时等同于 `offset = [0, 0]` |
| `{"slot": "<槽位名>", ...}` | `slot`、`facing`、`offset`、`rotation_z`、`colour` | `facing` 缺省 `"upstream"`，`offset` 缺省 `[0, 0]`，`rotation_z` 缺省 `0`，`colour` 缺省 `[1, 0.1, 0.8]` | `offset` 为 $\mu\text{m}$，`rotation_z` 为度 | 一块器件，沿 $z$ 占其几何全部层总厚 $l_z + t$；`facing` 取 `"upstream"`（前表面朝源）或 `"downstream"`（绕 $y$ 轴翻转 $180^\circ$，前表面朝下游），`rotation_z` 只取 `0`、`90`、`180`、`270`，按式 (17)–(18) 放置；`colour` 为可视化 RGB 颜色（`0` 至 `1`） |
| `[项, 项, ...]` | 列表中各项 | 无 | 无 | 并排放置的几项（只能是物体或槽位），前端面对齐在同一个 $z$，沿 $z$ 占其中最厚一项的厚度，靠各自的 `offset` 横向错开 |

`along_beam` 第一项不是 `"source"`、`gap` 为负、物体名不在 `object` 里、同一物体或槽位出现两次、`facing` 不是 `"upstream"`/`"downstream"`、`rotation_z` 取值不在 `{0, 90, 180, 270}`、并排的几项横向重叠，以及槽位名与器件表对不上时，均抛 `ValueError`。

#### `object` 两类几何体键

`object["elemental"]` 和 `object["binary_compounds"]` 都是以几何体名为键的字典，每一项是一个长方体：前者用 Geant4 NIST 材料，后者由两种元素组成。例如放在源与器件之间的一层铝：

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
        },
    },
},
```

这是一块 $5\ \text{mm} \times 5\ \text{mm} \times 0.08\ \mu\text{m}$ 的铝片；要让它的下表面离器件前表面距离 $d$，在 `along_beam` 里把 `"Al"` 写在槽位前面并隔开 `{"gap": d}`。

下表各键对其适用的分类都必填，只有 `elemental` 的 `tub` 可以省去。

| 键 | 适用分类 | 单位 | 含义 |
| --- | --- | --- | --- |
| `name` | 两者 | 无 | 几何体名称 |
| `material` | `elemental` | 无 | Geant4 NIST 材料名，如 `"G4_Al"`、`"G4_Ni"`、`"G4_Ti"`、`"G4_Si"`、`"G4_BRASS"` |
| `material_1`, `material_2` | `binary_compounds` | 无 | 两种元素的符号，如 `"Si"`、`"C"`、`"N"`、`"O"` |
| `compound_name` | `binary_compounds` | 无 | 化合物材料名；同名化合物的组分与密度须一致 |
| `density` | `binary_compounds` | $\text{g/cm}^3$ | 化合物密度 |
| `natoms_1`, `natoms_2` | `binary_compounds` | 无 | 两种元素的原子数份额，按原子量换成质量份额 |
| `side_x`, `side_y`, `side_z` | 两者 | $\mu\text{m}$ | 长方体沿 $x$、$y$、$z$ 的全尺寸（`side_z` 为厚度） |
| `colour` | 两者 | 无 | 可视化 RGB 颜色 `[r, g, b]` |
| `tub` | `elemental` 可选，`binary_compounds` 必填（无孔填 `{}`） | $\mu\text{m}$ | 从长方体中心沿 $z$ 轴减去的圆柱孔，含半径 `"tub_radius"` 和半长 `"tub_depth"` |

#### `"gdml_import"` 附加键

GDML 文件中含字符串 `RASER_GDML_WRAPPER_WORLD` 时，GDML 的世界体直接作 Geant4 世界体，世界的大小、材料与导入几何体的放置都由 GDML 文件给出；下表中起作用的是 `gdml.file`、`gdml.validate` 与 `visualization`。

| 键 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `world_half_size_um` | 由 `world_half_side` 计算 | $\mu\text{m}$ | 覆盖世界立方体的半边长 |
| `gdml.file` | 无（必填） | 无 | GDML 文件路径；依次按绝对路径、各组件根下的该路径、各组件根下 `deposit/<file>`、`src/raser/<file>` 查找；为空抛 `ValueError`，找不到抛 `FileNotFoundError` |
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
| `device_alone` | `raser/components/deposit/` | 器件单独放在真空里，源到器件前表面 $17\ \text{mm}$ |
| `Sr90_collimator` | `src/raser_bench/signal/components/deposit/` | 空气中源与器件之间的黄铜准直器（见 [信号](../bench/signal.md)） |
| `pcb_readout_gdml` | `src/raser_bench/signal/components/deposit/` | 导入 `pcb_readout.gdml` 的 PCB 读出板（见 [信号](../bench/signal.md)） |
| `time_resolution` | `src/raser_bench/timeres/components/deposit/` | 沿束流排布铝片、参考硅器件与两块开孔 PCB 板（见 [时间分辨](../bench/timeres.md)） |
| `telescope` | `src/raser_bench/telescope/components/deposit/` | 真空中沿束流排布的 8 个槽位，默认 3 + 2 + 3（见 [束流望远镜](../bench/telescope.md)） |

### 放射源和束流

#### 公共键

| 键 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `name` | 无（可选） | 无 | 源名称 |
| `kind` | 无（必填） | 无 | `"beam"`、`"decay_source"` 或 `"toy_mip"` |
| `description` | 无（可选） | 无 | 文字说明 |

源里不能有 `par_in`、`par_out`、`par_angle`：源在世界原点沿 $+z$ 发射，入射角由装置的 `source.angle` 给出。

#### `beam` 与 `decay_source` 键

`"beam"` 与 `"decay_source"` 走同一条 Geant4 分支；是否按核素衰变只看源里有没有 `nuclides`。

| 键 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `par_type` | 无（无 `nuclides` 时必填） | 无 | Geant4 粒子名（如 `"e-"`、`"proton"`、`"alpha"`），或等概率抽取的粒子名列表 |
| `par_energy` | 无（无 `nuclides` 时必填） | $\text{MeV}$ | 粒子动能，或与 `par_type` 等长的列表 |
| `par_randx`, `par_randy` | `0`, `0` | $\mu\text{m}$ | 发射方向向量（$\mathbf{r}_{\text{out}} - \mathbf{r}_{\text{in}}$）的 $x$、$y$ 分量上均匀随机偏移的半宽 |
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
| `bunch`（`src/raser_app/bmos/components/deposit/`） | `beam` | 三个 $80\ \text{MeV}$ 质子并排同时发射（见 [`bmos`](../apps/bmos.md)） |

### 激光

| 键 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `description` | 无（可选） | 无 | 激光器型号与参数说明 |
| `tech` | 无（必填） | 无 | `"SPA"`（单光子吸收）或 `"TPA"`（双光子吸收） |
| `direction` | 无（必填） | 无 | `"top"`（从 $z = 0$ 沿 $+z$）、`"bottom"`（从 $z = l_z$ 沿 $-z$）或 `"edge"`（从 $x = 0$ 沿 $+x$） |
| `refractionIndex` | 无（必填） | 无 | 器件材料在该波长的折射率 $n$ |
| `wavelength` | 无（必填） | $\text{nm}$ | 激光波长 |
| `alpha` | 硅按式 (7) 查表，碳化硅按式 (7a) 计算 | $\text{m}^{-1}$ | 吸收系数；给 `0` 时没有单光子吸收，`"TPA"` 激光只有 TPA 群 |
| `beta_2` | 无（`"TPA"` 必填） | $\text{m/W}$ | 双光子吸收系数 |
| `temporal_FWHM` | 无（必填） | $\text{s}$ | 脉冲时间半高全宽 $\tau$ |
| `pulse_energy` | 无（必填） | $\text{J}$ | 脉冲能量 $E_p$ |
| `spacial_FWHM` | 无（必填） | $\mu\text{m}$ | 焦点处光斑的空间半高全宽 |
| `l_Rayleigh` | 按式 (9) 计算 | $\mu\text{m}$ | 器件内的瑞利长度 |
| `central_time` | 无（必填） | $\text{s}$ | 脉冲中心时刻 |
| `pairs_per_group` | 无（必填） | 对 | 每个载流子群的对数上限 |
| `groups` | 无（必填） | 群 | 每种吸收至少分出的群数（去掉器件外的群之前） |
| `fx_rel`, `fy_rel`, `fz_rel` | 无（必填） | 无 | 焦点的相对坐标，绝对位置为 $(f_x l_x,\ f_y l_y,\ f_z l_z)$ |

#### 吸收系数表（`deposit/absorption/<material>.txt`）

空白分隔的两列文本，`#` 开头为注释：第一列波长（$\text{nm}$），第二列 $300\ \text{K}$ 下的带间吸收系数（$\text{cm}^{-1}$），按波长升序。库中只有 `Si.txt`，波长 $250$ 至 $1450\ \text{nm}$，取自文献 [7]。

#### 库中激光

| 组件 | `tech` | 说明 |
| --- | --- | --- |
| `LA01IR_top_Si`、`LA01IR_edge_Si` | `"SPA"` | $1064\ \text{nm}$，硅，查表取 $\alpha$ |
| `LA01R_top_Si`、`LA01R_bottom_Si` | `"SPA"` | $660\ \text{nm}$，硅，查表取 $\alpha$ |
| `PIL037_top_SiC`、`PIL037_edge_SiC` | `"SPA"` | $375\ \text{nm}$，碳化硅，按式 (7a) 计算 $\alpha$（$300\ \text{K}$ 时 $9.05\ \text{cm}^{-1}$） |
| `TPA1550_top_Si`、`TPA1550_edge_Si` | `"TPA"` | $1550\ \text{nm}$，硅，长于表的上限，$\alpha = 0$，只有 TPA 群 |

### `deposit.h5` 文件格式

#### 文件属性

| 属性 | 类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `generated_events` | `int` | 事例 | 源生成的事例数 |
| `recorded_events` | `int` | 事例 | 文件里的事例数 |
| `generated_fraction` | `float` | 无 | 源发射中被生成的部分；带 `par_cone` 的核素源为式 (16)，其余为 `1.0` |
| `edep_min.<槽位>`, `edep_max.<槽位>` | `float` | $\text{MeV}$ | 该槽位有源层内总沉积能量窗的下限、上限（单器件槽位名为 `"Device"`），给了才写 |
| `require` | `str` | 无 | 符合条件逻辑式 |
| `coincidence_window_ns` | `float` | $\text{ns}$ | 符合时间窗，给了才写 |

生成事例中被记录的比例是 `recorded_events / generated_events`；每次源发射记录的事例数是 `recorded_events / generated_events * generated_fraction`。

#### 数据集

| 数据集 | 形状与类型 | 单位 | 含义 |
| --- | --- | --- | --- |
| `event` | `(recorded_events,)`, `int64` | 无 | 事例号：Geant4 的 `eventID`，toy MIP 的生成序号，激光为 `0` |
| `count` | `(recorded_events,)`, `int64` | 步 | 每个事例的沉积步数 |
| `detector` | `(sum(count),)`, 变长 `str` | 无 | 沉积步所在的探测器名：单器件写 `"Device"`，多器件写槽位名 |
| `x`, `y`, `z` | `(sum(count),)`, `float64` | $\mu\text{m}$ | 所在器件的器件坐标中的步中点 |
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
| `nocarrier2D_<fx>_<fy>_<fz>.pdf` | `LaserInjection.draw_nocarrier2D` | $y = f_y l_y$ 的 $x$-$z$ 面上（三种入射方向下这个面都过光轴）电子-空穴对的体密度，`TH2D`（`COLZ`），由式 (10)、(11) 的 $dN/ds$ 乘横向分布 $\frac{k}{\pi w^2}\exp(-k r^2/w^2)$ 在 $200 \times 200$ 的网格上直接算出，颜色为对每 $\mu\text{m}^3$（`Pairs [μm⁻³]`）；沿光路从入射面画到累积对数 $M(s)$ 达到 $0.99\,N_{\text{tot}}$ 处，横向画到光轴两侧 $2 w_{\max}$（$w_{\max}$ 为这段光路上光斑半径的最大值，超出器件处截掉） | $\mu\text{m}$ |

## 参考文献

- [1] U. Fano, “Ionization Yield of Radiations. II. The Fluctuations of the Number of Ions”, Phys. Rev. 72 (1947) 26, doi:10.1103/PhysRev.72.26
- [2] T. Shimaoka et al., “Fano factor evaluation of diamond detectors for alpha particles”, Phys. Status Solidi A 213 (2016) 2629, doi:10.1002/pssa.201600195
- [3] S. Agostinelli et al. (GEANT4 Collaboration), “GEANT4—a simulation toolkit”, Nucl. Instrum. Methods Phys. Res. A 506 (2003) 250, doi:10.1016/S0168-9002(03)01368-8
- [4] J. Allison et al., “Recent developments in Geant4”, Nucl. Instrum. Methods Phys. Res. A 835 (2016) 186, doi:10.1016/j.nima.2016.06.125
- [5] S. Hauf et al., “Radioactive Decays in Geant4”, IEEE Trans. Nucl. Sci. 60 (2013) 2966, doi:10.1109/TNS.2013.2270894
- [6] L. Landau, “On the energy loss of fast particles by ionization”, J. Phys. (USSR) 8 (1944) 201
- [7] M. A. Green, “Self-consistent optical parameters of intrinsic silicon at 300 K including temperature coefficients”, Sol. Energy Mater. Sol. Cells 92 (2008) 1305, doi:10.1016/j.solmat.2008.06.009
- [8] S. Navas et al. (Particle Data Group), “Review of Particle Physics”, Phys. Rev. D 110 (2024) 030001, doi:10.1103/PhysRevD.110.030001
- [9] K. Ramanathan, N. Kurinsky, “Ionization yield in silicon for eV-scale electron-recoil processes”, Phys. Rev. D 102 (2020) 063026, doi:10.1103/PhysRevD.102.063026
- [10] B. G. Lowe, “Measurements of Fano factors in silicon and germanium in the low-energy X-ray region”, Nucl. Instrum. Methods Phys. Res. A 399 (1997) 354, doi:10.1016/S0168-9002(97)00965-0
- [11] A. Gsponer et al., Nucl. Instrum. Methods Phys. Res. A 1064 (2024) 169412, doi:10.1016/j.nima.2024.169412
- [12] S. K. Chaudhuri, K. J. Zavalla, K. C. Mandal, Appl. Phys. Lett. 102 (2013) 031109, doi:10.1063/1.4776703
- [13] M. E. Levinshtein, S. L. Rumyantsev, M. S. Shur (eds.), *Properties of Advanced Semiconductor Materials*, Wiley (2001)
- [14] H. Bichsel, “Straggling in thin silicon detectors”, Rev. Mod. Phys. 60 (1988) 663, doi:10.1103/RevModPhys.60.663
- [15] R. W. Boyd, *Nonlinear Optics*, 3rd ed., Academic Press (2008)
- [16] P. Grivickas, V. Grivickas, J. Linnros, A. Galeckas, “Fundamental band edge absorption in nominally undoped and doped 4H-SiC”, J. Appl. Phys. 101 (2007) 123521, doi:10.1063/1.2749335
- [17] S. G. Sridhara, R. P. Devaty, W. J. Choyke, “Absorption coefficient of 4H silicon carbide from 3900 to 3250 Å”, J. Appl. Phys. 84 (1998) 2963, doi:10.1063/1.368403
