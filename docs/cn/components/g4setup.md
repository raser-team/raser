# G4Setup 组件

G4Setup 组件定义应用所用的 Geant4 场景。它包含 world、属于装置的材料与体、所引用 Device、PCB 和 ASIC 几何的放置与方向，以及将沉积返回这些对象的灵敏体映射。

装置还提供场景的 Geant4 物理选择、产生与步长设置以及坐标变换。持有该次运行的应用将 Source 组件放置在此场景中。

Signal 可采用 Device 携带的 Geant4 描述。装置几何会改变相互作用的应用绑定自身的 G4Setup。
