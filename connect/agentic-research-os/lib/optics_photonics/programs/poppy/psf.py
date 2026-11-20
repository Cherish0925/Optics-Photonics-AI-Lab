"""Point spread function of a circular pupil with Zernike aberrations on a detector.

POPPY propagates from the pupil to a detector sampled in arcseconds per
pixel by a matrix Fourier transform; the PSF is normalized to the entrance
power, so a finite detector holds less than 1. Aberrations are RMS path
differences of Noll-ordered Zernike modes in nm, in POPPY's convention that a
positive value advances the wavefront. The Strehl ratio is the ratio of the
sampled peaks of the aberrated and unaberrated PSFs; oversample refines the
sampling of the calculation.
"""
import numpy as np
import astropy.units as u
import poppy
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'wavelength_m': (550e-9, 'wavelength in metres'),
        'diameter_m': (1, 'pupil diameter in metres'),
        'pixel_arcsec': (0.02, 'detector pixel scale in arcseconds'),
        'pixels': (64, 'detector pixels across'),
        'oversample': (1, 'oversampling of the detector in the calculation'),
        'zernike_rms_nm': ({}, 'RMS path difference in nm per Noll index, for example {"4": 30} for defocus'),
    },
    'domains': ['imaging', 'wave'],
    'results': 'psf.fits; psf.npz/.json with the PSF over arcseconds; captured power and Strehl ratio',
    'checks': 'captured_power: fraction of the entrance power on the detector',
}
p = parameters(PROGRAM, INPUTS)
wavelength, diameter = float(p['wavelength_m']), float(p['diameter_m'])
if wavelength <= 0 or diameter <= 0 or float(p['pixel_arcsec']) <= 0 or int(p['pixels']) < 2:
    raise ValueError('wavelength_m, diameter_m and pixel_arcsec are positive; pixels is at least 2')
coefficients = {int(k): float(v) for k, v in p['zernike_rms_nm'].items()}


def compute(aberrated):
    system = poppy.OpticalSystem(oversample=int(p['oversample']))
    system.add_pupil(poppy.CircularAperture(radius=diameter / 2))
    if aberrated and coefficients:
        values = [0.0] * max(coefficients)
        for k, rms in coefficients.items():
            values[k - 1] = rms * 1e-9
        system.add_pupil(poppy.ZernikeWFE(radius=diameter / 2, coefficients=values))
    system.add_detector(pixelscale=float(p['pixel_arcsec']), fov_pixels=int(p['pixels']))
    return system.calc_psf(wavelength=wavelength)


psf = compute(True)
psf.writeto(OUTPUT_DIR / 'psf.fits', overwrite=True)
image = psf[0].data
strehl = float(image.max() / compute(False)[0].data.max()) if coefficients else 1.0
scale = float(p['pixel_arcsec'])
start = -(image.shape[0] - 1) / 2 * scale
saved = data.save(OUTPUT_DIR / 'psf', {
    'psf': data.quantity(image, 'point spread function', unit='1', normalization='fraction of entrance power per pixel',
                         axes=[{'name': 'y', 'unit': 'arcsec', 'start': start, 'step': scale},
                               {'name': 'x', 'unit': 'arcsec', 'start': start, 'step': scale}],
                         wavelength={'value': wavelength, 'unit': 'm'}, wavefront='positive leads'),
})
RESULT = {'shape': list(image.shape), 'captured_power': float(image.sum()), 'pixel_arcsec': p['pixel_arcsec'], 'data': saved['data'],
          'files': ['psf.fits'], 'strehl': strehl, 'checks': {'captured_power': float(image.sum())}}
