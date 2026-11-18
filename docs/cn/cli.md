# 命令行接口（`raser`）

`raser`（定义于 `src/raser/cli/raser.py`）是 RASER 的统一命令行入口。`cli` 只负责分发：解析顶层全局选项、识别实验目录或短命令别名、设置工程与组件搜索路径上下文，并将参数交给对应的模块执行。各子命令的参数均由各自模块注册，具体选项含义与默认值见各命令自己的文档页面。

## 命令一览

| 命令（短别名） | 做什么 | 注册模块 | 页面 |
| --- | --- | --- | --- |
| `field`（`fld`） | 求解器件电势、电场、权重场与 IV/CV，使用 `-ext` 时导入单个偏压的 TCAD 场解并求解权重势，或求解某个实验各扫描点所需的共享场 | `raser.stages.field` | [stages/field.md](stages/field.md) |
| `deposit`（`dep`） | 在实验上跑到 `deposit` 这一步为止；只给器件名时，用默认的 `signal` 实验（文件夹 `work/<器件>/signal`） | `raser.stages.stage_commands` | [stages/deposit.md](stages/deposit.md) |
| `current`（`cur`） | 在实验上跑到 `current` 这一步为止，缺的上游自动补；只给器件名时，用默认的 `signal` 实验（文件夹 `work/<器件>/signal`） | `raser.stages.stage_commands` | [stages/current.md](stages/current.md) |
| `readout`（`rdo`） | 在实验上跑到 `readout` 这一步为止，缺的上游自动补；只给器件名时，用默认的 `signal` 实验（文件夹 `work/<器件>/signal`） | `raser.stages.stage_commands` | [stages/readout.md](stages/readout.md) |
| `reconstruction`（`reco`） | 在实验上跑到 `reconstruction` 这一步为止，缺的上游自动补；只给器件名时，用默认的 `signal` 实验（文件夹 `work/<器件>/signal`） | `raser.stages.stage_commands` | [stages/reconstruction.md](stages/reconstruction.md) |
| `analysis`（`ana`） | 汇总实验各请求扫描点已完成作业的电荷收集效率与时间分辨结果（若有扫描点无已完成作业，处理其余点后报错） | `raser.stages.analysis` | [stages/analysis.md](stages/analysis.md) |
| `status` | 查看实验各扫描点与各环节的作业运行状态 | `raser.lifecycle.status` | [lifecycle/slices.md](lifecycle/slices.md) |
| `signal` | 运行单器件信号仿真工作流 | `raser.bench.signal` | [bench/signal.md](bench/signal.md) |
| `cce` | 运行电荷收集效率实验工作流 | `raser.bench.cce` | [bench/cce.md](bench/cce.md) |
| `timeres` | 运行时间分辨实验工作流 | `raser.bench.timeres` | [bench/timeres.md](bench/timeres.md) |
| `tct` | 运行瞬态电流技术（TCT）激光脉冲仿真工作流 | `raser.bench.tct` | [bench/tct.md](bench/tct.md) |
| `telescope` | 运行束流望远镜（`taichu_v1`、`taichu_v2`）空间分辨仿真工作流 | `raser.bench.telescope` | [bench/telescope.md](bench/telescope.md) |
| `bmos` | 运行束流监测在线系统（BMOS）仿真工作流 | `raser.apps.bmos` | [apps/bmos.md](apps/bmos.md) |
| `cflm` | 运行 CEPC 快速亮度监测器（CFLM）24 垫片仿真工作流 | `raser.apps.cflm` | [apps/cflm.md](apps/cflm.md) |

## 分发机制与全局选项

### 1. 顶层全局选项（位于子命令之前）

- `-h`、`--help`：打印顶层帮助信息并退出；在子命令后传入可查看该子命令自身注册的参数说明（`raser <命令> --help`）。
- `--version`：输出当前版本（例如 `raser 5.0`）并退出。
- `-b`、`--batch`：将支持作业提交的子命令（工作流与环节命令）提交到集群；可叠写为 `-bb`、`-bbb` 等，重复次数对应申请的内存档位（每档 `8000` MB）。
- `-t`、`--test`：与顶层 `-b` 联用时等价于开启支持作业提交的子命令的 `--dry-run`。

### 2. 实验目录内的自动命令补全

当当前工作目录包含实验配置文件 `config.json`，配置中的 `"workflow"` 首词已注册，且命令行参数中未出现 `-h`、`--help`、`--version` 或任何与已注册命令名/短别名相同的词时，`raser` 会从当前目录的 `config.json` 读取 `"workflow"`（若存在 `"device"` 键则再读取 `"device"`）并自动插入到全局选项之后。因此在实验文件夹（如 `work/HPK-Si-PiN/signal`）内直接执行 `raser -s 2` 等价于执行 `raser signal HPK-Si-PiN -s 2`。

### 3. 共用运行参数

除 `status` 外的各工作流与环节命令均由 `lifecycle` 注册共用运行参数：

- **作业与随机种子**：`-s` / `--jobs` 指定每个扫描点的并行作业数；`--seed` 指定运行种子整数；`--same-seeds` 使各扫描点同编号作业在对应切片使用相同随机种子，并共享输入和依赖未变的切片。以上三个参数仅由带种子的工作流（`Workflow.seeds=True`）及四个环节命令（`dep|cur|rdo|reco`）注册。
- **参数设置与扫描**：`--set key=value` 固定单个参数或组件文件内点分地址的值，`--scan key=v1,v2,...` 对参数或文件内键路径做扫描（普通实验运行写入实验 `config.json`；`--dry-run` 预览及 `raser field <实验目录>` 仅用于选择本次点，不写入实验配置）。
- **集群提交与预览**：`-b` / `--batch`、`-mem`（`8000 * mem` MB）用于提交集群作业；`--dry-run` 仅打印待运行扫描点、作业与切片状态（`raser field <实验目录>` 打印各点共享片是否就绪）而不启动计算。

上述共用参数的详细规则、配置合并优先级与扫描文件夹命名方式见 [lifecycle/experiments.md](lifecycle/experiments.md)，集群提交与作业锁机制见 [lifecycle/jobs.md](lifecycle/jobs.md)。

### 4. 运行路径环境变量

- `RASER_WORK_PATH`：工作根目录（源码树下默认为 `<仓库根目录>/work`，包安装下默认为 `<当前目录>/work`）。
- `RASER_PROJECT_PATH`：非空时在 `infer_project_root()` 路径推导中显式指定当前工程根目录，覆盖按器件名推导的 `<RASER_WORK_PATH>/<device>`（独立的 `deposit`、`current`、`readout`、`reconstruction` 命令仅传器件名时直接使用 `<RASER_WORK_PATH>/<device>/signal` 及其工程上下文）。
- `RASER_COMPONENT_PATH`：附加组件搜索路径（以系统路径分隔符连接），优先于内置组件目录 `src/raser/components/` 被检索（详见 [supports/README.md](supports/README.md)）。

## 常见报错

- `raser: <what>. <how>`（退出码 `1`）：命令执行期间捕获 `MissingDependency`，或导入过程中触发 `error.name` 恰为 `"ROOT"` 或 `"cppyy"` 的 `ModuleNotFoundError` 时输出对应提示，例如缺少 `g4ppyy`、`ngspice` 或 `ROOT`。
- `<target>: neither an experiment folder (a folder with a config.json) nor a device; give one of them, e.g. work/<device>/cce or HPK-Si-PiN`（退出码 `1`）：传给 `raser dep|cur|rdo|reco` 的参数既不是含 `config.json` 的实验目录，也未能找到对应器件文件。
- `<folder>: the experiment <workflow> has no <stage> slice; its slices: <names>`（退出码 `1`）：目标实验的工作流中不包含所请求的环节。

## 相关页面

- [README.md](README.md)
- [getting-started.md](getting-started.md)
- [architecture.md](architecture.md)
- [lifecycle/experiments.md](lifecycle/experiments.md)
- [lifecycle/slices.md](lifecycle/slices.md)
- [lifecycle/jobs.md](lifecycle/jobs.md)
- [stages/README.md](stages/README.md)
- [supports/README.md](supports/README.md)
