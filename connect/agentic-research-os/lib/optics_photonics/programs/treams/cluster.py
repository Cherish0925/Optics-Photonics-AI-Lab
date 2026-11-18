"""Light scattering by a cluster of spheres with all multiple scattering (T-matrix method).

treams builds the T-matrix of each sphere, couples the spheres through the
translation of spherical waves and solves the interaction exactly up to the
multipole order lmax. A plane wave travelling along direction with its
electric field along polarization gives the scattering, extinction and
absorption cross sections; average gives the cross sections averaged over all
orientations and both polarizations, from a T-matrix of the whole cluster
about the origin. Each sphere has a radius, a position and an index: a
number, [n, k] with k >= 0 absorbing, or a material from the materials tool.
The surrounding medium is lossless. Lengths are in nanometres. Results
converge with lmax; coupling compares the cluster with the same spheres far
apart. For one sphere the extinction is compared with a separate Mie series.
Dimers and oligomers of nanoparticles are such clusters.
"""
import math
import numpy as np
from scipy import special
import treams
from optics_photonics import data, materials
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'spheres': ([{'radius_nm': 100, 'index': 1.5, 'position_nm': [0, 0, -125]},
                     {'radius_nm': 100, 'index': 1.5, 'position_nm': [0, 0, 125]}],
                    'spheres with radius_nm, index (number, [n, k] or material) and position_nm [x, y, z]'),
        'medium_index': (1.0, 'real index of the surrounding medium'),
        'wavelength_nm': ([500, 600, 700], 'vacuum wavelengths in nm, or {"start", "stop", "points"}'),
        'lmax': (4, 'multipole order of each sphere; increase until the cross sections stop changing'),
        'direction': ([1, 0, 0], 'propagation direction of the incident plane wave'),
        'polarization': ([0, 0, 1], 'electric field direction of the incident wave, normal to direction'),
        'average': (True, 'also compute cross sections averaged over orientations and polarizations'),
    },
    'results': 'cross_sections.npz/.json with Csca, Cext, Cabs (and orientation averages) over wavelength in nm^2; coupling; the wavelength of largest extinction',
    'checks': 'energy_error: largest |Cext - Csca| / Cext for lossless spheres; mie_difference for a single sphere',
}
p = parameters(PROGRAM, INPUTS)
grid = p['wavelength_nm']
wavelengths = np.linspace(grid['start'], grid['stop'], int(grid['points'])) if isinstance(grid, dict) else np.atleast_1d(np.asarray(grid, float))
direction = np.asarray(p['direction'], float)
direction /= np.linalg.norm(direction)
polarization = np.asarray(p['polarization'], float)
polarization = polarization - direction * (polarization @ direction)
if not p['spheres'] or np.linalg.norm(polarization) < 1e-9:
    raise ValueError('Give at least one sphere, and a polarization that is not parallel to direction')
polarization /= np.linalg.norm(polarization)
medium = float(p['medium_index'])
pages = {}


def index(entry, wavelength):
    if isinstance(entry, str):
        pages[entry] = materials.resolve(entry)
        return materials.index_at(entry, wavelength / 1000)
    return complex(entry[0], abs(entry[1])) if isinstance(entry, (list, tuple)) else complex(entry)


def mie(m, x, orders):
    """Extinction and scattering efficiencies of a sphere (Bohren and Huffman), m = n + ik relative index."""
    n = np.arange(1, orders + 1)
    jx, jmx = special.spherical_jn(n, x), special.spherical_jn(n, m * x)
    hx = jx + 1j * special.spherical_yn(n, x)
    djx, djmx = special.spherical_jn(n, x, True), special.spherical_jn(n, m * x, True)
    dhx = djx + 1j * special.spherical_yn(n, x, True)
    psi, dpsi = x * jx, jx + x * djx
    psim, dpsim = m * x * jmx, jmx + m * x * djmx
    xi, dxi = x * hx, hx + x * dhx
    a = (m * psim * dpsi - psi * dpsim) / (m * psim * dxi - xi * dpsim)
    b = (psim * dpsi - m * psi * dpsim) / (psim * dxi - m * xi * dpsim)
    return (2 / x ** 2 * np.sum((2 * n + 1) * (a + b).real), 2 / x ** 2 * np.sum((2 * n + 1) * (abs(a) ** 2 + abs(b) ** 2)))


rows, averages, alone, lossless, mie_difference = [], [], [], True, 0.0
positions = [list(map(float, sphere.get('position_nm', [0, 0, 0]))) for sphere in p['spheres']]
reach = max(np.linalg.norm(position) + float(sphere['radius_nm']) for position, sphere in zip(positions, p['spheres']))
for wavelength in wavelengths:
    k0 = 2 * math.pi / wavelength
    outside = treams.Material(medium ** 2)
    singles = []
    for sphere in p['spheres']:
        n = index(sphere['index'], wavelength)
        lossless = lossless and abs(n.imag) < 1e-12
        singles.append(treams.TMatrix.sphere(int(p['lmax']), k0, float(sphere['radius_nm']), [treams.Material(n ** 2), outside]))
    wave = lambda tm: treams.plane_wave(list(k0 * medium * direction), list(polarization), k0=tm.k0, material=tm.material)  # noqa: E731
    if len(singles) == 1:
        cluster = singles[0]  # cross sections do not depend on where a single sphere sits
    else:
        cluster = treams.TMatrix.cluster(singles, positions).interaction.solve()
    sca, ext = cluster.xs(wave(cluster))
    rows.append([float(sca), float(ext), float(ext - sca)])
    alone.append(float(sum(single.xs(wave(single))[1] for single in singles)))
    if p['average']:
        order = int(p['lmax']) + int(math.ceil(k0 * medium * reach)) + 2
        whole = cluster.expand(treams.SphericalWaveBasis.default(order)) if len(singles) > 1 else cluster
        averages.append([float(whole.xs_sca_avg), float(whole.xs_ext_avg)])
    if len(singles) == 1:
        sphere = p['spheres'][0]
        x = k0 * medium * float(sphere['radius_nm'])
        qext, _ = mie(index(sphere['index'], wavelength) / medium, x, int(x + 4 * x ** (1 / 3) + 2) + 10)
        mie_difference = max(mie_difference, abs(ext / (qext * math.pi * float(sphere['radius_nm']) ** 2) - 1))
table = np.asarray(rows)
axes = ['wavelength_nm']
arrays = {
    'Csca': data.quantity(table[:, 0], 'scattering cross section', unit='nm^2', axes=axes, materials=pages,
                          direction=direction.tolist(), polarization=polarization.tolist(), time_dependence='exp(-i omega t)'),
    'Cext': data.quantity(table[:, 1], 'extinction cross section', unit='nm^2', axes=axes),
    'Cabs': data.quantity(table[:, 2], 'absorption cross section', unit='nm^2', axes=axes),
    'coupling': data.quantity(table[:, 1] / np.asarray(alone), 'extinction over that of the same spheres apart', unit='1', axes=axes),
    'wavelength_nm': data.quantity(wavelengths, 'vacuum wavelength', unit='nm'),
}
if averages:
    mean = np.asarray(averages)
    arrays['Csca_average'] = data.quantity(mean[:, 0], 'scattering cross section averaged over orientation and polarization', unit='nm^2', axes=axes)
    arrays['Cext_average'] = data.quantity(mean[:, 1], 'extinction cross section averaged over orientation and polarization', unit='nm^2', axes=axes)
saved = data.save(OUTPUT_DIR / 'cross_sections', arrays)
peak = int(np.argmax(table[:, 1]))
RESULT = {'data': saved['data'], 'spheres': len(p['spheres']), 'extinction_peak_nm': float(wavelengths[peak]), 'first': {'wavelength_nm': float(wavelengths[0]), 'Csca': rows[0][0],
          'Cext': rows[0][1], 'Cabs': rows[0][2], 'coupling': rows[0][1] / alone[0], **({'Cext_average': averages[0][1]} if averages else {})},
          'materials': pages,
          'checks': {'energy_error': float(np.max(np.abs(table[:, 1] - table[:, 0]) / table[:, 1])) if lossless else None,
                     'mie_difference': mie_difference if len(p['spheres']) == 1 else None}}
