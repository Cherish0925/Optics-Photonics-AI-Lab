"""Resonant modes of a ring resonator: frequencies and quality factors by Harminv.

A two-dimensional Meep simulation excites a dielectric ring with a short
pulse and fits the decaying field at a point inside the ring with Harminv,
a sum of damped sinusoids. Each mode is reported with its frequency, its
quality factor Q = f / (-2 Im f) and Harminv's error estimate; fits with
Q <= 0 or a relative error above max_error are dropped. tm excites Ez
(electric field normal to the plane), te excites Hz. Lengths are in
micrometres and frequencies in 1/um (inverse vacuum wavelength). The
defaults are the Meep tutorial ring, with modes near 0.118, 0.147 and 0.175
and Q of about 80, 320 and 1700. High Q needs a longer run after the source
and a finer grid to converge. The field left at the end, dominated by the
longest-lived mode, is saved with the permittivity.
"""
import numpy as np
import meep as mp
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'index': (3.4, 'ring index'),
        'cladding': (1.0, 'index around the ring'),
        'width_um': (1.0, 'ring width'),
        'radius_um': (1.0, 'inner radius'),
        'center_frequency': (0.15, 'pulse centre frequency in 1/um'),
        'frequency_width': (0.1, 'pulse bandwidth in 1/um; Harminv searches this band'),
        'polarization': ('tm', 'tm (Ez) or te (Hz)'),
        'resolution': (10, 'grid points per micrometre'),
        'pad_um': (4.0, 'space between the ring and the absorbing layer'),
        'pml_um': (2.0, 'absorbing layer thickness'),
        'run_after_source': (300, 'time after the pulse, in um/c, over which Harminv fits'),
        'max_error': (1e-3, 'largest accepted Harminv relative error'),
    },
    'results': 'modes with frequency, wavelength_um, Q, imag_frequency (negative: decay) and error; fields.npz/.json with permittivity and final field',
    'checks': 'largest_error: the largest Harminv error among the reported modes',
}
p = parameters(PROGRAM, INPUTS)
if p['polarization'] not in ('tm', 'te'):
    raise ValueError('polarization is tm or te')
r, w = float(p['radius_um']), float(p['width_um'])
half = np.ceil((r + w + p['pad_um'] + p['pml_um']) * p['resolution']) / p['resolution']
component = mp.Ez if p['polarization'] == 'tm' else mp.Hz
probe = mp.Vector3(r + 0.1 * w)
sim = mp.Simulation(cell_size=mp.Vector3(2 * half, 2 * half), resolution=p['resolution'], boundary_layers=[mp.PML(p['pml_um'])],
                    default_material=mp.Medium(index=p['cladding']),
                    geometry=[mp.Cylinder(radius=r + w, material=mp.Medium(index=p['index'])),
                              mp.Cylinder(radius=r, material=mp.Medium(index=p['cladding']))],
                    sources=[mp.Source(mp.GaussianSource(p['center_frequency'], fwidth=p['frequency_width']), component, probe)])
harminv = mp.Harminv(component, probe, p['center_frequency'], p['frequency_width'])
sim.run(mp.after_sources(harminv), until_after_sources=p['run_after_source'])
modes = []
for mode in harminv.modes:
    if mode.Q > 0 and abs(mode.err) <= p['max_error']:
        modes.append({'frequency': float(mode.freq), 'wavelength_um': float(1 / mode.freq), 'Q': float(mode.Q),
                      'imag_frequency': float(mode.decay), 'amplitude': float(abs(mode.amp)), 'error': float(abs(mode.err))})
modes.sort(key=lambda mode: mode['frequency'])
region = mp.Volume(center=mp.Vector3(), size=mp.Vector3(2 * (half - p['pml_um']), 2 * (half - p['pml_um'])))
epsilon = sim.get_array(vol=region, component=mp.Dielectric)
field = sim.get_array(vol=region, component=component)
x, y, _, _ = sim.get_array_metadata(vol=region)
axes = ['x_um', 'y_um']
saved = data.save(OUTPUT_DIR / 'fields', {
    'x_um': data.quantity(np.asarray(x), 'x', unit='um'),
    'y_um': data.quantity(np.asarray(y), 'y', unit='um'),
    'epsilon': data.quantity(epsilon, 'relative permittivity', unit='1', axes=axes),
    'field': data.quantity(field, ('Ez' if p['polarization'] == 'tm' else 'Hz') + ' at the end of the run', unit='arbitrary',
                           axes=axes, time_um_per_c=float(sim.meep_time())),
})
RESULT = {'modes': modes, 'data': saved['data'], 'polarization': p['polarization'],
          'checks': {'largest_error': max((mode['error'] for mode in modes), default=None)}}
