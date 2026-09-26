# 入门

> RASER 5.0 · Python 3.11 · 安装与使用分为两个步骤

环境安装一次即可。每个新 shell 在运行 RASER 前激活一条完整环境路径。该路径提供彼此匹配的 Python、ROOT、Geant4 与 ngspice 运行环境。

---

## 📦 安装环境

根据主机平台选择一条路径。本节命令用于创建环境或镜像。工作流命令见[运行 RASER](#运行-raser)。

首次安装时按所选平台执行下列命令。安装完成后，每个新 shell 只需一条激活命令。

### 原生 Linux 与 WSL

`conda` 位于 `PATH` 中时，一条命令创建 `.conda/envs/raser` 与项目 venv：

```bash
env/install_conda.sh
```

脚本按主机架构选择 conda 规格。conda 环境提供 Python 3.11、ROOT、Geant4 11.3.2 及其数据集和 ngspice；x86-64 上还提供 MKL，aarch64 上由 `env/install-ngspice.sh` 把 ngspice 构建进该环境。项目 venv 继承这些包，并加入 `env/uv.txt` 中固定版本的 Python 包。WSL 中在 Linux 发行版内使用本路径。

`env/install_conda.sh --without-geant4` 使环境省略 Geant4；`--without-root` 同时省略 ROOT 与 Geant4，因为 Geant4 的 Python 绑定使用 ROOT 提供的 cppyy。激活时如何找到它们见[使用外部 ROOT 或 Geant4](#使用外部-root-或-geant4)。

| 架构 | conda 规格 | 显式规格 |
| --- | --- | --- |
| x86-64 | `env/conda-linux-x86.yml` | `env/conda-linux-64.lock` |
| aarch64 | `env/conda-linux-aarch64.yml` | `env/conda-linux-aarch64.lock` |

需要精确的 conda 产物时，由显式规格创建环境，再执行 venv 步骤：

```bash
conda create -p .conda/envs/raser -c conda-forge --file env/conda-linux-64.lock
conda activate "$PWD/.conda/envs/raser"
uv venv --system-site-packages --python "$(command -v python3.11)" .venv
uv pip sync --python .venv/bin/python env/uv.txt
```

### IHEP 计算集群 Conda

集群上的 conda 指令由以下脚本提供，随后执行原生 Linux 安装脚本：

```bash
source /cvmfs/common.ihep.ac.cn/software/anaconda/miniconda3-202505/etc/profile.d/conda.sh
env/install_conda.sh
```

### IHEP 计算集群 Ubuntu 22.04 SIF

```bash
apptainer build --mksquashfs-args '-processors 1' \
    img/raser_ubuntu.sif bootstrap/ubuntu/raser-ubuntu-sif.def
```

该镜像提供项目 Python 环境、ngspice 与 Ubuntu 运行库。ROOT 和 Geant4 来自匹配的 `ubuntu2204` LCG view。

### IHEP 计算集群 EL9 SIF

```bash
apptainer build --mksquashfs-args '-processors 1' \
    img/raser_el9.sif bootstrap/el9/raser-el9-sif.def
```

该镜像提供项目 Python 环境、ngspice 与 EL9 运行库。ROOT 来自匹配的 `x86_64-el9` LCG view，Geant4 来自外部 EL9 安装。可选源码归档可缓存在 `bootstrap/ingredients/` 下。

单进程 squashfs 选项用于受限集群节点。镜像细节见[容器路径说明](../../bootstrap/README.md)。

### 原生 Apple Silicon

固定版本的 Python 包要求 arm64 上的 macOS 14 或更新版本。ROOT 与 Geant4 11.3.2 及其数据集由 conda 提供；ngspice 构建至该 conda 环境中。同一安装脚本及其选项覆盖本平台：

```bash
env/install_conda.sh
```

对应的显式 conda 规格如下；由它创建环境后，先激活环境并执行 `env/install-ngspice.sh`，再执行 venv 步骤：

```bash
conda create -p .conda/envs/raser -c conda-forge --file env/conda-macos-arm64.lock
```

基于 Lima 的 macOS 路径先构建 Ubuntu SIF，再使用 `make run-raser-sif-macos`。

## 🔌 激活环境路径

激活其中一条路径：

| 路径 | 命令 |
| --- | --- |
| 原生 conda | `source env/setup_cvmfs.sh conda` |
| Ubuntu 22.04 SIF | `source env/setup_cvmfs.sh ubuntu` |
| EL9 SIF | `source env/setup_cvmfs.sh el9` |
| 本地自动选择 | `source env/setup_cvmfs.sh` |

自动选择依次查找本地 Ubuntu SIF、本地 EL9 SIF 和 conda 路径。conda 路径优先加载已配置的 CVMFS profile；若该文件不存在，则从 `PATH` 加载 conda。随后激活 `.conda/envs/raser`，其他 conda 环境处于激活状态时同样如此。

### 使用外部 ROOT 或 Geant4

conda 路径上，激活前指定的安装优先于 `.conda/envs/raser` 中的同名软件包，无论环境是否包含该软件包：

```bash
export RASER_ROOT_INSTALL=/path/to/root      # 含 bin/root-config 与 bin/thisroot.sh，针对 Python 3.11 构建
export RASER_GEANT4_INSTALL=/path/to/geant4  # 含 bin/geant4-config 与 bin/geant4.sh
source env/setup_cvmfs.sh conda
```

`RASER_ROOT_INSTALL` 指向独立安装的 ROOT，例如 CERN 二进制发行包、CVMFS 上的 LCG 发行版或源码构建。其他 conda 环境中的 ROOT 软件包只能在该环境激活后运行。激活时会报告每个外部安装及其版本；外部 ROOT 与随 conda ROOT 构建的 Geant4 同时使用时给出警告。以 `--without-geant4` 安装且未设置 `RASER_GEANT4_INSTALL` 的环境使用 CVMFS 上的 Geant4 11.3.p02 EL9 构建。

设置脚本向当前 shell 加入项目 CLI、组件搜索路径与 `work/` 位置。依赖安装在前述环境准备步骤中完成。

## 🚀 运行 RASER

首先使用元数据命令检查当前环境路径：

```bash
raser --version
raser --help
```

随后通过公共 CLI 运行工作流：

```bash
raser field -cv HPK-Si-PiN
raser signal HPK-Si-PiN
raser cce NJU-PiN
```

使用 `raser <command> --help` 查看选项。公共命令为 `raser`；源码树中的模块路径属于实现细节。

## 验证完整传感器链

下列命令求解 Device 场数据，并以固定工作参数和随机种子运行三个主要传感器响应应用：

```bash
source env/setup_cvmfs.sh conda
raser field HPK-Si-PiN -bias 200
raser field -wf HPK-Si-PiN -bias 200
raser signal HPK-Si-PiN decay/Sr90 -vol 200 --events-per-job 1 --seed 7
raser tct signal HPK-Si-PiN SPA_top_Si_IR -vol 200 --seed 7
raser timeres HPK-Si-PiN decay/Sr90 -vol 200 --events-per-job 100 --seed 7
```

Signal 处理一个 Geant4 事件。TCT 计算激光产生的载流子组。Timeres 处理 100 个 Geant4 事件并写入时间分析。

## 🌳 在工作树间共享环境

本地 SIF 镜像及 conda/venv 目录是被忽略的运行时资产。将工作树链接至主检出中的共享资产：

```bash
cd .worktrees/<name>
ln -s ../../img img
ln -s ../../.conda .conda
ln -s ../../.venv .venv
```

从工作树根目录运行激活命令，使路径指向相应源码树，同时共享大型运行时资产。

## 📌 依赖策略

RASER 按策略省略 `uv.lock`。直接 Python 依赖保留在 `pyproject.toml` 中；精简且固定版本的 `env/uv.txt` 定义部署的 Python 包，供原生与 SIF 路径使用。Conda YAML 与显式规格文件定义编译依赖。生成 `uv.lock` 需要明确调整相应策略。
