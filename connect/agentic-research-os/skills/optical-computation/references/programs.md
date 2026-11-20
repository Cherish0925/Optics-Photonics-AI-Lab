# Programs

## Packaged programs

Each is an ordinary native program in `optics_photonics/programs/TOOL/`: Python, or the language of software bound to its executable (Julia for QuantumOptics.jl, Lua for S4, the MATLAB language for GNU Octave and MATLAB), declared in its leading comment. `software_details(tool)` lists a tool's programs with the names of their inputs; `software_details(tool, program=NAME)` returns one program with its physics and conventions, every input's default and meaning, its results and checks, and with `source=true` its text to adapt. `submit_calculation(tool, action=NAME, inputs={...})` runs one with the given inputs replacing the defaults; an unknown input name is rejected at submission. Indices may be numbers, `[n, k]` or material names where the inputs say so. Arrays are saved with units and axes; `checks` in the result compare with a conservation law or an analytic limit.

| Program | Computes | Compared with |
| --- | --- | --- |
| `tmm/spectrum` | R, T, A of a planar multilayer over wavelength, angle and polarization; coherent or incoherent layers | energy balance; RCWA; quarter-wave coating |
| `grcwa/film` | R, T of uniform layers by RCWA | transfer matrix |
| `grcwa/grating` | Efficiency per diffraction order of a lamellar grating, TE and TM | energy balance; uniform-layer and effective-medium limits |
| `grcwa/metasurface` | Zeroth-order transmission and phase of a lattice of round pillars over diameter; phase coverage and a library of diameters for 2π/levels steps | energy balance; Fresnel transmission without pillars |
| `meep/stack` | R, T of a layered stack by FDTD | transfer matrix, second-order convergence |
| `meep/ring` | Ring-resonator modes: frequency, Q by Harminv; final field | Meep tutorial values |
| `mpb/bands` | Bands and complete gaps of 2-D lattices of rods or holes, TE and TM | rod-lattice TM gap 0.3225–0.4425 |
| `mpb/waveguide` | Guided modes of a strip or rib waveguide: effective and group index, polarization, mode intensity | analytic slab mode, second-order convergence |
| `tidy3d/modes` | Full-vector modes of a strip or rib waveguide by Tidy3D's mode solver on this computer, without an account: effective and group index, TE fraction, effective area, power in the core, mode intensity | slab dispersion relation for TE0 |
| `legume/bands` | Bands of 2-D crystals (plane waves) and slabs (guided modes) | MPB |
| `s4/crystal_slab` | Transmission and reflection of a photonic-crystal slab over frequency, with its Fano lines (Lua on an installed S4) | energy balance; Airy formula for the slab without holes |
| `treams/cluster` | Scattering, extinction and absorption of sphere clusters with multiple scattering; orientation averages | Mie series; energy balance |
| `miepython/sphere` | Mie efficiencies, cross sections, asymmetry, angular pattern | Rayleigh limit; angular integral |
| `adda/particle` | Extinction, scattering and absorption efficiencies and S11 over angle of a sphere or an ellipsoid by the discrete dipole approximation; runs an installed ADDA | exact series for a sphere, converging as dipoles get finer |
| `ngsolve/scattering` | Plane wave on a dielectric or metal cylinder in 2-D by finite elements with a perfectly matched layer, TM or TE: Q_sca, Q_abs, field map; a template for other cross-sections | exact Bessel–Hankel series: field on a circle and Q_sca |
| `hcipy/psf` | PSF with obstruction and Zernike aberrations; Strehl, encircled energy | Airy encircled energy; Maréchal |
| `poppy/psf` | PSF on a detector with Zernike aberrations; Strehl | HCIPy |
| `lightpipes/gaussian` | Gaussian beam propagation (Forvard or Fresnel); complex field | w(z) |
| `diffractio/apertures` | Rayleigh-Sommerfeld diffraction of a slit, double slit or grating from near to far field | Fraunhofer expression |
| `prysm/mtf` | MTF along x and y with Zernike aberrations; PSF; Strehl | diffraction-limited MTF |
| `scipy/slab_modes` | Guided modes of any layered slab, TE or TM, by finite differences | symmetric-slab dispersion relation |
| `scipy/fiber_modes` | Step-index fiber: effective indices of every LP and exact vector (TE, TM, HE, EH) mode over wavelength; LP11 cutoff; group index, dispersion, β2, mode field diameter, effective area and γ of the fundamental mode, with material dispersion | Bessel roots to 13 digits; MPB for vector modes; closed-form confinement |
| `scipy/second_harmonic` | Second-harmonic generation in a uniaxial crystal: type I, type II or quasi-phase-matching angle or period, walk-off, angle and wavelength acceptance; conversion with pump depletion | literature BBO angle and walk-off; tanh² and sinc² limits |
| `scipy/nlse` | Fiber pulse propagation: dispersion, self-phase modulation, third-order dispersion, loss | soliton; dispersive broadening; energy |
| `laserfun/supercontinuum` | Generalized NLSE with Raman scattering and self-steepening: solitons and supercontinuum | photon-number conservation; Dudley benchmark |
| `octave/bragg_grating` | Fiber Bragg grating, uniform, apodized or chirped: reflectance, transmittance and reflected group delay over wavelength by coupled-mode theory (MATLAB language; runs in GNU Octave and in MATLAB) | closed form of the uniform grating: spectrum, tanh² peak and delay; energy balance |
| `scipy/metalens` | Metalens from a unit-cell library: pillar of each cell by the hyperbolic phase, focal spot by angular-spectrum propagation; FWHM, Strehl ratio, focusing efficiency | Airy width of the ideal lens; energy of the propagation |
| `scipy/resonator` | Gaussian eigenmode of a two-mirror or any ABCD resonator: stability, waists, mirror spots, Gouy phase, FSR, transverse mode spacing, TEM_mn offsets | closed-form two-mirror expressions |
| `scipy/laser_rates` | Semiconductor laser L–I curve and step response | threshold, slope, relaxation frequency |
| `ceviche/bend` | Inverse design of a waveguide bend: topology optimization by adjoint gradients in 2-D FDFD; density, binary device, field, transmission per iteration | finite-difference gradient; binary device simulated again |
| `scipy/coupler` | Directional coupler from its even and odd supermodes: transfer length and coupling over length and wavelength; effective and group index of one core | coupled-mode theory, exact as the gap grows |
| `sax/circuit` | Mach-Zehnder interferometer, all-pass and add-drop ring transmission from component models; resonances, Q, FSR | analytic transfer functions |
| `finesse/cavity` | Fabry-Perot transmission, reflection and stored power over frequency; linewidth, finesse, buildup | Airy function |
| `opticomm/ber` | Bit and symbol error rates and GMI of QAM, PSK or PAM over additive noise and phase noise | theoretical BER |
| `solcore/detailed_balance` | Detailed-balance solar-cell efficiency, Voc, Jsc and fill factor over band gap | currents integrated from the spectrum and Planck's law |
| `scipy/fit_gaussian` | Least-squares Gaussian fit | residual |
| `qutip/rabi` | Rabi oscillation of a two-level system | sin²(Ωt/2) |
| `qutip/jaynes_cummings` | Emitter–cavity dynamics with losses; dressed states | one-excitation solution |
| `qutip/resonance_fluorescence` | Mollow spectrum, g²(τ), steady state | analytic population; g²(0) = 0 |
| `quantumoptics/jaynes_cummings` | Rabi oscillations and damped atom–cavity dynamics from the Schrödinger or master equation (Julia, QuantumOptics.jl) | exact population without losses; excitation number |
| `perceval/interference` | Output probabilities of photons in a beam splitter, Fourier or random interferometer, with partial distinguishability and loss | permanents; Hong-Ou-Mandel formula |
| `strawberry/gaussian_state` | Squeezed, displaced and lossy Gaussian states: quadrature variances, photon statistics, g2(0) | analytic squeezed vacuum |
| `sympy/fresnel` | Fresnel coefficients derived from the boundary conditions | Brewster identity; energy balance |
| `sympy/abcd` | Symbolic ABCD matrix of space, lens, space | lens law |
| `raytracing/abcd` | Paraxial ray transfer through spaces and thin lenses | unit determinant |
| `optiland/lens` | Lens analysis: focal length, back focus, f-number, pupils; Seidel sums and transverse aberrations per surface; axial colour; real-ray spot radii over field and wavelength | independent paraxial trace; real rays at small aperture; lensmaker's equation |
| `optiland/trace` | Real rays through a sequential lens prescription | rotational symmetry |
| `py-pol/polarization` | Jones calculus through polarizers and wave plates; Stokes output | Malus's law |
| `srw/undulator` | On-axis spectrum of a planar undulator and the flux density across the central cone at the fundamental (single-electron synchrotron radiation) | formulas of the harmonic energy and the peak flux density |
| `scipy/tissue_layers` | Layered tissue by Monte Carlo photon transport: diffuse reflectance, transmittance, absorbed fraction per layer and over depth, fluence rate, reflectance over the distance from the beam, each with its standard error | matched slab of known reflectance and transmittance; energy balance |
| `scikitimage/registration` | Subpixel translation between images | |
| `pyvisa/sweep` | Step a setting of a laboratory instrument and read a value at each step, with the time of each reading; lists the instruments found; a simulated source when no instrument is given | readback of the simulated source |
| `bluesky/scan` | Scan a motor through a peak, fit it and scan again around the fitted centre: a Bluesky plan with its documents, on simulated ophyd devices | centre and width of the simulated detector |
| `gdsfactory/waveguide` | Waveguide layout with ports, GDSII | KLayout readback |
| `klayout/layout` | Rectangles to GDSII | |

**Chaining programs.** One program's RESULT feeds another's inputs through `bindings` in `submit_workflow`. The fundamental mode of a fiber gives the dispersion and nonlinearity of a pulse propagation:

```json
[{"id": "fiber", "tool": "scipy", "action": "fiber_modes", "inputs": {"wavelength_nm": [1550]}},
 {"id": "pulse", "tool": "scipy", "action": "nlse", "after": ["fiber"], "inputs": {"peak_power_W": 16},
  "bindings": {"beta2_ps2_per_km": {"step": "fiber", "path": ["result", "fundamental", "beta2_ps2_per_km"]},
               "gamma_per_W_km": {"step": "fiber", "path": ["result", "fundamental", "gamma_per_W_km"]}}}]
```

A file passes the same way: the unit-cell library of `grcwa/metasurface` lays out a metalens and focuses it.

```json
[{"id": "cells", "tool": "grcwa", "action": "metasurface", "inputs": {}},
 {"id": "lens", "tool": "scipy", "action": "metalens", "after": ["cells"], "inputs": {"focal_um": 30, "aperture_um": 30},
  "bindings": {"library": {"step": "cells", "file": "library.npz"}}}]
```

A device becomes a circuit: the coupling of a directional coupler and the indices of its waveguide set a ring resonator's response.

```json
[{"id": "coupler", "tool": "scipy", "action": "coupler", "inputs": {"gap_um": 0.2, "length_um": 5}},
 {"id": "ring", "tool": "sax", "action": "circuit", "after": ["coupler"],
  "inputs": {"circuit": "ring", "ring_length_um": 60, "wavelength_um": {"start": 1.5, "stop": 1.6, "points": 20001}},
  "bindings": {"coupling": {"step": "coupler", "path": ["result", "coupling"]},
               "neff": {"step": "coupler", "path": ["result", "n_single"]},
               "ng": {"step": "coupler", "path": ["result", "ng_single"]},
               "wl0_um": {"step": "coupler", "path": ["result", "centre_wavelength_um"]}}}]
```

## Writing programs

**Python.** The submitted `source` runs once in the interpreter bound to the tool. It receives `INPUTS` (the step inputs with bound values) and `OUTPUT_DIR` (a `pathlib.Path` owned by this attempt), and must set `RESULT` to compact JSON. Everything else is the software's own API. Write arrays as NPY or NPZ, and models, meshes and plots in their native formats, under OUTPUT_DIR; `read_array` and `result_files` then show them without loading whole files. Record units, coordinate frames, sign and normalization conventions with the data. Each attempt of a step has its own directory `STEP/attempt-N/`, so parallel steps never share files.

**Another language.** `script` runs a program in the language of software bound to its executable: MATLAB, Octave, Julia, Wolfram Language, Maple, Lua (S4) or Lumerical script. It receives INPUTS and the output folder and sets RESULT ([native-software](native-software.md)). Arrays returned as `RESULT.save = {file, arrays: {name: {values, quantity, unit, axes}}}` are written as described NPZ, so `read_array` and later steps read them like those of Python programs. A Python `source` of such a tool drives its executable with `RUN(arguments)`.

**Executable of your own.** A program in any language reads JSON from the file named by `OPTICS_REQUEST_FILE` (or standard input), writes files under `OPTICS_OUTPUT_DIR` and writes its JSON result to `OPTICS_RESULT_FILE`. Bind it with `bind_environment(tool, command=[executable, argument, ...])`; the optional placeholders `{request}`, `{output}` and `{result}` are replaced in the arguments. Compiled C, C++, C#, Java and Fortran programs use this interface unchanged.

**Tool outside the catalogue.** `register_software(tool, name, description, kind, modules, distributions, sources)` records a local library, solver or executable under a new ID; `kind` is `python` or `command`. Then bind its interpreter or executable with `bind_environment`. `registered_software` lists local tools and `software_details` describes one. A registered tool uses the same submission, workflow and result tools; a Python binding also supports `sample_episodes`. Registration does not install software or grant a license.

**Command line.** Without MCP, `optics-photonics` (or `python -m optics_photonics`) offers the same operations: `search`, `info`, `register-software`, `registered-software`, `environments`, `prepare`, `bind`, `discover`, `bind-native`, `resources`, `run`, `submit`, `submit-workflow`, `sample`, `runs`, `status`, `files`, `read`, `array`, `download`, `cancel`, `resume`, `connect`. `run TOOL NAME` runs a packaged program and `info TOOL --program NAME` prints its source; `--inputs "@inputs.json"` reads inputs from a file, `--program research.py` submits a full program, `--script model.m` a program in the software's own language, `discover --tool matlab` finds an installation, and `search --license-group open` selects open-source tools. `tools` lists the MCP tools and `call TOOL JSON` invokes one.
