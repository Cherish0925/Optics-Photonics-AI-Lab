"""Guided modes of a strip or rib waveguide cross-section (Tidy3D mode solver, on this computer).

Tidy3D's mode solver discretizes the cross-section on the Yee grid and
solves the full-vector eigenproblem for fields varying as
exp(i(beta x - w t)); it runs locally and needs no account, unlike a
Tidy3D simulation. The core is a rectangle of width and height on a
substrate, under a cladding, with an optional slab of the core material
beside it (a rib). An index is a number, [n, k] or a material from the
materials tool at the wavelength. For each mode the program reports the
effective index, the group index, the fraction of the transverse electric
field energy along the width (near 1 for a quasi-TE mode), the effective
area and the share of the power in the core. The grid is refined from
steps_per_wavelength; without subpixel averaging the index converges
linearly with the grid step. The same solver computes the slab of the same
height, uniform along the width, and its TE0 index is compared with the
root of the slab dispersion relation.
"""
import warnings
import numpy as np
from scipy.optimize import brentq
import tidy3d as td
from tidy3d.plugins.mode import ModeSolver
from optics_photonics import data, materials
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'width_um': (0.5, 'core width in micrometres'),
        'height_um': (0.22, 'core height in micrometres'),
        'slab_um': (0.0, 'thickness of the core-material slab beside the core; 0 for a strip'),
        'core': (3.476, 'core index: number, [n, k] or material name (Si, Si3N4, ...)'),
        'substrate': (1.444, 'index below the core: number, [n, k] or material name'),
        'cladding': (1.444, 'index above and beside the core: number, [n, k] or material name'),
        'wavelength_um': (1.55, 'vacuum wavelength in micrometres'),
        'modes': (4, 'modes to compute, by decreasing effective index'),
        'steps_per_wavelength': (30, 'grid steps per wavelength in each material'),
        'margin_um': (1.5, 'distance from the core to the boundary of the computed window'),
    },
    'results': 'modes.npz/.json with the field intensity of each mode over the cross-section; per mode n_eff, group index, TE fraction, effective area, power in the core',
    'checks': 'slab_difference: TE0 index of the slab of the same height by the same solver minus the root of the analytic dispersion relation',
}
p = parameters(PROGRAM, INPUTS)
width, height, slab, margin = (float(p[key]) for key in ('width_um', 'height_um', 'slab_um', 'margin_um'))
wavelength, count = float(p['wavelength_um']), int(p['modes'])
if min(width, height, wavelength, margin) <= 0 or not 0 <= slab < height or count < 1 or p['steps_per_wavelength'] < 6:
    raise ValueError('width_um, height_um, wavelength_um and margin_um are positive, slab_um lies in [0, height_um), '
                     'modes >= 1 and steps_per_wavelength >= 6')
pages, frequency = {}, td.C_0 / wavelength
td.config.logging.level = 'ERROR'


def index(entry):
    if isinstance(entry, str):
        pages[entry] = materials.resolve(entry)
        return materials.index_at(entry, wavelength)
    return complex(entry[0], abs(entry[1])) if isinstance(entry, (list, tuple)) else complex(entry)


n_core, n_substrate, n_cladding = index(p['core']), index(p['substrate']), index(p['cladding'])
if n_core.real <= max(n_substrate.real, n_cladding.real):
    raise ValueError('The core index must exceed the substrate and cladding indices')
medium = lambda n: td.Medium.from_nk(n=n.real, k=n.imag, freq=frequency)


def solve(core_width, modes):
    """Modes of the cross-section in the plane x = 0: y along the width, z along the height, the substrate below z = 0."""
    span_y, span_z = width + 2 * margin, height + 2 * margin
    structures = [td.Structure(geometry=td.Box.from_bounds((-1, -span_y, -span_z), (1, span_y, 0)), medium=medium(n_substrate)),
                  td.Structure(geometry=td.Box.from_bounds((-1, -core_width / 2, 0), (1, core_width / 2, height)), medium=medium(n_core))]
    if slab:
        structures.insert(1, td.Structure(geometry=td.Box.from_bounds((-1, -span_y, 0), (1, span_y, slab)), medium=medium(n_core)))
    simulation = td.Simulation(
        center=(0, 0, height / 2), size=(1, span_y, span_z), structures=structures, medium=medium(n_cladding), run_time=1e-12,
        grid_spec=td.GridSpec.auto(min_steps_per_wvl=float(p['steps_per_wavelength']), wavelength=wavelength),
        boundary_spec=td.BoundarySpec.all_sides(td.PML()))
    spec = td.ModeSpec(num_modes=modes, target_neff=n_core.real, group_index_step=True)
    solver = ModeSolver(simulation=simulation, plane=td.Box(center=(0, 0, height / 2), size=(0, span_y, span_z)), mode_spec=spec,
                        freqs=[frequency])
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        return solver.solve()


found = solve(width, count)
n_eff = np.asarray(found.n_complex).reshape(-1)
group = np.asarray(found.n_group).reshape(-1)
te = np.asarray(found.pol_fraction.te).reshape(-1)
area = np.asarray(found.mode_area).reshape(-1)
y, z = np.asarray(found.Ey.y), np.asarray(found.Ey.z)
fields = {name: np.moveaxis(np.asarray(getattr(found, name).interp(y=y, z=z).values).reshape(len(y), len(z), -1), -1, 0)
          for name in ('Ex', 'Ey', 'Ez')}
intensity = sum(np.abs(part) ** 2 for part in fields.values())
intensity /= intensity.max(axis=(1, 2), keepdims=True)
# Power along the guide, Re(E x H*) . x, and its share inside the core rectangle.
flux = np.real(sum(sign * np.asarray(getattr(found, e).interp(y=y, z=z).values) * np.conj(np.asarray(getattr(found, h).interp(y=y, z=z).values))
                   for sign, e, h in ((1, 'Ey', 'Hz'), (-1, 'Ez', 'Hy'))))
flux = np.moveaxis(flux.reshape(len(y), len(z), -1), -1, 0)
inside = (np.abs(y)[:, None] <= width / 2) & (z[None, :] >= 0) & (z[None, :] <= height)
weights = np.gradient(y)[:, None] * np.gradient(z)[None, :]
core_power = (flux * weights * inside).sum(axis=(1, 2)) / (flux * weights).sum(axis=(1, 2))
guided = n_eff.real > max(n_substrate.real, n_cladding.real)


def slab_te0():
    """Root of the TE dispersion relation of the three-layer slab: substrate, core of the given height, cladding."""
    k0 = 2 * np.pi / wavelength
    def mismatch(n):
        kx = k0 * np.sqrt(n_core.real ** 2 - n ** 2)
        below, above = (k0 * np.sqrt(n ** 2 - other.real ** 2) for other in (n_substrate, n_cladding))
        return kx * height - np.arctan(below / kx) - np.arctan(above / kx)
    low = max(n_substrate.real, n_cladding.real)
    return brentq(mismatch, low + 1e-9, n_core.real - 1e-9)


lossless = max(abs(n.imag) for n in (n_core, n_substrate, n_cladding)) < 1e-12
slab_difference = None
if lossless and not slab:
    # Wider than the window, the core is a slab; the electric field of its TE0 mode points along the width.
    wide = solve(4 * (width + 2 * margin), 1)
    slab_difference = float(np.asarray(wide.n_eff).reshape(-1)[0] - slab_te0())

saved = data.save(OUTPUT_DIR / 'modes', {
    'intensity': data.quantity(intensity, 'electric field intensity |E|^2 of each mode, peak 1', unit='1', axes=['mode', 'y_um', 'z_um']),
    'n_eff': data.quantity(n_eff.real, 'effective index', unit='1', axes=['mode'], materials=pages),
    'mode': data.quantity(np.arange(len(n_eff)), 'mode number by decreasing effective index', unit='1'),
    'y_um': data.quantity(y, 'position along the width', unit='um', reference='0 at the centre of the core'),
    'z_um': data.quantity(z, 'position along the height', unit='um', reference='0 at the top of the substrate'),
})
RESULT = {
    'modes': [{'n_eff': float(n.real), 'loss_db_per_cm': float(4.342944819 * 4 * np.pi * n.imag / wavelength * 1e4), 'group_index': float(g),
               'te_fraction': float(t), 'effective_area_um2': float(a), 'core_power': float(c), 'guided': bool(ok)}
              for n, g, t, a, c, ok in zip(n_eff, group, te, area, core_power, guided)],
    'grid': [len(y), len(z)], 'data': saved['data'], 'materials': pages,
    'checks': {'slab_difference': slab_difference},
}
