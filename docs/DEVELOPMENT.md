# Developing the optical research environment

[中文](DEVELOPMENT.zh-CN.md) · [Contributing](../CONTRIBUTING.md) · [Source map](../AGENTS.md)

The environment connects scientific software, runs complete research programs and keeps interpretable results. It installs and operates independently of any particular agent, research OS or instrument controller. Release-specific changes belong in [RELEASE.md](RELEASE.md).

## Responsibilities

| Layer | Owns | Extension point |
| --- | --- | --- |
| Scientific programs | Physical models, numerical methods, observations and interpretation | Python/native programs and declared inputs/results |
| Software integrations | Solver identity, connection recipes, packaged programs and guides | Installed data-only integration distributions; local registration |
| Execution | Dependencies, attempts, resource admission and continuation | `jobs`, `worker`, `execution`, `progress` |
| Scientific data | Arrays, units, coordinates and physical conventions | `data`, `arrays`, file bindings |
| Hosts | Discovery, submission, cancellation and bounded result access | Python, CLI, MCP and TypeScript |
| Native processes | Process trees, deadlines and file-backed I/O | Rust executor, with a portable fallback |
| Persistence | Runs, requests, step state and local capacities | SQLite and per-attempt files |

New solver behavior belongs in an integration or program. A domain-specific choice should not become a global dispatch rule. Keep the solver's full API available; preserve existing imports, calls, identities, bindings and saved work.

## Existing capabilities

- Discovery covers the bilingual catalogue and independently installed integrations. Programs and guides can extend an existing solver without modifying its core record. Metadata is read without importing scientific packages. Submitted extension programs retain their source and provider information. See [integrations](../skills/optical-computation/references/integrations.md).
- Every catalogue entry states its connection route: Python, native session, executable, automation, service or inside the application. Recipes prepare separate solver environments. COMSOL, Lumerical, OpticStudio and CST use session adapters; native-language programs use the same input/output contract. See [native software](NATIVE.md).
- Parameter sweeps, bounded optimization, dependency workflows and episode collections run as persistent jobs. Resource quantities are acquired together across processes on a computing host. MCP waits are separately cancellable and do not block other requests. See [execution](EXECUTION.md).
- `CHECKPOINT` saves explicit program state and immutable artifact references. Optimization retains completed evaluations; grouped sweeps retain completed points. `resume_run` preserves successful steps and prior attempts. Search and stable pages recover work after reconnecting. See [continuation](../skills/optical-computation/references/continuation.md).
- Described arrays retain units, axes, phase/sign conventions, normalization and reference planes. File bindings avoid copying arrays through JSON. Partial reads, plots and TypeScript transfers serve large results. Existing exchanges include HCIPy to POPPY, RCWA unit cells to metalens propagation, and device coupling to a circuit model.

## Extend by a research task

Choose a concrete observable, the physical assumptions and the outputs another researcher needs. Reuse an existing program or publish an integration containing one. Keep scientific dependencies in the solver environment. Inputs should name units; outputs should retain sampling and conventions. A conservation law, analytic limit, convergence change or independent model should address the relevant numerical question.

For an agent interface, keep the initial reply short. Give the program's inputs, model and source when requested; let the task select the relevant guide. Update the Python/CLI/MCP/TypeScript surfaces together when an operation changes. Use the existing schemas and serializers rather than a parallel protocol.

For long calculations, save at a scientifically meaningful boundary after output files have been written. Save a remote provider's job ID before polling and reconnect to that job after interruption. Native solver objects stay in their process; they are not assumed serializable.

## Current boundaries

The catalogue is broader than unattended automation. Inside-only software needs its own application workflow; licensed SDKs require compatible installations and credentials. Session lifecycle cases use SDK substitutes where licensed installations are unavailable. New integrations should state the actual route and exercised operations.

Local resource capacities do not select GPU IDs, allocate MPI ranks or schedule a cluster. Those choices belong to the solver launcher or external scheduler. A reusable remote-job adapter should retain the backend ID, reconnect, retrieve results and cancel the actual job; a lost submission reply must not create a duplicate calculation.

First-order data conversions and existing examples do not cover every optical quantity or model. Further scientific work should extend reusable programs and described results for meshes, rays, layouts, coupled devices and uncertainty. Optional learning frameworks retain their own policies and training algorithms.

## Integration and release

Start from current main and read related open contributions. Implement one usable behavior per commit. Preserve contributor history and saved work. Regenerate catalogues and host bundles from their canonical sources; repository builds exclude integrations installed only on the maintainer's machine.

Run the relevant program/runtime/client cases, then the repository workflow. Describe what changed, the observed outcome and any workstation or software still required. Version package, client, native executable and plugin metadata consistently when publishing; personal and EnvFoundry repositories retain the same integrated history.
