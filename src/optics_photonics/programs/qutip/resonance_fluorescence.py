"""Resonance fluorescence of a driven two-level emitter: Mollow spectrum and antibunching.

QuTiP solves H = -detuning s+s- + (omega/2)(s+ + s-) in the frame of the laser
(rotating-wave approximation, hbar = 1) with decay gamma, where s- = destroy(2)
takes the excited state basis(2, 1) to the ground state basis(2, 0). Rates are angular,
in rad per unit time. From the steady state it computes the emission
spectrum S(w) of <s+(t) s-(0)> relative to the laser frequency, which splits
into the Mollow triplet with sidebands near +-sqrt(omega^2 + detuning^2) when
omega exceeds gamma, and the second-order correlation g2(tau), which is zero
at tau = 0. The steady excited population is compared with
(omega^2/4) / (detuning^2 + gamma^2/4 + omega^2/2).
"""
import numpy as np
import qutip as qt
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'omega': (10.0, 'Rabi frequency of the drive'),
        'gamma': (1.0, 'emitter energy decay rate'),
        'detuning': (0.0, 'laser minus emitter frequency'),
        'frequencies': ({'start': -20, 'stop': 20, 'points': 801}, 'spectrum frequencies relative to the laser'),
        'delays': ({'stop': 10, 'points': 201}, 'g2 delays from 0'),
    },
    'results': 'fluorescence.npz/.json with the spectrum and g2(tau); steady excited population; sideband positions',
    'checks': 'population_error against the analytic steady state; g2_zero = g2(0)',
}
p = parameters(PROGRAM, INPUTS)
omega, gamma, delta = (float(p[k]) for k in ('omega', 'gamma', 'detuning'))
if gamma <= 0:
    raise ValueError('gamma must be positive')


def axis(value, start=0.0):
    if isinstance(value, dict):
        return np.linspace(float(value.get('start', start)), float(value['stop']), int(value['points']))
    return np.asarray(value, dtype=float)


frequencies, delays = axis(p['frequencies']), axis(p['delays'])
sm = qt.destroy(2)
excited = sm.dag() * sm
H = -delta * excited + 0.5 * omega * (sm + sm.dag())
c_ops = [np.sqrt(gamma) * sm]
steady = qt.steadystate(H, c_ops)
population = float(qt.expect(excited, steady))
analytic = (omega ** 2 / 4) / (delta ** 2 + gamma ** 2 / 4 + omega ** 2 / 2)
spectrum = np.asarray(qt.spectrum(H, frequencies, c_ops, sm.dag(), sm))
g2, _ = qt.coherence_function_g2(H, steady, delays, c_ops, sm)
g2 = np.real(np.asarray(g2))
peaks = [float(frequencies[i]) for i in range(1, len(frequencies) - 1)
         if spectrum[i] > spectrum[i - 1] and spectrum[i] >= spectrum[i + 1] and spectrum[i] > 0.05 * spectrum.max()]
saved = data.save(OUTPUT_DIR / 'fluorescence', {
    'spectrum': data.quantity(spectrum, 'fluorescence spectrum S(w)', unit='arbitrary', axes=['frequency']),
    'frequency': data.quantity(frequencies, 'frequency relative to the laser', unit='rad/(unit time)'),
    'g2': data.quantity(g2, 'second-order correlation g2(tau)', unit='1', axes=['delay']),
    'delay': data.quantity(delays, 'delay', unit='unit time'),
})
RESULT = {'data': saved['data'], 'excited_population': population, 'analytic_population': analytic, 'spectrum_peaks': peaks,
          'generalized_rabi': float(np.hypot(omega, delta)),
          'checks': {'population_error': abs(population - analytic), 'g2_zero': float(g2[0])}}
