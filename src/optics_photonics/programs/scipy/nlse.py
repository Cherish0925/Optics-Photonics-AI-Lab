"""Pulse propagation in a fiber by the split-step Fourier method (nonlinear Schrodinger equation).

The envelope A(z, T) in sqrt(W), T in ps in the frame moving with the pulse,
obeys dA/dz = -(alpha/2) A - i (beta2/2) d2A/dT2 + (beta3/6) d3A/dT3
+ i gamma |A|^2 A (Agrawal's convention, exp(i(beta0 z - w0 t)) carrier).
Each step applies half the linear operator in the frequency domain, the
nonlinear phase, and the other half. The soliton order N = sqrt(gamma P0 T0^2 /
|beta2|), the dispersion length T0^2/|beta2| and the nonlinear length
1/(gamma P0) are reported. Checks compare with analytic limits when they
apply: a Gaussian without nonlinearity broadens as T0 sqrt(1 + (z/LD)^2), and
a fundamental soliton (N = 1, beta2 < 0, no loss or beta3) keeps its shape.
"""
import numpy as np
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'shape': ('sech', 'sech or gaussian: |A|^2 = P0 sech^2(T/T0) or P0 exp(-T^2/T0^2)'),
        'peak_power_W': (0.5, 'peak power P0 in W'),
        'width_ps': (1.0, 'T0 in ps (half width at 1/e intensity for a Gaussian; FWHM = 1.763 T0 for sech)'),
        'chirp': (0.0, 'initial chirp parameter C: A(0, T) multiplied by exp(-i C T^2 / (2 T0^2))'),
        'beta2_ps2_per_km': (-20.0, 'group-velocity dispersion beta2 in ps^2/km'),
        'beta3_ps3_per_km': (0.0, 'third-order dispersion beta3 in ps^3/km'),
        'gamma_per_W_km': (40.0, 'nonlinear coefficient gamma in 1/(W km)'),
        'alpha_dB_per_km': (0.0, 'loss in dB/km'),
        'length_km': (0.5, 'fiber length in km'),
        'steps': (2000, 'split steps along the fiber'),
        'window_ps': (40.0, 'time window in ps'),
        'points': (2048, 'time samples'),
        'saved_positions': (21, 'positions along the fiber at which the field is saved'),
    },
    'domains': ['fiber'],
    'results': 'pulse.npz/.json with power over position and time, and spectrum over position and frequency; widths; characteristic lengths',
    'checks': 'energy_error for a lossless fiber; dispersive_width_error or soliton_shape_error when the analytic limit applies',
}
p = parameters(PROGRAM, INPUTS)
P0, T0, C = float(p['peak_power_W']), float(p['width_ps']), float(p['chirp'])
beta2, beta3, gamma = float(p['beta2_ps2_per_km']), float(p['beta3_ps3_per_km']), float(p['gamma_per_W_km'])
alpha = float(p['alpha_dB_per_km']) * np.log(10) / 10
length, steps, points = float(p['length_km']), int(p['steps']), int(p['points'])
if P0 <= 0 or T0 <= 0 or length <= 0 or steps < 1 or points < 16 or p['shape'] not in ('sech', 'gaussian'):
    raise ValueError('peak_power_W, width_ps and length_km are positive; steps >= 1; points >= 16; shape is sech or gaussian')
T = (np.arange(points) - points // 2) * float(p['window_ps']) / points
dT = T[1] - T[0]
envelope = 1 / np.cosh(T / T0) if p['shape'] == 'sech' else np.exp(-T ** 2 / (2 * T0 ** 2))
A = np.sqrt(P0) * envelope * np.exp(-0.5j * C * (T / T0) ** 2)
w = 2 * np.pi * np.fft.fftfreq(points, dT)                         # angular frequency, rad/ps
dz = length / steps
half = np.exp((0.5j * beta2 * w ** 2 - 1j * beta3 / 6 * w ** 3 - alpha / 2) * dz / 2)
saved_at = np.unique(np.linspace(0, steps, int(p['saved_positions'])).round().astype(int))
powers, spectra, positions = [], [], []


def record(field, step):
    positions.append(step * dz)
    powers.append(np.abs(field) ** 2)
    # The exp(-i omega t) convention associates positive frequency with exp(-i omega T).
    spectra.append(np.abs(np.fft.fftshift(np.fft.ifft(field)) * points) ** 2 * dT ** 2)


record(A, 0)
energy0 = np.sum(np.abs(A) ** 2) * dT
for step in range(1, steps + 1):
    A = np.fft.ifft(half * np.fft.fft(A))
    A = A * np.exp(1j * gamma * np.abs(A) ** 2 * dz)
    A = np.fft.ifft(half * np.fft.fft(A))
    if step in saved_at:
        record(A, step)


def rms_width(power):
    weight = power / power.sum()
    centre = np.sum(weight * T)
    return float(np.sqrt(np.sum(weight * (T - centre) ** 2)))


def fwhm(power):
    above = np.where(power >= power.max() / 2)[0]
    return float((above[-1] - above[0]) * dT)


LD = T0 ** 2 / abs(beta2) if beta2 else None
LNL = 1 / (gamma * P0) if gamma else None
order = float(np.sqrt(gamma * P0 * T0 ** 2 / abs(beta2))) if beta2 else None
energy = np.sum(np.abs(A) ** 2) * dT
checks = {'energy_error': float(abs(energy / energy0 - 1)) if alpha == 0 else None, 'dispersive_width_error': None, 'soliton_shape_error': None}
if p['shape'] == 'gaussian' and gamma == 0 and beta3 == 0 and C == 0 and beta2:
    analytic = rms_width(powers[0]) * np.sqrt(1 + (length / LD) ** 2)
    checks['dispersive_width_error'] = float(abs(rms_width(powers[-1]) / analytic - 1))
if p['shape'] == 'sech' and order and abs(order - 1) < 1e-3 and beta2 < 0 and alpha == 0 and beta3 == 0 and C == 0:
    checks['soliton_shape_error'] = float(np.max(np.abs(powers[-1] - powers[0])) / P0)
frequency = np.fft.fftshift(w) / (2 * np.pi)
saved = data.save(OUTPUT_DIR / 'pulse', {
    'power': data.quantity(np.asarray(powers), 'instantaneous power |A|^2', unit='W', axes=['position_km', 'time_ps']),
    'spectrum': data.quantity(np.asarray(spectra), 'energy spectral density |FT A|^2', unit='W ps^2', axes=['position_km', 'frequency_THz'],
                              time_dependence='exp(-i omega t)', convention='frequency offset from the carrier'),
    'position_km': data.quantity(np.asarray(positions), 'position along the fiber', unit='km'),
    'time_ps': data.quantity(T, 'time in the frame moving with the group velocity', unit='ps'),
    'frequency_THz': data.quantity(frequency, 'frequency offset from the carrier', unit='THz'),
})
RESULT = {'data': saved['data'], 'soliton_order': order, 'dispersion_length_km': LD, 'nonlinear_length_km': LNL,
          'fwhm_in_ps': fwhm(powers[0]), 'fwhm_out_ps': fwhm(powers[-1]), 'rms_width_out_ps': rms_width(powers[-1]),
          'peak_power_out_W': float(powers[-1].max()), 'energy_pJ': float(energy), 'checks': checks}
