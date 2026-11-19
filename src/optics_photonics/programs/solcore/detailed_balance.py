"""Detailed-balance (Shockley-Queisser) efficiency of a single-junction solar cell (Solcore).

Solcore's detailed-balance junction absorbs every photon above the band gap
(a step absorptance), generates one electron-hole pair per photon, and loses
carriers only by radiative recombination, emitting as a black body above the
gap through its front and back surfaces. Solcore solves the current-voltage
curve with the generalized Planck law and finds its maximum power point.
spectrum is AM1.5g, AM1.5d or AM0 from Solcore's standard spectra, scaled by
concentration. The short-circuit current and the radiative dark current are
also integrated here from the photon flux and Planck's law, which gives the
open-circuit voltage independently, and the efficiency with a back mirror
(emission through the front surface only) is computed for comparison. Band
gaps are in eV and currents in A/m^2. These are ideal limits for one
junction; real cells add non-radiative recombination, reflection and
resistance.
"""
import math
import numpy as np
from solcore.light_source import LightSource
from solcore.solar_cell import SolarCell
from solcore.solar_cell_solver import solar_cell_solver
from solcore.structure import Junction
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'band_gap_ev': ({'start': 0.8, 'stop': 2.2, 'points': 29}, 'band gaps in eV: list or {"start", "stop", "points"}'),
        'spectrum': ('AM1.5g', 'AM1.5g, AM1.5d or AM0'),
        'concentration': (1.0, 'suns: multiplies the spectrum'),
        'temperature_k': (300.0, 'cell temperature'),
        'wavelength_nm': ({'start': 280, 'stop': 4000, 'points': 3721}, 'wavelength grid of the spectrum'),
    },
    'results': 'cells.npz/.json with efficiency, Voc, Jsc, fill factor, maximum power and the back-mirror efficiency over band gap; the best band gap',
    'checks': 'jsc_difference and voc_difference: largest relative differences from the currents integrated here for emission through both surfaces',
}
p = parameters(PROGRAM, INPUTS)
if p['spectrum'] not in ('AM1.5g', 'AM1.5d', 'AM0'):
    raise ValueError('spectrum is AM1.5g, AM1.5d or AM0')
gaps = p['band_gap_ev']
gaps = np.linspace(gaps['start'], gaps['stop'], int(gaps['points'])) if isinstance(gaps, dict) else np.atleast_1d(np.asarray(gaps, float))
grid = p['wavelength_nm']
wl = np.linspace(grid['start'], grid['stop'], int(grid['points'])) * 1e-9
T, suns = float(p['temperature_k']), float(p['concentration'])
q, h, c, k = 1.602176634e-19, 6.62607015e-34, 299792458.0, 1.380649e-23
light = LightSource(source_type='standard', version=p['spectrum'], x=wl, output_units='photon_flux_per_m', concentration=suns)
flux = light.spectrum(wl)[1]                       # photons / (s m^2 m)
power = float(np.trapezoid(flux * h * c / wl, wl))  # incident irradiance in W/m^2
voltages = np.linspace(0, float(gaps.max()) + 0.2, 2401)
rows, jsc_difference, voc_difference = [], 0.0, 0.0
for gap in gaps:
    junction = Junction(kind='DB', T=T, Eg=float(gap), A=1, R_shunt=np.inf, n=1)
    cell = SolarCell([junction], T=T)
    solar_cell_solver(cell, 'iv', user_options={'T_ambient': T, 'db_mode': 'top_hat', 'voltages': voltages, 'internal_voltages': voltages,
                                                 'light_iv': True, 'wavelength': wl, 'mpp': True, 'light_source': light})
    iv = cell.iv
    # Independent integrals: absorbed photon current and radiative dark current from Planck's law.
    above = wl <= h * c / (gap * q)
    jsc = q * float(np.trapezoid(flux[above], wl[above]))
    energy = np.linspace(gap, gap + 40 * k * T / q, 4001) * q
    # Black-body photon flux above the gap into one hemisphere; a slab without a mirror emits through two.
    j0 = q * 2 * math.pi / (h ** 3 * c ** 2) * float(np.trapezoid(energy ** 2 / np.expm1(energy / (k * T)), energy))
    voc = k * T / q * math.log(jsc / (2 * j0) + 1)
    jsc_difference = max(jsc_difference, abs(iv['Isc'] / jsc - 1))
    voc_difference = max(voc_difference, abs(iv['Voc'] / voc - 1))
    v = np.linspace(0, k * T / q * math.log(jsc / j0 + 1), 20001)
    mirror = float(np.max(v * (jsc - j0 * np.expm1(q * v / (k * T))))) / power
    rows.append([float(iv['Eta']), float(iv['Voc']), float(iv['Isc']), float(iv['FF']), float(iv['Pmpp']), mirror])
table = np.asarray(rows)
best = int(np.argmax(table[:, 0]))
axes = ['band_gap_ev']
saved = data.save(OUTPUT_DIR / 'cells', {
    'efficiency': data.quantity(table[:, 0], 'detailed-balance efficiency', unit='1', axes=axes, spectrum=p['spectrum'], concentration=suns,
                                incident_power_w_m2=power),
    'voc': data.quantity(table[:, 1], 'open-circuit voltage', unit='V', axes=axes),
    'jsc': data.quantity(table[:, 2], 'short-circuit current density', unit='A/m^2', axes=axes),
    'fill_factor': data.quantity(table[:, 3], 'fill factor', unit='1', axes=axes),
    'power': data.quantity(table[:, 4], 'maximum power density', unit='W/m^2', axes=axes),
    'efficiency_back_mirror': data.quantity(table[:, 5], 'detailed-balance efficiency with emission through the front surface only',
                                            unit='1', axes=axes),
    'band_gap_ev': data.quantity(gaps, 'band gap', unit='eV'),
})
RESULT = {'data': saved['data'], 'best': {'band_gap_ev': float(gaps[best]), 'efficiency': float(table[best, 0]), 'voc': float(table[best, 1]),
                                          'jsc': float(table[best, 2]), 'fill_factor': float(table[best, 3])},
          'best_back_mirror': {'band_gap_ev': float(gaps[int(np.argmax(table[:, 5]))]), 'efficiency': float(table[:, 5].max())},
          'incident_power_w_m2': power, 'spectrum': p['spectrum'], 'concentration': suns,
          'checks': {'jsc_difference': jsc_difference, 'voc_difference': voc_difference}}
