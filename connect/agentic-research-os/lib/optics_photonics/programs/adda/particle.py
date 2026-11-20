"""Scattering and absorption of a sphere or an ellipsoid by the discrete dipole approximation (ADDA), checked against the exact series.

ADDA replaces the particle by cubical dipoles on a grid, dipoles_per_wavelength
of them per wavelength in the particle, and solves for their polarizations by
iteration. The particle is lit along z, and ADDA reports the extinction,
absorption and scattering efficiencies Q = C / (pi a_eq^2), with a_eq the radius
of the sphere of equal volume, and the Mueller matrix over the scattering angle
in one plane. Indices are relative: m = n_particle / n_medium, and the
wavelength in the medium sets the size parameter x = 2 pi a_eq n_medium / lambda.
For a sphere the exact Mie series (Bohren and Huffman, appendix A, with the
logarithmic derivative by downward recurrence) gives the same efficiencies and
S11 = (|S1|^2 + |S2|^2) / 2, against which the dipole result converges as the
dipoles get finer: slowly for metals (|m| > 2), whose surface plasmons feel the
staircase surface, so that a gold sphere needs tens of thousands of dipoles for
ten per cent. Lengths in micrometres. The adda executable is bound with
bind_native_software('adda', executable=...); RUN calls it.
"""
import math
import re
import numpy as np
from optics_photonics import data, materials
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'shape': ('sphere', 'sphere, or ellipsoid with aspect [y/x, z/x]'),
        'aspect': ([1.0, 1.0], 'semi-axes y/x and z/x of an ellipsoid'),
        'diameter_um': (1.0, 'size of the particle along x in micrometres'),
        'wavelength_um': (0.6328, 'vacuum wavelength in micrometres'),
        'particle_index': (1.5, 'particle index: number, [n, k] or material'),
        'medium_index': (1.0, 'index of the surrounding medium'),
        'dipoles_per_wavelength': (15, 'dipoles per wavelength inside the particle'),
    },
    'domains': ['scatter'],
    'results': 'particle.npz/.json: S11 over the scattering angle from ADDA and, for a sphere, Mie theory; extinction, scattering and '
               'absorption efficiencies, the size parameter and the number of dipoles',
    'checks': 'mie_difference: relative difference of the extinction efficiency from Mie theory (sphere); s11_difference: relative '
              'L2 difference of S11 over angle from Mie theory (sphere); both shrink as dipoles_per_wavelength grows',
}
p = parameters(PROGRAM, INPUTS)
diameter, wavelength, medium = float(p['diameter_um']), float(p['wavelength_um']), float(p['medium_index'])
if diameter <= 0 or wavelength <= 0 or medium <= 0 or p['shape'] not in ('sphere', 'ellipsoid') or float(p['dipoles_per_wavelength']) < 3:
    raise ValueError('diameter_um, wavelength_um and medium_index are positive, shape is sphere or ellipsoid, dipoles_per_wavelength >= 3')
entry = p['particle_index']
if isinstance(entry, str):
    index, pages = complex(materials.index_at(entry, wavelength)), {entry: materials.resolve(entry)}
else:
    index, pages = (complex(entry[0], entry[1]) if isinstance(entry, (list, tuple)) else complex(entry)), {}
m = index / medium
shape = ['-shape', 'sphere'] if p['shape'] == 'sphere' else ['-shape', 'ellipsoid', *map(float, p['aspect'])]
# ADDA's -dpl counts dipoles per wavelength in the medium; the input counts them per wavelength in the particle.
RUN('-size', diameter, '-lambda', wavelength / medium, '-m', m.real, abs(m.imag), '-dpl', float(p['dipoles_per_wavelength']) * abs(m),
    *shape, '-dir', OUTPUT_DIR / 'adda', log='adda.log')


def efficiencies(file):
    text = file.read_text()
    return {key: float(re.search(rf'^{key}\s*=\s*(\S+)', text, re.M).group(1)) for key in ('Qext', 'Qabs', 'Cext', 'Cabs')}


crossed = {axis: efficiencies(OUTPUT_DIR / 'adda' / f'CrossSec-{axis}') for axis in ('Y', 'X') if (OUTPUT_DIR / 'adda' / f'CrossSec-{axis}').exists()}
mueller = np.loadtxt(OUTPUT_DIR / 'adda' / 'mueller', skiprows=1)
theta, s11 = mueller[:, 0], mueller[:, 1]
log = (OUTPUT_DIR / 'adda' / 'log').read_text()
size_parameter = float(re.search(r'Volume-equivalent size parameter:\s*(\S+)', log).group(1))
dipoles = int(re.search(r'Total number of occupied dipoles:\s*(\d+)', log).group(1))
y = crossed['Y']
RESULT = {'Qext': y['Qext'], 'Qabs': y['Qabs'], 'Qsca': y['Qext'] - y['Qabs'], 'size_parameter': size_parameter, 'dipoles': dipoles,
          'relative_index': [m.real, m.imag], 'materials': pages}
if 'X' in crossed:
    RESULT['X'] = {'Qext': crossed['X']['Qext'], 'Qabs': crossed['X']['Qabs'], 'Qsca': crossed['X']['Qext'] - crossed['X']['Qabs']}
quantities = {'theta_deg': data.quantity(theta, 'scattering angle in the plane of the Mueller matrix', unit='deg'),
              's11_adda': data.quantity(s11, 'Mueller element S11 from ADDA (Bohren and Huffman normalization)', unit='1', axes=['theta_deg'])}
checks = {'mie_difference': None, 's11_difference': None}
if p['shape'] == 'sphere':
    x = size_parameter
    stop = int(x + 4 * x ** (1 / 3) + 2)
    terms = max(stop, int(abs(m * x))) + 15
    D = np.zeros(terms + 1, complex)
    for n in range(terms, 0, -1):                         # logarithmic derivative of psi_n(m x), downward
        D[n - 1] = n / (m * x) - 1 / (D[n] + n / (m * x))
    mu = np.cos(np.radians(theta))
    psi0, psi1, chi0, chi1 = math.cos(x), math.sin(x), -math.sin(x), math.cos(x)
    pi0, pi1 = np.zeros_like(mu), np.ones_like(mu)
    S1, S2 = np.zeros_like(mu, complex), np.zeros_like(mu, complex)
    qext = qsca = 0.0
    for n in range(1, stop + 1):
        psi, chi = (2 * n - 1) * psi1 / x - psi0, (2 * n - 1) * chi1 / x - chi0
        xi, xi1 = psi - 1j * chi, psi1 - 1j * chi1
        a = ((D[n] / m + n / x) * psi - psi1) / ((D[n] / m + n / x) * xi - xi1)
        b = ((m * D[n] + n / x) * psi - psi1) / ((m * D[n] + n / x) * xi - xi1)
        qext += (2 * n + 1) * (a + b).real
        qsca += (2 * n + 1) * (abs(a) ** 2 + abs(b) ** 2)
        tau = n * mu * pi1 - (n + 1) * pi0
        weight = (2 * n + 1) / (n * (n + 1))
        S1 += weight * (a * pi1 + b * tau)
        S2 += weight * (a * tau + b * pi1)
        pi0, pi1 = pi1, ((2 * n + 1) * mu * pi1 - (n + 1) * pi0) / n
        psi0, psi1, chi0, chi1 = psi1, psi, chi1, chi
    mie = {'Qext': 2 * qext / x ** 2, 'Qsca': 2 * qsca / x ** 2}
    mie['Qabs'] = mie['Qext'] - mie['Qsca']
    s11_mie = (abs(S1) ** 2 + abs(S2) ** 2) / 2
    quantities['s11_mie'] = data.quantity(s11_mie, 'Mueller element S11 of the exact Mie series', unit='1', axes=['theta_deg'])
    RESULT['mie'] = mie
    checks = {'mie_difference': abs(y['Qext'] - mie['Qext']) / mie['Qext'],
              's11_difference': float(np.linalg.norm(s11 - s11_mie) / np.linalg.norm(s11_mie))}
saved = data.save(OUTPUT_DIR / 'particle', quantities)
RESULT.update(data=saved['data'], checks=checks)
