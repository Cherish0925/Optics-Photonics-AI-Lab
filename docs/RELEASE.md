# Optics-Photonics-AI-Lab 0.8.0

This release integrates the 26 research-program contributions without rewriting their history. It ships 45 inspectable programs across 29 software libraries, spanning films, scattering, imaging, cavities, fiber propagation, nonlinear and quantum optics, photonic circuits, and inverse design. Each program exposes its source, inputs, physical assumptions, outputs and checks; custom programs retain the complete upstream API. The catalogue still distinguishes its 97 entries from installed or tested capabilities.

Environment recipes prepare supported Python or conda tools on demand. Parameter sweeps, bounded optimization, short calculation waits and result tables share the existing persistent scheduler. Python and commercial SDK sweep groups preserve every point's inputs and project ownership; external command programs receive one complete request per point. Retried submissions return their original result, including after later appends. Existing runs, bindings and the 0.7 operation discovery interfaces are retained.

The 24 MCP tools include material lookup and sweep results. The pinned refractiveindex.info catalogue provides refractive index, extinction coefficient, group index and dispersion; common materials are bundled and concurrent downloads use independent temporary files. Described arrays can be rendered as PNG lines or maps, including complex components, with matching coordinates. Search recognizes scientific concepts in both languages and returns individual program details on request.

Integration fixes enforce optimization budgets and integer bounds, preserve signed two-axis ray fields, align fiber propagation and spectrum frequency conventions, represent unbounded characteristic lengths and balanced-interferometer periods as JSON null, and support tight metalens windows and complete optical loss. Multi-program examples pass unit-cell libraries into metalens propagation and waveguide modes into circuit calculations.

Validation: 178 Python tests completed successfully (165 passed, 13 separate-environment skips); all 5 TypeScript tests passed. These cover Linux scientific calculations, real Rust process execution, SDK test doubles and MCP reconnect/file-transfer paths. A wheel upgrade from 0.7.0 to 0.8.0 retained the previous run and solver binding. Software needing separate environments, licensed workstations and live Research OS, Qiushi or DeepSeek hosts is not claimed as newly exercised. The Windows/macOS and six-architecture executor checks run in repository CI before release publication. Downloads include the Python wheel/source archive, TypeScript package and ResearchOS, Connect, Codex, Claude and Portable bundles; the connector requires Python 3.10+, while supported solver workers can use Python 3.9+.

## 中文

本次完整保留并整合 26 个贡献提交，提供 29 套软件中的 45 个可读、可修改科研程序，覆盖薄膜、散射、成像、谐振腔、光纤传播、非线性与量子光学、光子电路和逆向设计。每个程序声明物理假设、输入、输出和检查；自定义程序继续使用软件完整原生 API。目录中的 97 个条目不代表全部已安装或经过实机验证。

支持按需准备 Python/conda 环境、参数扫描、有界优化、短任务直接返回和结果表格。扫描保留各点的完整输入与工程文件；商业 SDK 每点独立管理会话，外部命令每点接收完整请求。追加任务后重试同一请求仍返回原计算结果，已有运行记录、环境绑定和 0.7 版本的 operations 发现接口继续可用。

24 个 MCP 工具包含材料查询和扫描结果读取。材料模块使用固定版本数据库，常用数据离线附带，支持折射率、消光系数、群折射率和色散；并行下载互不覆盖。科学数组保留单位与坐标，可直接生成曲线或二维 PNG，支持复数分量。中英文搜索支持物理概念，并可按需读取单个程序的原理和源码。

修正优化超预算、整数越界、光线角度符号与分量、光纤三阶色散和频率坐标、零色散或零非线性结果序列化、平衡干涉仪、超透镜紧窗口及完全损耗边界。178 项 Python 测试完成，其中 165 项通过、13 项专用环境测试按条件跳过；5 项 TypeScript 测试全部通过，并验证 wheel 从 0.7.0 升级到 0.8.0 后旧任务和环境绑定保留。测试覆盖 Linux 科学计算、Rust 真实进程、SDK 替身和 MCP 断线重连；专用软件环境、商业授权工作站及具体宿主的实机验证仍按各自条件进行。跨平台 CI 通过后才发布发行包。
