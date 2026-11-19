"""Rabi oscillation of a closed two-level system.

QuTiP evolves H = (omega/2) sigma_x with hbar = 1 from basis(2, 0) and
reports the population of basis(2, 1), which follows sin^2(omega t / 2).
omega in rad/s, times in seconds. Open systems use the jaynes_cummings and
resonance_fluorescence programs or a native program.
"""
import numpy as np
import qutip as qt
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'omega_rad_s': (1, 'Rabi frequency in rad/s'),
        'times_s': ([0, 3.141592653589793, 6.283185307179586], 'times in seconds, starting at zero and increasing'),
    },
    'results': 'population.csv; first, last and largest population of the upper state',
    'checks': 'analytic_error: largest difference from sin^2(omega t / 2)',
}
p = parameters(PROGRAM, INPUTS)
times = np.asarray(p['times_s'], dtype=float)
if len(times) < 2 or np.any(np.diff(times) <= 0) or times[0] != 0:
    raise ValueError('times_s must start at zero and increase strictly')
excited = qt.basis(2, 1).proj()
evolution = qt.sesolve(0.5 * p['omega_rad_s'] * qt.sigmax(), qt.basis(2, 0), times, e_ops=[excited], options={'atol': 1e-10, 'rtol': 1e-9})
values = np.asarray(evolution.expect[0])
np.savetxt(OUTPUT_DIR / 'population.csv', np.column_stack([times, values]), delimiter=',', header='time_s,population_1', comments='')
RESULT = {'samples': len(times), 'first': float(values[0]), 'last': float(values[-1]), 'maximum': float(values.max()), 'data': 'population.csv',
          'checks': {'analytic_error': float(np.max(np.abs(values - np.sin(p['omega_rad_s'] * times / 2) ** 2)))}}
