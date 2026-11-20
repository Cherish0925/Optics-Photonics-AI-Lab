# Optics-Photonics-AI-Lab 0.10.0

The laboratory domain brings the catalogue to 110 software tools across 15 domains, with 69 installation recipes and 57 packaged programs across 39 software libraries. New programs cover Bragg gratings, local waveguide modes, finite-element scattering, tissue transport, undulator spectra, holograms, measured resonances and instrument scans. Programs declare their domains, so domain searches and references also find relevant programs in general-purpose libraries.

MCP provides six research prompts and exposes the same guides as resources. Software details are brief by default; `brief=false` retains the complete software record and program input definitions. Request one program for its physics and inputs, and `source=true` when adapting its implementation. The existing Python detail response and discovery fields remain available. Prompt arguments are inserted literally, and malformed arguments identify what is needed.

Integration fixes include wavelength-based fitting on nonuniform spectra, separate windows for neighboring resonances, and track-length fluence across tissue layers and transparent regions. Raw Octave scripts retain their execution order. Instrument scans save raw replies before parsing, preserve partial data after a later failure, reject inconsistent column counts, and attempt all configured finish operations without masking the original acquisition error. Simulated Bluesky data is labelled explicitly. Shared instruments use a common resource pool or their existing IOP controller; per-library concurrency does not provide a cross-library device lock.

Package, plugin and client versions are aligned. The bilingual entry pages, generated catalogues and Research OS bundle are rebuilt from their source. The connector supports Python 3.10+; solvers retain their own platform and runtime requirements.

Real hardware and MATLAB execution are outside this release's validation. PyVISA and Bluesky examples use simulated devices; Octave exercises the shared MATLAB-language grating program. Catalogue inclusion describes available software interfaces and does not imply that each user's installation, license or instrument is already connected.

## 中文

新增实验仪器领域后，目录包含 15 个领域的 110 项软件、69 份安装配方和 39 套软件中的 57 个封装程序。新程序覆盖布拉格光栅、本地波导模式、有限元散射、组织光子输运、波荡器谱、全息图、实测谐振谱和仪器扫描。程序声明所属领域，通用数值库中的相关程序也能按领域找到。

MCP 提供六个研究提示，并将同一套指南作为资源提供。软件详情默认精简；`brief=false` 返回完整软件记录与程序输入定义。指定一个程序可查看物理模型和输入，需要修改时用 `source=true` 取源码。已有 Python 详细接口与发现字段继续保留。提示参数按原文插入，格式错误时说明缺少什么。

整合修复包括非均匀波长采样的拟合、相邻谐振的窗口分离，以及跨材料层和透明区域的路径长度光通量。原生 Octave 脚本保持执行顺序。仪器扫描在解析前保存原始回复，后续失败时保留已有数据，拒绝不一致的列数，并尝试全部约定的结束操作而不覆盖原始采集错误。Bluesky 模拟数据明确标注来源。共享仪器使用同一资源池或已有 IOP 控制器；单个库的并发限制不能替代跨库设备协调。

软件包、插件及客户端版本已统一；中英文入口、目录和 Research OS 包由源文件重新生成。连接程序支持 Python 3.10+，求解软件保留自己的平台与运行环境要求。

本版未验证真实仪器和 MATLAB 执行。PyVISA 与 Bluesky 示例使用模拟设备；共用的 MATLAB 语言光栅程序通过 Octave 执行。软件被收录表示相关接口已列出，并不表示用户本机的安装、许可和仪器已经连接。
