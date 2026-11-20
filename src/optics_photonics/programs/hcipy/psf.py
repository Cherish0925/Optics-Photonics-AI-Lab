"""Point spread function of a circular pupil with obstruction and Zernike aberrations.

HCIPy propagates a monochromatic wavefront from the pupil to the focal plane
by a Fraunhofer (matrix Fourier) transform with a unit focal length, so
focal coordinates are angles in radians. Aberrations are given as RMS path
differences of Noll-ordered Zernike modes; the phase is 2 pi times the path
difference over the wavelength. The Strehl ratio is the peak intensity over
that of the unaberrated pupil; encircled energy is a fraction of the pupil
power, so power outside the computed focal field is not counted.
"""
import numpy as np
import hcipy as hp
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'wavelength_m': (550e-9, 'wavelength in metres'),
        'diameter_m': (1, 'pupil diameter in metres'),
        'samples': (128, 'pupil samples across the diameter'),
        'pixels_per_lambda_over_d': (4, 'focal samples per lambda/D'),
        'radius_lambda_over_d': (8, 'radius of the computed focal field in lambda/D'),
        'obstruction': (0, 'central obstruction diameter over the pupil diameter'),
        'zernike_rms_nm': ({}, 'RMS path difference in nm per Noll index, for example {"4": 30} for defocus'),
    },
    'domains': ['imaging', 'wave'],
    'results': 'psf.npz/.json: intensity normalized to unit integral over the computed field, encircled energy; Strehl ratio',
    'checks': 'encircled energy at 1.22 lambda/D: 0.838 for an unobstructed, unaberrated pupil, approached as samples grow',
}
p = parameters(PROGRAM, INPUTS)
wavelength, diameter = float(p['wavelength_m']), float(p['diameter_m'])
if wavelength <= 0 or diameter <= 0 or int(p['samples']) < 8 or not 0 <= float(p['obstruction']) < 1:
    raise ValueError('wavelength_m and diameter_m are positive, samples at least 8, obstruction from 0 to below 1')
pupil = hp.make_pupil_grid(int(p['samples']), diameter)
if p['obstruction']:
    shape = hp.make_obstructed_circular_aperture(diameter, float(p['obstruction']))
else:
    shape = hp.make_circular_aperture(diameter)
aperture = hp.evaluate_supersampled(shape, pupil, 4)
coefficients = {int(k): float(v) for k, v in p['zernike_rms_nm'].items()}
path = 0
if coefficients:
    modes = hp.make_zernike_basis(max(coefficients), diameter, pupil)
    path = sum(rms * 1e-9 * modes[k - 1] for k, rms in coefficients.items())
focal = hp.make_focal_grid(float(p['pixels_per_lambda_over_d']), float(p['radius_lambda_over_d']), spatial_resolution=wavelength / diameter)
propagator = hp.FraunhoferPropagator(pupil, focal)
field = hp.Wavefront(aperture * np.exp(2j * np.pi * path / wavelength), wavelength)
image = propagator(field)
reference = propagator(hp.Wavefront(aperture, wavelength))
intensity = np.asarray(image.intensity.shaped)
total = float(np.sum(image.intensity * focal.weights))
strehl = float(image.intensity.max() / reference.intensity.max())
radius = np.hypot(focal.x, focal.y) / (wavelength / diameter)
order = np.argsort(radius)
encircled = np.cumsum(np.asarray(image.power)[order]) / field.total_power
radii = np.linspace(0, float(p['radius_lambda_over_d']), 321)
ee = np.interp(radii, np.asarray(radius)[order], encircled)
ee_airy = float(np.interp(1.2197, np.asarray(radius)[order], encircled))
x = np.unique(np.asarray(focal.x)); y = np.unique(np.asarray(focal.y))
saved = data.save(OUTPUT_DIR / 'psf', {
    'intensity': data.quantity(intensity / total, 'point spread function', unit='1/sr',
                               axes=[{'name': 'y', 'unit': 'rad', 'start': float(y[0]), 'step': float(y[1] - y[0])},
                                     {'name': 'x', 'unit': 'rad', 'start': float(x[0]), 'step': float(x[1] - x[0])}],
                               normalization='integral over the computed field = 1', wavelength={'value': wavelength, 'unit': 'm'}),
    'x_rad': data.quantity(np.asarray(focal.x.shaped), 'focal angle x', unit='rad'),
    'y_rad': data.quantity(np.asarray(focal.y.shaped), 'focal angle y', unit='rad'),
    'encircled_energy': data.quantity(ee, 'encircled energy', unit='1', axes=['radius'], normalization='fraction of pupil power'),
    'radius': data.quantity(radii, 'radius', unit='lambda/D'),
})
RESULT = {'shape': list(intensity.shape), 'normalization': 'integral over computed focal grid = 1', 'data': saved['data'],
          'strehl': strehl, 'encircled_energy_1_22': ee_airy, 'checks': {'encircled_energy_1_22': ee_airy}}
