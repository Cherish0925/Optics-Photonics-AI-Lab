"""Bit error rate and information rate of a coherent modulation over an additive-noise channel (OptiCommPy).

OptiCommPy maps random bits onto a Gray-coded QAM, PSK or PAM constellation
of order M, normalized to unit mean power. Complex white Gaussian noise sets
Eb/N0 (SNR per symbol = Eb/N0 + 10 log10(log2 M) dB), and an optional random
phase per symbol stands for residual carrier phase noise. Hard decisions
give the bit and symbol error rates; the generalized mutual information
(GMI) is the achievable rate of bit-wise decoding in bits per symbol. The
error rates are compared with OptiCommPy's theoretical bit error rate for
Gray coding, a close approximation at moderate and high SNR. Rates below
about 100 / (bits simulated) are not resolved; increase symbols to reach
them.
"""
import math
import numpy as np
from optic.comm.metrics import fastBERcalc, monteCarloGMI, theoryBER
from optic.comm.modulation import modulateGray
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'modulation': ('qam', 'qam, psk or pam'),
        'order': (16, 'constellation size M, a power of 2'),
        'ebn0_db': ({'start': 0, 'stop': 14, 'points': 15}, 'Eb/N0 values in dB: list or {"start", "stop", "points"}'),
        'symbols': (200000, 'symbols per Eb/N0 value'),
        'phase_noise_rad': (0.0, 'standard deviation of a random phase per symbol'),
        'target_ber': (1e-3, 'bit error rate whose required Eb/N0 is reported'),
        'seed': (1, 'random seed'),
    },
    'results': 'ber.npz/.json with BER, SER, GMI and theoretical BER over Eb/N0; the Eb/N0 that reaches target_ber',
    'checks': 'theory_difference: largest |log10(BER / BER_theory)| where at least 100 errors were counted and no phase noise',
}
p = parameters(PROGRAM, INPUTS)
M, kind = int(p['order']), p['modulation']
if kind not in ('qam', 'psk', 'pam') or M < 2 or M & (M - 1):
    raise ValueError('modulation is qam, psk or pam and order a power of 2')
grid = p['ebn0_db']
ebn0 = np.linspace(grid['start'], grid['stop'], int(grid['points'])) if isinstance(grid, dict) else np.atleast_1d(np.asarray(grid, float))
rng = np.random.default_rng(int(p['seed']))
bits_per_symbol = int(math.log2(M))
count = int(p['symbols'])
rows = []
for value in ebn0:
    bits = rng.integers(0, 2, bits_per_symbol * count)
    symbols = modulateGray(bits, M, kind)
    symbols = symbols / np.sqrt(np.mean(np.abs(symbols) ** 2))
    snr = value + 10 * math.log10(bits_per_symbol)
    noise = np.sqrt(10 ** (-snr / 10) / 2) * (rng.normal(size=count) + 1j * rng.normal(size=count))
    received = symbols * np.exp(1j * float(p['phase_noise_rad']) * rng.normal(size=count)) + noise
    ber, ser, snr_estimate = (float(np.asarray(v).ravel()[0]) for v in fastBERcalc(received, symbols, M, kind))
    gmi = float(np.asarray(monteCarloGMI(received, symbols, M, kind)[0]).ravel()[0])
    rows.append([ber, ser, snr_estimate, gmi, float(theoryBER(M, float(value), kind)), ber * bits_per_symbol * count])
table = np.asarray(rows)
counted = (table[:, 5] >= 100) & (table[:, 0] > 0)
difference = float(np.max(np.abs(np.log10(table[counted, 0] / table[counted, 4])))) if counted.any() and not p['phase_noise_rad'] else None
# Eb/N0 at the target error rate, interpolated in log(BER) between the two points around it.
required = None
target = float(p['target_ber'])
for i in range(len(ebn0) - 1):
    a, b = table[i, 0], table[i + 1, 0]
    if a >= target > b > 0:
        required = float(ebn0[i] + (math.log10(target) - math.log10(a)) / (math.log10(b) - math.log10(a)) * (ebn0[i + 1] - ebn0[i]))
        break
axes = ['ebn0_db']
saved = data.save(OUTPUT_DIR / 'ber', {
    'ber': data.quantity(table[:, 0], 'bit error rate', unit='1', axes=axes, modulation=f'{M}-{kind.upper()}, Gray coded'),
    'ser': data.quantity(table[:, 1], 'symbol error rate', unit='1', axes=axes),
    'snr_estimate_db': data.quantity(table[:, 2], 'SNR estimated from the received symbols', unit='dB', axes=axes),
    'gmi': data.quantity(table[:, 3], 'generalized mutual information', unit='bit/symbol', axes=axes),
    'ber_theory': data.quantity(table[:, 4], 'theoretical bit error rate, Gray coding', unit='1', axes=axes),
    'ebn0_db': data.quantity(ebn0, 'energy per bit over noise spectral density', unit='dB'),
})
RESULT = {'data': saved['data'], 'modulation': f'{M}-{kind.upper()}', 'ber': table[:, 0].tolist(), 'gmi': table[:, 3].tolist(),
          'required_ebn0_db': required, 'target_ber': target, 'checks': {'theory_difference': difference}}
