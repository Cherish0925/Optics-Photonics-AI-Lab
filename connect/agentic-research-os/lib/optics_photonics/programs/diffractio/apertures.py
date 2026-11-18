"""Diffraction of a plane wave by a slit, a double slit or a grating (Rayleigh-Sommerfeld, diffractio).

diffractio samples a one-dimensional scalar field (the aperture is uniform
along y), multiplies a plane wave by the aperture transmission and
propagates it to each distance with the Rayleigh-Sommerfeld integral
evaluated by fast Fourier transforms, valid from the near to the far field.
aperture is slit (width_um), double_slit (width_um, separation_um) or
grating (a binary amplitude grating of period_um, fill_factor and periods,
centred). Intensities are relative to the incident plane wave. The Fresnel
number N_F = (D/2)^2 / (lambda z) of the aperture size D tells near
(N_F > 1) from far field (N_F << 1); where N_F < 0.05 the pattern is
compared with the Fraunhofer expression of the same aperture, with the
obliquity and 1/r spreading of a line source, inside the first three
side lobes of one slit.
"""
import math
import numpy as np
from diffractio.scalar_masks_X import Scalar_mask_X
from diffractio.scalar_sources_X import Scalar_source_X
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'aperture': ('double_slit', 'slit, double_slit or grating'),
        'width_um': (20.0, 'slit width (and grating slit width = fill_factor * period_um)'),
        'separation_um': (100.0, 'distance between the centres of the two slits'),
        'period_um': (50.0, 'grating period'),
        'fill_factor': (0.5, 'open fraction of a grating period'),
        'periods': (10, 'number of grating periods'),
        'wavelength_um': (0.6328, 'wavelength'),
        'distance_mm': ([5, 50, 500], 'propagation distances'),
        'window_um': (8000.0, 'width of the computed field'),
        'samples': (131072, 'samples across the window; finer sampling resolves the aperture edges'),
    },
    'results': 'pattern.npz/.json with intensity over distance and x; Fresnel numbers; the far-field comparison',
    'checks': 'fraunhofer_difference: largest difference of the peak-normalized pattern from the Fraunhofer expression where N_F < 0.05',
}
p = parameters(PROGRAM, INPUTS)
wl, kind = float(p['wavelength_um']), p['aperture']
x = np.linspace(-p['window_um'] / 2, p['window_um'] / 2, int(p['samples']))
source = Scalar_source_X(x, wl)
source.plane_wave()
mask = Scalar_mask_X(x, wl)
a = float(p['width_um'])
if kind == 'slit':
    mask.slit(x0=0, size=a)
    size = a
elif kind == 'double_slit':
    mask.double_slit(x0=0, size=a, separation=float(p['separation_um']))
    size = float(p['separation_um']) + a
elif kind == 'grating':
    period, count = float(p['period_um']), int(p['periods'])
    a = float(p['fill_factor']) * period
    centres = (np.arange(count) - (count - 1) / 2) * period
    mask.u = np.where(np.any(np.abs(x[:, None] - centres[None, :]) <= a / 2, axis=1), 1.0, 0.0).astype(complex)
    size = count * period
else:
    raise ValueError('aperture is slit, double_slit or grating')
field = source * mask
distances = np.atleast_1d(np.asarray(p['distance_mm'], dtype=float))
patterns, fresnel, differences = [], [], []
for distance in distances:
    z = distance * 1000.0
    I = np.abs(field.RS(z=z, new_field=True, verbose=False).u) ** 2
    patterns.append(I)
    number = (size / 2) ** 2 / (wl * z)
    fresnel.append(number)
    if number < 0.05:
        r = np.sqrt(x ** 2 + z ** 2)
        s = x / r
        beta = np.pi * a * s / wl
        envelope = np.sinc(beta / np.pi) ** 2
        if kind == 'double_slit':
            factor = np.cos(np.pi * float(p['separation_um']) * s / wl) ** 2
        elif kind == 'grating':
            phase = np.pi * float(p['period_um']) * s / wl
            factor = np.where(np.abs(np.sin(phase)) < 1e-12, count ** 2, (np.sin(count * phase) / np.where(np.sin(phase) == 0, 1, np.sin(phase))) ** 2)
        else:
            factor = 1.0
        expected = envelope * factor * (z / r) ** 2 / r
        inside = np.abs(s) < 3 * wl / a
        differences.append(float(np.max(np.abs(I[inside] / I[inside].max() - expected[inside] / expected[inside].max()))))
patterns = np.asarray(patterns)
saved = data.save(OUTPUT_DIR / 'pattern', {
    'intensity': data.quantity(patterns, 'intensity relative to the incident plane wave', unit='1',
                               axes=['distance_mm', {'name': 'x', 'unit': 'um', 'start': float(x[0]), 'step': float(x[1] - x[0])}],
                               wavelength_um=wl, aperture=kind),
    'distance_mm': data.quantity(distances, 'propagation distance', unit='mm'),
    'transmission': data.quantity(np.abs(mask.u) ** 2, 'aperture transmission', unit='1',
                                  axes=[{'name': 'x', 'unit': 'um', 'start': float(x[0]), 'step': float(x[1] - x[0])}]),
})
RESULT = {'data': saved['data'], 'aperture': kind, 'size_um': size, 'fresnel_numbers': fresnel,
          'peak_intensity': [float(pattern.max()) for pattern in patterns],
          'fringe_spacing_um_at_last': float(wl * distances[-1] * 1000 / float(p['separation_um'])) if kind == 'double_slit' else None,
          'checks': {'fraunhofer_difference': max(differences) if differences else None}}
