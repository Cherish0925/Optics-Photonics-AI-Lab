"""Continue a scalar Fraunhofer slit calculation from its last completed detector point.

The complex amplitude is the midpoint quadrature of a uniform slit pupil,
normalized to one on axis. The reference is sinc(width*x/(wavelength*z))^2.
This is a paraxial, monochromatic, far-field model; it does not model vector
polarization or near-field propagation. Lengths are converted to metres.
"""
import cmath
import csv
import json
import math

p = {'width_um': 50, 'wavelength_nm': 550, 'distance_mm': 1000,
     'pixels': 61, 'pupil_samples': 512, 'pause_after': 7, **INPUTS}
width, wavelength, distance = p['width_um'] * 1e-6, p['wavelength_nm'] * 1e-9, p['distance_mm'] * 1e-3
state = CHECKPOINT.load({'next': 0})
files = dict(CHECKPOINT.files)
for i in range(state['next'], p['pixels']):
    x = (6 * i / (p['pixels'] - 1) - 3) * wavelength * distance / width
    amplitude = sum(cmath.exp(-2j * math.pi * x * width * ((j + 0.5) / p['pupil_samples'] - 0.5)
                             / (wavelength * distance)) for j in range(p['pupil_samples'])) / p['pupil_samples']
    phase = math.pi * width * x / (wavelength * distance)
    reference = (math.sin(phase) / phase) ** 2 if phase else 1.0
    file = OUTPUT_DIR / ('pixel-' + str(i).zfill(4) + '.json')
    file.write_text(json.dumps({'x_m': x, 'intensity': abs(amplitude) ** 2, 'reference': reference}), encoding='utf-8')
    files[str(i)] = file
    CHECKPOINT.save({'next': i + 1}, files=files)
    if p['pause_after'] and i + 1 == p['pause_after'] and CHECKPOINT.restored_from is None:
        raise RuntimeError('Example pause after ' + str(i + 1) + ' completed detector points; resume this run')

rows = [json.loads(files[str(i)].read_text(encoding='utf-8')) for i in range(p['pixels'])]
with (OUTPUT_DIR / 'pattern.csv').open('w', encoding='utf-8', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=['x_m', 'intensity', 'reference'])
    writer.writeheader()
    writer.writerows(rows)
RESULT = {'pixels': len(rows), 'max_absolute_error': max(abs(row['intensity'] - row['reference']) for row in rows),
          'data': 'pattern.csv', 'model': 'Scalar paraxial Fraunhofer diffraction of a uniform slit'}
