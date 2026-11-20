# Optics-Photonics-AI-Lab 0.11.0

## Independent software integrations

Installed distributions can add software identities, recipes, programs and bilingual guides through data-only `optics_photonics.integrations` entry points. They can also add distinct programs to an existing solver. Search, details, binding and submission use these additions without importing their scientific dependencies in the connector.

`software_integrations` lists providers and load errors, refreshes changed installations and reads a guide on request. Submitted extension programs retain source, defaults and provider information, so the worker can run in a separate interpreter and accepted work does not depend on the package still being installed. The installable Gaussian-beam example demonstrates the complete path.

## Continuing research

- Python programs receive optional `CHECKPOINT` for atomic JSON state and references to written model/data files. Continuation checks the source, inputs and binding before reusing state; previous attempts stay available.
- Both built-in optimizers reuse completed evaluations while reconstructing the seeded search under its original budget. Solver objects are not serialized. Completed grouped-sweep points are retained across interrupted attempts; each table row names its original output directory.
- `run_status` exposes compact progress references without loading saved state. The diffraction example pauses inside a calculation and resumes the remaining detector points.
- `list_runs` searches names, run IDs, request IDs and software, with state/tool filters and stable `before` pagination. SQLite indexes support these queries; summaries contain software and step counts without program sources or large results.

## Host interfaces and maintenance

TypeScript adds typed run discovery, program details, integration metadata and guide access. MCP descriptions, prompts, the compact computation Skill, bilingual READMEs and development guidance follow the same behavior. Generated bundles include the new guides; repository catalogue generation excludes locally installed integrations.

Native executors reject invalid deadlines before launching a program or opening its output files. The package, TypeScript client, native executor and plugin metadata are 0.11.0; the DeepSeek launcher selects this same version.

The bundled catalogue remains 110 entries, 69 recipes and 57 programs across 39 libraries. Independent additions do not alter these repository-owned counts. Commercial SDK and instrument requirements remain those of their integrations. Saved progress resumes explicitly saved program state, not arbitrary process memory or physical equipment state.

## 中文

新增独立软件接入包：静态声明软件、配方、程序与双语指南，可为已有求解器增加程序，读取时不导入科学依赖。提交时保存扩展程序的源码、默认输入和来源，使独立求解器环境以及后续接续都能使用原定义。高斯光束接入包演示安装、发现和运行全过程。

Python 程序通过 `CHECKPOINT` 保存状态与文件引用；两个内置优化器恢复已完成的评估，分组扫描保留完成的参数点及其原输出位置。任务概况只返回进度位置，按需读取详细状态。新增名称、请求编号和软件搜索、稳定分页及对应 SQL 索引。

同步更新 TypeScript、MCP、按需指南、双语入口与宿主包，压缩旧开发文档的重复内容。Rust 在执行前拒绝非法时限；发布版本与 DeepSeek 实际启动版本统一为 0.11.0。保留已有接口和运行记录。
