# 本机软件

环境通过一种或几种“通路”连接目录中的每个软件。通路说明环境掌握软件的哪一部分、计算怎样使用它：

| 通路 | 环境掌握的部分 | 计算的用法 |
| --- | --- | --- |
| python | 能导入软件模块的解释器，模块来自安装配方，或随软件安装 | Python 程序（`source`）或封装程序（`action`） |
| session | 由单个任务独占的 COMSOL、Lumerical、OpticStudio、CST 会话 | `inspect_project`、`solve_project`，或基于完整原生 API 的程序 |
| executable | 软件自己的可执行程序 | 用软件自身语言写的程序（`script`），或用 `RUN` 调用它的 Python 程序 |
| automation | Windows 自动化（COM）服务 | 以 `APP` 持有该服务的 Python 程序 |
| service | 连接正在运行的软件、服务器或云的客户端 | 使用该客户端的 Python 程序 |
| inside | 无：软件只在自己的界面里运行脚本 | 程序写出它的输入文件，读取它导出的文件 |

`software_details(tool)` 列出一个软件的通路；[下表](#全部软件的通路)列出全部软件。

## 查找与连接

```sh
optics-photonics discover                       # 所有通路：PATH、常用安装目录、环境变量、Windows 注册表
optics-photonics discover --tool matlab --root /software
optics-photonics bind-native matlab --executable /usr/local/MATLAB/R2025b/bin/matlab
optics-photonics bind-native jcm --route python --python /path/to/python --sdk-path "$JCMROOT/ThirdPartySupport/Python"
optics-photonics bind-native fred --progid FRED.Application --python C:/Python312/python.exe
optics-photonics bind-native lumerical --python /path/to/python --sdk-path /opt/lumerical/v252/api/python --threads 4
optics-photonics prepare octave                 # Linux 与 Apple 芯片上从 conda-forge 安装；Julia、QuantumOptics.jl、Luna.jl 同理
```

查找读取 PATH、安装程序通常使用的目录、指向安装位置的环境变量（`JCMROOT`）、`--root` 给出的目录，以及 Windows 上已注册的自动化服务；不启动任何软件，不占用许可。找到的每个安装都附带 `bind-native` 的参数；不给 `--executable`、`--progid` 或 `--sdk-path` 时，`bind-native` 使用查找到的第一个安装。MCP 对应工具是 `discover_native_software` 和 `bind_native_software`。连接保存 `threads`、`concurrency`、资源需求和环境变量；已提交的任务沿用提交时的连接。需要许可的软件先用并发数 1。

## 用软件自身语言写的程序

```sh
optics-photonics submit matlab --script mode_solver.m --inputs '{"wavelength_um": 1.55}' --wait 25
optics-photonics submit octave --script mode_solver.m --sweep '{"wavelength_um": {"start": 1.5, "stop": 1.6, "points": 11}}'
```

| 语言 | 软件 | INPUTS | 输出目录 | 命令 |
| --- | --- | --- | --- | --- |
| matlab | MATLAB R2019a 及以后 | struct（jsondecode） | `OUTPUT_DIR` | `matlab -sd FOLDER -batch optics_main` |
| octave | GNU Octave 7 及以后 | struct（jsondecode） | `OUTPUT_DIR` | `octave-cli --no-gui --quiet --norc --no-window-system optics_main.m` |
| julia | Julia；QuantumOptics.jl、Luna.jl | `Dict{String,Any}` | `OUTPUT_DIR` | `julia --project=ENV --threads=N optics_main.jl` |
| wolfram | Mathematica、Wolfram Engine | Association | `OUTPUTDIR` | `wolframscript -file optics_main.wls` |
| maple | Maple 2015 及以后 | table | `OUTPUT_DIR` | `maple -q optics_main.mpl`（Windows 上为 `cmaple`） |
| lua | S4 | table | `OUTPUT_DIR` | `S4 optics_main.lua` |
| lsf | Lumerical 设计环境 | 每个输入一个变量 | `OUTPUT_DIR` | `fdtd-solutions -nw -trust-script -exit -run optics_main.lsf` |

目录之外的软件用 `register-software` 登记为命令后，在连接时指定语言（`bind-native TOOL --executable PATH --language julia`）。工作进程把程序保存为带该语言后缀的 `optics_program`，并用同一语言写一个简短的 `optics_main`：定义 INPUTS 和输出目录，运行程序，把 RESULT 写成 JSON。可执行程序在本次计算（扫描时为每个点）的输出目录中运行，输出写入 `script.log`。RESULT 可含数值、字符串、列表和对象；复数场和大数组存为同目录下的文件。参数扫描、优化和工作流的结果引用与 Python 程序相同。Octave、Julia、Lua 的桥接（以及经 Octave 走过的 MATLAB 代码路径）已在本开发环境用真实解释器运行；MATLAB、Wolfram Language、Maple 和 Lumerical 脚本的桥接按厂商文档中的命令与函数编写，需要有许可的软件才能运行。

## 调用可执行程序的 Python 程序

绑定到可执行程序的软件，其 Python 程序获得 `EXECUTABLE`、`SIBLINGS`、`THREADS` 和 `RUN(*arguments, program=None, cwd=None, input=None, timeout=None, check=True, log=None)`。`RUN` 在输出目录中运行该可执行程序，或名为 `program` 的同目录程序；输出写入日志文件，退出码非零时报错并附日志末尾。程序随后读取软件写出的文件，按单位和坐标轴保存数组。

```python
from pathlib import Path
# COMSOL：Linux 与 macOS 上是 comsol batch，Windows 上是 comsolbatch。
RUN(*(['batch'] if Path(EXECUTABLE).stem == 'comsol' else []), '-inputfile', INPUTS['model'],
    '-outputfile', OUTPUT_DIR / 'solved.mph', '-study', 'std1', '-pname', 'wl', '-plist', '1.5[um],1.55[um]')
RESULT = {'model': 'solved.mph'}
```

Lumerical 用 `RUN('-t', THREADS, model, program='fdtd-engine')` 求解保存好的项目；CST 用 `RUN('-m', '-r', project)`。封装程序 `adda/particle` 调用 ADDA 计算球或椭球，并把球的结果与精确级数比较。用源码编译的 ADDA 运行时，偶极子越细越接近精确解：尺寸参数 5、折射率 1.5 的球，粒子内每波长 8、15（默认）、30 个偶极子时，消光效率相差 1.0 %、0.26 %、0.11 %。金球收敛很慢，这是偶极子近似处理金属时的已知行为。

## 会话

| 软件 | 连接 | 运行主机 | 可用操作 |
| --- | --- | --- | --- |
| Lumerical | 官方 `lumapi` 或 `ansys.lumerical.core` | Windows / Linux，按厂商支持的安装 | FDTD / MODE / DEVICE / INTERCONNECT 会话；项目读写；对象属性；求解；监视器结果；完整脚本 API |
| COMSOL | 社区 MPh 桥接本机 COMSOL Java API | Windows / Linux / macOS | 模型读写与新建；带单位参数；研究；表达式计算；完整 `MODEL.java` 与 `SESSION.java` |
| OpticStudio | 社区 ZOSPy 桥接 ZOS-API | Windows | 独立会话；光学系统读写；序列与非序列编辑器；原生分析、光线追迹与优化 |
| CST | 官方 `cst.interface` 与 `cst.results` | 厂商 SDK 支持的 Windows / Linux | 设计环境；项目读写；原生建模与历史；求解器；结果树 |

使用已安装 SDK 支持的解释器，本工作进程要求 Python 3.9 以上。使用 MPh 或 ZOSPy 时把它们装进该解释器；安装桥接包不会安装 COMSOL 或 OpticStudio。COMSOL 版本和 OpticStudio DLL 位置可用 `--options "@options.json"` 指定。Lumerical 选项为 `product`、`hide`、`module`，默认 FDTD。COMSOL 与 Lumerical 接收线程数；CST 与 OpticStudio 的线程由其自身求解设置控制。

```json
{"project":"/work/optical-model.mph","parameters":{"wavelength":"1550[nm]"},"results":["ewfd.normE"]}
```

```sh
optics-photonics submit comsol solve_project --inputs "@inputs.json"
optics-photonics submit comsol --program research.py --inputs "@inputs.json"
```

`inspect_project` 打开并保存项目，不求解；`solve_project` 调用 COMSOL 研究、Lumerical 求解器或 CST 求解器；OpticStudio 根据具体分析编写程序。会话程序获得 `INPUTS`、`OUTPUT_DIR`、`SDK`、`SESSION`、`MODEL`、`PROJECT_FILE` 和 `EXPORT(value, name)`，设置 `RESULT`。工作模型在程序执行前及成功结束后保存；数组与复数场导出为 NPZ，附 JSON 结构说明。[原生程序示例](../examples/native)可按实际项目修改。会话生命周期用替代 SDK 运行过；这些需要许可的求解器未在本开发环境运行。

## 自动化服务与在线服务

Windows 上，查找读取 FRED（`FRED.Application`、`FRED.Document`）、CODE V、LightTools、OptiLayer 已注册的自动化名称。按 `progid` 绑定的软件，其程序在本进程计算的所有点上以 `APP` 持有该服务，结束时释放；对象与方法以厂商自动化文档为准，例如 FRED 的 `APP.Documents.Open(path)` 返回文档对象。解释器需要安装 pywin32。

Tidy3D 从 `SIMCLOUD_APIKEY` 或 `tidy3d configure` 写出的配置读取 API key；查找只报告二者是否存在。PySpeos（`ansys-speos-core`，按配方安装）连接有许可的 Speos 安装中的 SpeosRPC 服务。以 `-pt 5101` 启动的 FIMMWAVE 响应 `pdPythonLib.pdApp().ConnectToApp()`；把 `pdPythonLib.py` 所在目录绑定为 SDK 路径。

只能在自身界面中运行脚本的软件（TracePro 的 Scheme 宏、OSLO 的 CCL、RP Photonics 脚本语言、VirtualLab Fusion 的可编程组件，以及表中其他软件）在这里没有无人值守的通路；程序仍可写出它们的输入文件并读取它们导出的文件。

MCP 服务可以运行在装有软件的工作站上，Agent 所在计算机通过 SSH 连接；例如 macOS 上的 Agent 可以使用 Windows 工作站上的 OpticStudio。

## 全部软件的通路

<!-- routes -->
| 软件 | 通路 | 安装 |
| --- | --- | --- |
| Ansys Zemax OpticStudio (`opticstudio`) | session | — |
| Keysight CODE V (`codev`) | automation; inside (Macro-PLUS) | — |
| Keysight LightTools (`lighttools`) | automation | — |
| FRED (`fred`) | automation (FRED.Application); inside (FRED Basic scripts (.frs)) | — |
| TracePro (`tracepro`) | inside (Scheme macros (.scm)) | — |
| OSLO (`oslo`) | inside (CCL) | — |
| ASAP (`asap`) | inside (ASAP scripts, with integrated Python and VBScript) | — |
| VirtualLab Fusion (`virtuallab`) | inside (programmable components and scripts of its Programming API) | — |
| Ansys Speos (`speos`) | python; service | pip |
| Ansys Lumerical (`lumerical`) | python; session; executable (lsf) | — |
| COMSOL Multiphysics (`comsol`) | session; executable | — |
| CST Studio Suite (`cst`) | session; executable | — |
| Keysight RSoft Photonic Device Tools (`rsoft`) | inside (parametric CAD, MOST scans and optimization) | — |
| JCMsuite (`jcm`) | python | — |
| Photon Design FIMMWAVE / FIMMPROP (`photond`) | service | — |
| Flexcompute Tidy3D (`tidy3d`) | python; service | pip |
| Luceda IPKISS (`ipkiss`) | python | — |
| VPIphotonics Design Suite (`vpi`) | inside (Python, MATLAB, C++ and COM co-simulation modules in its schematics) | — |
| Optiwave OptiSystem (`optisystem`) | inside (VBScript on the project Document object; Python and MATLAB …) | — |
| Essential Macleod (`macleod`) | inside (BASIC-like scripts of the Function extension) | — |
| OptiLayer / OptiRE / OptiChar (`optilayer`) | automation | — |
| RP Fiber Power (`rpfiber`) | inside (RP script language; inputs and results as text or binary files) | — |
| RP Resonator / RP ProPulse (`rpresonator`) | inside (RP script language; inputs and results as text or binary files) | — |
| Crosslight APSYS / PICS3D (`crosslight`) | inside (input files of the Crosslight simulation environment) | — |
| SYNOPSYS Lens Design（OSD） (`synopsys-osd`) | inside (SYNOPSYS commands and macros) | — |
| TFCalc (`tfcalc`) | inside (desktop application; no scripting interface was verified) | — |
| MATLAB / Simulink (`matlab`) | executable (matlab); python | — |
| Wolfram Mathematica (`mathematica`) | executable (wolfram); python | — |
| Maple (`maple`) | executable (maple) | — |
| PhotonForge Community (`photonforge`) | python | — |
| OSLO EDU (`osloedu`) | inside (CCL and commands within the EDU limits) | — |
| PtyPy (`ptypy`) | python | pip |
| Meep (`meep`) | python | conda (linux-64, linux-aarch64, osx-64, osx-arm64) |
| MPB (`mpb`) | python | conda (linux-64, linux-aarch64, osx-64, osx-arm64) |
| FDTDX (`fdtdx`) | python | pip (linux-64, linux-aarch64, osx-arm64, win-64) |
| openEMS (`openems`) | python | — |
| S⁴ / S4 (`s4`) | executable (lua) | — |
| torcwa (`torcwa`) | python | pip (linux-64, linux-aarch64, osx-arm64, win-64) |
| grcwa (`grcwa`) | python | pip |
| legume (`legume`) | python | pip |
| Ceviche (`ceviche`) | python | pip |
| tmm (`tmm`) | python | pip |
| Solcore (`solcore`) | python | pip (linux-64, osx-64, osx-arm64, win-64) |
| RayOptics (`rayoptics`) | python | pip |
| Optiland (`optiland`) | python | pip |
| Raysect (`raysect`) | python | pip (linux-64) |
| DCC-Lab RayTracing (`raytracing`) | python | pip |
| LightPipes (`lightpipes`) | python | pip |
| POPPY (`poppy`) | python | pip |
| HCIPy (`hcipy`) | python | pip |
| prysm (`prysm`) | python | pip |
| Diffractio (`diffractio`) | python | pip |
| TorchOptics (`torchoptics`) | python | pip (linux-64, linux-aarch64, osx-arm64, win-64) |
| waveprop (`waveprop`) | python | pip (linux-64, linux-aarch64, osx-arm64, win-64) |
| gdsfactory (`gdsfactory`) | python | pip |
| KLayout (`klayout`) | python | pip |
| SAX (`sax`) | python | pip (linux-64, linux-aarch64, osx-arm64, win-64) |
| SiEPIC-Tools (`siepic`) | python | pip |
| Nazca Design (`nazca`) | python | — |
| ADDA (`adda`) | executable | — |
| miepython (`miepython`) | python | pip |
| treams (`treams`) | python | pip (linux-64, osx-arm64, win-64) |
| SMUTHI (`smuthi`) | python | — |
| pyGDM (`pygdm`) | python | pip |
| QuTiP (`qutip`) | python | pip |
| QuantumOptics.jl (`quantumoptics`) | executable (julia) | julia |
| Perceval (`perceval`) | python | pip |
| Strawberry Fields (`strawberry`) | python | pip |
| Luna.jl (`luna`) | executable (julia) | julia |
| py-fmas (`pyfmas`) | python | pip |
| laserfun (`laserfun`) | python | pip |
| OptiCommPy (`opticomm`) | python | pip |
| Finesse 3 (`finesse`) | python | pip (linux-64, osx-arm64) |
| reZonator 2 (`rezonator`) | inside (desktop application and its project files) | — |
| MCX (`mcx`) | python; executable | pip (linux-64, win-64) |
| MMC (`mmc`) | python; executable | pip (linux-64, osx-64, osx-arm64, win-64) |
| HoloPy (`holopy`) | python | conda (linux-64, osx-64, win-64) |
| pyDHM (`pydhm`) | python | pip |
| PyNX (`pynx`) | python | — |
| Mitsuba 3 (`mitsuba`) | python | pip (linux-64, linux-aarch64, osx-arm64, win-64) |
| PBRT v4 (`pbrt`) | executable | — |
| SRW (`srw`) | python | pip (linux-64, osx-arm64, win-64) |
| SHADOW4 / OASYS (`shadow`) | python | pip |
| xrt (`xrt`) | python | pip |
| SymPy (`sympy`) | python | pip |
| SageMath (`sage`) | python | — |
| GNU Octave (`octave`) | executable (octave) | conda (linux-64, osx-arm64) |
| Julia (`julia`) | executable (julia) | conda (linux-64) |
| FreeCAD (`freecad`) | python | — |
| Gmsh (`gmsh`) | python | conda |
| scikit-image (`scikitimage`) | python | pip |
| napari (`napari`) | python | pip |
| FEniCSx / DOLFINx (`fenics`) | python | conda |
| Netgen / NGSolve (`ngsolve`) | python | pip (linux-64, osx-64, osx-arm64, win-64) |
| NumPy / SciPy (`scipy`) | python | pip |
| JAX (`jax`) | python | pip (linux-64, linux-aarch64, osx-arm64, win-64) |
| PyTorch (`pytorch`) | python | pip (linux-64, linux-aarch64, osx-arm64, win-64) |
| py-pol (`py-pol`) | python | pip |
<!-- /routes -->

原始资料：[MATLAB 命令行](https://www.mathworks.com/help/matlab/ref/matlablinux.html)、[MATLAB Engine for Python](https://www.mathworks.com/help/matlab/matlab_external/install-the-matlab-engine-for-python.html)、[Octave 7](https://octave.org/NEWS-7.html)、[Julia 命令行](https://docs.julialang.org/en/v1/manual/command-line-interface/)、[juliaup](https://github.com/JuliaLang/juliaup)、[wolframscript](https://reference.wolfram.com/language/ref/program/wolframscript.html)、[RawJSON](https://reference.wolfram.com/language/ref/format/RawJSON.html)、[Maple 命令行](https://www.maplesoft.com/support/help/maple/view.aspx?path=maple)、[COMSOL 批处理](https://www.comsol.com/blogs/how-to-run-simulations-in-batch-mode-from-the-command-line)、[Lumerical 命令行](https://optics.ansys.com/hc/en-us/articles/52492316567187-CommandLine-Win-Lin-DesignEnvironmentOptions)、[Lumerical Linux](https://optics.ansys.com/hc/en-us/articles/360024974033-Running-simulations-using-terminal-on-Linux)、[jsonsave](https://optics.ansys.com/hc/en-us/articles/360034928313)、[CST 批处理](https://deepthoughtdocs.flinders.edu.au/en/latest/software/cststudio.html)、[JCMsuite Python](https://www.docs.jcmwave.com/JCMsuite/html/PythonInterface/bf647454e36069fd16f1a7a35cf6a865.html)、[FIMMWAVE 脚本](https://web.ece.ucsb.edu/oewiki/images/4/4c/Fimmwave_Scripting_Manual.pdf)、[FRED 自动化](https://help.photonengr.com/Topics/AutomationFundamentals.htm)、[PySpeos](https://pypi.org/project/ansys-speos-core/)、[Tidy3D](https://github.com/flexcompute/tidy3d)、[S4](https://web.stanford.edu/group/fan/S4/tutorial.html)、[ADDA](https://github.com/adda-team/adda/wiki/Tutorial)、[MCX](https://github.com/fangq/mcx)、[MMC](https://github.com/fangq/mmc)、[Lumerical 会话](https://optics.ansys.com/hc/en-us/articles/360041873053-Session-Management-Python-API)、[MPh](https://mph.readthedocs.io/en/stable/api/mph.start.html)、[ZOSPy](https://zospy.readthedocs.io/en/stable/api/zospy.zpcore.ZOS.html)、[CST Python](https://events.3ds.com/python-driven-automation-electromagnetic-simulations)。
