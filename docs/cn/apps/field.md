# Field

Field 应用计算一个 Device 的场数据。它作用于 Device 项目，结果保存在该 Device 项目下。

## 装置

Device 提供传感器结构与默认工作状态。调用可指定偏压等工作状态值。解析后的状态与 Field 设置共同构成一项 Field 配置。

## 计算

Field 应用按所选计算调用 [Core Field](../core/field.md)：

- 静电场：求解至指定偏压，保存场数据
- 权重场：为每个读出电极求解权重势
- IV：记录各电压点的电流
- CV：记录各电压点的电容
- TCAD 导入：将 TCAD 结果转换为同一格式的场数据

场数据按 Field 配置的哈希保存在 `<device>/field/` 下，供其他应用按同一配置读取。
