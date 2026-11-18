"""Rectangles written to GDSII with KLayout.

Coordinates in micrometres on one layer and datatype; dbu_um sets the
integer database grid. No design-rule check is performed.
"""
import klayout.db as db
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'rectangles_um': ([[0, 0, 10, 0.5], [12, 0, 22, 0.5]], 'rectangles [left, bottom, right, top] in micrometres'),
        'layer': (1, 'GDS layer number'),
        'datatype': (0, 'GDS datatype'),
        'dbu_um': (0.001, 'database unit in micrometres'),
    },
    'results': 'layout.gds with one top cell',
}
p = parameters(PROGRAM, INPUTS)
if float(p['dbu_um']) <= 0:
    raise ValueError('dbu_um must be positive')
layout = db.Layout()
layout.dbu = float(p['dbu_um'])
top = layout.create_cell('TOP')
layer = layout.layer(int(p['layer']), int(p['datatype']))
for rect in p['rectangles_um']:
    if len(rect) != 4 or rect[2] <= rect[0] or rect[3] <= rect[1]:
        raise ValueError('Rectangles are [left,bottom,right,top] in increasing order')
    top.shapes(layer).insert(db.DBox(*rect))
layout.write(str(OUTPUT_DIR / 'layout.gds'))
RESULT = {'cells': layout.cells(), 'rectangles': len(p['rectangles_um']), 'dbu_um': layout.dbu, 'data': 'layout.gds'}
