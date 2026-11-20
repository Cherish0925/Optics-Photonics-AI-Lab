"""Paraxial ray transfer (ABCD) matrix of free spaces and thin lenses.

raytracing multiplies the matrices of the elements in propagation order and
transfers a ray [height in m, angle in rad]. The matrix assumes equal
indices before and after the system, so its determinant is 1.
"""
import numpy as np
from raytracing import Matrix, Space, Lens
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'elements': ([{'space_m': 0.1}, {'focal_length_m': 0.05}, {'space_m': 0.1}], 'elements in order: {space_m} or {focal_length_m}'),
        'ray': ([0.001, 0], 'input ray [height in m, angle in rad]'),
    },
    'domains': ['ray'],
    'results': 'matrix [[A, B], [C, D]] with units, output ray, determinant',
    'checks': 'determinant: 1 for a system between equal indices',
}
p = parameters(PROGRAM, INPUTS)
matrix = Matrix()
for element in p['elements']:
    if set(element) == {'space_m'}:
        matrix = Space(element['space_m']) * matrix
    elif set(element) == {'focal_length_m'} and element['focal_length_m'] != 0:
        matrix = Lens(element['focal_length_m']) * matrix
    else:
        raise ValueError('Each element is space_m or a nonzero focal_length_m')
a = np.array([[matrix.A, matrix.B], [matrix.C, matrix.D]])
RESULT = {'matrix': a.tolist(), 'matrix_units': [['1', 'm'], ['1/m', '1']], 'ray_out': (a @ p['ray']).tolist(), 'ray_units': ['m', 'rad'],
          'determinant': float(np.linalg.det(a)), 'checks': {'determinant': float(np.linalg.det(a))}}
