"""Real rays through a sequential lens prescription.

Optiland traces rays from one field point through surfaces given by radius,
thickness and the constant index of the medium after each surface (an
IdealMaterial, without dispersion). Lengths in millimetres, wavelength in
micrometres. A null radius is planar and a null first thickness puts the
object at infinity. pupil_points are normalized entrance-pupil coordinates.
Catalog glasses, aspheres, freeforms and optimization use a native program.
"""
import numpy as np
from optiland import optic
from optiland.materials import IdealMaterial
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'surfaces': ([{'radius_mm': None, 'thickness_mm': None}, {'radius_mm': 50, 'thickness_mm': 5, 'index': 1.5, 'stop': True},
                      {'radius_mm': -50, 'thickness_mm': 50}, {'radius_mm': None, 'thickness_mm': 0}],
                     'surfaces from object to image: radius_mm (null planar), thickness_mm (null: object at infinity), index after the surface, stop'),
        'aperture_mm': (10, 'entrance pupil diameter in mm'),
        'field_deg': ([0, 0], 'field angle [x, y] in degrees'),
        'wavelength_um': (0.55, 'wavelength in micrometres'),
        'pupil_points': ([[0, 0], [0, 0.5], [0, -0.5], [0.5, 0], [-0.5, 0]], 'normalized entrance-pupil coordinates [x, y] of the rays'),
    },
    'results': 'rays.npz with ray coordinates at every surface; image.csv; centroid and RMS spot radius at the image',
    'checks': 'finite_intersections: rays that reached the image surface',
}
p = parameters(PROGRAM, INPUTS)
system = optic.Optic()
for i, surface in enumerate(p['surfaces']):
    radius, thickness = surface.get('radius_mm'), surface.get('thickness_mm', 0)
    if float(surface.get('index', 1)) <= 0:
        raise ValueError('index must be positive')
    system.surfaces.add(index=i, radius=np.inf if radius is None else radius, thickness=np.inf if thickness is None else thickness,
                        material=IdealMaterial(float(surface.get('index', 1))), is_stop=surface.get('stop', False))
if float(p['aperture_mm']) <= 0 or float(p['wavelength_um']) <= 0:
    raise ValueError('aperture_mm and wavelength_um must be positive')
system.set_aperture('EPD', float(p['aperture_mm']))
system.fields.set_type('angle')
fx, fy = p['field_deg']
system.fields.add(x=fx, y=fy)
wavelength = float(p['wavelength_um'])
system.wavelengths.add(value=wavelength, is_primary=True)
pupil = np.asarray(p['pupil_points'], dtype=float)
if pupil.ndim != 2 or pupil.shape[1] != 2 or np.any(np.sum(pupil ** 2, axis=1) > 1):
    raise ValueError('pupil_points must be [x,y] pairs within the unit entrance pupil')
field_scale = system.fields.max_field or 1.0
system.trace_generic(Hx=float(fx) / field_scale, Hy=float(fy) / field_scale,
                     Px=pupil[:, 0], Py=pupil[:, 1], wavelength=wavelength)
x, y = np.asarray(system.surfaces.x), np.asarray(system.surfaces.y)
np.savez_compressed(OUTPUT_DIR / 'rays.npz', x_mm=x, y_mm=y, pupil_xy=pupil, wavelength_um=wavelength)
data.save(OUTPUT_DIR / 'rays-described', {
    'x': data.quantity(x, 'ray height x at each surface', unit='mm', axes=[{'name': 'surface', 'start': 0, 'step': 1}, {'name': 'ray', 'start': 0, 'step': 1}]),
    'y': data.quantity(y, 'ray height y at each surface', unit='mm', axes=[{'name': 'surface', 'start': 0, 'step': 1}, {'name': 'ray', 'start': 0, 'step': 1}]),
})
xy = np.column_stack([x[-1], y[-1]])
np.savetxt(OUTPUT_DIR / 'image.csv', xy, delimiter=',', header='x_mm,y_mm', comments='')
valid = np.isfinite(xy).all(axis=1)
if not valid.any():
    raise ValueError('No finite image-plane intersections; inspect the surface prescription')
centroid = xy[valid].mean(axis=0)
rms = np.sqrt(np.mean(np.sum((xy[valid] - centroid) ** 2, axis=1)))
RESULT = {'rays': len(xy), 'finite_intersections': int(valid.sum()), 'centroid_mm': centroid.tolist(), 'rms_spot_mm': float(rms),
          'image_xy_mm': [[float(v) if np.isfinite(v) else None for v in row] for row in xy], 'data': 'rays.npz'}
