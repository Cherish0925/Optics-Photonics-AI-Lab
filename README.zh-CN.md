<p align="right"><b>中文</b> · <a href="README.md">English</a></p>

![Optics · Photonics](docs/assets/readme-header.webp)

# Optics-Photonics AI Lab

面向光学研究的开源环境：物理方法、可编辑程序、求解器连接与持续计算。按研究任务选择模块，在计算主机上准备所需软件，再使用对应的方法和示例。

[开始任务](skills/optical-computation/references/start.md) · [安装与连接](docs/CONNECT.zh-CN.md) · [下载](https://github.com/EnvFoundry/Optics-Photonics-AI-Lab/releases) · [Agent 入口](llms.txt)

## 按任务选择模块

产品目录包含 **27 个研究任务模块、34 项开源软件组件**，另有独立的软件视图，包含全部 **77 项开源软件**，分为四个研究领域和共用的光学基础。多个模块共用软件，例如两个模块需要 SciPy 时，只准备一套 SciPy 环境。

| 领域 | 方向 | 任务示例 |
| --- | --- | --- |
| 光学系统 | 几何光学、波动光学、成像 | 镜头设计、衍射、偏振、成像 |
| 光子结构与器件 | 电磁、周期结构、薄膜、光子电路 | FDTD、能带、镀膜、波导、版图 |
| 光与物质 | 光纤、激光、散射、量子光学、组织光学、X射线 | 脉冲传播、谐振腔、光子输运、量子动力学 |
| 光学测量 | 实验室采集 | 仪器读数、全息图、实测光谱 |
| 光学基础 | 符号与数值模型 | 光线矩阵、界面关系 |

每个模块关联软件、领域方法与可编辑程序。[模块源数据](data/modules.json) · [产品目录](data/environment-catalogue.json)。

另有涵盖 110 项软件的[软件参考目录](docs/catalogue.zh.md)，其中包括商业软件。这是资料目录，**不是默认安装列表**。商业软件为可选接入，需要用户已有安装、许可和受支持的操作系统；环境不附带商业软件本体。

## 安装与计算

连接器需要 Python 3.10+，无第三方依赖；求解器单独安装。

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install "https://github.com/EnvFoundry/Optics-Photonics-AI-Lab/releases/download/optics-v0.11.3/optics_photonics-0.11.3-py3-none-any.whl"
optics-photonics prepare tmm
optics-photonics run tmm spectrum
```

选择多个模块：`optics-photonics plan thin-film-spectra waveguide-modes` 查看当前主机上的准备方式，然后 `optics-photonics prepare-modules thin-film-spectra waveguide-modes` 开始。返回的任务号可通过 `optics-photonics status RUN_ID --wait 25` 查询。已有解释器用 `bind --python PATH` 连接；`installed` 查看准备情况；`uninstall MODULE...` 移除所选的闲置软件，共用安装与研究文件保留。

**Research OS / Origo：** 导入[发布页](https://github.com/EnvFoundry/Optics-Photonics-AI-Lab/releases)的 ResearchOS ZIP，或添加 `https://github.com/EnvFoundry/Optics-Photonics-AI-Lab/tree/main/connect/agentic-research-os`。在计算主机上启用，选择任务模块，再准备所需软件。包内包含连接器、目录与 Skills，不会下载全部求解器。

**其他 Agent：** `optics-photonics connect HOST --output DIR` 生成 Codex、Claude、DeepSeek、Qiushi、通用插件或 MCP 配置；MCP 主机也可直接启动 `optics-photonics mcp`。[连接说明](docs/CONNECT.zh-CN.md)。

## 软件、知识与结果

| 内容 | 位置 |
| --- | --- |
| 研究任务及其软件 | `data/modules.json`；生成的 `data/environment-catalogue.json` |
| 安装配方与外部接口 | `data/connections.json`；[原生软件](docs/NATIVE.zh-CN.md) |
| 模型选择、假设与领域知识 | [Optical research](skills/optical-research/SKILL.md)，按需读取 15 份方向参考 |
| 执行、工作流、数据与续算 | [Optical computation](skills/optical-computation/SKILL.md) |
| 可编辑计算程序 | `src/optics_photonics/programs/`；[程序参考](skills/optical-computation/references/programs.md) |
| MCP、CLI、Python、TypeScript | `src/optics_photonics/`；`clients/typescript/` |
| 宿主包 | 生成的 `connect/`，不另写一套实现 |
| 物理框架 | [场、物质与相互作用](foundations/README.md) |

MCP 提供 calculate、study、reproduce、connect、measure、continue 六个任务提示。Agent 只读相关指南与程序，无需把整个软件目录装入上下文。

计算在安装求解器的主机上运行。网页产品连接该主机；Windows 软件仍需 Windows 主机。配方分别说明平台与 Python 要求，驱动、GPU、许可遵循所选软件的要求。持久主机上的后台计算可在客户端断连后继续，结果保留数组、单位、坐标及续算文件。

## 与其他环境组合

通过绑定复用 SeedEnv 的合适解释器；共享仪器使用 IOP 已有控制器。通过各自接口与 Synthetic-Lab、Data Engineering、Agent Gym、AI Evaluation 交换测量、数组和轨迹。每个环境管理自身运行时与状态，安装本插件不替换其他环境。

连接配置与运行记录使用 `OPTICS_HOME`，默认 `~/.optics-photonics`。软件使用 `OPTICS_SOFTWARE_HOME` 指定的目录，否则使用 `OPTICS_HOME/environments`。Research OS 将新软件放在 `System/software/optics-photonics`，状态仍保存在原有位置。已有安装继续复用；更新插件保留软件与研究记录。

## 开发

```sh
git clone https://github.com/EnvFoundry/Optics-Photonics-AI-Lab.git
cd Optics-Photonics-AI-Lab
python -m pip install -e .
python -m unittest discover -s tests
python scripts/build.py
python scripts/package_marketplace.py
```

参见 [AGENTS.md](AGENTS.md) 和[开发说明](docs/DEVELOPMENT.zh-CN.md)。生成文件随仓库发布，修改其源文件后重新生成。原创代码与说明采用 [MIT](LICENSE)，引用软件与数据保留各自许可。[NOTICE](NOTICE)。
