<p align="right"><b>中文</b> · <a href="README.md">English</a></p>

![Optics · Photonics — 软件、物理模型与可编程接口](docs/assets/readme-header.webp)

# 光学与光子学研究环境

研究者和 Agent 可以把它作为 Python 包、MCP 服务、插件或 Skills 安装。它从 110 项软件的目录中选择工具，涵盖建模、仿真、计算和实验仪器，按每个软件提供的通路连接它（Python 模块、独占会话、软件自己的可执行程序和语言、Windows 自动化服务、在线服务），在各软件自己的环境中运行完整的原生研究程序，Agent 断开后长计算继续运行，结果以科学数据文件保存，可以按需读取其中一部分。统一物理基础：**场 + 物质 + 相互作用**。

| 阅读与浏览 | 数据与资料 | 参与开发 |
| --- | --- | --- |
| [中文 HTML](https://cherish0925.github.io/Optics-Photonics-AI-Lab/index.zh.html) · [English HTML](https://cherish0925.github.io/Optics-Photonics-AI-Lab/) | [中文 JSON](data/catalogue.zh.json) · [English JSON](data/catalogue.en.json) | [Agent 入口](llms.txt) · [贡献说明](CONTRIBUTING.md) |
| [中文 Markdown](docs/catalogue.zh.md) · [English Markdown](docs/catalogue.en.md) | [资料索引](data/resources.zh.json) · [数据结构](data/schema.json) | [代码示例](examples/) · [本地开发](#本地开发) |
| [基础框架](docs/foundations.zh.html) · [Foundations](docs/foundations.html) | [中文源文件](foundations/README.zh-CN.md) | [运行机制](docs/EXECUTION.md) · [原生软件](docs/NATIVE.zh-CN.md) |

[中文](https://raw.githubusercontent.com/Cherish0925/Optics-Photonics-AI-Lab/main/docs/index.zh.html)和[英文](https://raw.githubusercontent.com/Cherish0925/Optics-Photonics-AI-Lab/main/docs/index.html) HTML 是独立文件，下载后可离线打开。[完整软件目录](https://cherish0925.github.io/Optics-Photonics-AI-Lab/catalogue.zh.html)提供并排比较和 CSV/JSON 导出。

## 安装

| 宿主 | 安装方式 |
| --- | --- |
| Agentic Research OS | 下载 [Research OS 插件包](https://github.com/Cherish0925/Optics-Photonics-AI-Lab/releases/download/optics-v0.8.0/Optics-Photonics-0.8.0-ResearchOS.zip)，解压后安装包含 `plugin.json` 的目录；包内有六种系统与架构的原生执行程序、MCP、软件目录和两个 Skills，使用宿主自带的 Python。也可以在 **Extensions → Plugins → Add from link** 填入 `https://github.com/Cherish0925/Optics-Photonics-AI-Lab/tree/main/connect/agentic-research-os`。 |
| Codex | `codex plugin marketplace add Cherish0925/Optics-Photonics-AI-Lab`，再 `codex plugin add optics-photonics@optics-photonics` |
| Claude Code | `claude plugin marketplace add Cherish0925/Optics-Photonics-AI-Lab`，再 `claude plugin install optics-photonics@optics-photonics` |
| Qiushi | 基于 Research OS 的版本使用上面的插件包；其他版本用 `optics-photonics connect qiushi` 生成 MCP 或命令入口。 |
| DeepSeek Harness | 项目索引 `https://raw.githubusercontent.com/Cherish0925/Optics-Photonics-AI-Lab/main/docs/dsh/index.json`；指定解释器时运行 `optics-photonics connect deepseek`。 |
| 其他 MCP 宿主、Python、命令行 | 安装下面的 wheel，把 `optics-photonics mcp` 注册为 stdio 服务。 |

```sh
python -m pip install "https://github.com/Cherish0925/Optics-Photonics-AI-Lab/releases/download/optics-v0.8.0/optics_photonics-0.8.0-py3-none-any.whl"
optics-photonics prepare tmm
optics-photonics connect agentic-research-os --output optics-plugin
```

连接程序需要 Python 3.10+，支持 Windows、macOS 和 Linux，不依赖第三方库。GitHub 插件市场版本通过 [uv](https://docs.astral.sh/uv/getting-started/installation/) 选择执行端的 Python 3.10+，缺少时自动下载。先安装一次 uv；已有 Python 时也可以用 `optics-photonics connect HOST --python /path/to/python` 生成宿主包。Research OS 使用自带 Python。各科学软件保留自己的 Python、平台和许可。MCP 服务应运行在装有科学软件的机器上，本地或通过 SSH 均可。[接入说明](docs/CONNECT.zh-CN.md) · [交互指南](https://cherish0925.github.io/Optics-Photonics-AI-Lab/connect.zh.html) · [发布包](https://github.com/Cherish0925/Optics-Photonics-AI-Lab/releases)

### 第一个计算

```sh
optics-photonics search "Bragg mirror"
optics-photonics submit tmm spectrum --wait 25 --inputs '{"n": [1, 2.35, 1.46, 2.35, 1.46, 2.35, 1.46, 2.35, 1.46, 2.35, 1.46, 1.52], "thickness_nm": [63.83, 102.74, 63.83, 102.74, 63.83, 102.74, 63.83, 102.74, 63.83, 102.74], "wavelength_nm": {"start": 450, "stop": 800, "points": 351}}'
optics-photonics array RUN_ID calculate/attempt-1/spectrum.npz --member R --image R.png
```

搜索给出软件 `tmm` 和它的封装程序 `spectrum`。提交时第一次会把 tmm 装进它自己的环境，然后计算按 600 nm 设计的五对四分之一波长膜的反射率（600 nm 处 97.8 %），在等待时间内返回结果；若返回 `running`，用 `optics-photonics status RUN_ID --wait 25` 继续等。最后一条命令把反射率随波长画成图。智能体通过 MCP 做同样的事：`software_search`、`submit_calculation(tool, action, inputs, wait)`、`read_array(image="auto")`。

## 一次计算怎么进行

1. **选软件。** `software_search` 按物理问题查找软件和封装程序，中英文皆可，光学概念的同义词与缩写互相匹配（[词表](data/vocabulary.json)）。`software_details` 给出一项软件的物理方法、接口、通路、安装方式和封装程序；目录之外的工具用 `register_software` 加入。
2. **连接软件。** 69 项软件带安装配方，各装进自己的环境：第一次提交时自动安装，也可用 `prepare_environment` 提前安装；`bind_environment` 复用已有解释器。本机已安装的软件由 `discover_native_software` 查找（PATH、常用安装目录、`JCMROOT` 等环境变量、Windows 注册表），由 `bind_native_software` 按下表中的一种通路连接（[本机软件](docs/NATIVE.zh-CN.md)）。
3. **使用实测材料数据。** `materials` 给出 refractiveindex.info 数据库 3576 页（CC0）的 n、k 和文献，带 `dispersion` 时还给出群折射率、群速度色散和色散参数 D；SiO2、Si、Au、N-BK7、BBO 等常用名称离线可用，其他页面首次使用时下载。
4. **运行封装程序或自己写程序。** 下表的 56 个封装程序都写明输入，并给出与守恒律、解析极限或另一求解器的对照；可以直接运行，也可以取出源码修改（[程序说明](skills/optical-computation/references/programs.md)）。自己写的程序接收 `INPUTS` 和 `OUTPUT_DIR`，使用软件完整的原生 API，设置 `RESULT`：Python 的 `source`，用本机软件自身语言写的 `script`，或用 `RUN` 调用本机可执行程序的 Python 程序。
5. **参数研究与多步计算。** `submit_calculation` 立即返回运行编号，带 `wait` 时还返回在等待时间内完成的计算结果。`sweep` 并行计算输入取值的所有组合，`sweep_results` 汇总成表并给出最优点；`optimize` 在给定范围内搜索最优输入（[参数研究](skills/optical-computation/references/studies.md)）。`submit_workflow` 把多个步骤连起来，后一步接收前一步的数值和文件。`data.save` 把数组连同单位、坐标轴和约定一起保存，下一个程序和 `read_array` 都能知道这些数的物理含义（[数据说明](docs/EXECUTION.md#keep-the-meaning-of-arrays-between-programs)）。
6. **继续与取回结果。** `run_status` 每次最多等待 25 秒，等待期间其他请求照常返回。运行不随连接断开而停止，用 `list_runs` 重新找到；`resume_run` 重跑未完成步骤，保留已完成步骤。`result_files`、`read_result`、`read_array` 分别返回文件列表、字节片段和 NPY/NPZ 数组的局部；`read_array` 加 `image` 时把所选部分画成曲线或带色标的二维图，标出坐标和单位。
7. **采集 episode。** `sample_episodes` 在并行的软件进程中运行 Gymnasium 形式的环境，保存种子、动作、观测和奖励，供学习使用；中断或追加的采集会接着进行，不重复已完成的 episode（[接口说明](docs/LEARNING.md)）。

| 通路 | 软件 | 运行什么 |
| --- | --- | --- |
| python | 77 项：配方安装的模块（pip 由 uv 安装、conda-forge、Julia 包管理器），或随软件安装的模块（JCMsuite、Photon Design） | Python `source` |
| session | COMSOL、Lumerical、OpticStudio、CST | 持有独占会话的 Python 程序 |
| executable | MATLAB、GNU Octave、Julia、Mathematica、Maple、QuantumOptics.jl、Luna.jl、S4、COMSOL、Lumerical、CST、ADDA、MCX、MMC、pbrt | 用软件自身语言写的 `script`；用 `RUN` 调用它的 Python 程序 |
| automation | FRED、CODE V、LightTools、OptiLayer、LabVIEW（Windows） | 以 `APP` 持有该服务的 Python 程序 |
| service | Tidy3D 云端、Speos 服务、FIMMWAVE | 服务的 Python 客户端 |
| inside | 17 项只能在自身界面中运行脚本的软件 | 为它写入文件、读取它导出的文件 |

| 方向 | 封装程序 |
| --- | --- |
| 薄膜、光栅、超表面 | `tmm/spectrum` · `grcwa/film` · `grcwa/grating` · `grcwa/metasurface` · `scipy/metalens` |
| 电磁场与逆向设计 | `meep/stack` · `meep/ring` · `ngsolve/scattering` · `ceviche/bend` |
| 光子晶体 | `mpb/bands` · `legume/bands` · `s4/crystal_slab` |
| 波导、光子回路、版图 | `mpb/waveguide` · `tidy3d/modes` · `scipy/slab_modes` · `scipy/coupler` · `sax/circuit` · `gdsfactory/waveguide` · `klayout/layout` |
| 光纤与光通信 | `scipy/fiber_modes` · `scipy/nlse` · `laserfun/supercontinuum` · `octave/bragg_grating` · `opticomm/ber` |
| 激光器、谐振腔、非线性光学 | `scipy/resonator` · `scipy/laser_rates` · `finesse/cavity` · `scipy/second_harmonic` |
| 散射 | `miepython/sphere` · `treams/cluster` · `adda/particle` |
| 成像与光束 | `hcipy/psf` · `poppy/psf` · `prysm/mtf` · `lightpipes/gaussian` · `diffractio/apertures` · `scikitimage/registration` |
| 镜头、光线、偏振 | `optiland/lens` · `optiland/trace` · `raytracing/abcd` · `sympy/abcd` · `sympy/fresnel` · `py-pol/polarization` |
| 量子光学 | `qutip/rabi` · `qutip/jaynes_cummings` · `qutip/resonance_fluorescence` · `quantumoptics/jaynes_cummings` · `perceval/interference` · `strawberry/gaussian_state` |
| 生物组织、X 射线、光伏、数据 | `scipy/tissue_layers` · `srw/undulator` · `solcore/detailed_balance` · `scipy/fit_gaussian` |
| 实验仪器与全息图 | `pyvisa/sweep` · `bluesky/scan` · `slmsuite/spot_array` |

同样的操作也有 `optics-photonics` 命令、Python 接口和 TypeScript 客户端；MCP 宿主还会得到六个提示（calculate、study、reproduce、connect、measure、continue），各篇指南也作为资源提供。每个封装程序都已运行并与其参照结果对照：Meep 和 MPB 的程序在 conda-forge 环境中运行，Octave、Julia、Lua 的程序在真实软件中运行。有三部分还有待在有许可证的软件或真实硬件上运行：四个商业软件的会话适配器（已用 SDK 替身运行），MATLAB、Wolfram Language、Maple 和 Lumerical 脚本的桥接（按厂商文档中的命令编写），仪器程序（已在模拟设备上运行）。

## 运行机制

Rust 执行器管理求解进程、取消和超时。Python 连接科学 SDK 并组织任务。SQLite 保存运行记录，并按本机所有运行共享的 CPU 和命名额度（GPU、软件许可证等）安排步骤。TypeScript 客户端连接 Agent 宿主。MPI 进程数、GPU 选择和集群队列仍在各软件自己的启动配置中设置。[运行机制与资源](docs/EXECUTION.md)

## 统一物理基础

> **光学 / 光子学 = 场 + 物质 + 相互作用**

**场**指经典或量子化的电磁场及其状态；**物质**包括微观自由度、材料、器件和探测器；**相互作用**是二者之间能量、动量和信息的交换。自由传播是场的动力学，光学器件是结构化的物质，测量是设计好的场与物质相互作用。软件目录和 Skills 按这一框架组织，覆盖几何光学、波动光学、纳米光子学、光纤、激光、成像、光谱和量子光学，并保留各有效理论的适用边界。[基础框架](docs/foundations.zh.html) · [Markdown 源文件](foundations/)

## 软件目录

- **30 项商业软件**、**77 项开源软件**、**3 项免费但有限制**，分属 15 个领域，从几何光学到实验仪器。免费客户端、收费求解器、学术许可和外部 PDK 分别说明。
- 每项记录物理方法、用途、编程接口、运行环境、许可、应用依据、适用边界和原始资料。资料核对日期 **2026-10-20**。
- API、命令行和宏与**官方 / 社区 / 未核实**的 MCP 服务、Agent Skills 分开标注。文档检索类 MCP 不当作求解器接口。
- 中英文使用同一套稳定编号 `id`。Agent 先读 [`llms.txt`](llms.txt)，再读 [`llms-full.txt`](llms-full.txt) 或 JSON。

不同模型之间通过它们传递的物理量连接：

| 任务链 | 模型之间传递什么 | 目录中的工具示例 |
| --- | --- | --- |
| 镜头 → 图像 → 反演 | 瞳面复场、像差、PSF、采样与探测器响应 | OpticStudio、CODE V、Optiland、prysm、POPPY |
| 单胞 → 超表面 → 系统 | 复数透反射、偏振、角度和波长依赖 | torcwa、grcwa、Meep、Lumerical、Tidy3D、Diffractio |
| 版图 → 器件 → 电路 | 工艺层、端口、参考平面和归一化 S 参数 | gdsfactory、KLayout、IPKISS、JCMsuite、SAX |
| 脉冲 → 链路 → 接收 | 复包络、时间网格、色散、非线性与噪声 | Luna、py-fmas、RP Fiber Power、VPI、OptiCommPy |
| 光机热 → 腔模 → 读出 | 热致形变、折射率变化、工作点和噪声谱 | COMSOL、Finesse、HCIPy |
| 样品 → 传播 → 重建 | 实际观测量及其前向算子 | MCX、MMC、PyNX、pyDHM、HoloPy |
| 模型 → 仪器 → 数据 | 发出的设置、带时间的原始读数、定标与不确定度 | PyVISA、pylablib、Bluesky、python-seabreeze、LabVIEW |

每一处连接都要统一单位、参考系、场的约定和模型近似。

## 本地开发

```bash
git clone https://github.com/Cherish0925/Optics-Photonics-AI-Lab.git
cd Optics-Photonics-AI-Lab
python -m pip install -e ".[rl]"
python -m unittest discover -s tests
python scripts/build.py
python scripts/package_marketplace.py
```

`build.py` 根据 `data/` 重新生成 HTML、Markdown、资料索引和 Agent 文档；修改源码或 Skills 后，`package_marketplace.py` 重新生成内置的 Research OS 副本。生成的文件随仓库提交。设置 `OPTICS_SCIENCE_TESTS=1` 会运行调用科学软件库的用例。

| 路径 | 内容 |
| --- | --- |
| `src/optics_photonics/` | 连接程序：软件目录、环境、执行、任务、结果数组、episode 采样、MCP、命令行 |
| `native/executor/` | Rust 进程执行器 |
| `clients/typescript/` | 供 Agent 宿主使用的 TypeScript 客户端 |
| `skills/` | Agent Skills 与领域参考资料 |
| `connect/` | 生成的宿主接入包 |
| `data/` | 中英文软件目录、连接方式、领域和数据结构 |
| `src/render.py`、`scripts/build.py` | 网页与文档生成 |
| `examples/` | 原生程序、软件会话和 episode 示例 |
| `foundations/` | 场 · 物质 · 相互作用框架 |
| `AGENTS.md` | 修改本仓库时的结构说明、常用命令与约定 |

## 许可

本项目原创代码与目录说明采用 [MIT](LICENSE) 许可。被收录软件、外部文档、PDK 和数据遵循各自许可；内嵌字体采用 [SIL OFL 1.1](docs/assets/FONT_LICENSE.txt)。详见 [NOTICE](NOTICE)。仓库改名后，软件包名、命令、插件 ID 和本地计算环境保持不变。
