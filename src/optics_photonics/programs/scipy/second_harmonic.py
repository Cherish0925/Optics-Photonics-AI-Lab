"""Second-harmonic generation in a uniaxial crystal: phase matching, walk-off, acceptance and conversion along the crystal.

A fundamental of vacuum wavelength lambda generates its second harmonic at
lambda/2. In a uniaxial crystal with ordinary index n_o and extraordinary
index n_e (numbers or materials), an extraordinary wave at angle theta to the
optic axis has 1/n(theta)^2 = cos^2(theta)/n_o^2 + sin^2(theta)/n_e^2.
Birefringent phase matching finds theta where delta k = 2 k(omega) - k(2 omega)
vanishes: type I mixes two fundamental waves of one polarization (ooe in a
negative crystal, n_e < n_o; eeo in a positive one), type II an ordinary and
an extraordinary one (eoe; oeo). Quasi-phase matching (all waves
extraordinary along theta = 90 degrees) reverses the nonlinearity with the
period Lambda = m lambda / (2 (n_e(lambda/2) - n_e(lambda))) of order m. For
the chosen interaction the program reports the angle or the period, the
walk-off angle of the extraordinary harmonic, and the full widths at half
maximum of the sinc^2(delta k L / 2) tuning curves in internal angle and in
fundamental wavelength for the crystal length L. For type I and quasi-phase
matching it integrates the plane-wave coupled-amplitude equations of the
fundamental and harmonic fields (Boyd, Nonlinear Optics, section 2.7) along
the crystal with the effective coefficient d_eff, which gives the conversion
efficiency with pump depletion; for quasi-phase matching d_eff already holds
the factor 2 / (m pi) of the order (about 14 pm/V for first-order periodically
poled lithium niobate). The checks compare the integration with tanh^2(sqrt
eta0) at delta k = 0 and, at low intensity and delta k L = 2 pi / 3, with
eta0 sinc^2(delta k L / 2), where eta0 = 8 pi^2 d_eff^2 L^2 I / (eps0 c
n(omega)^2 n(2 omega) lambda^2) is the undepleted efficiency. Biaxial
crystals use their principal-plane indices as the two indices of a uniaxial
crystal.
"""
import math
import numpy as np
from scipy import integrate, optimize
from optics_photonics import data, materials
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'fundamental_nm': (1064, 'vacuum wavelength of the fundamental in nm'),
        'ordinary_index': ('BBO-o', 'ordinary index n_o: number, [n, k] or material (beta barium borate by default)'),
        'extraordinary_index': ('BBO-e', 'extraordinary index n_e: number, [n, k] or material'),
        'interaction': ('type I', 'type I, type II or quasi (quasi-phase matching with all waves extraordinary)'),
        'length_mm': (5.0, 'crystal length in mm'),
        'intensity_MW_per_cm2': (100.0, 'fundamental intensity of the plane wave in MW/cm^2'),
        'd_eff_pm_per_V': (2.0, 'effective nonlinear coefficient in pm/V; for quasi-phase matching including 2 / (m pi)'),
        'angle_detuning_mrad': (0.0, 'internal angle from phase matching for the conversion along the crystal (type I)'),
        'qpm_order': (1, 'order m of quasi-phase matching'),
        'period_um': (None, 'poling period in um for quasi-phase matching; null takes the phase-matched period'),
        'points': (401, 'samples along the crystal and on each tuning curve'),
    },
    'results': 'shg.npz/.json: efficiency along the crystal, and normalized efficiency over angle and wavelength detuning; '
               'phase-matching angle or period, walk-off, acceptance bandwidths, the efficiency at the crystal end and eta0',
    'checks': 'depletion_difference: integrated efficiency at delta k = 0 minus tanh^2(sqrt(eta0)); '
              'undepleted_difference: low-intensity efficiency over eta0 sinc^2(delta k L / 2) minus 1',
}
p = parameters(PROGRAM, INPUTS)
lam, length = float(p['fundamental_nm']) / 1000, float(p['length_mm']) * 1e3        # um
interaction = str(p['interaction']).lower().replace('-', ' ').replace('_', ' ').strip()
if interaction not in ('type i', 'type ii', 'quasi'):
    raise ValueError('interaction is type I, type II or quasi')
if lam <= 0 or length <= 0 or float(p['intensity_MW_per_cm2']) < 0 or int(p['points']) < 21:
    raise ValueError('fundamental_nm and length_mm are positive, intensity_MW_per_cm2 is not negative and points is at least 21')
pages = {}
EPS0, C = 8.8541878128e-12, 299792458.0
HALF = 1.3915573782515103   # sinc^2(x) = 1/2 at x = 1.39156


def index(entry, wavelength_um):
    if isinstance(entry, str):
        pages[entry] = materials.resolve(entry)
        return materials.index_at(entry, wavelength_um).real
    return float(entry[0]) if isinstance(entry, (list, tuple)) else float(entry)


def principal(wavelength_um):
    return index(p['ordinary_index'], wavelength_um), index(p['extraordinary_index'], wavelength_um)


def angled(no, ne, theta):
    """Index of an extraordinary wave at angle theta to the optic axis."""
    return 1 / math.sqrt(math.cos(theta) ** 2 / no ** 2 + math.sin(theta) ** 2 / ne ** 2)


no1, ne1 = principal(lam)
negative = ne1 < no1


def indices(theta, wavelength_um):
    """Effective fundamental index (mean of the two fundamental waves) and harmonic index at theta."""
    no1, ne1 = principal(wavelength_um)
    no2, ne2 = principal(wavelength_um / 2)
    if interaction == 'quasi':
        return ne1, ne2
    if interaction == 'type i':
        return (no1, angled(no2, ne2, theta)) if negative else (angled(no1, ne1, theta), no2)
    return ((angled(no1, ne1, theta) + no1) / 2, angled(no2, ne2, theta)) if negative else \
           ((no1 + angled(no1, ne1, theta)) / 2, no2)


def mismatch(theta, wavelength_um, period=None):
    """delta k = 2 k(omega) - k(2 omega), plus the grating vector of quasi-phase matching, in 1/um."""
    fundamental, harmonic = indices(theta, wavelength_um)
    value = 4 * math.pi / wavelength_um * (fundamental - harmonic)
    return value + (2 * math.pi * int(p['qpm_order']) / period if period else 0.0)


# Phase matching: the angle, or for quasi-phase matching the period.
if interaction == 'quasi':
    theta, ne2 = math.pi / 2, principal(lam / 2)[1]
    design = int(p['qpm_order']) * lam / (2 * (ne2 - ne1))
    if design <= 0:
        raise ValueError('n_e(lambda/2) does not exceed n_e(lambda); no forward quasi-phase matching')
    period = float(p['period_um']) if p['period_um'] else design
else:
    period, design = None, None
    ends = (mismatch(0.0, lam), mismatch(math.pi / 2, lam))
    if ends[0] * ends[1] > 0:
        raise ValueError(f'No {p["interaction"]} phase matching for {lam * 1000:g} nm in this crystal: delta k has one sign from 0 to 90 degrees')
    theta = optimize.brentq(lambda angle: mismatch(angle, lam), 0.0, math.pi / 2, xtol=1e-15)

# Walk-off of the extraordinary harmonic (type I in a negative crystal, type II) or fundamental (type I, positive).
no2, ne2 = principal(lam / 2)
if interaction == 'quasi':
    walkoff = 0.0
else:
    no, ne = (no2, ne2) if negative else (no1, ne1)
    n = angled(no, ne, theta)
    walkoff = math.atan(0.5 * n * n * (1 / ne ** 2 - 1 / no ** 2) * math.sin(2 * theta))


def acceptance(function, limit):
    """Full width at half maximum of sinc^2(delta k L / 2) about phase matching, where function(x) is delta k at
    detuning x; None when it is wider than 2 limit or reaches beyond the range of a material page."""
    widths = []
    try:
        for sign in (1, -1):
            step = limit * 1e-6
            while abs(function(sign * step)) * length / 2 < HALF:
                step *= 2
                if step > limit:
                    return None
            widths.append(optimize.brentq(lambda x: abs(function(sign * x)) * length / 2 - HALF, 0.0, step, xtol=1e-13 * step))
    except ValueError:
        return None
    return sum(widths)


# Tuning of the phase-matched crystal (the design period for quasi-phase matching): internal angle in mrad, wavelength in nm.
tunings = {'wavelength': (lambda x: mismatch(theta, lam + x * 1e-3, design), lam * 250, 'nm', 'fundamental wavelength minus its design value')}
if interaction != 'quasi':
    tunings['angle'] = (lambda x: mismatch(theta + x * 1e-3, lam), 500.0, 'mrad', 'internal angle minus the phase-matching angle')
widths = {name: acceptance(function, limit) for name, (function, limit, _, _) in tunings.items()}

# Conversion along the crystal: normalized amplitudes b1, b2 of the fundamental and harmonic, |b2|^2 = I(2 omega) / I(omega, 0).
n1, n2 = indices(theta, lam)


def coupling(intensity_MW_per_cm2):
    """g in 1/um: d b1/dz = i g b2 b1* exp(-i dk z), d b2/dz = i g b1^2 exp(i dk z); eta0 = (g L)^2."""
    omega = 2 * math.pi * C / (lam * 1e-6)
    intensity = intensity_MW_per_cm2 * 1e10                                   # W/m^2
    g = 2 * omega * float(p['d_eff_pm_per_V']) * 1e-12 / (C * n1 * math.sqrt(n2)) * math.sqrt(intensity / (2 * EPS0 * C))
    return g * 1e-6


def convert(g, dk, z):
    def rates(position, b):
        b1, b2 = b
        return [1j * g * b2 * np.conj(b1) * np.exp(-1j * dk * position), 1j * g * b1 * b1 * np.exp(1j * dk * position)]
    solution = integrate.solve_ivp(rates, (0.0, z[-1]), [1 + 0j, 0j], t_eval=z, method='DOP853', rtol=1e-11, atol=1e-13)
    return np.abs(solution.y[1]) ** 2, np.abs(solution.y[0]) ** 2


points = int(p['points'])
z = np.linspace(0.0, length, points)
g = coupling(float(p['intensity_MW_per_cm2']))
eta0 = (g * length) ** 2
detuned = mismatch(theta + float(p['angle_detuning_mrad']) * 1e-3, lam) if interaction != 'quasi' else mismatch(theta, lam, period)
efficiency = None
if interaction != 'type ii':
    efficiency, remaining = convert(g, detuned, z)
    matched, _ = convert(g, 0.0, z)
    depletion_difference = float(matched[-1] - math.tanh(g * length) ** 2)
    weak, dk = 1e-4 / length, 2 * math.pi / 3 / length   # (weak L)^2 = 1e-8: no depletion
    low, _ = convert(weak, dk, z)
    undepleted_difference = float(low[-1] / ((weak * length) ** 2 * (math.sin(dk * length / 2) / (dk * length / 2)) ** 2) - 1)
else:
    depletion_difference = undepleted_difference = None

# Tuning curves in the low-conversion limit, sinc^2 normalized to 1 at phase matching.
def sinc2(dk):
    x = np.asarray(dk) * length / 2
    return np.sinc(x / np.pi) ** 2


arrays = {'z_mm': data.quantity(z / 1e3, 'position along the crystal', unit='mm')}
if efficiency is not None:
    arrays['efficiency'] = data.quantity(efficiency, 'second-harmonic intensity over the incident fundamental intensity', unit='1',
                                         axes=['z_mm'], delta_k_per_um=detuned)
    arrays['fundamental'] = data.quantity(remaining, 'fundamental intensity over its incident value', unit='1', axes=['z_mm'])
for name, (function, _, unit, about) in tunings.items():
    if widths[name] is None:
        continue
    detuning = np.linspace(-3 * widths[name], 3 * widths[name], points)
    try:
        curve = sinc2([function(x) for x in detuning])
    except ValueError:   # beyond the range of a material page
        continue
    arrays[f'{name}_detuning_{unit}'] = data.quantity(detuning, about, unit=unit)
    arrays[f'{name}_tuning'] = data.quantity(curve, 'low-conversion efficiency relative to phase matching', unit='1',
                                             axes=[f'{name}_detuning_{unit}'])
saved = data.save(OUTPUT_DIR / 'shg', arrays)

centimetres = length / 1e4
RESULT = {
    'data': saved['data'], 'interaction': p['interaction'], 'crystal': 'negative uniaxial' if negative else 'positive uniaxial',
    'indices': {'fundamental': n1, 'harmonic': n2, 'n_o': [no1, no2], 'n_e': [ne1, ne2]},
    **({'angle_deg': math.degrees(theta)} if interaction != 'quasi' else {'period_um': period, 'phase_matched_period_um': design}),
    'walkoff_mrad': walkoff * 1e3,
    'acceptance': {**{f'{name}_{unit}': widths[name] for name, (_, _, unit, _) in tunings.items()},
                   **{f'{name}_{unit}_cm': widths[name] * centimetres if widths[name] else None for name, (_, _, unit, _) in tunings.items()}},
    'eta0': eta0 if interaction != 'type ii' else None,
    'efficiency': float(efficiency[-1]) if efficiency is not None else None,
    'materials': pages,
    'checks': {'depletion_difference': depletion_difference, 'undepleted_difference': undepleted_difference},
}
