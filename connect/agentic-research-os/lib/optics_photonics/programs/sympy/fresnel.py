"""Fresnel coefficients derived from the boundary conditions at a planar interface.

SymPy solves the continuity of the tangential electric and magnetic fields
for a plane wave from medium n1 onto medium n2 (z = 0 interface, plane of
incidence xz, Snell's law n1 sin(ti) = n2 sin(tt)). s: the electric field is
along y for all three waves. p: the magnetic field is along y for all three
waves, and r_p and t_p are ratios of that magnetic field, which makes
r_p = (n2 - n1)/(n2 + n1) = -r_s at normal incidence; t_p is converted to the
electric field. Power coefficients use R = |r|^2 and
T = (n2 cos tt)/(n1 cos ti) |t_E|^2. The Brewster angle, where r_p = 0, is
verified symbolically to be atan(n2/n1).
"""
import math
import sympy as sp
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'n1': (1.0, 'index of the incident medium'),
        'n2': (1.5, 'index of the second medium'),
        'angle_deg': (30.0, 'angle of incidence in degrees at which the coefficients are evaluated'),
    },
    'results': 'r_s, t_s, r_p, t_p as SymPy and LaTeX expressions; their values, R and T at the angle; Brewster and critical angles',
    'checks': 'energy errors |R + T - 1| for s and p; brewster_identity: r_p simplifies to 0 at atan(n2/n1)',
}
p = parameters(PROGRAM, INPUTS)
n1, n2 = sp.symbols('n1 n2', positive=True)
ti = sp.symbols('theta_i', real=True)
ci = sp.cos(ti)
ct = sp.sqrt(1 - (n1 / n2) ** 2 * sp.sin(ti) ** 2)                # cos of the transmission angle
r, t = sp.symbols('r t')
# s: E_y continuous; H_x proportional to -n cos(theta) E_y continuous.
s_solution = sp.solve([sp.Eq(1 + r, t), sp.Eq(n1 * ci * (1 - r), n2 * ct * t)], [r, t], dict=True)[0]
# p: H_y continuous; E_x proportional to cos(theta) H_y / n continuous.
p_solution = sp.solve([sp.Eq(1 + r, t), sp.Eq(ci / n1 * (1 - r), ct / n2 * t)], [r, t], dict=True)[0]
rs, ts = sp.simplify(s_solution[r]), sp.simplify(s_solution[t])
rp, tp_h = sp.simplify(p_solution[r]), sp.simplify(p_solution[t])
tp = sp.simplify(n1 / n2 * tp_h)                                   # electric-field transmission
brewster = sp.atan(n2 / n1)
identity = sp.simplify(rp.subs(ti, brewster)) == 0

values = {n1: float(p['n1']), n2: float(p['n2']), ti: math.radians(float(p['angle_deg']))}
if values[n1] <= 0 or values[n2] <= 0 or not 0 <= values[ti] < math.pi / 2:
    raise ValueError('n1 and n2 are positive and angle_deg lies in [0, 90)')
numbers = {name: complex(sp.N(expr.subs(values))) for name, expr in (('r_s', rs), ('t_s', ts), ('r_p', rp), ('t_p', tp))}
ratio = complex(sp.N((n2 * ct / (n1 * ci)).subs(values)))
total = values[n1] > values[n2] and values[n1] * math.sin(values[ti]) >= values[n2]
power = {'R_s': abs(numbers['r_s']) ** 2, 'R_p': abs(numbers['r_p']) ** 2,
         'T_s': 0.0 if total else (ratio * abs(numbers['t_s']) ** 2).real,
         'T_p': 0.0 if total else (ratio * abs(numbers['t_p']) ** 2).real}
critical = math.degrees(math.asin(values[n2] / values[n1])) if values[n1] > values[n2] else None
RESULT = {'expressions': {'r_s': str(rs), 't_s': str(ts), 'r_p': str(rp), 't_p': str(tp)},
          'latex': {'r_s': sp.latex(rs), 't_s': sp.latex(ts), 'r_p': sp.latex(rp), 't_p': sp.latex(tp)},
          'values': {key: [value.real, value.imag] for key, value in numbers.items()}, 'power': power,
          'total_internal_reflection': total, 'brewster_deg': math.degrees(math.atan(values[n2] / values[n1])), 'critical_deg': critical,
          'checks': {'energy_error_s': abs(power['R_s'] + power['T_s'] - 1), 'energy_error_p': abs(power['R_p'] + power['T_p'] - 1),
                     'brewster_identity': bool(identity)}}
