"""Single-mode semiconductor laser: light-current curve and modulation dynamics from rate equations.

Carrier density N and photon density S obey
dN/dt = eta_i I/(q V) - N/tau_n - vg a (N - Ntr) S/(1 + eps S),
dS/dt = Gamma vg a (N - Ntr) S/(1 + eps S) - S/tau_p + Gamma beta_sp N/tau_n,
with linear gain of differential gain a. Output power is
P = eta_o h nu V S/(Gamma tau_p). Without spontaneous emission and gain
compression the threshold current is q V (Ntr + 1/(Gamma vg a tau_p))/(eta_i tau_n),
the slope efficiency eta_i eta_o h nu/q, the relaxation oscillation
frequency sqrt(vg a S0/tau_p)/(2 pi) at photon density S0, its damping
1/tau_n + vg a S0 and the ringing frequency of a step response; these are
reported beside the numerical results. The step response starts from the steady state
at the first current of current_step_mA.
"""
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'volume_um3': (150.0, 'active volume V in cubic micrometres'),
        'confinement': (0.2, 'optical confinement factor Gamma'),
        'differential_gain_cm2': (2.5e-16, 'differential gain a in cm^2'),
        'transparency_cm3': (1.5e18, 'transparency carrier density Ntr in cm^-3'),
        'carrier_lifetime_ns': (2.0, 'carrier lifetime tau_n in ns'),
        'photon_lifetime_ps': (2.0, 'photon lifetime tau_p in ps'),
        'group_index': (3.6, 'group index'),
        'injection_efficiency': (0.8, 'eta_i'),
        'output_efficiency': (0.5, 'eta_o: mirror loss over total loss'),
        'gain_compression_cm3': (0.0, 'gain compression eps in cm^3'),
        'spontaneous_factor': (1e-4, 'beta_sp, fraction of spontaneous emission into the mode'),
        'wavelength_um': (1.55, 'emission wavelength in micrometres'),
        'currents_mA': ({'start': 0, 'stop': 120, 'points': 121}, 'currents of the light-current curve in mA'),
        'current_step_mA': ([75, 80], 'current before and after the step in mA; small-signal theory holds for small steps'),
        'duration_ns': (3.0, 'duration of the step response in ns'),
    },
    'results': 'light_current.npz/.json; step.npz/.json with power and carrier density over time; thresholds, slope and relaxation frequency',
    'checks': 'threshold_error and slope_error against the analytic values; ringing_frequency_error of the step response at the final current',
}
p = parameters(PROGRAM, INPUTS)
q, h, c = 1.602176634e-19, 6.62607015e-34, 299792458.0
V = float(p['volume_um3']) * 1e-18
gamma_c, a = float(p['confinement']), float(p['differential_gain_cm2']) * 1e-4
Ntr, tau_n, tau_p = float(p['transparency_cm3']) * 1e6, float(p['carrier_lifetime_ns']) * 1e-9, float(p['photon_lifetime_ps']) * 1e-12
vg, eta_i, eta_o = c / float(p['group_index']), float(p['injection_efficiency']), float(p['output_efficiency'])
eps, beta = float(p['gain_compression_cm3']) * 1e-6, float(p['spontaneous_factor'])
photon = h * c / (float(p['wavelength_um']) * 1e-6)
if min(V, gamma_c, a, Ntr, tau_n, tau_p, vg, eta_i, eta_o) <= 0 or eps < 0 or beta < 0:
    raise ValueError('Physical parameters are positive; gain compression and spontaneous factor are nonnegative')


def rates(t, y, current):
    N, S = y
    gain = vg * a * (N - Ntr) / (1 + eps * S)
    return [eta_i * current / (q * V) - N / tau_n - gain * S, gamma_c * gain * S - S / tau_p + gamma_c * beta * N / tau_n]


def steady(current):
    """Photon density on the stable branch: eliminate N and solve dS/dt = 0 for S >= 0."""
    def carriers(S):  # from dN/dt = 0 at photon density S
        return (eta_i * current / (q * V) + vg * a * Ntr * S / (1 + eps * S)) / (1 / tau_n + vg * a * S / (1 + eps * S))
    def balance(S):
        return rates(0, [carriers(S), S], current)[1]
    # Without spontaneous emission S = 0 is always a solution; the lasing root lies above it.
    low, high = (0.0 if beta > 0 else 1.0), 1e18
    if balance(low) <= 0:
        return carriers(0.0), 0.0
    while balance(high) > 0:
        high *= 10
    S = brentq(balance, low, high, xtol=1e-30, rtol=1e-14)
    return carriers(S), S


grid = p['currents_mA']
currents = (np.linspace(float(grid['start']), float(grid['stop']), int(grid['points'])) if isinstance(grid, dict)
            else np.asarray(grid, dtype=float)) * 1e-3
states = np.array([steady(i) for i in currents])
power = eta_o * photon * V * states[:, 1] / (gamma_c * tau_p)
threshold = q * V * (Ntr + 1 / (gamma_c * vg * a * tau_p)) / (eta_i * tau_n)
slope = eta_i * eta_o * photon / q
above = (currents > 1.5 * threshold) & (power > 0)
numeric_threshold = numeric_slope = None
if above.sum() >= 2:
    fit = np.polyfit(currents[above], power[above], 1)
    numeric_slope, numeric_threshold = float(fit[0]), float(-fit[1] / fit[0])

before, after = (float(v) * 1e-3 for v in p['current_step_mA'])
duration = float(p['duration_ns']) * 1e-9
times = np.linspace(0, duration, 3001)
solution = solve_ivp(rates, (0, duration), list(steady(before)), args=(after,), t_eval=times, method='LSODA', rtol=1e-9, atol=[1e10, 1e6])
step_power = eta_o * photon * V * solution.y[1] / (gamma_c * tau_p)
final_S = steady(after)[1]
# Linearized equations (eps = beta = 0): w_R^2 = vg a S0/tau_p, damping 1/tau_n + vg a S0, ringing at sqrt(w_R^2 - damping^2/4).
w_r2, damping = vg * a * final_S / tau_p, 1 / tau_n + vg * a * final_S
analytic_frequency = np.sqrt(w_r2) / (2 * np.pi) if final_S > 0 else None
ringing = np.sqrt(w_r2 - damping ** 2 / 4) / (2 * np.pi) if final_S > 0 and w_r2 > damping ** 2 / 4 else None
peaks = [i for i in range(1, len(step_power) - 1) if step_power[i] > step_power[i - 1] and step_power[i] >= step_power[i + 1]]
numeric_frequency = float(1 / np.mean(np.diff(times[peaks[:4]]))) if len(peaks) >= 3 else None

data.save(OUTPUT_DIR / 'light_current', {
    'power_mW': data.quantity(power * 1e3, 'output power', unit='mW', axes=['current_mA']),
    'carrier_density_cm3': data.quantity(states[:, 0] * 1e-6, 'carrier density', unit='cm^-3', axes=['current_mA']),
    'current_mA': data.quantity(currents * 1e3, 'injection current', unit='mA'),
})
data.save(OUTPUT_DIR / 'step', {
    'power_mW': data.quantity(step_power * 1e3, 'output power', unit='mW', axes=['time_ns']),
    'carrier_density_cm3': data.quantity(solution.y[0] * 1e-6, 'carrier density', unit='cm^-3', axes=['time_ns']),
    'time_ns': data.quantity(times * 1e9, 'time after the current step', unit='ns'),
})
analytic_ghz = None if analytic_frequency is None else float(analytic_frequency / 1e9)
ringing_ghz = None if ringing is None else float(ringing / 1e9)
numeric_ghz = None if numeric_frequency is None else numeric_frequency / 1e9
RESULT = {'threshold_mA': threshold * 1e3, 'numeric_threshold_mA': None if numeric_threshold is None else numeric_threshold * 1e3,
          'slope_W_per_A': slope, 'numeric_slope_W_per_A': numeric_slope, 'relaxation_frequency_GHz': analytic_ghz,
          'damped_frequency_GHz': ringing_ghz, 'damping_rate_per_ns': float(damping * 1e-9),
          'numeric_ringing_frequency_GHz': numeric_ghz, 'data': ['light_current.npz', 'step.npz'],
          'checks': {'threshold_error': None if numeric_threshold is None else abs(numeric_threshold / threshold - 1),
                     'slope_error': None if numeric_slope is None else abs(numeric_slope / slope - 1),
                     'ringing_frequency_error': None if not (ringing_ghz and numeric_ghz) else abs(numeric_ghz / ringing_ghz - 1)}}
