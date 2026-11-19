# Installed software

Every catalogued software has routes: the ways this environment reaches it. `software_details(tool)` lists them; `discover_native_software(tool=...)` lists them with the installations it finds. Discovery reads PATH, the usual installation folders, variables such as `JCMROOT`, the folders given as `roots` and, on Windows, the registry. It starts no software and acquires no license. Each found installation carries the arguments of `bind_native_software`.

| Route | The software | Connect | Run |
| --- | --- | --- | --- |
| python | a module in an interpreter | `prepare_environment` for a recipe; `bind_environment(tool, python)`; a module shipped inside an installation: `bind_native_software(tool, route="python", python, sdk_path)` | `source` |
| session | COMSOL, Lumerical, OpticStudio, CST | `bind_native_software(tool, python, sdk_path, options)` | `action` inspect_project or solve_project; `source` with the session |
| executable | its executable | `bind_native_software(tool, executable)`; Octave, Julia, QuantumOptics.jl and Luna.jl install from recipes | `script` in its language; `source` that drives it with `RUN` |
| automation | a Windows automation (COM) server | `bind_native_software(tool, progid, python)`; the interpreter needs pywin32 | `source` with `APP` |
| service | a client of a running application, server or cloud | a Python binding of the client; the server or account is the user's | `source` |
| inside | scripts that run only inside the application | nothing to bind | a `source` program writes its input files and reads the files it exports |

Bindings keep `threads`, `concurrency`, `requirements` and `env`. Begin licensed software with concurrency 1 and raise it to what the license and the machine allow. A job owns its process tree: cancelling a run stops the executable, and normal completion releases sessions and automation servers. Vendor services started outside that tree follow their own documentation.

## Programs in the software's language

`submit_calculation(tool, script=TEXT, inputs=...)` and workflow steps with `script` run TEXT in the language of the bound executable. The program receives INPUTS and the output folder, and sets RESULT to numbers, strings, lists and objects; complex values and large arrays go to files in the output folder. Sweeps, optimization and workflow bindings work as for Python programs, one folder per point.

| Language | Software | INPUTS | Output folder | Run as |
| --- | --- | --- | --- | --- |
| matlab | MATLAB R2019a+ | struct (jsondecode) | `OUTPUT_DIR` | `matlab -sd FOLDER -batch optics_main` |
| octave | GNU Octave 7+ | struct (jsondecode) | `OUTPUT_DIR` | `octave-cli --no-gui --quiet --norc --no-window-system optics_main.m` |
| julia | Julia, QuantumOptics.jl, Luna.jl | `Dict{String,Any}`; number lists are typed vectors | `OUTPUT_DIR` | `julia --project=ENV --threads=N optics_main.jl` |
| wolfram | Mathematica, Wolfram Engine | Association | `OUTPUTDIR` | `wolframscript -file optics_main.wls` |
| maple | Maple 2015+ | table (JSON:-ParseFile) | `OUTPUT_DIR` | `maple -q optics_main.mpl` (cmaple on Windows) |
| lua | S4 | table; null is nil | `OUTPUT_DIR` | `S4 optics_main.lua` |
| lsf | Lumerical design environments | one variable per input: numbers, strings, numeric vectors and matrices | `OUTPUT_DIR` | `fdtd-solutions -nw -trust-script -exit -run optics_main.lsf` |

A tool outside the catalogue, registered with `register_software(kind="command")`, takes its language at binding: `bind_native_software(tool, executable, language)`. The program is saved as `optics_program` with the language's suffix next to `optics_main`, which defines INPUTS, runs the program and writes RESULT to `script-result.json`; the executable's output is in `script.log`. MATLAB and Octave run the program with `run`, so it may end with local functions. Julia writes a matrix as a list of rows and a named tuple as an object; Lumerical saves RESULT with `jsonsave`, in its own JSON notation. A program that ends without RESULT fails with the end of `script.log`.

```json
{"tool": "octave", "inputs": {"wavelength_um": 1.55, "n": [1.45, 3.48]},
 "script": "k0 = 2*pi/INPUTS.wavelength_um; RESULT = struct('beta', k0*INPUTS.n(:)');",
 "sweep": {"wavelength_um": {"start": 1.5, "stop": 1.6, "points": 11}}}
```

## Python programs that drive an executable

A `source` program of a tool bound to its executable also receives `EXECUTABLE`, `SIBLINGS` (other executables of the installation found beside it, by name), `THREADS` and `RUN(*arguments, program=None, cwd=None, input=None, timeout=None, check=True, log=None)`. RUN runs the executable, or the sibling named `program`, in the output folder, writes its output to `log` (`run-N.log` by default), returns the exit code and raises with the end of the log when `check` and the code is not zero. The program then reads the files the software wrote and saves arrays with `data.save`. The interpreter of these programs is `python` of the binding: by default the scipy environment when one is connected, otherwise this connector's.

- COMSOL: `RUN(*(['batch'] if Path(EXECUTABLE).stem == 'comsol' else []), '-inputfile', INPUTS['model'], '-outputfile', OUTPUT_DIR / 'solved.mph', '-study', 'std1', '-pname', 'wl', '-plist', '1.5[um],1.55[um]')`; `comsolbatch` on Windows takes the options without `batch`.
- Lumerical: the design environment runs `script`; `RUN('-t', THREADS, model, program='fdtd-engine')` solves a saved `.fsp` (`fdtd-engine-msmpi.exe` on Windows).
- CST: `RUN('-m', '-r', project)` solves a project in batch mode; thread options differ between versions.
- ADDA: the packaged program `adda/particle` computes a sphere or an ellipsoid and checks a sphere against the exact series.
- MCX and MMC: their executables read a JSON input file; the Python modules pmcx and pmmc install from recipes.

## Automation servers and services

On Windows `discover_native_software` reads the registered automation names of FRED (`FRED.Application`, `FRED.Document`), CODE V, LightTools and OptiLayer. A `source` program of a tool bound by `progid` holds the server as `APP` for all the points of its process; FRED's `APP.Documents.Open(path)` returns a document whose scripts the program can call. The objects and methods are those of the vendor's automation reference.

Tidy3D reads its key from `SIMCLOUD_APIKEY` or the file that `tidy3d configure` writes; discovery reports only whether either is present. Ansys Speos is reached by PySpeos (`ansys-speos-core`) through the SpeosRPC server of a licensed installation. FIMMWAVE started with `-pt 5101` answers `pdPythonLib.pdApp().ConnectToApp()`; bind the folder of `pdPythonLib.py` as `sdk_path`.

## Sessions

`bind_native_software(tool, python, sdk_path, options, threads, concurrency)` selects the interpreter and SDK of COMSOL (MPh), Lumerical (`lumapi` or `ansys.lumerical.core`), OpticStudio (ZOSPy) or CST (`cst.interface`, `cst.results`); module discovery does not start or verify a licensed solver. Install a bridge package in the selected environment only when needed. The input `project` is an absolute path on the computing machine. The worker creates a new owned session, opens the model and saves its working copy in OUTPUT_DIR before the program runs; all iterations within a program reuse that session, and success saves the model again.

The program receives `SDK`, `SESSION`, `MODEL`, `PROJECT_FILE`, `EXPORT`, `INPUTS`, `OUTPUT_DIR`, and sets `RESULT`. `EXPORT(value, name)` saves arrays and complex values in NPZ with their structure in JSON. `inspect_project` opens and saves without solving. `solve_project` takes, for COMSOL, `parameters` as names to values with units, an optional `study` and `results` as expressions; for Lumerical, `parameters` as object to property to value and `results` as [{monitor, quantity}]; for CST, `results` as result-tree paths. OpticStudio analyses use a source program. Read project-specific names rather than inventing monitor paths or expressions.

Lumerical options: `module` (lumapi or ansys.lumerical.core), `product` (FDTD, MODE, DEVICE, INTERCONNECT), `hide`. COMSOL option: `version`. OpticStudio options: `opticstudio_directory` or `zosapi_nethelper`, not both; its session runs standalone on Windows. COMSOL and Lumerical receive the thread count; CST and OpticStudio use their own CPU settings.

An agent on another computer reaches a workstation's software by running this MCP server there over SSH.
