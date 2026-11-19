"""First-order properties, third-order (Seidel) aberrations and real-ray spots of a lens (Optiland).

Optiland traces the paraxial marginal and chief rays of a sequential system
of spherical surfaces, which give the effective focal length, the back focal
distance, the f-number, the entrance and exit pupils and the Lagrange
invariant, and from them each surface's Seidel coefficients: spherical
aberration, coma, astigmatism, Petzval field curvature and distortion (S1 to
S5) with the transverse aberrations they produce at the image in mm, and the
longitudinal and transverse axial colour. Real rays on a hexapolar pupil grid
at each field and wavelength give the RMS spot radius about the centroid on
the image surface, which image_solve puts at the paraxial focus; a lens design
is judged and optimized by these quantities. Lengths are
in mm, wavelengths in um and field angles in degrees from the axis, for an
object at infinity. A surface takes the index after it from a glass of
Optiland's catalog or a number, with an optional Abbe number for dispersion
(Buchdahl model). The default is a Cooke triplet of 50 mm focal length at
f/4 (N-LAK9, N-SF5, N-LAK9). Checks: the focal length against an independent
paraxial (y-nu) trace of the same prescription, and the third-order
transverse spherical aberration against real rays near the axis,
extrapolated to zero aperture.
"""
import numpy as np
from optiland import optic
from optiland.materials import AbbeMaterial, IdealMaterial, Material
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'surfaces': ([{'radius_mm': None, 'thickness_mm': None},
                      {'radius_mm': 23.713, 'thickness_mm': 4.831, 'glass': 'N-LAK9'}, {'radius_mm': 7331.288, 'thickness_mm': 5.86},
                      {'radius_mm': -24.456, 'thickness_mm': 0.975, 'glass': 'N-SF5', 'stop': True}, {'radius_mm': 21.896, 'thickness_mm': 4.822},
                      {'radius_mm': 86.759, 'thickness_mm': 3.127, 'glass': 'N-LAK9'}, {'radius_mm': -20.4942, 'thickness_mm': 41.2365},
                      {'radius_mm': None, 'thickness_mm': 0}],
                     'surfaces from object (thickness null: at infinity) to image: radius_mm (null planar), thickness_mm after it, '
                     'glass (Optiland catalog) or index with optional abbe, stop'),
        'aperture_mm': (12.5, 'entrance pupil diameter in mm'),
        'fields_deg': ([0, 14, 20], 'field angles in degrees; the largest is the full field'),
        'wavelengths_um': ([0.4861327, 0.5875618, 0.6562725], 'wavelengths in um'),
        'primary_um': (0.5875618, 'primary wavelength, one of wavelengths_um'),
        'image_solve': (True, 'move the image surface to the paraxial focus'),
        'rings': (8, 'rings of the hexapolar pupil grid of the spot diagrams'),
    },
    'results': 'lens.npz/.json: Seidel and transverse coefficients of every surface, spot coordinates per field and wavelength, '
               'RMS spot radii; first-order data, Seidel sums and RMS spot radius per field',
    'checks': 'focal_length_difference: EFL from Optiland minus an independent paraxial trace, relative; '
              'spherical_difference: third-order transverse spherical aberration minus real rays extrapolated to zero aperture, relative',
}
p = parameters(PROGRAM, INPUTS)
wavelengths = [float(w) for w in p['wavelengths_um']]
primary, fields = float(p['primary_um']), [float(f) for f in p['fields_deg']]
if not wavelengths or primary not in wavelengths or min(wavelengths) <= 0 or float(p['aperture_mm']) <= 0 or not fields:
    raise ValueError('wavelengths_um holds primary_um, wavelengths and aperture_mm are positive and fields_deg is not empty')
if len(p['surfaces']) < 3 or p['surfaces'][0].get('thickness_mm') is not None:
    raise ValueError('surfaces run from an object at infinity (thickness_mm null) through at least one surface to the image')


def material(surface):
    if surface.get('glass'):
        return Material(str(surface['glass']))
    index = float(surface.get('index', 1))
    if index <= 0:
        raise ValueError('index must be positive')
    return AbbeMaterial(index, float(surface['abbe']), model='buchdahl') if surface.get('abbe') else IdealMaterial(index)


system = optic.Optic()
media = []
for i, surface in enumerate(p['surfaces']):
    radius, thickness = surface.get('radius_mm'), surface.get('thickness_mm', 0)
    media.append(material(surface))
    system.surfaces.add(index=i, radius=np.inf if radius is None else float(radius), thickness=np.inf if thickness is None else float(thickness),
                        material=media[-1], is_stop=bool(surface.get('stop', False)))
system.set_aperture('EPD', float(p['aperture_mm']))
system.fields.set_type('angle')
full = max(abs(f) for f in fields) or 1.0
for f in fields:
    system.fields.add(y=f)
for w in wavelengths:
    system.wavelengths.add(value=w, is_primary=w == primary)
if p['image_solve']:
    system.image_solve()


def scalar(value):
    return float(np.asarray(value).ravel()[0])


paraxial = system.paraxial
first_order = {'efl_mm': scalar(paraxial.f2()), 'bfl_mm': None, 'f_number': scalar(paraxial.FNO()),
               'entrance_pupil_mm': {'diameter': scalar(paraxial.EPD()), 'position': scalar(paraxial.EPL())},
               'exit_pupil_mm': {'diameter': scalar(paraxial.XPD()), 'position': scalar(paraxial.XPL())},
               'lagrange_invariant': scalar(paraxial.invariant())}
thicknesses = [scalar(s.thickness) if np.isfinite(scalar(s.thickness)) else None for s in system.surfaces.surfaces] \
    if hasattr(system.surfaces, 'surfaces') else None

# Independent paraxial trace: y-nu through the refracting surfaces, a ray parallel to the axis at height 1.
indices = [scalar(m.n(primary)) for m in media]
height, angle = 1.0, 0.0
for i in range(1, len(p['surfaces']) - 1):
    radius = p['surfaces'][i].get('radius_mm')
    power = 0.0 if radius is None else (indices[i] - indices[i - 1]) / float(radius)
    angle = (indices[i - 1] * angle - height * power) / indices[i]
    if i < len(p['surfaces']) - 2:
        height += angle * float(p['surfaces'][i].get('thickness_mm', 0))
efl = -1.0 / angle
back = -height / angle                                    # from the last refracting surface to the paraxial focus
first_order['bfl_mm'] = back

aberrations = system.aberrations
names = ['S1', 'S2', 'S3', 'S4', 'S5']
seidel = np.asarray(aberrations.seidels(), dtype=float).ravel()     # sums over the surfaces
coefficients = {name: np.asarray(getattr(aberrations, name)(), dtype=float).ravel()
                for name in ('TSC', 'TCC', 'TAC', 'TPC', 'DC', 'LchC', 'TchC')}

# Real rays: spots per field and wavelength on the image surface.
rings = int(p['rings'])
spots, rms = [], []
for f in fields:
    per_field, points = [], []
    for w in wavelengths:
        system.trace(Hx=0, Hy=f / full, wavelength=w, num_rays=rings, distribution='hexapolar')
        xy = np.column_stack([np.asarray(system.surfaces.x)[-1].ravel(), np.asarray(system.surfaces.y)[-1].ravel()])
        per_field.append(xy)
        points.append(xy[np.isfinite(xy).all(axis=1)])
    spots.append(per_field)
    together = np.concatenate(points)
    primary_points = points[wavelengths.index(primary)]
    rms.append({'field_deg': f,
                'polychromatic_um': float(np.sqrt(np.mean(np.sum((together - together.mean(axis=0)) ** 2, axis=1)))) * 1000,
                'primary_um': float(np.sqrt(np.mean(np.sum((primary_points - primary_points.mean(axis=0)) ** 2, axis=1)))) * 1000,
                'centroid_y_mm': float(primary_points[:, 1].mean())})
count = max(len(xy) for per_field in spots for xy in per_field)
coordinates = np.full((len(fields), len(wavelengths), count, 2), np.nan)
for i, per_field in enumerate(spots):
    for j, xy in enumerate(per_field):
        coordinates[i, j, :len(xy)] = xy

# Third-order spherical aberration against real rays near the axis, extrapolated as a + b rho^2 to zero aperture.
spherical_difference = None
if p['image_solve']:
    values = []
    for rho in (0.05, 0.1):
        system.trace_generic(Hx=0, Hy=0, Px=0.0, Py=rho, wavelength=primary)
        values.append(scalar(np.asarray(system.surfaces.y)[-1]) / rho ** 3)
    limit = (values[0] * 0.01 - values[1] * 0.0025) / 0.0075
    spherical_difference = abs(limit - coefficients['TSC'].sum()) / abs(coefficients['TSC'].sum())

surface_axis = {'name': 'surface', 'start': 1, 'step': 1}
saved = data.save(OUTPUT_DIR / 'lens', {
    'seidel': data.quantity(seidel, 'Seidel sums S1 (spherical) to S5 (distortion)', unit='mm', axes=[{'name': 'coefficient', 'labels': names}]),
    **{name.lower(): data.quantity(values, {'TSC': 'transverse spherical aberration', 'TCC': 'transverse sagittal coma',
                                            'TAC': 'transverse astigmatism', 'TPC': 'transverse Petzval curvature', 'DC': 'distortion',
                                            'LchC': 'longitudinal axial colour', 'TchC': 'transverse axial colour'}[name] + ' of each surface',
                                   unit='mm', axes=[surface_axis]) for name, values in coefficients.items()},
    'spots': data.quantity(coordinates, 'real-ray intersections with the image surface', unit='mm',
                           axes=[{'name': 'field_deg', 'labels': [str(f) for f in fields]},
                                 {'name': 'wavelength_um', 'labels': [str(w) for w in wavelengths]},
                                 {'name': 'ray', 'start': 0, 'step': 1}, {'name': 'coordinate', 'labels': ['x', 'y']}]),
})
RESULT = {'data': saved['data'], 'first_order': first_order,
          'seidel': dict(zip(names, map(float, seidel))),
          'transverse_mm': {name: float(values.sum()) for name, values in coefficients.items()},
          'spots': rms, 'image_distance_mm': thicknesses[-2] if thicknesses else None,
          'checks': {'focal_length_difference': abs(first_order['efl_mm'] - efl) / abs(efl), 'spherical_difference': spherical_difference}}
