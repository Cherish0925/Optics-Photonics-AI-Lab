"""Scan a motor through a peak, fit it and scan again around the fitted centre (Bluesky plan on simulated ophyd devices).

Bluesky's RunEngine carries out a plan, here scan: at each position move
the motor, trigger and read the detector. It emits start, descriptor,
event and stop documents that hold every reading with its time, and the
program collects the events. The devices are ophyd objects: the simulated
ones (ophyd.sim) stand for a motor and a detector whose signal is a
Gaussian of the motor position with noise, as when a slit, a mirror angle
or a monochromator is scanned through a beam. A Gaussian is fitted to the
scan; a second scan then covers three fitted widths on each side of the
fitted centre, as an alignment procedure does. On an instrument the same
plan runs on devices declared with ophyd over EPICS or another control
system: replace the two simulated devices.
"""
import numpy as np
from scipy.optimize import curve_fit
from bluesky import RunEngine
from bluesky.plans import scan
from ophyd.sim import SynAxis, SynGauss
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'centre': (0.3, 'position of the peak of the simulated detector'),
        'width': (0.8, 'standard deviation of the peak, in position units'),
        'peak': (1000.0, 'signal at the peak'),
        'noise': (10.0, 'amplitude of the uniform noise added to the signal'),
        'start': (-3.0, 'first position of the first scan'),
        'stop': (3.0, 'last position of the first scan'),
        'points': (31, 'positions of each scan'),
        'refine': (True, 'scan again around the fitted centre'),
        'seed': (1, 'seed of the noise'),
    },
    'domains': ['lab'],
    'results': 'scan.npz/.json with positions and signal of each scan; per scan the fitted centre, width and amplitude with their '
               'standard errors, the run identifier and the number of documents',
    'checks': 'centre_difference and width_difference: last fitted centre and width minus those of the simulated detector',
}
p = parameters(PROGRAM, INPUTS)
points = int(p['points'])
if points < 5 or float(p['width']) <= 0 or float(p['peak']) <= 0 or float(p['start']) == float(p['stop']) or float(p['noise']) < 0:
    raise ValueError('points >= 5, width and peak are positive, noise is not negative, and start differs from stop')

motor = SynAxis(name='motor')
detector = SynGauss('detector', motor, 'motor', center=float(p['centre']), Imax=float(p['peak']), sigma=float(p['width']),
                    noise='uniform' if p['noise'] else None, noise_multiplier=float(p['noise']),
                    random_state=np.random.RandomState(int(p['seed'])))
engine = RunEngine({})


def gaussian(x, amplitude, centre, width, offset):
    return amplitude * np.exp(-(x - centre) ** 2 / (2 * width ** 2)) + offset


def measure(first, last):
    """One scan: positions, signal, fitted parameters with standard errors, the run identifier and the document count."""
    events, count = [], [0]

    def collect(name, document):
        count[0] += 1
        if name == 'event':
            events.append((document['data']['motor'], document['data']['detector']))

    run, = engine(scan([detector], motor, first, last, points), collect)
    position, signal = (np.asarray(column, dtype=float) for column in zip(*events))
    guess = [signal.max() - signal.min(), position[signal.argmax()], abs(last - first) / 6, signal.min()]
    values, covariance = curve_fit(gaussian, position, signal, p0=guess)
    errors = np.sqrt(np.diag(covariance))
    fit = {name: float(value) for name, value in zip(('amplitude', 'centre', 'width', 'offset'), values)}
    fit['width'] = abs(fit['width'])
    return position, signal, {**fit, 'centre_error': float(errors[1]), 'width_error': float(errors[2]), 'run': run, 'documents': count[0],
                              'range': [float(first), float(last)]}


passes = [measure(float(p['start']), float(p['stop']))]
if p['refine']:
    fit = passes[0][2]
    passes.append(measure(fit['centre'] - 3 * fit['width'], fit['centre'] + 3 * fit['width']))
saved = data.save(OUTPUT_DIR / 'scan', {
    'position': data.quantity(np.asarray([position for position, _, _ in passes]), 'motor position at each step', unit='1', axes=['scan', 'step']),
    'signal': data.quantity(np.asarray([signal for _, signal, _ in passes]), 'detector signal at each step', unit='1', axes=['scan', 'step']),
    'scan': data.quantity(np.arange(len(passes)), 'scan number', unit='1'),
    'step': data.quantity(np.arange(points), 'step of the scan', unit='1'),
})
last = passes[-1][2]
RESULT = {
    'scans': [fit for _, _, fit in passes], 'data': saved['data'],
    'checks': {'centre_difference': last['centre'] - float(p['centre']), 'width_difference': last['width'] - float(p['width'])},
}
