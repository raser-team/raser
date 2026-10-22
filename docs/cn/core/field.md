# Field

_RASER 5.0 半导体场计算_

Field 包含物理方程、网格构造、数值求解、TCAD 转换与场数据 I/O。一项解析后的配置选择完整计算，所得数据保存在相应 Device 项目下。

---

## ⚙️ 配置

偏压、温度、辐照状态、`field_dimension`、`field_source`、物理设置、网格设置与求解器设置共同构成一项 Field 配置。`field_source` 与其他值同为配置值。当前 source 包括 `devsim` 与 `tcad`。

结果所用配置保存为 `config.json`。其哈希作为 `field/` 下对应目录的名称：

```text
<device>/field/
└── <config-hash>/
    ├── config.json
    └── <field-files>
```

配置记录已解析的 Field 设置，以及提供传感器结构的 Device 版本。这些值共同标识 Physics、Mesher、Solver、Converter 与 I/O 所用输入。任一值发生变化即产生新的哈希与目录。

## 🧮 Physics

Physics 定义半导体区域上求解的方程。基础方程组包含泊松方程，以及电子与空穴连续性方程。

静电势 `φ` 给出电场

```math
\mathbf{E}=-\nabla\phi.
```

泊松方程为

```math
\nabla\cdot(\varepsilon\nabla\phi)=-\rho,
```

其中电荷密度包含电子、空穴、电离掺杂，以及所选辐照修正引入的电荷。

电子与空穴连续性方程为

```math
\frac{\partial n}{\partial t}
=\frac{1}{q}\nabla\cdot\mathbf{J}_n+G_n-R_n,
```

```math
\frac{\partial p}{\partial t}
=-\frac{1}{q}\nabla\cdot\mathbf{J}_p+G_p-R_p.
```

`J_n` 与 `J_p` 包含载流子的漂移和扩散。`G_n`、`G_p`、`R_n` 与 `R_p` 汇集已配置的产生与复合项。

### 辐照修正

辐照修正定义缺陷能级、引入率、俘获截面和注量。这些数值决定被俘获的电子与空穴密度、缺陷辅助产生与复合，以及电子和空穴俘获率。俘获电荷进入泊松方程，产生率与复合率进入连续性方程。

### 碰撞电离与击穿修正

碰撞电离修正根据材料参数与电场计算电子和空穴电离系数。所得载流子产生项进入两条连续性方程。步进加压期间求解该耦合方程组，得到 IV 结果中的雪崩与击穿行为。

### 隧穿修正

隧穿修正将配置的隧穿率加入载流子产生与复合项。当前实现包含带间隧穿、陷阱辅助隧穿与场增强复合表达式。

## 🕸️ Mesher

Mesher 定义 Physics 与 Solver 所用的材料、界面、接触、求解区域和数值网格。

DEVSIM 路径根据网格线、区域、接触和界面创建网格。该路径使用 DEVSIM 提供的一维与二维网格构造函数。

Gmsh 路径读取 Gmsh 网格，并将其物理组映射至 DEVSIM 区域、接触与界面。该映射与 Gmsh 文件和网格设置共同保存在 Field 配置中。

两条路径均产生一个包含已配置材料、区域、界面、接触、坐标与掺杂分布的 DEVSIM device。Mesher 在构造方程前校验这些定义。

## 🧭 Solver

Solver 接收方程与网格，建立初始解并施加配置的电压。数值设置包括绝对与相对误差限、迭代次数上限、初始电压步长、最大电压步长、步长增加因子、步长减小因子及保存电压点。

### 步进加压

步进加压从初始解开始，向配置偏压推进。收敛解作为下一步的起点。收敛后根据配置因子增加后续步长。收敛失败时减小步长，并从前一收敛解重新尝试。

求解器保存指定电压点与最终偏压点。每个保存点包含所选物理设置产生的场物理量。

### IV 与 CV

IV 计算在每个收敛电压点记录电压、电子电流、空穴电流与总电流。

CV 计算在每个收敛 DC 电压点执行 AC 求解。其配置包含频率与 AC 电压。结果记录电压与电容。

Field AC 计算还为 [Frontend](frontend.md) 提供传感器电学值。这些数值可包括体电容、电极间耦合、偏置电阻和 AC 耦合电容，并与计算所用的 Field 配置及工作条件关联。

<!-- TODO: 定义用于生成传感器网表的 Field AC 输出模式。 -->

### 权重场

为每个配置的读出电极求解权重势。对于电极 `k`，权重势 `ψ_k` 满足

```math
\nabla\cdot\left(\varepsilon\nabla\psi_k\right)=0.
```

电极 `k` 设为 `1 V`，其余电极设为 `0 V`。权重场为

```math
\mathbf{E}_{w,k}=-\nabla\psi_k.
```

结果按对应电极名称保存。当前实现保存权重势，并在需要时由该势得到权重场。

## 🔄 Converter

Converter 调用 Juan Sanchez 的 `tdr-convert` 包，将 TCAD TDR 文件转换为 DEVSIM 格式。转换后的文件通过 DEVSIM 加载，指定数据集随后传给 Field I/O。

转换配置包含 TDR 文件、偏压、坐标方向与指定 TCAD 数据集。当前实现读取 TCAD 电势、电场、掺杂、空间电荷、电子密度、空穴密度，以及电子和空穴复合数据。

## 💾 I/O

I/O 读取解析后的 Field 配置，并将计算所得场物理量写入由配置哈希选择的目录。

当前实现分别以 Python pickle（`.pkl`）文件写入电势、净掺杂、电子俘获率、空穴俘获率与权重势。每个 pickle 包含

```text
points
values
metadata:
    voltage
    dimension
```

电势、俘获率和掺杂按偏压保存。权重势按电极名称保存。加载时由已保存电势计算电场。

<!-- TODO: 定义最终场文件格式；`.pkl` 记录当前实现。 -->
