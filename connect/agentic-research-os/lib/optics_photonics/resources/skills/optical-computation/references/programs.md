# Programs

## Packaged programs

Each is an ordinary native program in `optics_photonics/programs/TOOL/NAME.py`. `software_details(tool)` lists a tool's programs with every input's default and meaning; `submit_calculation(tool, action=NAME, inputs={...})` runs one with the given inputs replacing the defaults, and an unknown input name is rejected at submission. `software_details(tool, program=NAME)` returns the source to adapt. Indices may be numbers, `[n, k]` or material names where the inputs say so. Arrays are saved with units and axes; `checks` in the result compare with a conservation law or an analytic limit.

| Program | Computes | Compared with |
| --- | --- | --- |
| `tmm/spectrum` | R, T, A of a planar multilayer over wavelength, angle and polarization; coherent or incoherent layers | energy balance; RCWA; quarter-wave coating |
| `grcwa/film` | R, T of uniform layers by RCWA | transfer matrix |
| `grcwa/grating` | Efficiency per diffraction order of a lamellar grating, TE and TM | energy balance; uniform-layer and effective-medium limits |
| `meep/stack` | R, T of a layered stack by FDTD | transfer matrix, second-order convergence |
| `meep/ring` | Ring-resonator modes: frequency, Q by Harminv; final field | Meep tutorial values |
| `mpb/bands` | Bands and complete gaps of 2-D lattices of rods or holes, TE and TM | rod-lattice TM gap 0.3225–0.4425 |
| `mpb/waveguide` | Guided modes of a strip or rib waveguide: effective and group index, polarization, mode intensity | analytic slab mode, second-order convergence |
| `legume/bands` | Bands of 2-D crystals (plane waves) and slabs (guided modes) | MPB |
| `treams/cluster` | Scattering, extinction and absorption of sphere clusters with multiple scattering; orientation averages | Mie series; energy balance |
| `miepython/sphere` | Mie efficiencies, cross sections, asymmetry, angular pattern | Rayleigh limit; angular integral |
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
| `scipy/laser_rates` | Semiconductor laser L–I curve and step response | threshold, slope, relaxation frequency |
| `sax/circuit` | Mach-Zehnder interferometer, all-pass and add-drop ring transmission from component models; resonances, Q, FSR | analytic transfer functions |
| `finesse/cavity` | Fabry-Perot transmission, reflection and stored power over frequency; linewidth, finesse, buildup | Airy function |
| `opticomm/ber` | Bit and symbol error rates and GMI of QAM, PSK or PAM over additive noise and phase noise | theoretical BER |
| `solcore/detailed_balance` | Detailed-balance solar-cell efficiency, Voc, Jsc and fill factor over band gap | currents integrated from the spectrum and Planck's law |
| `scipy/fit_gaussian` | Least-squares Gaussian fit | residual |
| `qutip/rabi` | Rabi oscillation of a two-level system | sin²(Ωt/2) |
| `qutip/jaynes_cummings` | Emitter–cavity dynamics with losses; dressed states | one-excitation solution |
| `qutip/resonance_fluorescence` | Mollow spectrum, g²(τ), steady state | analytic population; g²(0) = 0 |
| `perceval/interference` | Output probabilities of photons in a beam splitter, Fourier or random interferometer, with partial distinguishability and loss | permanents; Hong-Ou-Mandel formula |
| `strawberry/gaussian_state` | Squeezed, displaced and lossy Gaussian states: quadrature variances, photon statistics, g2(0) | analytic squeezed vacuum |
| `sympy/fresnel` | Fresnel coefficients derived from the boundary conditions | Brewster identity; energy balance |
| `sympy/abcd` | Symbolic ABCD matrix of space, lens, space | lens law |
| `raytracing/abcd` | Paraxial ray transfer through spaces and thin lenses | unit determinant |
| `optiland/trace` | Real rays through a sequential lens prescription | rotational symmetry |
| `py-pol/polarization` | Jones calculus through polarizers and wave plates; Stokes output | Malus's law |
| `scikitimage/registration` | Subpixel translation between images | |
| `gdsfactory/waveguide` | Waveguide layout with ports, GDSII | KLayout readback |
| `klayout/layout` | Rectangles to GDSII | |

## Writing programs

**Python.** The submitted `source` runs once in the interpreter bound to the tool. It receives `INPUTS` (the step inputs with bound values) and `OUTPUT_DIR` (a `pathlib.Path` owned by this attempt), and must set `RESULT` to compact JSON. Everything else is the software's own API. Write arrays as NPY or NPZ, and models, meshes and plots in their native formats, under OUTPUT_DIR; `read_array` and `result_files` then show them without loading whole files. Record units, coordinate frames, sign and normalization conventions with the data. Each attempt of a step has its own directory `STEP/attempt-N/`, so parallel steps never share files.

**Executable.** A program in any language reads JSON from the file named by `OPTICS_REQUEST_FILE` (or standard input), writes files under `OPTICS_OUTPUT_DIR` and writes its JSON result to `OPTICS_RESULT_FILE`. Bind it with `bind_environment(tool, command=[executable, argument, ...])`; the optional placeholders `{request}`, `{output}` and `{result}` are replaced in the arguments. C, C++, C#, Java, Julia and vendor batch programs use this interface unchanged.

**Tool outside the catalogue.** `register_software(tool, name, description, kind, modules, distributions, sources)` records a local library, solver or executable under a new ID; `kind` is `python` or `command`. Then bind its interpreter or executable with `bind_environment`. `registered_software` lists local tools and `software_details` describes one. A registered tool uses the same submission, workflow and result tools; a Python binding also supports `sample_episodes`. Registration does not install software or grant a license.

**Command line.** Without MCP, `optics-photonics` (or `python -m optics_photonics`) offers the same operations: `search`, `info`, `register-software`, `registered-software`, `environments`, `prepare`, `bind`, `discover`, `bind-native`, `resources`, `run`, `submit`, `submit-workflow`, `sample`, `runs`, `status`, `files`, `read`, `array`, `download`, `cancel`, `resume`, `connect`. `run TOOL NAME` runs a packaged program and `info TOOL --program NAME` prints its source; `--inputs "@inputs.json"` reads inputs from a file, `--program research.py` submits a full program, and `search --license-group open` selects open-source tools. `tools` lists the MCP tools and `call TOOL JSON` invokes one.
