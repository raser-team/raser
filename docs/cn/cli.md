# 命令行接口（`raser`）

`raser` 是统一命令行入口，`cli` 只负责把命令和参数分发给对应的环节、测试、应用或生命周期模块。环节名和它们的短命令、`status`、`new`、`model`、`device` 是保留字，实验文件夹不用这些名字。

## 命令

| 命令 | 做什么 | 页面 |
| --- | --- | --- |
| `raser signal <器件>` | 对这块器件跑 signal 测试：整条链跑完，给出电荷收集效率 | [bench/signal.md](bench/signal.md) |
| `raser timeres <器件>` | 对这块器件跑时间分辨（Time Resolution）测试 | [bench/timeres.md](bench/timeres.md) |
| `raser tct <器件>` | 对这块器件跑瞬态电流技术（Transient Current Technique）测试 | [bench/tct.md](bench/tct.md) |
| `raser telescope <器件>` | 把这块器件放在束流望远镜中间当被测器件，跑空间分辨测试 | [bench/telescope.md](bench/telescope.md) |
| `raser bmos` | 跑在线束流监测系统（Beam Monitor Online System） | [apps/bmos.md](apps/bmos.md) |
| `raser cflm` | 跑 CEPC 快速亮度监测器（CEPC Fast Luminosity Monitor） | [apps/cflm.md](apps/cflm.md) |
| `raser hbf` | 跑氢硼聚变（Hydrogen–Boron Fusion，p–¹¹B） | [apps/hbf.md](apps/hbf.md) |
| `raser pimg` | 跑质子成像（Proton Imaging） | [apps/pimg.md](apps/pimg.md) |
| `raser field [路径]`（短命令 `fld`） | 不给路径就是当前文件夹，给了就是相对或绝对路径；算器件里的电场、权重场、IV/CV | [stages/field.md](stages/field.md) |
| `raser deposit [路径]`（短命令 `dep`） | 在当前文件夹或给定路径的实验上跑到 `deposit`（用 Geant4 算粒子沉积的能量），缺的上游自动补上 | [stages/deposit.md](stages/deposit.md) |
| `raser current [路径]`（短命令 `cur`） | 在当前文件夹或给定路径的实验上跑到 `current`（让载流子在场中漂移，算电极上的感应电流），缺的上游自动补上 | [stages/current.md](stages/current.md) |
| `raser readout [路径]`（短命令 `rdo`） | 在当前文件夹或给定路径的实验上跑到 `readout`（把电流送进器件等效电路和前端放大器，得到波形），缺的上游自动补上 | [stages/readout.md](stages/readout.md) |
| `raser digitizer [路径]`（短命令 `digi`） | 在当前文件夹或给定路径的实验上跑到 `digitizer`（按示波器或数字化板的采样和量化把波形变成数字波形），缺的上游自动补上 | [stages/digitizer.md](stages/digitizer.md) |
| `raser trigger [路径]`（短命令 `trig`） | 在当前文件夹或给定路径的实验上跑到 `trigger`（按真实触发设备的条件决定记录哪些事例），缺的上游自动补上 | [stages/trigger.md](stages/trigger.md) |
| `raser reconstruction [路径]`（短命令 `reco`） | 在当前文件夹或给定路径的实验上跑到 `reconstruction`（从波形里取击中时间和幅度，束流测试里做径迹拟合），缺的上游自动补上 | [stages/reconstruction.md](stages/reconstruction.md) |
| `raser analysis [路径]`（短命令 `ana`） | 在当前文件夹或给定路径的实验上跑到 `analysis`（统计效率、时间分辨，并在 `<实验>/analysis/` 下出趋势图），缺的上游自动补上 | [stages/analysis.md](stages/analysis.md) |
| `raser status [路径]` | 打印 project 的参数表：各实验、各扫描点、各环节的状态和节点号 | [lifecycle/slices.md](lifecycle/slices.md) |
| `raser new --from <示例> <路径>` | 把 `examples/<示例>` 整个复制成新 project，配置完整，之后和示例互不影响 | [lifecycle/experiments.md](lifecycle/experiments.md) |
| `raser model --draw <模型>` | 画迁移率、碰撞电离系数等随电场、温度、掺杂的曲线 | [core/model.md](core/model.md) |
| `raser device --draw <器件>` | 画几何、电极、掺杂 | [core/device.md](core/device.md) |
| `raser <环节> --draw <对象>` | 画本环节的对象，例如 `readout` 画原理图和冲击响应，`field` 画网格和网格节点上的掺杂 | [stages/README.md](stages/README.md) |

## 全局选项

- `-b`：把运行作业提交到集群队列。
- `-t`：与 `-b` 联用，只检查并预览提交信息，不真正提交作业。
- `--help`：打印顶层或子命令的帮助信息并退出。
- `--version`：打印当前 `raser` 版本号并退出。

## 共用运行参数

- `-s`：指定每个扫描点并行运行的作业数。
- `--seed`：指定整数随机种子，让仿真结果可重复；不给时用当前时间戳作种子。
- `--same-seeds`：让各扫描点的同编号作业共用随机种子，从而复用未受扫描影响的上游结果。
- `--set`：用“段.键”作地址修改配置文件中的设置，例如 `--set field.voltage=100`。
- `--scan`：用“段.键”作地址扫描一个或多个设置，例如 `--scan field.voltage=100,200`。
- `--dry-run`：只打印将要运行的扫描点、环节和作业状态，不启动实际计算。

配置文件分段规则、扫描点展开与集群作业调度的细节见 [lifecycle/experiments.md](lifecycle/experiments.md) 和 [lifecycle/jobs.md](lifecycle/jobs.md)。
