"""Translation between two images by phase cross-correlation.

scikit-image returns the [row, column] shift in pixels that aligns moving to
reference, with subpixel precision set by upsample_factor. Periodic
ambiguity and partial overlap need consideration for real images.
"""
import numpy as np
from skimage.registration import phase_cross_correlation
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'reference': ([[0, 1, 0, 0], [0, 0, 0, 0], [0, 0, 2, 0], [0, 0, 0, 0]], 'reference image as rows of numbers'),
        'moving': ([[0, 0, 1, 0], [0, 0, 0, 0], [0, 0, 0, 2], [0, 0, 0, 0]], 'image to align, same shape'),
        'upsample_factor': (1, 'subpixel precision: 1 / upsample_factor pixel'),
    },
    'results': 'shift in pixels [row, column], normalized error, global phase difference',
}
p = parameters(PROGRAM, INPUTS)
reference, moving = np.asarray(p['reference'], dtype=float), np.asarray(p['moving'], dtype=float)
if reference.shape != moving.shape or reference.ndim != 2:
    raise ValueError('reference and moving are two-dimensional images of the same shape')
shift, error, phase = phase_cross_correlation(reference, moving, upsample_factor=p['upsample_factor'])
RESULT = {'shift_pixels': shift.tolist(), 'axis_order': ['row', 'column'], 'normalized_error': float(error), 'phase_difference_rad': float(phase)}
