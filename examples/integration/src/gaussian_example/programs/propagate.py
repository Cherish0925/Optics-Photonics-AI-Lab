"""Propagate an ideal Gaussian beam through free space.

The input wavelength is the wavelength in the homogeneous medium. The waist
is the 1/e field radius, also the 1/e-squared intensity radius, at z=0.
The Rayleigh distance is pi*w0**2/wavelength; the complex beam parameter is
q=z+i*zR. The direct beam-width expression is compared with Im(1/q).
The paraxial model assumes w0 much larger than wavelength and M-squared=1.
"""
import math
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'wavelength_um': [1.064, 'Wavelength in the medium, micrometres'],
        'waist_um': [100.0, 'Field 1/e radius at z=0, micrometres'],
        'distance_mm': [100.0, 'Signed distance from the waist, millimetres'],
    },
    'domains': ['wave', 'laser'],
    'results': 'Rayleigh distance, field radius, wavefront radius and Gouy phase at the selected plane',
    'checks': 'The radius from direct propagation agrees with the imaginary part of inverse q',
}

p = parameters(PROGRAM, INPUTS)
for name, value in p.items():
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(name + ' must be a finite number')
if p['wavelength_um'] <= 0 or p['waist_um'] <= 0:
    raise ValueError('wavelength_um and waist_um must be positive')
wavelength = p['wavelength_um'] * 1e-6
waist = p['waist_um'] * 1e-6
distance = p['distance_mm'] * 1e-3
rayleigh = math.pi * waist**2 / wavelength
q = complex(distance, rayleigh)
radius = waist * math.hypot(1.0, distance / rayleigh)
from_q = math.sqrt(-wavelength / (math.pi * (1 / q).imag))
error = abs(radius - from_q) / radius
RESULT = {
    'rayleigh_mm': rayleigh * 1e3,
    'radius_um': radius * 1e6,
    'wavefront_radius_mm': None if distance == 0 else distance * (1 + (rayleigh / distance)**2) * 1e3,
    'gouy_phase_rad': math.atan2(distance, rayleigh),
    'checks': {'complex_q_relative_error': error, 'passed': error < 1e-12},
}
