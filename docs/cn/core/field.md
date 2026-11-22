# 器件场（`core/field`）

`src/raser/core/field/` 从 [器件定义](device.md) 取得几何、掺杂、偏压与辐照设定，按 `field` 段的设置选用网格，从 [材料模型](model.md) 取得能带、介电常数、复合寿命与碰撞电离系数。它用 DEVSIM 求解器件在给定偏压与辐照注量下的电势、载流子浓度、俘获率与导电区，再求各读出电极的权重势、单位条长互容、IV/CV/噪声曲线与一维器件的未耗尽体区参数，也可以从 Sentaurus TDR 文件导入场。结果写入场节点 `field/<节点号>/`，每个偏压一个场节点，节点记录为 `node.json`；[载流子输运](current.md) 通过 `DevsimField` 读取插值后的电场、掺杂、俘获率、导电标志、权重势与平面雪崩增益，[电子学读出](readout.md) 通过 `field_circuit` 与 `device_circuit` 取得器件的等效 SPICE 电路。命令行入口见 [../stages/field.md](../stages/field.md)。

## 物理

### 泊松方程与漂移-扩散方程

DEVSIM 在器件网格上联立求解电势与电子、空穴浓度。空间电荷由自由载流子、净掺杂和带电的辐照缺陷组成，电流由漂移与扩散组成，两种载流子的连续性方程通过复合与碰撞电离耦合。代码求解的稳态方程组为：

$$\nabla\cdot\bigl(\varepsilon\,\nabla\psi\bigr) = -q\,\bigl(p - n + N_{\text{net}} + N_t^{+} - N_t^{-}\bigr) \tag{1}$$

$$\nabla\cdot\mathbf{J}_n = q\,(U - G_{\text{ii}}), \qquad \nabla\cdot\mathbf{J}_p = -q\,(U - G_{\text{ii}}) \tag{2}$$

$$U = U_{\text{SRH}} + U_{\text{const}} + U_r + R_{\text{TAT}} \tag{3}$$

其中：

- $\psi$：静电势，$\text{V}$；
- $\varepsilon = \varepsilon_r \varepsilon_0$：介电常数，$\text{F/cm}$（$\varepsilon_0 = 8.8541878128\times10^{-14}\ \text{F/cm}$，$\varepsilon_r$ 取 [model.md](model.md) 的 `RELATIVE_PERMITTIVITY`：Si `11.9`、SiC `9.76`、Diamond `5.7`）；
- $q = 1.602176634\times10^{-19}\ \text{C}$：元电荷（`ElectronCharge`）；
- $n$、$p$：电子、空穴浓度，$\text{cm}^{-3}$；
- $N_{\text{net}} = N_D - N_A$：净掺杂（`NetDoping = Donors - Acceptors`），$\text{cm}^{-3}$；
- $N_t^{+}$、$N_t^{-}$：带正电的施主型缺陷与带负电的受主型缺陷浓度（`TrappedHoles`、`TrappedElectrons`），$\text{cm}^{-3}$，见式 (12)；无辐照模型时为零；
- $\mathbf{J}_n$、$\mathbf{J}_p$：电子、空穴电流密度，$\text{A/cm}^2$；
- $U$：净复合率，$\text{cm}^{-3}\,\text{s}^{-1}$；$U_{\text{const}}$ 为器件文件 `U_const` 给出的附加复合率（数值或 DEVSIM 表达式，缺省 `0`）；$U_r$ 为辐照缺陷的复合率，见式 (13)；$R_{\text{TAT}}$ 为 SiC 在启用雪崩项时的陷阱辅助隧穿项，见式 (8)；
- $G_{\text{ii}}$：碰撞电离产生率，$\text{cm}^{-3}\,\text{s}^{-1}$，见式 (7)；不启用雪崩项时为零。

电流按 Scharfetter-Gummel 离散化写在网格边上 [1]：

$$J_n = \frac{q\,\mu_n V_T}{L}\Bigl[n_1 B(-\Delta) - n_0 B(\Delta)\Bigr], \qquad J_p = -\frac{q\,\mu_p V_T}{L}\Bigl[p_1 B(\Delta) - p_0 B(-\Delta)\Bigr] \tag{4}$$

$$\Delta = \frac{\psi_0 - \psi_1}{V_T}, \qquad B(x) = \frac{x}{e^{x} - 1}, \qquad V_T = \frac{kT}{q} \tag{5}$$

其中：

- 下标 $0$、$1$：一条网格边的两个端点；$L$：边长，$\text{cm}$；
- $\mu_n$、$\mu_p$：电子、空穴迁移率，$\text{cm}^2/(\text{V}\cdot\text{s})$；
- $k = 1.380649\times10^{-23}\ \text{J/K}$；$T$：器件温度 `temperature`，$\text{K}$。

复合采用 Shockley-Read-Hall 形式 [2]：

$$U_{\text{SRH}} = \frac{np - n_i^2}{\tau_p\,(n + n_1) + \tau_n\,(p + p_1)}, \qquad n_1 = p_1 = n_i \tag{6}$$

其中 $n_i$ 为本征载流子浓度（$\text{cm}^{-3}$，由 [model.md](model.md) 的 `BAND_STRUCTURE` 在温度 $T$ 下给出），$\tau_n$、$\tau_p$ 为寿命（$\text{s}$）。

代码对应关系：`physics_drift_diffusion.CreateSiliconDriftDiffusion` 依次建立 `CreatePE`（式 1）、`CreateBernoulli` 与 `CreateElectronCurrent`/`CreateHoleCurrent`（式 4、5）、`CreateSRH`（式 3、6）、`CreateECE`/`CreateHCE`（式 2）。`create_parameter.create_parameter` 按 DEVSIM 区域材料 `Silicon`、`SiliconCarbide`、`Diamond`、`gas` 写入常数。迁移率模型按名字注册，器件文件按名字选用，每种材料有缺省选用的模型（见 [model.md](model.md)）；DEVSIM 求解中各材料现在缺省选用的是与场强、掺杂无关的常数迁移率，取区域参数 `mu_n`、`mu_p`（Si `1450`/`500`，SiC `1100`/`114`，Diamond `1714`/`2064`，单位 $\text{cm}^2/(\text{V}\cdot\text{s})$）。寿命取 `SRH_LIFETIME`（Si `7e-3`/`7e-3` s，SiC `2.5e-6`/`0.5e-6` s，Diamond `5.6e-7`/`2.4e-7` s）；SiC 的电子寿命取自 [20]，空穴寿命 `0.5e-6` s 由组里的时间分辨光致发光测量确认 [21]。

所有电极按欧姆接触处理（各调用处 `set_contact_type` 均为 `None`）：电极节点上 $n = n_0$、$p = n_i^2/n_0$（$N_{\text{net}} > 0$）或 $p = p_0$、$n = n_i^2/p_0$（$N_{\text{net}} \le 0$），电势 $\psi = V_{\text{bias}} + V_T \ln(n_0/n_i)$ 或 $\psi = V_{\text{bias}} - V_T \ln(p_0/n_i)$，其中 $n_0 = 10^{-10} + \tfrac12\bigl|N_{\text{net}} + \sqrt{N_{\text{net}}^2 + 4n_i^2}\bigr|$，$p_0$ 同式但 $N_{\text{net}}$ 取负。方程组与接触条件改写自 DEVSIM 示例 [3]。

### 碰撞电离

高场区的载流子在一个平均自由程内获得足以电离晶格的能量，产生次级电子-空穴对。DEVSIM 求解中，产生率由两种载流子的电流与各自的电离系数给出：

$$G_{\text{ii}} = \frac{\alpha_n(E)\,|J_n| + \alpha_p(E)\,|J_p|}{q} \tag{7}$$

其中 $\alpha_n$、$\alpha_p$ 为电子、空穴碰撞电离系数（$\text{cm}^{-1}$），$E$ 为网格边上的场强（$\text{V/cm}$）。系数公式取自 [model.md](model.md)：判断阈值时用 $|E|$，其余处用 $|E| + 1\ \text{V/cm}$，使 $b/E$ 有限（`EDGE_FIELD`、`EDGE_FIELD_IN_THRESHOLDS`）。

仅当 `has_avalanche` 为真（`enable_gain` 为真且 `avalanche_model` 非空）时，`physics_avalanche.CreateImpactGeneration` 按 `avalanche_model` 与区域材料选系数：

- `"NoAvalanche"`：$G_{\text{ii}} = 0$；
- 材料 `Silicon` 且名字不是 `"CustomAvalanche"`：van Overstraeten–de Man 系数 `VAN_OVERSTRAETEN` [4]；
- 材料 `SiliconCarbide`，名字不是 `"CustomAvalanche"` 或 `"Fine_exponential_models"`：Hatakeyama 系数 `hatakeyama` [5]；
- 材料 `SiliconCarbide` 且名字为 `"Fine_exponential_models"`：式 (9)；
- 其余组合（包括 `"CustomAvalanche"`）：系数取函数参数 `custom_ion_n`、`custom_ion_p`，缺省 `'0'`。

SiC 区域另从 $G_{\text{ii}}$ 中减去陷阱辅助隧穿项 $R_{\text{TAT}}$（`CreateFESRH`），其场增强因子采用 Hurkx 形式并在 $F_{\text{sat}}$ 以上保持不变 [6]：

$$R_{\text{TAT}} = \Gamma(|E|)\,U_{\text{const}}, \qquad \Gamma(F) = 2\sqrt{3\pi}\,\frac{F'}{F_\Gamma}\exp\!\Bigl[\Bigl(\frac{F'}{F_\Gamma}\Bigr)^2\Bigr], \quad F' = \min(F, F_{\text{sat}}) \tag{8}$$

其中 $F_\Gamma = 3.9\times10^4\ \text{V/cm}$，$F_{\text{sat}}$ 缺省 `TAT_SATURATION_FIELD` $= 10^5\ \text{V/cm}$（参数名 `F_sat`，可由器件文件 `parameter` 改写），$\pi$ 取 `3.14159`；$U_{\text{const}}$ 取边的 `n1` 端节点值。

`"Fine_exponential_models"` 的系数取 Thornber 形式 [13]，参数取 Konstantinov 等对 4H-SiC 的测量 [14]：

$$\alpha_n = \frac{qE'}{\epsilon_{in}}\exp\!\Bigl[-\frac{\epsilon_{in}E_R}{(qE'\lambda_n)^2}\Bigr], \qquad \alpha_p = \frac{qE'}{\epsilon_{ip}}\exp\!\Bigl[-\frac{\epsilon_{ip}E_R}{qE'\lambda_p\,(E_R + qE'\lambda_p)}\Bigr] \tag{9}$$

其中 $E' = E + 1\ \text{V/cm}$；$\epsilon_{in} = 10\ \text{eV}$、$\epsilon_{ip} = 7\ \text{eV}$ 为电子、空穴的有效电离阈能；$E_R = 3E_p = 0.36\ \text{eV}$，$E_p = 0.12\ \text{eV}$ 为光学声子能量；$\lambda_n = 2.99\times10^{-7}\ \text{cm}$、$\lambda_p = 3.25\times10^{-7}\ \text{cm}$ 为平均自由程；能量按 $1.602176634\times10^{-19}\ \text{J/eV}$ 换成 J，$\alpha$ 单位 $\text{cm}^{-1}$。$\alpha_p$ 是 Thornber 式取 $E_{kT} = 0$；$\alpha_n$ 是它的高场极限 $qE'\lambda_n \gg E_R$，按 [14] 对电子只用高场渐近。

`avalanche_model` 为 `"Tunnel"` 时，在 $G_{\text{ii}}$ 上再加 $R_{\text{improved}} = 3.11\,|E|^{2.5}\exp(|E|/3\times10^4)$（`CreateTunnelModel_Zaiyi`），SiC 区域中 $R_{\text{TAT}}$ 被重新定义为不饱和的 $\Gamma(|E|)\,U_{\text{SRH}}$。

`DevsimField` 另提供一维平板倍增的稳态积分，供 [current.md](current.md) 的 `"planar_integral"` 算法使用。沿深度 $z$，从电子离开的一面 $b$ 起积分 [7]：

$$K(z) = \exp\!\int_b^z (\alpha_n - \alpha_p)\,dz', \qquad I_{\text{bd}} = \int_0^W \alpha_p K\,dz \tag{10}$$

$$G(z) = \frac{K(z)}{1 - I_{\text{bd}}} - 1 \tag{11}$$

其中 $W$ 为网格深度（$\text{cm}$），$I_{\text{bd}}$ 为击穿积分（无量纲），$G(z)$ 为深度 $z$ 处产生的一对载流子额外增加的对数。这里的系数由 `Material(material, avalanche_model=avalanche_model).cal_coefficient` 给出，只接受 `"vanOverstraeten"`、`"Okuto"`、`"Hatakeyama"`（见 [model.md](model.md)）。

### 辐照缺陷与俘获率

辐照在禁带中引入深能级缺陷。缺陷按 SRH 统计占据电子，带电的缺陷进入泊松方程，空缺陷俘获电子、满缺陷俘获空穴，并贡献复合。对每个缺陷 $i$：

$$N_{t,i} = g_i\,\Phi, \qquad f_i = \frac{c_{n,i}\,n + c_{p,i}\,p_{1,i}}{c_{n,i}(n + n_{1,i}) + c_{p,i}(p + p_{1,i})} \tag{12}$$

$$U_r = \sum_i \frac{N_{t,i}\,c_{n,i}\,c_{p,i}\,(np - n_i^2)}{c_{n,i}(n + n_{1,i}) + c_{p,i}(p + p_{1,i})} \tag{13}$$

$$\Gamma_n = \sum_i c_{n,i} N_{t,i}\,(1 - f_i), \qquad \Gamma_p = \sum_i c_{p,i} N_{t,i}\,f_i \tag{14}$$

$$n_{1,i} = N_c \exp\!\Bigl(-\frac{E_g/2 - E_{t,i}}{kT}\Bigr), \qquad p_{1,i} = N_v \exp\!\Bigl(-\frac{E_{t,i} + E_g/2}{kT}\Bigr), \qquad c_{n,i} = v_{\text{th}}\sigma_{n,i},\ c_{p,i} = v_{\text{th}}\sigma_{p,i} \tag{15}$$

其中：

- $\Phi$：辐照注量，$\text{cm}^{-2}$；$g_i$：缺陷引入率（`g_int`），$\text{cm}^{-1}$；$N_{t,i}$：缺陷浓度，$\text{cm}^{-3}$；
- $f_i$：缺陷被电子占据的比例（无量纲）；受主型缺陷贡献 $N_t^{-} = \sum N_{t,i} f_i$，施主型缺陷贡献 $N_t^{+} = \sum N_{t,i}(1 - f_i)$；
- $E_{t,i}$：缺陷能级（`E_t_ev`，以禁带中央为零点、向导带为正，$\text{eV}$，乘以 $1.602176634\times10^{-19}\ \text{J/eV}$ 换成 J）；$E_g$：禁带宽度，J；$N_c$、$N_v$：导带、价带有效态密度，$\text{cm}^{-3}$；
- $\sigma_{n,i}$、$\sigma_{p,i}$：电子、空穴俘获截面，$\text{cm}^2$；$v_{\text{th}}$ = `vel_mean` $= 10^7\ \text{cm/s}$；
- $\Gamma_n$、$\Gamma_p$：电子、空穴俘获率（`TrappingRate_n`、`TrappingRate_p`），$\text{s}^{-1}$，存盘后由 `DevsimField.get_trap_e`、`get_trap_h` 交给 [current.md](current.md)。

`physics_irradiation.CreateIrradiation` 按 `irradiation.irradiation_model` 选缺陷表；其余名字取参数 `custom_defect`，缺省为空表。有 `irradiation` 块且求解电场时建立辐照项；其余情况俘获率为 `0`。缺陷字典的 `"type"` 不是 `"donor"` 或 `"acceptor"` 时抛出 `ValueError`。`"Schwandt"` 是 Hamburg Penta Trap Model [15]，`"XingChen"` 是组里拟合质子辐照硅的结果 [16]，`"Perugia"` 是 p 型 FZ 硅的三能级模型 [17]：

| 模型 | 缺陷 | 类型 | `E_t_ev` [eV] | `g_int` [$\text{cm}^{-1}$] | $\sigma_n$ [$\text{cm}^2$] | $\sigma_p$ [$\text{cm}^2$] |
| --- | --- | --- | --- | --- | --- | --- |
| `"XingChen"` | `E30K` | 施主 | `0.56-0.1` | `2.0810` | `2.300e-14` | `2.920e-16` |
| | `V3` | 受主 | `0.56-0.458` | `1.6504` | `2.551e-14` | `1.511e-13` |
| | `Ip` | 受主 | `0.56-0.545` | `0.6936` | `4.478e-15` | `6.709e-15` |
| | `H220` | 施主 | `-0.56+0.48` | `2.6112` | `4.166e-15` | `1.965e-16` |
| | `CiOi` | 施主 | `-0.56+0.36` | `1.6511` | `3.230e-17` | `2.036e-14` |
| `"Perugia"` | `DA1` | 受主 | `0.56-0.42` | `1.613` | `1e-15` | `1e-14` |
| | `DA2` | 受主 | `0.56-0.46` | `0.9` | `7e-15` | `7e-14` |
| | `DD` | 施主 | `-0.56+0.36` | `0.9` | `3.23e-13` | `3.23e-14` |
| `"Schwandt"` | `E30K` | 施主 | `0.56-0.1` | `0.0497` | `2.300e-14` | `2.920e-16` |
| | `V3` | 受主 | `0.56-0.458` | `0.6447` | `2.551e-14` | `1.511e-13` |
| | `Ip` | 受主 | `0.56-0.545` | `0.4335` | `4.478e-15` | `6.709e-15` |
| | `H220` | 施主 | `-0.56+0.48` | `0.5978` | `4.166e-15` | `1.965e-16` |
| | `CiOi` | 施主 | `-0.56+0.36` | `0.3780` | `3.230e-17` | `2.036e-14` |
| `"CommonDefect"`（SiC） | `Z12` | 受主 | `1.63-0.67` | `1` | `3e-16` | `2e-12` |
| | `EH67` | 施主 | `1.63-1.65` | `1` | `2e-17` | `3e-17` |

### 权重势

由 Shockley-Ramo 定理 [8, 9]，读出电极的权重势是该电极置 $1$、其余电极置 $0$、去掉空间电荷后的静电解。偏压下器件里导电的部分对信号相当于导体：代码在每个偏压把节点分成导电与介质两类，导电节点与它接触的电极等势，其余为介质。求解的方程为：

$$\nabla\cdot\bigl(\varepsilon_0\,[1 + 10^{10}\,c_0 c_1]\,\nabla\phi_w\bigr) = 0, \qquad \phi_w\big|_{\text{读出电极}} = 1, \quad \phi_w\big|_{\text{其他电极}} = 0 \tag{16}$$

其中：

- $\phi_w$：无量纲权重势；
- $c_0$、$c_1$：一条网格边两端节点的导电标志（`Conductive`，`1.0` 或 `0.0`），来自该偏压的 `Conductive_<V>V.pkl`，判据见式 (19)；两端都导电的边的介电常数放大 `CONDUCTOR_PERMITTIVITY` $= 10^{10}$ 倍，导体内残留的权重势量级为 $10^{-10}$；不接触任何电极的导电区浮空，同时接触两个电极的导电区报错（见“权重场求解”第 4 步）；
- 介质部分一律取真空介电常数 $\varepsilon_0$：`DevsimMesh._regions` 把所有区域材料换成 `"gas"`（`n_i = 1e-9`），掺杂换成 `Acceptors = "0"`、`Donors = "1"`，权重势与材料无关。

所以“按电阻率换材料”在代码里的做法是：低电阻率或未耗尽的节点当作导体并入电极，其余（包括耗尽的半导体）当作介电常数为 $\varepsilon_0$ 的介质。`weighting.take_conductors_into_electrodes` 实现这一步。

一个读出电极重复排成一行（`read_out_contact` 只列一项、`read_ele_num > 1`）时，网格只画一个晶胞。权重势在这个晶胞左右各拼 $s$ 个晶胞的一行上求一次，代码按全耗尽器件中权重势随距离衰减的估计取初始的 $s$：

$$s_0 = \Bigl\lceil \frac{d}{\pi\,p}\,\ln\frac{2}{\delta} \Bigr\rceil \tag{17}$$

其中 $d$ 为 `l_z`，$p$ 为 `p_x`（均为 $\mu\text{m}$），$\delta$ 为 `weighting_tolerance`；远离电极处权重势按 $\exp(-\pi x/d)$ 衰减，行端的反射使该处加倍（`cells_to_fall_off` 的注释）。

同一个解给出该条到其余各电极的单位条长互容：

$$C_j = \frac{\varepsilon_r\,|Q_j|}{V_1} \tag{18}$$

其中 $Q_j$ 为第 $j$ 个电极上的接触电荷（$\text{C/cm}$），$V_1 = 1\ \text{V}$ 为读出电极上置的电压，$\varepsilon_r$ 为器件材料的相对介电常数（解在 $\varepsilon_0$ 中求得，再乘回），$C_j$ 单位 $\text{F/cm}$。离读出条 $k$ 个位置的左右两条合为一个电极 `neighbour<k>`。

### 导电区的划分

求解后，代码按每个节点的电阻率与耗尽程度判定它在该偏压下是否导电：

$$\text{导电} \iff \rho < \rho_0 \ \ \text{或}\ \ \bigl(|N_{\text{net}}| > 0 \ \text{且}\ n_{\text{maj}} > 0.5\,|N_{\text{net}}|\bigr), \qquad \rho = \frac{1}{q(\mu_n n + \mu_p p)} \tag{19}$$

其中 $\rho$ 为电阻率（$\Omega\cdot\text{cm}$），$\rho_0$ = `RESISTIVITY` $= 10\ \Omega\cdot\text{cm}$，$n_{\text{maj}}$ 为多子浓度（$N_{\text{net}} > 0$ 的 n 型节点取 $n$，$N_{\text{net}} < 0$ 的 p 型节点取 $p$），`UNDEPLETED` $= 0.5$ 为每个净掺杂离子对应的多子数阈值：第二条判多子是否还在、未被耗尽，从别处溢入的少子不算，少子只经第一条的电阻率计入，$q$ 取 `1.602176634e-19` C。无净掺杂的节点只看电阻率。DEVSIM 求解的场用该区域选用的迁移率（缺省为常数迁移率参数 `mu_n`、`mu_p`）；TCAD 导入的场用文件里每个节点的 `eMobility`、`hMobility`。实现为 `conductive.conductive`，判定结果写成 `Conductive_<V>V.pkl`，同时用于式 (16) 与 [current.md](current.md) 的“已收集”判定（`DevsimField.get_conductive`）。

### 器件电路参数

器件在电子学网表中表示为电容、电阻与感应电流源组成的网络（`DeviceCircuit`）。每个读出电极 `<e>` 的耗尽层电容 $C_{\text{dep}}$ 接在 `<e>_pad` 与耗尽层背面的节点 `undepleted` 之间，感应电流源与它并联；所有读出电极共用这一个 `undepleted` 节点。未耗尽体区为 $R_{\text{und}} \parallel C_{\text{und}}$，接在 `undepleted` 与地之间。可选的偏置电阻 $R_{\text{bias}}$ 从 `<e>_pad` 接地，可选的耦合电容 $C_{\text{c}}$ 接在 `<e>_pad` 与读出端 `<e>_port` 之间。

结电容 $C_{\text{dep}}$ 由 `junction_capacitance` 依次取：器件文件 `capacitance_pF`（实测值）、场在该偏压求得的电容（`<V>V.cv.json` 的比电容乘 `area_factor`）、`Detector.capacitance` 的平行板估计（读出面积除以 `depletion_depth`，缺省 `l_z`）；三者都没有时抛出 `ValueError`。场电容只来自单点电容子任务在该偏压写出的 `<V>V.cv.json`（记入 `solved.capacitance`）；只求扫描与权重场的场节点里结电容取平行板估计。

未耗尽体区按 Riegler 的集总 $R \parallel C$ 模型 [10] 处理，一维、二维、三维器件用同一组式子 [22]。场给出比电阻 $r$ 与比电容 $c$（单位面积），电路乘器件面积 $A$：

$$R_{\text{und}} = \frac{r}{A}, \qquad C_{\text{und}} = c\,A, \qquad c = \frac{\varepsilon}{W_{\text{und}}} \tag{20}$$

$$\text{1D:}\quad r = \sum_{k} w_k\,\bar\rho_k, \quad W_{\text{und}} = \sum_k w_k; \qquad \text{2D、3D:}\quad r = \frac{1}{S}\sum_{i} \rho_i\,V_i, \quad W_{\text{und}} = \frac{1}{S}\sum_i V_i \tag{20a}$$

其中：

- 体区节点的条件是有净掺杂、$n_{\text{maj}} > 0.5|N_{\text{net}}|$（多子同式 (19)）且 $\rho \ge 10\ \Omega\cdot\text{cm}$（电极下的重掺杂层不算）；
- 1D：求和遍及相邻两节点都属于未耗尽体区的网格区间 $k$；$w_k$ 为区间宽度（cm），$\bar\rho_k$ 为两端节点电阻率的平均（$\Omega\cdot\text{cm}$）；
- 2D、3D：求和遍及未耗尽体区节点 $i$；$V_i$ 为节点体积（DEVSIM 的 `NodeVolume`，2D 为 $\text{cm}^2$，3D 为 $\text{cm}^3$），$\rho_i$ 为节点电阻率；$S$ 为网格在电极平面内的跨度（2D 为横向宽度 cm，3D 为横向面积 $\text{cm}^2$）；$W_{\text{und}}$ 为未耗尽层的平均厚度；
- $r$：$\Omega\cdot\text{cm}^2$；$c$：$\text{F/cm}^2$；$\varepsilon$：区域参数 `Permittivity`，$\text{F/cm}$；
- $A$：1D 取 `area_factor`，2D、3D 取 $l_x l_y$，$\text{cm}^2$。

全耗尽时 $W_{\text{und}} = 0$，`undepleted` 节点直接接地。器件文件可以用 `undepleted_resistance_ohm` 与 `undepleted_capacitance_pF` 成对给定 $R_{\text{und}}$、$C_{\text{und}}$，优先于场。

一维的集总模型是精确的。二维、三维中共用节点只保留所有电极同相的那一部分，对所有电极信号之和是精确的，对单个电极在成形时间远大于 $\max(\tau_0, 2\tau_r)$ 时趋于精确，对相邻电极的信号不准（$\tau_r = \varepsilon\rho$，$\tau_0 = \tau_r\,l_z/d_0$，$d_0 = l_z - W_{\text{und}}$ 为耗尽深度）。二维、三维器件有未耗尽层时，组装器件电路的一步打印一条警告，给出偏压、$d_0$、$\tau_r$ 与 $\tau_0$，说明偏压过低、未耗尽层的集总参数对相邻电极不准。

条形电极行（`field_circuit` 读到 `Capacitance_<V>V.json`）中，相隔 $k$ 个位置的两条之间接电容 $C_k = \tfrac12 C_{\text{neighbour}k}\,L$，$k \le$ `neighbours_coupled`，$L$ 为条长 `l_y`（换成 cm）；每条接到 `undepleted` 的电容为 $C_{\text{total}}L$（或 `capacitance_pF`）减去它到行内其他条的互容之和。只为击中条附近的一段条搭电路时（`part_of_row`），段外的 $n$ 根条在虚地上，它们的这份电容合成 $n$ 倍行中部一根条的值，接在 `undepleted` 与地之间（`C_undepleted_rest`）。

阻性电荷共享层（`resistive_layer`）把层切成宽为间距的晶胞，每个晶胞是一个节点，经耗尽层电容接到 `undepleted`；相邻晶胞之间接层电阻：

$$C_{\text{cell}} = c_A\,w\,l, \qquad R_{\text{row}} = \frac{R_\square}{l}\,w\,\Bigl(1 - \frac{m}{2}\Bigr), \qquad R_{\text{grid}} = R_\square\,\frac{w_\parallel}{w_\perp}\Bigl(1 - \frac{m}{2}\Bigr) \tag{21}$$

其中 $c_A = C_{\text{dep}}/(w\,l)$ 为单位面积耗尽层电容（$\text{F/m}^2$，$C_{\text{dep}}$ 为一个晶胞的结电容）；$w$、$l$ 为晶胞宽度（`p_x`）与条长（`l_y`），$\text{m}$（网格中为 `p_x`、`p_y`）；$R_\square$ 为方块电阻，$\Omega$；$m \in \{0, 1\}$ 为这对晶胞中位于电极下的个数（电极从晶胞边缘开始，离邻胞中心半个晶胞）；网格中 $w_\parallel$、$w_\perp$ 为沿电阻方向与垂直方向的晶胞宽度。电极下的晶胞并成一个节点；给出 `coupling` 时电极经介质耦合到层上，层在电极下连续，每个晶胞到电极的电容为 $\varepsilon_0\varepsilon_r w l / t$（$t$ 为 `coupling.thickness`，器件文件里以 $\mu\text{m}$ 给出，代码换成 m）。

方块电阻 $R_\square$ 取器件文件 `resistive_layer.sheet_resistance`，没有时由铝注入 4H-SiC 层的模型算出 [11]：

$$R_\square = \frac{1}{q\,p\,t\,\mu}, \qquad N = \frac{D}{t}, \quad N_A = N\,a(T_a), \quad N_D = N\,\frac{\langle N_D\rangle}{10^{20}}, \quad \mu = \frac{\langle\mu_H\rangle}{\mu_{\text{drift}}(300\,\text{K}, 10^{20})}\,\mu_{\text{drift}}(T, N) \tag{22}$$

$$a(T_a) = \min\!\Bigl[1,\ \exp\Bigl(b + \frac{s}{k_B T_a}\Bigr)\Bigr] \tag{23}$$

其中：

- $D$：注入剂量 `implanted`，$\text{cm}^{-2}$；$t$：层厚 `thickness`（$\mu\text{m}$，代码换成 cm）；$N$：注入浓度，$\text{cm}^{-3}$；
- $a$：退火后成为受主的比例；$T_a$：退火温度 `anneal`（$^\circ\text{C}$，代码加 $273.15$ 换成 K）；$s$、$b$：$\ln(N_A/10^{20})$ 对 $1/(k_B T_a)$ 的线性拟合斜率（eV）与截距，拟合点为文献表 1、2 在 $1675$、$1775$、$1825\ ^\circ\text{C}$ 的三组测量；$k_B = 8.617333262\times10^{-5}\ \text{eV/K}$；
- $\langle N_D\rangle$、$\langle\mu_H\rangle$：三组测量的补偿施主浓度与霍尔迁移率的平均；$\mu_{\text{drift}}$：`Material("SiC").cal_mobility` 的零场空穴迁移率，$\text{cm}^2/(\text{V}\cdot\text{s})$；
- $p$：自由空穴浓度，由 [model.md](model.md) 的 `free_holes("SiC", "Al", N_A, N_D, T)` 按不完全电离求得，$\text{cm}^{-3}$；$T$：器件温度，K。

近似：退火温度在 $1675$–$1825\ ^\circ\text{C}$ 以外时，式 (23) 是外推（代码注释举例 sicar3 的 $1500\ ^\circ\text{C}$）。

### 解析场

`simple.py` 给出一维漂移场配上平板、条/像素、三维柱电极权重势的闭式 toy 场，接口与 `DevsimField` 的 `*_cached` 方法同名。

线性耗尽场（`LinearDepletionField1D`，代码注释称仿照 Allpix² [12]）：

$$E_z(z) = \operatorname{sgn}(V)\,\max\!\Bigl[0,\ \frac{|V| - V'_d}{d_{\text{eff}}} + \frac{2V'_d}{d_{\text{eff}}}\Bigl(1 - \frac{s}{d_{\text{eff}}}\Bigr)\Bigr]\times10^4 \tag{24}$$

$$d_{\text{eff}} = \begin{cases} d\sqrt{|V|/|V_d|}, & |V| < |V_d| \\ d, & |V| \ge |V_d| \end{cases}, \qquad V'_d = \min(|V_d|, |V|) \tag{25}$$

其中 $E_z$ 单位 $\text{V/cm}$（$10^4$ 由 $\text{V}/\mu\text{m}$ 换算），$V$ 为偏压，$V_d$ 为全耗尽电压（V），$d$ 为厚度（$\mu\text{m}$），$s = d - z$（`deplete_from_implants=True`，缺省）或 $s = z$，$z$ 先截到 $[0, d]$。$V \ge 0$ 时 $\operatorname{sgn}(V) = +1$。低于全耗尽电压时 $s > d_{\text{eff}}$ 的区域场为零，即未耗尽区。三种解析场的掺杂取常数 `doping_cm3`（缺省 $10^{12}\ \text{cm}^{-3}$），俘获率恒为 $0$。

平板（`AnalyticPlanarField`）：$\phi_w = z/d$（$z$ 截到 $[0, d]$），位置在 $[0, l_x]\times[0, l_y]$ 以外时 `get_w_p_cached` 抛出 `ValueError`；电场为式 (24)。

条与像素（`AnalyticStripPixelField`）：电极为宽 $a$ = `pitch_x_um`、长 $b$ 的矩形（像素 $b$ = `pitch_y_um`；条依次取 `sensor_y_um`、`pitch_y_um`、`pitch_x_um`），权重势为两接地平板间矩形电极的镜像级数 [18]：

$$\phi_w = \frac{1}{2\pi}\Bigl\{F(x, y, u) - \sum_{n=1}^{N}\bigl[F(x, y, 2nd - u) - F(x, y, 2nd + u)\bigr]\Bigr\} \tag{26}$$

$$F(x, y, u) = \sum_{\pm,\pm} (\pm)(\pm)\arctan\frac{x_\pm\,y_\pm}{u\,\sqrt{x_\pm^2 + y_\pm^2 + u^2}}, \qquad x_\pm = x \pm \tfrac{a}{2},\ y_\pm = y \pm \tfrac{b}{2} \tag{27}$$

其中 $(x, y)$ 为相对电极中心的位置（$\mu\text{m}$），$u = d - z$ 为到电极平面的距离，$N$ = `weighting_series_terms`（缺省 `100`）；$F$ 中 $(x_+, y_+)$ 与 $(x_-, y_-)$ 两项取正、交叉两项取负；结果截到 $[0, 1]$。只列一个读出电极（`central_electrode`）时电极中心在器件中央，否则按电极序号排成 `round(l_x / p_x)` 列。

三维柱（`AnalyticColumn3DField`）：在 $W\times H$ 的矩形晶胞（缺省 $2p_x \times 2p_y$）内用零边界的正弦级数求二维解，忽略 $z$。权重势为读出柱上 49 个源点平均的格林函数，按柱面一点 $(x_r + r_c, y_r)$ 归一；电势为权重势与均匀空间电荷解的叠加，两者都是矩形区域上 Dirichlet 问题的本征函数展开 [19]：

$$\mathcal{G}(x, y) = \sum_{m,n=1}^{M}\frac{4}{WH}\,\frac{\overline{\sin k_m x_s \sin k_n y_s}}{k_m^2 + k_n^2}\,\sin k_m x\,\sin k_n y, \qquad \phi_w = \frac{\mathcal{G}(x, y)}{\mathcal{G}(x_r + r_c, y_r)} \tag{28}$$

$$u_1 = \sum_{m,n\ \text{奇}}\frac{16}{\pi^2 mn\,(k_m^2 + k_n^2)}\sin k_m x\,\sin k_n y, \qquad P = u_1 - \frac{u_1(x_r + r_c, y_r)}{\mathcal{G}(x_r + r_c, y_r)}\,\mathcal{G} \tag{29}$$

$$\psi = -V\phi_w + \frac{qN}{\varepsilon_0\varepsilon_r}\,P, \qquad \mathbf{E} = \Bigl(V\nabla\phi_w - \frac{qN}{\varepsilon_0\varepsilon_r}\nabla P\Bigr)\times10^4 \tag{30}$$

其中 $k_m = m\pi/W$、$k_n = n\pi/H$（$\mu\text{m}^{-1}$），$M$ = `series_terms`；源点为柱心与半径 $0.35r_c$、$0.65r_c$、$0.9r_c$ 上的 8、16、24 点；$(x_r, y_r)$ 为读出柱位置（缺省晶胞中心），$r_c$ 为柱半径（$\mu\text{m}$）；$N$ 为 `doping_cm3`，$\varepsilon_r$ 缺省 `11.9`；$\psi$ 单位 V，$\mathbf{E}$ 单位 $\text{V/cm}$（$q N/(\varepsilon_0\varepsilon_r)$ 先按 SI 算出再乘 $10^{-12}$ 换成 $\text{V}/\mu\text{m}^2$）。位置先截到晶胞内；读出柱内 $\phi_w = 1$，接地柱（缺省四角）内 $\phi_w = 0$，其余截到 $[0, 1]$。

`strip_pixel_field_from_detector` 按小写的 `det_model` 选场：含 `"3d"` 用三维柱，含 `"planar"` 或等于 `"lgad"` 用平板，含 `"strip"` 或 `"pixel"` 用条/像素（含 `"pixel"` 为像素），其余抛出 `ValueError`。

## 算法

### 内置常数

下表的量写在代码里。“键”一列写明器件文件里能否改它。

| 常数 | 取值 | 单位 | 位置与含义 | 键 |
| --- | --- | --- | --- | --- |
| `q`（`ElectronCharge`） | `1.602176634e-19` | C | `CreateGlobalConstant`，DEVSIM 方程 | 无 |
| `k` | `1.380649e-23` | J/K | 同上 | 无 |
| `eps_0` | `8.8541878128e-14` | F/cm | 同上，及各材料 `Permittivity` | 无 |
| `T0` | `300.0` | K | 同上，区域参数 | 无 |
| `vel_mean` | `1e7` | cm/s | 缺陷俘获的热速度 $v_{\text{th}}$ | 无 |
| `mu_n`, `mu_p` | Si `1450`/`500`；SiC `1100`/`114`；Diamond `1714`/`2064` | $\text{cm}^2/(\text{V}\cdot\text{s})$ | 常数迁移率 | 无（`parameter` 可覆盖任一区域参数） |
| `taun`, `taup` | Si `7e-3`/`7e-3`；SiC `2.5e-6`/`0.5e-6`；Diamond `5.6e-7`/`2.4e-7` | s | `SRH_LIFETIME` | 无 |
| `n1`, `p1` | $n_i$ | $\text{cm}^{-3}$ | SRH 陷阱取本征能级 | 无 |
| `n_i`（`gas`） | `1e-9` | $\text{cm}^{-3}$ | 权重场介质 | 无 |
| `F_sat` | `1e5` | V/cm | `TAT_SATURATION_FIELD` | `parameter: {"name": "F_sat", ...}` |
| `F_gamma` | `3.9e4` | V/cm | 式 (8) | 无 |
| `epsilon_model_in`, `_ip`, `_0` | `10`, `7`, `0.36` 乘 `1.602176634e-19` | J | 式 (9) | 无 |
| `lambda_model_n`, `_p` | `2.99e-7`, `3.25e-7` | cm | 式 (9) | 无 |
| `EDGE_FIELD` 偏移 | `1` | V/cm | 电离系数中 $|E| + 1$ | 无 |
| 缺陷能量换算 `e` | `1.602176634e-19` | J/eV | `CreateIrradiation` | 无 |
| `CONDUCTOR_PERMITTIVITY` | `1e10` | 无 | 式 (16)，DEVSIM 与 TCAD 权重场 | 无 |
| `RESISTIVITY` | `10.0` | $\Omega\cdot\text{cm}$ | 式 (19) | 无 |
| `UNDEPLETED` | `0.5` | 无 | 式 (19) | 无 |
| `ELEMENTARY_CHARGE` | `1.602176634e-19` | C | `conductive.py`、`simple.py` | 无 |
| 接触 $n_0$ 偏移 | `1e-10` | $\text{cm}^{-3}$ | 欧姆接触浓度 | 无 |
| 最小偏压步长 | `1e-7` | V | 偏压扫描放弃条件 | 无 |
| 行晶胞扩展倍数 | `1.5`，上限 `2` 倍 $s_0$ | 无 | 权重场单晶胞拼接 | 无 |
| 晶胞宽度容差 | `1e-6` 倍 `p_x` | 无 | `createRowOfCells` | 无 |
| 节点重合容差 | `1e-9` 倍网格跨度 | 无 | `createRowOfCells`、`take_conductors_into_electrodes` | 无 |
| `STEP` | `1.0e-5` | cm | `gradient` 中心差分步长 | 无 |
| `max_size` | `50000` | $\mu\text{m}$ | 缓存接受的最大坐标 | 无 |
| `resolution_default_1d` | `z: 0.05`, `x: 10000.0`, `y: 10000.0` | $\mu\text{m}$ | 缓存箱宽 | 无 |
| `resolution_default_2d` | `z: 0.1`, `x: 0.5`, `y: 10000.0` | $\mu\text{m}$ | 同上，轴 `("z", "x")` | 无 |
| `resolution_default_plugin_2d` | `x: 0.1`, `y: 0.1`, `z: 10000.0` | $\mu\text{m}$ | 同上，轴 `("x", "y")` | 无 |
| `resolution_default_3d` | `z: 0.5`, `x: 1`, `y: 1` | $\mu\text{m}$ | 同上 | 无 |
| 三维规则化箱数 | `x: 30`, `y: 30`, `z: 30` | 个 | `interpolate_3d` | `field_interpolation_bins` |
| IDW 近邻数、幂次、零距离 | `8`、`2`、`1e-15` | 个、无、cm | `_idw_grid_3d` | 无 |
| TCAD 介电常数 | Silicon `11.9`、SiliconCarbide `9.76`、Oxide `3.9`、Nitride `7.5`；Aluminum 为导体 | 无 | `tcad.PERMITTIVITY`、`METALS` | 无 |
| TCAD 电极钳位系数 | `1e20` | 无 | `set_up_weighting` 的 `Hold` | 无 |
| TCAD 权重场收敛 | 绝对 `1e-6`、相对 `1e-6`、`20` 次 | 无 | `solve_weighting` | 无 |
| `DEFAULT_RELATIVE_PERMITTIVITY` | `11.9` | 无 | `simple.py` 三维柱 | `relative_permittivity` |
| 解析场掺杂 | `1.0e12` | $\text{cm}^{-3}$ | `simple.py` | `input_doping` |
| `VACUUM_PERMITTIVITY_F_M` | `8.8541878128e-12` | F/m | 阻性层耦合电容 | 无 |
| 铝注入参考层 | 浓度 `1e20` $\text{cm}^{-3}$、厚 `300e-7` cm、测量温度 `300.0` K、表 `ANNEALED` | 见左 | `implanted_aluminium.py` | 无 |

求解器的收敛设置 `SOLVER` 可由器件文件 `field.solver` 改写，见 [接口](#求解器设置-solver)。

### 网格

网格属于 `field`：器件文件里没有 `mesh` 段，几何（各层厚度、材料、电极在哪一面）是器件的固有性质；用哪一套网格由 `field` 段的设置指定。

1. **取坐标轴**：`mesh_axes` 给出存盘坐标对应的器件轴：1D 为 `("z",)`；2D 为 `("x", "y")`（所选网格在横向 $x$-$y$ 平面）或 `("z", "x")`；3D 为 `("x", "y", "z")`（所选网格由 `sde` 生成）或 `("z", "x", "y")`。DEVSIM 内部长度单位为 cm。
2. **建网格**（`DevsimMesh.mesh_define`）：求单晶胞拼接的权重场时（$s > 0$）调用 `createRowOfCells`；否则 1D 用所选一维网格的 `mesh_line`、`region`、`contact`；2D 用所选的 Gmsh 网格文件或内置二维网格（`mesh_line`、`region`、`contact`）；3D 一律读 Gmsh 网格文件。`dimension` 不是 1、2、3 时抛出 `ValueError`。
3. **权重场的材料与掺杂**：求权重场时 `_regions` 把每个区域材料换成 `"gas"`（内置 2D 网格里的 `"air"` 区域保留；Gmsh 网格不保留），`setDoping` 把掺杂换成 `Acceptors = "0"`、`Donors = "1"`。
4. **掺杂**：`Acceptors` 取 `doping.Acceptors`，有 `doping.Acceptors_ir` 时以 `+` 相接；`Donors` 同理；`NetDoping = Donors - Acceptors`。不求权重场的 1D 器件画 `plots/doping`。最后写出 `<det_name>.dat`（Tecplot）。
5. **HEMT 界面**：`hemt_physics.transport_model == "drift_diffusion_v1"` 时 2D 网格还加所选二维网格的 `interface`，没有界面时抛出 `ValueError`。
6. **单晶胞拼接**（`createRowOfCells`）：
   - 只支持非 `plugin` 的 2D 网格，否则抛出 `ValueError`；
   - 先建一个晶胞，读出其节点坐标（深度、横向）；晶胞宽度与 `p_x` 之差超过 $10^{-6}\,p_x$ 时抛出 `ValueError`；
   - 把晶胞沿横向复制 $2s + 1$ 份，坐标按 $10^{-9}$ 倍晶胞宽度取整后合并重合节点；合并后的节点数不等于 $(2s+1)N - 2s\,N_{\text{face}}$（$N_{\text{face}}$ 为一个侧面上的节点数）时抛出 `ValueError`，即两个侧面的节点必须一一对应；
   - 中间晶胞的读出电极保留原名；距中间 $k$ 个晶胞的两份读出电极合为 `neighbour<k>`；不读出的电极在所有晶胞上合为一个；整行一个区域，材料 `"gas"`，电极材料 `"metal"`。

### 偏压扫描与收敛

`solver_section.main` 求电场时按以下顺序执行：

1. **包装器件**：`Reading(Detector(...))` 记下求解期间读取的属性、键与网格文件哈希。器件文件有 `frequency` 时覆盖小信号频率；`area_factor` 缺省 `1.0`。HEMT 器件转交 `run_hemt_transport`。
2. **建网格与常数**：见上节；`create_parameter` 写入温度与材料常数、可选 `parameter`、节点模型 `U_const`。
3. **辐照与雪崩**：有 `irradiation` 块且不求权重场时启用辐照项；注量取 `field.irradiation_flux`，为 `null` 时取 `irradiation.irradiation_flux`。雪崩模型取 `avalanche_model`（`has_avalanche` 为假时为 `None`）。
4. **电路**：在 `bias.electrode` 上接电压源 `V1`（直流 `0`，交流幅值 `ac.real`、`ac.imaginary`）。
5. **初值**（`loop_section.initial_solver`）：先只解泊松方程，载流子取本征分布 $n = n_i e^{\psi/V_T}$、$p = n_i^2/n$，用 `initial` 的容差直流求解；再以本征浓度为初值建立式 (1)–(6) 并求解；然后删去本征载流子模型。
6. **零偏压**：在 $0\ \text{V}$ 求解并存盘，写 `0V.dd`、`0V.devsim`，在 `node.json` 的 `solved.potential` 记 `0.0`。
7. **目标与停点**：目标偏压 $V_g$ 取 `field.voltage`，为 `null` 时取 `bias.voltage`。一个场节点对应一个目标偏压；节点里存的中间偏压文件是升压到 $V_g$ 途中的存盘点。存盘点为 $\pm k\Delta_s$（$k = 1, \dots, \lfloor |V_g|/\Delta_s\rfloor$，$\Delta_s$ = `saved_voltage_interval`），末点不足 $|V_g|$ 时补上 $V_g$；曲线点同样按 `curve_voltage_interval` 生成。正负号随 $V_g$。间隔为 `0` 时抛出 `ValueError`。
8. **步进**：初始步长 $\Delta$ = `voltage_step.initial`，符号随 $V_g$。每步试探 $V_t = V_c + \Delta$；若 $|V_t|$ 超过最近的停点（$V_g$、下一个存盘点、下一个曲线点中绝对值最小者），把 $V_t$ 截到该停点。
9. **单步求解**（`loop_solver`）：初值取上一个解；已有两个解时电势按两点线性外推到 $V_t$。设偏压后用 `voltage_step` 的容差直流求解。
10. **成功**：$\Delta \leftarrow \Delta \times$ `increase_factor`。$V_t$ 是曲线点时记录电压、电流 $(I_n + I_p)\times$ `area_factor`（A），以及下节的电容、噪声。$V_t$ 是存盘点或 $V_g$ 时存盘，写 `<V_t>V.dd`、`<V_t>V.devsim`，记入 `solved.potential`；到达 $V_g$ 即结束。
11. **失败**：单步求解出任何 DEVSIM 错误时先写 `last_solvable.dd`。报错信息含 `"Convergence failure"` 时令 $\Delta \leftarrow (V_t - V_c)\times$ `decrease_factor` 后重试；其他 DEVSIM 错误原样抛出。$|\Delta| < 10^{-7}\ \text{V}$ 时停止并抛出 `RuntimeError("Step size too small (less than 1e-7). Exiting loop.")`。
12. **收尾**：在 `node.json` 写 `read`，画 IV 曲线；CV 模式画 CV 与 $1/C^2$ 曲线；打开噪声开关时画噪声曲线。

### 小信号电容与噪声

1. **扫描中的 CV**：CV 模式（`field` 段未单独打开 IV 扫描、单点电容或权重场子任务时的整套求解）在每个曲线点先 `circuit_alter` 到该偏压，再做频率 $f$ 的交流小信号求解：
   $$C = \frac{10^{12}\,\operatorname{Im} I_{V1}}{-2\pi f\,V_{\text{ac}}}\times\texttt{area\_factor}\quad[\text{pF}]$$

   其中 $I_{V1}$ 为偏压电路节点 `V1` 上的交流小信号电流（1D 为 $\text{A/cm}^2$，2D 为 $\text{A/cm}$，3D 为 A），$V_{\text{ac}} = 1\ \text{V}$ 为交流激励的幅值，$f$ 为频率（Hz）。
   结果画进 CV 图；`cv.json` 由下一步的单点电容写出。
2. **单点电容**（`saved_point.capacitance`，单点电容子任务）：读 `<V>V.devsim`（文件名用浮点格式，如 `200.0V.devsim`；不存在时抛出 `FileNotFoundError`，列出已有文件），重建参数，偏压电极置 $V$、其余置 $0$，用 `voltage_step` 的容差直流求解，再做交流求解得比电容 $10^{12}\operatorname{Im} I_{V1}/(-2\pi f)$：1D 为 $\text{pF/cm}^2$，2D 为 $\text{pF/cm}$，3D 为 pF。只有存盘点（`saved_voltage_interval` 的倍数与目标偏压）有 `.devsim` 文件。
3. **噪声**：打开噪声开关时在每个曲线点做 DEVSIM 噪声求解（输出节点 `V1.I`），记录电路节点 `V1.I` 的网格值。

### 权重场求解

1. **前提**：`Conductive_<V_g>V.pkl` 不存在时抛出 `FileNotFoundError`，提示先求该偏压的场。
2. **电极**：读出电极取 `read_out_contact` 的 `name`（所选二维网格的 `ac_contact` 非空时取它的 `name`），每个电极接一个电压源。
3. **行晶胞数**：`read_out_contact` 只有一项且 `read_ele_num > 1` 时，$s$ 取式 (17)。
4. **逐个电极**：只解泊松方程（材料 `"gas"`）；`take_conductors_into_electrodes` 读 `Conductive_<V_g>V.pkl`，每个区域节点按最近邻匹配到文件中的点（拼接行先把横向坐标对晶胞宽度取模），距离超过 $10^{-9}$ 倍网格跨度的节点视为不在网格上，抛出 `ValueError`；然后沿两端都导电的网格边把导电节点连成片，一片里有两个电极的接触节点时抛出 `ValueError`，写明这两个电极、偏压 $V_g$、该片的节点数与坐标范围：这片导电区把两个电极连成一块导体，式 (18) 的互容会被放大约 `CONDUCTOR_PERMITTIVITY` 倍；最后按式 (16) 改写 `PotentialEdgeFlux` 与 `contactcharge_edge`，读出电极置 $1\ \text{V}$ 求解。
5. **行端检查**（$s > 0$）：取两端各一个晶胞内 $|\phi_w|$ 的最大值 $r$，按式 (18) 求互容，`neighbours_coupled` 从 `neighbour1` 起数满足 $C_{\text{neighbour}k} \ge$ `crosstalk_tolerance` $\times\sum_j C_j$ 的连续个数 $c$。若 $r >$ `weighting_tolerance` 或 $c = s$：令 $s' = \lceil 1.5\,s\rceil$；$s' > 2s_0$ 时抛出 `ValueError`（行上权重势不衰减，通常是接触读出电极的导电区所致）；否则清空 DEVSIM（保留 `direct_solver`、`solver_callback`）后以 $s'$ 从头重解。
6. **存盘**：权重势存为 `weightingfield/<contact>/Potential_<V_g>V.pkl`；$s > 0$ 时另写 `Capacitance_<V_g>V.json`；在 `solved.weighting` 记 $V_g$；写 `weightingfield/weightingfield.dat`。

### 存盘

`save_milestone` 按维数与是否权重场分派，跳过材料为 `"Aluminum"` 或 `"air"` 的区域：

1. **节点量**：逐区域收集坐标与 `Potential`、`NetDoping`、`Electrons`、`Holes`、`TrappingRate_n`、`TrappingRate_p`；DEVSIM 场另算 `Conductive`（式 19）。
2. **未耗尽体区**（DEVSIM 场，1D、2D、3D）：按式 (20a) 求 $W_{\text{und}}$ 与比电阻 $r$，写 `<V>V.undepleted.json`，比电容为 $10^{12}\varepsilon/W_{\text{und}}$（$\text{pF/cm}^2$），全耗尽时为 `null`；记入 `solved.undepleted`。
3. **画图**：电势、电子与空穴俘获率（无辐照时不画）、电场。1D 的电场：DEVSIM 场取网格边中点的边电场，TCAD 场取 `ElectricField_0`。2D、3D 的电场画场强 $|\mathbf{E}| = |\nabla\psi|$：在每个网格单元（三角形、四面体）上按节点电势的线性插值求梯度，再按单元面积（体积）加权平均到节点，DEVSIM 场与 TCAD 场相同；权重场同样画 $|\nabla\phi_w|$。
4. **写 pickle**：每个量一个文件；`NetDoping` 只在 $V = 0$ 或 TCAD 场时写。`is_flip` 为真时 2D 的两坐标互换。

### 读取：场节点里的资产

1. **场节点**：偏压、辐照注量、场模式、所选网格及其文件的哈希与 `read` 记下的器件部分（求解期间读到的器件属性、器件文件的键及其值，如 `doping`、`bias`、`irradiation`）都是场节点的输入，节点号由它们的指纹给出（见 [../stages/field.md](../stages/field.md)）；改了其中任何一项就得到新节点。本包从给定的场节点目录 `field/<节点号>/` 读取。
2. **资产检查**：`solved.potential` 或 `solved.weighting` 中没有该偏压时抛出 `FileNotFoundError`。
3. **电容与未耗尽层**：`solved_capacitance` 返回 `specific_capacitance_pF × area_factor × 1e-12`（F）；`solved_undepleted` 返回 $(r/A,\ c\cdot A\cdot10^{-12})$（$\Omega$、F），$A$ 见式 (20)，未耗尽宽度为 `0` 时返回 `None`；对应偏压未求解时抛出 `FileNotFoundError`。
4. **电路取值**（`field_circuit`）：条形器件只列一个读出电极且 `read_ele_num > 1` 时读 `Capacitance_<V>V.json`，文件不存在时抛出 `FileNotFoundError`；其余器件在 `solved.capacitance` 有该偏压时取场电容；所有器件取未耗尽层。

### 插值与缓存

`DevsimField(device_name, voltage, read_out_contact, bounds, resolution, field_directory, interpolation_bins, pitch)` 构造时：

1. **目录**：用 `field_directory` 给出的场节点目录 `field/<节点号>/`。`node.json` 缺失时抛出 `FileNotFoundError`；`axes` 取自其中。
2. **加载**：`NetDoping` 取目录中第一个匹配 `NetDoping_<V>V.pkl` 的文件；`Potential`、`TrappingRate_p`、`TrappingRate_n`、`Conductive` 与各读出电极的权重势取该偏压的文件。文件缺失时抛出 `FileNotFoundError`；文件的维数小于 `axes` 的长度时抛出 `ValueError`。
3. **插值器**：1D 用 `interp1d`（线性，界外报错）；2D 用 `LinearNDInterpolator`（一次 Delaunay 剖分，凸包外为 `NaN`）；3D 用 `interpolate_3d`：
   - 点数不足 2、含非有限值、点形状不是 $N\times3$ 或值数不符时抛出 `ValueError`；所有值相同时返回常数；
   - 点恰好构成完整规则网格（各轴唯一坐标数之积等于点数且无重复）时直接填格；
   - 否则在各轴 $[\min, \max]$ 上取 `field_interpolation_bins` 个等距坐标（缺省 30，少于 2 或出现未知轴时抛出 `ValueError`；某轴无跨度时抛出 `ValueError`），每个格点取 8 个最近邻做反距离平方加权 $\hat v = \sum v_j d_j^{-2}/\sum d_j^{-2}$（$d_j$ 下限 $10^{-15}$，距离 $\le 10^{-15}$ 时取该点值）；
   - 最后用 `RegularGridInterpolator`（线性，界外报错）。
4. **晶胞折回**（`_in_the_cell`）：只列一个读出电极时，对 `bounds` 中给出的非 `z` 轴，若器件宽度大于电势网格跨度的 $1 + 10^{-6}$ 倍，把位置折回网格中的一个晶胞：晶胞宽为该轴的节距（`pitch`，`x` 轴为 `p_x`，`y` 轴为 `p_y`），多晶胞网格取中间一个。电势、掺杂、俘获率、导电标志经折回查询；权重势按原位置查询。加载时核对网格与节距（`_check_mesh_against_pitch`）：电势网格沿 `x` 或 `y` 的跨度小于该轴节距时抛出 `ValueError`；要折回的轴上网格跨度不是节距的整数倍、或没有给出该轴节距时抛出 `ValueError`；报错写明器件名、偏压、轴、网格跨度与节距。
5. **电场**：`get_e_field` 取 $\mathbf{E} = -\nabla\psi$，`gradient` 在每个轴上以 `STEP` 为宽做中心差分；跨出网格端点时截到端点成为单侧差分；点在网格坐标范围外时抛出 `ValueError`。返回 $(E_x, E_y, E_z)$（V/cm），不在 `axes` 中的分量为 $0$。
6. **权重势**：`get_w_p` 的结果 $< 0$ 或 `NaN` 时返回 $0$，$> 1$ 时返回 $1$。
7. **导电标志**：`get_conductive` 在 1D 找位置所在区间，两端点都导电才为真；多维在 Delaunay 剖分中找所在单纯形，所有顶点都导电才为真；位置在网格外时取最近节点的值。
8. **缓存**：`*_cached` 方法把位置（$\mu\text{m}$）按 `resolution` 分箱，箱号 $\lfloor u/r_u\rfloor$ 截到 $[\lfloor u_{\min}/r_u\rfloor,\ \lfloor (u_{\max} - 10^{-12})/r_u\rfloor]$（`bounds` 给出时）；同一箱内复用第一次查询的值。坐标绝对值超过 `max_size` 或非有限时不缓存，直接计算。`resolution` 中非正或非数值的项换回缺省。查询抛错时：电场重新直接计算并让错误抛出；掺杂与俘获率记警告并返回 `0.0`；权重势抛出 `RuntimeError`。
9. **平面增益**（`_integrate_planar_gain`，首次调用后缓存）：`axes` 不含 `"z"` 时抛出 `ValueError`；沿 $(0.5l_x, 0.5l_y)$ 取电势网格的所有深度节点，区间内取常数场 $E_m = -\Delta\psi_m/\Delta z_m$，按式 (10) 精确积分分段常数场，$I_{\text{bd}} \ge 1$ 时抛出 `ValueError`；场最强区间的中点为增益层深度，场方向与增益层位于前后哪一半决定被倍增的载流子极性。各步的详细取法见 [current.md](current.md)。

### TCAD 场的导入

`tcad.import_field(tdr, my_d, folder, asked, flip)`：

1. **偏压**：读 `/collection/geometry_0/state_0` 中名为 `ContactExternalVoltage` 的数据集，取 `bias.electrode` 的电压。文件没有电极电压且 `field.voltage` 为 `null` 时、没有该电极时、或给出的偏压与文件不符时抛出 `ValueError`。
2. **转换网格**：`tdr_reader.read_tdr` 读几何与节点数据集（只读体区域、位于节点上的标量或矢量数据集；元素类型混杂、区域多于一部分等情况抛出 `RuntimeError`），`tdr_import.import_tdr` 建 DEVSIM 网格与节点解（多行数据集命名为 `<name>_<row>`），写 `converted.devsim`。坐标由 $\mu\text{m}$ 乘 `1e-4` 换成 cm。
3. **存场**：`save_milestone(..., is_tcad=True)` 把 `ElectrostaticPotential`、`DopingConcentration`、`eDensity`、`hDensity`、`eGapStatesRecombination`、`hGapStatesRecombination` 存为 `Potential`、`NetDoping`、`Electrons`、`Holes`、`TrappingRate_n`、`TrappingRate_p`。
4. **导电区**：`Aluminum` 区域全部导电；没有 `eDensity`、`hDensity` 的区域不导电；半导体区域缺 `eDensity`、`hDensity`、`DopingConcentration`、`eMobility`、`hMobility` 之一时抛出 `ValueError`；其余按式 (19) 用节点迁移率判定，写 `Conductive_<V>V.pkl`。
5. **权重场**：每个区域的介电常数取 `PERMITTIVITY`（金属取 `1.0`，又是导体），不在表中的材料抛出 `ValueError`；边通量为式 (16)；与电极节点同位置的所有节点（含界面另一侧）以 $10^{20}(\phi - \phi_{\text{held}})$ 钳在电极电势；区域之间电势连续。每个读出电极置 $1$、其余置 $0$ 求解，电极不在文件中时抛出 `ValueError`。
6. **记录**：写 `node.json` 的 `axes`、`read`，在 `solved.potential` 与 `solved.weighting` 记该偏压。

## 软件实现

### 文件分工

- `solver_section.py`：`SOLVER` 缺省设置与求解主流程 `main`（偏压扫描、权重场、行晶胞扩展）。
- `loop_section.py`：`loop_section` 类，初值求解、单步求解与 IV/CV/噪声记录。
- `initial.py`：只含泊松方程与漂移-扩散的初值建模。
- `physics_drift_diffusion.py`：泊松方程、SG 电流、SRH、连续性方程与欧姆/肖特基接触。
- `physics_avalanche.py`：碰撞电离产生率与 SiC 陷阱辅助隧穿项。
- `physics_irradiation.py`：辐照缺陷表、缺陷电荷、复合率与俘获率。
- `create_mesh.py`：`DevsimMesh` 建网格、掺杂与单晶胞拼接；`mesh_axes`。
- `create_parameter.py`：DEVSIM 区域常数。
- `model_create.py`：DEVSIM 节点、边、接触模型的封装（取自 DEVSIM）。
- `weighting.py`：把导电节点并入电极。
- `conductive.py`：导电判定与未耗尽体区。
- `save_milestone.py`：存盘、画图与 `node.json` 记录（`save_record`、`save_solved`）。
- `saved_point.py`：从存盘点求单点小信号电容。
- `reading.py`：`Reading` 包装器，记下求解期间读取的器件部分。
- `solved.py`：读场节点的电容与未耗尽层；`DEFAULT_MODE`（装有 DEVSIM 时为 `"full"`，否则 `"fast"`）。
- `assets.py`：场文件名（`voltage_label`、`field_pickle_path`、`resolve_field_pickle`）。
- `devsim_field.py`：`DevsimField` 插值查询、缓存与平面增益。
- `interpolation.py`：1D/2D/3D 插值器与中心差分函数 `calculate_gradient`。
- `gradient.py`：限定在网格范围内的中心差分梯度。
- `device_circuit.py`：`DeviceCircuit`、`planar_circuit`、`side_by_side`、`row_of_electrodes`。
- `circuit_parameters.py`：结电容、偏置与耦合、未耗尽层、方块电阻的取值，`field_circuit`、`device_circuit`、`part_of_row`、`device_row`、`device_grid`；`undepleted_layer` 按 Riegler 的平板式由面积、厚度、耗尽宽度、介电常数与电阻率给出未耗尽层的 $R$、$C$。
- `resistive_layer.py`：阻性层的行电路 `resistive_row` 与网格电路 `resistive_grid`。
- `implanted_aluminium.py`：铝注入 4H-SiC 层的方块电阻。
- `simple.py`：解析 toy 场。
- `tcad.py`：TDR 场导入与其权重场求解。
- `tdr_reader.py`、`tdr_import.py`：读 TDR 并建 DEVSIM 器件（改写自 DEVSIM LLC 的 tdr-convert 0.1.7，Apache-2.0）。
- `devsim_draw.py`：IV/CV/噪声曲线（`draw_iv(V, I, path)`、`draw_cv(V, C, path)`、`draw_noise(V, noise, path)`，同时写 `simIV`、`simCV`、`simnoise` 的 `.root`）与 1D/2D/3D 场分布图；1D 的剖面由 `draw_profile(x, curves, ylabel, path, name, *suffixes, log=False, boundaries=())` 画进 `<path>/plots`，在 `boundaries` 的各深度画灰色细虚线；分界由 `doping_boundaries(depth, doping)` 取：相邻网格点净掺杂的绝对值相差 10 倍以上处取两点中点，相距不到 0.5 μm 的合并取平均。权重场求解时掺杂换成了常数，权重势、权重场两张图的分界取自场文件夹的 `NetDoping_0V.pkl`；`draw_electrons`、`draw_holes`、`draw_field` 画一维电子、空穴浓度与电场，`save_field` 把电场随深度写成表。
- `hemt_solver_2d_transport_v1.py`：2D AlGaN/GaN HEMT 只含电子的直流转移特性求解分支，由 `solver_section.main` 转交，写 `HEMT_TRANSPORT_*` 文件。
- `plot_hemt_transport_csv.py`：独立脚本，读 `work/AlGaN_GaN_HEMT_TRANSPORT_V1/field`（或环境变量 `RASER_HEMT_FIELD_DIR`）下最新的 `HEMT_TRANSPORT_final_profile.csv` 作图。

### 核心数据结构

- 场 pickle：字典 `{"points", "values", "metadata"}`。`points` 为节点坐标（cm），1D 为长 $N$ 的数组，2D、3D 为 $N$ 个 `[u, v]` 或 `[u, v, w]` 列表，顺序同 `axes`；`values` 为长 $N$ 的 `float64` 数组，单位随量；`metadata` 含 `voltage`（V）、`dimension`，权重势另可含 `cells_either_side`（2D 拼接行）或 `contact_name`（3D）。
- `node.json`：本包写 `axes`（列表）、`read`（`{"attributes", "keys", "files"}`，值为数、字符串、`null` 或 `"sha256:<hex>"`，缺失项记 `["absent"]`）、`solved`（`potential`、`weighting`、`capacitance`、`undepleted` 各为已求偏压列表，V）。节点的其余输入、代码版本、运行环境与运行状态由 [../stages/field.md](../stages/field.md) 的命令写入。
- `DevsimField`：`axes`；`resolution`（$\mu\text{m}$）；`potential_ranges`、`weighting_ranges`（各轴端点，cm）；`cells_either_side`；五个缓存字典；`WeightingPotential`（各读出电极的插值器列表）。
- `DeviceCircuit`：`lines`（SPICE 元件行，地为节点 `0`，电容 F、电阻 $\Omega$）、`sources`（电极名到感应电流源节点对 `(from, to)`）、`outputs`（读出名到第一级放大器输入节点）、`alike`（噪声谱相同的输出分组）。`device_circuit` 等函数另返回记录字典，写明各值及其来源（`"device file"`、`"field"`、`"parallel plate"`、`"chosen"`、`"implanted layer"`）。

## 接口

使用者能设的是下表中器件文件的键，以及 `field.solver` 下的求解器设置；网格不在器件文件里，用哪一套由 `field` 段的设置指定；其余参数写死在代码里。命令行用法见 [../stages/field.md](../stages/field.md)，器件文件的通用写法见 [../components/device.md](../components/device.md)。

### 器件文件读取的键

| 键 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `det_name`, `default_dimension`, `field_dimension` | 见 [device.md](device.md) | 无 | 器件名与求解维数（1、2、3） |
| `l_x`, `l_y`, `l_z` | 无（必选） | $\mu\text{m}$ | 器件尺寸；`l_z` 用于式 (17)，`l_y` 为条长 |
| `electrodes`, `p_x`, `p_y`, `read_ele_num`, `x_ele_num`, `y_ele_num` | 见 [device.md](device.md) | $\mu\text{m}$ / 个 | 电极布局；`p_x` 为拼接晶胞宽度 |
| `area_factor` | `1.0` | 1D $\text{cm}^2$，2D cm，3D 无 | 网格比电流、比电容换成器件值的因子 |
| `temperature` | 无（必选） | K | 器件温度 |
| `material` | 无（必选） | 无 | 器件材料，决定式 (18) 的 $\varepsilon_r$ 与平面增益的系数 |
| `bias.electrode`, `bias.voltage` | 无（必选） | 无, V | 偏压电极与 `field.voltage` 为 `null` 时的目标偏压 |
| `read_out_contact` | 无（必选） | 无 | 读出电极列表，每项含 `name`，可选 `x_span`、`y_span`（晶胞跨度） |
| `doping.Acceptors`, `doping.Donors` | 无（必选） | $\text{cm}^{-3}$ | DEVSIM 表达式 |
| `doping.Acceptors_ir`, `doping.Donors_ir` | 无 | $\text{cm}^{-3}$ | 叠加的附加掺杂表达式 |
| `irradiation.irradiation_model` | 无块时 `None` | 无 | `"XingChen"`、`"Perugia"`、`"Schwandt"`、`"CommonDefect"`；其他名字为空缺陷表 |
| `irradiation.irradiation_flux` | 无块时 `0` | $\text{cm}^{-2}$ | `field.irradiation_flux` 为 `null` 时的注量 |
| `avalanche_model`, `enable_gain` | `None`, `False` | 无 | 两者都有效时启用式 (7) |
| `parameter` | 无 | 依参数 | 一个 `{"name", "value"}` 对象，在材料常数之后写入器件区域的一个 DEVSIM 区域参数，如 `{"name": "mu_n", "value": 1350}`、`{"name": "F_sat", "value": 2e5}`；一个器件文件写一个参数 |
| `U_const` | `0` | $\text{cm}^{-3}\,\text{s}^{-1}$ | 附加复合率（数值或表达式） |
| `frequency` | `ac.frequency` | Hz | 小信号与噪声频率 |
| `field.solver` | `SOLVER` | 见下表 | 逐层覆盖求解器设置 |
| `hemt_physics.transport_model` | 无 | 无 | `"drift_diffusion_v1"` 时转交 HEMT 求解 |
| `field_interpolation_bins` | `None`（各轴 `30`） | 个 | 3D 非规则点云的规则化箱数，按轴名给的字典，如 `{"x": 60, "y": 60, "z": 60}`；只给某些轴时其余轴取 `30`（由 [../stages/current.md](../stages/current.md) 传入） |
| `capacitance_pF` | 无 | pF | 单电极结电容，优先于场 |
| `depletion_depth` | `l_z` | $\mu\text{m}$ | 平行板估计的耗尽深度 |
| `bias_resistance_ohm` | `None` | $\Omega$ | 单电极偏置电阻 |
| `coupling_capacitance_pF` | `None` | pF | 单电极耦合电容，需同时给 `bias_resistance_ohm`，否则抛出 `ValueError` |
| `undepleted_resistance_ohm`, `undepleted_capacitance_pF` | `None` | $\Omega$, pF | 未耗尽层，必须成对给出 |
| `resistive_layer.sheet_resistance` | 无 | $\Omega$ | 方块电阻 |
| `resistive_layer.implanted`, `.thickness`, `.anneal` | 无 | $\text{cm}^{-2}$, $\mu\text{m}$, $^\circ\text{C}$ | 无 `sheet_resistance` 时按式 (22) 计算 |
| `resistive_layer.strips` | 无 | 晶胞号 | 行电路：条名到首末晶胞号 `[first, last]` |
| `resistive_layer.pads` | 无 | 晶胞号 | 网格电路：电极名到 `[x_first, x_last, y_first, y_last]` |
| `resistive_layer.grounded` | `{}` | 晶胞号 | 接地触点；行为 `[first, last]`，网格为矩形列表 |
| `resistive_layer.coupling.thickness`, `.permittivity` | 无 | $\mu\text{m}$, 无 | 电极下介质层 |
| `det_model` | 无 | 无 | 选解析场类型；含 `"3d"` 时 `Detector.capacitance` 在没有 `capacitance_pF` 时为 `None` |
| `depletion_voltage`, `input_doping` | `|bias.voltage|`, `1e12` | V, $\text{cm}^{-3}$ | 解析场 |
| `column_radius_um`, `column_cell_x_um`, `column_cell_y_um`, `readout_column_x_um`, `readout_column_y_um`, `ground_columns_um`, `relative_permittivity`, `weighting_series_terms` | 必选、`2*p_x`、`2*p_y`、晶胞中心、晶胞中心、四角、`11.9`、`100` | $\mu\text{m}$ / 无 | 解析场（三维柱与条/像素） |

### 求解器设置 `SOLVER`

器件文件写 `"field": {"solver": {...}}`，按下表的键路径嵌套，逐层叠在缺省设置上，只写要改的键，例如 `"field": {"solver": {"voltage_step": {"initial": 0.2, "decrease_factor": 0.25}, "saved_voltage_interval": 50.0}}`。

| 键路径 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `initial.absolute_error`, `.relative_error`, `.maximum_iterations` | `1e10`, `1e-4`, `100` | 无, 无, 次 | 初值求解 |
| `voltage_step.absolute_error`, `.relative_error`, `.maximum_iterations` | `1e20`, `1e-4`, `100` | 无, 无, 次 | 偏压步与单点电容的直流求解 |
| `voltage_step.initial` | `1.0` | V | 初始步长 |
| `voltage_step.increase_factor`, `.decrease_factor` | `2.0`, `0.5` | 无 | 成功放大、失败缩小倍数 |
| `saved_voltage_interval` | `100.0` | V | 存盘间隔 |
| `curve_voltage_interval` | `10.0` | V | IV/CV/噪声曲线点间隔 |
| `ac.real`, `ac.imaginary` | `1.0`, `0.0` | V | 小信号激励 |
| `ac.frequency` | `1000.0` | Hz | 小信号频率 |
| `weighting_tolerance` | `5e-2` | 无 | 行端残留权重势上限 $\delta$ |
| `crosstalk_tolerance` | `5e-2` | 无 | 判为耦合的互容占比下限 |

### 输出文件

文件写入场节点目录 `work/<device>/field/<节点号>/`。pickle 与 `Capacitance_*.json` 的偏压用 `voltage_label`（整数值写成整数，如 `Potential_200V.pkl`）；`.devsim`、`.dd`、`.undepleted.json`、`.cv.json` 用浮点格式（如 `200.0V.devsim`、`0.0V.undepleted.json`），零偏压的状态文件为 `0V.devsim`、`0V.dd`。负偏压照此带负号，如 `Potential_-100V.pkl`、`-100.0V.devsim`。

| 文件 | 内容、形状、类型 | 单位 |
| --- | --- | --- |
| `node.json` | `axes`、`read`、`solved`，见核心数据结构 | 偏压 V |
| `Potential_<V>V.pkl` | 节点电势，`values` 为 `(N,)` `float64` | `points` cm；V |
| `Electrons_<V>V.pkl`, `Holes_<V>V.pkl` | 电子、空穴浓度 | cm；$\text{cm}^{-3}$ |
| `TrappingRate_n_<V>V.pkl`, `TrappingRate_p_<V>V.pkl` | 电子、空穴俘获率 | cm；$\text{s}^{-1}$ |
| `Conductive_<V>V.pkl` | 导电标志，`1.0` 或 `0.0` | cm；无 |
| `NetDoping_0V.pkl`（TCAD 为 `NetDoping_<V>V.pkl`） | 净掺杂 | cm；$\text{cm}^{-3}$ |
| `<V>V.undepleted.json` | DEVSIM 场：`voltage_V`、`undepleted_width_um`、`specific_resistance_ohm_cm2`、`specific_capacitance_pF`（全耗尽为 `null`）、`per`（`"cm^2"`） | V、$\mu\text{m}$、$\Omega\cdot\text{cm}^2$、$\text{pF/cm}^2$ |
| `<V>V.cv.json` | 单点电容子任务写出：`voltage_V`、`specific_capacitance_pF`、`per`（`"cm^2"`、`"cm"`、`"device"`）、`area_factor`、`frequency_Hz` | V、pF/单位、—、Hz |
| `weightingfield/<contact>/Potential_<V>V.pkl` | 权重势 | cm；无 |
| `weightingfield/<contact>/Capacitance_<V>V.json` | 拼接行：`unit`（`"F/cm"`）、`of`、`total`、`to`（`neighbour<k>` 及不读出的电极）、`neighbours_coupled` | F/cm |
| `<V>V.devsim`, `<V>V.dd`, `0V.devsim`, `0V.dd` | DEVSIM 状态（供单点电容重载）与 Tecplot 数据 | cm, V |
| `<det_name>.dat`, `weightingfield/weightingfield.dat`, `last_solvable.dd`, `converted.devsim` | 网格、权重场、收敛失败前一状态、TCAD 转换结果 | cm, V |
| `simIV<min>to<max>.root` | TTree `SicarTestIV`，分支 `voltage`、`Current` | V, A |
| `simCV<min>to<max>.root` | TTree `SicarTestCV`，分支 `voltage`、`CAP` | V, pF |
| `simnoise<min>to<max>.root` | TTree `SicarTestnoise`，分支 `voltage`、`Current` | V, — |
| `HEMT_TRANSPORT_IdVg.csv`, `HEMT_TRANSPORT_final_profile.csv`, `HEMT_TRANSPORT_final.devsim`, `HEMT_TRANSPORT_summary.json` | HEMT 分支的转移特性、末态剖面、状态与摘要 | V, mA/mm, $\text{cm}^{-3}$ |

### 画出的图

1D、2D、3D 器件的图都存进场节点目录的 `plots/`，样式见[出图（`supports/figures`）](../supports/figures.md)。

| 文件 | 内容 | 坐标单位 |
| --- | --- | --- |
| `plots/iv.png/.pdf` | IV 曲线：反向偏压（取绝对值）对漏电流（取绝对值），对数纵轴；比整条曲线的中位数低 6 个数量级以上的离群点（例如 pA 量级曲线上 0 V 的那一点）图上不画，`simIV` 文件里照旧保留；整条曲线都很小时照原样画；轴 `Reverse bias [V]`、`Leakage current [A]` | V, A |
| `plots/cv.png/.pdf` | 左：电容随反向偏压，轴 `Capacitance [pF]`；右：$1/C^2$ 随反向偏压，轴 `1/C² [pF⁻²]`；横轴 `Reverse bias [V]` | V, pF, $\text{pF}^{-2}$ |
| `plots/noise.png/.pdf` | 噪声电流随反向偏压，对数纵轴 `Noise current [A]` | V, A |
| `plots/doping.png/.pdf` | 1D 施主、受主浓度沿深度，对数纵轴；轴 `Depth [μm]`、`Doping [cm⁻³]` | μm, $\text{cm}^{-3}$ |
| `plots/potential_<V>V`, `plots/electric_field_<V>V`, `plots/trapping_rate_<V>V`（均有 `.png/.pdf`） | 1D 每档偏压的电势 `Potential [V]`、电场 `Electric field [kV/cm]`、电子（蓝）与空穴（红）俘获率同画一张，对数纵轴 `Trapping rate [s⁻¹]`；两者全为零（无辐照）时不画俘获率；`<V>` 写成最短形式（`200.0` 写作 `200`） | μm；V、kV/cm、$\text{s}^{-1}$ |
| `plots/weighting_potential_<contact>_<V>V`, `plots/weighting_field_<contact>_<V>V`（均有 `.png/.pdf`） | 1D 每个读出电极、每档算了权重场的偏压的权重势 `Weighting potential`、权重场 `Weighting field [cm⁻¹]`；与其他图同在 `plots/`，不在 `weightingfield/<contact>/` 下 | μm；无、$\text{cm}^{-1}$ |
| `plots/potential_<V>V`, `plots/electric_field_<V>V`（均有 `.png/.pdf`） | 2D、3D 每档偏压一张，三幅并排：左为二维切面（viridis 色图，色标为该量），中为深度剖面，右为横向剖面；轴 `Potential [V]`、`Electric field [kV/cm]` | μm；V、kV/cm |
| `plots/trapping_rate_<V>V`（`.png/.pdf`） | 2D、3D 电子（蓝）与空穴（红）俘获率的深度剖面，同画一张，对数纵轴；全为零（无辐照）时不画 | μm；$\text{s}^{-1}$ |
| `plots/weighting_potential_<contact>_<V>V`, `plots/weighting_field_<contact>_<V>V`（均有 `.png/.pdf`） | 2D、3D 每个读出电极的权重势、权重场，三幅同上；轴 `Weighting potential`、`Weighting field [cm⁻¹]` | μm；无、$\text{cm}^{-1}$ |
| `HEMT_TRANSPORT_IdVg.png/.pdf` | HEMT 转移特性 | V, mA/mm |

2D、3D 图的切面与剖面按 `mesh_axes` 取，轴标题写器件的轴：横向为 `x [μm]`、`y [μm]`，深度为 `Depth [μm]`。“中点”指该坐标在网格上的最小值与最大值的平均。

- 深度与 $x$ 的网格 `("z", "x")`：切面为整张网格；深度剖面取在 $x$ 的中点，横向剖面沿 $x$、取在深度的中点。
- 横截面网格 `("x", "y")`：切面为整张网格；没有深度，两条剖面分别沿 $x$（取在 $y$ 的中点）、沿 $y$（取在 $x$ 的中点）。
- 3D：切面为过 $y$ 中点的 $x$-$z$ 平面；深度剖面取在 $x$、$y$ 的中点，横向剖面沿 $x$、取在 $y$ 与深度的中点。
- 权重势、权重场：深度剖面取在该读出电极各节点横向坐标的平均处，即电极正下方；拼成一行晶胞时即中间晶胞的电极。
- 剖面和 3D 切面上的值在网格单元上线性插值得到。

## 参考文献

- [1] D. L. Scharfetter, H. K. Gummel, “Large-signal analysis of a silicon Read diode oscillator”, IEEE Trans. Electron Devices 16 (1969) 64, doi:10.1109/T-ED.1969.16566
- [2] S. M. Sze, K. K. Ng, *Physics of Semiconductor Devices*, 3rd ed., Wiley-Interscience (2007), sec. 1.5.4, doi:10.1002/0470068329
- [3] J. E. Sanchez, “DEVSIM: A TCAD Semiconductor Device Simulator”, J. Open Source Softw. 7 (2022) 3898, doi:10.21105/joss.03898
- [4] R. van Overstraeten, H. de Man, “Measurement of the ionization rates in diffused silicon p-n junctions”, Solid-State Electronics 13 (1970) 583, doi:10.1016/0038-1101(70)90139-5
- [5] T. Hatakeyama, T. Watanabe, T. Shinohe, K. Kojima, K. Arai, N. Sano, “Impact ionization coefficients of 4H silicon carbide”, Appl. Phys. Lett. 85 (2004) 1380, doi:10.1063/1.1784520
- [6] G. A. M. Hurkx, D. B. M. Klaassen, M. P. G. Knuvers, “A new recombination model for device simulation including tunneling”, IEEE Trans. Electron Devices 39 (1992) 331, doi:10.1109/16.121690
- [7] R. J. McIntyre, “Multiplication noise in uniform avalanche diodes”, IEEE Trans. Electron Devices ED-13 (1966) 164, doi:10.1109/T-ED.1966.15651
- [8] W. Shockley, “Currents to Conductors Induced by a Moving Point Charge”, J. Appl. Phys. 9 (1938) 635, doi:10.1063/1.1710367
- [9] S. Ramo, “Currents Induced by Electron Motion”, Proc. IRE 27 (1939) 584, doi:10.1109/JRPROC.1939.228757
- [10] W. Riegler, “An application of extensions of the Ramo–Shockley theorem to signals in silicon sensors”, Nucl. Instrum. Methods Phys. Res. A 940 (2019) 453, eq. 50, doi:10.1016/j.nima.2019.06.056, arXiv:1812.07570
- [11] M. Spera, D. Corso, S. Di Franco, G. Greco, A. Severino, P. Fiorenza, F. Giannazzo, F. Roccaforte, “Effect of high temperature annealing (T > 1650 °C) on the morphological and electrical properties of p-type implanted 4H-SiC layers”, Mater. Sci. Semicond. Process. 93 (2019) 274, doi:10.1016/j.mssp.2019.01.019, arXiv:2001.08021
- [12] S. Spannagel et al., “Allpix²: A modular simulation framework for silicon detectors”, Nucl. Instrum. Methods Phys. Res. A 901 (2018) 164, doi:10.1016/j.nima.2018.06.020
- [13] K. K. Thornber, “Applications of scaling to problems in high-field electronic transport”, J. Appl. Phys. 52 (1981) 279, doi:10.1063/1.328490
- [14] A. O. Konstantinov, Q. Wahab, N. Nordell, U. Lindefelt, “Ionization rates and critical fields in 4H silicon carbide”, Appl. Phys. Lett. 71 (1997) 90, doi:10.1063/1.119478
- [15] J. Schwandt, E. Fretwurst, E. Garutti, R. Klanner, C. Scharf, G. Steinbrück, “A new model for the TCAD simulation of the silicon damage by high fluence proton irradiation”, 2018 IEEE NSS/MIC, doi:10.1109/NSSMIC.2018.8824412, arXiv:1904.10234
- [16] X. Li et al., “Simulation of radiation damage effect on silicon detectors using RASER”, JINST 20 (2025) P12009, doi:10.1088/1748-0221/20/12/P12009, arXiv:2504.20463
- [17] M. Petasecca, F. Moscatelli, D. Passeri, G. U. Pignatel, “Numerical simulation of radiation damage effects in p-type and n-type FZ silicon detectors”, IEEE Trans. Nucl. Sci. 53 (2006) 2971, doi:10.1109/TNS.2006.881910
- [18] W. Riegler, G. Aglieri Rinella, “Point charge potential and weighting field of a pixel or pad in a plane condenser”, Nucl. Instrum. Methods Phys. Res. A 767 (2014) 267, doi:10.1016/j.nima.2014.08.044；显式级数见 W. Riegler, “Time resolution of silicon pixel sensors”, JINST 12 (2017) P11017, 附录 E, doi:10.1088/1748-0221/12/11/P11017
- [19] J. D. Jackson, *Classical Electrodynamics*, 3rd ed., Wiley (1999), sec. 3.12
- [20] A. Das, S. P. Duttagupta, “TCAD simulation for alpha-particle spectroscopy using SiC Schottky diode”, Radiat. Prot. Dosim. 167 (2015) 443, doi:10.1093/rpd/ncu369
- [21] Z. Li et al., “Mechanisms of proton irradiation-induced defects on the electrical performance of 4H-SiC PIN detectors”, JINST 21 (2026) P03010, doi:10.1088/1748-0221/21/03/P03010, arXiv:2503.09016
- [22] S. Mägdefessel, R. Mori, N. Sorgenfrei, U. Parzefall, “Understanding the frequency dependence of capacitance measurements of irradiated silicon detectors”, arXiv:2301.09371, eqs. (2), (3)
