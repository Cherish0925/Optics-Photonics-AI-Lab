"""Scattering of a plane wave by a cylinder in two dimensions (NGSolve, finite elements with a perfectly matched layer).

A wave exp(i k x) meets an infinite cylinder of radius a and index n + ik in
a medium of index 1; fields vary as exp(-i w t). The scattered field u
solves the Helmholtz equation with the incident wave as its source inside
the cylinder: for TM (u = E along the axis)
div grad u + k^2 eps u = -k^2 (eps - 1) u_inc, and for TE (u = H along the
axis) div (grad u / eps) + k^2 u = -div((1/eps - 1) grad u_inc). The mesh
has curved elements of the given order; a radial perfectly matched layer
absorbs the outgoing wave. Efficiencies are cross sections per unit length
over the diameter: Q_sca from the flux of the scattered field through a
circle, Q_abs from the loss inside the cylinder. A circular cylinder has an
exact series in Bessel and Hankel functions (Bohren and Huffman, ch. 8),
with which the field on a circle and Q_sca are compared; a metal cylinder
in TE shows its plasmon resonance. For another cross-section, replace the
circle of the cylinder in the geometry: the equations stay the same.
"""
import numpy as np
from scipy.special import h1vp, hankel1, jv, jvp
import ngsolve as ng
from netgen.geom2d import SplineGeometry
from optics_photonics import data, materials
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'radius_um': (0.3, 'cylinder radius in micrometres'),
        'index': ([2.0, 0.0], 'cylinder index: number, [n, k] or material name (Si, Ag, ...)'),
        'wavelength_um': (1.0, 'vacuum wavelength in micrometres'),
        'polarization': ('tm', 'tm: electric field along the axis; te: magnetic field along the axis'),
        'order': (4, 'polynomial order of the elements'),
        'elements_per_wavelength': (5, 'elements per wavelength in each material'),
        'air_um': (1.0, 'distance from the cylinder to the absorbing layer'),
        'layer_um': (1.0, 'thickness of the absorbing layer'),
        'grid': (121, 'points per side of the saved field map; 0 skips the map'),
    },
    'domains': ['em', 'scatter'],
    'results': 'field.npz/.json: |total field|^2 on a square grid and the scattered field on a circle; Q_sca, Q_abs, Q_ext; unknowns',
    'checks': 'field_difference: largest difference of the scattered field on the circle from the exact series, relative to its '
              'largest value, or absolute for a zero scattered field (unit incident amplitude); efficiency_difference: Q_sca minus the series',
}
p = parameters(PROGRAM, INPUTS)
radius, wavelength, air, layer = (float(p[key]) for key in ('radius_um', 'wavelength_um', 'air_um', 'layer_um'))
if min(radius, wavelength, air, layer) <= 0 or p['polarization'] not in ('tm', 'te') or not 1 <= int(p['order']) <= 8:
    raise ValueError('radius_um, wavelength_um, air_um and layer_um are positive, polarization tm or te, order from 1 to 8')
pages = {}
entry = p['index']
if isinstance(entry, str):
    pages['cylinder'] = materials.resolve(entry)
    n = materials.index_at(entry, wavelength)
else:
    n = complex(entry[0], abs(entry[1])) if isinstance(entry, (list, tuple)) else complex(entry)
eps, k = n ** 2, 2 * np.pi / wavelength
tm = p['polarization'] == 'tm'

inner, outer = radius + air, radius + air + layer
step = wavelength / float(p['elements_per_wavelength'])
geometry = SplineGeometry()
geometry.AddCircle((0, 0), outer, leftdomain=3, rightdomain=0, bc='outer')
geometry.AddCircle((0, 0), inner, leftdomain=2, rightdomain=3)
geometry.AddCircle((0, 0), radius, leftdomain=1, rightdomain=2)
for number, name, size in ((1, 'cylinder', step / max(abs(n), 1)), (2, 'air', step), (3, 'layer', step)):
    geometry.SetMaterial(number, name)
    geometry.SetDomainMaxH(number, size)
mesh = ng.Mesh(geometry.GenerateMesh(maxh=step))
mesh.Curve(int(p['order']))
mesh.SetPML(ng.pml.Radial(rad=inner, alpha=2j, origin=(0, 0)), 'layer')

space = ng.H1(mesh, order=int(p['order']), complex=True, dirichlet='outer')
u, v = space.TnT()
incident = ng.exp(1j * k * ng.x)
permittivity = mesh.MaterialCF({'cylinder': eps}, default=1.0)
a, f = ng.BilinearForm(space), ng.LinearForm(space)
if tm:
    a += (ng.grad(u) * ng.grad(v) - k ** 2 * permittivity * u * v) * ng.dx
    f += k ** 2 * (eps - 1) * incident * v * ng.dx('cylinder')
else:
    a += (1 / permittivity * ng.grad(u) * ng.grad(v) - k ** 2 * u * v) * ng.dx
    f += -(1 / eps - 1) * 1j * k * incident * ng.grad(v)[0] * ng.dx('cylinder')
a.Assemble()
f.Assemble()
scattered = ng.GridFunction(space)
scattered.vec.data = a.mat.Inverse(space.FreeDofs()) * f.vec
total = scattered + incident

# Efficiencies. The flux of the scattered field through a circle in the air, per unit incident intensity, is
# Im(integral of conj(u) du/dr) / k; the loss inside is k Im(eps) |u|^2 for TM and k Im(eps) |grad u|^2 / (k^2 |eps|^2) for TE.
circle = radius + air / 2
angles = np.linspace(0, 2 * np.pi, 361)[:-1]
points = mesh(circle * np.cos(angles), circle * np.sin(angles))
values = scattered(points).reshape(-1)
gradient = ng.grad(scattered)(points).reshape(len(angles), 2)
radial = gradient[:, 0] * np.cos(angles) + gradient[:, 1] * np.sin(angles)
q_sca = float(np.imag(np.sum(np.conj(values) * radial)) * 2 * np.pi * circle / len(angles) / k / (2 * radius))
if tm:
    loss = ng.Integrate(k * eps.imag * ng.Norm(total) ** 2 * ng.dx('cylinder'), mesh)
else:
    whole = ng.grad(scattered) + ng.CoefficientFunction((1j * k * incident, 0))
    loss = ng.Integrate(eps.imag / (k * abs(eps) ** 2) * ng.Norm(whole) ** 2 * ng.dx('cylinder'), mesh)
q_abs = float(np.real(loss) / (2 * radius))

# Exact series: u = sum_m i^m a_m H_m(k r) exp(i m phi) outside the cylinder.
x = k * radius
m = np.arange(-int(x + 4 * x ** (1 / 3) + 12), int(x + 4 * x ** (1 / 3) + 12) + 1)
if eps == 1:
    coefficients = np.zeros(m.size, dtype=complex)  # Identical media have no scattering; avoid cancellation in the Bessel quotient.
elif tm:
    coefficients = -(n * jvp(m, n * x) * jv(m, x) - jv(m, n * x) * jvp(m, x)) / (n * jvp(m, n * x) * hankel1(m, x) - jv(m, n * x) * h1vp(m, x))
else:
    coefficients = -(jvp(m, n * x) * jv(m, x) - n * jv(m, n * x) * jvp(m, x)) / (jvp(m, n * x) * hankel1(m, x) - n * jv(m, n * x) * h1vp(m, x))
exact = (1j ** m * coefficients * hankel1(m, k * circle) * np.exp(1j * np.outer(angles, m))).sum(axis=1)
exact_sca = float(2 / x * np.sum(np.abs(coefficients) ** 2))
exact_ext = float(-2 / x * np.sum(coefficients.real))

arrays = {
    'scattered': data.quantity(values, 'scattered field on a circle, incident amplitude 1', unit='1', axes=['angle_deg'],
                               radius_um=circle, materials=pages),
    'scattered_exact': data.quantity(exact, 'scattered field on the circle from the exact series', unit='1', axes=['angle_deg']),
    'angle_deg': data.quantity(np.degrees(angles), 'angle from the direction of incidence', unit='deg'),
}
side = int(p['grid'])
if side:
    axis = np.linspace(-inner, inner, side) * 0.999
    X, Y = np.meshgrid(axis, axis, indexing='ij')
    keep = X ** 2 + Y ** 2 < inner ** 2
    field = np.full(X.shape, np.nan)
    field[keep] = np.abs(scattered(mesh(X[keep], Y[keep])).reshape(-1) + np.exp(1j * k * X[keep])) ** 2
    arrays.update({
        'intensity': data.quantity(field, '|total field|^2, incident 1; empty outside the computed disk', unit='1', axes=['x_um', 'y_um']),
        'x_um': data.quantity(axis, 'position along the direction of incidence', unit='um'),
        'y_um': data.quantity(axis, 'position across the direction of incidence', unit='um'),
    })
saved = data.save(OUTPUT_DIR / 'field', arrays)
field_scale = float(np.abs(exact).max())
field_difference = float(np.abs(values - exact).max()) / (field_scale if field_scale else 1.0)
RESULT = {
    'Q_sca': q_sca, 'Q_abs': q_abs, 'Q_ext': q_sca + q_abs, 'series': {'Q_sca': exact_sca, 'Q_ext': exact_ext},
    'index': [n.real, n.imag], 'unknowns': int(space.ndof), 'elements': int(mesh.ne), 'data': saved['data'], 'materials': pages,
    'checks': {'field_difference': field_difference, 'efficiency_difference': q_sca - exact_sca},
}
