"""Two-level emitter coupled to a cavity mode with losses (Jaynes-Cummings).

QuTiP solves the Lindblad master equation for H = delta a+a + g (a+ s- + a s+)
in the frame of the emitter (rotating-wave approximation, hbar = 1), with
cavity energy decay kappa and emitter decay gamma. Frequencies and rates are
angular, in rad per unit time; times share that unit. The emitter starts
excited and the cavity holds photons Fock photons. In the one-excitation
manifold the non-Hermitian matrix [[delta - i kappa/2, g], [g, -i gamma/2]]
gives the dressed states; their frequency difference is the vacuum Rabi
splitting, real only above the exceptional point g = |kappa - gamma| / 4.
"""
import numpy as np
import qutip as qt
from scipy.linalg import expm
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'g': (1.0, 'coupling rate in rad per unit time'),
        'kappa': (0.2, 'cavity energy decay rate'),
        'gamma': (0.05, 'emitter energy decay rate into other modes'),
        'detuning': (0.0, 'cavity minus emitter frequency'),
        'photons': (0, 'initial photons in the cavity (Fock state)'),
        'n_max': (10, 'Fock space cutoff; must exceed photons + 1'),
        'times': ({'stop': 20, 'points': 401}, 'times from 0: {"stop": .., "points": ..} or a list'),
    },
    'results': 'dynamics.npz/.json with emitter population and mean photon number over time; dressed-state frequencies and widths',
    'checks': 'one_excitation_error: largest difference from the analytic one-excitation solution (when photons is 0)',
}
p = parameters(PROGRAM, INPUTS)
g, kappa, gamma, delta = (float(p[k]) for k in ('g', 'kappa', 'gamma', 'detuning'))
photons, n_max = int(p['photons']), int(p['n_max'])
if kappa < 0 or gamma < 0 or photons < 0 or n_max <= photons + 1:
    raise ValueError('kappa and gamma are nonnegative, and n_max exceeds photons + 1')
times = (np.linspace(0, float(p['times']['stop']), int(p['times']['points'])) if isinstance(p['times'], dict)
         else np.asarray(p['times'], dtype=float))
if times[0] != 0 or np.any(np.diff(times) <= 0):
    raise ValueError('times start at 0 and increase')
a = qt.tensor(qt.destroy(n_max), qt.qeye(2))
sm = qt.tensor(qt.qeye(n_max), qt.destroy(2))
H = delta * a.dag() * a + g * (a.dag() * sm + a * sm.dag())
c_ops = [np.sqrt(kappa) * a, np.sqrt(gamma) * sm]
start = qt.tensor(qt.basis(n_max, photons), qt.basis(2, 1))
result = qt.mesolve(H, start, times, c_ops, e_ops=[sm.dag() * sm, a.dag() * a], options={'atol': 1e-10, 'rtol': 1e-8})
excited, mean_photons = (np.asarray(v) for v in result.expect)

effective = np.array([[delta - 0.5j * kappa, g], [g, -0.5j * gamma]])
values = np.linalg.eigvals(effective)
order = np.argsort(values.real)
frequencies, widths = values.real[order], -2 * values.imag[order]
error = None
if photons == 0:
    amplitudes = np.array([expm(-1j * effective * t) @ np.array([0, 1]) for t in times])
    error = float(np.max(np.abs(excited - np.abs(amplitudes[:, 1]) ** 2)))
saved = data.save(OUTPUT_DIR / 'dynamics', {
    'emitter_population': data.quantity(excited, 'excited-state population', unit='1', axes=['time']),
    'photon_number': data.quantity(mean_photons, 'mean cavity photon number', unit='1', axes=['time']),
    'time': data.quantity(times, 'time', unit='1/(unit of g)', convention='rates are angular frequencies'),
})
RESULT = {'data': saved['data'], 'dressed_frequencies': frequencies.tolist(), 'dressed_widths': widths.tolist(),
          'vacuum_rabi_splitting': float(frequencies[1] - frequencies[0]),
          'above_exceptional_point': bool(g > abs(kappa - gamma) / 4), 'final_population': float(excited[-1]),
          'checks': {'one_excitation_error': error}}
