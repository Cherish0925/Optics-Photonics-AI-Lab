"""Photonic band structure of a two-dimensional lattice of holes or rods (MPB).

MPB finds the eigenfrequencies of a periodic dielectric structure for each
Bloch wavevector by iterative minimization in a plane-wave basis, with
subpixel smoothing of the permittivity. tm has the electric field along the
rods (normal to the plane), te in the plane. Lengths are in units of the
period a and frequencies are a / lambda. Bands are followed along a path
through the Brillouin zone, and complete gaps between consecutive bands are
reported; openings below 0.1 % of the midgap frequency are bands that touch.
Gaps are searched along the path, which holds the band extrema of these
lattices in most cases. Frequencies converge with resolution, roughly as its
inverse square; increase it until they stop changing.
"""
import math
import numpy as np
import meep as mp
from meep import mpb
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'lattice': ('square', 'square or hexagonal'),
        'structure': ('rods', 'rods: rods of epsilon in air; holes: air holes in a background of epsilon'),
        'epsilon': (8.9, 'permittivity of the rods or of the background'),
        'radius_over_period': (0.2, 'radius of each rod or hole over the period'),
        'polarization': ('tm', 'tm (E along the rods), te (E in the plane) or both'),
        'path': ('G-X-M-G', 'corners of the path: G, X, M for square; G, M, K for hexagonal'),
        'points': (10, 'points inserted between consecutive corners'),
        'bands': (8, 'number of bands'),
        'resolution': (32, 'grid points per period'),
    },
    'domains': ['periodic'],
    'results': 'bands.npz/.json with frequency over polarization, path position and band; kx and ky; complete gaps',
    'checks': 'gaps between consecutive bands with their gap-midgap ratio',
}
p = parameters(PROGRAM, INPUTS)
if p['lattice'] not in ('square', 'hexagonal') or p['structure'] not in ('holes', 'rods') or p['polarization'] not in ('tm', 'te', 'both'):
    raise ValueError('lattice is square or hexagonal; structure is holes or rods; polarization is tm, te or both')
radius, epsilon = float(p['radius_over_period']), float(p['epsilon'])
if not 0 < radius < 0.5 or epsilon <= 0:
    raise ValueError('radius_over_period lies between 0 and 0.5 and epsilon is positive')
if p['lattice'] == 'square':
    lattice = mp.Lattice(size=mp.Vector3(1, 1))
    corners = {'G': mp.Vector3(), 'X': mp.Vector3(0.5), 'M': mp.Vector3(0.5, 0.5)}
else:
    lattice = mp.Lattice(size=mp.Vector3(1, 1), basis1=mp.Vector3(math.sqrt(3) / 2, 0.5), basis2=mp.Vector3(math.sqrt(3) / 2, -0.5))
    corners = {'G': mp.Vector3(), 'M': mp.Vector3(y=0.5), 'K': mp.Vector3(-1 / 3, 1 / 3)}
labels = p['path'].split('-')
if any(label not in corners for label in labels) or len(labels) < 2:
    raise ValueError('path joins corners of the ' + p['lattice'] + ' zone: ' + ', '.join(corners))
kpoints = mp.interpolate(int(p['points']), [corners[label] for label in labels])
material = mp.Medium(epsilon=epsilon)
solver = mpb.ModeSolver(num_bands=int(p['bands']), k_points=kpoints, geometry_lattice=lattice, resolution=int(p['resolution']),
                        dimensions=2, default_material=mp.air if p['structure'] == 'rods' else material,
                        geometry=[mp.Cylinder(radius, material=material if p['structure'] == 'rods' else mp.air)])
polarizations = ['tm', 'te'] if p['polarization'] == 'both' else [p['polarization']]
frequencies, gaps = [], {}
for polarization in polarizations:
    solver.run_tm() if polarization == 'tm' else solver.run_te()
    bands = np.asarray(solver.all_freqs)
    frequencies.append(bands)
    gaps[polarization] = []
    for band in range(bands.shape[1] - 1):
        top, bottom = float(bands[:, band].max()), float(bands[:, band + 1].min())
        if 2 * (bottom - top) / (bottom + top) > 1e-3:  # narrower openings are bands that touch, split by discretization
            gaps[polarization].append({'bands': [band + 1, band + 2], 'from': top, 'to': bottom,
                                       'gap_midgap_ratio': 2 * (bottom - top) / (bottom + top)})
frequencies = np.asarray(frequencies)
cartesian = np.array([[v.x, v.y] for v in (mp.reciprocal_to_cartesian(k, lattice) for k in kpoints)]).T * 2 * math.pi
distance = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(cartesian, axis=1), axis=0))])
positions = [[label, i * (int(p['points']) + 1)] for i, label in enumerate(labels)]
saved = data.save(OUTPUT_DIR / 'bands', {
    'frequencies': data.quantity(frequencies, 'eigenfrequency', unit='a/lambda', resolution=int(p['resolution']),
                                 axes=[{'name': 'polarization', 'labels': polarizations}, 'path_distance', {'name': 'band', 'start': 1, 'step': 1}]),
    'kpoints': data.quantity(cartesian, 'Bloch wavevector [kx, ky]', unit='rad/a', axes=[{'name': 'component', 'labels': ['kx', 'ky']}, 'path_distance']),
    'path_distance': data.quantity(distance, 'distance along the path', unit='rad/a', corners=positions),
})
complete = gaps[polarizations[0]] if len(polarizations) == 1 else [
    {'from': low, 'to': high, 'gap_midgap_ratio': 2 * (high - low) / (high + low)}
    for low, high in sorted((max(a['from'], b['from']), min(a['to'], b['to'])) for a in gaps['tm'] for b in gaps['te'])
    if 2 * (high - low) / (high + low) > 1e-3]
RESULT = {'data': saved['data'], 'corners': positions, 'gaps': gaps, 'complete_gaps': complete,
          'corner_frequencies': {pol: frequencies[i][[index for _, index in positions]].tolist() for i, pol in enumerate(polarizations)},
          'checks': {'gaps': gaps}}
