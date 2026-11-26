<p align="right"><a href="README.zh-CN.md">中文</a> · <b>English</b></p>

![Optics · Photonics](docs/assets/readme-header.webp)

# Optics-Photonics AI Lab

An open-source environment for optical research: physical methods, editable programs, solver connections and persistent calculations. Choose a research task, prepare its software on the computing host, and use the corresponding methods and examples.

[Start a task](skills/optical-computation/references/start.md) · [Install and connect](docs/CONNECT.md) · [Releases](https://github.com/EnvFoundry/Optics-Photonics-AI-Lab/releases) · [Agent entry](llms.txt)

## Choose a research module

The product catalogue contains **27 task modules using 34 open-source software components**; the separate software view contains all **77 open-source entries**, organized into four research areas and shared optical foundations. Modules share software where appropriate; selecting two modules that use SciPy prepares one SciPy environment.

| Area | Directions | Example tasks |
| --- | --- | --- |
| Optical systems | Geometrical optics, wave optics, imaging | Lens design, diffraction, polarization, image formation |
| Photonic structures | Electromagnetics, periodic structures, films, circuits | FDTD, photonic bands, coatings, waveguides, layout |
| Light and matter | Fibers, lasers, scattering, quantum optics, tissue, X-rays | Pulse propagation, cavities, photon transport, quantum dynamics |
| Optical measurements | Laboratory acquisition | Instrument acquisition, holograms, measured spectra |
| Optical foundations | Symbolic and numerical models | Ray matrices and interface relations |

Each module links to its software, domain methods and editable programs. [Module source](data/modules.json) · [Product catalogue](data/environment-catalogue.json).

The broader [software reference](docs/catalogue.en.md) describes 110 products and libraries, including commercial applications. It is reference material, **not the default installation list**. Commercial software is optional: connect an installation with its own licence and supported operating system. No commercial application is bundled.

## Install and calculate

The connector requires Python 3.10+ and has no third-party dependencies. Solver packages are installed separately.

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install "https://github.com/EnvFoundry/Optics-Photonics-AI-Lab/releases/download/optics-v0.11.3/optics_photonics-0.11.3-py3-none-any.whl"
optics-photonics prepare tmm
optics-photonics run tmm spectrum
```

For a module selection, use `optics-photonics plan thin-film-spectra waveguide-modes`, then `optics-photonics prepare-modules thin-film-spectra waveguide-modes`. Preparation returns a run ID; `optics-photonics status RUN_ID --wait 25` follows it. Existing software can be connected with `bind --python PATH` instead of installed again. `installed` lists prepared modules; `uninstall MODULE...` removes selected unused software while retaining shared installations and research files.

**Research OS / Origo:** import the ResearchOS ZIP from [releases](https://github.com/EnvFoundry/Optics-Photonics-AI-Lab/releases), or add `https://github.com/EnvFoundry/Optics-Photonics-AI-Lab/tree/main/connect/agentic-research-os`. Activate it on the computing host, select task modules, and prepare them. The package includes the connector, catalogue and Skills; it does not download every solver.

**Other agents:** use `optics-photonics connect HOST --output DIR` for Codex, Claude, DeepSeek, Qiushi, a portable plugin or MCP. Any MCP host can launch `optics-photonics mcp`. See [connection options](docs/CONNECT.md).

## Software, knowledge and results

| Need | Location |
| --- | --- |
| Research tasks and their software | `data/modules.json`; generated `data/environment-catalogue.json` |
| Installation recipes and external interfaces | `data/connections.json`; [native software](docs/NATIVE.md) |
| Model choice, assumptions and domain knowledge | [Optical research](skills/optical-research/SKILL.md), with 15 references loaded on demand |
| Execution, workflows, data and continued work | [Optical computation](skills/optical-computation/SKILL.md) |
| Editable calculations | `src/optics_photonics/programs/`; [program reference](skills/optical-computation/references/programs.md) |
| MCP, CLI, Python and TypeScript | `src/optics_photonics/`; `clients/typescript/` |
| Host packages | Generated `connect/`; no separate source implementation |
| Physical framework | [Field · Matter · Interaction](foundations/README.md) |

MCP offers six task prompts: calculate, study, reproduce, connect, measure and continue. Read only the relevant guide and program; the complete software reference need not enter an agent's context.

Calculations run where the solver is installed. A web product connects to that host; it does not turn Windows applications into Linux programs. Platform and Python requirements belong to each recipe, and native drivers, GPUs and licences belong to the selected software. Background work survives client disconnection on a persistent host. Results retain arrays, units, coordinates and the files needed to continue.

## Compose with other environments

Reuse SeedEnv's suitable scientific interpreter through a binding. Use IOP's existing controller for shared instruments. Exchange measurements, arrays and trajectories with Synthetic-Lab, Data Engineering, Agent Gym or AI Evaluation through their documented interfaces. Each environment keeps its own runtime and state; installing this plugin does not activate or replace another environment.

Connection settings and runs use `OPTICS_HOME` (default `~/.optics-photonics`). Software uses `OPTICS_SOFTWARE_HOME` when set, otherwise `OPTICS_HOME/environments`. Research OS places new software in `System/software/optics-photonics` and keeps its existing state location. Existing installations are reused; updating the plugin preserves software and research records.

## Develop

```sh
git clone https://github.com/EnvFoundry/Optics-Photonics-AI-Lab.git
cd Optics-Photonics-AI-Lab
python -m pip install -e .
python -m unittest discover -s tests
python scripts/build.py
python scripts/package_marketplace.py
```

Read [AGENTS.md](AGENTS.md) and [development notes](docs/DEVELOPMENT.md). Generated files are committed; edit their source. Original code and descriptions use [MIT](LICENSE); linked software and data retain their own licences. [NOTICE](NOTICE).
