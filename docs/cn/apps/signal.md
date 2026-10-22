# Signal

Signal 计算 Device 对粒子 Source 的电学响应。应用项目绑定一个 Device 组件、一个 Source 组件，以及读取传感器所用的前端电子学。

## 装置

Device 组件选择传感器状态和 Field 配置。Source 组件提供粒子定义及其在 Device Geant4 几何上的入射。前端选择确定传感器电学模型，以及连接至其电极的 AFE、PCB 或 ASIC 电路。

运行配置提供事件数、随机种子、执行模式和该次运行选定的值。解析后的装置记录在 `run.json` 中。

## 计算

对于每个事件，Signal 执行以下计算：

1. [Interaction](../core/interaction.md) 将 Source 放入 Device 的 Geant4 描述中，并由沉积能量产生载流子群。
2. [Current](../core/current.md) 在所选 Field 数据中输运载流子，为每个电极产生感应电流源。
3. [Frontend](../core/frontend.md) 将这些电流源连接到传感器及所选电子学网表，计算读出波形。

Signal 保存每个事件的相互作用数据、电极电流和前端波形。[电荷收集](cce.md)和[时间分辨](timeres.md)等应用可结合自身装置与分析定义使用这套计算。
