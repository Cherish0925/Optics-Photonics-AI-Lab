"""Scattering and absorption of a homogeneous sphere (Mie theory).

miepython computes efficiencies Q (cross section over geometric cross
section), the backscattering efficiency and the asymmetry parameter g for a
sphere in a lossless medium, over vacuum wavelength. An index is a number,
[n, k] with k > 0 absorbing (a negative k is read as the same loss in
miepython's n - ik form), or a material from the materials tool. With angles,
the differential scattering cross section of unpolarized light and the
amplitudes |S1|^2, |S2|^2 (Bohren and Huffman normalization) are saved.
"""
import math
import numpy as np
import miepython
from optics_photonics import data, materials
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'index': ([1.5, 0], 'sphere index: number, [n, k] or material name (Au, SiO2, main/Ag/Johnson, ...)'),
        'diameter_nm': (200, 'sphere diameter in nm'),
        'wavelength_nm': ([450, 550, 650], 'vacuum wavelengths in nm, or {"start": .., "stop": .., "points": ..}'),
        'medium_index': (1, 'index of the lossless surrounding medium: number or material name'),
        'angles_deg': ([], 'scattering angles in degrees for the angular pattern; empty skips it'),
    },
    'results': 'scattering.npz/.json with Q and cross sections over wavelength, and the angular pattern; scattering.csv; first and last rows',
    'checks': 'extinction_minus_scattering: largest |Qext - Qsca| for a lossless sphere',
}
p = parameters(PROGRAM, INPUTS)
if isinstance(p['wavelength_nm'], dict):
    grid = p['wavelength_nm']
    wavelengths = np.linspace(float(grid['start']), float(grid['stop']), int(grid['points']))
else:
    wavelengths = np.atleast_1d(np.asarray(p['wavelength_nm'], dtype=float))
diameter = float(p['diameter_nm'])
if diameter <= 0 or np.any(wavelengths <= 0):
    raise ValueError('diameter_nm and wavelength_nm must be positive')
angles = np.asarray(p['angles_deg'], dtype=float)
pages = {}


def index(entry, wavelength_nm, name):
    """n + ik with k >= 0 for absorption."""
    if isinstance(entry, str):
        pages[name] = materials.resolve(entry)
        return materials.index_at(entry, wavelength_nm / 1000)
    if isinstance(entry, (list, tuple)):
        return complex(entry[0], abs(entry[1]))
    return complex(entry)


rows, angular = [], []
lossless, medium_k = True, 0.0
for wavelength in wavelengths:
    sphere, medium = index(p['index'], wavelength, 'sphere'), index(p['medium_index'], wavelength, 'medium')
    # Efficiencies need a lossless medium; a trace of absorption, as in water, is neglected and reported.
    if abs(medium.imag) > 1e-4 * medium.real:
        raise ValueError(f'The surrounding medium absorbs (k = {medium.imag:.3g}); Mie efficiencies need a lossless medium')
    medium_k = max(medium_k, abs(medium.imag))
    lossless = lossless and abs(sphere.imag) < 1e-12
    m = complex(sphere.real, -sphere.imag) / medium.real   # miepython: n - ik, relative to the medium
    x = math.pi * diameter * medium.real / wavelength
    qext, qsca, qback, g = (float(v) for v in miepython.efficiencies_mx(m, x))
    rows.append([float(wavelength), qext, qsca, qback, g])
    if angles.size:
        # With norm='qsca' the unpolarized phase function (|S1|^2 + |S2|^2)/2 integrates to Qsca over 4 pi sr;
        # times the geometric cross section it is dCsca/dOmega, and times pi x^2 Bohren and Huffman's |S|^2.
        s1, s2 = (np.abs(v) ** 2 for v in miepython.S1_S2(m, x, np.cos(np.radians(angles)), norm='qsca'))
        angular.append((s1 * math.pi * x * x, s2 * math.pi * x * x, (s1 + s2) / 2 * math.pi * diameter ** 2 / 4))

table = np.asarray(rows)
area = math.pi * diameter ** 2 / 4
arrays = {
    'Qext': data.quantity(table[:, 1], 'extinction efficiency', unit='1', axes=['wavelength_nm'], materials=pages),
    'Qsca': data.quantity(table[:, 2], 'scattering efficiency', unit='1', axes=['wavelength_nm']),
    'Qabs': data.quantity(table[:, 1] - table[:, 2], 'absorption efficiency', unit='1', axes=['wavelength_nm']),
    'Qback': data.quantity(table[:, 3], 'backscattering efficiency', unit='1', axes=['wavelength_nm']),
    'g': data.quantity(table[:, 4], 'asymmetry parameter', unit='1', axes=['wavelength_nm']),
    'Cext': data.quantity(table[:, 1] * area, 'extinction cross section', unit='nm^2', axes=['wavelength_nm']),
    'Csca': data.quantity(table[:, 2] * area, 'scattering cross section', unit='nm^2', axes=['wavelength_nm']),
    'wavelength_nm': data.quantity(wavelengths, 'vacuum wavelength', unit='nm'),
}
if angles.size:
    s1, s2, dc = (np.asarray(part) for part in zip(*angular))
    axes = ['wavelength_nm', 'angle_deg']
    arrays.update({
        'S1_squared': data.quantity(s1, '|S1|^2, perpendicular polarization', unit='1', axes=axes, normalization='Bohren and Huffman'),
        'S2_squared': data.quantity(s2, '|S2|^2, parallel polarization', unit='1', axes=axes, normalization='Bohren and Huffman'),
        'dCsca_dOmega': data.quantity(dc, 'differential scattering cross section, unpolarized', unit='nm^2/sr', axes=axes),
        'angle_deg': data.quantity(angles, 'scattering angle', unit='deg', reference='0 is forward'),
    })
saved = data.save(OUTPUT_DIR / 'scattering', arrays)
np.savetxt(OUTPUT_DIR / 'scattering.csv', table, delimiter=',', header='wavelength_nm,Qext,Qsca,Qback,g', comments='')
RESULT = {'samples': len(rows), 'first': rows[0], 'last': rows[-1], 'data': saved['data'], 'files': ['scattering.csv'],
          'materials': pages, 'medium_k_neglected': medium_k,
          'checks': {'extinction_minus_scattering': float(np.max(np.abs(table[:, 1] - table[:, 2]))) if lossless else None}}
