"""Squeezed, displaced and lossy single-mode Gaussian states of light (Strawberry Fields).

Strawberry Fields prepares a mode by squeezing (parameter r at angle phi),
displacement (complex amplitude alpha) and a loss channel of transmission
eta, then reads the Gaussian state: quadrature means and covariance
(hbar = 2, so vacuum has unit variance), mean photon number and the
photon-number distribution up to cutoff. Squeezing is reported in dB
relative to vacuum along the squeezed and the anti-squeezed quadrature,
with Mandel's Q and the second-order correlation g2(0) from the exact
mean and variance of the photon number. For the squeezed vacuum these are compared with the
analytic values: variances eta e^(-+2r) + 1 - eta, mean photon number
eta sinh^2 r, g2(0) = 3 + 1/sinh^2 r (unchanged by loss) and, without
loss, P(2n) = tanh(r)^(2n) (2n)! / (4^n n!^2 cosh r).
"""
import math
import numpy as np
import strawberryfields as sf
from strawberryfields import ops
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'squeezing': (0.8, 'squeezing parameter r'),
        'angle': (0.0, 'squeezing angle phi in radians; 0 squeezes the x quadrature'),
        'displacement': ([0.0, 0.0], 'coherent amplitude alpha as [re, im]'),
        'transmission': (0.9, 'loss channel transmission eta'),
        'cutoff': (40, 'largest photon number of the distribution'),
    },
    'results': 'state.npz/.json with the photon-number distribution; covariance, means, squeezing in dB, mean photon number, Mandel Q, g2(0)',
    'checks': 'analytic_difference: largest difference from the analytic squeezed vacuum (without displacement)',
}
p = parameters(PROGRAM, INPUTS)
r, phi, eta, cutoff = float(p['squeezing']), float(p['angle']), float(p['transmission']), int(p['cutoff'])
alpha = complex(*p['displacement'])
if not 0 <= eta <= 1 or r < 0:
    raise ValueError('transmission lies in [0, 1] and squeezing is nonnegative')
program = sf.Program(1)
with program.context as q:
    ops.Sgate(r, phi) | q[0]
    if alpha:
        ops.Dgate(abs(alpha), math.atan2(alpha.imag, alpha.real)) | q[0]
    ops.LossChannel(eta) | q[0]
state = sf.Engine('gaussian').run(program).state
means, covariance = state.reduced_gaussian([0])
vacuum = sf.hbar / 2
eigen = np.linalg.eigvalsh(covariance / vacuum)
mean_photons, variance = (float(v) for v in state.mean_photon(0))  # exact moments of the Gaussian state
P = np.array([float(state.fock_prob([n], cutoff=cutoff + 1)) for n in range(cutoff + 1)])
g2 = (variance + mean_photons ** 2 - mean_photons) / mean_photons ** 2 if mean_photons > 0 else None
mandel = variance / mean_photons - 1 if mean_photons > 0 else None
difference = None
if not alpha and r > 0:
    expected = [eta * math.exp(-2 * r) + 1 - eta, eta * math.exp(2 * r) + 1 - eta]
    gaps = [abs(eigen[0] - expected[0]), abs(eigen[1] - expected[1]), abs(mean_photons - eta * math.sinh(r) ** 2)]
    if g2 is not None:
        gaps.append(abs(g2 - (3 + 1 / math.sinh(r) ** 2)))
    if eta == 1:
        pure = [math.tanh(r) ** (2 * k) * math.factorial(2 * k) / (4 ** k * math.factorial(k) ** 2 * math.cosh(r)) for k in range(cutoff // 2 + 1)]
        gaps.append(max(abs(P[2 * k] - value) for k, value in enumerate(pure)))
    difference = float(max(gaps))
saved = data.save(OUTPUT_DIR / 'state', {
    'photon_number_probability': data.quantity(P, 'probability of n photons', unit='1', axes=[{'name': 'n', 'start': 0, 'step': 1}],
                                               truncated_at=cutoff, missing_probability=float(1 - P.sum())),
    'covariance': data.quantity(covariance, 'quadrature covariance [x, p]', unit='hbar/2 = 1 for vacuum' if sf.hbar == 2 else 'hbar',
                                hbar=sf.hbar),
    'means': data.quantity(np.asarray(means), 'quadrature means [x, p]', unit='1', hbar=sf.hbar),
})
RESULT = {'data': saved['data'], 'squeezing_db': float(-10 * math.log10(eigen[0])), 'anti_squeezing_db': float(10 * math.log10(eigen[1])),
          'mean_photons': mean_photons, 'g2': g2, 'mandel_q': mandel, 'means': [float(v) for v in means],
          'probabilities': [float(v) for v in P[:8]], 'missing_probability': float(1 - P.sum()),
          'checks': {'analytic_difference': difference}}
