"""Ultrashort pulses in a fiber with Raman scattering and self-steepening: solitons and supercontinuum (laserfun).

laserfun integrates the generalized nonlinear Schrodinger equation for the
complex envelope A(z, t) with |A|^2 in watts: dispersion from the Taylor
coefficients beta_k (ps^k/m) about the centre wavelength, Kerr
nonlinearity gamma (1/(W m)), the delayed Raman response of silica and
self-steepening (the frequency dependence of the nonlinearity). The
defaults are the supercontinuum benchmark of Dudley, Genty and Coen (Rev.
Mod. Phys. 78, 1135, 2006): a 50 fs sech pulse of 10 kW at 835 nm in 15 cm
of photonic crystal fibre. The spectrum and the temporal intensity are
saved over distance. With loss_db_per_m = 0 the equation conserves the
photon number even with Raman scattering and self-steepening, and the
energy as well without them; both are reported. soliton_order is
sqrt(gamma P0 T0^2 / |beta2|) with T0 the 1/e half-width of the field.
"""
import math
import numpy as np
import laserfun as lf
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'pulse': ('sech', 'sech or gaussian'),
        'fwhm_ps': (0.050, 'intensity full width at half maximum'),
        'wavelength_nm': (835.0, 'centre wavelength'),
        'peak_power_w': (10000.0, 'peak power'),
        'length_m': (0.15, 'fibre length'),
        'betas': ([-11.830e-3, 8.1038e-5, -9.5205e-8, 2.0737e-10, -5.3943e-13, 1.3486e-15, -2.5495e-18, 3.0524e-21, -1.7140e-24],
                  'dispersion coefficients beta2, beta3, ... in ps^k/m'),
        'gamma_per_w_m': (0.11, 'nonlinear coefficient'),
        'loss_db_per_m': (0.0, 'propagation loss'),
        'raman': (True, 'include the delayed Raman response'),
        'self_steepening': (True, 'include self-steepening'),
        'window_ps': (12.5, 'time window'),
        'points': (8192, 'time samples'),
        'saves': (100, 'distances at which the fields are saved'),
    },
    'results': 'propagation.npz/.json with spectral and temporal intensity over distance; output -30 dB spectral width; soliton order',
    'checks': 'photon_number_error (lossless), energy_error (lossless, without Raman and self-steepening)',
}
p = parameters(PROGRAM, INPUTS)
if p['pulse'] not in ('sech', 'gaussian'):
    raise ValueError('pulse is sech or gaussian')
pulse = lf.Pulse(pulse_type=p['pulse'], fwhm_ps=float(p['fwhm_ps']), center_wavelength_nm=float(p['wavelength_nm']),
                 time_window_ps=float(p['window_ps']), power=float(p['peak_power_w']), npts=int(p['points']))
fiber = lf.Fiber(length=float(p['length_m']), center_wl_nm=float(p['wavelength_nm']), dispersion_format='GVD',
                 dispersion=[float(b) for b in p['betas']], gamma_W_m=float(p['gamma_per_w_m']), loss_dB_per_m=float(p['loss_db_per_m']))
result = lf.NLSE(pulse, fiber, nsaves=int(p['saves']), raman=bool(p['raman']), shock=bool(p['self_steepening']), print_status=False)
z, f_thz, t_ps, AW, AT = result.get_results()
z, f_thz, t_ps = np.asarray(z), np.asarray(f_thz), np.asarray(t_ps)
spectral = np.abs(np.asarray(AW)) ** 2
temporal = np.abs(np.asarray(AT)) ** 2
energy = np.trapezoid(temporal, t_ps, axis=1)                      # pJ
photons = np.trapezoid(spectral / np.abs(f_thz)[None, :], f_thz, axis=1)  # proportional to the photon number
lossless = float(p['loss_db_per_m']) == 0
c_nm_thz = 299792.458
out = spectral[-1] / spectral[-1].max()
band = f_thz[out > 1e-3]
width_nm = float(c_nm_thz / band.min() - c_nm_thz / band.max()) if band.size else None
T0 = float(p['fwhm_ps']) / (1.7627 if p['pulse'] == 'sech' else 1.6651)
beta2 = float(p['betas'][0]) if p['betas'] else 0.0
order = math.sqrt(float(p['gamma_per_w_m']) * float(p['peak_power_w']) * T0 ** 2 / abs(beta2)) if beta2 else None
axes_f = ['distance_m', 'frequency_thz']
saved = data.save(OUTPUT_DIR / 'propagation', {
    'spectrum_db': data.quantity(10 * np.log10(spectral / spectral.max() + 1e-30), 'spectral intensity relative to its maximum', unit='dB',
                                 axes=axes_f, raman=bool(p['raman']), self_steepening=bool(p['self_steepening'])),
    'intensity': data.quantity(temporal, 'temporal intensity', unit='W', axes=['distance_m', 'time_ps']),
    'distance_m': data.quantity(z, 'propagation distance', unit='m'),
    'frequency_thz': data.quantity(f_thz, 'optical frequency', unit='THz'),
    'time_ps': data.quantity(t_ps, 'time in the frame moving with the pulse', unit='ps'),
})
RESULT = {'data': saved['data'], 'soliton_order': order, 'energy_pj': [float(energy[0]), float(energy[-1])],
          'output_width_nm_30db': width_nm, 'output_peak_power_w': float(temporal[-1].max()),
          'wavelength_span_nm_30db': [float(c_nm_thz / band.max()), float(c_nm_thz / band.min())] if band.size else None,
          'checks': {'photon_number_error': float(np.max(np.abs(photons / photons[0] - 1))) if lossless else None,
                     'energy_error': float(np.max(np.abs(energy / energy[0] - 1))) if lossless and not p['raman'] and not p['self_steepening'] else None}}
