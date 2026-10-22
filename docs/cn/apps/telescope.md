# Telescope

Telescope 描述多层径迹装置。其项目绑定各层所用的 Device、一个粒子 Source、读出定义，以及包含各层放置和周围几何的 G4Setup。

## 装置

G4Setup 为每层给出 Device 引用、位置、方向和灵敏体映射。Source 定义入射粒子。所选读出定义提供构造击中与簇所用的通道测量值。

Telescope 装置可附带 ACTS 配置，用于 ACTS 输运、数字化、径迹种子生成和径迹重建。

## 计算

Geant4 相互作用在 telescope 各层产生能量沉积。Device 响应将沉积映射至读出通道。Telescope 构造击中和簇，对有序层上的径迹进行拟合，并推导逐层残差与分辨结果。参数研究改变已记录的装置值，同时保留对应的 G4Setup 和 Device 定义。
