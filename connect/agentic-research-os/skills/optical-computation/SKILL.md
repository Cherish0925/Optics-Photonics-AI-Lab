---
name: optical-computation
description: "Connect optical solvers and instrument software, run native research programs, parameter studies and learning episodes, continue interrupted calculations, and retrieve scientific data through Python, MCP or an agent host. Use for installed commercial software, open-source libraries and external integration packages."
---

# Optical computation

Use the current research task and computing host. For a first connection, read [start](references/start.md); for existing work, find its run with `list_runs` and continue from its results.

- **Choose.** `software_search` finds a solver and program; `software_details(tool, program=NAME)` gives its inputs and physics. Request `source=true` only to adapt it. `materials` supplies optical constants. Read `optical-research` only when choosing or reconsidering the model.
- **Connect.** Reuse `environments` with `bind_environment`, or `discover_native_software` with `bind_native_software`. `environment_plan` explains installation on this host. Read [hosts](references/hosts.md) for selected installation, removal and remote work. `software_integrations` lists extensions; `register_software` describes a local solver.
- **Run.** `submit_calculation` accepts a packaged action, Python source or native script, with optional sweep or optimization. `submit_workflow` connects dependent steps. Programs receive INPUTS and OUTPUT_DIR, return RESULT, and save large data as files with units and axes. Reuse the same request_id after a lost reply. Keep coupled numerical loops in one program.
- **Continue.** `run_status(wait=25)` follows work; `cancel_run` stops it. Read the error and saved progress before `resume_run`. Successful steps remain. Read [continuation](references/continuation.md) when a long program needs explicit CHECKPOINT state or a remote provider's job ID.
- **Use the result.** `result_files`, `read_result`, `read_array` and `sweep_results` return the relevant files, curves or numbers. State units and model assumptions; use refinement or a reference calculation when it changes the scientific conclusion. Keep run/file references for the next session.

Read the topic needed for the task through `read_guide(topic)` or these files:

| Topic | Read when |
| --- | --- |
| [programs](references/programs.md) | Choosing a packaged program or writing one against a solver's full API |
| [studies](references/studies.md) | Scanning parameters, selecting an objective, optimizing or refining a study |
| [continuation](references/continuation.md) | Saving state and model files, recovering a long calculation |
| [data](references/data.md) | Moving scientific arrays between programs with units and conventions |
| [native-software](references/native-software.md) | Connecting executables, SDK sessions, Windows automation or services |
| [integrations](references/integrations.md) | Installing or distributing additional software, programs and guides |
| [episodes](references/episodes.md) | Collecting versioned trajectories and continuing a collection |
| [hosts](references/hosts.md) | Installing a plugin, using a remote workstation or updating a connection |

`compute_resources` sets the computing host's CPU and named capacities; bindings declare threads, concurrency and requirements. The solver launcher selects actual GPUs, MPI ranks and cluster queues. A shared instrument must have one owner and a common resource reservation across libraries. Reuse an existing controller when the laboratory already has one.
