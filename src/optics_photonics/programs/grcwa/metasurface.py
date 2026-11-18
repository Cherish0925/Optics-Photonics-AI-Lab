"""Transmission amplitude and phase of a metasurface of cylindrical pillars over pillar diameter (RCWA), a phase library.

grcwa solves a square lattice of period P of round pillars of height H on a
substrate, lit at normal incidence from the substrate by a plane wave
polarized along x. For each diameter it gives the power transmitted into the
zeroth order of the medium above the pillars (the only propagating order
when P is below the wavelength in both media) and the phase of that order's
electric field relative to the same layer without pillars. The phase
coverage over the diameters and, for a lens or a deflector with 2 pi / levels
phase steps, the diameter whose phase is nearest each level with its
transmission, form a phase library for a metalens design. Indices are
numbers, [n, k] or materials; lengths in micrometres. Results converge with
the number of Fourier orders and with the grid that samples the unit cell.
"""
import math
import numpy as np
import grcwa
from optics_photonics import data, materials
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'wavelength_um': (1.55, 'vacuum wavelength in micrometres'),
        'period_um': (0.6, 'lattice period in micrometres'),
        'height_um': (0.9, 'pillar height in micrometres'),
        'diameters_um': ({'start': 0.1, 'stop': 0.5, 'points': 41}, 'pillar diameters in micrometres, or {"start", "stop", "points"}'),
        'pillar': (3.48, 'pillar index: number, [n, k] or material (amorphous silicon near 1.55 um by default)'),
        'cladding': (1.0, 'index around the pillars and above them'),
        'substrate': ('SiO2', 'index of the substrate the light comes from'),
        'levels': (8, 'phase levels of the library, 2 pi / levels apart'),
        'orders': (241, 'Fourier orders retained'),
        'grid': (256, 'samples of the unit cell along each side'),
    },
    'results': 'library.npz/.json: zeroth-order transmission, relative phase (unwrapped), total R and T over diameter; '
               'phase coverage and the diameter chosen for each phase level',
    'checks': 'energy_error: largest |1 - R - T| for lossless media; fresnel_difference: the cell without pillars against the Fresnel '
              'transmission of the substrate-cladding interface; single_order: whether only the zeroth order propagates',
}
p = parameters(PROGRAM, INPUTS)
wavelength, period, height = float(p['wavelength_um']), float(p['period_um']), float(p['height_um'])
spec = p['diameters_um']
diameters = (np.linspace(float(spec['start']), float(spec['stop']), int(spec['points'])) if isinstance(spec, dict)
             else np.atleast_1d(np.asarray(spec, float)))
if wavelength <= 0 or period <= 0 or height < 0 or np.any(diameters < 0) or np.any(diameters > period) or int(p['levels']) < 2:
    raise ValueError('wavelength_um and period_um are positive, diameters lie between 0 and period_um and levels is at least 2')
pages = {}


def index(entry):
    if isinstance(entry, str):
        pages[entry] = materials.resolve(entry)
        return materials.index_at(entry, wavelength)
    return complex(entry[0], entry[1]) if isinstance(entry, (list, tuple)) else complex(entry)


n_pillar, n_clad, n_sub = index(p['pillar']), index(p['cladding']), index(p['substrate'])
lossless = all(abs(n.imag) < 1e-12 for n in (n_pillar, n_clad, n_sub))
cells = int(p['grid'])
coordinate = (np.arange(cells) + 0.5) / cells * period - period / 2
x, y = np.meshgrid(coordinate, coordinate, indexing='ij')


def solve(diameter):
    """Zeroth-order transmitted power, complex Ex of that order above the pillars, and total R and T."""
    solver = grcwa.obj(int(p['orders']), [period, 0], [0, period], 1 / wavelength, 0.0, 0.0, verbose=0)
    solver.Add_LayerUniform(0, n_sub ** 2)
    solver.Add_LayerGrid(height, cells, cells)
    solver.Add_LayerUniform(0, n_clad ** 2)
    solver.Init_Setup(Gmethod=0)
    solver.GridLayer_geteps(np.where(x ** 2 + y ** 2 <= (diameter / 2) ** 2, n_pillar ** 2, n_clad ** 2).flatten())
    solver.MakeExcitationPlanewave(p_amp=1, p_phase=0, s_amp=0, s_phase=0, order=0)
    reflected, transmitted = solver.RT_Solve(normalize=1, byorder=1)
    zero = int(np.flatnonzero((solver.G[:, 0] == 0) & (solver.G[:, 1] == 0))[0])
    fields, _ = solver.Solve_FieldFourier(2, 0.0)
    return float(np.real(transmitted[zero])), complex(np.asarray(fields[0])[zero]), float(np.real(np.sum(reflected))), float(np.real(np.sum(transmitted)))


empty, reference, _, _ = solve(0.0)
rows = [solve(d) for d in diameters]
zeroth = np.array([row[0] for row in rows])
phase = np.unwrap(np.angle(np.array([row[1] for row in rows]) / reference))
R = np.array([row[2] for row in rows])
T = np.array([row[3] for row in rows])

# Only the zeroth order propagates when the period is below the wavelength in both outer media.
single_order = period < wavelength / max(n_sub.real, n_clad.real)
coverage = float(phase.max() - phase.min())
levels = int(p['levels'])
library = []
wrapped = np.mod(phase - phase[0], 2 * math.pi)
for level in range(levels):
    target = 2 * math.pi * level / levels
    distance = np.abs(np.angle(np.exp(1j * (wrapped - target))))
    best = int(np.argmin(distance - 1e-3 * zeroth))           # nearest phase; among equals the higher transmission
    library.append({'phase_rad': target, 'diameter_um': float(diameters[best]), 'phase_error_rad': float(distance[best]),
                    'transmission': float(zeroth[best])})
saved = data.save(OUTPUT_DIR / 'library', {
    'diameter_um': data.quantity(diameters, 'pillar diameter', unit='um'),
    'transmission': data.quantity(zeroth, 'power transmitted into the zeroth order', unit='1', axes=['diameter_um'], materials=pages),
    'phase': data.quantity(phase, 'phase of the zeroth-order Ex relative to the layer without pillars, unwrapped', unit='rad',
                           axes=['diameter_um'], time_dependence='exp(-i omega t)'),
    'R': data.quantity(R, 'total reflectance', unit='1', axes=['diameter_um']),
    'T': data.quantity(T, 'total transmittance', unit='1', axes=['diameter_um']),
})
RESULT = {'data': saved['data'], 'phase_coverage_rad': coverage, 'full_coverage': coverage >= 2 * math.pi,
          'mean_transmission': float(zeroth.mean()), 'library': library,
          'library_mean_transmission': float(np.mean([entry['transmission'] for entry in library])), 'materials': pages,
          'checks': {'energy_error': float(np.max(np.abs(1 - R - T))) if lossless else None,
                     'fresnel_difference': abs(empty - 4 * n_sub.real * n_clad.real / (n_sub.real + n_clad.real) ** 2) if lossless else None,
                     'single_order': bool(single_order)}}
