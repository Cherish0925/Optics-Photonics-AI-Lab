"""Guided modes of a step-index optical fiber: LP and exact vector modes, and the dispersion of the fundamental mode.

A core of radius a and index n1 in a cladding of index n2 guides modes whose
transverse wavenumbers u = a sqrt(k0^2 n1^2 - beta^2) and w = a sqrt(beta^2 -
k0^2 n2^2) satisfy u^2 + w^2 = V^2, V = k0 a sqrt(n1^2 - n2^2). LP modes are
the weakly guiding (scalar) solutions of u J_{l-1}(u) / J_l(u) = -w
K_{l-1}(w) / K_l(w); vector modes solve the exact characteristic equation of
the step-index fiber (Snyder and Love): TE0m, TM0m and the hybrid HE and EH
modes. HE_{nu,m} tends to LP_{nu-1,m} and EH_{nu,m} to LP_{nu+1,m} as n1 - n2
goes to zero. An index is a number, [n, k] (k is ignored), or a material from
the materials tool evaluated at each wavelength; without core_index the core
index is sqrt(n2^2 + NA^2). The fiber is single-mode below V = 2.405, where
LP11 sets in. For the fundamental mode (HE11, or LP01 without vector modes)
the program reports the group index n_g = n_eff - lambda dn_eff/dlambda and
the chromatic dispersion D = -(lambda/c) d^2n_eff/dlambda^2, both including
the material dispersion of the indices, with beta2 = -lambda^2 D / (2 pi c);
from the LP01 field, the mode field diameter (Petermann II), the effective
area and the nonlinear coefficient gamma = 2 pi n2 / (lambda A_eff) that the
nlse program takes. Derivatives are central differences of solutions at
neighbouring wavelengths.
"""
import math
import numpy as np
from scipy import integrate, optimize, special
from optics_photonics import data, materials
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'radius_um': (4.1, 'core radius in micrometres'),
        'cladding_index': ('SiO2', 'cladding index: number, [n, k] or material name'),
        'core_index': (None, 'core index: number, [n, k] or material name; null takes it from numerical_aperture'),
        'numerical_aperture': (0.12, 'sqrt(n1^2 - n2^2), used when core_index is null'),
        'wavelength_nm': ({'start': 1200, 'stop': 1700, 'points': 26}, 'vacuum wavelengths in nm, or {"start", "stop", "points"}'),
        'vector': (True, 'also solve the exact vector modes (TE, TM, HE, EH)'),
        'n2_m2_per_W': (2.6e-20, 'nonlinear index of the core for gamma; 2.6e-20 m^2/W for fused silica'),
    },
    'domains': ['fiber'],
    'results': 'modes.npz/.json: effective indices of every guided LP and vector mode over wavelength, and the fundamental mode\'s '
               'group index, dispersion, beta2, mode field diameter, effective area and gamma; profiles.npz/.json: radial LP fields at the '
               'first wavelength; the modes at the first and last wavelength, the LP11 cutoff wavelength and the zero-dispersion wavelength',
    'checks': 'confinement_difference: LP01 core power fraction integrated from the field minus the closed form; '
              'vector_lp_difference: largest |n_eff(vector) - n_eff(LP)| / (n1 - n2) over corresponding modes',
}
p = parameters(PROGRAM, INPUTS)
radius = float(p['radius_um'])
spec = p['wavelength_nm']
wavelengths = (np.linspace(float(spec['start']), float(spec['stop']), int(spec['points'])) if isinstance(spec, dict)
               else np.atleast_1d(np.asarray(spec, float)))
if radius <= 0 or not len(wavelengths) or np.any(wavelengths <= 0):
    raise ValueError('radius_um and the wavelengths are positive')
pages = {}
C = 299792458.0


def name(kind, order, m):
    return f'{kind}{order}{m}' if order < 10 and m < 10 else f'{kind}{order},{m}'


def index(entry, wavelength_um):
    if isinstance(entry, str):
        pages[entry] = materials.resolve(entry)
        return materials.index_at(entry, wavelength_um).real
    return float(entry[0]) if isinstance(entry, (list, tuple)) else float(entry)


def indices(wavelength_um):
    n2 = index(p['cladding_index'], wavelength_um)
    n1 = index(p['core_index'], wavelength_um) if p['core_index'] is not None else math.hypot(n2, float(p['numerical_aperture']))
    if n1 <= n2:
        raise ValueError(f'The core index {n1:.6f} must exceed the cladding index {n2:.6f}')
    return n1, n2


def k_ratio(order, w):
    """K_{order-1}(w) / K_order(w), with K_{-1} = K_1; exponentially scaled Bessel functions keep it finite."""
    ratio = special.kve(abs(order - 1), w) / special.kve(order, w)
    return np.where(np.isfinite(ratio), ratio, 0.0)


def roots(function, v):
    """Every u in (0, V) where function changes sign, refined by Brent's method; ascending."""
    grid = v * np.linspace(1e-6, 1 - 1e-10, max(400, int(60 * v)))
    values = function(grid)
    found = []
    for i in np.flatnonzero(np.sign(values[:-1]) * np.sign(values[1:]) < 0):
        found.append(optimize.brentq(function, grid[i], grid[i + 1], xtol=1e-15, rtol=1e-15, maxiter=200))
    return found


def lp_function(order, v):
    def f(u):
        u = np.asarray(u, float)
        w = np.sqrt(np.maximum(v * v - u * u, 1e-300))
        upper = -special.jv(1, u) if order == 0 else special.jv(order - 1, u)
        return u * upper + w * k_ratio(order, w) * special.jv(order, u)
    return f


def vector_functions(order, v, r):
    """TE, TM for order 0; the HE (s = -1) and EH (s = +1) branches of the hybrid equation for order >= 1."""
    def kterm(w):  # K_order'(w) / (w K_order(w))
        return (-k_ratio(order, w) - order / w) / w if order else -special.kve(1, w) / special.kve(0, w) / w
    def make(kind):
        def f(u):
            u = np.asarray(u, float)
            w = np.sqrt(np.maximum(v * v - u * u, 1e-300))
            if order == 0:  # J0'(u) / u = -J1(u) / u
                factor = 1.0 if kind == 'TE' else r
                return special.jv(1, u) / u + factor * special.jv(0, u) * (-kterm(w))
            b = kterm(w)
            s = -1.0 if kind == 'HE' else 1.0
            root = np.sqrt(((1 - r) / 2) ** 2 * b * b + order ** 2 * (1 / u ** 2 + 1 / w ** 2) * (1 / u ** 2 + r / w ** 2))
            return special.jvp(order, u) / u - special.jv(order, u) * (-(1 + r) / 2 * b + s * root)
        return f
    return {kind: make(kind) for kind in (('TE', 'TM') if order == 0 else ('HE', 'EH'))}


def solve(wavelength_um, vector):
    """Effective indices by mode label at one wavelength, LP modes and optionally vector modes; V and the indices."""
    n1, n2 = indices(wavelength_um)
    k0 = 2 * math.pi / wavelength_um
    v = k0 * radius * math.sqrt(n1 * n1 - n2 * n2)
    def neff(u):
        return math.sqrt(n1 * n1 - (u / (k0 * radius)) ** 2)
    lp, uvalues = {}, {}
    order = 0
    while True:
        found = roots(lp_function(order, v), v)
        if not found:
            break
        for m, u in enumerate(found, 1):
            lp[name('LP', order, m)] = neff(u)
            uvalues[name('LP', order, m)] = (order, u)
        order += 1
    modes = {}
    if vector:
        r, order, highest = (n2 / n1) ** 2, 0, max(l for l, _ in uvalues.values())
        while True:  # HE_nu tends to LP_{nu-1}: orders up to one above the highest LP order, and on while modes appear
            found = {kind: roots(function, v) for kind, function in vector_functions(order, v, r).items()}
            for kind, values in found.items():
                for m, u in enumerate(values, 1):
                    modes[name(kind, order, m)] = neff(u)
            if order > highest and not any(found.values()):
                break
            order += 1
    return {'V': v, 'n1': n1, 'n2': n2, 'lp': lp, 'u': uvalues, 'vector': modes}


def fundamental(wavelength_um):
    """n_eff of HE11 (vector) or LP01 at one wavelength."""
    n1, n2 = indices(wavelength_um)
    k0 = 2 * math.pi / wavelength_um
    v = k0 * radius * math.sqrt(n1 * n1 - n2 * n2)
    function = vector_functions(1, v, (n2 / n1) ** 2)['HE'] if p['vector'] else lp_function(0, v)
    u = roots(function, v)[0]
    return math.sqrt(n1 * n1 - (u / (k0 * radius)) ** 2)


def field(order, u, w, r):
    """LP field at radius r (same unit as the core radius) normalized to 1 at the core boundary."""
    r = np.asarray(r, float)
    inside = special.jv(order, u * r / radius) / special.jv(order, u)
    outside = special.kve(order, w * r / radius) / special.kve(order, w) * np.exp(-w * (r / radius - 1))
    return np.where(r <= radius, inside, outside)


def lp01_properties(u, w):
    """Petermann II mode field diameter, effective area, and the core power fraction integrated and in closed form."""
    e = lambda r: field(0, u, w, r)
    de = lambda r: np.where(r <= radius, -u / radius * special.jv(1, u * r / radius) / special.jv(0, u),
                            -w / radius * special.kve(1, w * r / radius) / special.kve(0, w) * np.exp(-w * (r / radius - 1)))
    def total(f):
        return integrate.quad(f, 0, radius, epsabs=0, epsrel=1e-12, limit=200)[0] + \
               integrate.quad(f, radius, np.inf, epsabs=0, epsrel=1e-12, limit=400)[0]
    power = total(lambda r: e(r) ** 2 * r)
    gradient = total(lambda r: de(r) ** 2 * r)
    fourth = total(lambda r: e(r) ** 4 * r)
    core = integrate.quad(lambda r: e(r) ** 2 * r, 0, radius, epsabs=0, epsrel=1e-12, limit=200)[0]
    k0, k1 = special.kve(0, w), special.kve(1, w)
    closed = 1 - (u * u / (u * u + w * w)) * (1 - k0 * k0 / (k1 * k1))   # K_{-1} = K_1
    return {'mfd_um': 2 * math.sqrt(2 * power / gradient), 'aeff_um2': 2 * math.pi * power ** 2 / fourth,
            'confinement': core / power, 'confinement_closed_form': closed}


solutions = [solve(wavelength / 1000, bool(p['vector'])) for wavelength in wavelengths]
lp_labels = sorted({label for s in solutions for label in s['lp']}, key=lambda label: -max(s['lp'].get(label, 0) for s in solutions))
vector_labels = sorted({label for s in solutions for label in s['vector']}, key=lambda label: -max(s['vector'].get(label, 0) for s in solutions))
lp_neff = np.array([[s['lp'].get(label, np.nan) for s in solutions] for label in lp_labels])
vector_neff = np.array([[s['vector'].get(label, np.nan) for s in solutions] for label in vector_labels]) if vector_labels else None

# The fundamental mode: derivatives from solutions at neighbouring wavelengths, so the material dispersion is included.
rows = []
for wavelength, solution in zip(wavelengths, solutions):
    lam = wavelength / 1000
    step = lam * 2e-3
    values = [fundamental(lam - step), fundamental(lam), fundamental(lam + step)]
    first = (values[2] - values[0]) / (2 * step)                       # 1/um
    second = (values[2] - 2 * values[1] + values[0]) / step ** 2        # 1/um^2
    dispersion = -lam * second * 1e12 / C                               # ps/(nm km)
    u = solution['u']['LP01'][1]
    properties = lp01_properties(u, math.sqrt(max(solution['V'] ** 2 - u * u, 0.0)))
    rows.append({'neff': values[1], 'group_index': values[1] - lam * first, 'dispersion_ps_per_nm_km': dispersion,
                 'beta2_ps2_per_km': -lam ** 2 * dispersion * 1e9 / (2 * math.pi * C), **properties,
                 'gamma_per_W_km': 2 * math.pi * float(p['n2_m2_per_W']) / (lam * properties['aeff_um2']) * 1e21})


def cutoff():
    """The wavelength in nm below which LP11 is guided: V = j01."""
    j01 = special.jn_zeros(0, 1)[0]
    def excess(lam):
        n1, n2 = indices(lam)
        return 2 * math.pi / lam * radius * math.sqrt(n1 * n1 - n2 * n2) - j01
    middle = float(np.median(wavelengths)) / 1000
    guess = middle * (excess(middle) + j01) / j01
    try:
        return 1000 * optimize.brentq(excess, guess / 1.5, guess * 1.5, xtol=1e-12)
    except ValueError:   # outside the range of a material page
        return None


dispersion = np.array([row['dispersion_ps_per_nm_km'] for row in rows])
zero_dispersion = [float(wavelengths[i] - dispersion[i] * (wavelengths[i + 1] - wavelengths[i]) / (dispersion[i + 1] - dispersion[i]))
                   for i in range(len(rows) - 1) if dispersion[i] == 0 or dispersion[i] * dispersion[i + 1] < 0]


def partner(label):
    """The LP mode a vector mode tends to in weak guidance."""
    kind, rest = label[:2], label[2:]
    order, m = (int(part) for part in rest.split(',')) if ',' in rest else (int(rest[0]), int(rest[1:]))
    return name('LP', 1 if kind in ('TE', 'TM') else order - 1 if kind == 'HE' else order + 1, m)


difference = None
if vector_neff is not None:
    gaps = []
    for label, row in zip(vector_labels, vector_neff):
        if partner(label) in lp_labels:
            scalar = lp_neff[lp_labels.index(partner(label))]
            contrast = np.array([s['n1'] - s['n2'] for s in solutions])
            both = np.isfinite(row) & np.isfinite(scalar)
            gaps.extend(np.abs(row[both] - scalar[both]) / contrast[both])
    difference = float(max(gaps)) if gaps else None

# Radial LP fields at the first wavelength, each scaled to a largest magnitude of 1.
first = solutions[0]
r = np.linspace(0, 3 * radius, 301)
profile_labels = [label for label in lp_labels if label in first['lp']]
profiles = []
for label in profile_labels:
    order, u = first['u'][label]
    values = field(order, u, math.sqrt(max(first['V'] ** 2 - u * u, 0.0)), r)
    profiles.append(values / np.max(np.abs(values)))
profile_file = data.save(OUTPUT_DIR / 'profiles', {
    'field': data.quantity(np.array(profiles), 'LP mode field E(r), times cos(l phi) or sin(l phi)', unit='1',
                           axes=[{'name': 'mode', 'labels': profile_labels}, 'r_um'], normalization='largest magnitude = 1',
                           wavelength_nm=float(wavelengths[0])),
    'r_um': data.quantity(r, 'radial distance from the fiber axis', unit='um', core_radius_um=radius),
})

wavelength_axis = 'wavelength_nm'
arrays = {
    'wavelength_nm': data.quantity(wavelengths, 'vacuum wavelength', unit='nm'),
    'V': data.quantity([s['V'] for s in solutions], 'normalized frequency k0 a sqrt(n1^2 - n2^2)', unit='1', axes=[wavelength_axis]),
    'lp_neff': data.quantity(lp_neff, 'effective index of each LP mode, NaN where it is not guided', unit='1',
                             axes=[{'name': 'mode', 'labels': lp_labels}, wavelength_axis]),
}
if vector_neff is not None:
    arrays['vector_neff'] = data.quantity(vector_neff, 'effective index of each vector mode, NaN where it is not guided', unit='1',
                                          axes=[{'name': 'mode', 'labels': vector_labels}, wavelength_axis])
fundamental_name = 'HE11' if p['vector'] else 'LP01'
for key, (name, unit) in {'neff': ('effective index', '1'), 'group_index': ('group index', '1'),
                          'dispersion_ps_per_nm_km': ('chromatic dispersion D', 'ps/(nm km)'), 'beta2_ps2_per_km': ('group velocity dispersion beta2', 'ps^2/km'),
                          'mfd_um': ('mode field diameter, Petermann II, of LP01', 'um'), 'aeff_um2': ('effective area of LP01', 'um^2'),
                          'gamma_per_W_km': ('nonlinear coefficient gamma', '1/(W km)')}.items():
    arrays['fundamental_' + key] = data.quantity([row[key] for row in rows], name + ('' if 'LP01' in name else ' of ' + fundamental_name),
                                                 unit=unit, axes=[wavelength_axis])
saved = data.save(OUTPUT_DIR / 'modes', arrays)


def listing(position):
    """The guided modes at one wavelength, at most 12 of each kind by effective index; the arrays hold all."""
    solution = solutions[position]
    def first(modes):
        return dict(sorted(modes.items(), key=lambda item: -item[1])[:12])
    # Polarizations and orientations: LP0m twice, LPlm four times.
    return {'wavelength_nm': float(wavelengths[position]), 'V': solution['V'], 'lp_modes': len(solution['lp']), 'lp': first(solution['lp']),
            **({'vector_modes': len(solution['vector']), 'vector': first(solution['vector'])} if p['vector'] else {}),
            'guided_modes': sum(2 if label.startswith('LP0') else 4 for label in solution['lp'])}


middle = len(rows) // 2
ends = [listing(0), listing(-1)]
lp11 = cutoff()
RESULT = {
    'data': saved['data'], 'files': [profile_file['data']],
    'first': ends[0], 'last': ends[1],
    'lp11_cutoff_nm': lp11, 'single_mode': bool(all(len(s['lp']) == 1 for s in solutions)),
    'fundamental': {'mode': fundamental_name, 'wavelength_nm': float(wavelengths[middle]),
                    **{key: rows[middle][key] for key in ('neff', 'group_index', 'dispersion_ps_per_nm_km', 'beta2_ps2_per_km',
                                                           'mfd_um', 'aeff_um2', 'gamma_per_W_km')}},
    'zero_dispersion_nm': zero_dispersion,
    'materials': pages,
    'checks': {'confinement_difference': float(max(abs(row['confinement'] - row['confinement_closed_form']) for row in rows)),
               'vector_lp_difference': difference},
}
