# Software integrations / 软件扩展

An integration is an ordinary Python distribution containing software
descriptions, installation recipes, programs and task guides. Install it in
the **connector's** Python environment. Heavy scientific dependencies belong
in the solver environment selected by `prepare_environment` or
`bind_environment`. Discovery reads metadata and files; it does not import the
integration or start its software.

扩展是普通的 Python 分发包，携带软件说明、安装配方、程序和任务指南。
安装在**连接器的** Python 环境中；科学计算依赖安装在
`prepare_environment` 或 `bind_environment` 选择的求解环境中。
发现扩展时只读取元数据和文件，不导入扩展，也不启动软件。

## Use an installed integration / 使用已安装的扩展

1. `software_integrations(refresh=true)` reloads installed distributions and
   lists their software, programs, guides and any declaration errors.
2. Use `software_search` and `software_details` as usual. A program and its
   provider are listed together; `integration_guides` names relevant guides.
3. Read a guide only when needed:
   `software_integrations(integration="PACKAGE:ENTRY", topic="TOPIC", language="en")`.
4. Prepare or bind the solver, then `submit_calculation(tool, action, inputs)`.
   A submitted integration program retains its source, defaults and provider
   version, including when the worker uses a different Python environment.

1. `software_integrations(refresh=true)` 重新读取已安装的扩展，列出软件、程序、指南和声明错误。
2. 照常使用 `software_search` 和 `software_details`；程序注明来源，
   `integration_guides` 给出相关指南。
3. 按需读取指南：
   `software_integrations(integration="PACKAGE:ENTRY", topic="TOPIC", language="zh")`。
4. 准备或绑定求解环境，再用 `submit_calculation(tool, action, inputs)`。
   提交时保存扩展程序的源码、默认输入和提供方版本；计算进程可以使用另一套 Python。

The equivalent CLI is `optics-photonics integrations [PACKAGE:ENTRY] [TOPIC]
[--language en|zh] [--refresh]`. Python exposes `integrations.listing()` and
`integrations.guide(integration, topic, language)`. Update or remove a package
with pip, then refresh or restart the connector. Removing an integration
does not delete bindings or previous research data. Keep required solver
dependencies installed for queued and resumed work.

CLI 对应 `optics-photonics integrations [PACKAGE:ENTRY] [TOPIC]
[--language en|zh] [--refresh]`。Python 接口为 `integrations.listing()` 和
`integrations.guide(integration, topic, language)`。用 pip 更新或删除扩展后，
刷新或重启连接器。删除扩展不删除已有绑定与研究数据；排队或继续的任务仍需保留求解依赖。

## Publish an integration / 发布扩展

Declare a data entry point in `pyproject.toml`; its value is a package name,
with **no callable**. Include `optics.json` and the declared files as package
data. Common flat and `src` editable layouts also work without executing an
import finder.

在 `pyproject.toml` 中声明数据入口，值为包名，**不带可调用函数**。
将 `optics.json` 和它声明的文件作为包数据发布。
常见的平铺目录与 `src` 可编辑安装也可使用，不执行其导入查找器。

```toml
[project.entry-points."optics_photonics.integrations"]
models = "my_optical_models"

[tool.setuptools.package-data]
my_optical_models = ["optics.json", "programs/*.py", "guides/*.md"]
```

A manifest may add programs and guides to an existing solver without
redeclaring that solver. This is a complete manifest for that case:

扩展可以为已有求解器添加程序和指南，无需重新声明该求解器。例如：

```json
{
  "schema_version": 1,
  "programs": [{"tool": "scipy", "name": "my_model", "path": "programs/my_model.py"}],
  "guides": [{"name": "model", "title": "Use the model", "path": "guides/model.md", "tools": ["scipy"]}]
}
```

For new software, add a `software` array. Each entry needs `id`, `name`,
`summary`, `license` and `connection`. Optional `domains`, `group`
(`open`, `paid`, `limited`), `sources` (`label` and HTTPS `url`) and physical
descriptions make it discoverable. `translations.en` and `translations.zh`
may translate `name`, `method`, `summary`, `api`, `license`, `compute`, `usage`
and `limit`, while identifiers remain shared. `connection` uses the existing
recipe and native-route fields; it does not introduce a second solver runtime.

新软件另加 `software` 数组，每项必需 `id`、`name`、`summary`、`license` 和
`connection`。可用 `domains`、`group`（`open`、`paid`、`limited`）、
`sources`（`label` 和 HTTPS `url`）及物理说明帮助发现。
`translations.en` 与 `translations.zh` 翻译文字，保持标识一致。
`connection` 沿用现有安装配方与原生通路。

Programs use the normal `PROGRAM` declaration, including `inputs`, `domains`,
`results` and the physical meaning of their output. Their source is read
statically; Python programs receive `INPUTS` and `OUTPUT_DIR`, then set
`RESULT`. Native-language programs use the same leading-comment declaration
as built-ins. A program should be self-contained or import its calculation
dependencies from the solver environment. Arbitrary helper files beside an
integration program are not automatically copied to a worker.

程序使用现有 `PROGRAM` 声明，包括 `inputs`、`domains`、`results` 和结果的物理含义。
源码静态读取；Python 程序接收 `INPUTS`、`OUTPUT_DIR` 并设置 `RESULT`。
原生语言程序沿用内置程序的首部注释声明。
程序应自包含，或从求解环境导入计算依赖；程序旁边的任意辅助文件不会自动复制给计算进程。

Software IDs and `tool/program` names must be unique. A package cannot replace
a built-in identity or program. Conflicting or malformed integrations are
listed with their errors and excluded; unrelated software remains available.
Keep vendor versions, model assumptions and input units in the relevant
description. Repository-generated catalogues include only built-in content.

软件 ID 和 `tool/program` 名称必须唯一；扩展不能替换内置身份或程序。
冲突或声明错误的扩展会列出原因并被排除，不影响无关软件。
版本要求、模型假设和输入单位写在相关说明中。
仓库生成的公开目录仅包含内置内容。
