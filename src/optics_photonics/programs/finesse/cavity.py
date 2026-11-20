"""Transmission, reflection and stored power of a Fabry-Perot cavity over laser frequency (Finesse).

Finesse solves the plane-wave fields of a laser, an input mirror, a space
of length_m and an end mirror; each mirror has power reflectivity R,
transmissivity T and loss 1 - R - T, with real reflection and imaginary
transmission amplitudes. The laser frequency is swept around a resonance
over span_fsr free spectral ranges. Powers are fractions of the input
power: transmitted, reflected, and circulating on the end mirror. The
free spectral range c / 2L, the linewidth (full width at half maximum),
the finesse FSR / FWHM, the power buildup and the quality factor
nu / FWHM are reported and compared with the Airy function of the same
mirrors.
"""
import math
import numpy as np
import finesse
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'input_mirror': ({'R': 0.99, 'T': 0.01}, 'R and T of the input mirror; loss is 1 - R - T'),
        'end_mirror': ({'R': 0.99, 'T': 0.01}, 'R and T of the end mirror'),
        'length_m': (1.0, 'mirror spacing'),
        'wavelength_nm': (1064.0, 'laser wavelength, for the quality factor'),
        'span_fsr': (1.5, 'half-width of the frequency sweep in free spectral ranges'),
        'points': (4001, 'frequencies in the sweep'),
    },
    'domains': ['laser'],
    'results': 'cavity.npz/.json with transmitted, reflected and circulating power over frequency offset; FSR, linewidth, finesse, buildup, Q',
    'checks': 'airy_difference: largest difference from the Airy functions; finesse_error: relative difference of the measured finesse',
}
p = parameters(PROGRAM, INPUTS)
m1, m2, L = p['input_mirror'], p['end_mirror'], float(p['length_m'])
for mirror in (m1, m2):
    if not 0 <= mirror['R'] <= 1 or not 0 <= mirror['T'] <= 1 or mirror['R'] + mirror['T'] > 1:
        raise ValueError('Each mirror needs 0 <= R, T and R + T <= 1')
c = 299792458.0
fsr = c / (2 * L)


def sweep(half_width, points):
    model = finesse.Model()
    model.parse(f"""
l L0 P=1
s s0 L0.p1 ITM.p1
m ITM R={m1['R']} T={m1['T']}
s CAV ITM.p2 ETM.p1 L={L}
m ETM R={m2['R']} T={m2['T']}
pd trans ETM.p2.o
pd refl ITM.p1.o
pd circ ETM.p1.i
xaxis(L0.f, lin, {-half_width}, {half_width}, {points - 1})
""")
    out = model.run()
    return (np.asarray(out.x[0], dtype=float), *(np.asarray(out[name], dtype=float) for name in ('trans', 'refl', 'circ')))


offset, T, R, circulating = sweep(p['span_fsr'] * fsr, int(p['points']))

r1, r2, t1, t2 = math.sqrt(m1['R']), math.sqrt(m2['R']), math.sqrt(m1['T']), math.sqrt(m2['T'])
loop = r1 * r2 * np.exp(-2j * math.pi * offset * 2 * L / c)
airy = {'trans': t1 ** 2 * t2 ** 2 / np.abs(1 - loop) ** 2, 'circ': t1 ** 2 / np.abs(1 - loop) ** 2,
        'refl': np.abs(r1 - t1 ** 2 * r2 * np.exp(-2j * math.pi * offset * 2 * L / c) / (1 - loop)) ** 2}
difference = max(float(np.max(np.abs(T - airy['trans']))), float(np.max(np.abs(R - airy['refl']))),
                 float(np.max(np.abs(circulating - airy['circ'])) / np.max(airy['circ'])))
g = r1 * r2  # round-trip amplitude; the exact finesse of the Airy peak, pi sqrt(g) / (1 - g) when g is near 1
expected = math.pi / (2 * math.asin(min(1.0, (1 - g) / (2 * math.sqrt(g))))) if g > 0 else 0.0
# Linewidth from the half-maximum crossings of a second, finer sweep across the resonance at zero offset;
# the expected width only sets that sweep's window.
near, peak_curve, _, _ = sweep(min(3 * fsr / max(expected, 1e-9), fsr / 2), 2001)
half = peak_curve.max() / 2
inside = np.where(peak_curve > half)[0]
fwhm = None
if len(inside) and 0 < inside[0] and inside[-1] < len(near) - 1:
    a, b = inside[0], inside[-1]
    left = near[a - 1] + (half - peak_curve[a - 1]) * (near[a] - near[a - 1]) / (peak_curve[a] - peak_curve[a - 1])
    right = near[b] + (half - peak_curve[b]) * (near[b + 1] - near[b]) / (peak_curve[b + 1] - peak_curve[b])
    fwhm = float(right - left)
frequency = c / (float(p['wavelength_nm']) * 1e-9)
axes = ['offset_hz']
saved = data.save(OUTPUT_DIR / 'cavity', {
    'transmitted': data.quantity(T, 'transmitted power over input power', unit='1', axes=axes, length_m=L),
    'reflected': data.quantity(R, 'reflected power over input power', unit='1', axes=axes),
    'circulating': data.quantity(circulating, 'circulating power on the end mirror over input power', unit='1', axes=axes),
    'offset_hz': data.quantity(offset, 'laser frequency offset from resonance', unit='Hz'),
})
RESULT = {'data': saved['data'], 'fsr_hz': fsr, 'fwhm_hz': fwhm, 'finesse': fsr / fwhm if fwhm else None, 'finesse_expected': expected,
          'buildup': float(circulating.max()), 'transmission_peak': float(T.max()), 'reflection_dip': float(R.min()),
          'quality_factor': frequency / fwhm if fwhm else None,
          'checks': {'airy_difference': difference, 'finesse_error': abs(fsr / fwhm / expected - 1) if fwhm else None}}
