"""Plane-wave reflectance and transmittance of uniform layers by RCWA.

grcwa solves layers of real isotropic permittivity; thickness is divided by
the vacuum wavelength and the first and last layers are the exterior media.
A uniform film has only the zeroth order, which makes this a reference for
the thin-film solvers; patterned layers use the grating program.
"""
import math
import grcwa
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'epsilon': ([1, 2.1025, 2.3104], 'permittivity of each layer, exterior media first and last'),
        'thickness_over_wavelength': ([0, 0.1818181818, 0], 'thickness over vacuum wavelength for each layer'),
        'polarization': ('s', 's or p'),
        'angle_deg': (0, 'angle of incidence in degrees'),
    },
    'results': 'R, T and 1 - R - T',
    'checks': 'one_minus_R_minus_T: zero for lossless layers',
}
p = parameters(PROGRAM, INPUTS)
if len(p['epsilon']) != len(p['thickness_over_wavelength']) or len(p['epsilon']) < 2:
    raise ValueError('Provide matching permittivity and thickness lists including exterior media')
if p['polarization'] not in ('s', 'p'):
    raise ValueError('polarization is s or p')
# A uniform film has only the zeroth diffraction order; grcwa keeps one order from nG=2.
solver = grcwa.obj(2, [1, 0], [0, 1], 1.0, math.radians(p['angle_deg']), 0, verbose=0)
for eps, thick in zip(p['epsilon'], p['thickness_over_wavelength']):
    solver.Add_LayerUniform(float(thick), float(eps))
solver.Init_Setup()
solver.MakeExcitationPlanewave(p_amp=int(p['polarization'] == 'p'), p_phase=0, s_amp=int(p['polarization'] == 's'), s_phase=0)
r, t = solver.RT_Solve(normalize=1)
RESULT = {'R': float(r), 'T': float(t), 'one_minus_R_minus_T': float(1 - r - t), 'checks': {'one_minus_R_minus_T': float(1 - r - t)}}
