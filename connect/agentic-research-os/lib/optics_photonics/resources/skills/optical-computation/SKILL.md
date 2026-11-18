---
name: optical-computation
description: "Connect optical software environments, model and simulate optical systems, run native research programs and parallel calculations, collect versioned research episodes for learning, retrieve scientific results, or install optical MCP and plugin connections."
---

# Optical computation

Write one complete program per scientific task and submit it. A background worker runs it in the solver's own environment and keeps running after the agent or the MCP connection ends.

| Stage | Tools |
| --- | --- |
| Choose software | `software_search`, `software_details` |
| Material data | `materials` |
| Connect its environment | `environments`, `prepare_environment`, `bind_environment`, `discover_native_software`, `bind_native_software`, `register_software` |
| Run | `submit_calculation` (with `sweep` or `optimize`), `submit_workflow`, `sample_episodes`, `compute_resources` |
| Follow | `run_status`, `list_runs`, `cancel_run`, `resume_run` |
| Read results | `result_files`, `read_result`, `read_array`, `sweep_results`, `download_result` |

1. **Connect.** `software_details(tool)` gives the installation recipe, native interfaces and packaged programs; search results show `install` as `pip`, `conda` or `manual`. A tool with a recipe needs no preparation: the first submission installs it as step `prepare.TOOL` of its run. `prepare_environment(tool, packages=[...])` installs ahead of time or adds packages such as scipy. `bind_environment(python=...)` without a tool connects every tool an existing interpreter provides; `bind_environment(tool, python=...)` connects one. `environments` lists what is configured; `refresh=true` only when current availability matters.
2. **Program.** `software_details(tool)` lists the tool's packaged programs, each with its physics, inputs (default and meaning), results and checks; [programs](references/programs.md) lists all of them. When one matches the task, submit it as `action` with only the inputs that differ from the defaults, and read its `checks` (energy balance, analytic limits) before trusting the numbers. When one is close, `software_details(tool, program=NAME)` returns its source to edit and submit as `source`. Otherwise write Python `source` on the software's full native API: it receives `INPUTS` and `OUTPUT_DIR` and sets `RESULT` to compact JSON. For refractive indices, `materials(material, wavelength)` returns n and k from the refractiveindex.info database with the page's references; in a program, `materials.index_at('SiO2', wavelength_um)` from `optics_photonics` gives n + ik. Save arrays, meshes, models and plots as files in OUTPUT_DIR; `data.save` keeps units, axes and conventions with the arrays ([data](references/data.md)). Keep a tightly coupled loop or a live solver session inside one program.
3. **Submit.** `submit_calculation` returns `run_id` at once; with `wait` (up to 25 seconds) it also returns the result, files and output folder, or the error, of a calculation that finishes in that time. Pass the same `request_id` when retrying a submission. `sweep` computes every combination of input values in parallel and `sweep_results` tabulates them with the best point; `optimize` searches inputs within bounds inside one process for the minimum or maximum of a result value ([studies](references/studies.md)). `submit_workflow` takes steps with `id`, `tool`, `action` or `source`, `inputs`, and optional `after`, `bindings`, `requirements`, `timeout` in seconds. Steps without `after` run in parallel. `{"value":{"step":"solve","path":["result","R"]}}` binds a predecessor value; `{"field":{"step":"solve","file":"field.npz"}}` binds the location of a predecessor file or folder, for arrays, meshes and models. Pass `run_id` to add steps to an existing run.
4. **Follow.** `run_status(run_id, wait=25)` waits for completion while other calls are answered. `list_runs` finds earlier work after reconnecting. `cancel_run` stops a run. `resume_run` reruns unfinished steps and keeps completed steps and every attempt's files; read the earlier log, and any saved remote job ID, before restarting a remote calculation.
5. **Read.** `result_files(run_id, prefix="solve/")` lists files with sizes and array shapes. `read_result` returns a byte range of a text or log file. `read_array` returns part of an NPY or NPZ array (`index`, `member`, `max_elements`) with its unit and the coordinates of the returned values when the program described them; read arrays in parts, not as whole files. `image` draws the selection instead: lines over the long axis, or a map with a color bar for two long axes, returned as a PNG with the extremes and their coordinates; `part` takes the phase or another part of complex values and `scale="log"` shows decades, as for a PSF or a scattering pattern.

**Resources.** `compute_resources(cpu=..., pools={...})` sets shared CPU and named capacities such as GPU slots and solver licenses. `bind_environment` sets a tool's threads, concurrency, environment variables and resource requirements; a step may add `requirements`, and all quantities are acquired together across runs. Set concurrency to what the license and the machine allow. MPI ranks, GPUs and cluster or cloud queues are configured in the solver's own launcher. A program that starts a cloud or cluster job saves the job ID in its result and continues that job through the provider's API.

Read when the task needs it:

- [programs](references/programs.md): the packaged programs, executable programs, the command line, tools outside the catalogue.
- [studies](references/studies.md): sweeps, their table and refinement, optimization.
- [data](references/data.md): units, axes and conventions that travel with arrays between programs.
- [native-software](references/native-software.md): installed Lumerical, COMSOL, OpticStudio and CST.
- [episodes](references/episodes.md): `sample_episodes`, retries and continued collections.
- [hosts](references/hosts.md): host packages, remote workstations, long runs and updates.
