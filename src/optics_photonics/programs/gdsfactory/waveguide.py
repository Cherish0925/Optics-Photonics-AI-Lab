"""Straight strip waveguide layout from GDSFactory's generic PDK.

Writes GDSII and the port names, centres, widths and orientations, all in
micrometres. The generic PDK illustrates layout; fabrication uses the
foundry's PDK through a native program.
"""
import gdsfactory as gf
from gdsfactory.gpdk import get_generic_pdk
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'length_um': (20, 'waveguide length in micrometres'),
        'width_um': (0.5, 'waveguide width in micrometres'),
    },
    'domains': ['pic'],
    'results': 'waveguide.gds and the ports of the component',
}
p = parameters(PROGRAM, INPUTS)
if float(p['length_um']) <= 0 or float(p['width_um']) <= 0:
    raise ValueError('length_um and width_um must be positive')
get_generic_pdk().activate()
component = gf.components.straight(length=float(p['length_um']), width=float(p['width_um']))
component.write_gds(OUTPUT_DIR / 'waveguide.gds', with_metadata=False)
ports = [{'name': port.name, 'center_um': list(port.center), 'orientation_deg': float(port.orientation), 'width_um': float(port.width)}
         for port in component.ports]
RESULT = {'pdk': 'generic', 'ports': ports, 'data': 'waveguide.gds'}
