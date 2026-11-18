"""Transmission of photonic circuits composed from waveguide and coupler models (SAX).

SAX joins the S-matrices of component models into the S-matrix of a circuit.
A waveguide has effective index neff at wl0_um, group index ng (first-order
dispersion) and a propagation loss; a directional coupler transfers the power
fraction coupling with the scattering matrix [[t, i k], [i k, t]]. circuit mzi
is a Mach-Zehnder interferometer with splitter couplers and arms differing by
arm_difference_um; ring is an all-pass ring of length ring_length_um on one
bus; add_drop couples the ring to a second bus with drop_coupling.
Wavelengths and lengths are in micrometres. The transfer function of each
circuit, written out analytically, is evaluated alongside. Dips of the
through port (the bar port of the interferometer) are reported with their
wavelength, extinction, full width at half depth and loaded Q, and the free
spectral range is compared with lambda^2 / (ng L).
"""
import numpy as np
import jax.numpy as jnp
import sax
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'circuit': ('ring', 'mzi, ring or add_drop'),
        'wavelength_um': ({'start': 1.54, 'stop': 1.56, 'points': 4001}, 'vacuum wavelengths: list or {"start", "stop", "points"}'),
        'neff': (2.34, 'effective index of the waveguide at wl0_um'),
        'ng': (4.2, 'group index of the waveguide'),
        'wl0_um': (1.55, 'reference wavelength of neff'),
        'loss_db_per_cm': (3.0, 'propagation loss'),
        'coupling': (0.1, 'power coupling between the input bus and the ring'),
        'drop_coupling': (0.1, 'power coupling between the ring and the drop bus (add_drop)'),
        'ring_length_um': (62.83185307179586, 'ring circumference'),
        'splitter': (0.5, 'power coupling of both couplers of the interferometer'),
        'arm_length_um': (100.0, 'length of the shorter interferometer arm'),
        'arm_difference_um': (50.0, 'length difference between the interferometer arms'),
    },
    'results': 'transmission.npz/.json with the power at each port over wavelength and the analytic values; dips with extinction, width and loaded Q; free spectral range',
    'checks': 'analytic_difference: largest |T_sax - T_analytic|; fsr_error: relative difference from lambda^2 / (ng L)',
}
p = parameters(PROGRAM, INPUTS)
if p['circuit'] not in ('mzi', 'ring', 'add_drop'):
    raise ValueError('circuit is mzi, ring or add_drop')
grid = p['wavelength_um']
wl = np.linspace(grid['start'], grid['stop'], int(grid['points'])) if isinstance(grid, dict) else np.asarray(grid, float)
neff0, ng, wl0, loss = float(p['neff']), float(p['ng']), float(p['wl0_um']), float(p['loss_db_per_cm'])


def straight(wl=wl0, length=10.0):
    neff = neff0 - (wl - wl0) * (ng - neff0) / wl0
    amplitude = 10 ** (-loss * length * 1e-4 / 20)
    return sax.reciprocal({('in0', 'out0'): amplitude * jnp.exp(2j * jnp.pi * neff * length / wl)})


def coupler(coupling=0.5):
    k, t = coupling ** 0.5, (1 - coupling) ** 0.5
    return sax.reciprocal({('in0', 'out0'): t, ('in0', 'out1'): 1j * k, ('in1', 'out0'): 1j * k, ('in1', 'out1'): t})


def wave(length):
    """Analytic amplitude transmission of a waveguide."""
    neff = neff0 - (wl - wl0) * (ng - neff0) / wl0
    return 10 ** (-loss * length * 1e-4 / 20) * np.exp(2j * np.pi * neff * length / wl)


models = {'coupler': coupler, 'straight': straight}
if p['circuit'] == 'mzi':
    netlist = {'instances': {'lft': 'coupler', 'top': 'straight', 'btm': 'straight', 'rgt': 'coupler'},
               'connections': {'lft,out0': 'btm,in0', 'btm,out0': 'rgt,in0', 'lft,out1': 'top,in0', 'top,out0': 'rgt,in1'},
               'ports': {'in0': 'lft,in0', 'in1': 'lft,in1', 'out0': 'rgt,out0', 'out1': 'rgt,out1'}}
    short, extra, c = float(p['arm_length_um']), float(p['arm_difference_um']), float(p['splitter'])
    settings = {'btm': {'length': short}, 'top': {'length': short + extra}, 'lft': {'coupling': c}, 'rgt': {'coupling': c}}
    t, k = (1 - c) ** 0.5, c ** 0.5
    analytic = {'bar': t * t * wave(short) - k * k * wave(short + extra), 'cross': 1j * k * t * (wave(short) + wave(short + extra))}
    ports = {'bar': ('in0', 'out0'), 'cross': ('in0', 'out1')}
    dips_of, length = 'bar', extra
else:
    L, c1, c2 = float(p['ring_length_um']), float(p['coupling']), float(p['drop_coupling'])
    t1, t2 = (1 - c1) ** 0.5, (1 - c2) ** 0.5
    if p['circuit'] == 'ring':
        netlist = {'instances': {'dc': 'coupler', 'rg': 'straight'}, 'connections': {'dc,out1': 'rg,in0', 'rg,out0': 'dc,in1'},
                   'ports': {'in0': 'dc,in0', 'out0': 'dc,out0'}}
        settings = {'rg': {'length': L}, 'dc': {'coupling': c1}}
        round_trip = wave(L)
        analytic = {'through': (t1 - round_trip) / (1 - t1 * round_trip)}
        ports = {'through': ('in0', 'out0')}
    else:
        netlist = {'instances': {'dc1': 'coupler', 'dc2': 'coupler', 'h1': 'straight', 'h2': 'straight'},
                   'connections': {'dc1,out1': 'h1,in0', 'h1,out0': 'dc2,in1', 'dc2,out1': 'h2,in0', 'h2,out0': 'dc1,in1'},
                   'ports': {'in0': 'dc1,in0', 'out0': 'dc1,out0', 'drop': 'dc2,out0', 'add': 'dc2,in0'}}
        settings = {'h1': {'length': L / 2}, 'h2': {'length': L / 2}, 'dc1': {'coupling': c1}, 'dc2': {'coupling': c2}}
        round_trip = wave(L)
        analytic = {'through': (t1 - t2 * round_trip) / (1 - t1 * t2 * round_trip),
                    'drop': -(c1 * c2) ** 0.5 * wave(L / 2) / (1 - t1 * t2 * round_trip)}
        ports = {'through': ('in0', 'out0'), 'drop': ('in0', 'drop')}
    dips_of, length = 'through', L
circuit, _ = sax.circuit(netlist=netlist, models=models)
S = circuit(wl=jnp.asarray(wl), **settings)
power = {name: np.abs(np.asarray(S[pair])) ** 2 for name, pair in ports.items()}
expected = {name: np.abs(value) ** 2 for name, value in analytic.items()}

T = power[dips_of]
inner = np.where((T[1:-1] < T[:-2]) & (T[1:-1] <= T[2:]))[0] + 1
top = float(T.max())
dips = []
for i in inner:
    if T[i] > top - 0.1 * (top - T.min()):
        continue  # ripple, not a resonance
    half = (top + T[i]) / 2
    left, right = i, i
    while left > 0 and T[left] < half:
        left -= 1
    while right < len(T) - 1 and T[right] < half:
        right += 1
    if T[left] < half or T[right] < half:
        continue  # the dip runs past the edge of the band
    x0 = wl[left] + (half - T[left]) * (wl[left + 1] - wl[left]) / (T[left + 1] - T[left])
    x1 = wl[right - 1] + (half - T[right - 1]) * (wl[right] - wl[right - 1]) / (T[right] - T[right - 1])
    dips.append({'wavelength_um': float(wl[i]), 'transmission': float(T[i]), 'extinction_db': float(10 * np.log10(top / max(T[i], 1e-30))),
                 'width_nm': float((x1 - x0) * 1e3), 'loaded_q': float(wl[i] / (x1 - x0))})
fsr = float(np.mean(np.diff([d['wavelength_um'] for d in dips]))) if len(dips) > 1 else None
centre = float(np.mean([d['wavelength_um'] for d in dips])) if dips else wl0
axes = ['wavelength_um']
arrays = {'wavelength_um': data.quantity(wl, 'vacuum wavelength', unit='um')}
for name in power:
    arrays[name] = data.quantity(power[name], f'power transmission to the {name} port', unit='1', axes=axes, circuit=p['circuit'])
    arrays[name + '_analytic'] = data.quantity(expected[name], f'analytic power transmission to the {name} port', unit='1', axes=axes)
saved = data.save(OUTPUT_DIR / 'transmission', arrays)
RESULT = {'data': saved['data'], 'circuit': p['circuit'], 'dips': dips[:20], 'dip_count': len(dips), 'fsr_nm': fsr * 1e3 if fsr else None,
          'fsr_expected_nm': centre ** 2 / (ng * length) * 1e3,
          'checks': {'analytic_difference': float(max(np.max(np.abs(power[n] - expected[n])) for n in power)),
                     'fsr_error': abs(fsr / (centre ** 2 / (ng * length)) - 1) if fsr else None}}
