# Common Infrastructure (`supports`)

`src/raser/supports/` sits at the bottom layer of the RASER software hierarchy (see [Architecture Overview](../architecture.md) for layer boundaries) and imports only the Python standard library and `psutil`; plotting (`figures`) additionally imports matplotlib and ROOT. It handles command target arguments, runtime environment variables, exit cleanup requests, and exception interception passed from [Command-Line Interface (`raser`)](../cli.md); performs workspace and project path resolution (`paths`), in-project output boundary checks and file deletion (`output`), missing-dependency reporting (`dependency`), process-exit cleanup callbacks (`process`), function memory-usage sampling (`memory_decorator`), and shared figure styling and saving across stages ([`figures`](figures.md)); and supplies resolved `Path` objects, directory and file operations, dependency exceptions, and memory diagnostics to upper layers such as [Experiments, Scan Points, and Seeds](../lifecycle/experiments.md), [Simulation Chain and Stage Entry Points (`stages`)](../stages/README.md), and [Device Model (`core/device`)](../core/device.md), as well as `components`, the benchmark package `raser_bench`, and the application package `raser_app`.

## Behavior

### Workspace, Project, and Component Path Resolution (`paths`)

Whether RASER is run from a source tree or as an installed package, CLI startup, experiment initialization, and component loading across stages all use `raser.supports.paths` to resolve the workspace root, active project root, and packaged files of benchmark and application classes, and to locate component files across a four-level priority order. When running the following scan command:

```bash
raser signal HPK-Si-PiN --scan field.voltage=100,200 -s 2 --seed 1
```

Before entering the subcommand, the CLI entry point calls `infer_project_root("HPK-Si-PiN")` (resolving to `examples/HPK-Si-PiN/` when `HPK-Si-PiN` does not exist under `work/`) and sets the path context via `project_root_context()`, so each layer resolves the following paths:

```text
work_root()           -> work/
project_root()        -> examples/HPK-Si-PiN/
component_file_path() -> src/raser/components/device/HPK-Si-PiN.json
                         src/raser/components/deposit/   source decay/Sr90, Geant4 setup device_alone
                         src/raser/components/readout/   SantaCruz, Gali52, Termination50
```

Components are grouped into folders by the stage that reads them: `device/` holds devices, `deposit/` holds Geant4 setups, radioactive sources and beams, and lasers, `readout/` holds front-end amplifiers and termination circuits, `digitizer/` holds sampling and quantization settings, and `trigger/` holds trigger conditions (see [Architecture Overview](../architecture.md#components)).

### In-Project Output Paths and File Deletion Protection (`output`)

When stages and core modules construct output directories or remove old files under the active project, they validate relative path segments and deletion targets through `raser.supports.output`. If a path segment is an absolute path or contains `".."`, if the owner name is empty, or if a resolved deletion target lies outside `project_root()`, the operation aborts with `ValueError` before touching disk:

```text
owned_path("field", "<node_id>") -> <device_project>/field/<node_id>/
owned_path("field", "../out")    -> ValueError: Output label must remain inside the project: ../out
delete_file("/tmp/test.h5")      -> ValueError: File removal must remain inside the project: /tmp/test.h5
```

### Missing Dependency Catching and Reporting (`dependency`)

When an external program or Python package required by a subcommand is not installed in the current environment, modules construct and raise `raser.supports.dependency.MissingDependency` (or the CLI entry point intercepts a `ModuleNotFoundError` whose module name is in `ROOT_MODULES` and substitutes `ROOT_MISSING`). Upon catching the exception, the CLI prints a single-line reason and installation command to standard error and exits with status code `1`:

```text
raser: ROOT's Python bindings are not available in this Python. Install them with conda install -c conda-forge root_base
```

### Process-Exit Cleanup Callbacks (`process`)

Modules that need to release external resources or finalize runtime state before process exit register zero-argument cleanup functions via `raser.supports.process.at_process_end()` during execution. The command calls `process.close()` in the `finally` block of `main()`, popping and executing registered callbacks in last-in, first-out (LIFO) order so that each callback runs only once:

```python
from raser.supports import process

process.at_process_end(cleanup_first)
process.at_process_end(cleanup_second)
process.close()  # Executes cleanup_second() first, then cleanup_first()
```

### Function Memory Usage Diagnostics (`memory_decorator`)

Before and after each call to a function decorated with `@memory_decorator`, the decorator reads the current process's resident set size (`rss`) and virtual memory size (`vms`) via `psutil`, converts them to $\text{MB}$, and prints before, after, and delta memory lines to standard output. `loop_solver` in `loop_section.py` of [Field Solving and Loading (`core/field`)](../core/field.md) uses this decorator (see [Field Solving Stage (`stages/field`)](../stages/field.md) for stage dispatch), producing terminal output such as:

```text
Memory usage before calling loop_solver: RSS = 357.12 MB, VMS = 402563.59 MB
...
Memory usage after calling loop_solver: RSS = 358.62 MB, VMS = 402563.59 MB
Memory increase: RSS = 1.50 MB, VMS = 0.00 MB
```

## Rules

### Built-in Constants

The table below lists all module-level constants and fixed conversion factors in `paths.py`, `dependency.py`, and `memory_decorator.py`:

| Constant Name | Value | Unit | Definition Location and Meaning |
| --- | --- | --- | --- |
| `PACKAGE_ROOT` | `Path(__file__).resolve().parents[1]` | None | `paths.py`: root directory of the `raser` package; `<REPO_ROOT>/src/raser` in a source tree, or the installed `raser` directory in package-install mode |
| `REPO_ROOT` | Return value of `source_tree()` (`Path` or `None`) | None | `paths.py`: repository root directory when running from a source checkout or `pip install -e`; `None` for a regular package installation |
| `DEFAULT_COMPONENT_ROOT` | `PACKAGE_ROOT / "components"` | None | `paths.py`: root directory of the built-in component library; `src/raser/components` in a source tree |
| `ROOT_MODULES` | `{"ROOT", "cppyy"}` | None | `dependency.py`: set of top-level module names corresponding to ROOT's Python bindings |
| `ROOT_MISSING` | `MissingDependency("ROOT's Python bindings are not available in this Python", "Install them with conda install -c conda-forge root_base")` | None | `dependency.py`: preconstructed exception instance printed uniformly by the CLI entry point when PyROOT is missing |
| `1024**2` | `1048576` | $\text{B/MB}$ | `memory_decorator.py`: divisor converting `psutil` memory byte counts ($\text{B}$) to megabytes ($\text{MB}$) |

### Source Tree Detection and Workspace and Project Root Resolution

`paths.py` determines the source tree, workspace root, and project root in the following order:

1. **Source tree detection (`source_tree(package_root=PACKAGE_ROOT)`)**: Takes the directory two levels up, `tree = package_root.parents[1]`. If both `package_root.parent.name == "src"` and `(tree / "pyproject.toml").is_file()` are true, returns that repository root `tree` (`Path`); otherwise returns `None`. `source_tree()` is called at module import time to initialize `REPO_ROOT`.
2. **Default workspace root calculation (`default_work_root(tree=REPO_ROOT, cwd=None)`)**: If `tree is not None`, returns `tree / "work"`; if `tree is None` (regular package-install mode), returns `Path(cwd or Path.cwd()) / "work"` so that outputs fall under the current working directory.
3. **Active workspace root lookup (`work_root()`)**: Reads the environment variable `given = os.environ.get("RASER_WORK_PATH")`. If `given is not None`, returns `Path(given)`; otherwise returns `default_work_root()`.
4. **Active project root and path joining (`project_root()`, `project_path(*parts)`)**: `project_root()` reads `os.environ.get("RASER_PROJECT_PATH", Path.cwd())` and returns it as a `Path` (falling back to the current working directory `Path.cwd()` when `RASER_PROJECT_PATH` is unset). `project_path(*parts)` passes relative path segments `*parts` to `project_root().joinpath(*parts)` and returns the resulting `Path`.

### Project Root Inference and Environment Variable Context Switching

When the CLI entry point infers the project root from an input argument and temporarily switches environment variables, it executes the following steps:

1. **Checking the environment variable and empty input (`infer_project_root(input_value)`)**:
   - If `os.environ.get("RASER_PROJECT_PATH")` is set and non-empty, returns `project_root()` directly;
   - If `input_value is None`, returns `project_root()` directly.
2. **Distinguishing path inputs from non-path inputs (`_is_path_input(input_value)`)**: Sets `path = Path(input_value)` and tests whether any of the following three conditions holds:
   - `path.is_absolute()` is true (absolute path);
   - `len(path.parts) > 1` (multi-segment path);
   - `bool(path.suffix)` is true (has a file suffix).

   If none of the three holds (a plain name, such as `"HPK-Si-PiN"` or `"bmos"`), looks up the project in order of `work/<name>/` (`work_root() / str(input_value)`), `examples/<name>/` (`REPO_ROOT / "examples" / str(input_value)` in a source tree), and `./<name>/` (`Path.cwd() / str(input_value)`), returning the first existing directory; if none of the three exists, exits with an error (use `raser new --from` to create a new project; see [Experiments, Scan Points, and Seeds](../lifecycle/experiments.md)). For example, `raser signal HPK-Si-PiN` resolves to `examples/HPK-Si-PiN/` when it does not exist under `work/`. If any condition holds, the input is treated as a path, `Path(input_value).expanduser()` is called to expand `~`, and execution proceeds to step 3.
3. **Extracting the project root from a path input (`_project_root_from_path(path)`)**: Takes the path segment tuple `parts = path.parts`:
   - If `"components" in parts`, takes its first occurrence `index = parts.index("components")`; when `index > 0` (i.e., `"components"` appears after the first segment), returns the parent path preceding the first `"components"`, `Path(*parts[:index])`;
   - Otherwise checks `path.is_dir()`: if the path itself is an existing directory, returns `path`; in all other cases, returns its parent directory `path.parent`.
4. **Temporarily switching environment-variable context (`project_root_context(project_path_value, component_apps=())`)**:
   - Computes the target project path string: `project = None` when `project_path_value is None`, otherwise `project = str(project_path_value)`;
   - Computes the additional component path string: `components = None` when `component_apps` is empty; when `component_apps` is non-empty, builds `roots = [str(app_component_root(app)) for app in component_apps]` in order, reads the existing environment variable `previous = os.environ.get("RASER_COMPONENT_PATH")`, appends `previous` to the end of `roots` if non-empty, and sets `components = os.pathsep.join(roots)`;
   - Enters nested `_environment("RASER_PROJECT_PATH", project)` and `_environment("RASER_COMPONENT_PATH", components)`: when the passed `value is None`, leaves `os.environ` unchanged and yields directly; when `value is not None`, saves `previous = os.environ.get(name)`, sets `os.environ[name] = value`, and in the `finally` block either calls `os.environ.pop(name, None)` if `previous is None` or restores `os.environ[name] = previous`.

### Component Search Priority and File Lookup

Component files and packaged files of benchmark and application classes are located in the following steps:

1. **Assembling and deduplicating search root directories (`component_roots(extra_roots=None)`)**:
   - Collects four tiers of directories into list `roots` in fixed order from highest to lowest priority:
     1. `project_path("components")`: the `components/` directory of the active project;
     2. `_as_path_list(extra_roots)`: `[]` when `extra_roots` is `None`, `[Path(extra_roots)]` for a single `str | os.PathLike`, or item-by-item `Path` conversion for a list; benchmark and application classes live in the sibling packages `raser_bench` (`src/raser_bench/`) and `raser_app` (`src/raser_app/`) alongside `raser`, and calling `app_component_roots(app_name, *app_names)` passes one or more benchmarks' or apps' `app_component_root(name)` (resolved from each package's own root, i.e., `<package_root>/<name>/components`) as `extra_roots` to `component_roots()`;
     3. `os.environ.get("RASER_COMPONENT_PATH", "")`: split by `os.pathsep` (`:` on Linux and macOS, `;` on Windows), dropping empty string segments and converting each remaining entry to `Path(path)`;
     4. `DEFAULT_COMPONENT_ROOT`: the package's built-in `PACKAGE_ROOT / "components"`.
   - Iterates over `roots`, deduplicating by string `key = str(root)` in set `seen` while preserving first appearance, and returns `deduped` (`list[Path]`).
2. **Generating candidate paths (`component_candidates(*parts, roots=None)`)**: Uses `search_roots = component_roots()` when `roots is None`, or `search_roots = list(roots)` when `roots` is explicitly provided. Appends relative path segments `*parts` to each root and returns `[root.joinpath(*parts) for root in search_roots]`.
3. **Searching candidates in order (`component_path(*parts, roots=None)`, `optional_component_path(*parts, roots=None)`)**:
   - Iterates over `component_candidates(*parts, roots=roots)` and returns the first `Path` for which `candidate.exists()` is true;
   - If none of the candidates exist: `optional_component_path()` returns `None`; `component_path()` raises `FileNotFoundError` listing all inspected paths:

     ```text
     FileNotFoundError: Cannot find RASER component <parts>:
       - <candidate_1>
       - <candidate_2>
     ```

     where `<parts>` is the passed segments joined with `/`. This happens because no search root contains the component file; verify the component name and subdirectory, or place a custom component in the active project's `components/` directory or `RASER_COMPONENT_PATH`.
4. **Resolving a file path by component kind (`component_file_path(kind, name_or_path, suffix=".json")`)**:
   - Calls `_is_path_input(name_or_path)` to check whether `name_or_path` is a path input (absolute path, multi-segment path, or carrying a suffix);
   - If it is a path input, sets `path = Path(name_or_path).expanduser()` and checks the filesystem directly:
     - Returns `path` when `path.is_file()` is true;
     - Raises `IsADirectoryError: RASER <kind> input must be a file: <path>` when `path.exists()` is true but it is not a file (for example, a directory was passed), so the caller should point to a specific file instead;
     - Raises `FileNotFoundError: Cannot find RASER <kind> file: <path>` when `path.exists()` is false, indicating the file path should be checked.
   - If `name_or_path` is a plain component name, delegates to and returns `component_path(kind, str(name_or_path) + suffix)`; if not found, raises `component_path()`'s `FileNotFoundError` as in step 3.
5. **Locating packaged files of benchmark and application classes (`app_file_path(app_name, filename)`)**: Benchmark classes live in the `raser_bench` package (`src/raser_bench/`) and application classes live in the `raser_app` package (`src/raser_app/`), alongside `raser`, constructing `path = <package_root>/<name>/<filename>` from each package's own root. Returns `path` when `path.exists()` is true; raises `FileNotFoundError: Cannot find RASER app file: <path>` if missing. This occurs when the benchmark or app name or filename is wrong or the data file was not included in the installed package; verify spelling and confirm the file exists in the corresponding package directory.

### Module Work Paths and In-Project Output Boundary Protection

`paths.py` and `output.py` derive module work directories and enforce directory-creation and file-deletion boundaries in the following steps:

1. **Computing module work directory name and path (`module_work_name(current_file_path)`, `module_work_path(current_file_path, *labels)`)**:
   - Resolves `current_file_path` to an absolute path `path = Path(current_file_path).resolve()`;
   - If the file lies under the root directory of the `raser_bench` (`src/raser_bench/`) or `raser_app` (`src/raser_app/`) package, computes `relative` relative to that `<package_root>`: if it is under `<package_root>/<name>/...` (i.e., `len(relative.parts) >= 2`), returns `<name>` (`relative.parts[0]`, such as `"signal"` or `"bmos"`), otherwise returns `path.stem`;
   - If the file lies under `PACKAGE_ROOT` (the `raser` package root), computes `relative = path.relative_to(PACKAGE_ROOT)` and takes `parts = relative.parts`: if `len(parts) >= 2` and `parts[0] == "core"`, returns the second segment `parts[1]` (such as `"field"` or `"current"`); if `parts` is non-empty and `parts[0] == "cli"`, returns `"cli"`; otherwise returns `path.stem`;
   - If the file does not lie under any of the three package roots above, returns the filename stem `path.stem`;
   - `module_work_path(current_file_path, *labels)` returns `project_path(module_work_name(current_file_path), *labels)`.
2. **Validating in-project relative path segments (`_relative_parts(parts)`)**: Converts each segment into string tuple `values = tuple(str(part) for part in parts)` and sets `path = Path(value)` for each entry. If `path.is_absolute()` is true or `".." in path.parts`, raises `ValueError: Output label must remain inside the project: <value>`. Output paths must stay within the project directory, so relative path segments inside the project must be used. Returns `values` once all checks pass.
3. **Constructing an owned in-project path (`owned_path(owner, *parts)`)**:
   - Calls `labels = _relative_parts((owner, *parts))` to validate `owner` and every segment in `*parts` (raising `ValueError` as in step 2 if any segment is absolute or contains `".."`);
   - Checks `if not owner`: if `owner` is an empty string, raises `ValueError: Output owner must be named`, because every output directory must name a non-empty module or stage owner;
   - Returns `project_root().joinpath(*labels)`.
4. **Creating directories and legacy module output directories (`create_path(path)`, `output(current_file_path, *label)`)**:
   - `create_path(path)` calls `destination.mkdir(parents=True, exist_ok=True)` on `destination = Path(path)`, creating the target directory and any missing parent directories as needed, and returns `destination` (`Path`);
   - `output(current_file_path, *label)` first validates all subdirectory labels via `_relative_parts(label)` (likewise raising `ValueError: Output label must remain inside the project: <value>` if any is absolute or contains `".."`, resolved by passing valid relative subdirectory labels), constructs `path = module_work_path(current_file_path, *_relative_parts(label))`, ensures the directory exists with `create_path(path)`, and returns the resolved absolute path string `str(path.resolve())`.
5. **Boundary-protected single-file deletion (`delete_file(path)`)**:
   - Resolves the target path and active project root as `target = Path(path).resolve()` and `project_root().resolve()`, and verifies containment via `target.relative_to(project_root().resolve())`;
   - If `ValueError` is raised (the resolved target lies outside the project root), catches it and raises `ValueError: File removal must remain inside the project: <target>`; this function deletes only files inside the project root, so verify the file path or confirm `RASER_PROJECT_PATH` points to the intended project;
   - If the target lies inside the project root and `target.exists()` is true, calls `target.unlink()` to remove the file.

### Missing Dependency Reporting, Process-Exit Cleanup, and Memory Sampling

`dependency.py`, `process.py`, and `memory_decorator.py` execute as follows:

1. **Constructing and catching missing-dependency exceptions (`MissingDependency(what, how)`)**:
   - Initialization stores `self.what = what` (such as `"devsim is not installed"`) and `self.how = how` (such as `"Install it with pip install devsim"`), and calls `super().__init__(f"{what}. {how}")` to set the exception message;
   - When `MissingDependency` is raised during command execution, the CLI entry point `main()` catches it and prints one line to standard error `sys.stderr`:

     ```text
     raser: <what>. <how>
     ```

     and exits with code `1`. Upon seeing this error, install the missing dependency using the command in `<how>` or verify that the environment containing it is activated;
   - Modules requiring ROOT execute `import ROOT` or `import cppyy` directly. If `ModuleNotFoundError as error` is raised during command execution with `error.name in ROOT_MODULES` (i.e., in `{"ROOT", "cppyy"}`), the CLI entry point catches it, prints `ROOT_MISSING` to `sys.stderr`, and exits with code `1`; all other `ModuleNotFoundError` exceptions are re-raised unchanged.
2. **Deduplicated registration and reverse-order cleanup execution (`at_process_end(callback)`, `close()`)**:
   - `at_process_end(callback)` checks `if callback not in _callbacks`; only when `callback` is not already in the module list `_callbacks` is it appended to the end, so repeated registrations of the same callback keep only its first insertion;
   - `close()` is called in the `finally` block of the CLI entry point `main()`, triggering on both normal completion and error exit. It loops `while _callbacks: _callbacks.pop()()`, popping and running callbacks in last-in, first-out (LIFO) order so each runs only once after popping; if any callback raises an exception, cleanup stops immediately and propagates the exception, leaving unpopped callbacks in `_callbacks`.
3. **Process memory sampling before and after function calls (`memory_decorator(func)`)**:
   - Wraps `func` with `functools.wraps(func)`. On each call to `wrapper(*args, **kwargs)`, gets `process = psutil.Process()` and reads `mem_info_before = process.memory_info()`;
   - Converts pre-call resident set size and virtual memory size from bytes ($\text{B}$) to megabytes ($\text{MB}$):

     $$\text{rss} = \frac{\text{mem\_info.rss}}{1024^2}, \qquad \text{vms} = \frac{\text{mem\_info.vms}}{1024^2} \tag{1}$$

     where:
     - $\text{mem\_info.rss}$: process resident set size, $\text{B}$;
     - $\text{mem\_info.vms}$: process virtual memory size, $\text{B}$;
     - $\text{rss}$, $\text{vms}$: converted resident set size and virtual memory size, $\text{MB}$.
   - Prints the first line to standard output before calling `func`: `Memory usage before calling <func.__name__>: RSS = <rss_before:.2f> MB, VMS = <vms_before:.2f> MB`;
   - Executes `result = func(*args, **kwargs)`. If the decorated function raises an exception, only the first pre-call line appears on the terminal and the original exception propagates normally;
   - After normal return, reads `mem_info_after = process.memory_info()`, computes `rss_after` and `vms_after` ($\text{MB}$) by Eq. (1), prints the remaining two lines to standard output, and returns `result`:

     ```text
     Memory usage before calling <func.__name__>: RSS = <rss_before:.2f> MB, VMS = <vms_before:.2f> MB
     Memory usage after calling <func.__name__>: RSS = <rss_after:.2f> MB, VMS = <vms_after:.2f> MB
     Memory increase: RSS = <rss_after - rss_before:.2f> MB, VMS = <vms_after - vms_before:.2f> MB
     ```

## Software Implementation

### Source File Responsibilities

- `src/raser/supports/paths.py`: defines `PACKAGE_ROOT`, `REPO_ROOT`, and `DEFAULT_COMPONENT_ROOT`; implements source tree detection (`source_tree`), workspace and project root resolution (`default_work_root`, `work_root`, `project_root`, `project_path`, `infer_project_root`), environment-variable context management (`project_root_context`, `_environment`), component and benchmark/app packaged file lookup (`component_roots`, `app_component_root`, `app_component_roots`, `app_file_path`, `component_candidates`, `component_path`, `optional_component_path`, `component_file_path`), and module work directory derivation (`module_work_name`, `module_work_path`).
- `src/raser/supports/output.py`: implements in-project relative path segment validation (`_relative_parts`), owned in-project path construction (`owned_path`), backward-compatible module output directory creation (`output`), on-demand directory creation (`create_path`), and project-root-bounded single-file deletion (`delete_file`).
- `src/raser/supports/dependency.py`: defines the missing-dependency exception `MissingDependency`, the PyROOT module name set `ROOT_MODULES`, and the preconstructed exception instance `ROOT_MISSING`.
- `src/raser/supports/process.py`: maintains the module-level cleanup callback list `_callbacks`, providing deduplicated registration `at_process_end` and LIFO cleanup `close`.
- `src/raser/supports/memory_decorator.py`: provides the function decorator `memory_decorator`, sampling and printing process `RSS` and `VMS` before and after function execution via `psutil.Process().memory_info()`.

### Core Data Structures

| Data Structure or State | Field or Element | Type | Unit | Meaning |
| --- | --- | --- | --- | --- |
| `MissingDependency` (`dependency.py`) | `what` | `str` | None | Description of the missing external program or Python package (such as `"devsim is not installed"`) |
| `MissingDependency` (`dependency.py`) | `how` | `str` | None | Installation command hint for the missing dependency (such as `"Install it with pip install devsim"`) |
| `MissingDependency` (`dependency.py`) | `args` | `tuple[str]` | None | Message tuple passed to the `Exception` base class, with first item `f"{what}. {how}"` |
| `_callbacks` (`process.py`) | List element `callback` | `Callable[[], None]` | None | Zero-argument process-exit cleanup callbacks ordered by registration and deduplicated by equality |
| `memory_decorator` sampled quantities (`memory_decorator.py`) | `mem_info_before.rss`, `mem_info_after.rss` | `int` | $\text{B}$ | Process resident set size in bytes before and after the function call |
| `memory_decorator` sampled quantities (`memory_decorator.py`) | `mem_info_before.vms`, `mem_info_after.vms` | `int` | $\text{B}$ | Process virtual memory size in bytes before and after the function call |
| `memory_decorator` sampled quantities (`memory_decorator.py`) | `rss_before`, `rss_after` | `float` | $\text{MB}$ | Resident set size before and after the call converted by $1024^2\ \text{B/MB}$ |
| `memory_decorator` sampled quantities (`memory_decorator.py`) | `vms_before`, `vms_after` | `float` | $\text{MB}$ | Virtual memory size before and after the call converted by $1024^2\ \text{B/MB}$ |

## Interface

### Environment Variables

The only three environment variables users can set are listed in the table below; all other parameters—such as package path constants, the four-tier component search order, `ROOT_MODULES`, and the memory conversion factor—are hardcoded in the code.

| Option or Key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `RASER_WORK_PATH` | Unset (falls back to `default_work_root()`: `<REPO_ROOT>/work` in a source tree, or `work` under the current working directory in package-install mode) | None | Workspace root directory path read by `work_root()`; when set, resolved directly as `Path(RASER_WORK_PATH)` |
| `RASER_PROJECT_PATH` | Unset (`project_root()` falls back to `Path.cwd()`) | None | Active project root directory path read by `project_root()` and `infer_project_root()`; when set and non-empty, adopted directly by `infer_project_root()`; temporarily overridden inside `project_root_context()` and restored on exit |
| `RASER_COMPONENT_PATH` | `""` | None | List of additional component search root directories read by `component_roots()`; multiple directories are separated by `os.pathsep` (`:` on Linux and macOS, `;` on Windows) with empty segments ignored; when `project_root_context()` receives a benchmark or app list, each corresponding `<package_root>/<name>/components` directory is prepended to this variable and the original value is restored on exit |

### Files and Directories Read, Written, and Checked

`supports` checks, creates, or deletes the following paths for stages and commands:

- **`<REPO_ROOT>/pyproject.toml`**: checked read-only for existence via `.is_file()` by `source_tree()`, paired with `PACKAGE_ROOT.parent.name == "src"` to determine whether RASER is running from a source tree (TOML text file).
- **Component candidate files `<component_root>/<kind>/<name><suffix>`**: checked via `.exists()` or `.is_file()` by `component_path()`, `optional_component_path()`, and `component_file_path()` in order `<project_root>/components/`, `extra_roots`, `RASER_COMPONENT_PATH`, `<PACKAGE_ROOT>/components/`, returning `Path` (`suffix` defaults to `".json"`); file contents and field units are parsed by the calling stage or component module.
- **Packaged files of benchmark and application classes `<package_root>/<name>/<filename>`**: checked via `.exists()` by `app_file_path()` against each package's own root directory in `raser_bench` (`src/raser_bench/`) or `raser_app` (`src/raser_app/`), returning `Path` for benchmarks or apps to read built-in configuration or data files under their respective directories.
- **In-project output directories `<project_root>/<owner>/<parts...>` and `<project_root>/<module_work_name>/<label...>`**: constructed by `owned_path()` and `module_work_path()`, and created via `mkdir(parents=True, exist_ok=True)` by `create_path()` and `output()`; single files `<project_root>/<relative_path>` inside the project root are validated for containment and deleted via `unlink()` by `delete_file()`.
