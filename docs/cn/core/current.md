# Current

_RASER 5.0 载流子输运与感应电流_

Current 输运 Interaction 产生的电子与空穴群，并计算每个读出电极上的瞬时感应电流。

## 载流子群

`ionized_pairs` 中的每个条目在 `track_position` 对应的 `[x, y, z, t]` 位置产生一个电子群和一个空穴群。两者群权重大小相等，电荷符号相反。

每个群记录其位置、产生时间、输运电荷及在探测器坐标中的路径。Device 提供材料、温度、运行时边界、读出电极，以及所选 Transport、Damage 与 Gain 设置。

## 输运

Field 提供各载流子位置处的电场、掺杂、电子俘获率与空穴俘获率。所选迁移率模型分别为电子和空穴计算

```math
\mu=\mu(T,N_{\mathrm{eff}},|\mathbf E|),
```

其漂移速度为

```math
\mathbf v_e=-\mu_e\mathbf E,
\qquad
\mathbf v_h=+\mu_h\mathbf E.
```

扩散遵循爱因斯坦关系

```math
D=\frac{k_B T}{q}\mu.
```

在时间步 `Δt` 内，每个空间方向的扩散分量从方差为 `2DΔt` 的高斯分布采样。漂移与扩散共同给出下一载流子位置。

Transport 设置定义时间步、最大漂移时间、空间边界容差与最小场强。载流子路径在到达探测器边界、设定漂移上限或设定低场条件时结束。

## 俘获

对于局部俘获率 `Γ`，一个路径段后的输运载流子数为

```math
Q(t+\Delta t)=Q(t)\exp(-\Gamma\Delta t).
```

电子群与空穴群采用 Field 提供的对应俘获率。沿路径累积的衰减决定信号感应所用的电荷。

## 增益

Gain 产生次级电子-空穴群，并使其在同一场中输运。所选雪崩模型提供依赖电场与温度的电子和空穴电离系数。

`planar_integral` 计算根据设定增益率，在声明的增益边界产生次级群。`local_path` 计算沿每条载流子路径积分电离系数：

```math
N_{\mathrm{secondary}}
=N_{\mathrm{primary}}
\left[\exp\left(\int\alpha\,ds\right)-1\right].
```

产生的电子和空穴从其产生位置与时间进入输运。其感应电流加入初级信号。

## 感应电流

Field 为每个读出电极 `k` 提供一个权重势 `ψ_k`。对于从 `r_n` 移动到 `r_{n+1}`、电荷为 `q` 的载流子群，该电极上的感应电荷为

```math
\Delta Q_k
=q\left[\psi_k(\mathbf r_{n+1})-\psi_k(\mathbf r_n)\right].
```

相应时间步内的电流为

```math
I_k=\frac{\Delta Q_k}{\Delta t}.
```

该计算产生与各电极对应的瞬时 Norton 电流源。完整结果在公共时间轴上包含电子、空穴、增益及总电流贡献。电极顺序遵循 Device 声明的读出布局。

[Frontend](frontend.md) 将这些电流源连接到传感器电学模型和 AFE 电路。
