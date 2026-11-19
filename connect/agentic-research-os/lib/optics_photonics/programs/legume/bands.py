"""Photonic band structure of a two-dimensional lattice of holes or rods.

legume solves a two-dimensional crystal by plane-wave expansion (TE: electric
field in the plane; TM: electric field along the rods) or a slab of finite
thickness in air by guided-mode expansion, whose guided bands lie below the
light line. Lengths are in units of the period a; wavevectors in radians per
period; frequencies are a / lambda. Bands are followed along a path through
the Brillouin zone, and complete gaps between consecutive bands are reported.
Results converge with gmax, which should be increased until they stop changing.
"""
import numpy as np
import legume
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'lattice': ('square', 'square or hexagonal'),
        'structure': ('holes', 'holes: air holes in a background of epsilon; rods: rods of epsilon in air'),
        'epsilon': (12, 'permittivity of the background (holes) or of the rods'),
        'hole_radius_over_period': (0.2, 'radius of each hole, or of each rod for structure rods, over the period'),
        'thickness_over_period': (0.5, 'slab thickness over the period (guided-mode expansion); null for a two-dimensional crystal (plane-wave expansion)'),
        'polarization': ('te', 'te or tm, for a two-dimensional crystal'),
        'gmode_inds': ([0], 'guided-mode orders of the slab basis; [0] gives the lowest TE-like modes'),
        'path': ('G-X-M-G', 'corners of the path: G, X, M for square; G, M, K for hexagonal'),
        'points': (12, 'points between consecutive corners'),
        'kpoints': (None, 'explicit wavevectors [[kx, ...], [ky, ...]] in radians per period, instead of the path'),
        'gmax': (3, 'plane-wave cutoff; increase until the frequencies converge'),
        'numeig': (6, 'number of bands'),
    },
    'results': 'bands.npz/.json with frequency over path position and band, kx and ky; complete gaps; light line of a slab',
    'checks': 'gaps between consecutive bands with their gap-midgap ratio',
}
p = parameters(PROGRAM, INPUTS)
if p['lattice'] not in ('square', 'hexagonal') or p['structure'] not in ('holes', 'rods'):
    raise ValueError('lattice is square or hexagonal; structure is holes or rods')
radius, epsilon = float(p['hole_radius_over_period']), float(p['epsilon'])
if not 0 < radius < 0.5 or epsilon <= 0:
    raise ValueError('hole_radius_over_period lies between 0 and 0.5 and epsilon is positive')
lattice = legume.Lattice(p['lattice'])
background, inclusion = (epsilon, 1.0) if p['structure'] == 'holes' else (1.0, epsilon)
slab = p['thickness_over_period'] is not None
crystal = legume.PhotCryst(lattice)
crystal.add_layer(d=float(p['thickness_over_period']) if slab else 0, eps_b=background)
crystal.add_shape(legume.Circle(eps=inclusion, r=radius))

if p['kpoints'] is not None:
    kpoints = np.asarray(p['kpoints'], dtype=float)
    labels, corners = [], []
else:
    labels = p['path'].split('-')
    path = lattice.bz_path(labels, [int(p['points'])] * (len(labels) - 1))
    kpoints, corners = path['kpoints'], [int(i) for i in path['indexes']]
if kpoints.ndim != 2 or kpoints.shape[0] != 2:
    raise ValueError('kpoints is [[kx, ...], [ky, ...]]')

if slab:
    solver = legume.GuidedModeExp(crystal, gmax=float(p['gmax']))
    solver.run(kpoints=kpoints, gmode_inds=list(p['gmode_inds']), numeig=int(p['numeig']), compute_im=False, verbose=False)
else:
    if p['polarization'] not in ('te', 'tm'):
        raise ValueError('polarization is te or tm')
    solver = legume.PlaneWaveExp(crystal.layers[0], gmax=float(p['gmax']))
    solver.run(kpoints=kpoints, pol=p['polarization'], numeig=int(p['numeig']))
frequencies = np.asarray(solver.freqs)
distance = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(kpoints, axis=1), axis=0))])

gaps = []
for band in range(frequencies.shape[1] - 1):
    top, bottom = float(frequencies[:, band].max()), float(frequencies[:, band + 1].min())
    if 2 * (bottom - top) / (bottom + top) > 1e-3:  # narrower openings are bands that touch, split by discretization
        gaps.append({'bands': [band + 1, band + 2], 'from': top, 'to': bottom, 'gap_midgap_ratio': 2 * (bottom - top) / (bottom + top)})
light_line = np.linalg.norm(kpoints, axis=0) / (2 * np.pi)
axes = ['path_distance', {'name': 'band', 'start': 1, 'step': 1}]
arrays = {
    'frequencies': data.quantity(frequencies, 'eigenfrequency', unit='a/lambda', axes=axes,
                                 method='guided-mode expansion' if slab else 'plane-wave expansion ' + p['polarization'].upper()),
    'kpoints': data.quantity(kpoints, 'Bloch wavevector [kx, ky]', unit='rad/a', axes=[{'name': 'component', 'labels': ['kx', 'ky']}, 'path_distance']),
    'path_distance': data.quantity(distance, 'distance along the path', unit='rad/a', corners=[[label, index] for label, index in zip(labels, corners)]),
}
if slab:
    arrays['light_line'] = data.quantity(light_line, 'light line of the air cladding', unit='a/lambda', axes=['path_distance'])
saved = data.save(OUTPUT_DIR / 'bands', arrays)
values = {'corners': [[label, index] for label, index in zip(labels, corners)], 'corner_frequencies': frequencies[corners].tolist()} if labels else {
    'frequencies_a_over_lambda': frequencies.tolist()}
RESULT = {**values, 'data': saved['data'],
          'method': arrays['frequencies'].description['method'], 'gaps': gaps, 'checks': {'gaps': gaps}}
