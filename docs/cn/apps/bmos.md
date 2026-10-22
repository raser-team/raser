# BMOS

BMOS 描述束流监测器装置及其传感器响应。其项目绑定一个 Device、一个粒子 Source、前端电子学，以及包含监测器几何的 G4Setup。

## 计算

Source 在 BMOS G4Setup 中输运。沉积于 Device 的能量经 Core 的 Interaction、Current 和 Frontend 计算，转化为载流子群、电极电流源和前端波形。

BMOS 记录事件响应，并对所选 Device 状态、束流、几何和电子学推导信号幅度分布。
