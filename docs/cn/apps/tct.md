# TCT

TCT 计算 Device 对激光注入的瞬态响应。应用项目绑定一个 Device 组件、一个 Laser 组件，以及 TCT 装置所用的前端电子学。

## 装置

Device 组件选择传感器状态和 Field 配置。Laser 组件提供吸收方式、方向、光脉冲、焦点及空间采样。前端选择提供测量时连接的传感器与读出电路。

位置扫描加入扫描轴、位置及用于重建的电极响应。这些值描述 TCT 测量，并随运行记录保存。

## 计算

1. 激光 [Interaction](../core/interaction.md) 将光脉冲转化为 Device 内部的载流子群。
2. [Current](../core/current.md) 在所选 Field 数据中输运这些载流子并计算电极电流源。
3. [Frontend](../core/frontend.md) 计算传感器及 TCT 电子学产生的波形。
4. 位置分析结合记录的波形与注入位置，形成响应曲线和位置分辨结果。

单次注入和各扫描点采用运行记录中的同一组 Device、Laser、Field 与前端定义。
