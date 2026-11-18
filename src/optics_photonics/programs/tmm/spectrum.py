"""Reflectance, transmittance and absorptance of a planar multilayer.

Transfer-matrix method (tmm) for isotropic layers between two semi-infinite
media, over vacuum wavelength, angle of incidence and polarization. An index
is a number, [n, k] with k >= 0 absorbing, or a material from the materials
tool, which brings its measured dispersion. Layers listed in incoherent are
treated without interference, as a thick substrate is; the others are
coherent. Power quantities refer to the incident medium; with an absorbing
incident medium tmm's definitions of R and T apply.
"""
import math
import numpy as np
from tmm import coh_tmm, inc_tmm
from optics_photonics import data, materials
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'n': ([1, 1.45, 1.52], 'media in order of incidence, first and last semi-infinite: number, [n, k] or material name (SiO2, Si, main/Si/Green-2008, ...)'),
        'thickness_nm': ([100], 'thickness of each internal layer in nm'),
        'wavelength_nm': ([450, 550, 650], 'vacuum wavelengths in nm, or {"start": .., "stop": .., "points": ..}'),
        'angle_deg': (0, 'angle of incidence in the first medium in degrees; number or list'),
        'polarization': ('s', 's, p or both'),
        'incoherent': ([], 'positions in n (1 = first internal layer) of layers without interference'),
    },
    'results': 'spectrum.npz/.json with R, T, A over polarization, angle and wavelength; spectrum.csv; the first and last rows; mean and max of R, T, A over everything computed',
    'checks': 'energy_error: largest |1 - R - T| when every medium is lossless',
}
p = parameters(PROGRAM, INPUTS)


def grid(value):
    if isinstance(value, dict):
        if set(value) != {'start', 'stop', 'points'} or int(value['points']) < 1:
            raise ValueError('A wavelength grid is {"start": nm, "stop": nm, "points": count}')
        return np.linspace(float(value['start']), float(value['stop']), int(value['points']))
    values = np.atleast_1d(np.asarray(value, dtype=float))
    if values.ndim != 1 or not values.size or np.any(~np.isfinite(values)) or np.any(values <= 0):
        raise ValueError('wavelength_nm takes positive wavelengths in nm')
    return values


wavelengths = grid(p['wavelength_nm'])
angles = np.atleast_1d(np.asarray(p['angle_deg'], dtype=float))
if np.any(np.abs(angles) >= 90):
    raise ValueError('angle_deg must lie between -90 and 90 degrees')
polarizations = ['s', 'p'] if p['polarization'] == 'both' else [p['polarization']]
if polarizations[0] not in ('s', 'p'):
    raise ValueError('polarization is s, p or both')
thickness = [float(d) for d in p['thickness_nm']]
if len(p['n']) != len(thickness) + 2 or any(d < 0 for d in thickness):
    raise ValueError('Give N media in n and N - 2 nonnegative internal thicknesses')
incoherent = set(int(i) for i in p['incoherent'])
if not incoherent <= set(range(1, len(thickness) + 1)):
    raise ValueError('incoherent lists internal layer positions from 1 to ' + str(len(thickness)))

pages = {}


def index(entry, wavelength_nm):
    if isinstance(entry, str):
        pages[entry] = materials.resolve(entry)
        return materials.index_at(entry, wavelength_nm / 1000)
    if isinstance(entry, (list, tuple)):
        if len(entry) != 2 or entry[1] < 0:
            raise ValueError('An index pair is [n, k] with k >= 0 for absorption')
        return complex(entry[0], entry[1])
    return complex(entry)


distances = [math.inf, *thickness, math.inf]
coherence = ['i'] + ['i' if i in incoherent else 'c' for i in range(1, len(thickness) + 1)] + ['i']
shape = (len(polarizations), len(angles), len(wavelengths))
R, T = np.zeros(shape), np.zeros(shape)
lossless = True
for w, wavelength in enumerate(wavelengths):
    n = [index(entry, wavelength) for entry in p['n']]
    lossless = lossless and all(abs(value.imag) < 1e-12 for value in n)
    for a, angle in enumerate(np.radians(angles)):
        for k, polarization in enumerate(polarizations):
            if incoherent:
                values = inc_tmm(polarization, n, distances, coherence, angle, wavelength)
            else:
                values = coh_tmm(polarization, n, distances, angle, wavelength)
            R[k, a, w], T[k, a, w] = values['R'], values['T']
A = 1 - R - T

axes = [{'name': 'polarization', 'labels': polarizations}, 'angle_deg', 'wavelength_nm']
saved = data.save(OUTPUT_DIR / 'spectrum', {
    'R': data.quantity(R, 'reflectance', unit='1', axes=axes, power='fraction of incident power', materials=pages),
    'T': data.quantity(T, 'transmittance', unit='1', axes=axes, power='fraction of incident power'),
    'A': data.quantity(A, 'absorptance', unit='1', axes=axes, power='1 - R - T'),
    'angle_deg': data.quantity(angles, 'angle of incidence', unit='deg', medium='first medium'),
    'wavelength_nm': data.quantity(wavelengths, 'vacuum wavelength', unit='nm'),
})
if shape[:2] == (1, 1):
    columns = ['wavelength_nm', 'R', 'T', 'one_minus_R_minus_T']
    rows = [[float(wavelengths[w]), float(R[0, 0, w]), float(T[0, 0, w]), float(A[0, 0, w])] for w in range(len(wavelengths))]
else:
    columns = ['wavelength_nm', 'angle_deg', 'polarization', 'R', 'T', 'A']
    rows = [[float(wavelengths[w]), float(angles[a]), polarizations[k], float(R[k, a, w]), float(T[k, a, w]), float(A[k, a, w])]
            for k in range(shape[0]) for a in range(shape[1]) for w in range(shape[2])]
with open(OUTPUT_DIR / 'spectrum.csv', 'w', encoding='utf-8') as stream:
    stream.write(','.join(columns) + '\n')
    stream.writelines(','.join(str(value) for value in row) + '\n' for row in rows)
RESULT = {'columns': columns, 'samples': len(rows), 'first': rows[0], 'last': rows[-1], 'data': saved['data'],
          'mean': {'R': float(R.mean()), 'T': float(T.mean()), 'A': float(A.mean())},
          'max': {'R': float(R.max()), 'T': float(T.max()), 'A': float(A.max())},
          'files': ['spectrum.csv'], 'materials': pages,
          'checks': {'energy_error': float(np.max(np.abs(A))) if lossless else None}}
