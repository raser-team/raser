# 实验、扫描点与种子

`src/raser/lifecycle/workflow.py` 与 `src/raser/core/seeding.py` 承接 [命令行接口（`raser`）](../cli.md) 分发的测试命令、应用命令、`raser new` 命令与 [仿真链与环节入口（`stages`）](../stages/README.md) 的八个环节命令，读取各实验类的定义。该模块负责从 `examples/` 复制建立新 project，定位 project 与实验文件夹，读写按八个环节分段的配置文件 `config.json`，应用 `--set` 与 `--scan` 的“段.键”地址展开参数扫描点，计算各环节节点的输入指纹并维护参数表 `points.json`、节点目录 `nodes/<环节>/<节点号>/`（含 `node.json`）与软链接视图 `points/<点名>/<环节>/<作业号>`，同时为测量环节与作业初始化随机数生成器及命名随机流。规划出的节点与作业交给 [片与重跑](slices.md) 执行指纹复用与代码版本核对，交由 [作业、日志、锁、断点续跑与集群提交](jobs.md) 对节点加锁并启动本地或集群作业；各环节完成后由 [统计分析环节（`stages/analysis`）](../stages/analysis.md) 汇总各扫描点结果并在 `<实验>/analysis/` 下输出跨点趋势图。

## 行为

### 实验类、project 与目录布局

每个测试或应用是一个继承 `raser` 实验基类的 Python 类，在类中写明它由哪些环节组成、有哪些器件、各器件是什么角色（如被测器件、参考器件）；类里不写设置的取值，取值只来自 `config.json`，代码不留默认值，缺了要用的键就报错并指出缺的“段.键”。命令行传入的器件替换被测器件（例如 `telescope` 默认以 `TAICHU3` 为参考层、中间放两块被测器件，命令行传入的器件把这两块都换掉）。官方测试类位于 `raser_bench` 包（`signal`、`timeres`、`tct`、`telescope`），输出放在器件的 project 下，即 `work/<器件>/<测试>/`；官方应用类位于 `raser_app` 包（`bmos`、`cflm`、`hbf`、`pimg`），输出放在 `work/<应用>/` 下，器件本身可以作为扫描轴（支持多个器件轴）以对比不同器件的结果。用户自定义的测试或应用同样写成继承实验基类的 Python 类，放在自有包里、在 `pyproject.toml` 的 `[project.entry-points."raser.experiments"]` 下登记，或放在 project 根下的 `*.py` 里由程序自动发现，按名字注册，写法见[架构总纲](../architecture.md#实验是-python-类)。环节名（`field`、`deposit`、`current`、`readout`、`digitizer`、`trigger`、`reconstruction`、`analysis`）和它们的短命令（`fld`、`dep`、`cur`、`rdo`、`digi`、`trig`、`reco`、`ana`）、`status`、`new`、`model`、`device` 是保留字，实验文件夹不使用这些名字。

`work/` 下的一个器件文件夹或一个应用文件夹构成一个 project；`examples/` 中的每个示例也是一个配好完整 `config.json` 的 project（如 `examples/HPK-Si-PiN/`、`examples/bmos/`）。示例可在 `examples/` 里就地运行，结果存在示例自己的 project 里。实验命令给的是名字时（例如 `raser signal HPK-Si-PiN`、`raser bmos`），先找 `work/<名字>/`，再找 `examples/<名字>/`，最后找当前文件夹下的 `./<名字>/`；三处都没有时报错退出。使用 `raser new --from <示例> <路径>` 可将 `examples/<示例>` 整个复制为新 project，配置完整，之后与示例各自独立：

```bash
raser new --from HPK-Si-PiN work/my-PiN
raser signal my-PiN
```

引用器件时，若 project 文件夹下有自己的器件文件则优先使用该文件；只写器件名字时到 `raser/components/device/` 组件库中查找（组件定义见 [器件定义（`components/device`）](../components/device.md)）。组件库只用来找器件文件；project 本身要在上面三处之一，库里有这个器件也照样报错，新建 project 用 `raser new --from`。

一个实验的结果分两层存放：底下是按输入内容指纹存放的节点，上面是给人按扫描点查看的软链接视图。器件 project 与实验文件夹的目录布局如下：

| 路径 | 内容 |
| --- | --- |
| `<器件 project>/field/<节点号>/` | 该器件的场节点（含电场、权重场、IV/CV、器件参数电路图及 `node.json`），被这块器件的各个实验共用 |
| `<实验>/config.json` | 分段配置文件，写全本次运行用到的设置，按 `field`、`deposit`、`current`、`readout`、`digitizer`、`trigger`、`reconstruction`、`analysis` 八个环节分段 |
| `<实验>/points.json` | 参数表，每次运行时从 `config.json` 算出，一行一个扫描点，记录各扫描轴的取值以及每个环节用的节点号；`raser status` 打印这张表 |
| `<实验>/nodes/<环节>/<节点号>/` | 环节节点文件夹，存放这一环节在该组输入下写出的文件、本环节图像和一份 `node.json`；`deposit` 到 `reconstruction` 每个作业一个节点，`analysis` 每个扫描点一个节点 |
| `<实验>/points/<点名>/<环节>/<作业号>` | 扫描点视图：`deposit` 到 `reconstruction` 每个环节一个文件夹，每个作业一个指向 `../../../nodes/<环节>/<节点号>` 的软链接；`points/<点名>/field` 指向共享场节点、`points/<点名>/analysis` 指向 `../../nodes/analysis/<节点号>`，各是一个软链接 |
| `<实验>/analysis/` | `analysis` 环节生成的跨扫描点统计和趋势图 |

在已含有效 `config.json` 的实验文件夹根目录下直接运行 `raser <选项>` 时，命令行入口会自动从 `config.json` 读出实验命令词和器件名，补在前导全局选项（`-b`、`-t` 等）之后。若未处于含有效 `config.json` 的实验文件夹根目录（例如进入了子文件夹，或当前目录没有 `config.json`）就直接运行 `raser -s 2`，命令行入口按原样解析参数并报错：

```text
raser: error: argument command: invalid choice: '2' (choose from ...)
```

原因是只有当前工作目录存在 `config.json`、其中记录的实验命令已注册，且命令行里没有出现其他命令名、短别名或 `-h`/`--help`/`--version` 时，`raser` 才会自动补全命令词和器件名。`cd` 回到实验文件夹根目录再执行，或写全 `raser <命令> <器件> ...` 即可。

### 分段配置、`--set` 与 `--scan` 参数扫描

每个实验文件夹里的 `config.json` 按链上的八个环节分段（`field`、`deposit`、`current`、`readout`、`digitizer`、`trigger`、`reconstruction`、`analysis` 各一段），写全这次运行用到的全部设置；运行用到的每个设置都来自配置文件。组件文件按读它的环节分文件夹存放在 `raser/components/` 下（`device/` 放器件，`deposit/`、`readout/`、`digitizer/`、`trigger/` 各放对应环节的组件）。

命令行通过 `--set <段.键>=<值>` 修改 `config.json` 中单个设置，通过 `--scan <段.键>=<值1>,<值2>,...` 将逗号分隔的多个取值按笛卡尔积展开成一组扫描点；两者均可重复传入多次：

```bash
raser signal my-PiN --set field.voltage=100
raser signal my-PiN --scan field.voltage=100,200
```

每次运行时，程序从 `config.json` 算出 `points.json`，并在 `points/<点名>/` 下更新软链接视图。点名按扫描轴的取值命名（如 `voltage_100`、`voltage_200`），作为给人查看的入口；修改设置或增加扫描轴后，点名可能不变，但软链接指向的节点会随之更新，使参数与结果始终通过指纹严格对应。

同一条命令里把同一个键同时传给 `--set` 和 `--scan` 时，程序在展开扫描点前报错：

```text
ValueError: field.voltage: given to --set and to --scan at once; give it to one of them
```

原因是本次命令行对同一参数同时请求了固定取值与多值扫描；固定取值用 `--set`，扫描多个值用 `--scan`，只保留其中一个即可。

### 节点指纹、跨点复用、版本提示与节点锁

一个环节在一组输入下算出的一份结果是一个节点。节点的输入由四项组成：

1. 这个环节用到的设置值；
2. 组件文件里它用到的那一部分；
3. 上游各节点的节点号；
4. 测量环节（`deposit`、`current`）的随机种子，以及 `readout`（NGspice 噪声）、`digitizer`（时钟相位、孔径抖动）自己的种子，都由作业的种子派生，规则见下面的“种子”一节。不给 `--seed` 时，主种子取启动时的时间戳，每次运行都是一次新的测量；要复用测量环节的节点，带上同一个 `--seed`。

指纹由这四项输入算出，指纹就是节点号。节点文件夹 `nodes/<环节>/<节点号>/` 里的 `node.json` 把上述输入原样记下来，另外记下代码版本、运行环境和运行状态。

只要指纹相同，节点即直接复用，不论它是在哪个扫描点、哪次运行里算出来的。扫描只影响下游的设置时，上游节点在各扫描点之间自动共用；传入 `--seed <整数>` 可固定随机种子使结果可重复，传入 `--same-seeds` 可让各扫描点的同编号作业共用随机种子，从而复用未受扫描影响的上游结果。例如在 `signal` 上同时扫描 `field.voltage=100,200` 和 `readout` 中某个电阻的两档取值时：`deposit` 与 `current` 产生 `2` 个节点（换偏压属于重新测量，两档偏压各测各的；电阻只被 `readout` 读取，两档电阻共用这两个节点），`readout` 及下游环节产生 `4` 个节点（两档偏压乘两档电阻）。

节点只增不减：若把每个作业的事例数从 `20` 改成 `40`，所有环节的指纹随之改变并写出新节点，旧节点保留在 `nodes/` 下；再把事例数改回 `20` 时，`points/<点名>/<环节>/<作业号>` 视图重新指回原来的旧节点，全部直接复用。当代码版本与节点 `node.json` 记录的代码版本不一致时，程序只打印一条提示，已有结果照常复用。

并发运行时，每个节点单独加锁；写到一半的节点带 `.part` 后缀，写完才改成正式的名字，正式名字的节点都是完整结果。若底层网络文件系统不支持 `flock`，终端打印警告并继续执行：

```text
warning: <锁文件路径> cannot be locked here (Operation not supported): nothing keeps another command off it
```

看到该警告时，需人工避免同时向同一实验发起并发写命令。

### 种子

一次运行有一个主种子：`--seed <整数>` 给出，不给时取启动时的时间戳。每个作业的种子由三样派生：

1. 主种子；
2. 作业号（`0` 至 `-s` 给的作业数减 `1`）；
3. 这个扫描点上测量相关的扫描轴取值：`field`、`deposit`、`current` 三段里的扫描轴。换偏压、换源、换漂移设置都是重新测一遍，所以这些轴的取值进作业种子；`readout` 及下游各段的扫描轴只改测完以后的处理，不进作业种子。

点名不参与派生：改了点名的写法，或加了一条与测量无关的扫描轴，作业种子不变。作业种子由字符串 `"<主种子>/<作业号>/<段.键>=<值>;<段.键>=<值>;…"`（测量相关的扫描轴按“段.键”的字母序排列，值按 JSON 写法）按式 (1) 同样的 SHA-256 映射得到；作业里各环节、各随机流的种子再由作业种子按名字派生（式 (1)），`readout` 的 NGspice 噪声种子也是其中一条。

- **加作业**：同一个 `--seed` 下把 `-s 3` 改成 `-s 5`，作业 `0`、`1`、`2` 的种子不变，节点照常复用，只新算作业 `3`、`4`；每个点的 `analysis` 统计的作业变了，算成新节点，`<实验>/analysis/` 下的跨点统计随之重写。
- **扫偏压**：`--scan field.voltage=100,200` 时两个点的作业种子不同，`deposit`、`current` 各测各的。
- **扫读出电阻**：只扫 `readout` 段的键时，各点的作业种子相同，`deposit`、`current` 的节点在各点之间共用。
- **`--same-seeds`**：作业种子只由主种子和作业号派生，不含扫描轴取值，各扫描点的同号作业共用种子；扫描轴不被某个测量环节读到时，这个环节的节点在各点之间共用。

### 多扫描点调度与集群重提检查

多扫描点实验中，程序先准备各点所需的共享节点（如 `work/<器件>/field/<节点号>/`），再依次调度各扫描点的待跑作业。各扫描点彼此独立，某一点因前置依赖未就绪进入等待，或因作业执行抛出异常而失败时，程序会继续跑完其余扫描点，最后集中列出失败点退出：

```text
1 of 2 points failed:
  ...
```

在登录节点带 `-b` 重跑命令时，程序向集群调度器（`hep_q` 或 `condor_q`，超时 `120` $\text{s}$）查询已提交作业的存活状态：若作业仍在集群中，打印 `are submitted already` 并跳过；若作业在集群中已消失且未完成，打印 `is no more on the cluster: it failed and is submitted again` 并自动重新提交；若调度器报错或超时无法查询，打印 `the scheduler cannot be asked; left as it is` 并保持原状。

## 规则

### 内置常数

下表列出 `src/raser/cli/raser.py`、`src/raser/lifecycle/workflow.py` 与 `src/raser/core/seeding.py` 中的内置常数与固定运行参数。它们是模块级常量，写死在代码里：

| 常数名 | 值 | 单位 | 定义位置与含义 |
| --- | --- | --- | --- |
| `GLOBAL_OPTIONS` | `{"-t", "--test", "--batch"}`（另匹配正则 `r"-b+"`） | 无 | `cli/raser.py` 中 `_experiment_arguments` 在实验文件夹内自动补全命令词与器件名时保留在最前面的前导全局选项 |
| `SHORT` | `{"fld": "field", "dep": "deposit", "cur": "current", "rdo": "readout", "digi": "digitizer", "trig": "trigger", "reco": "reconstruction", "ana": "analysis"}` | 无 | `cli/raser.py` 中八个环节子命令的命令行短别名映射（写文件与文件夹时始终用全称） |
| `_STARTS` | `4` | 次 | `workflow.py` 中 `_run_again` 在集群作业结束时尝试重新拉起等待命令或本实验命令的最大次数 |
| `_PAUSE` | `30` | $\text{s}$ | `workflow.py` 中 `_run_again` 相邻两次重启尝试之间的休眠等待时间 |
| `_WAITING_DEPTH` | `8` | 层 | `workflow.py` 中 `_start_again` 在集群上自动拉起外部等待命令的最大递归深度上限 |
| 派生种子模数 | $2^{31}-1$（`2147483647`） | 无 | `seeding.py` 中将 SHA-256 前 `8` $\text{B}$ 大端无符号整数映射为正整数种子的取模基数（加 `1` 后范围 $[1, 2^{31}-1]$） |

### 命令行补全与入口分发

`src/raser/cli/raser.py` 中的 `main(argv)` 按以下顺序解析并分发命令：

1. **实验文件夹内自动补全（`_experiment_arguments(argv)`）**：检查当前工作目录文件 `config = Path.cwd() / "config.json"`。若满足以下任一条件，原样返回 `argv`：
   - `not config.is_file()`；
   - `{"-h", "--help", "--version"}.intersection(argv)` 非空；
   - `argv` 中存在任一参数属于已注册命令表 `APPLICATIONS` 或短别名表 `SHORT`。
   否则读取 `config.json` 提取实验命令词 `words` 与器件名 `device`（无器件应用为空列表 `[]`）；若 `words` 为空或首词未注册，原样返回 `argv`。否则从下标 `lead = 0` 起向右跳过满足 `argv[lead] in GLOBAL_OPTIONS` 或 `re.fullmatch(r"-b+", argv[lead])` 的全部前导全局选项，返回 `[*argv[:lead], *words, *device, *argv[lead:]]`。
2. **顶层全局选项归并**：调用 `build_parser().parse_args(argv)` 得字典 `kwargs`，将子命令名还原为 `command = SHORT.get(kwargs["_command"], kwargs["_command"])`（为 `None` 时打印帮助并返回退出码 `1`）。若顶层 `-b`/`--batch` 累计计数 `kwargs["global_batch"] != 0`，执行：
   - `kwargs["dry_run"] = kwargs["dry_run"] or kwargs["test"]`；
   - `kwargs["batch"] = True`；
   - `kwargs["mem"] = max(kwargs["mem"], kwargs["global_batch"])`；
   - `kwargs["global_batch"] = 0`。
3. **设置 project 根目录上下文并执行命令**：写入 `kwargs["_argv"] = argv` 与 `kwargs["_entry_command_prefix"] = (command,)`。project 按“实验类、project 与目录布局”一节的查找顺序定：测试命令按器件名、应用命令按应用名，依次找 `work/<名字>/`、`examples/<名字>/`、`./<名字>/`；环节命令和 `raser status` 取给定路径（不给为当前文件夹）所在的 project（路径解析见 [公共基础设施（`supports`）](../supports/README.md)）。进入 `project_root_context(project, kwargs.get("_components", ()))` 上下文并调用 `kwargs["_run"](kwargs)`；若捕获 `MissingDependency` 或属于 `ROOT_MODULES` 的 `ModuleNotFoundError`，向标准错误打印提示并返回退出码 `1`；退出前在 `finally` 中调用 `process.close()`。

### 配置解析、节点规划与加锁调度

实验命令与环节命令启动后按以下步骤展开扫描点、计算节点指纹并调度作业：

1. **定位 project 与读写分段 `config.json`**：测试类实验的文件夹是 `<器件 project>/<测试>/`，应用类实验的文件夹就是 `<应用 project>/`，project 按上一节的查找顺序定（如 `work/HPK-Si-PiN/signal/`、`examples/HPK-Si-PiN/signal/`、`work/bmos/`）。读取实验根目录下的 `config.json`（含 `field`、`deposit`、`current`、`readout`、`digitizer`、`trigger`、`reconstruction`、`analysis` 八段）。对命令行传入的 `--set` 与 `--scan` 条目，按首个 `"="` 切分出“段.键”地址与取值字符串（`--scan` 的取值按 `","` 切分），每个值调用 `_parse`（`json.loads` 成功取解析值，抛出 `JSONDecodeError` 保留原字符串）；若同一地址同时出现在 `--set` 与 `--scan` 中，抛出 `ValueError`。非 `--dry-run` 模式下将更新后的设置写回 `config.json`。
2. **展开扫描点并计算各环节节点号**：对扫描轴取值的笛卡尔积逐组合生成扫描点，按本环节用到的设置值、组件文件（project 自有器件文件或 `raser/components/` 下对应环节组件）中用到的部分、上游各节点号及种子（测量环节 `deposit`、`current` 的种子，`readout`、`digitizer` 自己的种子，都由作业种子派生）计算各环节节点号，写出 `points.json` 并更新 `points/<点名>/<环节>/<作业号>` 软链接。
3. **比对节点指纹与代码版本 `_commit()`**：获取当前代码版本标识 `_commit()`（当 `REPO_ROOT is None` 时取 `f"raser {raser.__version__}"`；否则在 `REPO_ROOT` 下执行 `git rev-parse HEAD` 与 `git status --short`，工作树干净时取提交哈希，有未提交改动时附加 `"+dirty"`；源码树不是 git 仓库（例如从压缩包解出来的）时拿不到提交号，同样取 `f"raser {raser.__version__}"`）。若目标节点 `nodes/<环节>/<节点号>/`（或 `<器件 project>/field/<节点号>/`）已存在，直接复用该节点；若其 `node.json` 记录的代码版本与当前 `_commit()` 不一致，打印提示后照常复用。若 `--dry-run` 为真，打印各扫描点、环节和作业规划后直接返回。
4. **节点加锁、`.part` 写入与启动本地或集群作业**：对待计算的每个节点调用 `_lock` 以追加模式打开锁文件并执行 `fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)`（捕获 `BlockingIOError` 时关闭句柄并抛出 `Running`；捕获 `errno` 属于 `(errno.ENOLCK, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EINVAL)` 的 `OSError` 时打印警告并返回 `None`）。计算期间节点带 `.part` 后缀，写出数据文件与 `node.json` 后原子改名为正式节点目录。本地与集群作业按以下规则启动（详见 [作业、日志、锁、断点续跑与集群提交](jobs.md)）：
   - 单扫描点且省略 `-s`、不加 `-b`：在当前进程经 `_logged` 将 Python 标准输出与标准错误同步写入日志并直接执行 `_run_job`；
   - 多扫描点且省略 `-s`、不加 `-b`：调用 `_own_process` 为每个扫描点启动独立子进程 `jobs._run_local_job`；
   - 传入 `-s` 或 `-b`：调用 `jobs.run_indexed_jobs` 使用本地进程池并行运行或打包提交到集群调度器（启用 `RASER_SUBMIT_QUEUE` 时打印 `the jobs go to the queue the host submits: a job that waits for others is not started again by itself; run the command again when those are done`）。

### 随机种子播种、命名随机流与集群自动续跑

测量环节与作业的随机数生成器在 `src/raser/core/seeding.py` 中统一播种，集群作业结束后的自动续跑由 `src/raser/lifecycle/workflow.py` 中的 `_start_again` 与 `_run_again` 执行：

1. **重置全局随机数生成器（`seeding.seed_generators(seed)`）**：将模块变量 `_job_seed` 设为 `int(seed)`，同步执行 `random.seed(_job_seed)` 与 `ROOT.gRandom.SetSeed(_job_seed)`，并调用 `_streams.clear()` 清空已缓存的命名随机流。
2. **按名派生独立随机流（`seeding.stream(name)`）**：物理模块调用 `seeding.stream(name)` 获取名为 `name`（如 `"drift"`、`"diffusion"`、`"source"`、`"ionization/<event>"`）的 `ROOT.TRandom3` 实例时，若 `name in _streams` 则直接返回缓存实例；若 `name not in _streams`：
   - 当 `_job_seed is None`（调用 `seed_generators` 之前）时，取流种子 $\text{seed}_{\text{stream}} = 0$（由 ROOT 随机初始化）；
   - 当 `_job_seed is not None` 时（`_job_seed` 是上面“种子”一节派生出的作业种子），对拼接字符串 `f"{_job_seed}/{name}"` 计算 UTF-8 字节串的 SHA-256 摘要，取前 `8` $\text{B}$ 按大端无符号整数映射到 $[1, 2^{31}-1]$：

     $$\text{seed}_{\text{stream}}(name) = 1 + \left(\operatorname{int\_from\_bytes}\!\left(\operatorname{SHA256}\!\left(\text{"\{\_job\_seed\}/\{name\}"}\right)[0:8],\, \text{"big"}\right) \bmod (2^{31} - 1)\right) \tag{1}$$

     其中 $\text{seed}_{\text{stream}}(name)$ 为传入 `ROOT.TRandom3` 的正整数种子（无量纲，取值范围 $[1, 2^{31}-1]$），`_job_seed` 为当前整数种子（无量纲），`name` 为随机流名称字符串。构造 `_streams[name] = ROOT.TRandom3(seed)` 存入缓存并返回。
3. **集群作业完成后自动重新拉起命令（`_start_again`、`_run_again`）**：当环境变量 `RASER_CLUSTER_JOB` 非空且本次作业完成了新的计算进展时，读取当前递归深度 `depth = int(os.environ.get("RASER_RESUBMIT_DEPTH", "0"))`：
   - 先遍历等待当前共享结果的外部命令列表：若 `depth >= _WAITING_DEPTH`（`8` 层），打印 `not starting raser <命令>: <深度> starts deep`；否则调用 `_run_again` 拉起该外部命令，成功后将其从等待列表移除；
   - 再检查本实验待续跑命令（未启用 `RASER_SUBMIT_QUEUE` 时记录）：若 `depth` 已达到链的片数，打印 `not starting the command again: <深度> starts deep, ...` 并返回；否则调用 `_run_again` 重新拉起本实验命令以提交等待上游完成的下游作业；
   - `_run_again(words, cwd, depth)` 打印 `starting the command again: raser <命令>`，将子进程环境变量 `RASER_RESUBMIT_DEPTH` 设为 `str(depth + 1)`，在 `cwd` 下最多尝试 `_STARTS = 4` 次（相邻两次间隔 `time.sleep(_PAUSE)` 即 `30` $\text{s}$）；任一次返回码为 `0` 即返回 `True`，`4` 次均失败则打印 `the command did not start again in 4 tries: give it again when the jobs it waits for are done` 并返回 `False`。

## 软件实现

### 源文件分工

- `src/raser/lifecycle/experiment.py`：实验基类 `Experiment` 与器件槽位 `Slot`。
- `src/raser/lifecycle/workflow.py`：提供并发占用退出异常 `Running`；实现 `raser new --from` 示例 project 复制、公共运行选项注册 `run_arguments`、分段 `config.json` 读写与 `--set`/`--scan` “段.键”地址合并、节点指纹计算、`points.json` 参数表与 `points/<点名>/<环节>/<作业号>` 软链接视图维护、共享场节点准备、多扫描点本地与集群作业调度，以及集群自动续跑 `_start_again`/`_run_again`。
- `src/raser/core/seeding.py`：维护模块级当前种子 `_job_seed` 与命名随机流字典 `_streams`；提供 `seed_generators(seed)` 统一播种 Python `random`、`ROOT.gRandom` 并清空流缓存，提供 `stream(name)` 按流名经 SHA-256 派生并缓存独立的 `ROOT.TRandom3` 实例。
- `src/raser/cli/raser.py`：定义 `raser` 命令行入口 `main` 与参数解析器 `build_parser`，维护子命令映射表 `APPLICATIONS` 与八个环节短别名表 `SHORT`；提供 `_experiment_arguments` 在含 `config.json` 的实验文件夹根目录下自动补全命令词与器件名，并将顶层 `-b`/`-t` 全局选项归并至子命令参数。

### 核心数据结构

| 数据结构与字段 | 类型与默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| 实验基类与实验子类 | Python 类 | 无 | `raser_bench`、`raser_app` 及用户自定义实验继承的基类，声明实验包含的环节、器件清单、各器件角色（如被测器件、参考器件），通过包入口点 `raser.experiments` 或 project 文件夹自动发现并按名字注册（见[架构总纲](../architecture.md#实验是-python-类)） |
| `Experiment` 的类属性 | `name`（命令词）、`stages`（环节）、`devices`（槽位名 → `Slot`，按实验里的顺序）、`components`、`application`（默认 `False`） | 无 | 一个器件的实验只有槽位 `Device`；槽位名只用字母、数字、`_`、`-`；`application` 为 `True` 时输出放在 `work/<名字>/`，否则放在 `work/<器件>/<名字>/` |
| `Slot(role, device, positions)` | `role` 为 `"tested"`（默认）或 `"reference"`；`device` 默认 `None`；`positions` 默认 `()` | 无 | 被测槽位由命令行给的器件占用，不写 `device`；参考槽位必须写 `device`；至少有一个被测槽位；`positions` 是这块器件占的各个位置，不写时只有一个位置、名字同槽位 |
| `Running` | `SystemExit` 子类 | 无 | 目标锁文件已被另一进程持有时抛出的并发占用退出异常 |
| `seeding._job_seed` | `int \| None`，默认 `None` | 无 | 当前由 `seed_generators` 写入的整数随机种子（范围 $[1, 2^{31}-1]$） |
| `seeding._streams` | `dict[str, ROOT.TRandom3]`，默认 `{}` | 无 | 当前作业或环节内按流名 `name` 缓存的独立 `ROOT.TRandom3` 实例字典 |

## 接口

### 命令行选项与配置分段

使用者在命令行与 `config.json` 中能设的公共运行选项和配置分段如下表所示；表外的运行控制参数（如派生种子模数、集群自动续跑重试次数 `_STARTS`、重试间隔 `_PAUSE`、外部等待递归深度上限 `_WAITING_DEPTH`）都写死在代码里。

| 选项或配置段 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `--version`（顶层位置） | 无 | 无 | 打印当前 `raser` 版本号并退出 |
| `-h`, `--help` | 无 | 无 | 打印顶层或子命令的帮助信息并退出 |
| `-b`, `--batch`（顶层位置） | `0` | 档（`8000 MB`/档） | 可连写累计计数（如 `-b`、`-bb`、`-bbb`）；计数非 `0` 时开启集群提交，并将内存档位更新为 `max(-mem, b 的个数)` |
| `-t`, `--test`（顶层位置） | `False` | 无 | 只在与顶层 `-b` 联用时生效：将 `dry_run` 设为 `True`，只检查并预览提交信息 |
| `raser new --from <示例> <路径>` | 无（必选参数） | 无 | 将 `examples/<示例>` 整个复制为 `<路径>` 下的新 project，带完整 `config.json`，之后与示例各自独立 |
| `-s`, `--jobs <整数>` | `None`（按 `1` 处理） | 个 | 指定每个扫描点并行运行的作业数，作业号为 `0` 至 `<整数>-1` |
| `--seed <整数>` | `None`（取启动时的时间戳） | 无 | 指定整数随机种子，让测量环节（`deposit`、`current`）和 `readout` 的噪声可重复 |
| `--same-seeds` | `False` | 无 | 让各扫描点的同编号作业共用随机种子，从而复用未受扫描影响的上游结果 |
| `--set <段.键>=<值>` | `[]` | 依目标参数而定 | 用“段.键”作地址修改 `config.json` 中的设置（如 `--set field.voltage=100`），可重复给出；值按 `json.loads` 解析（失败保留原字符串） |
| `--scan <段.键>=<值1>,<值2>,...` | `[]` | 依目标参数而定 | 用“段.键”作地址扫描一个或多个设置（如 `--scan field.voltage=100,200`），逗号分隔各值并按 `json.loads` 解析，可重复给出并按笛卡尔积展开 |
| `--dry-run` | `False` | 无 | 只打印将要运行的扫描点、环节和作业状态，打印完即返回 |
| `-b`, `--batch`（子命令位置） | `False` | 无 | 将待运行作业提交到集群队列运行 |
| `-mem <档位>` | `1` | `8000 MB` | 集群模式下每个作业申请的内存档位（实际申请 `8000 * <档位>` $\text{MB}$），须为正整数；传入非正整数提交作业时报错 `ValueError: Indexed job memory level must be positive` |
| `config.json`: `field`、`deposit`、`current`、`readout`、`digitizer`、`trigger`、`reconstruction`、`analysis` 八个环节段 | 依实验类与示例 project 而定 | 依各段键而定 | 按八个环节分段写出本次运行用到的全部设置；运行用到的每个设置均来自对应环节段（各环节段的键定义见 [仿真链与环节入口（`stages`）](../stages/README.md) 各页） |

### 读写的文件与目录

- **`<实验文件夹>/config.json`**：实验分段配置文件，按 `field`、`deposit`、`current`、`readout`、`digitizer`、`trigger`、`reconstruction`、`analysis` 八个环节分段记录完整设置；`--set` 与 `--scan` 通过“段.键”地址读写对应环节段中的键。
- **`<实验文件夹>/points.json`**：参数表 JSON 文件，每次运行时由程序从 `config.json` 算出，一行一个扫描点，记录各扫描轴的取值以及每个环节所用的节点号；`raser status` 读取并打印该表。
- **`<实验文件夹>/nodes/<环节>/<节点号>/` 与 `<器件 project>/field/<节点号>/`**：按输入指纹命名的节点目录（写到一半时带 `.part` 后缀，写完后改为正式名字，每个节点单独加锁），存放该环节写出的数据文件（如 HDF5 文件与本环节图像，具体格式见 [仿真链与环节入口（`stages`）](../stages/README.md) 与 `docs/cn/core/` 各页）以及一份 `node.json`。`node.json` 原样记录决定节点指纹的四项输入（本环节用到的设置值、组件文件中用到的部分、上游各节点号、测量环节 `deposit` 与 `current` 的种子，以及 `readout`、`digitizer` 自己的种子），并另记代码版本、运行环境和运行状态。
- **`<实验文件夹>/points/<点名>/<环节>/<作业号>`**：扫描点视图软链接，`<点名>` 按扫描轴取值命名（如 `voltage_100`）；`deposit` 到 `reconstruction` 每个作业一个，指向 `../../../nodes/<环节>/<节点号>`；`points/<点名>/field` 指向 `<器件 project>/field/<节点号>`，`points/<点名>/analysis` 指向 `../../nodes/analysis/<节点号>`。
- **`<实验文件夹>/analysis/`**：`analysis` 环节输出的跨扫描点统计与趋势图目录。

### `config.json` 的格式

`config.json` 随 project 而来：`raser new --from <示例> <路径>` 把示例里每个实验的 `config.json` 一起复制过来，在示例上就地运行时用的就是示例自带的那一份。每一段有哪些键、各是什么意思，见[仿真链与环节入口（`stages`）](../stages/README.md#设置)的设置表和各环节的页面。

`config.json` 是一个 JSON 对象。顶层的键分三组：

| 键 | 类型 | 含义 |
| --- | --- | --- |
| `workflow` | 字符串 | 实验的命令词，例如 `"signal"` |
| `device` | 字符串 | 器件名；不带器件的应用没有这一项 |
| `field`、`deposit`、`current`、`readout`、`digitizer`、`trigger`、`reconstruction`、`analysis` | 对象 | 八个环节各一段，写这个环节的全部设置；实验里没有的环节写空对象 |
| `names` | 对象 | 给长地址起的短名：“段.键”或“段.槽位.键” → 短名，例如 `{"readout.amplifier": "amp"}`；点名里用短名（`amp_SantaCruz`），`--set`、`--scan` 里两种写法都认 |
| `same_seeds` | 布尔 | 各扫描点的同号作业是否共用种子 |

`HPK-Si-PiN` 的 `signal` 示例：

```json
{
  "workflow": "signal",
  "device": "HPK-Si-PiN",
  "field": {"voltage": 200.0, "irradiation_flux": null},
  "deposit": {
    "source": "decay/Sr90", "g4setup": "device_alone",
    "events_per_job": 200, "generated_per_job": null, "generated_limit": 10000000,
    "edep_min": null, "edep_max": null, "fano": true, "plots": 100
  },
  "current": {"plots": 100},
  "readout": {"amplifier": "SantaCruz+Gali52+Termination50", "sheet_resistance": null},
  "digitizer": {},
  "trigger": {},
  "reconstruction": {
    "threshold": 10.0, "amplitude_threshold": 10.0,
    "fractions": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9], "edge": null
  },
  "analysis": {},
  "names": {},
  "same_seeds": false
}
```

读写规则：

1. **一个设置只有一种给法**：`--set <段.键>=<值>` 把值写进对应的段，`--scan <段.键>=<值1>,<值2>` 把取值列表写进同一个位置。两者都留在 `config.json` 里，之后不带选项的命令照样用它们。链上的设置没有各自单独的命令行选项；只管当次运行的开关（`-g4_vis`、`--g4-vis-driver`）不进 `config.json`。
2. **两类设置**：`field`、`deposit`、`current`、`readout` 四段的设置定的是测什么，叫物理参数；`digitizer`、`trigger`、`reconstruction`、`analysis` 四段的设置定的是测到的事例怎么分析，叫分析参数。物理参数多给一个值就是多一组实验：它在段里写成列表就是扫描，每个取值一个点，例如 `"field": {"voltage": [100, 200]}`，点名按取值起（`voltage_100`、`voltage_200`）。分析参数不扫描：它的列表就是这个参数自己的值，例如 `reconstruction.fractions`；对它给 `--scan` 会报错。想换一个分析参数，用 `--set` 改掉、带上同一个 `--seed` 再跑一次，已经测到的事例照常复用，只重做分析这几环；不给 `--seed` 时每次运行都是一次新的测量。物理参数用 `--set` 给一个列表同样报错，并提示改用 `--scan`。
3. **取消扫描与改回设置**：对扫描着的地址给 `--set`，段里的列表换成这一个值，扫描结束。不做扫描的实验只有一个点，叫 `default`；有扫描时没有 `default` 这个点。扫描结束或换了扫描的取值后，`points/` 下不再属于这次实验的点的视图会去掉，节点留着。`--set` 给的值一直留在段里，没有“撤销”这个操作；要改回去，再给一次 `--set` 写上原来的值，或直接编辑 `config.json`。
4. **组件里的键**：段里选组件的键叫槽位，例如 `deposit.source`、`deposit.g4setup`；器件是 `field.device`。槽位缺了或为 `null` 时命令在作业开始前报错，例如 `ValueError: config.json has no deposit.source: it names the source of the experiment`；只有环节页写明可以为 `null` 的槽位例外，它为 `null` 时不读组件文件，例如 `trigger.device` 为 `null` 表示用 `digitizer.device` 里示波器自己的触发（见[触发环节（`stages/trigger`）](../stages/trigger.md)）。组件文件内部的一个键写成“段.槽位.键”，例如 `--set deposit.source.par_radius=1000` 改的是放射源文件里的 `par_radius`（源圆盘半径，$\mu\text{m}$）。它在 `config.json` 里写进槽位的对象，和组件名并列：`"source": {"name": "decay/Sr90", "par_radius": 1000}`；扫描它时写成列表，点名取地址的末两段（`source.par_radius_1000`）。给槽位换一个组件（`--set deposit.source=decay/Am241`）时，原来写在对象里的键一并去掉。地址既不是设置、也不在某个槽位下面时，命令报错并列出全部设置和槽位。组件里本身是列表的键不能这样覆盖：要改它，把组件文件复制到 project 里改。
5. **每个环节读自己的段**：环节运行时拿到的是自己那一段的设置，所以 `deposit.plots` 和 `current.plots` 是两个设置。
6. **缺键与多余的键**：段里没写的键等于 `null`；环节要用它的值而它是 `null` 时报错，指出缺的“段.键”，例如 `ValueError: examples/HPK-Si-PiN/signal/config.json has no deposit.generated_limit`；用不到的键缺了不报错。段里有环节不认识的键会报错，例如 `config.json: no current.plot; the settings of current are plots`；顶层出现上表以外的键也报错。程序写 `config.json` 时把每个键都写出来。
7. **`null` 是一个取值**：表里写明“`null` 时取……”的键（如 `field.voltage` 取器件文件里的偏压）写 `null` 就按表里说的取值。
