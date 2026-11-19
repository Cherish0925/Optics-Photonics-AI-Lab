# Installed software

The environment reaches each catalogued software by one or more routes. A route says what the environment holds of the software and how a calculation uses it:

| Route | What the environment holds | How a calculation uses it |
| --- | --- | --- |
| python | an interpreter that imports the software's module, installed from a recipe or shipped inside the installation | a Python program (`source`) or a packaged program (`action`) |
| session | a COMSOL, Lumerical, OpticStudio or CST session that one job owns | `inspect_project`, `solve_project`, or a program on the full native API |
| executable | the software's own executable | a program in its language (`script`), or a Python program that runs it with `RUN` |
| automation | a Windows automation (COM) server | a Python program that holds it as `APP` |
| service | a client of a running application, a server or a cloud | a Python program with the client |
| inside | nothing: the software runs its scripts in its own window | a program writes its input files and reads the files it exports |

`software_details(tool)` lists a tool's routes; the [table below](#every-software-by-route) lists all of them.

## Find and connect

```sh
optics-photonics discover                       # every route: PATH, usual folders, variables, the Windows registry
optics-photonics discover --tool matlab --root /software
optics-photonics bind-native matlab --executable /usr/local/MATLAB/R2025b/bin/matlab
optics-photonics bind-native jcm --route python --python /path/to/python --sdk-path "$JCMROOT/ThirdPartySupport/Python"
optics-photonics bind-native fred --progid FRED.Application --python C:/Python312/python.exe
optics-photonics bind-native lumerical --python /path/to/python --sdk-path /opt/lumerical/v252/api/python --threads 4
optics-photonics prepare octave                 # conda-forge on Linux and Apple silicon; Julia, QuantumOptics.jl and Luna.jl likewise
```

Discovery reads PATH, the folders where installers usually put the software, variables that name an installation (`JCMROOT`), folders given with `--root` and, on Windows, the registered automation servers. It starts no software and acquires no license. Each installation found comes with the arguments of `bind-native`; without `--executable`, `--progid` or `--sdk-path`, `bind-native` uses the first installation discovery finds. MCP equivalents are `discover_native_software` and `bind_native_software`. Bindings keep `threads`, `concurrency`, resource requirements and environment variables; jobs keep the binding with which they were submitted. Begin licensed software with concurrency 1.

## Programs in the software's language

```sh
optics-photonics submit matlab --script mode_solver.m --inputs '{"wavelength_um": 1.55}' --wait 25
optics-photonics submit octave --script mode_solver.m --sweep '{"wavelength_um": {"start": 1.5, "stop": 1.6, "points": 11}}'
```

| Language | Software | INPUTS | Output folder | Command |
| --- | --- | --- | --- | --- |
| matlab | MATLAB R2019a and later | struct (jsondecode) | `OUTPUT_DIR` | `matlab -sd FOLDER -batch optics_main` |
| octave | GNU Octave 7 and later | struct (jsondecode) | `OUTPUT_DIR` | `octave-cli --no-gui --quiet --norc --no-window-system optics_main.m` |
| julia | Julia; QuantumOptics.jl, Luna.jl | `Dict{String,Any}` | `OUTPUT_DIR` | `julia --project=ENV --threads=N optics_main.jl` |
| wolfram | Mathematica, Wolfram Engine | Association | `OUTPUTDIR` | `wolframscript -file optics_main.wls` |
| maple | Maple 2015 and later | table | `OUTPUT_DIR` | `maple -q optics_main.mpl` (`cmaple` on Windows) |
| lua | S4 | table | `OUTPUT_DIR` | `S4 optics_main.lua` |
| lsf | Lumerical design environments | one variable per input | `OUTPUT_DIR` | `fdtd-solutions -nw -trust-script -exit -run optics_main.lsf` |

The worker saves the program as `optics_program` with the language's suffix and writes a short `optics_main` in the same language: it defines INPUTS and the output folder, runs the program and writes RESULT as JSON. The executable runs in the output folder of the calculation, or of each point of a sweep, and its output goes to `script.log`. RESULT holds numbers, strings, lists and objects; complex fields and large arrays belong in files beside it. Sweeps, optimization and workflow bindings work as for Python programs. The bridges of Octave, Julia and Lua (and the MATLAB code path, through Octave) have run here against the real interpreters; those of MATLAB, Wolfram Language, Maple and Lumerical script follow the vendors' documented commands and functions and need the licensed software to run.

## Python programs that drive an executable

A Python program of a tool bound to its executable receives `EXECUTABLE`, `SIBLINGS`, `THREADS` and `RUN(*arguments, program=None, cwd=None, input=None, timeout=None, check=True, log=None)`. `RUN` runs the executable, or the sibling executable named `program`, in the output folder; its output goes to a log file, and a nonzero exit code raises with the end of that log. The program then reads what the software wrote and saves arrays with units and axes.

```python
from pathlib import Path
# COMSOL: comsol batch on Linux and macOS, comsolbatch on Windows.
RUN(*(['batch'] if Path(EXECUTABLE).stem == 'comsol' else []), '-inputfile', INPUTS['model'],
    '-outputfile', OUTPUT_DIR / 'solved.mph', '-study', 'std1', '-pname', 'wl', '-plist', '1.5[um],1.55[um]')
RESULT = {'model': 'solved.mph'}
```

Lumerical solves a saved project with `RUN('-t', THREADS, model, program='fdtd-engine')`; CST with `RUN('-m', '-r', project)`. The packaged program `adda/particle` runs ADDA for a sphere or an ellipsoid and compares a sphere with the exact series; with ADDA built from source it converges to that series as the dipoles get finer: for a sphere of size parameter 5 and index 1.5 the extinction efficiency differs by 1.0 %, 0.26 % and 0.11 % at 8, 15 (the default) and 30 dipoles per wavelength in the particle. A gold sphere converges slowly, as the dipole approximation does for metals.

## Sessions

| Software | Connection | Execution host | Available operations |
| --- | --- | --- | --- |
| Lumerical | Vendor `lumapi`, or `ansys.lumerical.core` | Windows / Linux, supported vendor installation | FDTD / MODE / DEVICE / INTERCONNECT sessions; project load/save; object properties; solve; monitor results; full scripting API |
| COMSOL | Community MPh bridge to the installed COMSOL Java API | Windows / Linux / macOS | Model load/create/save; parameters with units; studies; evaluation; full `MODEL.java` and `SESSION.java` |
| OpticStudio | Community ZOSPy bridge to ZOS-API | Windows | Standalone session; optical system load/save; lens and nonsequential editors; native analyses, ray tracing and optimization |
| CST | Vendor `cst.interface` and `cst.results` | Windows / Linux where the vendor SDK is supported | Design environment; project load/save; native modeling/history; solver; result-tree access |

Use the interpreter supported by the installed SDK, with Python 3.9+ for this worker. Install MPh or ZOSPy in that interpreter when using their bridges; installing a bridge does not install COMSOL or OpticStudio. COMSOL version and OpticStudio DLL location can be supplied through `--options "@options.json"`. Lumerical options are `product`, `hide` and `module`; the default product is FDTD. COMSOL and Lumerical receive the configured thread count; CST and OpticStudio thread controls belong to their native solver configuration.

```json
{"project":"/work/optical-model.mph","parameters":{"wavelength":"1550[nm]"},"results":["ewfd.normE"]}
```

```sh
optics-photonics submit comsol solve_project --inputs "@inputs.json"
optics-photonics submit comsol --program research.py --inputs "@inputs.json"
```

`inspect_project` opens and saves a project without solving; `solve_project` uses the selected COMSOL study, Lumerical solver or CST solver. OpticStudio uses analysis-specific programs. A session program receives `INPUTS`, `OUTPUT_DIR`, `SDK`, `SESSION`, `MODEL`, `PROJECT_FILE` and `EXPORT(value, name)`, and sets `RESULT`. The working model is saved before and after a successful program; arrays and complex fields are exported as NPZ with JSON structure metadata. The examples in [examples/native](../examples/native) are programs to adapt to a project. Session lifetimes are exercised with SDK doubles; these licensed solvers have not run in this development environment.

## Automation servers and services

On Windows, discovery reads the registered automation names of FRED (`FRED.Application`, `FRED.Document`), CODE V, LightTools and OptiLayer. A program of a tool bound by `progid` holds the server as `APP` for all the points it computes and releases it at the end; objects and methods are those of the vendor's automation reference, for FRED `APP.Documents.Open(path)` returning a document. The interpreter needs pywin32.

Tidy3D reads its API key from `SIMCLOUD_APIKEY` or the configuration that `tidy3d configure` writes; discovery reports only whether either exists. PySpeos (`ansys-speos-core`, installed from its recipe) reaches the SpeosRPC server of a licensed Speos installation. FIMMWAVE started with `-pt 5101` answers `pdPythonLib.pdApp().ConnectToApp()`; bind the folder of `pdPythonLib.py` as the SDK path.

Software reached only from inside its own window (TracePro's Scheme macros, OSLO's CCL, the RP Photonics script language, VirtualLab Fusion's programmable components and others in the table) has no unattended route here. A program can still write its input files and read the files it exports.

The MCP server can run on the workstation that holds the software, reached from the agent's computer over SSH; an agent on macOS can so use an OpticStudio installation on Windows.

## Every software by route

<!-- routes -->
| Software | Routes | Installs |
| --- | --- | --- |
| Ansys Zemax OpticStudio (`opticstudio`) | session | — |
| Keysight CODE V (`codev`) | automation; inside (Macro-PLUS) | — |
| Keysight LightTools (`lighttools`) | automation | — |
| FRED (`fred`) | automation (FRED.Application); inside (FRED Basic scripts (.frs)) | — |
| TracePro (`tracepro`) | inside (Scheme macros (.scm)) | — |
| OSLO (`oslo`) | inside (CCL) | — |
| ASAP (`asap`) | inside (ASAP scripts, with integrated Python and VBScript) | — |
| VirtualLab Fusion (`virtuallab`) | inside (programmable components and scripts of its Programming API) | — |
| Ansys Speos (`speos`) | python; service | pip |
| Ansys Lumerical (`lumerical`) | python; session; executable (lsf) | — |
| COMSOL Multiphysics (`comsol`) | session; executable | — |
| CST Studio Suite (`cst`) | session; executable | — |
| Keysight RSoft Photonic Device Tools (`rsoft`) | inside (parametric CAD, MOST scans and optimization) | — |
| JCMsuite (`jcm`) | python | — |
| Photon Design FIMMWAVE / FIMMPROP (`photond`) | service | — |
| Flexcompute Tidy3D (`tidy3d`) | python; service | pip |
| Luceda IPKISS (`ipkiss`) | python | — |
| VPIphotonics Design Suite (`vpi`) | inside (Python, MATLAB, C++ and COM co-simulation modules in its schematics) | — |
| Optiwave OptiSystem (`optisystem`) | inside (VBScript on the project Document object; Python and MATLAB …) | — |
| Essential Macleod (`macleod`) | inside (BASIC-like scripts of the Function extension) | — |
| OptiLayer / OptiRE / OptiChar (`optilayer`) | automation | — |
| RP Fiber Power (`rpfiber`) | inside (RP script language; inputs and results as text or binary files) | — |
| RP Resonator / RP ProPulse (`rpresonator`) | inside (RP script language; inputs and results as text or binary files) | — |
| Crosslight APSYS / PICS3D (`crosslight`) | inside (input files of the Crosslight simulation environment) | — |
| SYNOPSYS Lens Design(OSD) (`synopsys-osd`) | inside (SYNOPSYS commands and macros) | — |
| TFCalc (`tfcalc`) | inside (desktop application; no scripting interface was verified) | — |
| MATLAB / Simulink (`matlab`) | executable (matlab); python | — |
| Wolfram Mathematica (`mathematica`) | executable (wolfram); python | — |
| Maple (`maple`) | executable (maple) | — |
| PhotonForge Community (`photonforge`) | python | — |
| OSLO EDU (`osloedu`) | inside (CCL and commands within the EDU limits) | — |
| PtyPy (`ptypy`) | python | pip |
| Meep (`meep`) | python | conda (linux-64, linux-aarch64, osx-64, osx-arm64) |
| MPB (`mpb`) | python | conda (linux-64, linux-aarch64, osx-64, osx-arm64) |
| FDTDX (`fdtdx`) | python | pip (linux-64, linux-aarch64, osx-arm64, win-64) |
| openEMS (`openems`) | python | — |
| S⁴ / S4 (`s4`) | executable (lua) | — |
| torcwa (`torcwa`) | python | pip (linux-64, linux-aarch64, osx-arm64, win-64) |
| grcwa (`grcwa`) | python | pip |
| legume (`legume`) | python | pip |
| Ceviche (`ceviche`) | python | pip |
| tmm (`tmm`) | python | pip |
| Solcore (`solcore`) | python | pip (linux-64, osx-64, osx-arm64, win-64) |
| RayOptics (`rayoptics`) | python | pip |
| Optiland (`optiland`) | python | pip |
| Raysect (`raysect`) | python | pip (linux-64) |
| DCC-Lab RayTracing (`raytracing`) | python | pip |
| LightPipes (`lightpipes`) | python | pip |
| POPPY (`poppy`) | python | pip |
| HCIPy (`hcipy`) | python | pip |
| prysm (`prysm`) | python | pip |
| Diffractio (`diffractio`) | python | pip |
| TorchOptics (`torchoptics`) | python | pip (linux-64, linux-aarch64, osx-arm64, win-64) |
| waveprop (`waveprop`) | python | pip (linux-64, linux-aarch64, osx-arm64, win-64) |
| gdsfactory (`gdsfactory`) | python | pip |
| KLayout (`klayout`) | python | pip |
| SAX (`sax`) | python | pip (linux-64, linux-aarch64, osx-arm64, win-64) |
| SiEPIC-Tools (`siepic`) | python | pip |
| Nazca Design (`nazca`) | python | — |
| ADDA (`adda`) | executable | — |
| miepython (`miepython`) | python | pip |
| treams (`treams`) | python | pip (linux-64, osx-arm64, win-64) |
| SMUTHI (`smuthi`) | python | — |
| pyGDM (`pygdm`) | python | pip |
| QuTiP (`qutip`) | python | pip |
| QuantumOptics.jl (`quantumoptics`) | executable (julia) | julia |
| Perceval (`perceval`) | python | pip |
| Strawberry Fields (`strawberry`) | python | pip |
| Luna.jl (`luna`) | executable (julia) | julia |
| py-fmas (`pyfmas`) | python | pip |
| laserfun (`laserfun`) | python | pip |
| OptiCommPy (`opticomm`) | python | pip |
| Finesse 3 (`finesse`) | python | pip (linux-64, osx-arm64) |
| reZonator 2 (`rezonator`) | inside (desktop application and its project files) | — |
| MCX (`mcx`) | python; executable | pip (linux-64, win-64) |
| MMC (`mmc`) | python; executable | pip (linux-64, osx-64, osx-arm64, win-64) |
| HoloPy (`holopy`) | python | conda (linux-64, osx-64, win-64) |
| pyDHM (`pydhm`) | python | pip |
| PyNX (`pynx`) | python | — |
| Mitsuba 3 (`mitsuba`) | python | pip (linux-64, linux-aarch64, osx-arm64, win-64) |
| PBRT v4 (`pbrt`) | executable | — |
| SRW (`srw`) | python | pip (linux-64, osx-arm64, win-64) |
| SHADOW4 / OASYS (`shadow`) | python | pip |
| xrt (`xrt`) | python | pip |
| SymPy (`sympy`) | python | pip |
| SageMath (`sage`) | python | — |
| GNU Octave (`octave`) | executable (octave) | conda (linux-64, osx-arm64) |
| Julia (`julia`) | executable (julia) | conda (linux-64) |
| FreeCAD (`freecad`) | python | — |
| Gmsh (`gmsh`) | python | conda |
| scikit-image (`scikitimage`) | python | pip |
| napari (`napari`) | python | pip |
| FEniCSx / DOLFINx (`fenics`) | python | conda |
| Netgen / NGSolve (`ngsolve`) | python | pip (linux-64, osx-64, osx-arm64, win-64) |
| NumPy / SciPy (`scipy`) | python | pip |
| JAX (`jax`) | python | pip (linux-64, linux-aarch64, osx-arm64, win-64) |
| PyTorch (`pytorch`) | python | pip (linux-64, linux-aarch64, osx-arm64, win-64) |
| py-pol (`py-pol`) | python | pip |
<!-- /routes -->

Sources: [MATLAB command line](https://www.mathworks.com/help/matlab/ref/matlablinux.html), [MATLAB Engine for Python](https://www.mathworks.com/help/matlab/matlab_external/install-the-matlab-engine-for-python.html), [Octave 7](https://octave.org/NEWS-7.html), [Julia command line](https://docs.julialang.org/en/v1/manual/command-line-interface/), [juliaup](https://github.com/JuliaLang/juliaup), [wolframscript](https://reference.wolfram.com/language/ref/program/wolframscript.html), [RawJSON](https://reference.wolfram.com/language/ref/format/RawJSON.html), [Maple command line](https://www.maplesoft.com/support/help/maple/view.aspx?path=maple), [COMSOL batch](https://www.comsol.com/blogs/how-to-run-simulations-in-batch-mode-from-the-command-line), [Lumerical command line](https://optics.ansys.com/hc/en-us/articles/52492316567187-CommandLine-Win-Lin-DesignEnvironmentOptions), [Lumerical on Linux](https://optics.ansys.com/hc/en-us/articles/360024974033-Running-simulations-using-terminal-on-Linux), [jsonsave](https://optics.ansys.com/hc/en-us/articles/360034928313), [CST batch mode](https://deepthoughtdocs.flinders.edu.au/en/latest/software/cststudio.html), [JCMsuite Python](https://www.docs.jcmwave.com/JCMsuite/html/PythonInterface/bf647454e36069fd16f1a7a35cf6a865.html), [FIMMWAVE scripting](https://web.ece.ucsb.edu/oewiki/images/4/4c/Fimmwave_Scripting_Manual.pdf), [FRED automation](https://help.photonengr.com/Topics/AutomationFundamentals.htm), [PySpeos](https://pypi.org/project/ansys-speos-core/), [Tidy3D](https://github.com/flexcompute/tidy3d), [S4](https://web.stanford.edu/group/fan/S4/tutorial.html), [ADDA](https://github.com/adda-team/adda/wiki/Tutorial), [MCX](https://github.com/fangq/mcx), [MMC](https://github.com/fangq/mmc), [Lumerical sessions](https://optics.ansys.com/hc/en-us/articles/360041873053-Session-Management-Python-API), [MPh](https://mph.readthedocs.io/en/stable/api/mph.start.html), [ZOSPy](https://zospy.readthedocs.io/en/stable/api/zospy.zpcore.ZOS.html), [CST Python](https://events.3ds.com/python-driven-automation-electromagnetic-simulations).
