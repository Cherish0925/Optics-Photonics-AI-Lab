"""Phase hologram that splits a beam into an array of focal spots (slmsuite, weighted Gerchberg-Saxton).

A phase-only spatial light modulator of N x N pixels under uniform
illumination stands before a lens; the field in the focal plane is the
Fourier transform of exp(i phi). The program finds the phase phi that sends
the light into rows x columns spots with the given relative powers.
Gerchberg-Saxton iterations go back and forth between the two planes,
keeping the computed phase in each and imposing the uniform amplitude on
the modulator and the target amplitudes in the focal plane. The weighted
variants rescale the targets by the amplitudes reached (Di Leonardo et al.,
Opt. Express 15, 1913 (2007)) and fix the focal-plane phase after some
iterations (Kim et al., Opt. Lett. 44, 3178 (2019)): the spots become
equal at a small cost in efficiency. Efficiency is the share of the power
in the spots; uniformity is 1 - (max - min) / (max + min) of the spot
powers over their targets. A phase-only element cannot reach every target:
three spots in a line with unequal outer powers need light in further
orders, and the iteration, which keeps the efficiency, stops short of them;
the uniformity says how far. With levels the phase is rounded to that many
steps, as a modulator displays it. One focal-plane pixel is
lambda f / (N pixel pitch); the array is placed off the axis, away from
the undiffracted light of a real modulator. The spot powers are computed
again from the phase by a separate Fourier transform. With hardware,
slmsuite's FourierSLM and feedback holograms take camera images in place
of the computed focal plane.
"""
import logging
import warnings
import numpy as np
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'pixels': (512, 'pixels per side of the modulator and of the computed focal plane'),
        'rows': (5, 'rows of spots'),
        'columns': (6, 'columns of spots'),
        'pitch': (16, 'distance between neighbouring spots in focal-plane pixels'),
        'offset': ([48, 32], 'position of the centre of the array from the optical axis, [x, y] in focal-plane pixels'),
        'weights': ([], 'relative power of each spot, rows x columns; empty for equal spots'),
        'method': ('WGS-Kim', 'GS, WGS-Leonardo or WGS-Kim'),
        'iterations': (30, 'iterations of the method'),
        'start_iterations': (20, 'Gerchberg-Saxton iterations before a weighted method'),
        'levels': (256, 'phase levels of the modulator; 0 keeps the phase continuous'),
        'seed': (1, 'seed of the random starting phase'),
    },
    'domains': ['wave', 'lab'],
    'results': 'hologram.npz/.json with the phase, the focal-plane intensity and the power of each spot; efficiency and uniformity '
               'after the Gerchberg-Saxton start, after the method, and with the phase levels',
    'checks': 'transform_difference: largest relative difference of the spot powers from a separate Fourier transform of the phase; '
              'power_error: total focal-plane power minus 1',
}
p = parameters(PROGRAM, INPUTS)
size, rows, columns, pitch = (int(p[key]) for key in ('pixels', 'rows', 'columns', 'pitch'))
methods = ('GS', 'WGS-Leonardo', 'WGS-Kim')
x = size // 2 + int(p['offset'][0]) + (np.arange(columns) - (columns - 1) / 2) * pitch
y = size // 2 + int(p['offset'][1]) + (np.arange(rows) - (rows - 1) / 2) * pitch
if p['method'] not in methods or min(rows, columns, pitch, int(p['iterations'])) < 1 or size < 16 or int(p['levels']) == 1 or \
        x.min() < 1 or y.min() < 1 or x.max() > size - 2 or y.max() > size - 2 or np.any(x % 1) or np.any(y % 1):
    raise ValueError('method is ' + ', '.join(methods) + '; rows, columns, pitch and iterations are at least 1; levels is 0 or at least 2; '
                     'the array lies inside the focal plane on whole pixels (an even pitch for an even count)')
targets = np.ones((rows, columns)) if not p['weights'] else np.asarray(p['weights'], dtype=float)
if targets.shape != (rows, columns) or np.any(targets <= 0):
    raise ValueError('weights holds one positive number per spot, as rows of columns')
targets = targets / targets.sum()
X, Y = np.meshgrid(x.astype(int), y.astype(int))

logging.disable(logging.INFO)              # slmsuite announces each object it creates
with warnings.catch_warnings():
    warnings.simplefilter('ignore')        # and the absence of a GPU
    from slmsuite.holography.algorithms import SpotHologram
    np.random.seed(int(p['seed']))
    hologram = SpotHologram((size, size), np.vstack([X.ravel(), Y.ravel()]).astype(float), basis='knm', spot_amp=np.sqrt(targets.ravel()))


def spots(phase):
    """Power of each spot and the whole focal-plane intensity, by a Fourier transform of exp(i phase); total power 1."""
    intensity = np.abs(np.fft.fftshift(np.fft.fft2(np.fft.fftshift(np.exp(1j * phase)), norm='ortho'))) ** 2 / phase.size
    return intensity[Y, X], intensity


def quality(power):
    ratio = power / targets
    return {'efficiency': float(power.sum()), 'uniformity': float(1 - (ratio.max() - ratio.min()) / (ratio.max() + ratio.min()))}


stages = {}
with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    if p['method'] != 'GS' and int(p['start_iterations']) > 0:
        hologram.optimize('GS', maxiter=int(p['start_iterations']), verbose=False)
        stages['start'] = quality(spots(np.asarray(hologram.get_phase(), dtype=float))[0])
    hologram.optimize(p['method'], maxiter=int(p['iterations']), verbose=False)
    library = np.abs(np.asarray(hologram.get_farfield())[Y, X]) ** 2
phase = np.mod(np.asarray(hologram.get_phase(), dtype=float), 2 * np.pi)
power, intensity = spots(phase)
stages['method'] = quality(power)
levels = int(p['levels'])
if levels:
    phase = np.mod(np.round(phase / (2 * np.pi / levels)), levels) * (2 * np.pi / levels)
    shown, intensity = spots(phase)
    stages['levels'] = quality(shown)
else:
    shown = power

saved = data.save(OUTPUT_DIR / 'hologram', {
    'phase': data.quantity(phase.astype(np.float32), 'phase displayed on the modulator', unit='rad', axes=['row', 'column']),
    'intensity': data.quantity(intensity.astype(np.float32), 'focal-plane intensity for unit incident power', unit='1',
                               axes=['focal_y', 'focal_x']),
    'spot_power': data.quantity(shown, 'power of each spot for unit incident power', unit='1', axes=['spot_row', 'spot_column']),
    'spot_target': data.quantity(targets, 'requested share of the spot power', unit='1', axes=['spot_row', 'spot_column']),
    'row': data.quantity(np.arange(size), 'modulator pixel row', unit='1'),
    'column': data.quantity(np.arange(size), 'modulator pixel column', unit='1'),
    'focal_y': data.quantity(np.arange(size) - size // 2, 'focal-plane position from the axis', unit='pixel',
                             pixel='wavelength x focal length / (pixels x pixel pitch)'),
    'focal_x': data.quantity(np.arange(size) - size // 2, 'focal-plane position from the axis', unit='pixel'),
    'spot_row': data.quantity(y - size // 2, 'spot position from the axis along y', unit='pixel'),
    'spot_column': data.quantity(x - size // 2, 'spot position from the axis along x', unit='pixel'),
})
RESULT = {
    'spots': rows * columns, **stages['levels' if levels else 'method'], 'stages': stages, 'method': p['method'], 'data': saved['data'],
    'checks': {'transform_difference': float(np.max(np.abs(power - library) / library)), 'power_error': float(intensity.sum() - 1)},
}
