"""Exact ABCD matrix of free space, thin lens and free space.

SymPy multiplies the symbolic matrices for propagation a, a thin lens of
focal length f and propagation b. The names are symbols; use one length
unit throughout. Imaging holds where B = 0, the lens law 1/a + 1/b = 1/f.
"""
import sympy as sp
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'focal_length': ('f', 'symbol name of the focal length'),
        'distance_before': ('a', 'symbol name of the distance before the lens'),
        'distance_after': ('b', 'symbol name of the distance after the lens'),
    },
    'domains': ['ray'],
    'results': 'matrix entries and determinant as SymPy expressions, and the imaging condition B = 0 solved for the distance after',
}
p = parameters(PROGRAM, INPUTS)
names = [p[k] for k in ('focal_length', 'distance_before', 'distance_after')]
if not all(isinstance(v, str) and v.isidentifier() for v in names):
    raise ValueError('Provide three symbolic variable names')
f, a, b = (sp.Symbol(v, nonzero=True) if i == 0 else sp.Symbol(v) for i, v in enumerate(names))
result = sp.Matrix([[1, b], [0, 1]]) * sp.Matrix([[1, 0], [-1 / f, 1]]) * sp.Matrix([[1, a], [0, 1]])
imaging = sp.solve(sp.Eq(result[0, 1], 0), b)
RESULT = {'matrix': [[str(sp.simplify(v)) for v in row] for row in result.tolist()], 'determinant': str(sp.simplify(result.det())),
          'imaging': [str(sp.simplify(v)) for v in imaging], 'latex': sp.latex(result)}
