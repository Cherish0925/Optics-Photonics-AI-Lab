# Optics-Photonics-AI-Lab 0.9.0

The environment now describes 99 software tools, with 59 installation recipes and 48 inspectable programs across 32 software libraries. GNU Octave and Julia join the catalogue. The Field + Matter + Interaction framework, package names, existing bindings and run records remain the foundation of the environment.

Installed executables and Windows automation servers now join the existing Python and owned-session connections. Programs can run in MATLAB, Octave, Julia, Wolfram Language, Maple, Lua or Lumerical script; Python drivers can invoke a bound executable with `RUN`. These routes use the existing worker, persistent scheduler, shared CPU and license resources, sweeps, optimization and result files. Service clients reuse Python bindings. A route labelled `inside` describes scripts or file exchange within the application, rather than an unattended connection. Discovery reports installations and credential presence without starting the software or verifying service access.

Three new programs cover ADDA particle scattering, S4 photonic-crystal slab spectra and QuantumOptics.jl atom–cavity dynamics. Their source, inputs, physical assumptions and comparison quantities are available through the same program interface. Julia package installation and conda cache updates are serialized, and native-language results can save arrays with units and axes in the established NPZ/JSON format.

Integration preserves positional Python sweep calls and named program provenance. Lua inputs and outputs retain nulls, empty objects, sparse arrays and embedded null characters; unequal array rows are rejected before saving. Lumerical results unwrap the named workspace variable written by `jsonsave`. Workflow files accept long inline scripts, the TypeScript client exposes the script-language binding, and the uncoupled resonant Jaynes–Cummings limit returns its constant exact population. The bilingual entry points now give a shorter route from installation to a first calculation and distinguish catalogue coverage from local execution. MCP program details return source text only with `source=true`; Python and CLI source access remain compatible. Tool annotations describe actual execution and configuration effects, including queued-worker recovery through `run_status`.

Validation: 199 Python tests completed with scientific calculations enabled: 178 passed and 21 were skipped for separate solver installations. The Lua bridge ran against the host's Lua 5.4 shared runtime; the Lumerical serialization check uses the documented output format, and commercial session lifecycle tests use SDK doubles. All 6 TypeScript tests passed. After the final MCP context changes, 43 focused checks completed (38 passed, 5 separate-software skips), and the 24 tool definitions validated against the MCP SDK and JSON Schema. Independent MCP calculation, disconnection, reconnection and file transfer passed; the catalogue and Research OS package regenerate consistently, and the 0.9.0 wheel and source archive build successfully. Julia, Octave, S4 and ADDA were not installed for this integration run. Repository CI retains the Windows/macOS, Python-minimum and six-platform native executor checks before publishing versioned release bundles.

## 中文

目录现有 99 项软件、59 份安装配方，以及 32 套软件中的 48 个可读、可修改程序；新增 GNU Octave 与 Julia。继续以场 + 物质 + 相互作用为物理框架，沿用软件包名称、已有环境绑定与运行记录。

在原有 Python 与独占会话连接基础上，增加本机可执行程序和 Windows 自动化服务。程序可使用 MATLAB、Octave、Julia、Wolfram Language、Maple、Lua 或 Lumerical 脚本；Python 程序可用 `RUN` 调用绑定的可执行程序。这些通路复用现有工作进程、持久任务调度、共享 CPU 与许可证额度、扫描、优化和结果文件接口。服务客户端复用 Python 绑定；`inside` 表示在软件内部运行脚本或交换文件，不表示已实现无人值守连接。发现过程读取安装位置及凭据是否存在，不启动软件，也不据此判定服务已经联通。

新增 ADDA 颗粒散射、S4 光子晶体平板光谱和 QuantumOptics.jl 原子–腔动力学程序，沿用同一套源码、输入、物理假设及对照量接口。Julia 包安装与 conda 缓存更新分别串行处理；其他语言的计算结果可按既有 NPZ/JSON 形式保存带单位、坐标轴的科学数组。

整合修复保留 Python 扫描的原位置参数及封装程序名称；Lua 往返保留空值、空对象、稀疏数组和内嵌空字符，不等长数组在保存前报错；Lumerical 的 `jsonsave` 输出按统一契约取出 `RESULT`。工作流支持长单行脚本，TypeScript 客户端可指定脚本语言，零耦合且零失谐的 Jaynes–Cummings 解析结果保持恒定。中英文入口缩短安装与首次计算路径，明确区分目录覆盖和本机执行能力。MCP 程序详情仅在 `source=true` 时展开源码，Python 与命令行源码访问保持兼容；工具注解按实际执行及配置修改行为标注，包括 `run_status` 对排队工作进程的恢复。

启用科学计算后共完成 199 项 Python 测试，178 项通过，21 项因需要独立求解器环境而跳过。Lua 桥接使用宿主 Lua 5.4 共享运行库执行；Lumerical 序列化采用厂商文档格式检验，商业会话生命周期采用 SDK 替身。6 项 TypeScript 测试全部通过。最后的 MCP 上下文调整另完成 43 项定向检查（38 项通过、5 项独立软件测试跳过），24 项工具定义通过 MCP SDK 与 JSON Schema 验证；独立 MCP 计算、断线续算、重连和文件传输通过；目录、Research OS 包可一致再生成，0.9.0 wheel 与源码包构建成功。本轮未安装 Julia、Octave、S4 和 ADDA；仓库 CI 继续在发布前执行 Windows/macOS、最低 Python 版本及六平台原生执行器检查。
