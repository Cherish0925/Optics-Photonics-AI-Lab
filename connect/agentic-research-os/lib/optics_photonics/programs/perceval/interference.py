"""Multi-photon interference in a linear optical interferometer (Perceval).

Perceval's SLOS back end computes the probability of every output photon
pattern for single photons entering the modes of a unitary interferometer:
a beam splitter of reflectivity R (Hong-Ou-Mandel interference for [1, 1]),
an N-mode discrete Fourier transform, a Haar-random unitary, or a given
matrix. Imperfect sources enter through Perceval's noise model:
indistinguishability (mode overlap of the photons), g2 (multi-photon
emission) and transmittance (loss). For perfect photons the probabilities
are compared with permanents of submatrices of the unitary, computed here
by Ryser's formula; for two photons on a beam splitter with partial
indistinguishability M, with T^2 + R^2 - 2 T R M for one photon in each output.
"""
import itertools
import math
import numpy as np
import perceval as pcvl
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'interferometer': ('beam_splitter', 'beam_splitter, fourier, haar or matrix'),
        'input_state': ([1, 1], 'photons in each input mode'),
        'reflectivity': (0.5, 'power reflectivity of the beam splitter'),
        'matrix': (None, 'unitary for interferometer matrix: rows of [re, im] pairs'),
        'seed': (1, 'seed of the Haar-random unitary'),
        'indistinguishability': (1.0, 'mode overlap of the photons'),
        'g2': (0.0, 'second-order correlation of the source at zero delay'),
        'transmittance': (1.0, 'probability that a photon survives the interferometer'),
    },
    'results': 'probabilities.json and outputs.npz/.json with the probability of each output pattern; coincidence and bunching probabilities',
    'checks': 'permanent_difference for perfect photons; hom_difference for two photons on a beam splitter',
}
p = parameters(PROGRAM, INPUTS)
state = [int(n) for n in p['input_state']]
modes = len(state)
kind = p['interferometer']
if kind == 'beam_splitter':
    if modes != 2:
        raise ValueError('A beam splitter has two input modes')
    R = float(p['reflectivity'])
    circuit = pcvl.BS(theta=pcvl.BS.r_to_theta(R))
    U = np.asarray(circuit.compute_unitary(), dtype=complex)
elif kind in ('fourier', 'haar', 'matrix'):
    if kind == 'fourier':
        U = np.array([[np.exp(2j * np.pi * j * k / modes) for k in range(modes)] for j in range(modes)]) / np.sqrt(modes)
    elif kind == 'haar':
        z = np.random.default_rng(int(p['seed'])).normal(size=(modes, modes)) + 1j * np.random.default_rng(int(p['seed']) + 1).normal(size=(modes, modes))
        q, r = np.linalg.qr(z)
        U = q * (np.diag(r) / np.abs(np.diag(r)))
    else:
        U = np.array([[complex(*entry) for entry in row] for row in p['matrix']])
        if U.shape != (modes, modes) or not np.allclose(U.conj().T @ U, np.eye(modes), atol=1e-9):
            raise ValueError('matrix is a unitary with one row per input mode')
    circuit = pcvl.Unitary(pcvl.Matrix(U))
else:
    raise ValueError('interferometer is beam_splitter, fourier, haar or matrix')
noise = pcvl.NoiseModel(indistinguishability=float(p['indistinguishability']), g2=float(p['g2']), transmittance=float(p['transmittance']))
processor = pcvl.Processor('SLOS', circuit, noise=noise)
processor.with_input(pcvl.BasicState(state))
results = pcvl.algorithm.Sampler(processor).probs()['results']
outcomes = sorted(((tuple(int(n) for n in key), float(value)) for key, value in results.items()), key=lambda item: -item[1])


def permanent(a):
    """Ryser's formula."""
    n = a.shape[0]
    if n == 0:
        return 1.0
    total = 0j
    for size in range(1, n + 1):
        for columns in itertools.combinations(range(n), size):
            total += (-1) ** size * np.prod(a[:, columns].sum(axis=1))
    return (-1) ** n * total


checks = {'permanent_difference': None, 'hom_difference': None}
perfect = p['indistinguishability'] == 1 and p['g2'] == 0 and p['transmittance'] == 1
if perfect and sum(state) <= 8:
    rows = [mode for mode, count in enumerate(state) for _ in range(count)]
    difference = 0.0
    for pattern, probability in outcomes:
        columns = [mode for mode, count in enumerate(pattern) for _ in range(count)]
        if len(columns) != len(rows):
            continue
        normalization = np.prod([math.factorial(n) for n in state]) * np.prod([math.factorial(n) for n in pattern])
        value = abs(permanent(U[np.ix_(columns, rows)])) ** 2 / normalization  # U[out, in]
        difference = max(difference, abs(value - probability))
    checks['permanent_difference'] = float(difference)
if kind == 'beam_splitter' and state == [1, 1] and p['g2'] == 0 and p['transmittance'] == 1:
    R, M = float(p['reflectivity']), float(p['indistinguishability'])
    coincidence = dict(outcomes).get((1, 1), 0.0)
    checks['hom_difference'] = abs(coincidence - ((1 - R) ** 2 + R ** 2 - 2 * R * (1 - R) * M))
photons = sum(state)
coincidence = sum(prob for pattern, prob in outcomes if sum(pattern) == photons and max(pattern) == 1)
bunched = sum(prob for pattern, prob in outcomes if sum(pattern) == photons and max(pattern) > 1)
(OUTPUT_DIR / 'probabilities.json').write_text(__import__('json').dumps(
    [{'output': list(pattern), 'probability': prob} for pattern, prob in outcomes], indent=1) + '\n', encoding='utf-8')
saved = data.save(OUTPUT_DIR / 'outputs', {
    'probability': data.quantity(np.array([prob for _, prob in outcomes]), 'probability of the output pattern', unit='1',
                                 axes=[{'name': 'output', 'labels': ['|' + ','.join(map(str, pattern)) + '>' for pattern, _ in outcomes]}],
                                 input_state=state, interferometer=kind),
    'unitary_real': data.quantity(U.real, 'real part of the interferometer unitary', unit='1'),
    'unitary_imag': data.quantity(U.imag, 'imaginary part of the interferometer unitary', unit='1'),
})
RESULT = {'data': saved['data'], 'files': ['probabilities.json'], 'outputs': len(outcomes),
          'most_likely': [{'output': list(pattern), 'probability': prob} for pattern, prob in outcomes[:8]],
          'coincidence': float(coincidence), 'bunched': float(bunched), 'checks': checks}
