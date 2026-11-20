"""Modulation transfer function of an imaging system with Zernike aberrations (prysm).

prysm samples a circular pupil of diameter epd_mm, adds the wavefront
error of Noll-ordered Zernike modes given as RMS optical path differences
in nm, propagates to the focus of a lens of focal length efl_mm by a
Fraunhofer transform with Q-fold padding, and takes the MTF as the
normalized modulus of the Fourier transform of the point spread function.
Spatial frequencies are in cycles/mm up to the incoherent cutoff
1 / (lambda N) with N = efl / epd. The MTF along x and y, the values at the
requested frequencies and the Strehl ratio (peak over the peak of the
unaberrated system) are reported. Without aberrations the MTF is compared
with the analytic diffraction-limited MTF of a circular pupil.
"""
import math
import numpy as np
from prysm.coordinates import make_xy_grid, cart_to_polar
from prysm.geometry import circle
from prysm.otf import mtf_from_psf
from prysm.polynomials import noll_to_nm, zernike_nm
from prysm.propagation import Wavefront
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'epd_mm': (10.0, 'entrance pupil diameter'),
        'efl_mm': (100.0, 'effective focal length'),
        'wavelength_um': (0.55, 'wavelength'),
        'zernike_rms_nm': ({}, 'RMS optical path difference in nm per Noll index, for example {"4": 30, "7": 20}'),
        'samples': (256, 'pupil samples across the diameter'),
        'Q': (2, 'padding factor of the focal-plane transform; 2 samples the PSF at Nyquist'),
        'frequencies': ([10, 30, 50, 100], 'spatial frequencies in cycles/mm whose MTF is reported'),
    },
    'domains': ['imaging', 'wave'],
    'results': 'mtf.npz/.json with the MTF along x and y and the diffraction limit over frequency; the PSF; Strehl ratio',
    'checks': 'diffraction_limit_difference: largest |MTF - analytic MTF| without aberrations',
}
p = parameters(PROGRAM, INPUTS)
epd, efl, wavelength = float(p['epd_mm']), float(p['efl_mm']), float(p['wavelength_um'])
x, y = make_xy_grid(int(p['samples']), diameter=epd)
r, theta = cart_to_polar(x, y)
pupil = circle(epd / 2, r)
dx = float(x[0, 1] - x[0, 0])
opd = np.zeros_like(r)
for noll, rms in p['zernike_rms_nm'].items():
    n, m = noll_to_nm(int(noll))
    opd += float(rms) * zernike_nm(n, m, r / (epd / 2), theta, norm=True)
opd *= pupil


def focus(error):
    return Wavefront.from_amp_and_phase(pupil, error, wavelength, dx).focus(efl, Q=float(p['Q'])).intensity


psf = focus(opd)
perfect = focus(np.zeros_like(opd))
strehl = float(psf.data.max() / perfect.data.max())
mtf = mtf_from_psf(psf)
fx, mx = mtf.slices().x
fy, my = mtf.slices().y
cutoff = 1 / (wavelength * 1e-3 * efl / epd)
keep = (fx >= 0) & (fx <= cutoff)
frequencies, along_x = fx[keep], mx[keep]
along_y = np.interp(frequencies, fy[fy >= 0], my[fy >= 0])
nu = np.clip(frequencies / cutoff, 0, 1)
limit = 2 / np.pi * (np.arccos(nu) - nu * np.sqrt(1 - nu ** 2))
axes = ['frequency_per_mm']
size = psf.data.shape[0]
spacing = float(psf.dx)  # um
saved = data.save(OUTPUT_DIR / 'mtf', {
    'mtf_x': data.quantity(along_x, 'MTF along x', unit='1', axes=axes, wavelength_um=wavelength, f_number=efl / epd),
    'mtf_y': data.quantity(along_y, 'MTF along y', unit='1', axes=axes),
    'diffraction_limit': data.quantity(limit, 'diffraction-limited MTF of a circular pupil', unit='1', axes=axes),
    'frequency_per_mm': data.quantity(frequencies, 'spatial frequency', unit='1/mm'),
    'psf': data.quantity(psf.data / psf.data.sum(), 'point spread function', unit='1', normalization='unit sum',
                         axes=[{'name': 'y', 'unit': 'um', 'start': -spacing * (size // 2), 'step': spacing},
                               {'name': 'x', 'unit': 'um', 'start': -spacing * (size // 2), 'step': spacing}]),
})
asked = [float(v) for v in p['frequencies']]
RESULT = {'data': saved['data'], 'strehl': strehl, 'cutoff_per_mm': cutoff, 'f_number': efl / epd,
          'mtf_at': [{'frequency_per_mm': f, 'x': float(np.interp(f, frequencies, along_x)), 'y': float(np.interp(f, frequencies, along_y)),
                      'limit': float(np.interp(f, frequencies, limit))} for f in asked],
          'checks': {'diffraction_limit_difference': float(np.max(np.abs(along_x - limit))) if not p['zernike_rms_nm'] else None}}
