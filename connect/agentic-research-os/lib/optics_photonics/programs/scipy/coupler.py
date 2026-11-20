"""Directional coupler of two identical waveguides from its supermodes: coupling over length and wavelength, for a circuit.

In a two-dimensional (slab) model two identical cores of width w and index
n1 lie a gap g apart in a cladding of index n2; n1 is the effective index of
the vertical slab when the method of effective indices reduces a channel
waveguide to this plane. The even and odd supermodes of the five layers are
the roots of their exact dispersion relations (TE: E along y and E' continuous;
TM: H along y and H'/n^2 continuous). Light entering one core beats between
them, so after a length L the power in the other core is sin^2(pi L / (2 L_c))
with the transfer length L_c = lambda / (2 (n_even - n_odd)), and the coupler
is the scattering matrix [[t, i k], [i k, t]] that sax/circuit takes through
its coupling (ring) or splitter (interferometer) inputs, with the effective
and group index of one core alone for its waveguides. The coupling
coefficient kappa = pi / (2 L_c) is compared with the coupled-mode
expression for two slabs, 2 h^2 p exp(-p g) / (beta (w + 2/p)(h^2 + p^2))
for TE (Marcuse), which becomes exact as the gap grows. Lengths in
micrometres.
"""
import math
import numpy as np
from scipy import optimize
from optics_photonics import data, materials
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'width_um': (0.5, 'width of each core in micrometres'),
        'gap_um': (0.2, 'gap between the cores in micrometres'),
        'length_um': (5.0, 'length of the coupling section in micrometres'),
        'core_index': (2.85, 'core index: number or material; 2.85 is the TE effective index of a 220 nm silicon slab near 1.55 um'),
        'cladding_index': (1.444, 'cladding index: number or material'),
        'polarization': ('te', 'te or tm'),
        'wavelength_um': ({'start': 1.5, 'stop': 1.6, 'points': 21}, 'vacuum wavelengths, or {"start", "stop", "points"}'),
    },
    'domains': ['pic'],
    'results': 'coupler.npz/.json: even, odd and single-core effective indices, transfer length and coupling over wavelength, and the '
               'coupling along the length at the centre wavelength; the coupling and transfer length at the centre wavelength',
    'checks': 'cmt_difference: relative difference of the coupling coefficient from the coupled-mode expression (TE), small for wide gaps',
}
p = parameters(PROGRAM, INPUTS)
width, gap, length = float(p['width_um']), float(p['gap_um']), float(p['length_um'])
spec = p['wavelength_um']
wavelengths = (np.linspace(float(spec['start']), float(spec['stop']), int(spec['points'])) if isinstance(spec, dict)
               else np.atleast_1d(np.asarray(spec, float)))
if width <= 0 or gap < 0 or length < 0 or p['polarization'] not in ('te', 'tm') or np.any(wavelengths <= 0):
    raise ValueError('width_um is positive, gap_um and length_um are not negative, polarization is te or tm')
pages = {}


def index(entry, wavelength):
    if isinstance(entry, str):
        pages[entry] = materials.resolve(entry)
        return materials.index_at(entry, wavelength).real
    return float(entry[0]) if isinstance(entry, (list, tuple)) else float(entry)


def scan(function, low, high):
    """Roots of function between the two indices, highest first."""
    grid = np.linspace(low, high, 4001)[1:-1]
    values = np.array([function(x) for x in grid])
    roots = [optimize.brentq(function, grid[i], grid[i + 1], xtol=1e-15) for i in np.flatnonzero(np.sign(values[:-1]) * np.sign(values[1:]) < 0)]
    return sorted(roots, reverse=True)


def supermodes(wavelength):
    n1, n2 = index(p['core_index'], wavelength), index(p['cladding_index'], wavelength)
    if n1 <= n2:
        raise ValueError('The core index must exceed the cladding index')
    k0 = 2 * math.pi / wavelength
    tm = p['polarization'] == 'tm'

    def wavenumbers(n):
        h, q = k0 * math.sqrt(n1 * n1 - n * n), k0 * math.sqrt(n * n - n2 * n2)
        return h, q, (h / n1 ** 2, q / n2 ** 2) if tm else (h, q)

    def relation(n, parity):
        """Field matching at the outer core edge after matching cosh / sinh of the gap at the inner edge."""
        h, q, (hh, qq) = wavenumbers(n)
        inner = (math.cosh(q * gap / 2), math.sinh(q * gap / 2)) if parity == 'even' else (math.sinh(q * gap / 2), math.cosh(q * gap / 2))
        a, b = inner[0], qq / hh * inner[1]
        return a * (qq * math.cos(h * width) - hh * math.sin(h * width)) + b * (hh * math.cos(h * width) + qq * math.sin(h * width))

    def single(n):
        h, q, (hh, qq) = wavenumbers(n)
        return math.tan(h * width / 2) - qq / hh if math.cos(h * width / 2) != 0 else math.inf

    low, high = n2 * (1 + 1e-12), n1 * (1 - 1e-12)
    even, odd = scan(lambda n: relation(n, 'even'), low, high), scan(lambda n: relation(n, 'odd'), low, high)
    alone = [root for root in scan(single, low, high) if abs(single(root)) < 1e-6]
    if not even or not odd:
        raise ValueError(f'At {wavelength:g} um the coupler guides no {"odd" if even else "even"} supermode: widen the cores or shorten the wavelength')
    return n1, n2, even[0], odd[0], alone[0] if alone else None


rows = [supermodes(w) for w in wavelengths]
n_even = np.array([r[2] for r in rows]); n_odd = np.array([r[3] for r in rows])
n_alone = np.array([np.nan if r[4] is None else r[4] for r in rows])
# Group index of one core, n - lambda dn/dlambda, for the circuit; needs three or more wavelengths.
group = n_alone - wavelengths * np.gradient(n_alone, wavelengths) if len(wavelengths) >= 3 else np.full_like(n_alone, np.nan)
transfer = wavelengths / (2 * (n_even - n_odd))                      # L_c, um
coupling = np.sin(math.pi * length / (2 * transfer)) ** 2
centre = len(wavelengths) // 2

# Coupled-mode theory for two identical TE slabs: kappa = 2 h^2 p exp(-p g) / (beta (w + 2/p)(h^2 + p^2)).
cmt_difference = None
n1, n2, _, _, single_index = rows[centre]
if p['polarization'] == 'te' and single_index:
    k0 = 2 * math.pi / wavelengths[centre]
    h, q, beta = k0 * math.sqrt(n1 ** 2 - single_index ** 2), k0 * math.sqrt(single_index ** 2 - n2 ** 2), k0 * single_index
    kappa_cmt = 2 * h * h * q * math.exp(-q * gap) / (beta * (width + 2 / q) * (h * h + q * q))
    kappa = math.pi / (2 * transfer[centre])
    cmt_difference = abs(kappa - kappa_cmt) / kappa

along = np.linspace(0, max(length, 2 * transfer[centre]), 401)
saved = data.save(OUTPUT_DIR / 'coupler', {
    'wavelength_um': data.quantity(wavelengths, 'vacuum wavelength', unit='um'),
    'n_even': data.quantity(n_even, 'effective index of the even supermode', unit='1', axes=['wavelength_um'], polarization=p['polarization']),
    'n_odd': data.quantity(n_odd, 'effective index of the odd supermode', unit='1', axes=['wavelength_um']),
    'n_single': data.quantity(n_alone, 'effective index of one core alone', unit='1', axes=['wavelength_um']),
    'ng_single': data.quantity(group, 'group index of one core alone', unit='1', axes=['wavelength_um']),
    'transfer_length': data.quantity(transfer, 'length for complete transfer to the other core', unit='um', axes=['wavelength_um']),
    'coupling': data.quantity(coupling, 'power in the other core after the coupling length', unit='1', axes=['wavelength_um'], length_um=length),
    'position_um': data.quantity(along, 'position along the coupler', unit='um'),
    'cross_power': data.quantity(np.sin(math.pi * along / (2 * transfer[centre])) ** 2, 'power in the other core at the centre wavelength',
                                 unit='1', axes=['position_um'], wavelength_um=float(wavelengths[centre])),
})
RESULT = {'data': saved['data'], 'centre_wavelength_um': float(wavelengths[centre]), 'coupling': float(coupling[centre]),
          'transfer_length_um': float(transfer[centre]), 'half_transfer_length_um': float(transfer[centre] / 2),
          'n_even': float(n_even[centre]), 'n_odd': float(n_odd[centre]), 'n_single': single_index,
          'ng_single': float(group[centre]) if np.isfinite(group[centre]) else None,
          'coupling_range': [float(coupling.min()), float(coupling.max())], 'materials': pages,
          'checks': {'cmt_difference': cmt_difference}}
