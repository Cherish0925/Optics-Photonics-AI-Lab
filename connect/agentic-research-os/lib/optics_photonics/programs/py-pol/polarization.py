"""Fully polarized light through ideal polarizers and wave plates (Jones calculus).

py-pol propagates a linearly polarized Jones vector through elements in
order; azimuths in degrees from x. The Stokes parameters of the output are
reported with the Jones amplitudes, which keep py-pol's phase convention.
Arbitrary Jones and Mueller models use a native program.
"""
import math
import numpy as np
from py_pol.jones_vector import Jones_vector
from py_pol.jones_matrix import Jones_matrix
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'azimuth_deg': (0, 'azimuth of the incident linear polarization in degrees from x'),
        'intensity': (1, 'incident intensity'),
        'elements': ([{'type': 'polarizer', 'azimuth_deg': 45}], 'elements in order: type polarizer, quarter_waveplate or half_waveplate, with azimuth_deg'),
    },
    'results': 'output intensity, Jones amplitudes [x, y] as [real, imag], and Stokes parameters S0..S3',
    'checks': 'malus: for a single polarizer, I0 cos^2 of the angle between polarization and polarizer',
}
p = parameters(PROGRAM, INPUTS)
if float(p['intensity']) <= 0:
    raise ValueError('intensity must be positive')
field = Jones_vector('input')
field.linear_light(azimuth=math.radians(p['azimuth_deg']), intensity=float(p['intensity']))
methods = {'polarizer': 'diattenuator_perfect', 'quarter_waveplate': 'quarter_waveplate', 'half_waveplate': 'half_waveplate'}
for element in p['elements']:
    if element['type'] not in methods:
        raise ValueError('Element type must be polarizer, quarter_waveplate or half_waveplate')
    matrix = Jones_matrix(element['type'])
    getattr(matrix, methods[element['type']])(azimuth=math.radians(element.get('azimuth_deg', 0)))
    field = matrix * field
ex, ey = np.asarray(field.M).reshape(2)
stokes = [abs(ex) ** 2 + abs(ey) ** 2, abs(ex) ** 2 - abs(ey) ** 2, 2 * (ex * np.conj(ey)).real, -2 * (ex * np.conj(ey)).imag]
single = len(p['elements']) == 1 and p['elements'][0]['type'] == 'polarizer'
malus = float(p['intensity']) * math.cos(math.radians(p['elements'][0].get('azimuth_deg', 0) - p['azimuth_deg'])) ** 2 if single else None
RESULT = {'intensity': float(field.parameters.intensity()), 'jones_xy': [[float(v.real), float(v.imag)] for v in (ex, ey)],
          'stokes': [float(v) for v in stokes], 'checks': {'malus': malus}}
