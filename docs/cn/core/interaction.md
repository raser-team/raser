# Interaction

_RASER 5.0 传感器中的粒子与激光相互作用_

Interaction 计算 Device 中电子-空穴对产生的位置与时间。粒子输运、激光吸收和指定的 MIP 径迹均为载流子输运产生相同的两组数组。

## 载流子生成数据

`track_position` 为每个载流子组保存一个 `[x, y, z, t]` 条目。位置采用以微米表示的探测器坐标，时间以秒表示。`ionized_pairs` 包含对应的电子-空穴对数。两数组长度相同、顺序对应。

能量沉积 `E_dep` 产生

```math
N_{eh}=\frac{E_{\mathrm{dep}}}{W},
```

其中 `W` 是 Device 材料的电离能。一个载流子组可通过 `ionized_pairs` 数值表示大量物理电子-空穴对。

## Geant4 相互作用

Geant4 计算采用 Device 声明的几何、灵敏体、材料与探测器坐标映射。源定义提供粒子类型、能量、初始位置、方向、事件数与 Geant4 执行设置。可复用源定义见 [Source 组件](../components/source/README.md)。

Geant4 输运每个初级粒子，并记录灵敏体中每一步的位置与沉积能量。事件总量、步位置、步能量和粒子方向按事件分组。Device 映射随后将灵敏体位置转为探测器坐标。

每一步的沉积能量除以材料电离能，得到 `ionized_pairs`。映射后的步位置与事件时间构成 `track_position` 中的对应条目。

## 激光相互作用

激光相互作用计算单光子吸收（SPA）或双光子吸收（TPA）产生的载流子密度。其定义包含波长、脉冲能量、时间宽度、空间宽度、折射率、焦点、传播方向和空间积分步长。

对于 SPA，载流子密度取决于局部光强及沿光束的指数吸收：

```math
n_{\mathrm{SPA}}(s,r)
=\frac{\alpha\lambda}{h_{\mathrm P}c}
I(s,r)\exp[-\alpha(s+d)].
```

对于 TPA，空间计算采用脉冲能流密度 `F(s,r)` 与单位面积时间高斯函数 `g(t)`。脉冲积分载流子密度为

```math
n_{\mathrm{TPA}}(s,r)
=\frac{\beta_2\lambda}{2h_{\mathrm P}c}
F^2(s,r)\int g^2(t)\,dt,
```

其中

```math
\int g^2(t)\,dt
=\frac{\sqrt{2\ln2}}{\sqrt{\pi}\,\tau_{\mathrm{FWHM}}}.
```

这里，`s` 是沿光束方向的坐标，`r` 是距光束轴的横向距离，`d` 是从入射表面到焦点的距离，`h_P` 是普朗克常数。顶部、底部和边缘注入将这些光束坐标映射至探测器坐标。

空间网格在每个网格单元内积分载流子密度。网格中心构成 `track_position`，积分后的载流子数构成 `ionized_pairs`。中心时间与时间宽度定义这些载流子组对应的激光脉冲轮廓。

## 指定的 MIP 径迹

指定的 MIP 径迹是两个探测器坐标点之间的直线段。线段被分为等长载流子包，各包位于相应单元中心。沉积以每微米电子-空穴对数或每微米沉积能量给出。

对于长度为 `L`、分为 `N` 个载流子包的径迹，每个包包含

```math
N_{eh}^{\mathrm{packet}}
=\frac{L}{N}\left(\frac{dN_{eh}}{dx}\right).
```

载流子包中心与产生时间构成 `track_position`。各包权重构成 `ionized_pairs`。
