# Source 组件

Source 组件定义应用所用的粒子输入。Signal 将 Source 绑定到 Device 的 Geant4 描述。具有更大装置的应用将 Source 绑定到自身 G4Setup。

## 分类与条目

| 分类 | 定义 |
| --- | --- |
| [Beam](beam.md) | 粒子种类、能量、入射与束流分布 |
| [Decay](decay.md) | 放射源及其发射粒子分布 |

Am241、Sr90 和 Fe55 是 decay 分类中的具体 Source 条目。其同位素能谱与几何属于相应条目。

[Laser](../laser.md) 是独立的组件类型，其光学参数直接进入激光 Interaction。
