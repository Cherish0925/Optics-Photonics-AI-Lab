"""On-axis spectrum and central cone of a planar undulator (SRW, single-electron synchrotron radiation).

An electron of energy E = gamma m c^2 crosses N periods of length lambda_u
of a vertical magnetic field of peak B, with the deflection parameter
K = e B lambda_u / (2 pi m c). SRW integrates the radiation field along the
trajectory and gives the spectral flux per unit area at a distance for the
beam current, without the spread of a real beam (zero emittance and energy
spread). On the axis the spectrum has odd harmonics n at
E_n = n 2 gamma^2 h c / (lambda_u (1 + K^2 / 2)), each of relative width
about 1 / (n N), with the peak angular flux density
1.744e14 N^2 E[GeV]^2 I[A] F_n(K) photons/s/mrad^2/0.1% bandwidth,
F_n = (n K / (1 + K^2/2))^2 (J_(n-1)/2(Z) - J_(n+1)/2(Z))^2,
Z = n K^2 / (4 + 2 K^2) (Kim, AIP Conf. Proc. 184, 565 (1989)). The
program compares the fundamental with both formulas, valid for many periods
and a distant observer: the peak lies below E_1 by a fraction of the width,
and SRW's field includes the end poles, which raise the peak by a few 1/N.
It saves the flux density across the central cone at the fundamental.
"""
from array import array
import numpy as np
from scipy.special import jv
from srwpy import srwlib
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'period_mm': (20.0, 'undulator period in mm'),
        'periods': (100, 'number of periods'),
        'deflection': (1.2, 'deflection parameter K'),
        'electron_energy_gev': (3.0, 'electron energy in GeV'),
        'current_a': (0.5, 'beam current in A'),
        'distance_m': (30.0, 'distance from the undulator centre to the observation plane, in m'),
        'harmonics': (3, 'the spectrum reaches half a fundamental beyond this harmonic'),
        'points': (3001, 'photon energies of the spectrum'),
        'cone_points': (61, 'points per side of the map across the central cone; 0 skips it'),
    },
    'results': 'radiation.npz/.json: on-axis flux density over photon energy and across the central cone at the fundamental; '
               'energy and peak flux density of each odd harmonic; the field and K',
    'checks': 'fundamental_difference: relative difference of the spectral peak from the formula of the fundamental; '
              'flux_ratio: peak on-axis flux density over the formula',
}
p = parameters(PROGRAM, INPUTS)
period, periods, K = float(p['period_mm']) * 1e-3, int(p['periods']), float(p['deflection'])
energy, current, distance = float(p['electron_energy_gev']), float(p['current_a']), float(p['distance_m'])
if min(period, K, energy, current) <= 0 or periods < 2 or distance <= periods * period or int(p['harmonics']) < 1 or int(p['points']) < 3:
    raise ValueError('period_mm, deflection, electron_energy_gev and current_a are positive, periods >= 2, harmonics >= 1, '
                     'points >= 3 and distance_m exceeds the undulator length')
E_CHARGE, E_MASS, LIGHT, HC_EV_M = 1.602176634e-19, 9.1093837015e-31, 299792458.0, 1.239841984e-6
field = K * 2 * np.pi * E_MASS * LIGHT / (E_CHARGE * period)
gamma = energy / 0.51099895e-3
fundamental = 2 * gamma ** 2 * HC_EV_M / (period * (1 + K ** 2 / 2))

undulator = srwlib.SRWLMagFldU([srwlib.SRWLMagFldH(1, 'v', field, 0, 1, 1)], period, periods)
magnet = srwlib.SRWLMagFldC([undulator], array('d', [0]), array('d', [0]), array('d', [0]))
beam = srwlib.SRWLPartBeam()
beam.Iavg = current
beam.partStatMom1.x = beam.partStatMom1.y = beam.partStatMom1.xp = beam.partStatMom1.yp = 0.0
beam.partStatMom1.z = -0.5 * period * (periods + 4)
beam.partStatMom1.gamma = gamma
precision = [1, 0.01, 0, 0, max(20000, 200 * periods), 1, 0]   # undulator method, relative precision, trajectory points


def flux_density(energies, half_width, side):
    """Photons/s/0.1% bandwidth/mm^2 at the observation plane over photon energy (eV), x and y (m)."""
    front = srwlib.SRWLWfr()
    front.allocate(len(energies), side, side)
    front.mesh.zStart = distance
    front.mesh.eStart, front.mesh.eFin = float(energies[0]), float(energies[-1])
    front.mesh.xStart, front.mesh.xFin = -half_width, half_width
    front.mesh.yStart, front.mesh.yFin = -half_width, half_width
    front.partBeam = beam
    srwlib.srwl.CalcElecFieldSR(front, 0, magnet, precision)
    values = array('f', [0] * (len(energies) * side * side))
    kind = 0 if len(energies) > 1 else 3      # against photon energy, or against x and y
    srwlib.srwl.CalcIntFromElecField(values, front, 6, 0, kind, float(energies[0]), 0, 0)
    return np.asarray(values, dtype=float)


energies = np.linspace(0.5 * fundamental, (int(p['harmonics']) + 0.5) * fundamental, int(p['points']))
spectrum = flux_density(energies, 0.0, 1)
found = []
for n in range(1, int(p['harmonics']) + 1, 2):
    near = np.abs(energies - n * fundamental) < 0.25 * fundamental
    at = np.flatnonzero(near)[np.argmax(spectrum[near])]
    left, top, right = spectrum[at - 1:at + 2]
    peak = energies[at] + 0.5 * (left - right) / (left - 2 * top + right) * (energies[1] - energies[0])   # vertex of the parabola
    z = n * K ** 2 / (4 + 2 * K ** 2)
    shape = (n * K / (1 + K ** 2 / 2)) ** 2 * (jv((n - 1) / 2, z) - jv((n + 1) / 2, z)) ** 2
    formula = 1.744e14 * periods ** 2 * energy ** 2 * current * shape / distance ** 2      # mrad^2 to mm^2 at the distance
    found.append({'harmonic': n, 'energy_ev': float(peak), 'formula_ev': n * fundamental,
                  'flux_density': float(spectrum[at]), 'formula_flux_density': float(formula)})

arrays = {
    'flux_density': data.quantity(spectrum, 'on-axis spectral flux density', unit='photons/s/0.1%bw/mm^2', axes=['photon_energy_ev'],
                                  distance_m=distance, current_a=current),
    'photon_energy_ev': data.quantity(energies, 'photon energy', unit='eV'),
}
side = int(p['cone_points'])
cone = None
if side:
    wavelength = HC_EV_M / found[0]['energy_ev']
    cone = float(np.sqrt(wavelength / (2 * periods * period)))            # rms angle of the central cone
    half_width = 4 * cone * distance
    pattern = flux_density(np.asarray([found[0]['energy_ev']]), half_width, side).reshape(side, side)
    position = np.linspace(-half_width, half_width, side) * 1e3
    arrays.update({
        'cone': data.quantity(pattern, 'flux density at the fundamental across the observation plane', unit='photons/s/0.1%bw/mm^2',
                              axes=['y_mm', 'x_mm'], photon_energy_ev=found[0]['energy_ev']),
        'x_mm': data.quantity(position, 'horizontal position', unit='mm'),
        'y_mm': data.quantity(position, 'vertical position', unit='mm'),
    })
saved = data.save(OUTPUT_DIR / 'radiation', arrays)
RESULT = {
    'fundamental_ev': fundamental, 'field_t': float(field), 'gamma': gamma, 'harmonics': found, 'cone_rms_urad': cone and cone * 1e6,
    'data': saved['data'],
    'checks': {'fundamental_difference': found[0]['energy_ev'] / fundamental - 1,
               'flux_ratio': found[0]['flux_density'] / found[0]['formula_flux_density']},
}
