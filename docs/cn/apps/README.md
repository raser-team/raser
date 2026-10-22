# 应用

应用描述传感器的使用场景。每个应用项目选择构成装置的可复用对象，加入场景特有条件，并保存产生的运行记录。

## 组成

所选对象记录为具有明确类型的[组件](../components/README.md)。Device 组件提供传感器及其工作状态。Source 或 Laser 组件定义激励。PCB、ASIC、AFE 和 ADC 组件定义测量所用的电子学。周围几何参与相互作用时，G4Setup 组件定义 Geant4 场景。

应用将这些定义交给 [Core](../core/README.md)，并通过 [Runs](../supports/runs.md) 记录解析后的选择。依赖具体场景的结果保存在应用项目中。

## 应用绑定

| 应用 | 绑定组件 | 计算 |
| --- | --- | --- |
| [Signal](signal.md) | Device、Source 与前端电子学 | 粒子相互作用、感应电流与前端波形 |
| [TCT](tct.md) | Device、Laser 与前端电子学 | 激光注入、感应电流与扫描响应 |
| [时间分辨](timeres.md) | Device、Source、前端电子学、ADC 及其 G4Setup | 时间分辨装置中的信号生成与时间分析 |
| [电荷收集](cce.md) | Device、Source、前端电子学、ADC 及其 G4Setup | 信号生成与电荷分布分析 |
| [BMOS](bmos.md) | Device、Source、前端电子学及其 G4Setup | 束流监测器响应与幅度分布 |
| [Lumi](lumi.md) | Device、Source、读出电子学及其 G4Setup | 亮度监测器输运、响应与汇总 |
| [Telescope](telescope.md) | 多个 Device、Source、读出定义及其 G4Setup | 多层相互作用与径迹重建 |

## 项目数据

应用项目保存其组件选择、命名运行配置及运行产物：

```text
<application-project>/
├── components/
├── config/
└── <workflow>/
    └── <run-id>/
        ├── run.json
        ├── batch/
        └── analysis/
```

具体运行布局由[运行记录](../supports/runs.md)定义。
