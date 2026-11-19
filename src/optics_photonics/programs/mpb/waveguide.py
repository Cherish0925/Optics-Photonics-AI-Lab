"""Guided modes of a strip or rib waveguide cross-section (MPB).

MPB solves the vector Maxwell eigenproblem on the cross-section in a
periodic supercell with subpixel smoothing of the permittivity, and finds
for each mode the propagation constant k at the given frequency (find_k),
so the effective index is k / k0. The core is a rectangle of width_um by
height_um on a substrate, under a cladding; slab_um adds a slab of the
core material under the core across the whole cell, which makes a rib.
Indices are numbers or materials from the materials tool, evaluated at each
wavelength. The group index comes from the group velocity of each mode,
for the material indices held fixed (no material dispersion). te_fraction
is the share of the transverse electric energy along the width (1 for a
TE-like mode, 0 for TM-like). The cell must be large enough for the fields
to vanish at its edges: edge_energy is the largest fraction of a mode's
energy in the outer tenth of the cell. Results converge with resolution
(points per micrometre).
"""
import numpy as np
import meep as mp
from meep import mpb
from optics_photonics import data, materials
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'core': (3.476, 'core index: number or material'),
        'cladding': (1.444, 'index above the core'),
        'substrate': (1.444, 'index below the core'),
        'width_um': (0.5, 'core width'),
        'height_um': (0.22, 'core height'),
        'slab_um': (0.0, 'thickness of a slab of core material under the core across the cell (rib waveguide)'),
        'wavelength_um': ([1.55], 'vacuum wavelengths'),
        'modes': (2, 'number of modes'),
        'resolution': (64, 'grid points per micrometre'),
        'cell_um': ([3.0, 2.5], 'supercell width and height'),
    },
    'results': 'modes.npz/.json with effective index, group index and TE fraction over wavelength and mode; intensity of each mode at the first wavelength',
    'checks': 'edge_energy: largest fraction of mode energy in the outer tenth of the cell',
}
p = parameters(PROGRAM, INPUTS)
wavelengths = np.atleast_1d(np.asarray(p['wavelength_um'], dtype=float))
w, h, slab = float(p['width_um']), float(p['height_um']), float(p['slab_um'])
Y, Z = (float(v) for v in p['cell_um'])
bands = int(p['modes'])
pages = {}


def index(entry, wavelength):
    if isinstance(entry, str):
        pages[entry] = materials.resolve(entry)
        value = materials.index_at(entry, wavelength)
        if abs(value.imag) > 1e-3:
            raise ValueError(f'{entry} absorbs at {wavelength} um; this program takes lossless media')
        return value.real
    return float(entry)


rows, fields = [], {}
for n, wavelength in enumerate(wavelengths):
    n_core, n_clad, n_sub = (index(p[key], wavelength) for key in ('core', 'cladding', 'substrate'))
    core = mp.Medium(index=n_core)
    geometry = [mp.Block(size=mp.Vector3(mp.inf, mp.inf, Z / 2), center=mp.Vector3(0, 0, -Z / 4), material=mp.Medium(index=n_sub))]
    if slab > 0:
        geometry.append(mp.Block(size=mp.Vector3(mp.inf, mp.inf, slab), center=mp.Vector3(0, 0, slab / 2), material=core))
    geometry.append(mp.Block(size=mp.Vector3(mp.inf, w, h), center=mp.Vector3(0, 0, h / 2), material=core))
    solver = mpb.ModeSolver(geometry_lattice=mp.Lattice(size=mp.Vector3(0, Y, Z)), geometry=geometry, default_material=mp.Medium(index=n_clad),
                            resolution=int(p['resolution']), num_bands=bands)
    omega, light_line = 1 / wavelength, max(n_clad, n_sub)
    found = {}

    def measure(ms, band):
        e = np.asarray(ms.get_efield(band, bloch_phase=False))[:, :, 0, :]
        energy = np.abs(e) ** 2
        total = energy.sum()
        ny, nz = energy.shape[:2]
        border = np.ones((ny, nz), bool)
        border[ny // 10:ny - ny // 10, nz // 10:nz - nz // 10] = False
        transverse = energy[..., 1].sum() + energy[..., 2].sum()
        found[band] = {'group_index': 1 / ms.compute_group_velocity_component(mp.Vector3(1))[band - 1],
                       'te_fraction': float(energy[..., 1].sum() / transverse), 'edge': float(energy[border].sum() / total),
                       'intensity': energy.sum(axis=-1) / energy.sum(axis=-1).max()}
    k = solver.find_k(mp.NO_PARITY, omega, 1, bands, mp.Vector3(1), 1e-8, (light_line + n_core) / 2 * omega,
                      light_line * omega, n_core * omega, measure)
    for band in range(1, bands + 1):
        item = found.get(band, {})
        neff = k[band - 1] / omega
        guided = neff > light_line + 1e-6
        rows.append([neff if guided else np.nan, item.get('group_index', np.nan) if guided else np.nan,
                     item.get('te_fraction', np.nan) if guided else np.nan, item.get('edge', np.nan) if guided else np.nan])
        if n == 0 and guided:
            fields[band] = item['intensity']
    if n == 0:
        epsilon = np.asarray(solver.get_epsilon())
table = np.asarray(rows).reshape(len(wavelengths), bands, 4)
ny, nz = epsilon.shape
axes = ['wavelength_um', {'name': 'mode', 'start': 1, 'step': 1}]
grid = [{'name': 'y', 'unit': 'um', 'start': -Y / 2, 'step': Y / ny}, {'name': 'z', 'unit': 'um', 'start': -Z / 2, 'step': Z / nz}]
arrays = {
    'neff': data.quantity(table[..., 0], 'effective index', unit='1', axes=axes, materials=pages, resolution=int(p['resolution'])),
    'ng': data.quantity(table[..., 1], 'group index without material dispersion', unit='1', axes=axes),
    'te_fraction': data.quantity(table[..., 2], 'share of transverse electric energy along the width', unit='1', axes=axes),
    'wavelength_um': data.quantity(wavelengths, 'vacuum wavelength', unit='um'),
    'epsilon': data.quantity(epsilon, 'relative permittivity of the cross-section', unit='1', axes=grid),
}
for band, intensity in fields.items():
    arrays[f'intensity_{band}'] = data.quantity(intensity, f'|E|^2 of mode {band} at {wavelengths[0]} um', unit='1', axes=grid,
                                                normalization='maximum 1')
saved = data.save(OUTPUT_DIR / 'modes', arrays)
first = [{'mode': b + 1, 'neff': None if np.isnan(table[0, b, 0]) else float(table[0, b, 0]),
          'ng': None if np.isnan(table[0, b, 1]) else float(table[0, b, 1]),
          'te_fraction': None if np.isnan(table[0, b, 2]) else float(table[0, b, 2])} for b in range(bands)]
edge = table[..., 3]
RESULT = {'data': saved['data'], 'wavelength_um': float(wavelengths[0]), 'modes': first, 'guided': int(np.sum(~np.isnan(table[0, :, 0]))),
          'materials': pages, 'checks': {'edge_energy': float(np.nanmax(edge)) if np.any(~np.isnan(edge)) else None}}
