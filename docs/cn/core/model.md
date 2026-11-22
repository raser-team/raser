# 材料与物理模型（`core/model`）

`src/raser/core/model/` 接收 [器件定义](device.md) 从 [探测器组件](../components/device.md) 解析出的材料名 `material`、工作温度 `temperature`、掺杂浓度与碰撞电离模型名 `avalanche_model`，以及 [器件场](field.md) 和 [载流子输运](current.md) 传入的局部电场强度与载流子浓度。该包定义硅（`"Si"`）、4H 碳化硅（`"SiC"`）与金刚石（`"Diamond"`）的相对介电常数、有效质量、载流子迁移率、碰撞电离系数、能带结构、本征载流子浓度、杂质不完全电离与 Shockley-Read-Hall（SRH）复合模型，并通过 `Formula` 将同一套物理表达式同时编译为 Python 数值求值函数与 DEVSIM 符号方程。计算出的相对介电常数交给 [器件定义](device.md) 估算平行板结电容并交给 [器件场](field.md) 求解泊松方程与条间互容，能带、SRH 复合、不完全电离与碰撞电离的符号表达式和材料参数交给 [器件场](field.md) 执行 DEVSIM 漂移-扩散求解、一维平板雪崩增益积分与铝注入阻性层方阻计算，迁移率与碰撞电离系数的 Python 数值结果交给 [载流子输运](current.md) 计算载流子漂移、热扩散与多维路径雪崩倍增。

## 物理

### 介电常数与有效质量

半导体的静态相对介电常数决定给定空间电荷下的静电势分布与几何电容，电子与空穴有效质量表征载流子在晶格周期势场中对外力的惯性响应。材料介电常数与有效质量由自由空间基准常数按比例给出：

$$\varepsilon = \varepsilon_r \varepsilon_0, \qquad m_n^* = \left(\frac{m_n^*}{m_e}\right) m_e, \qquad m_p^* = \left(\frac{m_p^*}{m_e}\right) m_e \tag{1}$$

其中：

- $\varepsilon$：材料介电常数，在 DEVSIM 场求解中单位为 $\text{F/cm}$，在平行板电容估算中单位为 $\text{F/m}$；
- $\varepsilon_r$：无量纲相对介电常数（代码中为 `RELATIVE_PERMITTIVITY` 与 `Material.permittivity`），`"Si"` 取 `11.9`，`"SiC"`（4H-SiC，沿 $c$ 轴）取 `9.76`，`"Diamond"` 取 `5.7`；
- $\varepsilon_0$：真空介电常数，取 $8.8541878128\times 10^{-12}\ \text{F/m}$（CODATA 2018；在 DEVSIM 场求解中以 $\text{F/cm}$ 计为 $8.8541878128\times 10^{-14}\ \text{F/cm}$）；
- $m_e$：自由电子静止质量，代码中取 $9.109\times 10^{-31}\ \text{kg}$；
- $m_n^*, m_p^*$：电子与空穴有效质量，$\text{kg}$（代码中为 `Material.electron_mass` 与 `Material.hole_mass`）。

各材料在 `Material.mat_database`（`material.py`）中的基础物性与缺省选用的模型如下表：

| 材料名（`mat_name`） | 相对介电常数 `RELATIVE_PERMITTIVITY` | 电子有效质量 `electron_mass`（$\text{kg}$） | 空穴有效质量 `hole_mass`（$\text{kg}$） | 缺省 `mobility_model` | 缺省 `avalanche_model` |
| --- | --- | --- | --- | --- | --- |
| `"Si"` | `11.9` | `0.26 * m_e` | `0.386 * m_e` | `"Selberherr"` | `"vanOverstraeten"` |
| `"SiC"` | `9.76` | `0.29 * m_e` | `1.0 * m_e` | `"Das"` | `"Hatakeyama"` |
| `"Diamond"` | `5.7` | 未设置 | 未设置 | `"Pernegger"` | `None` |

相对介电常数定义在 `material.py` 的全局字典 `RELATIVE_PERMITTIVITY` 中，并在 `Material(mat_name).mat_database()` 中赋给 `self.permittivity`；有效质量在 `Material.mat_database()` 中赋给 `self.electron_mass` 与 `self.hole_mass`（`"SiC"` 取 4H-SiC 纵向有效质量，`"Diamond"` 未设置）。在调用关系上，[device.md](device.md) 的 `Detector.capacitance`（`src/raser/core/device/build_device.py`）读取 `Material(self.material).permittivity` 估算平行板结电容；[field.md](field.md) 的 `CreateSiliconConstant`、`CreateSiliconCarbideConstant`、`CreateDiamondConstant`（`src/raser/core/field/create_parameter.py`）读取 `RELATIVE_PERMITTIVITY` 设置 DEVSIM 区域参数 `eps` 与 `Permittivity`；[field.md](field.md) 的 `capacitances`（`src/raser/core/field/solver_section.py`）读取 `Material(MyDetector.material).permittivity`，将真空介电常数下求得的权重场接触电荷换算为周期性条形电极的单位长度互容（$\text{F/cm}$）。硅的相对介电常数见文献 [1]（附录 G）。

### 迁移率

载流子在低电场下受晶格声子散射（`L`）与电离杂质散射（`I`）共同决定低场迁移率 $\mu_{LI}$，在高电场驱动（`F`）下漂移速度趋近饱和速度 $v_{\text{sat}}$，使有效迁移率 $\mu(T, N_{\text{eff}}, E)$ 随场强升高而降低。近似：迁移率只由这三项决定，载流子-载流子散射（`C`）与表面散射（`S`）略去。定义对 $300\ \text{K}$ 归一化的无量纲温度为：

$$t = \frac{T}{300} \tag{2}$$

对于硅（`"Si"`）的缺省 `"Selberherr"` 模型，低场迁移率采用 Caughey–Thomas 形式，高场饱和分别按空穴（$\beta_p = 1.0$）与电子（$\beta_n = 2$）给出：

$$\mu_{LI} = \mu_{\min} + \frac{\mu_L - \mu_{\min}}{1 + \bigl(|N_{\text{eff}}| / C_{\text{ref}}\bigr)^{\alpha}} \tag{3}$$

$$\mu_p(T, N_{\text{eff}}, E) = \frac{\mu_{LI,p}}{1 + \mu_{LI,p} E / v_{\text{sat},p}} \tag{4}$$

$$\mu_n(T, N_{\text{eff}}, E) = \frac{2\mu_{LI,n}}{1 + \Bigl[1 + \bigl(2\mu_{LI,n} E / v_{\text{sat},n}\bigr)^{\beta_n}\Bigr]^{1/\beta_n}} \tag{5}$$

对于 4H 碳化硅（`"SiC"`）的缺省 `"Das"` 模型，低场杂质散射项分子直接取 $\mu_L$（不减 $\mu_{\min}$），高场饱和采用 Canali 形式；金刚石（`"Diamond"`）的缺省 `"Pernegger"` 模型取 $\mu_{LI} = \mu_L$，与温度和掺杂无关，高场饱和是式 (7) 取 $\beta = 1$：

$$\mu_{LI} = \mu_{\min} + \frac{\mu_L}{1 + \bigl(|N_{\text{eff}}| / C_{\text{ref}}\bigr)^{\alpha}} \tag{6}$$

$$\mu(T, N_{\text{eff}}, E) = \frac{\mu_{LI}}{\Bigl[1 + \bigl(\mu_{LI} E / v_{\text{sat}}\bigr)^{\beta}\Bigr]^{1/\beta}} \tag{7}$$

对于硅（`"Si"`）的备选 `"Reggiani"` 模型，代码按输入净掺杂 `input_doping` 的符号区分施主浓度 $N_D = \max(N_{\text{eff}}, 0)$ 与受主浓度 $N_A = \max(-N_{\text{eff}}, 0)$，计入超高掺杂下的第二级下降项 $\mu_1$：

$$\mu_0 = \frac{\mu_{0,d} N_D + \mu_{0,a} N_A}{N_D + N_A}, \qquad \mu_1 = \frac{\mu_{1,d} N_D + \mu_{1,a} N_A}{N_D + N_A} \tag{8}$$

$$\mu_{LI} = \mu_0 + \frac{\mu_L - \mu_0}{1 + (N_D / C_{r,d})^{\alpha_d} + (N_A / C_{r,a})^{\alpha_a}} - \frac{\mu_1}{1 + (N_D / C_{s,d} + N_A / C_{s,a})^2} \tag{9}$$

$$\mu_p(T, N_{\text{eff}}, E) = \frac{\mu_{LI,p}}{\Bigl[1 + \bigl(\mu_{LI,p} E / v_{\text{sat},p}\bigr)^{\beta_{p,1} + \beta_{p,2}}\Bigr]^{1/\beta_{p,1}}}, \qquad \mu_n(T, N_{\text{eff}}, E) = \frac{\mu_{LI,n}}{\Bigl[1 + \bigl(\mu_{LI,n} E / v_{\text{sat},n}\bigr)^{\beta_n}\Bigr]^{1/\beta_n}} \tag{10}$$

其中：

- $T$：器件温度（`temperature`），$\text{K}$；$t = T/300$ 为无量纲归一化温度；
- $N_{\text{eff}}$：局部有效净掺杂浓度（`input_doping`），$\text{cm}^{-3}$；$N_D, N_A$ 为 `"Reggiani"` 模型按 $N_{\text{eff}}$ 正负号拆分出的施主与受主浓度，$\text{cm}^{-3}$；
- $E$：电场强度（`electric_field`），$\text{V/cm}$；
- $\mu_L$：纯晶格声子散射迁移率，$\text{cm}^2/(\text{V}\cdot\text{s})$（空穴带下标 $p$，电子带下标 $n$）；
- $\mu_{\min}, \mu_0, \mu_1$：重掺杂极限下的基准与修正迁移率，$\text{cm}^2/(\text{V}\cdot\text{s})$（下标 $d, a$ 分别对应施主与受主）；
- $C_{\text{ref}}, C_{r,d}, C_{r,a}, C_{s,d}, C_{s,a}$：杂质散射特征参考掺杂浓度，$\text{cm}^{-3}$；
- $\alpha, \alpha_d, \alpha_a$：杂质散射无量纲幂指数；
- $v_{\text{sat}}$：高场饱和漂移速度，$\text{cm/s}$；
- $\beta, \beta_{p,1}, \beta_{p,2}$：高场速度饱和过渡区无量纲幂指数；
- $\mu_{LI}, \mu$：低场掺杂修正迁移率与含高场饱和的总迁移率，$\text{cm}^2/(\text{V}\cdot\text{s})$。

三种材料缺省选用的模型（`"Selberherr"`、`"Das"`、`"Pernegger"`，对应式 (3)–(7)）的全部参数取值如下表：

| 材料与模型 | 载流子（`charge`） | $\mu_L$（$\text{cm}^2/(\text{V}\cdot\text{s})$） | $\mu_{\min}$（$\text{cm}^2/(\text{V}\cdot\text{s})$） | $C_{\text{ref}}$（$\text{cm}^{-3}$） | $\alpha$（无量纲） | $\beta$（无量纲） | $v_{\text{sat}}$（$\text{cm/s}$） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `"Si"` / `"Selberherr"` | 空穴（`> 0`） | $460.0\,t^{-2.18}$ | $45.0\,t^{-0.45}$ | $2.23\times 10^{17}\,t^{3.2}$ | $0.72\,t^{0.065}$ | $1.0$ | $9.05\times 10^6\sqrt{\tanh(312.0/T)}$ |
| `"Si"` / `"Selberherr"` | 电子（`<= 0`） | $1430.0\,t^{-2.0}$ | $80.0\,t^{-0.45}$ | $1.12\times 10^{17}\,t^{3.2}$ | $0.72\,t^{0.065}$ | $2$ | $1.45\times 10^7\sqrt{\tanh(155.0/T)}$ |
| `"SiC"` / `"Das"` | 空穴（`> 0`） | $124\,t^{-2}$ | $15.9$ | $1.76\times 10^{19}$ | $0.34$ | $1.213\,t^{0.17}$ | $2\times 10^7\,t^{0.52}$ |
| `"SiC"` / `"Das"` | 电子（`<= 0`） | $947\,t^{-2}$ | $0$ | $1.94\times 10^{17}$ | $0.61$ | $1\cdot t^{0.66}$ | $2\times 10^7\,t^{0.87}$ |
| `"Diamond"` / `"Pernegger"` | 空穴（`> 0`） | $2064$ | $0$ | — | — | $1$ | $1.41\times 10^7$ |
| `"Diamond"` / `"Pernegger"` | 电子（`<= 0`） | $1714$ | $0$ | — | — | $1$ | $0.96\times 10^7$ |

硅的备选 `"Reggiani"` 模型（对应式 (8)–(10)）的全部参数取值如下表：

| 参数 | 空穴（`charge > 0`） | 电子（`charge <= 0`） | 单位 |
| --- | --- | --- | --- |
| $\mu_L$ | $470.50\,t^{-2.16}$ | $1441.0\,t^{-2.45 + 0.07t}$ | $\text{cm}^2/(\text{V}\cdot\text{s})$ |
| $\mu_{0,d}, \mu_{0,a}$ | $90.0\,t^{-1.3},\; 44.0\,t^{-0.8}$ | $62.2\,t^{-1.3},\; 132.0\,t^{-1.3}$ | $\text{cm}^2/(\text{V}\cdot\text{s})$ |
| $\mu_{1,d}, \mu_{1,a}$ | $28.2\,t^{-2.0},\; 28.2\,t^{-0.2}$ | $48.6\,t^{-0.7},\; 73.5\,t^{-1.25}$ | $\text{cm}^2/(\text{V}\cdot\text{s})$ |
| $\alpha_d, \alpha_a$ | $0.77,\; 0.719$ | $0.68,\; 0.72$ | 无量纲 |
| $C_{r,d}, C_{r,a}$ | $1.30\times 10^{18}\,t^{2.2},\; 2.45\times 10^{17}\,t^{3.1}$ | $8.30\times 10^{16}\,t^{3.65},\; 1.22\times 10^{17}\,t^{2.65}$ | $\text{cm}^{-3}$ |
| $C_{s,d}, C_{s,a}$ | $1.10\times 10^{18}\,t^{6.2},\; 6.10\times 10^{20}$ | $4\times 10^{20},\; 7\times 10^{20}$ | $\text{cm}^{-3}$ |
| $\beta_{p,1}$ 或 $\beta_n$ | $2\,t^{-0.2} + \dfrac{0.6 N_A^2}{N_A^2 + (8\times 10^{17})^2} + \dfrac{0.6 N_D^2}{N_D^2 + (10^{19})^2}$ | $2.1\,t^{-0.2} + \dfrac{2 N_A^2}{N_A^2 + (10^{19})^2} + \dfrac{3 N_D^2}{N_D^2 + (10^{19})^2}$ | 无量纲 |
| $\beta_{p,2}$ | $0.15\,t + \dfrac{0.8 N_A^2}{N_A^2 + (8\times 10^{17})^2} + \dfrac{0.8 N_D^2}{N_D^2 + (10^{19})^2}$ | 无 | 无量纲 |
| $v_{\text{sat}}$ | $9.1\times 10^6\,t^{-0.4}$ | $\dfrac{2.4\times 10^7}{1 + 0.8\exp(t/2)}$ | $\text{cm/s}$ |

迁移率计算由 `material.py` 中的 `Material.cal_mobility(temperature, input_doping, charge, electric_field)` 实现。迁移率模型按名字注册，器件文件按名字选用；每种材料有缺省选用的模型：`"Si"` 为 `"Selberherr"`，`"SiC"` 为 `"Das"`，`"Diamond"` 为 `"Pernegger"`。在调用关系上：

- [current.md](current.md) 的 `CalCurrent.drift_all`（`src/raser/core/current/cal_current.py`）将 `Material(my_d.material).cal_mobility` 传给 `advance`（`src/raser/core/current/drift.py`），在每个时间步用器件选用的迁移率模型求取局部迁移率，用于计算漂移位移与 Einstein 热扩散标准差；
- [current.md](current.md) 的 `collect_by_diffusion`（`src/raser/core/current/diffusion.py`）调用 `Material(my_d.material).cal_mobility(my_d.temperature, neff, -1, 0)` 计算无场像素传感器中电子的零场迁移率；
- [field.md](field.md) 的 `_fits` 与 `sheet_resistance`（`src/raser/core/field/implanted_aluminium.py`，供 `src/raser/core/field/circuit_parameters.py` 的 `sheet_resistance` 调用）调用 `Material("SiC").cal_mobility(..., 1, 0)`，以 `"Das"` 模型的零场空穴迁移率为基准标定实测霍尔迁移率折减比例 `MOBILITY_LEFT` 并计算铝注入 4H-SiC 阻性层方阻；
- `Material.draw_velocity`（`material.py`）调用 `self.cal_mobility` 绘制电子与空穴漂移速度随电场的变化曲线；
- 硅器件的器件文件选用 `"Reggiani"` 时，构造 `Material("Si", mobility_model="Reggiani")`。

硅的 `"Selberherr"` 模型见文献 [2]，硅的 `"Reggiani"` 模型见文献 [3]；4H-SiC 的 `"Das"` 模型见文献 [19]，其掺杂参数源于文献 [20]，电子的 $C_{\text{ref}}$ 取文献 [20] 的原值 $1.94\times 10^{17}\ \text{cm}^{-3}$（文献 [19] 中的 $1.94\times 10^{19}$ 是笔误），空穴取 $1.76\times 10^{19}\ \text{cm}^{-3}$。金刚石的 `"Pernegger"` 模型见文献 [22]：$470\ \mu\text{m}$ 厚单晶 CVD 金刚石在室温下对 Am-241 α 粒子的瞬态电流测量，场强 $0.2$–$1.5\ \text{V}/\mu\text{m}$，$\mu_L$ 与 $v_{\text{sat}}$ 是原文式 (7) 的拟合值。

### 碰撞电离系数

在高电场下，漂移载流子在自由程内获得的动能超过带隙电离阈值，与晶格碰撞激发出次级电子-空穴对，单位漂移路程上产生次级对的平均次数即为碰撞电离系数 $\alpha(E, T)$。代码实现三种模型：

1. **van Overstraeten–de Man 模型（`"vanOverstraeten"`，`"Si"` 缺省）**：在 $E_0 = 4.0\times 10^5\ \text{V/cm}$ 处分段衔接高低场 Chynoweth 定律，场强低于测量拟合下限 $1.75\times 10^5\ \text{V/cm}$ 时置零，并通过光学声子能量 $\hbar\omega$ 引入温度缩放因子 $\gamma(T)$：

$$\gamma(T) = \frac{\tanh\bigl(\hbar\omega / (2 k T_0)\bigr)}{\tanh\bigl(\hbar\omega / (2 k T)\bigr)} \tag{11}$$

$$\alpha(E, T) = \begin{cases} 0, & E < 1.75\times 10^5\ \text{V/cm} \\ \gamma(T)\,a_{\text{low}}\exp\!\left(-\dfrac{\gamma(T)\,b_{\text{low}}}{E}\right), & 1.75\times 10^5\ \text{V/cm} \le E \le E_0 \\ \gamma(T)\,a_{\text{high}}\exp\!\left(-\dfrac{\gamma(T)\,b_{\text{high}}}{E}\right), & E > E_0 \end{cases} \tag{12}$$

2. **Okuto–Crowell 模型（`"Okuto"`，`"Si"` 备选）**：将前因子与临界场表示为相对参考温度 $T_0 = 300.0\ \text{K}$ 的线性温度函数，场强不高于 $1.0\times 10^5\ \text{V/cm}$ 时置零：

$$\alpha(E, T) = \begin{cases} 0, & E \le 1.0\times 10^5\ \text{V/cm} \\ a\bigl[1 + c(T - T_0)\bigr] E^{\gamma_0} \exp\!\left(-\left(\dfrac{b\bigl[1 + d(T - T_0)\bigr]}{E}\right)^{\delta}\right), & E > 1.0\times 10^5\ \text{V/cm} \end{cases} \tag{13}$$

3. **Hatakeyama 模型（`"Hatakeyama"`，`"SiC"` 缺省）**：计入 4H-SiC 六方晶格各向异性，当电场方向偏离 $\langle 0001\rangle$ 晶向朝向 $\langle 11\bar{2}0\rangle$ 晶向夹角为 $\theta$（方向余弦 `along_0001` $= \cos\theta$、`along_1120` $= \sin\theta$）时，由两主轴系数 $(a_{0001}, b_{0001})$ 与 $(a_{1120}, b_{1120})$ 合成有效系数，场强不高于 $10^4\ \text{V/cm}$ 时置零：

$$B = \left[\left(\frac{\sin\theta}{b_{1120}}\right)^2 + \left(\frac{\cos\theta}{b_{0001}}\right)^2\right]^{-1/2}, \qquad A = \ln\!\left(\frac{a_{0001}}{a_{1120}}\right) \tag{14}$$

$$a = a_{1120}^{(B\sin\theta / b_{1120})^2}\,a_{0001}^{(B\cos\theta / b_{0001})^2}, \qquad b(E) = B\sqrt{1 - A^2\left(\frac{B\sin\theta\cos\theta\,E}{b_{1120} b_{0001}}\right)^2} \tag{15}$$

$$\alpha(E, T) = \begin{cases} 0, & E \le 10^4\ \text{V/cm} \\ \gamma(T)\,a\exp\!\left(-\dfrac{\gamma(T)\,b(E)}{E}\right), & E > 10^4\ \text{V/cm} \end{cases} \tag{16}$$

其中：

- $\alpha(E, T)$：碰撞电离系数，$\text{cm}^{-1}$；
- $E$：电场模长，$\text{V/cm}$；$T$：器件温度，$\text{K}$；
- $k$：玻尔兹曼常数，`BOLTZMANN_EV_PER_K` $= 8.617333262\times 10^{-5}\ \text{eV/K}$（CODATA 2018）；
- $\gamma(T)$：光学声子散射无量纲温度因子；$\hbar\omega$（代码中为 `hbarOmega`）为光学声子能量，$\text{eV}$；$T_0$ 为参考温度，$\text{K}$；
- $E_0$：`"vanOverstraeten"` 模型的高低场分界场强，取 $4.0\times 10^5\ \text{V/cm}$；$a_{\text{low}}, a_{\text{high}}$ 为低场与高场指前因子，$\text{cm}^{-1}$；$b_{\text{low}}, b_{\text{high}}$ 为低场与高场临界电场，$\text{V/cm}$；
- $\gamma_0, \delta$：`"Okuto"` 模型的电场幂指数（代码中分别为 `_gamma`、`_delta`，无量纲），分别取 $1.0$、$2.0$；$a$ 为指前系数，$\text{V}^{-1}$；$b$ 为临界电场，$\text{V/cm}$；$c, d$ 为温度系数，$\text{K}^{-1}$；
- $\theta$：`"Hatakeyama"` 模型中电场相对 $\langle 0001\rangle$ 朝向 $\langle 11\bar{2}0\rangle$ 的偏轴角（`angle_deg`），度，缺省取 `OFF_AXIS_DEG = 4.0`（对应 $4^\circ$ 偏轴 4H-SiC 外延片中垂直于表面的平面器件电场）；
- $a_{0001}, a_{1120}$：4H-SiC 沿 $\langle 0001\rangle$ 与 $\langle 11\bar{2}0\rangle$ 方向的指前因子，$\text{cm}^{-1}$；$b_{0001}, b_{1120}$ 为两方向的临界电场，$\text{V/cm}$；$A$（无量纲）、$B$（$\text{V/cm}$）、$a$（$\text{cm}^{-1}$）与 $b(E)$（$\text{V/cm}$）为合成参数。

三种碰撞电离模型的全部参数取值如下表：

| 模型 | 公共参数 | 载流子 | 载流子专属参数 |
| --- | --- | --- | --- |
| `"vanOverstraeten"` | $E_{\text{th}} = 1.75\times 10^5\ \text{V/cm}$，$E_0 = 4.0\times 10^5\ \text{V/cm}$，$\hbar\omega = 0.063\ \text{eV}$，$T_0 = 293.0\ \text{K}$ | 电子（`charges < 0`） | $a_{\text{low}} = 7.03\times 10^5\ \text{cm}^{-1}$，$a_{\text{high}} = 7.03\times 10^5\ \text{cm}^{-1}$，$b_{\text{low}} = 1.231\times 10^6\ \text{V/cm}$，$b_{\text{high}} = 1.231\times 10^6\ \text{V/cm}$ |
| `"vanOverstraeten"` | 同上 | 空穴（`charges > 0`） | $a_{\text{low}} = 1.582\times 10^6\ \text{cm}^{-1}$，$a_{\text{high}} = 6.71\times 10^5\ \text{cm}^{-1}$，$b_{\text{low}} = 2.036\times 10^6\ \text{V/cm}$，$b_{\text{high}} = 1.693\times 10^6\ \text{V/cm}$ |
| `"Okuto"` | $E_{\text{th}} = 1.0\times 10^5\ \text{V/cm}$，$T_0 = 300.0\ \text{K}$，$\gamma_0 = 1.0$，$\delta = 2.0$ | 电子（`charges < 0`） | $a = 0.426\ \text{V}^{-1}$，$b = 4.81\times 10^5\ \text{V/cm}$，$c = 3.05\times 10^{-4}\ \text{K}^{-1}$，$d = 6.86\times 10^{-4}\ \text{K}^{-1}$ |
| `"Okuto"` | 同上 | 空穴（`charges > 0`） | $a = 0.243\ \text{V}^{-1}$，$b = 6.53\times 10^5\ \text{V/cm}$，$c = 5.35\times 10^{-4}\ \text{K}^{-1}$，$d = 5.67\times 10^{-4}\ \text{K}^{-1}$ |
| `"Hatakeyama"` | $E_{\text{th}} = 10^4\ \text{V/cm}$，$\theta = 4.0^\circ$（`OFF_AXIS_DEG`），$\hbar\omega = 0.19\ \text{eV}$，$T_0 = 300.0\ \text{K}$ | 电子（`charges < 0`） | $a_{0001} = 1.76\times 10^8\ \text{cm}^{-1}$，$a_{1120} = 2.10\times 10^7\ \text{cm}^{-1}$，$b_{0001} = 3.30\times 10^7\ \text{V/cm}$，$b_{1120} = 1.70\times 10^7\ \text{V/cm}$ |
| `"Hatakeyama"` | 同上 | 空穴（`charges > 0`） | $a_{0001} = 3.41\times 10^8\ \text{cm}^{-1}$，$a_{1120} = 2.96\times 10^7\ \text{cm}^{-1}$，$b_{0001} = 2.50\times 10^7\ \text{V/cm}$，$b_{1120} = 1.60\times 10^7\ \text{V/cm}$ |

`VAN_OVERSTRAETEN` 字典与 `hatakeyama(carrier, angle_deg=OFF_AXIS_DEG)` 函数定义在 `impact_ionization.py` 中（返回自变量为 `["E", "T"]` 的 `Formula`），统一的 Python 求值入口为 `material.py` 中的 `Material.cal_coefficient(electric_field, charges, temperature)`。`Material` 的缺省 `avalanche_model` 在 `"Si"` 下为 `"vanOverstraeten"`，在 `"SiC"` 下为 `"Hatakeyama"`，在 `"Diamond"` 下为 `None`（代码注释指明非掺杂 MIM 金刚石器件无增益）。每种材料能选的模型列在 `material.py` 的 `AVALANCHE_MODELS` 中：`"Si"` 为 `"vanOverstraeten"`、`"Okuto"`，`"SiC"` 为 `"Hatakeyama"`，`"Diamond"` 没有。在调用关系上：

- [field.md](field.md) 的 `CreateImpactModel_vanOvenstraeten` 与 `CreateImpactModel_Hatakeyama`（`src/raser/core/field/physics_avalanche.py`）分别调用 `VAN_OVERSTRAETEN[...].devsim(EDGE_FIELD_IN_THRESHOLDS, E=EDGE_FIELD, T="T")` 与 `hatakeyama(...).devsim(EDGE_FIELD_IN_THRESHOLDS, E=EDGE_FIELD, T="T")`（取缺省 `OFF_AXIS_DEG = 4.0` 度），在 DEVSIM 连续性方程中生成硅和碳化硅的碰撞电离边模型 `Ion_coeff_n`、`Ion_coeff_p`；器件文件 `avalanche_model` 为 `"Okuto"` 时，`Silicon` 区域的边模型仍是 `VAN_OVERSTRAETEN`（该模块中的 `"Fine_exponential_models"`、`"Tunnel"`、`"sze"`、`"chynoweth"`、`"bologna"`、`"sic_custom"` 直接写在 `physics_avalanche.py` 内，见 [field.md](field.md)）；
- [field.md](field.md) 的 `DevsimField._integrate_planar_gain`（`src/raser/core/field/devsim_field.py`）调用 `Material(my_d.material, avalanche_model=my_d.avalanche_model).cal_coefficient(abs(E), ±1, my_d.temperature)`，沿一维中心深度剖面积分求取平板稳态倍增因子（供 [current.md](current.md) 的 `CalCurrentGain._build_planar_gain_carriers` 使用）；
- [current.md](current.md) 的 `CalCurrentGain._build_local_gain_carriers`（`src/raser/core/current/cal_current.py`）调用 `Material(my_d.material, avalanche_model=my_d.avalanche_model).cal_coefficient(field, charge_sign, my_d.temperature)`，在多维场中沿原生载流子漂移路径分段积分碰撞电离系数。

van Overstraeten–de Man 模型见文献 [4]，Okuto–Crowell 模型见文献 [5]，Hatakeyama 主轴参数与偏轴角合成公式见文献 [6, 7]。经光学声子能量 $\hbar\omega$ 引入的温度因子 $\gamma(T)$ 的物理来源见文献 [16]；`"vanOverstraeten"` 用 $\hbar\omega = 0.063\ \text{eV}$ 的写法取自文献 [17]；`"Hatakeyama"` 的 $\hbar\omega = 0.19\ \text{eV}$ 见文献 [18]，原文只对电子给出，代码对空穴也取这个值。

### 能带与本征载流子浓度

非简并半导体在热平衡下的导带有效状态密度 $N_c(T)$ 与价带有效状态密度 $N_v(T)$ 按 $T^{1.5}$ 随温度增长，并与禁带宽度 $E_g$ 共同决定本征载流子浓度 $n_i(T)$：

$$N_c(T) = N_{c0}\left(\frac{T}{T_{\text{ref}}}\right)^{1.5}, \qquad N_v(T) = N_{v0}\left(\frac{T}{T_{\text{ref}}}\right)^{1.5} \tag{17}$$

$$n_i(T) = \sqrt{N_c(T)\,N_v(T)}\,\exp\!\left(-\frac{E_g}{2 k T}\right) \tag{18}$$

其中：

- $T$：温度，$\text{K}$；
- $N_c(T), N_v(T)$：导带与价带有效状态密度，$\text{cm}^{-3}$；$N_{c0}, N_{v0}$ 为参考温度 $T_{\text{ref}}$（`"Si"` 与 `"Diamond"` 取 $300\ \text{K}$，`"SiC"` 取 $1\ \text{K}$）下的系数值；
- $E_g$：不随温度变化的禁带宽度，$\text{J}$（由以 $\text{eV}$ 为单位的带隙乘以 CODATA 2018 元电荷 $1.602176634\times 10^{-19}\ \text{J/eV}$ 得到）；
- $k$：玻尔兹曼常数，取 CODATA 2018 值 $1.380649\times 10^{-23}\ \text{J/K}$（对应 $8.617333262\times 10^{-5}\ \text{eV/K}$）；
- $n_i(T)$：本征载流子浓度，$\text{cm}^{-3}$。

各材料在 `BAND_STRUCTURE`（`band_structure.py`）中的公式与参数如下表：

| 材料 | `N_c`（$\text{cm}^{-3}$） | `N_v`（$\text{cm}^{-3}$） | `E_g`（$\text{J}$） | $300\ \text{K}$ 下的 $N_c, N_v$（$\text{cm}^{-3}$） |
| --- | --- | --- | --- | --- |
| `"Si"` | `2.82e19*pow(T/300, 1.5)` | `1.83e19*pow(T/300, 1.5)` | `1.12*1.602176634e-19` | $2.82\times 10^{19},\; 1.83\times 10^{19}$ |
| `"SiC"` | `3.25e15*pow(T, 1.5)` | `4.8e15*pow(T, 1.5)` | `3.26*1.602176634e-19` | $1.69\times 10^{19},\; 2.49\times 10^{19}$ |
| `"Diamond"` | `1.8e19*pow(T/300, 1.5)` | `1.5e19*pow(T/300, 1.5)` | `5.47*1.602176634e-19` | $1.80\times 10^{19},\; 1.50\times 10^{19}$ |

该模型由 `band_structure.py` 中的 `_material` 构造为字典 `BAND_STRUCTURE[material]`，每项包含 `"N_c"`、`"N_v"`、`"E_g"`、`"n_i"` 四个关于自变量 `["T"]` 的 `Formula`。在调用关系上，[field.md](field.md) 的 `CreateSiliconConstant`、`CreateSiliconCarbideConstant`、`CreateDiamondConstant`（`src/raser/core/field/create_parameter.py`）对 `BAND_STRUCTURE[material]` 中的四个 `Formula` 调用 `.value(T=T)`，向 DEVSIM 区域写入参数 `N_c`、`N_v`、`E_g`、`n_i` 以及 `n1 = n_i`、`p1 = n_i`；本包 `incomplete_ionization.py` 的 `free_holes` 调用 `BAND_STRUCTURE[material]["N_v"].value(T=temperature_k)` 计算价带有效状态密度（供 [field.md](field.md) 的 `implanted_aluminium.py` 计算铝注入 4H-SiC 层方阻）。4H-SiC 的有效状态密度由 $N = 2 M_c (2\pi m^* k T / h^2)^{3/2}$ 按导带 $M_c = 3$ 个能谷（每谷 $0.37\,m_0$）与价带空穴 $1.0\,m_0$ 导出，见文献 [8]（第 6 节）。

### 杂质与不完全电离

替位掺杂杂质可占据晶格中不同对称性的不等价格位（如 4H-SiC 的六方格位与立方格位，各占 $0.5$），重掺杂下杂质电离能随该杂质总浓度 $N$ 按 Pearson–Bardeen 关系线性降低；当电离能不可忽略时，各能级在玻尔兹曼统计下仅部分电离。第 $i$ 个格位能级的有效电离能 $\Delta E_i(N)$、特征载流子浓度 $n_{1,i}(T)$ 与总电离比例 $N_{\text{ion}}/N$ 为：

$$\Delta E_i(N) = \Delta E_{0,i} - \alpha_{\text{fall}}\,N^{1/3} \tag{19}$$

$$n_{1,i}(T) = N_{\text{band}}\exp\!\left(-\frac{\Delta E_i(N)}{k T}\right) \tag{20}$$

$$\frac{N_{\text{ion}}}{N} = \sum_{i} \begin{cases} \dfrac{f_i\,n_{1,i}(T)}{n_{1,i}(T) + g\,c}, & c > 0 \\ f_i, & c \le 0 \end{cases} \tag{21}$$

对于含单能级受主浓度 $N_A$（部分电离）与完全电离补偿施主浓度 $N_D$ 的半导体层，忽略自由电子与本征载流子浓度 $n_i$，由电中性条件 $p + N_D = N_A^-$，即 $p(p + N_D) = (N_A - N_D - p)\,p_1 / g$（其中 $p_1 = N_v(T)\exp\!\left(-\Delta E(N_A)/(k T)\right)$）解出的自由空穴浓度 $p$ 为：

$$p_{\text{freed}} = \frac{N_v(T)}{g}\exp\!\left(-\frac{\Delta E(N_A)}{k T}\right), \qquad p_{\text{taken}} = N_D + p_{\text{freed}} \tag{22}$$

$$p = \frac{\sqrt{p_{\text{taken}}^2 + 4\,p_{\text{freed}}(N_A - N_D)} - p_{\text{taken}}}{2} \tag{23}$$

其中：

- $\Delta E_{0,i}, \Delta E_i(N)$：第 $i$ 个能级在低掺杂极限下与浓度 $N$ 下的电离能（相对对应带边），$\text{eV}$；
- $f_i$：杂质占据第 $i$ 个格位能级的比例（无量纲，满足 $\sum_i f_i = 1$）；
- $\alpha_{\text{fall}}$：电离能随浓度下降的 Pearson–Bardeen 系数（代码中为 `fall_ev_cm`），$\text{eV}\cdot\text{cm}$；
- $N$：该掺杂元素的浓度（`concentration_cm3` 或 `acceptors_cm3`），$\text{cm}^{-3}$；
- $N_{\text{band}}$：对应能带的有效状态密度（施主取 $N_c$，受主取 $N_v$），$\text{cm}^{-3}$；
- $n_{1,i}(T)$：第 $i$ 个能级的特征载流子浓度，$\text{cm}^{-3}$；
- $c$：自由载流子浓度（代码中记为 `carriers`，施主取电子浓度 $n$，受主取空穴浓度 $p$），$\text{cm}^{-3}$；当 $c \le 0$ 时直接取完全电离 $f_i$，避免低温冻结下 $n_{1,i}$ 下溢为 $0$ 时出现 $0/0$；
- $g$：杂质能级简并因子（代码中为 `degeneracy`，无量纲），施主取 $2.0$，受主取 $4.0$；
- $k$：玻尔兹曼常数，`BOLTZMANN_EV_PER_K` $= 8.617333262\times 10^{-5}\ \text{eV/K}$；
- $T$：温度（`T` 或 `temperature_k`），$\text{K}$；
- $N_A, N_D$：受主浓度（`acceptors_cm3`）与补偿施主浓度（`donors_cm3`），$\text{cm}^{-3}$；
- $\Delta E(N_A)$：受主浓度 $N_A$ 下的有效电离能（按式 (19) 计算），$\text{eV}$；
- $p_1$：单能级受主的特征空穴浓度 $N_v(T)\exp\!\left(-\Delta E(N_A)/(k T)\right)$，$\text{cm}^{-3}$；
- $p_{\text{freed}}, p_{\text{taken}}, p$：折算特征空穴浓度（$p_1 / g$）、与补偿施主之和及求解出的自由空穴浓度（代码中分别为 `freed_cm3`、`taken_cm3` 与返回值），$\text{cm}^{-3}$。

`DOPANTS`（`dopants.py`）注册的全部材料与掺杂元素参数如下表：

| 材料 | 元素 | 类型 `kind` | 能级与占比 `levels`（$(\Delta E_{0,i}\ [\text{eV}],\, f_i)$） | 简并因子 `degeneracy` | `fall_ev_cm`（$\text{eV}\cdot\text{cm}$） |
| --- | --- | --- | --- | --- | --- |
| `"Si"` | `"P"` | `"donor"` | `((0.046, 1.0),)` | `2.0` | `0.0` |
| `"Si"` | `"As"` | `"donor"` | `((0.054, 1.0),)` | `2.0` | `0.0` |
| `"Si"` | `"Sb"` | `"donor"` | `((0.043, 1.0),)` | `2.0` | `0.0` |
| `"Si"` | `"B"` | `"acceptor"` | `((0.044, 1.0),)` | `4.0` | `0.0` |
| `"SiC"` | `"N"` | `"donor"` | `((0.0533, 0.5), (0.0996, 0.5))` | `2.0` | `0.0` |
| `"SiC"` | `"P"` | `"donor"` | `((0.057, 0.5), (0.113, 0.5))` | `2.0` | `0.0` |
| `"SiC"` | `"Al"` | `"acceptor"` | `((0.216, 1.0),)` | `4.0` | `3e-8` |
| `"SiC"` | `"B"` | `"acceptor"` | `((0.311, 1.0),)` | `4.0` | `0.0` |
| `"Diamond"` | `"B"` | `"acceptor"` | `((0.3685, 1.0),)` | `4.0` | `0.0` |
| `"Diamond"` | `"N"` | `"donor"` | `((1.7, 1.0),)` | `2.0` | `0.0` |
| `"Diamond"` | `"P"` | `"donor"` | `((0.60, 1.0),)` | `2.0` | `0.0` |

掺杂参数表定义在 `dopants.py` 的 `DOPANTS` 与 `Dopant` 中，电离比例公式构造函数 `ionized_fraction(material, element, concentration_cm3=0.0)`（返回自变量为 `["carriers", "N_band", "T"]` 的 `Formula`）与自由空穴求解函数 `free_holes(material, element, acceptors_cm3, donors_cm3, temperature_k)` 定义在 `incomplete_ionization.py` 中。在调用关系上，[field.md](field.md) 的 `holes`（`src/raser/core/field/implanted_aluminium.py`，由 `sheet_resistance` 调用，进而供 `src/raser/core/field/circuit_parameters.py` 构造阻性层等效电路）调用 `free_holes("SiC", "Al", acceptors_cm3, donors_cm3, temperature_k)` 计算铝注入 4H-SiC 层的自由空穴浓度。简并因子、硅中杂质电离能与玻尔兹曼不完全电离统计见文献 [1]（第 1.4.3 节），电离能随浓度的 $N^{1/3}$ 下降定律见文献 [9]，4H-SiC 杂质格位电离能与不完全电离综述见文献 [8]（第 10.1–10.2 节，其中氮施主取自 Schöner 等的拟合，硼只取浅受主能级 $311\ \text{meV}$），4H-SiC 铝受主电离能浓度依赖关系与补偿电中性方程见文献 [10]，金刚石中硼、氮、磷的电离能分别见文献 [11, 12, 13]。

### SRH 复合

非平衡电子与空穴通过禁带中的局域深能级陷阱中心发生间接复合或热产生（Shockley-Read-Hall 过程）；在强电场下的 4H-SiC 中，局部电场还通过陷阱辅助隧穿（Trap-Assisted Tunneling, TAT）引入带场强饱和上限的 Hurkx 场增强因子。SRH 净复合率 $U_{\text{SRH}}$ 与 TAT 场增强因子 $\Gamma_{\text{TAT}}(E, F_{\text{sat}})$ 分别为：

$$U_{\text{SRH}} = \frac{n p - n_i^2}{\tau_p (n + n_1) + \tau_n (p + p_1)} \tag{24}$$

$$\Gamma_{\text{TAT}}(E, F_{\text{sat}}) = \begin{cases} 2\sqrt{3\pi}\,\dfrac{E}{F_\gamma}\exp\!\left[\left(\dfrac{E}{F_\gamma}\right)^2\right], & E < F_{\text{sat}} \\ 2\sqrt{3\pi}\,\dfrac{F_{\text{sat}}}{F_\gamma}\exp\!\left[\left(\dfrac{F_{\text{sat}}}{F_\gamma}\right)^2\right], & E \ge F_{\text{sat}} \end{cases} \tag{25}$$

其中：

- $U_{\text{SRH}}$：SRH 净复合率，$\text{cm}^{-3}\cdot\text{s}^{-1}$；
- $n, p$：电子与空穴浓度，$\text{cm}^{-3}$；
- $n_i$：本征载流子浓度，$\text{cm}^{-3}$；
- $n_1, p_1$：费米能级与陷阱能级重合时的电子与空穴浓度，$\text{cm}^{-3}$；代码将陷阱取在本征能级处，设 $n_1 = p_1 = n_i$（注释说明若陷阱取在禁带中央 midgap，则 $n_1/p_1 = N_c/N_v$）；
- $\tau_n, \tau_p$：电子与空穴的 SRH 寿命，$\text{s}$；`SRH_LIFETIME` 中 `"Si"` 取 $\tau_n = 7\times 10^{-3}\ \text{s}$、$\tau_p = 7\times 10^{-3}\ \text{s}$，`"SiC"` 取 $\tau_n = 2.5\times 10^{-6}\ \text{s}$、$\tau_p = 0.5\times 10^{-6}\ \text{s}$，`"Diamond"` 取 $\tau_n = 5.6\times 10^{-7}\ \text{s}$、$\tau_p = 2.4\times 10^{-7}\ \text{s}$，均为与温度无关的定值；
- $\Gamma_{\text{TAT}}$：陷阱辅助隧穿无量纲场增强因子（代码中为 `TAT_FIELD_ENHANCEMENT`）；
- $E$：电场模长，$\text{V/cm}$；
- $F_{\text{sat}}$：TAT 场增强饱和上限场强，$\text{V/cm}$，缺省取 `TAT_SATURATION_FIELD = 1e5` $\text{V/cm}$；
- $F_\gamma$：TAT 特征场强，代码中固定为 `F_gamma = 3.9e4` $\text{V/cm}$；
- $\pi$：圆周率近似常数，代码中固定为 `pi = 3.14159`。

`SRH`（自变量为 `["n", "p", "n_i", "n1", "p1", "tau_n", "tau_p"]` 的 `Formula`）、`SRH_LIFETIME`、`TAT_SATURATION_FIELD` 与 `TAT_FIELD_ENHANCEMENT`（自变量为 `["E", "F_sat"]` 的 `Formula`）均定义在 `recombination.py` 中。在调用关系上：

- [field.md](field.md) 的 `CreateSiliconConstant`、`CreateSiliconCarbideConstant`、`CreateDiamondConstant` 与 `CreateTAT`（`src/raser/core/field/create_parameter.py`）读取 `SRH_LIFETIME` 设置 DEVSIM 区域参数 `taun`、`taup`（同时将 `n1`、`p1` 设为 `n_i`），并在 `"SiliconCarbide"` 区域将 `F_sat` 设为 `TAT_SATURATION_FIELD`（可被器件文件的 `parameter` 键覆盖）；
- [field.md](field.md) 的 `CreateSRH`（`src/raser/core/field/physics_drift_diffusion.py`）调用 `SRH.devsim(n="Electrons", p="Holes", n_i="n_i", n1="n1", p1="p1", tau_n="taun", tau_p="taup")` 生成节点模型 `USRH`，与附加复合项 `U_const`（以及开启辐照时由 `src/raser/core/field/physics_irradiation.py` 生成的辐照缺陷复合率 `U_r`，见 [field.md](field.md)）相加构成连续性方程源项 `ElectronGeneration` 与 `HoleGeneration`；
- [field.md](field.md) 的 `CreateFESRH`（`src/raser/core/field/physics_avalanche.py`）在 `"SiliconCarbide"` 区域开启碰撞电离模型时，调用 `TAT_FIELD_ENHANCEMENT.devsim(E="abs(ElectricField)", F_sat="F_sat")` 构造边模型 `R_TAT = (TAT_FIELD_ENHANCEMENT)*(U_const@n1)`，并从 `Ion_coeff_rate` 中减去 `R_TAT`。

SRH 复合率公式见文献 [1]（第 1.5.4 节）与原始文献 [14]，Hurkx 陷阱辅助隧穿场增强公式见文献 [15]；4H-SiC 的电子寿命 $2.5\ \mu\text{s}$ 见文献 [19]，空穴寿命 $0.5\ \mu\text{s}$ 见文献 [21]（组里时间分辨光致发光测量确认）。

## 算法

### 内置常数

下表列出 `src/raser/core/model/` 各模块中的全部内置物理常数与写死的数值参数。器件 JSON 的 `"parameter": {"name": ..., "value": ...}` 在 [field.md](field.md) 的 `create_parameter` 写完区域常数之后写入，可覆盖任意一个 DEVSIM 区域参数，因此 `TAT_SATURATION_FIELD`（DEVSIM 参数 `"F_sat"`）以及 `RELATIVE_PERMITTIVITY`、`BAND_STRUCTURE`、`SRH_LIFETIME` 写入 DEVSIM 的副本（`eps`、`Permittivity`、`N_c`、`N_v`、`E_g`、`n_i`、`n1`、`p1`、`taun`、`taup`）都可在场求解中被覆盖；`Material`、`free_holes` 等 Python 端的计算使用表中的值。其余常数写死在代码中：

| 常数或内置参数名 | `"Si"` | `"SiC"` | `"Diamond"` | 公共 / 固定值 | 单位 | 定义位置与含义 |
| --- | --- | --- | --- | --- | --- | --- |
| `RELATIVE_PERMITTIVITY` | `11.9` | `9.76` | `5.7` | — | 无量纲 | `material.py`，静态相对介电常数 $\varepsilon_r$ |
| `m_e` | — | — | — | `9.109e-31` | $\text{kg}$ | `material.py`（`Material.mat_database`），自由电子静止质量 |
| `electron_mass` | `0.26 * m_e` | `0.29 * m_e` | 未设置 | — | $\text{kg}$ | `material.py`，电子有效质量 |
| `hole_mass` | `0.386 * m_e` | `1.0 * m_e` | 未设置 | — | $\text{kg}$ | `material.py`，空穴有效质量 |
| `x_step`, 采样点数 | — | — | — | `1000`, `1001` | $\text{V/cm}$, 点 | `material.py`（`Material.draw_velocity`），绘图的电场步长与采样点数（$0$ 至 $10^6\ \text{V/cm}$） |
| `BOLTZMANN_EV_PER_K` | — | — | — | `8.617333262e-5` | $\text{eV/K}$ | `impact_ionization.py`（亦被 `incomplete_ionization.py` 导入），CODATA 2018 玻尔兹曼常数 |
| `_VAN_OVERSTRAETEN` 阈值与常数 | $E_{\text{th}} = 1.75\times 10^5$，$E_0 = 4.0\times 10^5$，$\hbar\omega = 0.063$，$T_0 = 293.0$ | — | — | — | $\text{V/cm}$, $\text{V/cm}$, $\text{eV}$, $\text{K}$ | `impact_ionization.py`，van Overstraeten–de Man 碰撞电离阈值、高低场分界、光学声子能量与参考温度 |
| `"Okuto"` 阈值与常数 | $E_{\text{th}} = 1.0\times 10^5$，$T_0 = 300.0$，`_gamma = 1.0`，`_delta = 2.0` | — | — | — | $\text{V/cm}$, $\text{K}$, 无量纲, 无量纲 | `material.py`（`Material.cal_coefficient`），Okuto–Crowell 碰撞电离阈值、参考温度与指数 |
| `_HATAKEYAMA` 阈值与常数 | — | $E_{\text{th}} = 10^4$，`OFF_AXIS_DEG = 4.0`，$\hbar\omega = 0.19$，$T_0 = 300.0$ | — | — | $\text{V/cm}$, 度, $\text{eV}$, $\text{K}$ | `impact_ionization.py`，Hatakeyama 碰撞电离阈值、偏轴角、光学声子能量与参考温度 |
| `_K_J_PER_K`, 带隙换算因子 | — | — | — | `1.380649e-23`, `1.602176634e-19` | $\text{J/K}$, $\text{J/eV}$ | `band_structure.py`，计算 $n_i(T)$ 与 $E_g$ 所用的 CODATA 2018 玻尔兹曼常数和元电荷换算因子 |
| `SRH_LIFETIME`（`tau_n`, `tau_p`） | `7e-3`, `7e-3` | `2.5e-6`, `0.5e-6` | `5.6e-7`, `2.4e-7` | — | $\text{s}$ | `recombination.py`，电子与空穴默认 SRH 寿命 |
| `TAT_SATURATION_FIELD` | — | `1e5` | — | — | $\text{V/cm}$ | `recombination.py`，4H-SiC 陷阱辅助隧穿场增强默认饱和场强（可通过器件文件 `parameter` 键覆盖 `"F_sat"`） |
| `F_gamma`, `pi` | — | `3.9e4`, `3.14159` | — | — | $\text{V/cm}$, 无量纲 | `recombination.py`（`TAT_FIELD_ENHANCEMENT`），TAT 特征场强与圆周率常数 |

### 单一公式双端编译与求值（`formula.py`）

为了让载流子漂移（Python 数值计算）与 DEVSIM 场求解器（符号表达式及其自动求导 `diff`）共用同一物理定义，`Formula(text, variables, **parameters)` 用 DEVSIM 表达式子集（`abs`、`exp`、`log`、`pow`、`sqrt`、`tanh`、`ifelse(condition, a, b)` 与幂运算符 `^`）只写一次公式，并按以下步骤初始化与求值：

1. **参数词法替换（`_substitute` 与 `Formula.__init__`）**：将 `variables` 转为元组 `self.variables = tuple(variables)`。按 `**parameters` 的传入顺序遍历每个 `(name, value)`，用正则表达式 `(?<![\w.@])<name>(?![\w@])` 匹配独立的完整标识符（不匹配带小数点或 DEVSIM 节点后缀 `@n0`/`@n1` 的部分词），替换为加圆括号的 `f"({value})"` 存入 `self.text`。因为按顺序依次替换，排在前面的字符串参数可以引用自变量及排在它后面的参数（如 `BAND_STRUCTURE` 中 `n_i` 的公式先展开为 `N_c`、`N_v`、`E_g` 的关于 `T` 的子表达式，或 `_VAN_OVERSTRAETEN` 先展开 `gamma` 表达式再将其中 `hbarOmega`、`k`、`T0` 替换为数值）。
2. **递归改写 `ifelse` 并编译 Python 字节码（`_closing` 与 `_python`）**：在 `self.text` 中用正则 `(?<!\w)ifelse\(` 搜索 `ifelse(`：
   - 若未找到，直接将字符串中的 `^` 替换为 Python 幂运算符 `**` 并返回；
   - 若找到，记左括号下标 `opening = match.end() - 1`，调用 `_closing(text, opening)` 从 `opening` 起逐字符扫描括号深度 `depth`（遇 `(` 加 `1`，遇 `)` 减 `1`，在 `depth == 1` 时记录顶层逗号下标，当 `depth == 0` 时返回右括号下标 `closing` 与逗号下标列表 `commas`）。若扫描完整个字符串 `depth` 仍未归零，抛出 `ValueError: unbalanced parentheses in <text>`；若顶层逗号个数 `len(commas) != 2`，抛出 `ValueError: ifelse takes three arguments in <text>`。随后对 `condition`、`if_true`、`if_false` 三个参数及括号前后的子串递归调用 `_python`，拼接为 Python 条件表达式 `(({if_true}) if ({condition}) else ({if_false}))`。
   - 调用 `compile(_python(self.text), "<formula>", "eval")` 生成字节码对象 `self._code`。
3. **Python 数值求值（`Formula.value(**variables)`）**：核对传入的关键字参数名集合 `set(variables) == set(self.variables)`；若不相等，抛出 `ValueError: the formula takes <self.variables>, not <tuple(variables)>`。在屏蔽内置函数的受限全局字典 `{"__builtins__": {}, **_FUNCTIONS}`（仅开放 `_FUNCTIONS` 中的 `abs`、`math.exp`、`math.log`、`math.pow`、`math.sqrt`、`math.tanh`）中执行 `eval(self._code, ..., variables)` 返回结果。由于 `ifelse` 已转为 Python 三元条件表达式，求值具有短路特性，只计算命中的分支（例如当 $E = 0$ 时直接返回 `0`，不会触发另一分支中 `b / E` 的除零错误）。
4. **DEVSIM 符号表达式生成（`Formula.devsim(in_conditions=None, **variables)`）**：首先核对 `set(variables) == set(self.variables)`，不一致时抛出 `ValueError: the formula takes <self.variables>, not <tuple(variables)>`。
   - 若传入了 `in_conditions` 字典，先对 `self.text` 调用 `_substitute_in_conditions(self.text, in_conditions)`：递归定位每一层 `ifelse(condition, if_true, if_false)`（括号不匹配或参数非 3 个时同样抛出 `ValueError`），**仅在第一个参数 `condition` 内**用 `_substitute` 将变量名替换为 `in_conditions` 给定的表达式；
   - 随后对整个表达式调用 `_substitute(..., variables)`，将其余位置的自变量名替换为求解器变量名或表达式。
   - 这一步用于处理 DEVSIM 边模型中的零场保护（[field.md](field.md) 的 `physics_avalanche.py` 传入 `in_conditions={"E": "abs(ElectricField)"}`、`E="abs(ElectricField)+1"`）：DEVSIM 求值 `ifelse` 时会同时计算两个分支，分支内的 `b / E` 用 `abs(ElectricField)+1` 避免除以零，而条件判断中的阈值比较仍保持精确的 `abs(ElectricField) >= 1.75e5` 或 `abs(ElectricField) > 1e4`。

### 材料初始化、迁移率与碰撞电离系数计算（`material.py`, `impact_ionization.py`）

1. **构造 `Material` 实例（`Material.__init__` 与 `mat_database`）**：记录 `self.mat_name = mat_name`，调用 `self.mat_database()` 按 `"Si"`、`"SiC"`、`"Diamond"` 三个 `if` 分支写入 `permittivity`、`hole_mass`、`electron_mass`、默认 `avalanche_model` 与默认 `mobility_model`。若构造参数 `mobility_model != None`，覆盖 `self.mobility_model`；若 `avalanche_model != None`，覆盖 `self.avalanche_model`。`mat_name` 取 `"Si"`、`"SiC"`、`"Diamond"` 之一。
2. **求取载流子迁移率（`Material.cal_mobility(temperature, input_doping, charge, electric_field)`）**：
   - 设 $T = \text{temperature}$，$t = T / 300$，$E = \text{electric\_field}$，$N_{\text{eff}} = \text{input\_doping}$。
   - 若 `mat_name == 'SiC'` 且 `mobility_model == "Das"`、或 `mat_name == 'Diamond'` 且 `mobility_model == "Pernegger"`、或 `mat_name == 'Si'` 且 `mobility_model == "Selberherr"`：先取 `Neff = abs(Neff)`，再按 `charge > 0`（空穴）与 `charge <= 0`（电子）代入式 (3)–(7) 及对应参数算出 `mu` 并返回。
   - 若 `mat_name == 'Si'` 且 `mobility_model == "Reggiani"`：当 `Neff >= 0` 时设 `N_D = Neff, N_A = 0`，否则设 `N_A = -Neff, N_D = 0`；再按 `charge > 0` 与 `charge <= 0` 代入式 (8)–(10) 算出 `mu` 并返回。
3. **求取碰撞电离系数（`Material.cal_coefficient(electric_field, charges, temperature)` 与 `hatakeyama`）**：
   - 检查 `self.avalanche_model not in AVALANCHE_MODELS[self.mat_name]`；若条件为真（包括 `"Diamond"` 缺省的 `None`，以及为 `"Diamond"` 或 `"SiC"` 选了 `"vanOverstraeten"` 这类别的材料的模型），抛出 `ValueError: Avalanche model <self.avalanche_model> is not defined for <self.mat_name>`。
   - 初始化 `coefficient = 0.0`，设 $E = \text{electric\_field}$，$T = \text{temperature}$。`charges` 取 `-1`（电子）或 `+1`（空穴）；`charges` 为 `0` 时 `coefficient` 为 `0.0`。
   - 当 `avalanche_model == 'vanOverstraeten'` 时：按 `charges` 符号调用 `VAN_OVERSTRAETEN["electron"].value(E=E, T=T)` 或 `VAN_OVERSTRAETEN["hole"].value(E=E, T=T)`，由式 (11)–(12) 返回结果。
   - 当 `avalanche_model == 'Okuto'` 时：按 `charges` 符号设置电子或空穴的 $a, b, c, d$ 参数；若 $E > 1.0\times 10^5\ \text{V/cm}$，按式 (13) 计算 `coefficient`，否则置 `coefficient = 0.0`。
   - 当 `avalanche_model == 'Hatakeyama'` 时：按 `charges` 符号调用带 `@functools.cache` 缓存的 `hatakeyama("electron")` 或 `hatakeyama("hole")`（`angle_deg` 取缺省 `OFF_AXIS_DEG`）。`hatakeyama` 首次对给定 `(carrier, angle_deg)` 执行时，将 `angle_deg`（默认 `4.0` 度）转为弧度求 `along_0001 = cos(angle)`、`along_1120 = sin(angle)`，按式 (14)–(15) 预算出浮点常数 `B`、`a`、`A` 与子表达式字符串 `b`，构造并返回 `Formula` 对象；随后调用 `.value(E=E, T=T)` 按式 (16) 返回电离系数。式 (15) 的 $b(E)$ 在默认 $4^\circ$ 偏角下定义于 $E \lesssim 1.16\times 10^8\ \text{V/cm}$（电子）与 $E \lesssim 9.44\times 10^7\ \text{V/cm}$（空穴）。
4. **绘制漂移速度曲线（`Material.draw_velocity(temperature, Neff)`）**：
   - 检查 `plt is None`（环境中未安装 `matplotlib`）；若为 `None`，抛出 `RuntimeError: matplotlib is required for draw_velocity`。
   - 对 `i in range(1001)`、步长 `x_step = 1000`（即 $x = 1000\,i\ \text{V/cm}$，覆盖 $0$ 至 $10^6\ \text{V/cm}$），依次计算电子漂移速度 `y_e = x * self.cal_mobility(temperature, Neff, -1, x)` 与空穴漂移速度 `y_h = x * self.cal_mobility(temperature, Neff, +1, x)`（$\text{cm/s}$）。
   - 创建双对数坐标图（`plt.xscale("log")`、`plt.yscale("log")`），绘制 `"electron"` 与 `"hole"` 速度曲线，调用 `output(__file__, "model")` 获取输出目录，并将图像保存至 `<output_directory>/<mat_name>Mobility<mobility_model>.png`。

### 不完全电离与自由空穴浓度求解（`incomplete_ionization.py`）

1. **计算浓度修正能级（`_levels(dopant, concentration_cm3)`）**：计算 Pearson–Bardeen 电离能下降量 $\Delta E_{\text{fall}} = \text{dopant.fall\_ev\_cm} \cdot N^{1/3}$（$\text{eV}$），将 `dopant.levels` 中每个能级 $(\Delta E_{0,i}, f_i)$ 变换为 $(\Delta E_{0,i} - \Delta E_{\text{fall}}, f_i)$ 列表。
2. **生成电离比例 `Formula`（`ionized_fraction(material, element, concentration_cm3=0.0)`）**：从 `DOPANTS[material][element]` 查出 `Dopant`（未知的材料或元素名会抛出 `KeyError`）。遍历 `_levels(dopant, concentration_cm3)` 的第 $i$ 个能级，令 $n_{1,i}$ 子式为 `N_band*exp(-E<i>/(k*T))`，生成带零载流子下溢保护的项 `ifelse(carriers > 0, f<i>*N_band*exp(-E<i>/(k*T))/(N_band*exp(-E<i>/(k*T)) + g*carriers), f<i>)`，用 `" + "` 拼接全部能级项，构造自变量为 `["carriers", "N_band", "T"]` 的 `Formula` 返回。
3. **求解补偿受主层自由空穴浓度（`free_holes(material, element, acceptors_cm3, donors_cm3, temperature_k)`）**：
   - 读取 `dopant = DOPANTS[material][element]`（未知材料或元素抛出 `KeyError`）。
   - 校验 `dopant.kind != "acceptor" or len(dopant.levels) != 1`；若不满足单能级受主条件（如施主 `"N"`、`"P"`），抛出 `ValueError: <element> in <material> is not an acceptor of one level`。
   - 调用 `_levels(dopant, acceptors_cm3)` 取出唯一能级的电离能 `level_ev`（$\text{eV}$），调用 `BAND_STRUCTURE[material]["N_v"].value(T=temperature_k)` 计算价带有效状态密度 $N_v(T)$（$\text{cm}^{-3}$）。
   - 按式 (22)–(23) 依次计算 `freed_cm3`、`taken_cm3` 与二次方程正根并返回自由空穴浓度（$\text{cm}^{-3}$）。近似：温度高于施主冻结区，补偿施主 $N_D$ 完全电离，自由电子与本征载流子浓度 $n_i$ 略去，适用于 $N_A \ge N_D$ 的 p 型区。

## 软件实现

### 模块与函数分工

- `formula.py`：提供将 DEVSIM 表达式文本同时编译为 Python 求值函数与 DEVSIM 符号表达式字符串的 `Formula` 类，以及词法替换函数 `_substitute`、括号配对扫描函数 `_closing`、Python 三元表达式转换函数 `_python` 与 `ifelse` 条件内局部替换函数 `_substitute_in_conditions`。
- `material.py`：定义静态相对介电常数字典 `RELATIVE_PERMITTIVITY` 与 `Material` 类（含 `mat_database`、`cal_mobility`、`cal_coefficient`、`draw_velocity`），以及绘制 `"Si"`（$300\ \text{K}, 5\times 10^{12}\ \text{cm}^{-3}$）和 `"SiC"`（$300\ \text{K}, 5\times 10^{13}\ \text{cm}^{-3}$）漂移速度图的脚本入口 `main`。
- `impact_ionization.py`：定义玻尔兹曼常数 `BOLTZMANN_EV_PER_K`、4H-SiC 缺省晶向偏角 `OFF_AXIS_DEG`、硅的 van Overstraeten–de Man 碰撞电离公式字典 `VAN_OVERSTRAETEN` 以及带缓存的 4H-SiC Hatakeyama 碰撞电离公式生成函数 `hatakeyama`。
- `band_structure.py`：通过内部函数 `_material` 构建硅、4H-SiC 与金刚石的导带状态密度 `"N_c"`、价带状态密度 `"N_v"`、禁带宽度 `"E_g"` 与本征载流子浓度 `"n_i"` 公式字典 `BAND_STRUCTURE`。
- `dopants.py`：定义掺杂元素数据类 `Dopant`、构造辅助函数 `_donor` 与 `_acceptor` 以及三类材料的掺杂能级注册表 `DOPANTS`。
- `incomplete_ionization.py`：提供能级浓度修正辅助函数 `_levels`、掺杂电离比例公式生成函数 `ionized_fraction` 与补偿 p 型层自由空穴浓度求解函数 `free_holes`。
- `recombination.py`：定义 SRH 复合率公式 `SRH`、三类材料的默认载流子寿命字典 `SRH_LIFETIME`、陷阱辅助隧穿默认饱和场强 `TAT_SATURATION_FIELD` 与场增强因子公式 `TAT_FIELD_ENHANCEMENT`。

### 核心数据结构

- `Formula`（`formula.py`）：跨求解器物理公式对象，包含自变量名元组 `variables`（`tuple[str, ...]`，自变量单位依具体物理量而定：`E` 与 `F_sat` 为 $\text{V/cm}$，`T` 为 $\text{K}$，`n`、`p`、`n_i`、`n1`、`p1`、`carriers`、`N_band` 为 $\text{cm}^{-3}$，`tau_n`、`tau_p` 为 $\text{s}$）、展开参数后的 DEVSIM 表达式文本 `text`（`str`）以及预编译 Python 字节码 `_code`（`code` 对象）。
- `Material`（`material.py`）：材料物性与输运计算实例，包含材料名称 `mat_name`（`str`）、相对介电常数 `permittivity`（`float`，无量纲）、电子有效质量 `electron_mass` 与空穴有效质量 `hole_mass`（`float`，$\text{kg}$，`"Diamond"` 下未设置该属性）、迁移率模型名 `mobility_model`（`str`）以及碰撞电离模型名 `avalanche_model`（`str | None`）。
- `Dopant`（`dopants.py`）：冻结数据类（`@dataclass(frozen=True)`），包含杂质类型 `kind`（`str`，取 `"donor"` 或 `"acceptor"`）、能级与格位占比元组 `levels`（`tuple[tuple[float, float], ...]`，每项为 `(零掺杂电离能 [eV], 格位占比 [无量纲])`）、简并因子 `degeneracy`（`float`，无量纲）以及电离能随浓度下降系数 `fall_ev_cm`（`float`，默认 `0.0`，单位 $\text{eV}\cdot\text{cm}$）。

## 接口

使用者在器件文件中能设并与本包模型相关的只有下表列出的键，其余全部模型参数（相对介电常数、有效质量、各材料缺省选用的迁移率模型及各模型系数、碰撞电离参数与 $4.0^\circ$ 偏轴角、能带参数、掺杂能级与简并度、SRH 寿命、TAT 特征场强 `F_gamma`）均写死在代码中；其中写入 DEVSIM 区域参数的副本可在场求解中被 `parameter` 键覆盖，一个器件文件只设一个（见上文内置常数）。命令行用 `raser model --draw <模型>` 绘制模型曲线（见 [命令行接口](../cli.md)）；场求解与载流子输运的命令行用法分别见 [../stages/field.md](../stages/field.md) 与 [../stages/current.md](../stages/current.md)。

### 器件文件读取的键

器件 JSON 中的以下键由 [device.md](device.md)、[field.md](field.md) 与 [current.md](current.md) 读取后传入本包各接口：

| 键名 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `material` | 无（必选） | 无 | 半导体材料标识，取 `"Si"`、`"SiC"` 或 `"Diamond"`；网格区域里的 `"Silicon"`、`"SiliconCarbide"` 是 DEVSIM 区域材料名，与此键分开。其他取值下 `Material` 不设物性属性，估算电容时出 `AttributeError`，求迁移率时出 `UnboundLocalError`。此键决定 `Material`、`RELATIVE_PERMITTIVITY`、`BAND_STRUCTURE`、`DOPANTS`、`SRH_LIFETIME` 的材料分支及缺省 `mobility_model` |
| `temperature` | 无（必选） | $\text{K}$ | 器件温度 $T$，传入 `Material.cal_mobility`、`Material.cal_coefficient`、`BAND_STRUCTURE`、`free_holes` 及 DEVSIM 区域参数 `"T"` |
| `avalanche_model`, `enable_gain` | `None`, `False` | 无 | `has_avalanche` 为真时启用倍增；在 [field.md](field.md) 的 `_integrate_planar_gain` 与 [current.md](current.md) 的 `_build_local_gain_carriers` 中传入 `Material(material, avalanche_model=...).cal_coefficient`（支持 `"vanOverstraeten"`、`"Okuto"`、`"Hatakeyama"`），并在 [field.md](field.md) 的 `physics_avalanche.py` 中控制 `VAN_OVERSTRAETEN`、`hatakeyama` 与 `TAT_FIELD_ENHANCEMENT` 的启用；DEVSIM 场求解按区域材料取系数，`Silicon` 区域用 `VAN_OVERSTRAETEN`，`SiliconCarbide` 区域用 `hatakeyama`，`"Okuto"` 只进入漂移侧的平板增益积分与路径增益 |
| `doping.Donors`, `doping.Acceptors` | 无（场求解与纯扩散必选） | $\text{cm}^{-3}$ | 施主与受主浓度表达式；[field.md](field.md) 求得网格净掺杂 `NetDoping` 后由 [current.md](current.md) 传入 `Material.cal_mobility`，纯扩散收集 `collect_by_diffusion` 直接取两者数值差传入 `Material.cal_mobility` |
| `parameter` | 无（可选） | 依参数而定 | `{"name": <str>, "value": <float>}`，由 [field.md](field.md) 的 `create_parameter` 写入 DEVSIM 区域参数；当 `"name"` 为 `"F_sat"` 时覆盖 `"SiliconCarbide"` 区域的默认饱和场强 `TAT_SATURATION_FIELD`（`1e5` $\text{V/cm}$） |
| `resistive_layer.implanted`, `resistive_layer.thickness`, `resistive_layer.anneal` | 无（阻性层未给 `sheet_resistance` 时必选） | $\text{cm}^{-2}$, $\mu\text{m}$, $^\circ\text{C}$ | 铝注入 4H-SiC 阻性层的注入剂量、厚度与退火温度，由 [field.md](field.md) 的 `implanted_aluminium.sheet_resistance` 换算为激活受主与补偿施主浓度后传入 `free_holes("SiC", "Al", ...)` 与 `Material("SiC").cal_mobility` |

### 输入与输出文件

`core/model` 是纯内存物理模型库，输出的数值与符号表达式在内存中直接交给 [device.md](device.md)、[field.md](field.md)（写出 `<project>/field/<节点号>/` 场节点里的 `.pkl` 与 `.json` 文件）和 [current.md](current.md)（写出 `current.h5`）。

### 绘图输出

命令行使用 `raser model --draw <模型>` 绘制迁移率、漂移速度、碰撞电离系数等物理模型随电场、温度或掺杂浓度的曲线（见 [命令行接口](../cli.md)）。在 Python 中也可调用 `Material(<材料名>).draw_velocity(temperature, Neff)`（例如 `Material("SiC").draw_velocity(300, 1e14)`），通过 [../supports/README.md](../supports/README.md) 的 `output(__file__, "model")` 在 `<项目根>/model/model/` 下生成漂移速度图；项目根取环境变量 `RASER_PROJECT_PATH`，未设时为当前目录：

| 文件名 | 内容 | 单位 |
| --- | --- | --- |
| `<mat_name>Mobility<mobility_model>.png` | 给定温度 `temperature`（$\text{K}$）与有效掺杂浓度 `Neff`（$\text{cm}^{-3}$）下，电子（`"electron"`）与空穴（`"hole"`）在电场 $0$ 至 $10^6\ \text{V/cm}$（步长 $1000\ \text{V/cm}$，共 $1001$ 点）上的双对数漂移速度曲线，图标题为 `"Mobility Model"` | 横轴 `ElectricField  [V/cm]`，纵轴 `Velocity [cm/s]` |

## 参考文献

- [1] S. M. Sze, K. K. Ng, *Physics of Semiconductor Devices*, 3rd ed., Wiley-Interscience (2007), doi:10.1002/0470068329
- [2] S. Selberherr, W. Hänsch, M. Seavey, J. Slotboom, “The Evolution of the MINIMOS Mobility Model”, Solid-State Electronics 33 (1990) 1425, doi:10.1016/0038-1101(90)90117-W
- [3] S. Reggiani, M. Valdinoci, L. Colalongo, M. Rudan, G. Baccarani, “An Analytical, Temperature-Dependent Model for Majority- and Minority-Carrier Mobility in Silicon Devices”, VLSI Design 10 (2000) 467, doi:10.1155/2000/52147
- [4] R. van Overstraeten, H. de Man, “Measurement of the ionization rates in diffused silicon p-n junctions”, Solid-State Electronics 13 (1970) 583, doi:10.1016/0038-1101(70)90139-5
- [5] Y. Okuto, C. R. Crowell, “Threshold energy effect on avalanche breakdown voltage in semiconductor junctions”, Solid-State Electronics 18 (1975) 161, doi:10.1016/0038-1101(75)90099-4
- [6] T. Hatakeyama, T. Watanabe, T. Shinohe, K. Kojima, K. Arai, N. Sano, “Impact ionization coefficients of 4H silicon carbide”, Appl. Phys. Lett. 85 (2004) 1380, doi:10.1063/1.1784520
- [7] T. Hatakeyama, J. Nishio, C. Ota, T. Shinohe, “Physical modeling and scaling properties of 4H-SiC power devices”, Proc. Int. Conf. Simulation of Semiconductor Processes and Devices (SISPAD) (2005) 171, doi:10.1109/SISPAD.2005.201500
- [8] J. Burin, P. Gaggl, S. Waid, A. Gsponer, T. Bergauer, “TCAD Parameters for 4H-SiC: A Review”, arXiv:2410.06798 (2024), doi:10.48550/arXiv.2410.06798
- [9] G. L. Pearson, J. Bardeen, “Electrical Properties of Pure Silicon and Silicon Alloys Containing Boron and Phosphorus”, Phys. Rev. 75 (1949) 865, doi:10.1103/PhysRev.75.865
- [10] M. Spera, D. Corso, S. Di Franco, G. Greco, A. Severino, P. Fiorenza, F. Giannazzo, F. Roccaforte, “Effect of high temperature annealing ($T > 1650\ ^\circ\text{C}$) on the morphological and electrical properties of p-type implanted 4H-SiC layers”, Mater. Sci. Semicond. Process. 93 (2019) 274, doi:10.1016/j.mssp.2019.01.019
- [11] A. T. Collins, A. W. S. Williams, “The nature of the acceptor centre in semiconducting diamond”, J. Phys. C: Solid State Phys. 4 (1971) 1789, doi:10.1088/0022-3719/4/13/030
- [12] R. G. Farrer, “On the substitutional nitrogen donor in diamond”, Solid State Commun. 7 (1969) 685, doi:10.1016/0038-1098(69)90593-6
- [13] E. Gheeraert, S. Koizumi, T. Teraji, H. Kanda, “Electronic transitions of electrons bound to phosphorus donors in diamond”, Solid State Commun. 113 (2000) 577, doi:10.1016/S0038-1098(99)00546-3
- [14] W. Shockley, W. T. Read, Jr., “Statistics of the Recombinations of Holes and Electrons”, Phys. Rev. 87 (1952) 835, doi:10.1103/PhysRev.87.835
- [15] G. A. M. Hurkx, D. B. M. Klaassen, M. P. G. Knuvers, “A new recombination model for device simulation including tunneling”, IEEE Trans. Electron Devices 39 (1992) 331, doi:10.1109/16.121690
- [16] C. R. Crowell, S. M. Sze, “Temperature dependence of avalanche multiplication in semiconductors”, Appl. Phys. Lett. 9 (1966) 242, doi:10.1063/1.1754731
- [17] Synopsys, *Sentaurus Device User Guide*, Synopsys Inc., 碰撞电离的 van Overstraeten–de Man 模型一节
- [18] T. Hatakeyama, “Measurements of impact ionization coefficients of silicon carbide for high voltage power devices”, Phys. Status Solidi A 206 (2009) 2284, doi:10.1002/pssa.200925213
- [19] A. Das, S. P. Duttagupta, “TCAD simulation for alpha-particle spectroscopy using SiC Schottky diode”, Radiat. Prot. Dosim. 167 (2015) 443, doi:10.1093/rpd/ncu369
- [20] W. J. Schaffer, G. H. Negley, K. G. Irvine, J. W. Palmour, “Conductivity anisotropy in epitaxial 6H and 4H SiC”, MRS Proc. 339 (1994) 595, doi:10.1557/PROC-339-595
- [21] Z. Li et al., “Mechanisms of proton irradiation-induced defects on the electrical performance of 4H-SiC PIN detectors”, JINST 21 (2026) P03010, doi:10.1088/1748-0221/21/03/P03010, arXiv:2503.09016
- [22] H. Pernegger et al., “Charge-carrier properties in synthetic single-crystal diamond measured with the transient-current technique”, J. Appl. Phys. 97 (2005) 073704, doi:10.1063/1.1863417
