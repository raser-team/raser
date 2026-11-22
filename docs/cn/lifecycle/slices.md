# 片与重跑

`src/raser/lifecycle/slices.py`、`src/raser/lifecycle/status.py`、`src/raser/lifecycle/workflow.py` 与 `src/raser/stages/chain.py` 管链上各环节之间的依赖、结果的复用和 `raser status`。它承接 [实验、扫描点与种子](experiments.md) 展开的扫描点与分段配置，以及实验类写明的环节组成；链的组装见 [仿真链与环节入口（`stages`）](../stages/README.md)。本模块对每个环节的输入取指纹，决定哪些节点复用、哪些要新算，并在一个作业里按依赖顺序运行各环节。要新算的作业交给 [作业、日志、锁、断点续跑与集群提交](jobs.md) 在本地或集群上跑；写好的节点交给下游环节和 [统计分析环节（`stages/analysis`）](../stages/analysis.md) 读取。

## 行为

### 链上的环节

链上有八个环节，地位相同。每个环节读上游环节写出的结果：

| 环节 | 读哪些环节的结果 |
| --- | --- |
| `field` | 无 |
| `deposit` | 无 |
| `current` | `field`、`deposit` |
| `readout` | `field`、`current` |
| `digitizer` | `readout` |
| `trigger` | `digitizer` |
| `reconstruction` | `trigger` |
| `analysis` | `deposit`、`current`、`reconstruction` |

`field` 和 `deposit` 各自独立，是链的两个根。器件的场是这块器件的资产，放在 `work/<器件>/field/`，被这块器件的各个实验共用。

只想跑到链上某一环节时，运行这个环节的命令，例如 `raser readout [路径]`、`raser digitizer [路径]`（`digi`）、`raser trigger [路径]`（`trig`）。程序补上缺的上游，在这个环节停下。命令清单见 [命令行接口（`raser`）](../cli.md)。

### 节点与指纹

一个环节在一组输入下算出的一份结果是一个节点，放在 `<实验>/nodes/<环节>/<节点号>/`。`deposit` 到 `reconstruction` 每个作业一个节点，`field` 和 `analysis` 每个扫描点一个节点；`analysis` 的上游是这个点各作业的节点，它的指纹因此记下了统计了哪些作业。节点的输入有四样：

- 这个环节用到的设置值；
- 组件文件里它用到的那一部分；
- 上游各节点的节点号；
- 测量环节（`deposit`、`current`）的种子，以及 `readout`（NGspice 噪声）、`digitizer`（时钟相位、孔径抖动）自己的种子，都由作业的种子派生；作业的种子由主种子、作业号和测量相关的扫描轴取值派生，见[实验、扫描点与种子](experiments.md#种子)。

指纹由这些输入算出，指纹就是节点号。节点文件夹里有这个环节写出的文件和一份 `node.json`。`node.json` 原样记下输入，另记代码版本、运行环境和运行状态。器件的场同样是节点，存在 `work/<器件>/field/` 下。

上游的节点号是下游的输入。一个节点变了，直接或间接读它的环节都得到新节点号，其余环节的节点号保持不变。例如只改 `readout` 段的一个设置：`field`、`deposit`、`current` 的节点照常复用，`readout` 和下游的 `digitizer`、`trigger`、`reconstruction`、`analysis` 算成新节点。

### 复用

指纹相同就复用，不管它是在哪个扫描点、哪次运行里算出来的。原样再跑一次同一条命令（带同一个 `--seed`），已算完的节点直接复用，只算缺的。

节点只增不减。把设置改回去，视图重新指回原来的节点，直接复用。例如把每个作业的事例数从 20 改成 40，全部算成新节点，旧节点留着；再改回 20，视图指回旧节点，全部直接复用。

### 扫描点之间共用节点

扫描只影响下游的设置时，上游节点在各点之间共用。换偏压是重新测，两档偏压各测各的。

在 signal 上同时扫两件事：`field.voltage=100,200`，和 `readout` 里一个电阻的两档取值。

| 环节 | 节点数 | 原因 |
| --- | --- | --- |
| `deposit`、`current` | 2 | 换偏压是重新测，两档偏压各测各的；电阻只有 `readout` 读，两档电阻共用这两个节点 |
| `readout` 及以后 | 4 | 两档偏压乘两档电阻 |

加 `--same-seeds` 时，各扫描点的同编号作业共用随机种子，未受扫描影响的上游结果在各点之间复用。

每次运行时，程序从 `config.json` 算出参数表 `points.json`：一行一个扫描点，写着各扫描轴的取值，以及每个环节用的节点号。

### 视图

`<实验>/points/<点名>/<环节>/` 是一个文件夹，这个点的每个作业在里面有一个以作业号命名的软链接，指向这个作业在这一环节的节点；`field` 和 `analysis` 一个点只有一个节点，`points/<点名>/field`、`points/<点名>/analysis` 直接是软链接。点名按扫描轴的取值起，例如 `voltage_100`，是给人看的入口。每个点都按全部扫描轴的取值起名；不做扫描的实验只有一个点，叫 `default`，有扫描时没有这个点。改了设置或加了扫描轴，点名可能不变，指向的节点会跟着变，参数和结果始终对得上。

### `analysis` 统计哪些作业

`analysis` 把一个扫描点上测的是同一件事的已完成作业都统计进来，不论是哪次运行、哪个种子算出来的。换一个 `--seed` 再跑一次，是给这个点加统计量。设置分三类：

| 类别 | 例子 | 不同时 |
| --- | --- | --- |
| 物理设置 | 器件、偏压、源、装置、放大器、阈值 | 是另一个测量，不合并 |
| 统计量 | 种子、每个点的作业数、每个作业的事例数 | 合并统计 |
| 只管画图 | `plots` | 合并统计 |

点测的是什么，以最近一次运行为准。读同一份沉积的两条链（例如一条画了图、一条没画）是同一批事例，只算一次。一个点的结果写在它的 `analysis` 节点里；节点号由它统计的那些作业决定，换一组设置得到另一个节点，原来的结果留着，设置改回去时 `points/<点名>/analysis` 指回原来的节点。`raser ana` 在屏幕上写出每个点统计的事例数和各次运行的作业数，例如 `default: 200 events of seed 1: 2 jobs, seed 2: 4 jobs`；没给 `--seed` 的运行按启动时间列出；因设置不同没算进来的作业另起一行，写明个数和不同的设置，例如 `default: 2 jobs measured something else and are not counted: source=decay/Am241`。

### 代码版本

代码版本和节点记录的不一致时，只给一条提示，结果照常复用。

### 加锁

每个节点单独加锁。写到一半的节点带 `.part` 后缀，写完才改成正式的名字，正式名字的节点都是完整结果。

### 提前结束

一个环节没给下游留下可算的东西时，这个作业到此结束。例如 `deposit` 一个事例也没记录：下游环节直接记为完成。

### 查看进度

`raser status [路径]` 打印 project 的参数表：各实验、各扫描点、各环节的状态和节点号。

```bash
raser status work/my-PiN
```

每一格写这个点在这个环节的状态和节点号。状态写成 `<已完成的作业数>/<作业数> done`，例如 `2/2 done`；没完成的作业在分号后按状态列出作业号。作业的状态有七种：

- **`done`**：这个作业在这个环节的结果已经写完。
- **`running`**：正在运行。
- **`submitted`**：已提交到集群，调度器确认它还在集群里。
- **`uncertain`**：已提交，但查询调度器报错或超过 `120 s`，确认不了。
- **`failed`**：已提交而调度器里已查不到它、结果又没写完；或本地作业留下了日志却没跑完。
- **`waiting`**：上游环节还没写完，或要用的场还没就绪。
- **`not started`**：上游都已写完，这个作业还没启动、没提交，也没有失败的日志。

启动前加 `--dry-run`，只打印将要运行的扫描点、环节和作业状态，打印完即返回。

## 规则

### 节点号的传递

1. 环节的输入只有四样：本环节用到的设置值、组件文件里它用到的部分、它直接读的上游节点的节点号、测量环节（`deposit`、`current`）的种子，以及 `readout`（NGspice 噪声）、`digitizer`（时钟相位、孔径抖动）自己的种子。
2. 节点号是这四样输入的指纹。代码版本、运行环境、运行状态另记在 `node.json` 里。
3. 上游节点号进了下游的输入，所以变化沿“链上的环节”那张表向下传：一个环节的节点号变了，读它的环节的节点号跟着变，一直传到链尾。

### 复用与共用

1. 要算某个扫描点的某个环节时，先算出它的节点号。这个节点号的节点已经存在，就直接复用。
2. 两个扫描点在某个环节的输入相同，节点号就相同，两点共用这一个节点。
3. 节点只增不减。设置改回去，节点号回到原来的值，视图指回原来的节点。
4. 代码版本和节点记录的不一致时照常复用，只给一条提示。

## 软件实现

### 模块与文件分工

- `src/raser/lifecycle/slices.py`：环节之间的依赖查询（谁读谁、上游的传递闭包），以及一个作业里按依赖顺序逐个运行各环节。
- `src/raser/lifecycle/nodes.py`：节点本身：输入的规范写法与指纹（`fingerprint`、`node_of`）、作业种子与环节种子（`job_seed`、`stage_seed`）、节点的加锁与写入（`lock`、`start`、`finish`、`found`）、视图链接（`link_view`）和参数表（`write_points`）。
- `src/raser/lifecycle/workflow.py`：判断哪些结果复用、哪些新算，安排扫描点之间的共用和各扫描点的运行顺序。
- `src/raser/lifecycle/status.py`：`raser status` 子命令。
- `src/raser/stages/chain.py`：把各环节组装成标准链。

## 接口

### 选项

| 选项 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `raser status [路径]` | 无 | 无 | 打印 project 的参数表：各实验、各扫描点、各环节的状态和节点号 |
| `--seed` | 无 | 无 | 整数随机种子，让仿真结果可重复 |
| `--same-seeds` | 关 | 无 | 各扫描点的同编号作业共用随机种子，未受扫描影响的上游结果在各点之间复用 |
| `--dry-run` | 关 | 无 | 只打印将要运行的扫描点、环节和作业状态，打印完即返回 |

`--set`、`--scan` 用“段.键”作地址，例如 `--set field.voltage=100`、`--scan field.voltage=100,200`；扫描语法见 [实验、扫描点与种子](experiments.md)。

### 读写的文件

- `<实验>/config.json`：本模块只读。写全这次运行用的设置，按 `field`、`deposit`、`current`、`readout`、`digitizer`、`trigger`、`reconstruction`、`analysis` 八段分开，格式见 [实验、扫描点与种子](experiments.md)。
- `<实验>/points.json`：参数表。每次运行时从 `config.json` 算出，一行一个扫描点，写着各扫描轴的取值和每个环节用的节点号。`raser status` 打印它。
- `<实验>/nodes/<环节>/<节点号>/`：节点。内有这个环节写出的文件和 `node.json`；写到一半带 `.part` 后缀。
- `work/<器件>/field/<节点号>/`：器件的场节点，被这块器件的各个实验引用。
- `<实验>/points/<点名>/<环节>/<作业号>`：视图，指向这个作业在这一环节的节点的软链接；`points/<点名>/field`、`points/<点名>/analysis` 各是一个软链接。

节点里各环节写出的数据文件，格式见 [场求解与加载（`core/field`）](../core/field.md)、[能量沉积与电离（`core/deposit`）](../core/deposit.md)、[载流子漂移与感应电流（`core/current`）](../core/current.md)、[电子学读出（`core/readout`）](../core/readout.md)、[数字化器（`core/digitizer`）](../core/digitizer.md)、[触发环节（`stages/trigger`）](../stages/trigger.md) 和 [事件重建（`core/reconstruction`）](../core/reconstruction.md)。

### `node.json` 与 `points.json` 的格式

节点号是指纹的前 `12` 位十六进制；指纹是输入的规范 JSON 的 SHA-256。规范 JSON 的写法：键按字母序、不带空格；取整数值的浮点数写成整数（`100.0` 与 `100` 是同一个值），其余浮点数原样保留；布尔值不当数；`NaN`、无穷大报错。组件按路径引用的文件（网格、宏、`.cir`、GDML）以文件内容的 SHA-256 进输入，路径本身不进。

`node.json` 的键：

| 键 | 类型 | 进指纹 | 含义 |
| --- | --- | --- | --- |
| `stage` | 字符串 | 否 | 环节名 |
| `node` | 字符串 | 否 | 节点号 |
| `fingerprint` | 字符串 | 否 | 完整指纹，`64` 位十六进制；复用前核对它，同名而指纹不同时报错 |
| `inputs.settings` | 对象 | 是 | `config.json` 本段里这个环节读的键和取值 |
| `inputs.components` | 对象 | 是 | 槽位 → 组件文件里用到的部分 |
| `inputs.upstream` | 对象 | 是 | 直接读的上游环节 → 节点号；场按槽位写；`analysis` 写这个点各作业的节点号列表 |
| `inputs.seed` | 整数 | 是 | 这个环节的种子，只有 `deposit`、`current`、`readout`、`digitizer` 有 |
| `job` | 对象 | 否 | 作业号 `index` 与主种子 `master_seed` |
| `code` | 字符串 | 否 | 代码版本，工作树有未提交改动时带 `+dirty` |
| `environment` | 对象 | 否 | 运行环境 |
| `state` | 字符串 | 否 | `running`（在 `.part` 里写）、`done`、`ended`（这个环节没给下游留下可算的东西，例如 `deposit` 一个事例也没记录；这个作业的下游环节没有节点） |
| `notes` | 对象 | 否 | 环节运行后留下的记录 |

环节自己要记的东西用自己的顶层键，例如 `field` 的 `axes`、`read`、`solved`，写入时与上表的键合并。

`points.json` 是一个对象，键是点名，每个点有三项：`measures` 是各环节“测的是什么”的指纹（见上面“`analysis` 统计哪些作业”），`analysis` 靠它找这个点的作业；`values` 是各扫描轴的“段.键”和取值；`nodes` 是各环节的节点号，`field`、`analysis` 是一个节点号，`deposit` 到 `reconstruction` 是按作业号排列的节点号列表。

```json
{
  "voltage_100": {
    "values": {"field.voltage": 100},
    "nodes": {"field": "c41f0a9d2b7e", "deposit": ["3f9a0c1d22e4", "8b02e6f4a1c9"], "analysis": "e07d5b3a914c"}
  }
}
```

每个节点的锁文件是节点目录旁的 `.<节点号>.lock`。
