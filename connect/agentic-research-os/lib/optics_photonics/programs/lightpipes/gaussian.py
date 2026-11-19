"""Free-space propagation of a Gaussian beam in scalar diffraction theory.

LightPipes samples a square window and propagates the field over each
distance, by default with Forvard (angular spectrum) and optionally with its
Fresnel convolution. The waist is the 1/e field radius (1/e^2 intensity). The
beam radius at each distance is twice the root mean square width of the
computed intensity and is compared with w(z) = w0 sqrt(1 + (z/zR)^2),
zR = pi w0^2 / lambda. With a 1 mm waist at 532 nm, Forvard reproduced w(z) to
1e-5 out to 1.7 zR, while LightPipes 2.1.5 Fresnel gave radii 4 to 7 percent
larger whatever the sampling. The window must hold the beam with margin.
"""
import numpy as np
from LightPipes import Begin, Forvard, GaussBeam, Fresnel, Intensity
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'wavelength_m': (532e-9, 'wavelength in metres'),
        'window_m': (0.01, 'side of the square window in metres'),
        'waist_m': (0.001, 'waist radius (1/e field) in metres'),
        'distance_m': (1, 'propagation distance in metres; a number or a list'),
        'samples': (128, 'grid points per side'),
        'method': ('forvard', 'forvard (angular spectrum) or fresnel (LightPipes Fresnel convolution)'),
    },
    'results': 'beam.npz/.json with intensity and beam radius over distance, and the complex field at the last distance',
    'checks': 'radius_error: largest relative difference between computed and analytic beam radius',
}
p = parameters(PROGRAM, INPUTS)
size, wavelength, waist, samples = float(p['window_m']), float(p['wavelength_m']), float(p['waist_m']), int(p['samples'])
distances = np.atleast_1d(np.asarray(p['distance_m'], dtype=float))
if size <= 0 or wavelength <= 0 or waist <= 0 or samples < 2:
    raise ValueError('window_m, wavelength_m and waist_m are positive; samples is at least 2')
if np.any(distances < 0):
    raise ValueError('Use a native propagation program for negative distance')
if p['method'] not in ('forvard', 'fresnel'):
    raise ValueError('method is forvard or fresnel')
propagate = Forvard if p['method'] == 'forvard' else Fresnel
x = np.arange(samples) * size / samples - size / 2
X, Y = np.meshgrid(x, x)
intensities, radii = [], []
for distance in distances:
    field = GaussBeam(Begin(size, wavelength, samples), waist)
    field = propagate(field, distance) if distance else field
    intensity = np.asarray(Intensity(field, 0))
    total = intensity.sum()
    cx, cy = (intensity * X).sum() / total, (intensity * Y).sum() / total
    radii.append(2 * np.sqrt((intensity * (X - cx) ** 2).sum() / total))
    intensities.append(intensity)
rayleigh = np.pi * waist ** 2 / wavelength
analytic = waist * np.sqrt(1 + (distances / rayleigh) ** 2)
axes = ['distance_m', {'name': 'y', 'unit': 'm', 'start': float(x[0]), 'step': size / samples},
        {'name': 'x', 'unit': 'm', 'start': float(x[0]), 'step': size / samples}]
saved = data.save(OUTPUT_DIR / 'beam', {
    'intensity': data.quantity(np.asarray(intensities), 'relative intensity', unit='1', axes=axes),
    'field': data.quantity(np.asarray(field.field), 'complex field at the last distance', unit='1', axes=axes[1:],
                           time_dependence='exp(-i omega t)'),
    'radius_m': data.quantity(np.asarray(radii), 'beam radius from the second moment', unit='m', axes=['distance_m']),
    'analytic_radius_m': data.quantity(analytic, 'Gaussian beam radius w(z)', unit='m', axes=['distance_m']),
    'distance_m': data.quantity(distances, 'propagation distance', unit='m'),
})
spacing = size / samples
RESULT = {'shape': list(intensity.shape), 'spacing_m': spacing, 'integrated_intensity_m2': float(intensity.sum() * spacing ** 2),
          'data': saved['data'], 'radius_m': [float(r) for r in radii], 'rayleigh_range_m': rayleigh, 'method': p['method'],
          'checks': {'radius_error': float(np.max(np.abs(np.asarray(radii) / analytic - 1)))}}
