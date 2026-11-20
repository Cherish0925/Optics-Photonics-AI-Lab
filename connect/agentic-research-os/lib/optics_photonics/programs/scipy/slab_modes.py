"""Guided modes of a planar waveguide with any layered index profile (finite differences).

The profile is a stack of layers along x between two claddings, each with a
number, [n, k] or a material from the materials tool evaluated at the
wavelength. With fields varying as exp(i(beta z - w t)), TE modes (E along
y) solve E'' + k0^2 n^2 E = beta^2 E and TM modes (H along y) solve
n^2 (H'/n^2)' + k0^2 n^2 H = beta^2 H, discretized on a uniform grid whose
outer boundaries lie far inside the claddings. A mode is guided when its
effective index exceeds both cladding indices. For a symmetric three-layer
slab the effective indices are compared with the roots of the analytic
dispersion relation.
"""
import numpy as np
from scipy.linalg import eigh_tridiagonal
from scipy.optimize import brentq
from optics_photonics import data, materials
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'layers': ([{'n': 3.476, 'thickness_um': 0.22}], 'core layers from bottom to top: n (number, [n, k] or material) and thickness_um'),
        'cladding_bottom': (1.444, 'index of the lower cladding: number or material'),
        'cladding_top': (1.444, 'index of the upper cladding: number or material'),
        'wavelength_um': (1.55, 'vacuum wavelength in micrometres'),
        'polarization': ('te', 'te or tm'),
        'cladding_um': (2.0, 'thickness of each cladding inside the computational window, in micrometres'),
        'points_per_um': (400, 'grid points per micrometre'),
        'modes': (4, 'largest number of guided modes to report'),
    },
    'domains': ['pic', 'em'],
    'results': 'modes.npz/.json with mode profiles and the index profile over x; effective indices; confinement in the layers',
    'checks': 'analytic_error: largest difference from the analytic effective indices of a symmetric three-layer slab',
}
p = parameters(PROGRAM, INPUTS)
wavelength = float(p['wavelength_um'])
if wavelength <= 0 or p['polarization'] not in ('te', 'tm') or not p['layers']:
    raise ValueError('wavelength_um is positive, polarization te or tm, and layers is not empty')
pages = {}


def index(entry):
    if isinstance(entry, str):
        pages[entry] = materials.resolve(entry)
        return materials.index_at(entry, wavelength)
    return complex(entry[0], entry[1]) if isinstance(entry, (list, tuple)) else complex(entry)


core = [(index(layer['n']), float(layer['thickness_um'])) for layer in p['layers']]
bottom, top, margin = index(p['cladding_bottom']), index(p['cladding_top']), float(p['cladding_um'])
edges = np.cumsum([0] + [thickness for _, thickness in core])
width = edges[-1] + 2 * margin
cells = int(round(width * float(p['points_per_um'])))
x = (np.arange(cells) + 0.5) * width / cells - margin              # cell centres; core from 0 to edges[-1]
n = np.where(x < 0, bottom, top).astype(complex)
for (value, _), low, high in zip(core, edges[:-1], edges[1:]):
    n[(x >= low) & (x < high)] = value
eps = n ** 2
dx, k0 = x[1] - x[0], 2 * np.pi / wavelength
lossless = np.all(np.abs(eps.imag) < 1e-12)
# d/dx (a d/dx) with a = 1 for TE and a = 1/eps for TM; a at the face between two cells is the value that keeps
# a dF/dx continuous there: 1/eps averaged as 2/(eps_i + eps_i+1).
face = np.ones(cells - 1) if p['polarization'] == 'te' else 2 / (eps[:-1] + eps[1:])
weight = np.ones(cells) if p['polarization'] == 'te' else eps        # TM: n^2 (a F')' + k0^2 n^2 F
outer = np.concatenate([[face[0]], face]) + np.concatenate([face, [face[-1]]])
diagonal = -weight * outer / dx ** 2 + k0 ** 2 * eps                 # TE: L + k0^2 eps; TM: eps (L + k0^2)
if lossless:
    # weight^(1/2) L weight^(1/2) + k0^2 eps is symmetric and has the same eigenvalues, beta^2.
    root = np.sqrt(weight.real)
    floor_value = k0 ** 2 * max(bottom.real, top.real) ** 2
    values, vectors = eigh_tridiagonal(diagonal.real, root[:-1] * root[1:] * face.real / dx ** 2,
                                       select='v', select_range=(floor_value, k0 ** 2 * np.max(eps.real) + 1))
    vectors = vectors * root[:, None]
else:
    from scipy.sparse import diags
    from scipy.sparse.linalg import eigs
    matrix = diags([weight[1:] * face / dx ** 2, diagonal, weight[:-1] * face / dx ** 2], [-1, 0, 1], format='csc')
    values, vectors = eigs(matrix, k=min(int(p['modes']) + 4, cells - 2), sigma=k0 ** 2 * np.max(eps.real))
neff = np.sqrt(values.astype(complex)) / k0
order = np.argsort(-neff.real)
floor = max(bottom.real, top.real)
guided = [i for i in order if neff[i].real > floor + 1e-9][:int(p['modes'])]
profiles, confinement = [], []
inside = (x >= 0) & (x < edges[-1])
for i in guided:
    field = vectors[:, i]
    field = field / field[np.argmax(np.abs(field))]
    profiles.append(field.real if lossless else field)
    weight = np.abs(field) ** 2 if p['polarization'] == 'te' else np.abs(field) ** 2 / np.abs(eps)
    confinement.append(float(weight[inside].sum() / weight.sum()))

error = None
if len(core) == 1 and abs(bottom - top) < 1e-12 and lossless and guided:
    n1, n2, d = core[0][0].real, bottom.real, core[0][1]
    ratio = (n1 / n2) ** 2 if p['polarization'] == 'tm' else 1.0
    def mismatch(m, ne):
        kappa, decay = k0 * np.sqrt(n1 ** 2 - ne ** 2), k0 * np.sqrt(ne ** 2 - n2 ** 2)
        return kappa * d - m * np.pi - 2 * np.arctan(ratio * decay / kappa)
    analytic = [brentq(lambda ne: mismatch(m, ne), n2 + 1e-12, n1 - 1e-12) for m in range(len(guided))
                if mismatch(m, n2 + 1e-12) > 0]
    count = min(len(analytic), len(guided))
    error = float(max(abs(neff[guided[m]].real - analytic[m]) for m in range(count))) if count else None
if not guided:
    raise ValueError('No guided mode: no effective index exceeds both claddings. A thicker or higher-index core, '
                     'a shorter wavelength or wider claddings in the window may change that')
axes = [{'name': 'mode', 'start': 0, 'step': 1}, 'x_um']
saved = data.save(OUTPUT_DIR / 'modes', {
    'profile': data.quantity(np.asarray(profiles), ('E_y' if p['polarization'] == 'te' else 'H_y') + ' mode profile', unit='1', axes=axes,
                             normalization='largest magnitude = 1', time_dependence='exp(-i omega t)', materials=pages),
    'index': data.quantity(n, 'refractive index profile', unit='1', axes=['x_um']),
    'x_um': data.quantity(x, 'transverse position', unit='um', reference='bottom of the first core layer'),
})
RESULT = {'data': saved['data'], 'effective_indices': [[float(neff[i].real), float(neff[i].imag)] for i in guided],
          'confinement': confinement, 'guided_modes': len(guided), 'materials': pages, 'checks': {'analytic_error': error}}
