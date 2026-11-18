"""Gaussian eigenmode of an optical resonator from its round-trip ray matrix: stability, waists, spot sizes, Gouy phase, mode spacing.

A resonator is a closed sequence of free spaces, curved mirrors and thin
lenses. Its round-trip ABCD matrix M = [[A, B], [C, D]] from a reference plane
back to that plane holds a self-consistent Gaussian beam when |A + D| < 2,
with complex beam parameter 1/q = (D - A)/(2B) - i sqrt(1 - ((A + D)/2)^2)/|B|
and round-trip Gouy phase arccos((A + D)/2) with the sign of B. A mirror of
radius of curvature R (concave positive) acts as a lens of focal length R/2;
lengths are in mm and the wavelength is that in the medium of the cavity.
The beam radius w (1/e^2 intensity) and the radius of curvature of the
wavefront are followed along the round trip, and every waist inside a space
is located exactly where Re(q) = 0. The free spectral range is c / (optical
round-trip length); the Hermite-Gaussian mode TEM_mn lies (m + n) times
Gouy / (2 pi) free spectral ranges above TEM_00, modulo one. With elements
empty, the cavity is a standing wave between mirrors of radii r1_mm and r2_mm
a length_mm apart (reference plane on mirror 1), and its waist, spot sizes
and mode spacing are also computed from the closed-form two-mirror
expressions with g = 1 - L/R (Siegman, Lasers, chapter 19) as a check. An
unstable resonator is reported as such, without a mode.
"""
import math
import numpy as np
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'wavelength_nm': (1064.0, 'vacuum wavelength in nm'),
        'r1_mm': (None, 'radius of curvature of mirror 1 in mm, concave positive; null is flat'),
        'r2_mm': (1000.0, 'radius of curvature of mirror 2 in mm'),
        'length_mm': (500.0, 'mirror spacing in mm'),
        'index': (1.0, 'refractive index inside the cavity'),
        'elements': ([], 'round trip from the reference plane instead of two mirrors: {"space_mm": d}, {"mirror_mm": R} or {"lens_mm": f}'),
        'max_order': (4, 'largest m + n of the transverse modes listed'),
        'samples': (400, 'beam samples along the round trip'),
    },
    'results': 'resonator.npz/.json: beam radius and wavefront curvature along the round trip; stability, waists, spot sizes on the '
               'mirrors, round-trip Gouy phase, free spectral range, transverse mode spacing and TEM_mn frequency offsets',
    'checks': 'two_mirror_difference: largest relative difference of the waist, the spot sizes on both mirrors and the transverse '
              'mode spacing from the closed-form two-mirror expressions',
}
p = parameters(PROGRAM, INPUTS)
wavelength = float(p['wavelength_nm']) * 1e-6 / float(p['index'])            # mm, in the medium
two_mirror = not p['elements']
if two_mirror:
    length = float(p['length_mm'])
    radii = [None if p['r1_mm'] is None else float(p['r1_mm']), None if p['r2_mm'] is None else float(p['r2_mm'])]
    elements = [{'mirror_mm': radii[0]}, {'space_mm': length}, {'mirror_mm': radii[1]}, {'space_mm': length}]
else:
    elements = list(p['elements'])
if wavelength <= 0 or not any('space_mm' in e for e in elements):
    raise ValueError('wavelength_nm is positive and the round trip holds at least one space')


def matrix(element):
    if 'space_mm' in element:
        return np.array([[1.0, float(element['space_mm'])], [0.0, 1.0]])
    radius = element.get('mirror_mm') if 'mirror_mm' in element else element.get('lens_mm')
    focal = None if radius is None else float(radius) / (2 if 'mirror_mm' in element else 1)
    return np.eye(2) if focal is None else np.array([[1.0, 0.0], [-1.0 / focal, 1.0]])


trip = np.eye(2)
for element in elements:
    trip = matrix(element) @ trip
A, B, C, D = trip.ravel()
half_trace = (A + D) / 2
round_trip = sum(float(e['space_mm']) for e in elements if 'space_mm' in e)
fsr = 299792458.0 / (round_trip * float(p['index']) * 1e-3) / 1e6        # MHz
RESULT = {'stable': bool(abs(half_trace) < 1 and B != 0), 'half_trace': float(half_trace), 'round_trip_matrix': trip.tolist(),
          'free_spectral_range_MHz': fsr}
if two_mirror:
    g1, g2 = (1 - (length / r if r else 0.0) for r in radii)
    RESULT.update(g1=g1, g2=g2, g1g2=g1 * g2)
if not RESULT['stable']:
    RESULT['checks'] = {'two_mirror_difference': None}
else:
    q = 1 / complex((D - A) / (2 * B), -math.sqrt(1 - half_trace ** 2) / abs(B))
    gouy = math.copysign(math.acos(half_trace), B)
    spacing = (gouy / (2 * math.pi)) % 1.0                                 # transverse mode spacing in free spectral ranges

    def radius_um(value):
        return math.sqrt(wavelength * abs(value) ** 2 / (math.pi * value.imag)) * 1e3   # w = sqrt(lambda |q|^2 / (pi Im q))

    positions, beam, curvature, waists, surfaces, z = [], [], [], [], [], 0.0
    per_mm = int(p['samples']) / round_trip
    for element in elements:
        if 'space_mm' in element:
            d = float(element['space_mm'])
            for s in np.linspace(0.0, d, max(2, int(math.ceil(d * per_mm)) + 1)):
                positions.append(z + s); beam.append(radius_um(q + s))
                curvature.append((q + s).real + (q + s).imag ** 2 / (q + s).real if abs((q + s).real) > 1e-12 else math.inf)
            if 0.0 <= -q.real <= d:                                       # a waist inside this space
                waists.append({'position_mm': z - q.real, 'radius_um': math.sqrt(wavelength * q.imag / math.pi) * 1e3,
                               'rayleigh_range_mm': q.imag})
            q, z = q + d, z + d
        else:
            surfaces.append({**element, 'position_mm': z, 'beam_radius_um': radius_um(q)})
            a, b, c, dd = matrix(element).ravel()
            q = (a * q + b) / (c * q + dd)
    modes = [{'order': n, 'offset_fsr': (n * spacing) % 1.0, 'offset_MHz': ((n * spacing) % 1.0) * fsr} for n in range(int(p['max_order']) + 1)]
    RESULT.update({'round_trip_gouy_rad': gouy, 'transverse_mode_spacing_fsr': spacing, 'transverse_mode_spacing_MHz': spacing * fsr,
                   'waists': waists, 'surfaces': surfaces, 'modes': modes})
    difference = None
    if two_mirror:
        scale = math.sqrt(wavelength * length / math.pi)
        w1 = scale * (g2 / (g1 * (1 - g1 * g2))) ** 0.25 if g1 else None
        w2 = scale * (g1 / (g2 * (1 - g1 * g2))) ** 0.25 if g2 else None
        w0 = scale * (g1 * g2 * (1 - g1 * g2) / (g1 + g2 - 2 * g1 * g2) ** 2) ** 0.25
        closed = (math.acos(math.copysign(math.sqrt(g1 * g2), g1)) / math.pi) % 1.0    # mode spacing in FSR: 2 acos(+-sqrt(g1 g2)) / 2 pi
        spots = [s['beam_radius_um'] for s in surfaces]
        inside = min(waists, key=lambda w: w['radius_um']) if waists else None    # a convex mirror can leave the waist outside
        RESULT.update({'waist_um': inside['radius_um'] if inside else None, 'waist_from_mirror1_mm': inside['position_mm'] if inside else None,
                       'spot_mirror1_um': spots[0], 'spot_mirror2_um': spots[1]})
        parts = [min(abs(spacing - closed), 1 - abs(spacing - closed))] + ([abs(inside['radius_um'] / (w0 * 1e3) - 1)] if inside else [])
        parts += [abs(spot / (w * 1e3) - 1) for spot, w in zip(spots, (w1, w2)) if w]
        difference = max(parts)
    saved = data.save(OUTPUT_DIR / 'resonator', {
        'position_mm': data.quantity(positions, 'position along the round trip from the reference plane', unit='mm'),
        'beam_radius': data.quantity(beam, 'beam radius at 1/e^2 intensity', unit='um', axes=['position_mm'], wavelength_nm=float(p['wavelength_nm'])),
        'curvature': data.quantity(curvature, 'radius of curvature of the wavefront, infinite at a waist', unit='mm', axes=['position_mm']),
    })
    RESULT.update(data=saved['data'], checks={'two_mirror_difference': difference})
