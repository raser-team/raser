# Beam source

Beam Source 描述进入 Device 或 G4Setup 的粒子。其定义包含粒子种类、能量、入射点、方向，以及空间或角分布。应用为此次运行加入事件数与随机种子。

Geant4 [Interaction](../../core/interaction.md) 使用 Source 定义与应用所选几何产生初级粒子。Source 标识及解析后的束流值记录在 `run.json` 中。
