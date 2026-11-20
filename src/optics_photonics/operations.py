"""Compatibility entry points for 0.7 clients; implementations live in programs."""
import math
from . import programs

_NAMES = {'optiland': 'trace', 'gdsfactory': 'waveguide', 'py-pol': 'polarization', 'tmm': 'spectrum',
          'miepython': 'sphere', 'raytracing': 'abcd', 'lightpipes': 'gaussian', 'poppy': 'psf',
          'hcipy': 'psf', 'qutip': 'rabi', 'sympy': 'abcd', 'scipy': 'fit_gaussian',
          'scikitimage': 'registration', 'klayout': 'layout', 'grcwa': 'film', 'legume': 'bands'}
EXAMPLES = {tool: (name, programs.inputs(programs.catalog()[tool][name])) for tool, name in _NAMES.items()}
NOTES = {tool: programs.catalog()[tool][name]['about'] for tool, name in _NAMES.items()}


def calculate(tool, action, p, output):
    return programs.run(tool, action, p, output)


def complex_number(value):
    return complex(*value) if isinstance(value, list) else complex(value)


def positive(value, name):
    if not math.isfinite(float(value)) or value <= 0:
        raise ValueError(name + ' must be positive and finite')
    return value


def count(value, name):
    if type(value) is not int or value < 2:
        raise ValueError(name + ' must be an integer >= 2')
    return value
