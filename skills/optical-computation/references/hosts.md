# Hosts

**Where it runs.** The MCP server and its background workers run on the computer that holds the scientific software. For a remote workstation, start the server there through SSH: `ssh -T USER@HOST /path/to/python -m optics_photonics mcp`. A worker outlives the agent session and the MCP process, but not the removal of its whole container or process group; when the agent's tool environment is disposable, connect to a persistent workstation instead.

**Remote results.** `read_result` and `read_array` return file content through the connection. `download_result` copies a file on the MCP host. The TypeScript client's `download` copies a file to the client's computer.

**Packages.** `optics-photonics connect HOST --output DIR` writes a package for `agentic-research-os`, `codex`, `claude`, `deepseek`, `qiushi`, `mcp` or `portable` (Agent Plugins); follow `DIR/INSTALL.md`. Research OS installs the directory containing `plugin.json` and activates the returned revision; DeepSeek uses the Cordis overlay or bundle; other hosts register the stdio command from `mcp.json`. Native host and MCP packages accept `--python PATH` to select the connector interpreter (Python 3.10+). Portable packages and `connect codex/claude --managed-python` use uv to select Python on the destination machine. GitHub marketplace packages also require uv on that machine. Scientific tools keep their own environments.

**Prompts and guides.** A host that shows MCP prompts lists six starting points: `calculate`, `study`, `reproduce`, `connect`, `measure`, `continue`. The guides are also MCP resources, `optics://guides/TOPIC`.

**Locations.** Keep `OPTICS_HOME` for connection settings and research records. Software uses `OPTICS_SOFTWARE_HOME` when set, otherwise `OPTICS_HOME/environments`. Research OS uses `System/software/optics-photonics` for new installations; existing installations remain usable at their earlier paths. The package contains Skills and knowledge references, which the host exposes through its resource entries. Updating the package preserves software and research records.

## Selecting software before preparation

Research OS packages publish `data/environment-catalogue.json`: research areas, their
directions, task modules and shared open-source components. Hosts read this
metadata before installation and use the exact operation names declared in
`environment.preparation`.

`environment_plan(selections)` reports reuse, automatic installation or a manual
connection with its reason. `environment_prepare(selections)` prepares the chosen
modules through the existing background run owner. `environment_installed` returns
configured modules and `ready_modules` separately; pending manual connections do
not count as ready. Commercial licensing and physical apparatus remain explicit.

A host may augment preparation with MCP `task: {}`, then call `tasks/get`,
`tasks/result` and `tasks/cancel`. Completed work survives reconnects and
cancellation. Failed tasks keep their partial results. Plain calls return the
existing `run_id`; use `run_status` and `cancel_run` for those calls. The CLI offers
`plan`, `prepare-modules` and `installed`; TypeScript uses `planSoftware`,
`prepareSoftware` and `installedSoftware`. Existing bindings and calculation files
are unchanged.

`environment_remove(selections)` uninstalls selected managed software when it is no longer shared or referenced by research. Active work retains its connection; external installations, saved results and referenced environments remain. The result lists removed modules and retained paths with reasons. CLI: `optics-photonics uninstall TOOL...`; TypeScript: `uninstallSoftware(selections)`.

Task modules resolve to software components once per request. A selected module retains its shared software while another selected module still needs it. The full software reference, including commercial applications, stays outside the default module picker. Direct software IDs remain accepted for existing callers and explicit external connections.
