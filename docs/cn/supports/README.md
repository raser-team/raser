# 公共基础设施（`supports`）

`src/raser/supports/` 处于 RASER 软件分层的最底层（分层边界见[架构总纲](../architecture.md)），只导入 Python 标准库和 `psutil`；出图（`figures`）另外导入 matplotlib 和 ROOT。它承接[命令行接口（`raser`）](../cli.md)传入的命令目标参数、运行环境变量、退出清理请求与异常拦截，执行工作区与项目路径解析（`paths`）、项目内输出边界检查与文件删除（`output`）、缺失依赖报告（`dependency`）、进程退出清理回调（`process`）、函数内存占用采样（`memory_decorator`）及各环节共用的出图样式与存图（[`figures`](figures.md)），把解析好的 `Path` 对象、目录与文件操作、依赖异常及内存诊断交给[实验、扫描点与种子](../lifecycle/experiments.md)、[仿真链与环节入口（`stages`）](../stages/README.md)、[器件模型（`core/device`）](../core/device.md)等上层模块，以及 `components` 和测试包 `raser_bench`、应用包 `raser_app`。

## 行为

### 工作区、项目与组件路径解析（`paths`）

无论 RASER 从源码树运行还是作为已安装包运行，命令行启动、实验初始化与各环节读取组件时，都通过 `raser.supports.paths` 解析工作区根目录、当前项目根目录、测试类与应用类的包内文件，并按四级优先级查找组件文件。运行下面这条扫描命令时：

```bash
raser signal HPK-Si-PiN --scan field.voltage=100,200 -s 2 --seed 1
```

命令行入口在进入子命令前调用 `infer_project_root("HPK-Si-PiN")`（`work/` 下没有 `HPK-Si-PiN` 时解析到 `examples/HPK-Si-PiN/`）并通过 `project_root_context()` 设定路径上下文，使各层解析到如下路径：

```text
work_root()           -> work/
project_root()        -> examples/HPK-Si-PiN/
component_file_path() -> src/raser/components/device/HPK-Si-PiN.json
                         src/raser/components/deposit/   放射源 decay/Sr90、Geant4 装置 device_alone
                         src/raser/components/readout/   SantaCruz、Gali52、Termination50
```

组件按读它的环节分文件夹：`device/` 放器件，`deposit/` 放 Geant4 装置、放射源和束流、激光，`readout/` 放前端放大器和端接电路，`digitizer/` 放采样和量化设置，`trigger/` 放触发条件（见[架构总纲](../architecture.md#组件)）。

### 项目内输出路径与文件删除保护（`output`）

各环节与核心模块在当前项目下构造输出目录或清理旧文件时，通过 `raser.supports.output` 校验相对路径片段与删除目标。路径片段含绝对路径或 `".."`、归属者名称为空，或删除目标解析后落在 `project_root()` 之外时，操作在访问磁盘前即抛出 `ValueError` 中止：

```text
owned_path("field", "nodes", "<节点号>") -> <器件 project>/field/nodes/<节点号>/
owned_path("field", "../out")   -> ValueError: Output label must remain inside the project: ../out
delete_file("/tmp/test.h5")     -> ValueError: File removal must remain inside the project: /tmp/test.h5
```

### 缺失依赖捕获与提示（`dependency`）

当子命令运行所需的外部程序或 Python 包在当前环境中未安装时，模块构造并抛出 `raser.supports.dependency.MissingDependency`（或由命令行入口拦截 `ROOT_MODULES` 中的 `ModuleNotFoundError` 并替换为 `ROOT_MISSING`）。命令行入口捕获该异常后，向标准错误输出单行原因与安装命令，并以退出码 `1` 结束进程：

```text
raser: ROOT's Python bindings are not available in this Python. Install them with conda install -c conda-forge root_base
```

### 进程退出清理回调（`process`）

需要在进程结束前释放外部资源或收尾运行状态的模块，在运行期间调用 `raser.supports.process.at_process_end()` 注册无参清理函数。命令在 `main()` 的 `finally` 块中调用 `process.close()`，按后进先出（LIFO）顺序逐个弹出并执行已注册的回调，每个回调只运行一次：

```python
from raser.supports import process

process.at_process_end(cleanup_first)
process.at_process_end(cleanup_second)
process.close()  # 先执行 cleanup_second()，再执行 cleanup_first()
```

### 函数内存占用诊断（`memory_decorator`）

被 `@memory_decorator` 装饰的函数在每次调用前后，通过 `psutil` 读取当前进程的常驻集大小（`rss`）和虚拟内存大小（`vms`），换算为 $\text{MB}$ 后向标准输出打印调用前、调用后及增量的内存记录。[场求解与加载（`core/field`）](../core/field.md)中 `loop_section.py` 的 `loop_solver` 使用了该装饰器（环节调度见[场求解环节（`stages/field`）](../stages/field.md)），调用时终端输出如下：

```text
Memory usage before calling loop_solver: RSS = 357.12 MB, VMS = 402563.59 MB
...
Memory usage after calling loop_solver: RSS = 358.62 MB, VMS = 402563.59 MB
Memory increase: RSS = 1.50 MB, VMS = 0.00 MB
```

## 规则

### 内置常数

下表列出 `paths.py`、`dependency.py` 与 `memory_decorator.py` 中的全部模块级常数与固定换算因子：

| 常数名 | 值 | 单位 | 定义位置与含义 |
| --- | --- | --- | --- |
| `PACKAGE_ROOT` | `Path(__file__).resolve().parents[1]` | 无 | `paths.py`：`raser` 包所在的根目录；源码树下为 `<REPO_ROOT>/src/raser`，包安装模式下为安装目录中的 `raser` |
| `REPO_ROOT` | `source_tree()` 返回值（`Path` 或 `None`） | 无 | `paths.py`：源码检出或 `pip install -e` 运行时的仓库根目录；作为普通包安装时为 `None` |
| `DEFAULT_COMPONENT_ROOT` | `PACKAGE_ROOT / "components"` | 无 | `paths.py`：内置组件库根目录；源码树下为 `src/raser/components` |
| `ROOT_MODULES` | `{"ROOT", "cppyy"}` | 无 | `dependency.py`：ROOT 的 Python 绑定对应的顶层模块名集合 |
| `ROOT_MISSING` | `MissingDependency("ROOT's Python bindings are not available in this Python", "Install them with conda install -c conda-forge root_base")` | 无 | `dependency.py`：缺少 PyROOT 时由命令行入口统一打印的预构造异常实例 |
| `1024**2` | `1048576` | $\text{B/MB}$ | `memory_decorator.py`：将 `psutil` 内存字节数（$\text{B}$）换算为兆字节（$\text{MB}$）的除数 |

### 源码树检测、工作区与项目根目录解析

`paths.py` 按以下顺序确定源码树、工作区根目录与项目根目录：

1. **源码树判定（`source_tree(package_root=PACKAGE_ROOT)`）**：取上两级目录 `tree = package_root.parents[1]`。若同时满足 `package_root.parent.name == "src"` 且 `(tree / "pyproject.toml").is_file()` 为真，返回该仓库根目录 `tree`（`Path`）；否则返回 `None`。模块导入时调用 `source_tree()` 初始化 `REPO_ROOT`。
2. **计算默认工作区根目录（`default_work_root(tree=REPO_ROOT, cwd=None)`）**：若 `tree is not None`，返回 `tree / "work"`；若 `tree is None`（普通包安装模式），返回 `Path(cwd or Path.cwd()) / "work"`，使输出落在当前工作目录下。
3. **读取生效工作区根目录（`work_root()`）**：读取环境变量 `given = os.environ.get("RASER_WORK_PATH")`。若 `given is not None`，返回 `Path(given)`；否则返回 `default_work_root()`。
4. **读取生效项目根目录与拼接路径（`project_root()`、`project_path(*parts)`）**：`project_root()` 读取 `os.environ.get("RASER_PROJECT_PATH", Path.cwd())` 并转为 `Path` 返回（未设置 `RASER_PROJECT_PATH` 时返回当前工作目录 `Path.cwd()`）。`project_path(*parts)` 将相对路径片段 `*parts` 传给 `project_root().joinpath(*parts)` 并返回对应的 `Path`。

### 项目根目录推断与环境变量上下文切换

命令行入口根据输入参数推断项目根目录并临时切换环境变量时，按以下步骤执行：

1. **检查环境变量与空输入（`infer_project_root(input_value)`）**：
   - 若 `os.environ.get("RASER_PROJECT_PATH")` 已设置且非空，直接返回 `project_root()`；
   - 若 `input_value is None`，直接返回 `project_root()`。
2. **区分路径输入与非路径输入（`_is_path_input(input_value)`）**：令 `path = Path(input_value)`。判断是否满足以下三个条件之一：
   - `path.is_absolute()` 为真（绝对路径）；
   - `len(path.parts) > 1`（包含多级路径）；
   - `bool(path.suffix)` 为真（带文件后缀）。

   若三者均不满足（纯名字，例如 `"HPK-Si-PiN"`、`"bmos"`），按 `work/<名字>/`（`work_root() / str(input_value)`）、`examples/<名字>/`（源码树下 `REPO_ROOT / "examples" / str(input_value)`）、`./<名字>/`（`Path.cwd() / str(input_value)`）的顺序查找 project，返回第一个存在的目录；三处都没有时报错退出（新建 project 用 `raser new --from`，见[实验、扫描点与种子](../lifecycle/experiments.md)）。例如 `raser signal HPK-Si-PiN` 在 `work/` 下没有它时解析到 `examples/HPK-Si-PiN/`。若满足任一条件，判定为路径输入，先对 `Path(input_value)` 调用 `.expanduser()` 展开 `~`，再进入第 3 步。
3. **从路径输入提取项目根目录（`_project_root_from_path(path)`）**：取路径分段元组 `parts = path.parts`：
   - 若 `"components" in parts`，取首次出现的位置 `index = parts.index("components")`；当 `index > 0`（即 `"components"` 位于首段之后）时，返回第一个 `"components"` 之前的父路径 `Path(*parts[:index])`；
   - 否则检查 `path.is_dir()`：若路径本身是已存在的目录，返回 `path`；其余情况返回其父目录 `path.parent`。
4. **临时切换环境变量上下文（`project_root_context(project_path_value, component_apps=())`）**：
   - 计算目标项目路径字符串：`project_path_value is None` 时取 `project = None`，否则取 `project = str(project_path_value)`；
   - 计算附加组件路径字符串：若 `component_apps` 为空，取 `components = None`；若 `component_apps` 非空，按顺序生成 `roots = [str(app_component_root(app)) for app in component_apps]`，读取原环境变量 `previous = os.environ.get("RASER_COMPONENT_PATH")`，当 `previous` 非空时将其追加到 `roots` 末尾，再令 `components = os.pathsep.join(roots)`；
   - 嵌套进入 `_environment("RASER_PROJECT_PATH", project)` 与 `_environment("RASER_COMPONENT_PATH", components)`：当传入值 `value is None` 时保持 `os.environ` 原样，直接 `yield`；当 `value is not None` 时保存进入前的 `previous = os.environ.get(name)` 并设 `os.environ[name] = value`，在 `finally` 块中，若 `previous is None` 则调用 `os.environ.pop(name, None)` 移除该变量，否则恢复 `os.environ[name] = previous`。

### 组件搜索优先级与文件定位

定位组件文件与测试类、应用类的包内文件时，按以下步骤执行：

1. **组装并去重搜索根目录（`component_roots(extra_roots=None)`）**：
   - 按从高到低的固定顺序收集四层目录到列表 `roots`：
     1. `project_path("components")`：当前项目的 `components/` 目录；
     2. `_as_path_list(extra_roots)`：`extra_roots` 为 `None` 时取 `[]`，为单个 `str | os.PathLike` 时取 `[Path(extra_roots)]`，为列表时逐项转为 `Path`；测试类与应用类分别在与 `raser` 平级的 `raser_bench`（`src/raser_bench/`）和 `raser_app`（`src/raser_app/`）包里，调用 `app_component_roots(app_name, *app_names)` 时，会将一个或多个测试或应用的 `app_component_root(name)`（按各自包的根目录定位，即 `<包根>/<名字>/components`）作为 `extra_roots` 传给 `component_roots()`；
     3. `os.environ.get("RASER_COMPONENT_PATH", "")`：按 `os.pathsep`（Linux 与 macOS 上为 `:`，Windows 上为 `;`）切分，过滤掉空字符串片段后逐项转为 `Path(path)`；
     4. `DEFAULT_COMPONENT_ROOT`：包内置的 `PACKAGE_ROOT / "components"`。
   - 遍历 `roots`，以字符串 `key = str(root)` 在集合 `seen` 中去重，保留首次出现的位置，返回 `deduped`（`list[Path]`）。
2. **生成候选路径列表（`component_candidates(*parts, roots=None)`）**：`roots is None` 时取 `search_roots = component_roots()`，显式传入 `roots` 时取 `search_roots = list(roots)`。依次把相对路径片段 `*parts` 拼接到每个根目录后，返回 `[root.joinpath(*parts) for root in search_roots]`。
3. **按候选顺序查找组件（`component_path(*parts, roots=None)`、`optional_component_path(*parts, roots=None)`）**：
   - 遍历 `component_candidates(*parts, roots=roots)`，返回第一个存在的 `Path`。名字按写法逐级核对，大小写也要一致：`HPK-Si-PIN` 找不到 `HPK-Si-PiN.json`，在不区分大小写的文件系统（如 macOS）上也一样，同一条命令在各台机器上结果相同；
   - 若所有候选路径都不存在：`optional_component_path()` 返回 `None`；`component_path()` 抛出 `FileNotFoundError` 并列出检查过的全部路径：

     ```text
     FileNotFoundError: Cannot find RASER component <parts>:
       - <candidate_1>
       - <candidate_2>
     ```

     其中 `<parts>` 是用 `/` 拼接的传入片段。原因是各级搜索根目录里都没有这个组件文件；核对组件名称与子目录，或把自定义组件放到当前项目的 `components/` 目录或 `RASER_COMPONENT_PATH` 中。
4. **按组件类别解析文件路径（`component_file_path(kind, name_or_path, suffix=".json")`）**：
   - 调用 `_is_path_input(name_or_path)` 判断 `name_or_path` 是否属于路径输入（绝对路径、含多级路径或带后缀）；
   - 若属于路径输入，令 `path = Path(name_or_path).expanduser()` 直接检查文件系统：
     - `path.is_file()` 为真时，返回 `path`；
     - `path.exists()` 为真但不是文件（例如传了目录）时，抛出 `IsADirectoryError: RASER <kind> input must be a file: <path>`，应改为指向具体文件；
     - `path.exists()` 为假时，抛出 `FileNotFoundError: Cannot find RASER <kind> file: <path>`，应核对文件路径。
   - 若 `name_or_path` 是纯组件名，转调并返回 `component_path(kind, str(name_or_path) + suffix)`；未找到时按第 3 步抛出 `component_path()` 的 `FileNotFoundError`。
5. **定位测试类与应用类的包内文件（`app_file_path(app_name, filename)`）**：测试类在 `raser_bench` 包（`src/raser_bench/`）、应用类在 `raser_app` 包（`src/raser_app/`），与 `raser` 平级，按各自包的根目录构造 `path = <包根>/<名字>/<filename>`。`app_name` 写成 `"<包名>/<名字>"`，例如 `"raser_app/cflm"`、`"raser_bench/signal"`。当 `path.exists()` 为真时返回 `path`；目标不存在时抛出 `FileNotFoundError: Cannot find RASER app file: <path>`。原因是测试或应用名、文件名有误，或该数据文件未打进安装包，核对拼写并确认文件存在于对应包目录即可。

### 模块工作路径与项目内输出边界保护

`paths.py` 与 `output.py` 按以下步骤推导模块工作目录并约束目录创建与文件删除：

1. **计算模块工作目录名与路径（`module_work_name(current_file_path)`、`module_work_path(current_file_path, *labels)`）**：
   - 将 `current_file_path` 解析为绝对路径 `path = Path(current_file_path).resolve()`；
   - 若文件在 `raser_bench`（`src/raser_bench/`）或 `raser_app`（`src/raser_app/`）包的根目录之下，求相对该 `<包根>` 的路径 `relative`：属于 `<包根>/<名字>/...`（即 `len(relative.parts) >= 2`）时返回 `<名字>`（`relative.parts[0]`，例如 `"signal"`、`"bmos"`），其余情况返回 `path.stem`；
   - 若文件在 `PACKAGE_ROOT`（`raser` 包根目录）之下，求 `relative = path.relative_to(PACKAGE_ROOT)` 并取 `parts = relative.parts`：若 `len(parts) >= 2` 且首段 `parts[0] == "core"`，返回第二段 `parts[1]`（例如 `"field"`、`"current"`）；若 `parts` 非空且首段 `parts[0] == "cli"`，返回 `"cli"`；其余情况返回 `path.stem`；
   - 若文件不在上述三个包的根目录之下，返回文件名词干 `path.stem`；
   - `module_work_path(current_file_path, *labels)` 返回 `project_path(module_work_name(current_file_path), *labels)`。
2. **校验项目内相对路径片段（`_relative_parts(parts)`）**：将各段转为字符串元组 `values = tuple(str(part) for part in parts)`，对每一项令 `path = Path(value)`。若 `path.is_absolute()` 为真或 `".." in path.parts`，抛出 `ValueError: Output label must remain inside the project: <value>`。原因是输出路径必须留在项目目录之内，应改用项目内的相对路径片段。校验全部通过后返回 `values`。
3. **构造带归属者的项目内路径（`owned_path(owner, *parts)`）**：
   - 调用 `labels = _relative_parts((owner, *parts))` 校验 `owner` 与 `*parts` 中的每一段（含绝对路径或 `".."` 时按第 2 步抛出 `ValueError`）；
   - 检查 `if not owner`：若 `owner` 为空字符串，抛出 `ValueError: Output owner must be named`，原因是输出目录必须明确归属者，应传入非空的模块名或环节名；
   - 返回 `project_root().joinpath(*labels)`。
4. **创建目录与兼容模块输出目录（`create_path(path)`、`output(current_file_path, *label)`）**：
   - `create_path(path)` 对 `destination = Path(path)` 执行 `destination.mkdir(parents=True, exist_ok=True)`，按需创建目标目录及所有缺失的父目录，并返回 `destination`（`Path`）；
   - `output(current_file_path, *label)` 先调用 `_relative_parts(label)` 校验所有子目录标签（若含绝对路径或 `".."`，同样抛出 `ValueError: Output label must remain inside the project: <value>`，改为合法的相对子目录标签即可），再按 `path = module_work_path(current_file_path, *_relative_parts(label))` 生成路径，调用 `create_path(path)` 确保目录存在，最后返回解析后的绝对路径字符串 `str(path.resolve())`。
5. **受边界保护的单文件删除（`delete_file(path)`）**：
   - 将目标路径与当前项目根目录分别解析为 `target = Path(path).resolve()` 和 `project_root().resolve()`，调用 `target.relative_to(project_root().resolve())` 校验包含关系；
   - 若抛出 `ValueError`（解析后的目标位于项目根目录之外），捕获并抛出 `ValueError: File removal must remain inside the project: <target>`；原因是该函数只删除项目根目录内的文件，核对文件路径或确认 `RASER_PROJECT_PATH` 指向正确项目即可；
   - 若目标位于项目根目录之内且 `target.exists()` 为真，调用 `target.unlink()` 删除该文件。

### 缺失依赖报告、进程退出清理与内存采样

`dependency.py`、`process.py` 与 `memory_decorator.py` 的执行流程如下：

1. **构造与捕获缺失依赖异常（`MissingDependency(what, how)`）**：
   - 初始化时保存 `self.what = what`（如 `"devsim is not installed"`）和 `self.how = how`（如 `"Install it with pip install devsim"`），并调用 `super().__init__(f"{what}. {how}")` 设置异常消息；
   - 命令执行期间抛出 `MissingDependency` 时，命令行入口 `main()` 捕获它并向标准错误 `sys.stderr` 输出一行：

     ```text
     raser: <what>. <how>
     ```

     随后以退出码 `1` 结束。遇到这类报错时，按 `<how>` 中的命令安装缺失依赖，或检查是否激活了包含该依赖的环境；
   - 需要 ROOT 的模块自行 `import ROOT` 或 `import cppyy`。命令执行期间若抛出 `ModuleNotFoundError as error` 且 `error.name in ROOT_MODULES`（即属于 `{"ROOT", "cppyy"}`），命令行入口捕获它并改用 `ROOT_MISSING` 向 `sys.stderr` 打印提示后以退出码 `1` 退出；其余 `ModuleNotFoundError` 原样重新抛出。
2. **去重注册与逆序执行清理回调（`at_process_end(callback)`、`close()`）**：
   - `at_process_end(callback)` 检查 `if callback not in _callbacks`；仅当 `callback` 尚未存在于模块列表 `_callbacks` 中时将其追加到末尾，同一个回调多次注册只保留首次加入的那一条；
   - `close()` 在命令行入口 `main()` 的 `finally` 块中调用，命令成功或出错退出时都会触发。函数循环执行 `while _callbacks: _callbacks.pop()()`，按后进先出（LIFO）顺序逐个弹出并执行回调，确保每个回调在弹出后只运行一次；若某个回调抛出异常，清理立即停止并把异常向外抛出，尚未弹出的回调留在 `_callbacks` 列表里。
3. **函数调用前后的进程内存采样（`memory_decorator(func)`）**：
   - 通过 `functools.wraps(func)` 包装 `func`。每次调用 `wrapper(*args, **kwargs)` 时，先取 `process = psutil.Process()` 并读取 `mem_info_before = process.memory_info()`；
   - 将调用前的常驻集大小与虚拟内存大小由字节（$\text{B}$）换算为兆字节（$\text{MB}$）：

     $$\text{rss} = \frac{\text{mem\_info.rss}}{1024^2}, \qquad \text{vms} = \frac{\text{mem\_info.vms}}{1024^2} \tag{1}$$

     其中：
     - $\text{mem\_info.rss}$：进程常驻集大小，$\text{B}$；
     - $\text{mem\_info.vms}$：进程虚拟内存大小，$\text{B}$；
     - $\text{rss}$、$\text{vms}$：换算后的常驻集大小与虚拟内存大小，$\text{MB}$。
   - 调用 `func` 前向标准输出打印第一行：`Memory usage before calling <func.__name__>: RSS = <rss_before:.2f> MB, VMS = <vms_before:.2f> MB`；
   - 执行 `result = func(*args, **kwargs)`。若被装饰函数在执行中抛出异常，终端只保留调用前的第一行输出，随后原异常照常向外传播；
   - 函数正常返回后再次读取 `mem_info_after = process.memory_info()`，按式 (1) 计算 `rss_after` 与 `vms_after`（$\text{MB}$），向标准输出打印后两行并返回 `result`：

     ```text
     Memory usage before calling <func.__name__>: RSS = <rss_before:.2f> MB, VMS = <vms_before:.2f> MB
     Memory usage after calling <func.__name__>: RSS = <rss_after:.2f> MB, VMS = <vms_after:.2f> MB
     Memory increase: RSS = <rss_after - rss_before:.2f> MB, VMS = <vms_after - vms_before:.2f> MB
     ```

## 软件实现

### 源文件分工

- `src/raser/supports/paths.py`：定义 `PACKAGE_ROOT`、`REPO_ROOT`、`DEFAULT_COMPONENT_ROOT`；实现源码树判定（`source_tree`）、工作区与项目根目录解析（`default_work_root`、`work_root`、`project_root`、`project_path`、`infer_project_root`）、环境变量上下文管理器（`project_root_context`、`_environment`）、组件与测试、应用包内文件路径定位（`component_roots`、`app_component_root`、`app_component_roots`、`app_file_path`、`component_candidates`、`component_path`、`optional_component_path`、`component_file_path`）以及模块工作目录推导（`module_work_name`、`module_work_path`）。
- `src/raser/supports/output.py`：实现项目内相对路径片段校验（`_relative_parts`）、带归属者的项目内路径构造（`owned_path`）、兼容旧调用的模块输出目录创建（`output`）、按需目录创建（`create_path`）以及限制在项目根目录之内的单文件删除（`delete_file`）。
- `src/raser/supports/dependency.py`：定义缺失依赖异常 `MissingDependency`，以及 PyROOT 模块名集合 `ROOT_MODULES` 和预构造异常实例 `ROOT_MISSING`。
- `src/raser/supports/process.py`：维护模块级清理回调列表 `_callbacks`，提供去重注册函数 `at_process_end` 和后进先出清理函数 `close`。
- `src/raser/supports/memory_decorator.py`：提供函数装饰器 `memory_decorator`，通过 `psutil.Process().memory_info()` 在函数执行前后采样并打印进程的 `RSS` 与 `VMS`。

### 核心数据结构

| 数据结构或状态 | 字段或元素 | 类型 | 单位 | 含义 |
| --- | --- | --- | --- | --- |
| `MissingDependency`（`dependency.py`） | `what` | `str` | 无 | 缺少的外部程序或 Python 包描述（如 `"devsim is not installed"`） |
| `MissingDependency`（`dependency.py`） | `how` | `str` | 无 | 补装该依赖的命令提示（如 `"Install it with pip install devsim"`） |
| `MissingDependency`（`dependency.py`） | `args` | `tuple[str]` | 无 | 传给 `Exception` 基类的消息元组，首项为 `f"{what}. {how}"` |
| `_callbacks`（`process.py`） | 列表元素 `callback` | `Callable[[], None]` | 无 | 按注册先后排列、按相等性去重的无参进程退出清理回调 |
| `memory_decorator` 采样量（`memory_decorator.py`） | `mem_info_before.rss`, `mem_info_after.rss` | `int` | $\text{B}$ | 函数调用前后的进程常驻集字节数 |
| `memory_decorator` 采样量（`memory_decorator.py`） | `mem_info_before.vms`, `mem_info_after.vms` | `int` | $\text{B}$ | 函数调用前后的进程虚拟内存字节数 |
| `memory_decorator` 采样量（`memory_decorator.py`） | `rss_before`, `rss_after` | `float` | $\text{MB}$ | 按 $1024^2\ \text{B/MB}$ 换算后的调用前后常驻集大小 |
| `memory_decorator` 采样量（`memory_decorator.py`） | `vms_before`, `vms_after` | `float` | $\text{MB}$ | 按 $1024^2\ \text{B/MB}$ 换算后的调用前后虚拟内存大小 |

## 接口

### 环境变量

使用者能设的只有下表列出的三个环境变量；表外的包路径常量、四级组件搜索顺序、`ROOT_MODULES` 与内存换算因子等参数都写死在代码里。

| 选项或键 | 默认值 | 单位 | 含义 |
| --- | --- | --- | --- |
| `RASER_WORK_PATH` | 未设置（回退到 `default_work_root()`：源码树下为 `<REPO_ROOT>/work`，包安装模式下为当前工作目录下的 `work`） | 无 | 工作区根目录路径，由 `work_root()` 读取；设置后直接按 `Path(RASER_WORK_PATH)` 解析 |
| `RASER_PROJECT_PATH` | 未设置（`project_root()` 回退到 `Path.cwd()`） | 无 | 当前项目根目录路径，由 `project_root()` 和 `infer_project_root()` 读取；设置且非空时 `infer_project_root()` 直接采用它；`project_root_context()` 在上下文内临时覆盖并在退出时恢复该变量 |
| `RASER_COMPONENT_PATH` | `""` | 无 | 附加组件搜索根目录列表，由 `component_roots()` 读取；多个目录用 `os.pathsep`（Linux 与 macOS 上为 `:`，Windows 上为 `;`）分隔，空片段忽略；`project_root_context()` 传入测试或应用列表时会把对应的 `<包根>/<名字>/components` 目录前置到该变量中，退出时恢复原值 |

### 读写与检查的文件及目录

`supports` 为各环节与命令检查、创建或删除以下路径：

- **`<REPO_ROOT>/pyproject.toml`**：由 `source_tree()` 通过 `.is_file()` 只读检查是否存在，配合 `PACKAGE_ROOT.parent.name == "src"` 判定当前是否运行于源码树中（TOML 文本文件）。
- **组件候选文件 `<component_root>/<kind>/<name><suffix>`**：由 `component_path()`、`optional_component_path()` 与 `component_file_path()` 按 `<project_root>/components/`、`extra_roots`、`RASER_COMPONENT_PATH`、`<PACKAGE_ROOT>/components/` 的顺序检查 `.exists()` 或 `.is_file()` 并返回 `Path`（`suffix` 默认为 `".json"`），文件内容与字段单位由调用方环节或组件模块解析。
- **测试类与应用类的包内文件 `<包根>/<名字>/<filename>`**：由 `app_file_path()` 按 `raser_bench`（`src/raser_bench/`）或 `raser_app`（`src/raser_app/`）各自包的根目录检查 `.exists()` 并返回 `Path`，供测试或应用读取各自目录下的内置配置或数据文件。
- **项目内输出目录 `<project_root>/<owner>/<parts...>` 与 `<project_root>/<module_work_name>/<label...>`**：由 `owned_path()`、`module_work_path()` 构造路径，`create_path()` 与 `output()` 调用 `mkdir(parents=True, exist_ok=True)` 创建目录；项目根目录内的单文件 `<project_root>/<相对路径>` 由 `delete_file()` 校验归属后调用 `unlink()` 删除。
