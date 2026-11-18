"""Inverse design of a waveguide bend by topology optimization with adjoint gradients (ceviche, 2-D FDFD).

ceviche solves the two-dimensional frequency-domain Maxwell equations for Ez
(electric field normal to the plane) on a uniform grid with perfectly matched
layers, and autograd differentiates the solution, so the gradient of the
objective with respect to every pixel of the design region costs one extra
(adjoint) solve. A horizontal input waveguide and a vertical output waveguide
of the same width meet at a square design region; the fundamental mode is
launched in the input and the objective is the power coupled into the
fundamental mode of the output, normalized by that of a straight waveguide
of the same length, so it is the bend's transmission into that mode. The
design density rho in [0, 1] is smoothed by a disk of radius filter_um and
projected by a tanh of growing sharpness, eps = eps_clad + (eps_core -
eps_clad) rho, and Adam updates it within bounds. The final design is
thresholded at 1/2 and simulated again, which gives the transmission of a
binary, fabricable pattern. A check compares the adjoint gradient with a
central finite difference along a random direction.
"""
import math
import numpy as np
import autograd.numpy as npa
from autograd import grad, value_and_grad
from autograd.scipy.signal import convolve
from ceviche import fdfd_ez
from ceviche.modes import insert_mode
from optics_photonics import data, materials
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'wavelength_um': (1.55, 'vacuum wavelength in micrometres'),
        'core_index': (3.48, 'index of the waveguides and of the design material: number or material name'),
        'cladding_index': (1.44, 'index of the surrounding medium: number or material name'),
        'width_um': (0.4, 'width of the input and output waveguides in micrometres'),
        'design_um': (1.6, 'side of the square design region in micrometres'),
        'grid_um': (0.025, 'grid spacing in micrometres'),
        'filter_um': (0.075, 'radius of the smoothing disk, the smallest feature scale, in micrometres'),
        'iterations': (40, 'Adam steps'),
        'step': (0.05, 'Adam step size in density units'),
        'seed': (0, 'seed of the random direction of the gradient check'),
    },
    'results': 'bend.npz/.json: final density and permittivity of the design, permittivity and |Ez| of the binary device, transmission over '
               'the iterations; transmission at the start, at the end and of the binary design',
    'checks': 'gradient_difference: relative difference between the adjoint and a finite-difference directional derivative at the start',
}
p = parameters(PROGRAM, INPUTS)
C0 = 299792458.0
pages = {}


def index(entry):
    if isinstance(entry, str):
        pages[entry] = materials.resolve(entry)
        return materials.index_at(entry, float(p['wavelength_um'])).real
    return float(entry[0]) if isinstance(entry, (list, tuple)) else float(entry)


wavelength, dl = float(p['wavelength_um']), float(p['grid_um'])
eps_core, eps_clad = index(p['core_index']) ** 2, index(p['cladding_index']) ** 2
if not (wavelength > 0 and dl > 0 and eps_core > eps_clad and int(p['iterations']) >= 0):
    raise ValueError('wavelength_um and grid_um are positive, the core index exceeds the cladding index and iterations is not negative')
omega = 2 * math.pi * C0 / (wavelength * 1e-6)
cells = lambda length: int(round(length / dl))
npml, margin = cells(0.5), cells(0.5)
width, design = max(1, cells(float(p['width_um']))), cells(float(p['design_um']))
n = 2 * npml + 2 * margin + design + 2 * cells(0.5)          # square domain: PML, feed, design, feed, PML
centre = n // 2
lo, hi = centre - design // 2, centre - design // 2 + design
guide = slice(centre - width // 2, centre - width // 2 + width)

base = np.full((n, n), eps_clad)
base[:lo, guide] = eps_core                                   # input waveguide along x, from the left
base[guide, hi:] = eps_core                                   # output waveguide along y, to the top
straight = np.full((n, n), eps_clad)
straight[:, guide] = eps_core
mask = np.zeros((n, n)); mask[lo:hi, lo:hi] = 1

window = slice(centre - 4 * width, centre + 4 * width)
source = insert_mode(omega, dl * 1e-6, npml + 5, window, base, m=1)
probe = insert_mode(omega, dl * 1e-6, window, n - npml - 5, base, m=1)            # across the output waveguide
reference_probe = insert_mode(omega, dl * 1e-6, n - npml - 5, window, straight, m=1)
_, _, reference_field = fdfd_ez(omega, dl * 1e-6, straight, [npml, npml]).solve(source)
reference = abs(np.sum(np.conj(reference_probe) * reference_field)) ** 2

radius = max(1, cells(float(p['filter_um'])))
r = np.arange(-radius, radius + 1)
kernel = (r[:, None] ** 2 + r[None, :] ** 2 <= radius ** 2).astype(float)
kernel /= kernel.sum()


def projection(rho, sharpness):
    """The density smoothed over the filter disk and pushed towards 0 or 1 about 1/2."""
    smooth = convolve(rho, kernel, mode='same')
    return (npa.tanh(sharpness / 2) + npa.tanh(sharpness * (smooth - 0.5))) / (2 * npa.tanh(sharpness / 2))


def permittivity(rho, sharpness):
    """The projected density in the design region; the waveguides elsewhere."""
    region = npa.pad(eps_clad + (eps_core - eps_clad) * projection(rho, sharpness), ((lo, n - hi), (lo, n - hi)), mode='constant')
    return base * (1 - mask) + region


def transmission(eps):
    _, _, ez = fdfd_ez(omega, dl * 1e-6, eps, [npml, npml]).solve(source)
    return npa.abs(npa.sum(npa.conj(probe) * ez)) ** 2 / reference, ez


def objective(rho, sharpness):
    return transmission(permittivity(rho, sharpness))[0]


gradient, evaluate = grad(objective), value_and_grad(objective)
rho = np.full((design, design), 0.5)

# Adjoint gradient against a central difference along a random direction.
direction = np.random.default_rng(int(p['seed'])).standard_normal(rho.shape)
direction /= np.linalg.norm(direction)
h = 1e-4
adjoint = float(np.sum(gradient(rho, 2.0) * direction))
finite = (objective(rho + h * direction, 2.0) - objective(rho - h * direction, 2.0)) / (2 * h)
gradient_difference = abs(adjoint - finite) / abs(finite)

# Adam with bounds, sharpening the projection over the iterations.
steps, history = int(p['iterations']), []
first, second = np.zeros_like(rho), np.zeros_like(rho)
for k in range(steps):
    sharpness = 2.0 * 2 ** (4 * k / max(steps - 1, 1))       # 2 to 32
    value, g = evaluate(rho, sharpness)
    history.append(float(value))
    first = 0.9 * first + 0.1 * g
    second = 0.999 * second + 0.001 * g * g
    rho = np.clip(rho + float(p['step']) * (first / (1 - 0.9 ** (k + 1))) / (np.sqrt(second / (1 - 0.999 ** (k + 1))) + 1e-8), 0, 1)

final_sharpness = 2.0 * 2 ** 4 if steps else 2.0
final = float(objective(rho, final_sharpness))
smooth = np.asarray(convolve(rho, kernel, mode='same'))
binary = base * (1 - mask) + np.pad(np.where(smooth > 0.5, eps_core, eps_clad), ((lo, n - hi), (lo, n - hi)))
binary_transmission, field = transmission(binary)
axis = (np.arange(n) - centre) * dl
saved = data.save(OUTPUT_DIR / 'bend', {
    'x_um': data.quantity(axis, 'position across the domain', unit='um', reference='centre of the design region'),
    'y_um': data.quantity(axis, 'position across the domain', unit='um', reference='centre of the design region'),
    'density': data.quantity(rho, 'design density before smoothing', unit='1', axes=[{'name': 'x', 'unit': 'um', 'start': (lo - centre) * dl, 'step': dl},
                                                                                     {'name': 'y', 'unit': 'um', 'start': (lo - centre) * dl, 'step': dl}]),
    'permittivity': data.quantity(binary, 'relative permittivity of the binary device', unit='1', axes=['x_um', 'y_um']),
    'field': data.quantity(np.abs(np.asarray(field)), '|Ez| of the binary device for the launched mode', unit='arbitrary', axes=['x_um', 'y_um'],
                           time_dependence='exp(-i omega t)'),
    'transmission': data.quantity(history, 'transmission into the output mode at each iteration', unit='1',
                                  axes=[{'name': 'iteration', 'start': 0, 'step': 1}]),
})
RESULT = {'data': saved['data'], 'grid': [n, n], 'design_cells': design,
          'transmission': {'start': history[0] if history else final, 'end': final, 'binary': float(binary_transmission)},
          'binary_fraction': float(np.mean(np.abs(np.asarray(projection(rho, final_sharpness)) - 0.5) > 0.4)), 'materials': pages,
          'checks': {'gradient_difference': gradient_difference}}
