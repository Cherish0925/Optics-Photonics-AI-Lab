"""Least-squares fit of a Gaussian profile.

SciPy fits A exp(-(x - center)^2 / (2 sigma^2)) without background. x_unit
names the unit of x; the result is a numerical fit, not an instrument
calibration.
"""
import numpy as np
from scipy.optimize import curve_fit
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'x': ([-2, -1, 0, 1, 2], 'coordinates'),
        'y': ([0.1353352832, 0.6065306597, 1, 0.6065306597, 0.1353352832], 'measured values at x'),
        'x_unit': ('mm', 'unit of x'),
    },
    'domains': ['foundation'],
    'results': 'amplitude, center, sigma, parameter covariance; fit.csv with observed and fitted values',
    'checks': 'residual_rms: root mean square of observed minus fitted',
}
p = parameters(PROGRAM, INPUTS)
x, y = np.asarray(p['x'], dtype=float), np.asarray(p['y'], dtype=float)
if x.shape != y.shape or x.size < 4:
    raise ValueError('x and y need the same length, at least 4 points')


def gaussian(x, amplitude, center, sigma):
    return amplitude * np.exp(-0.5 * ((x - center) / sigma) ** 2)


pars, cov = curve_fit(gaussian, x, y, p0=[y.max(), x[y.argmax()], np.std(x) / 2],
                      bounds=([-np.inf, -np.inf, np.finfo(float).eps], [np.inf, np.inf, np.inf]))
fitted = gaussian(x, *pars)
np.savetxt(OUTPUT_DIR / 'fit.csv', np.column_stack([x, y, fitted]), delimiter=',', header='x,observed,fitted', comments='')
RESULT = {'amplitude': float(pars[0]), 'center': float(pars[1]), 'sigma': float(pars[2]), 'x_unit': p['x_unit'],
          'parameter_covariance': cov.tolist(), 'data': 'fit.csv', 'checks': {'residual_rms': float(np.sqrt(np.mean((y - fitted) ** 2)))}}
