# Start an optical task

Choose a physical question, the relevant software and the computer where it can run. The default catalogue contains open-source research tasks. The wider software reference includes optional commercial connections; it is not an installation list.

## First calculation

Give an agent this task:

> Calculate the reflectance of a 100 nm, index 1.45 film between air and an index 1.52 substrate at 450, 550 and 650 nm. Use the optics environment on the selected computing host. Reuse an existing tmm installation or prepare its recipe. Return the spectrum and run ID with the model assumptions.

Through MCP: `software_search("thin film")`, `software_details(tool="tmm", program="spectrum")`, then `submit_calculation(tool="tmm", action="spectrum", inputs={"n":[1,1.45,1.52],"thickness_nm":[100],"wavelength_nm":[450,550,650]}, wait=25)`. Missing software with a supported recipe is prepared on submission. If still running, use `run_status` with the returned ID.

For installation before research, select task module IDs (such as thin-film-spectra or waveguide-modes) with `environment_plan` and `environment_prepare`; individual software IDs remain accepted. `environment_installed` reports existing bindings. A domain is a way to browse; choose the software needed for the task.

## Which computer?

| Software route | Where it runs |
| --- | --- |
| pip, conda or Julia recipe | An isolated environment on the selected host; the recipe states platform and Python requirements |
| Existing Python installation | Bind that interpreter; it may already belong to SeedEnv or another project |
| Installed application or SDK | A workstation with its software and licence; discover and bind it there |
| Windows automation | A Windows workstation; a Linux server connects to its MCP server over SSH |
| Cloud/service API | The provider's service through its configured client |
| Scripts inside a GUI application | That application; exchange its input and output files |

Installing a Python instrument client does not install every vendor driver or connect a physical device. Likewise, a GPU solver's package can be installed before its required GPU runtime is available. Read the selected software's installation note and native interface.

## Find the relevant material

| Need | Entry |
| --- | --- |
| Choose a model or research direction | `read_guide(topic="optical-research")`, then its domain reference |
| Program inputs or an editable example | `software_details`, with a program name; request source when adapting |
| Studies, data exchange or continued work | The corresponding reference in optical-computation |
| A task prompt | calculate, study, reproduce, connect, measure or continue |
| Product/plugin installation | The hosts reference |

## Work with other environments

Optics owns optical models, solver bindings and calculations. SeedEnv supplies shared computing and writing tools; bind an existing suitable interpreter instead of installing it again. IOP owns connected instruments and experiment sequences; use its existing client for a shared device. Synthetic-Lab owns its simulated task environments. Data Engineering, Agent Gym and AI Evaluation consume data, trajectories or task results through their respective interfaces.

The host product owns which computer is selected and how the plugin is enabled. Connection settings and runs live under OPTICS_HOME (default ~/.optics-photonics). Software uses OPTICS_SOFTWARE_HOME when configured, otherwise OPTICS_HOME/environments. Research OS places new software in System/software/optics-photonics and keeps state in its existing System/state location. Earlier installations are reused in place. Knowledge, Skills and workflows stay in the package and are exposed through their resource entries, so updates do not leave duplicate copies. Unloading a plugin does not delete research data; `environment_remove` handles selected software and retains shared installations.
