---
name: optical-computation
description: "Connect optical solvers and instrument software, run native research programs, parameter studies and learning episodes, continue interrupted calculations, and retrieve scientific data through Python, MCP or an agent host. Use for installed commercial software, open-source libraries and external integration packages."
---

# Optical computation

Submit a complete scientific task to the solver's own environment. Accepted work continues after the agent disconnects; the run ID retrieves it from any later session using the same computing host.

1. **Choose a model and program.** Search the physical problem with `software_search`; read `software_details(tool, program=NAME)` for inputs, assumptions and outputs. Request `source=true` only to adapt it. Read `optical-research` when choosing the physical model. Use `materials` when measured optical constants are needed and retain their source.
2. **Reuse an installation.** `environments` lists bindings. `discover_native_software` finds installed executables and SDKs; `bind_native_software` connects them. `bind_environment` selects an existing Python or command. An available recipe prepares missing software on first submission. `software_integrations` lists installed extension packages and their guides; `register_software` describes a local tool outside the catalogue.
3. **Express the research.** Use a packaged `action`, Python `source`, or native-language `script`. Programs receive `INPUTS` and `OUTPUT_DIR` and return compact `RESULT`; save arrays, models and plots as files. `data.save` retains units, coordinates and conventions. Keep coupled numerical loops and live solver sessions inside one program. For long Python programs, save explicit state with `CHECKPOINT`; read `continuation` before designing the loop.
4. **Submit once.** Use a meaningful `name` and stable `request_id`; retry a lost reply with the identical request. `submit_calculation` supports a single calculation, `sweep` or `optimize`. `submit_workflow` connects steps with `after` and `bindings`; file bindings pass locations without copying arrays into context. Specify shared resource needs before submitting concurrent work.
5. **Follow and continue.** `run_status(wait=25)` waits without blocking other calls; `cancel_run` stops active work. After reconnecting, `list_runs(search=..., tool=..., state=...)` finds work; pass `next_before` as `before` for the next page. Read the error and available progress before `resume_run`. It keeps successful steps; programs using `CHECKPOINT` and built-in studies reuse saved progress. A remote provider's job ID must be saved before reconnecting to it, so resuming does not blindly submit another remote job.
6. **Interpret results.** Request the relevant curve, map or numbers with `read_array`, `sweep_results`, `read_result` and `result_files`. Compare with an appropriate conservation law, analytic limit, discretization refinement or independent model when it resolves a scientific question. Report the result with units, assumptions, uncertainty or numerical accuracy where known, and the run/file references needed to continue.

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
