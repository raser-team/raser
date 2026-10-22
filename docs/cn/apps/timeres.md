# 时间分辨

时间分辨应用描述时间测量所用的源、装置、读出与分析。其项目绑定一个 Device、一个 Source、前端电子学、ADC 定义，以及该测量专用的 G4Setup。

## 装置

G4Setup 在实验几何中放置 Device 及周围材料。Source 定义入射粒子。前端组件描述传感器负载与模拟响应，ADC 提供时间分析所用的采样波形与阈值。

每次运行共同记录所选 Device 状态、Field 配置、Source、G4Setup、前端和 ADC。

## 计算

时间分辨使用 [Signal](signal.md) 计算在其 G4Setup 中产生事件波形。[Metrics](../core/metrics.md) 从记录的通道提取幅度、到达时间、过阈时间、恒比时间、电荷及位置数据。应用随后为所选装置建立时间分布与分辨结果。
