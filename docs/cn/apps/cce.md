# 电荷收集

电荷收集应用研究指定辐照装置中从 Device 测得的电荷。其项目绑定一个 Device、一个 Source、前端电子学、ADC 定义以及测量所用的 G4Setup。

## 计算

G4Setup 和 Source 定义粒子相互作用。应用使用 [Signal](signal.md) 计算产生每个事件的载流子、电流和波形数据。[Metrics](../core/metrics.md) 从记录的通道推导电荷与幅度观测量。

电荷收集分析将事件观测量汇总为分布和摘要值。每项结果保留该次运行所选的 Device 状态、Field 配置、Source、G4Setup、前端和 ADC。
