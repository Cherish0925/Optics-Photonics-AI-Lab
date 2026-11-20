<p align="right"><a href="README.zh-CN.md">中文</a> · <b>English</b></p>

![Optics · Photonics — software, physics, programmable access](docs/assets/readme-header.webp)

# Optics-Photonics AI Lab

A research environment for optics and photonics, built on **Field + Matter + Interaction**. Researchers and agents can discover software in a 110-tool catalogue that reaches from simulation and computation to laboratory instruments, connect local solvers, run programs in the software's own environment, and retrieve scientific data without keeping a client connected. It is available as a Python package, MCP server, plugin or Skills.

| Read | Explore the data | Build on it |
| --- | --- | --- |
| [English HTML](https://cherish0925.github.io/Optics-Photonics-AI-Lab/) · [中文 HTML](https://cherish0925.github.io/Optics-Photonics-AI-Lab/index.zh.html) | [English JSON](data/catalogue.en.json) · [中文 JSON](data/catalogue.zh.json) | [Agent entry point](llms.txt) · [Contributing](CONTRIBUTING.md) |
| [English Markdown](docs/catalogue.en.md) · [中文 Markdown](docs/catalogue.zh.md) | [Source index](data/resources.en.json) · [Schema](data/schema.json) | [Examples](examples/) · [Develop](#develop) |
| [Foundations](docs/foundations.html) · [基础框架](docs/foundations.zh.html) | [Foundation source](foundations/README.md) | [Execution](docs/EXECUTION.md) · [Native software](docs/NATIVE.md) |

The [English](https://raw.githubusercontent.com/Cherish0925/Optics-Photonics-AI-Lab/main/docs/index.html) and [Chinese](https://raw.githubusercontent.com/Cherish0925/Optics-Photonics-AI-Lab/main/docs/index.zh.html) HTML pages are self-contained and open offline. The [full catalogue page](https://cherish0925.github.io/Optics-Photonics-AI-Lab/catalogue.html) adds comparison and CSV/JSON export.

## Install

| Host | Install |
| --- | --- |
| Agentic Research OS | Download the [Research OS package](https://github.com/Cherish0925/Optics-Photonics-AI-Lab/releases/download/optics-v0.11.0/Optics-Photonics-0.11.0-ResearchOS.zip), extract it and install the directory containing `plugin.json`; it carries native executors for six system/architecture combinations, MCP, the catalogue and both Skills, and uses the host's Python. Or **Extensions → Plugins → Add from link** with `https://github.com/Cherish0925/Optics-Photonics-AI-Lab/tree/main/connect/agentic-research-os`. |
| Codex | `codex plugin marketplace add Cherish0925/Optics-Photonics-AI-Lab`, then `codex plugin add optics-photonics@optics-photonics` |
| Claude Code | `claude plugin marketplace add Cherish0925/Optics-Photonics-AI-Lab`, then `claude plugin install optics-photonics@optics-photonics` |
| Qiushi | Editions built on Research OS use the package above; other editions use `optics-photonics connect qiushi` for MCP or command access. |
| DeepSeek Harness | Project index `https://raw.githubusercontent.com/Cherish0925/Optics-Photonics-AI-Lab/main/docs/dsh/index.json`, or `optics-photonics connect deepseek` for a specific interpreter. |
| Any MCP host, Python, shell | Install the wheel below and register `optics-photonics mcp` as a stdio server. |

```sh
python -m pip install "https://github.com/Cherish0925/Optics-Photonics-AI-Lab/releases/download/optics-v0.11.0/optics_photonics-0.11.0-py3-none-any.whl"
optics-photonics prepare tmm
optics-photonics connect agentic-research-os --output optics-plugin
```

The connector needs Python 3.10+ on Windows, macOS or Linux and has no third-party dependencies; GitHub marketplace plugins use [uv](https://docs.astral.sh/uv/getting-started/installation/) to select Python 3.10+ on the execution host, downloading it only when needed. Install uv once, or generate a host package with an existing Python through `optics-photonics connect HOST --python /path/to/python`. Research OS uses its own Python. Each solver keeps its own Python, platforms and license. Run the MCP server on the machine that holds the scientific software, locally or over SSH. [Connection guide](docs/CONNECT.md) · [Interactive guide](https://cherish0925.github.io/Optics-Photonics-AI-Lab/connect.html) · [Releases](https://github.com/Cherish0925/Optics-Photonics-AI-Lab/releases)

### First calculation

```sh
optics-photonics search "Bragg mirror"
optics-photonics submit tmm spectrum --wait 25 --inputs '{"n": [1, 2.35, 1.46, 2.35, 1.46, 2.35, 1.46, 2.35, 1.46, 2.35, 1.46, 1.52], "thickness_nm": [63.83, 102.74, 63.83, 102.74, 63.83, 102.74, 63.83, 102.74, 63.83, 102.74], "wavelength_nm": {"start": 450, "stop": 800, "points": 351}}'
optics-photonics array RUN_ID calculate/attempt-1/spectrum.npz --member R --image R.png
```

The search names the tool `tmm` and its packaged program `spectrum`. The submission installs tmm into an environment of its own the first time, computes the reflectance of five quarter-wave pairs designed for 600 nm (97.8 % there) and returns the result within the wait; if it replies `running`, `optics-photonics status RUN_ID --wait 25` waits further. The last command draws the reflectance over wavelength. An agent does the same through MCP: `software_search`, `submit_calculation(tool, action, inputs, wait)`, `read_array(image="auto")`.

Optics connects models, solvers and measurement data. [IOP](https://github.com/EnvFoundry/IOP) manages shared instruments, experiment conditions and operation sequences. A research program can use the existing IOP client when a device is already controlled there, keeping simulation and measurement in one study without opening a second device connection.

## How a calculation runs

1. **Choose software.** `software_search` finds software and packaged programs by physical problem, in English or Chinese, with synonyms and abbreviations of optical concepts ([vocabulary](data/vocabulary.json)); `software_details` returns the physical method, interfaces, installation source and packaged programs of each catalogue entry. `register_software` adds a local tool outside the catalogue. [Independent integrations](skills/optical-computation/references/integrations.md) distribute software recipes, programs and guides through ordinary Python packages; `software_integrations` lists them without importing the solver.
2. **Connect its environment.** 69 tools have installation recipes for pip, conda-forge or Julia. `prepare_environment` installs them; submissions prepare missing environments automatically. `bind_environment` reuses an interpreter or command. `discover_native_software` and `bind_native_software` connect installed SDKs, executables and Windows automation servers. Service clients and software that requires its own interface are described separately in the [connection routes](docs/NATIVE.md).
3. **Use measured material data.** `materials` returns n and k of 3576 refractiveindex.info pages (CC0) with references, and with `dispersion` the group index, group velocity dispersion and D; common names such as SiO2, Si, Au, N-BK7 and BBO work offline, other pages download once.
4. **Run a program.** Choose from [57 programs across 39 software libraries](skills/optical-computation/references/programs.md), inspect its declared inputs and physics, or write a program using the full native API. Python `source` and native-language `script` programs receive inputs and an output folder and return `RESULT`. `submit_calculation` supports parallel sweeps and bounded optimization; `submit_workflow` connects dependent or parallel steps. [Parameter studies](skills/optical-computation/references/studies.md) and [described arrays](docs/EXECUTION.md#keep-the-meaning-of-arrays-between-programs) explain how inputs, units, coordinates and files pass between programs.
5. **Continue and read results.** `run_status` waits up to 25 s per call; other requests on the same connection are answered meanwhile. Runs survive disconnection and are found again with `list_runs(search=..., tool=...)`; stable pages remain usable while new work arrives. `result_files`, `read_result` and `read_array` return file listings, byte ranges and parts of NPY/NPZ arrays; `read_array` with `image` returns the selection drawn as a PNG, lines or a map with its coordinates, units and color bar. `resume_run` keeps completed steps and grouped sweep points. Python programs use `CHECKPOINT` for explicit state and model files; built-in optimization reuses completed evaluations. The [continuation guide](skills/optical-computation/references/continuation.md) and [diffraction example](examples/continuation/) show recovery within a long program.
6. **Collect episodes.** `sample_episodes` runs Gymnasium-style environments in parallel solver workers and stores seeds, actions, observations and rewards for learning; an interrupted or extended collection continues without repeating completed episodes ([episodes](docs/LEARNING.md)).

| Route | Software | What runs |
| --- | --- | --- |
| python | 77 entries: a module from a recipe or inside an installation (JCMsuite, Photon Design) | Python `source` |
| session | COMSOL, Lumerical, OpticStudio, CST | Python with a session the job owns |
| executable | MATLAB, GNU Octave, Julia, Mathematica, Maple, QuantumOptics.jl, Luna.jl, S4, COMSOL, Lumerical, CST, ADDA, MCX, MMC, pbrt | `script` in the software's language; Python that drives it with `RUN` |
| automation | FRED, CODE V, LightTools, OptiLayer, LabVIEW (Windows) | Python holding the server as `APP` |
| service | Tidy3D cloud, Speos server, FIMMWAVE | Python client of the server |
| inside | 17 applications whose scripts run only in their own window | files written for it and read from it |

| Field | Packaged programs |
| --- | --- |
| Thin films, gratings, metasurfaces | `tmm/spectrum` · `grcwa/film` · `grcwa/grating` · `grcwa/metasurface` · `scipy/metalens` |
| Electromagnetics and inverse design | `meep/stack` · `meep/ring` · `ngsolve/scattering` · `ceviche/bend` |
| Photonic crystals | `mpb/bands` · `legume/bands` · `s4/crystal_slab` |
| Waveguides, circuits, layout | `mpb/waveguide` · `tidy3d/modes` · `scipy/slab_modes` · `scipy/coupler` · `sax/circuit` · `gdsfactory/waveguide` · `klayout/layout` |
| Fibers and communications | `scipy/fiber_modes` · `scipy/nlse` · `laserfun/supercontinuum` · `octave/bragg_grating` · `opticomm/ber` |
| Lasers, resonators, nonlinear optics | `scipy/resonator` · `scipy/laser_rates` · `finesse/cavity` · `scipy/second_harmonic` |
| Scattering | `miepython/sphere` · `treams/cluster` · `adda/particle` |
| Imaging and beams | `hcipy/psf` · `poppy/psf` · `prysm/mtf` · `lightpipes/gaussian` · `diffractio/apertures` · `scikitimage/registration` |
| Lenses, rays, polarization | `optiland/lens` · `optiland/trace` · `raytracing/abcd` · `sympy/abcd` · `sympy/fresnel` · `py-pol/polarization` |
| Quantum optics | `qutip/rabi` · `qutip/jaynes_cummings` · `qutip/resonance_fluorescence` · `quantumoptics/jaynes_cummings` · `perceval/interference` · `strawberry/gaussian_state` |
| Tissue, X-rays, photovoltaics | `scipy/tissue_layers` · `srw/undulator` · `solcore/detailed_balance` |
| Measured data | `scipy/resonances` · `scipy/fit_gaussian` |
| Laboratory instruments and holograms | `pyvisa/sweep` · `bluesky/scan` · `slmsuite/spot_array` |

The same operations are available through the command line, Python and TypeScript; an MCP host also receives six prompts (calculate, study, reproduce, connect, measure, continue) and the guides as resources. A catalogue route describes an interface; local bindings determine what can run on a particular host. Software licenses, platform support and service access remain those of the selected software. [Release notes](docs/RELEASE.md) record the validation performed for each release.

## Execution

A Rust executor owns solver processes, cancellation and deadlines. Python connects scientific SDKs and coordinates jobs. SQLite stores runs and admits steps against shared CPU and named capacities such as GPUs and solver licenses, across all runs on the host. The TypeScript client connects agent hosts. MPI ranks, GPU selection and cluster queues remain in each solver's own launcher. [Execution and resources](docs/EXECUTION.md)

## Physical foundation

> **Optics / Photonics = Field + Matter + Interaction**

**Field** is the classical or quantized electromagnetic field and its states; **matter** includes microscopic degrees of freedom, materials, devices and detectors; **interaction** is the exchange of energy, momentum and information between them. Free propagation is field dynamics, components are structured matter, and a measurement is a designed field–matter interaction. The catalogue and Skills are organized by this framework, from geometrical and wave optics to nanophotonics, fibers, lasers, imaging, spectroscopy and quantum optics, each within the limits of its effective theory. [Foundations](docs/foundations.html) · [Markdown source](foundations/)

## Catalogue

- **30 commercial**, **77 open-source** and **3 free / restricted** entries in 15 domains, from geometrical optics to laboratory instruments. Free clients, paid solvers, academic licenses and external PDKs are distinguished.
- Each entry records physical methods, use cases, programming interfaces, compute environment, license, application basis, limitations and primary sources. Reviewed **2026-10-20**.
- API, CLI and macros are listed separately from **official / community / unverified** MCP servers and agent Skills. A documentation MCP is not treated as a solver interface.
- Stable `id` values are shared by both languages. Agents start at [`llms.txt`](llms.txt) and read [`llms-full.txt`](llms-full.txt) or the JSON.

Models connect through the physical quantities they exchange:

| Task | What passes between models | Examples in the catalogue |
| --- | --- | --- |
| Lens → image → inference | Pupil field, aberrations, PSF, sampling, detector response | OpticStudio, CODE V, Optiland, prysm, POPPY |
| Unit cell → metasurface → system | Complex transmission / reflection, polarization, angle, wavelength | torcwa, grcwa, Meep, Lumerical, Tidy3D, Diffractio |
| Layout → device → circuit | Process layers, ports, reference planes, normalized S-parameters | gdsfactory, KLayout, IPKISS, JCMsuite, SAX |
| Pulse → link → receiver | Complex envelope, time grid, dispersion, nonlinearity, noise | Luna, py-fmas, RP Fiber Power, VPI, OptiCommPy |
| Thermomechanics → cavity → readout | Deformation, index changes, operating point, noise spectra | COMSOL, Finesse, HCIPy |
| Sample → propagation → reconstruction | The measured observable and its forward operator | MCX, MMC, PyNX, pyDHM, HoloPy |
| Model → instrument → data | Settings sent, raw readings with their times, calibration, uncertainty | PyVISA, pylablib, Bluesky, python-seabreeze, LabVIEW |

Units, reference frames, field conventions and model assumptions must match at each connection.

## Develop

```bash
git clone https://github.com/Cherish0925/Optics-Photonics-AI-Lab.git
cd Optics-Photonics-AI-Lab
python -m pip install -e ".[rl]"
python -m unittest discover -s tests
python scripts/build.py
python scripts/package_marketplace.py
```

`build.py` regenerates the HTML, Markdown, source index and agent documents from `data/`; `package_marketplace.py` regenerates the bundled Research OS copy after source or Skill changes. Generated files are committed. `OPTICS_SCIENCE_TESTS=1` enables the cases that run scientific libraries.

| Path | Purpose |
| --- | --- |
| `src/optics_photonics/` | Connector: catalogue, environments, execution, jobs, result arrays, episode sampling, MCP, CLI |
| `native/executor/` | Rust process executor |
| `clients/typescript/` | TypeScript client for agent hosts |
| `skills/` | Agent Skills and domain references |
| `connect/` | Generated host packages |
| `data/` | Bilingual catalogue, connections, domains and schema |
| `src/render.py`, `scripts/build.py` | Website and document generation |
| `examples/` | Native programs, solver sessions and the episode example |
| `foundations/` | Field · Matter · Interaction framework |
| `AGENTS.md` | Map, commands and conventions for changing the repository |

## License

Original code and catalogue descriptions are [MIT](LICENSE). Referenced software, documentation, PDKs and data keep their own licenses. The embedded Noto-derived font subset is [SIL OFL 1.1](docs/assets/FONT_LICENSE.txt). See [NOTICE](NOTICE). Package names, commands, plugin IDs and stored environments are unchanged since the repository was renamed.
