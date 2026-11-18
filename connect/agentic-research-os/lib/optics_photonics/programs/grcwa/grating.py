"""Diffraction efficiencies of a lamellar (binary) grating by RCWA.

grcwa solves a layer of period P, in which a ridge of width fill_factor * P
alternates with a groove, between a superstrate and a substrate, for a
plane wave in the plane perpendicular to the grating lines. TE has the
electric field along the lines (s), TM the magnetic field along them (p).
Each index is a number, [n, k] with k >= 0 absorbing, or a material from the
materials tool. Efficiencies are fractions of the incident power per
diffraction order. They converge with the number of orders and the grid that
samples the period, which should be increased until the efficiencies stop
changing; TM converges more slowly than TE.
"""
import math
import numpy as np
import grcwa
from optics_photonics import data, materials
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'period_um': (1.0, 'grating period in micrometres'),
        'fill_factor': (0.5, 'ridge width over the period'),
        'depth_um': (0.3, 'grating depth in micrometres'),
        'ridge': (1.5, 'ridge index: number, [n, k] or material'),
        'groove': (1.0, 'groove index'),
        'superstrate': (1.0, 'index of the incident medium'),
        'substrate': (1.5, 'index of the substrate'),
        'wavelength_um': ([0.8], 'vacuum wavelengths in micrometres, or {"start": .., "stop": .., "points": ..}'),
        'angle_deg': (0.0, 'angle of incidence in the superstrate, in the plane perpendicular to the lines'),
        'polarization': ('te', 'te (E along the lines) or tm (H along the lines)'),
        'orders': (41, 'Fourier orders retained'),
        'grid': (512, 'samples of the permittivity over one period'),
    },
    'results': 'efficiency.npz/.json with reflected and transmitted efficiency per order over wavelength; totals',
    'checks': 'energy_error: largest |1 - R - T| when every medium is lossless',
}
p = parameters(PROGRAM, INPUTS)
period, fill, depth = float(p['period_um']), float(p['fill_factor']), float(p['depth_um'])
if period <= 0 or depth < 0 or not 0 <= fill <= 1 or p['polarization'] not in ('te', 'tm'):
    raise ValueError('period_um is positive, depth_um nonnegative, fill_factor in [0, 1], polarization te or tm')
if isinstance(p['wavelength_um'], dict):
    grid_spec = p['wavelength_um']
    wavelengths = np.linspace(float(grid_spec['start']), float(grid_spec['stop']), int(grid_spec['points']))
else:
    wavelengths = np.atleast_1d(np.asarray(p['wavelength_um'], dtype=float))
pages = {}


def index(entry, wavelength):
    if isinstance(entry, str):
        pages[entry] = materials.resolve(entry)
        return materials.index_at(entry, wavelength)
    return complex(entry[0], entry[1]) if isinstance(entry, (list, tuple)) else complex(entry)


cells = int(p['grid'])
ridge_cells = np.arange(cells) / cells < fill
reflected, transmitted, kept = [], [], None
lossless = True
for wavelength in wavelengths:
    n = {key: index(p[key], wavelength) for key in ('ridge', 'groove', 'superstrate', 'substrate')}
    lossless = lossless and all(abs(v.imag) < 1e-12 for v in n.values())
    # A short second period confines the circular truncation to orders along the grating vector.
    solver = grcwa.obj(int(p['orders']), [period, 0], [0, period * 1e-2], 1 / wavelength, math.radians(p['angle_deg']), 0, verbose=0)
    solver.Add_LayerUniform(0, n['superstrate'] ** 2)
    solver.Add_LayerGrid(depth, cells, 1)
    solver.Add_LayerUniform(0, n['substrate'] ** 2)
    solver.Init_Setup(Gmethod=0)
    solver.GridLayer_geteps(np.where(ridge_cells, n['ridge'] ** 2, n['groove'] ** 2).reshape(cells, 1).flatten())
    solver.MakeExcitationPlanewave(p_amp=int(p['polarization'] == 'tm'), p_phase=0, s_amp=int(p['polarization'] == 'te'), s_phase=0)
    R, T = solver.RT_Solve(normalize=1, byorder=1)
    order_index = solver.G[:, 0].astype(int)
    if kept is None:
        kept = np.sort(order_index)
    position = {m: i for i, m in enumerate(order_index)}
    reflected.append([float(np.real(R[position[m]])) for m in kept])
    transmitted.append([float(np.real(T[position[m]])) for m in kept])
reflected, transmitted = np.asarray(reflected), np.asarray(transmitted)
R_total, T_total = reflected.sum(axis=1), transmitted.sum(axis=1)
# Report only orders that carry power somewhere in the scan.
carrying = np.where((reflected.max(axis=0) > 1e-12) | (transmitted.max(axis=0) > 1e-12))[0]
orders = kept[carrying]
axes = ['wavelength_um', {'name': 'order', 'labels': [int(m) for m in orders]}]
saved = data.save(OUTPUT_DIR / 'efficiency', {
    'reflected': data.quantity(reflected[:, carrying], 'reflected diffraction efficiency', unit='1', axes=axes, materials=pages,
                               polarization=p['polarization']),
    'transmitted': data.quantity(transmitted[:, carrying], 'transmitted diffraction efficiency', unit='1', axes=axes),
    'R': data.quantity(R_total, 'total reflectance', unit='1', axes=['wavelength_um']),
    'T': data.quantity(T_total, 'total transmittance', unit='1', axes=['wavelength_um']),
    'wavelength_um': data.quantity(wavelengths, 'vacuum wavelength', unit='um'),
})
first = {'wavelength_um': float(wavelengths[0]),
         'reflected': {int(m): float(v) for m, v in zip(orders, reflected[0, carrying]) if v > 1e-6},
         'transmitted': {int(m): float(v) for m, v in zip(orders, transmitted[0, carrying]) if v > 1e-6}}
RESULT = {'data': saved['data'], 'first_wavelength': first, 'R': R_total.tolist(), 'T': T_total.tolist(), 'materials': pages,
          'checks': {'energy_error': float(np.max(np.abs(1 - R_total - T_total))) if lossless else None}}
