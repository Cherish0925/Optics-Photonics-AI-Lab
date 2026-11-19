"""Pictures of array selections: PNG content, colors, coordinates and the MCP image reply."""
import base64
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import unittest
import zlib
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from optics_photonics import arrays, jobs, mcp, pictures  # noqa: E402
from support import workspace  # noqa: E402


def decode(png):
    """Width, height and RGB rows of a PNG written with filter 0, as pictures writes it."""
    assert png[:8] == b'\x89PNG\r\n\x1a\n'
    position, chunks = 8, {}
    while position < len(png):
        length, kind = struct.unpack('>I4s', png[position:position + 8])
        chunks.setdefault(kind, b'')
        chunks[kind] += png[position + 8:position + 8 + length]
        position += 12 + length
    width, height = struct.unpack('>II', chunks[b'IHDR'][:8])
    raw = zlib.decompress(chunks[b'IDAT'])
    stride = 1 + 3 * width
    rows = [raw[y * stride + 1:(y + 1) * stride] for y in range(height)]
    return width, height, rows


def pixel(rows, x, y):
    return tuple(rows[y][3 * x:3 * x + 3])


def field(home, run_id='a' * 32):
    """A run folder with described arrays: a ramp over x and y, a complex vortex and three spectra."""
    folder = Path(home) / 'runs' / run_id / 'solve' / 'attempt-1'
    folder.mkdir(parents=True)
    x = [i * 0.5 for i in range(20)]
    y = [j * 0.5 for j in range(10)]
    ramp = [xi + 10 * yj for yj in y for xi in x]
    vortex = [complex(xi - 4.75, yj - 2.25) for yj in y for xi in x]
    spectra = [(s + 1) * math.sin(k * 0.1) for s in range(3) for k in range(50)]
    arrays.write(folder / 'data', {
        'ramp': (ramp, [10, 20]), 'x_um': (x, [20]), 'y_um': (y, [10]),
        'spectra': (spectra, [3, 50]), 'wavelength_nm': ([500.0 + 2 * k for k in range(50)], [50])},
        {'ramp': {'quantity': 'ramp', 'unit': 'V', 'axes': ['y_um', 'x_um']}, 'x_um': {'unit': 'um'}, 'y_um': {'unit': 'um'},
         'spectra': {'quantity': 'signal', 'axes': [{'name': 'channel', 'labels': ['a', 'b', 'c']}, 'wavelength_nm']},
         'wavelength_nm': {'unit': 'nm'}})
    # Complex values need NumPy's layout; write them through the NPY header directly.
    flat = [part for value in vortex for part in (value.real, value.imag)]
    header = repr({'descr': '<c16', 'fortran_order': False, 'shape': (10, 20)}).encode('latin1')
    header += b' ' * (-(10 + len(header) + 1) % 64) + b'\n'
    (folder / 'vortex.npy').write_bytes(b'\x93NUMPY\x01\x00' + struct.pack('<H', len(header)) + header + struct.pack(f'<{len(flat)}d', *flat))
    return run_id


class PictureCase(unittest.TestCase):
    def test_a_map_colors_the_extremes_and_keeps_square_cells(self):
        with workspace() as home:
            run_id = field(home)
            result = jobs.read_array(run_id, 'solve/attempt-1/data.npz', member='ramp', image='map', path=home)
            self.assertNotIn('values', result)
            self.assertEqual((result['summary']['min'], result['summary']['max']), (0.0, 9.5 + 45))
            self.assertEqual(result['summary']['at_max'], {'y_um': 4.5, 'x_um': 9.5})
            width, height, rows = decode(result['_image'])
            self.assertEqual((width, height), (880, 560))
            left, top = pictures.FRAME['left'], pictures.FRAME['top']
            # Square cells: 20 x 10 cells of 0.5 um fill a 2:1 area; the first row is drawn at the bottom.
            plot_width = 880 - pictures.FRAME['right'] - 110 - left
            plot_height = plot_width // 2
            self.assertEqual(pixel(rows, left + 1, top + plot_height - 2), pictures.VIRIDIS[0])
            self.assertEqual(pixel(rows, left + plot_width - 2, top + 1), pictures.VIRIDIS[-1])
            self.assertEqual(pixel(rows, left + plot_width - 2, top + plot_height + 30), pictures.WHITE)

    def test_short_axes_become_lines_and_complex_values_take_a_part(self):
        with workspace() as home:
            run_id = field(home)
            lines = jobs.read_array(run_id, 'solve/attempt-1/data.npz', member='spectra', image='auto', path=home)
            self.assertEqual(lines['summary']['drawn']['kind'], 'line')
            self.assertEqual(lines['summary']['at_max'], {'channel': 'c', 'wavelength_nm': 532.0})
            _, _, rows = decode(lines['_image'])
            colors = {pixel(rows, x, y) for y in range(0, 560, 2) for x in range(0, 880, 2)}
            self.assertTrue(set(pictures.LINES[:3]) <= colors)
            phase = jobs.read_array(run_id, 'solve/attempt-1/vortex.npy', image='map', part='phase', path=home)
            self.assertAlmostEqual(phase['summary']['max'], math.atan2(0.25, -4.75), places=12)  # just above the branch cut
            magnitude = jobs.read_array(run_id, 'solve/attempt-1/vortex.npy', image='map', scale='log', path=home)
            self.assertAlmostEqual(magnitude['summary']['min'], math.hypot(0.25, 0.25), places=12)
            with self.assertRaisesRegex(ValueError, 'imag applies to complex arrays'):
                jobs.read_array(run_id, 'solve/attempt-1/data.npz', member='ramp', image='map', part='imag', path=home)
            with self.assertRaisesRegex(ValueError, 'one- or two-dimensional selection; this one has shape'):
                jobs.read_array(run_id, 'solve/attempt-1/data.npz', member='ramp', index=[0, 0], image='auto', path=home)
            # Axes of length one, such as one polarization and one angle of a spectrum, are fixed for the picture.
            folder = Path(home) / 'runs' / run_id / 'solve' / 'attempt-1'
            arrays.write(folder / 'spectrum', {'R': ([0.1 * k for k in range(50)], [1, 1, 50])}, {'R': {'quantity': 'reflectance'}})
            drawn = jobs.read_array(run_id, 'solve/attempt-1/spectrum.npz', member='R', image='auto', path=home)
            self.assertEqual((drawn['summary']['drawn']['kind'], drawn['result_shape']), ('line', [50]))

    def test_the_mcp_reply_carries_the_png_and_the_command_line_writes_it(self):
        with workspace() as home:
            run_id = field(home)
            original = jobs.environments.home
            try:
                jobs.environments.home = lambda path=None: Path(home)
                reply = mcp.tool_result({'name': 'read_array', 'arguments': {'run_id': run_id, 'file': 'solve/attempt-1/data.npz',
                                                                             'member': 'ramp', 'image': 'map'}})
            finally:
                jobs.environments.home = original
            self.assertFalse(reply['isError'], reply)
            image, text = reply['content']
            self.assertEqual((image['type'], image['mimeType']), ('image', 'image/png'))
            self.assertEqual(decode(base64.b64decode(image['data']))[:2], (880, 560))
            self.assertNotIn('_image', reply['structuredContent'])
            self.assertEqual(json.loads(text['text'])['summary']['max'], 54.5)
            target = Path(home) / 'ramp.png'
            command = [sys.executable, '-m', 'optics_photonics', 'array', run_id, 'solve/attempt-1/data.npz', '--member', 'ramp',
                       '--image', str(target), '--scale', 'log']
            printed = subprocess.run(command, capture_output=True, text=True, check=True, cwd=Path(__file__).resolve().parents[1] / 'src',
                                     env={**__import__('os').environ, 'OPTICS_HOME': home})
            self.assertEqual(json.loads(printed.stdout)['image'], str(target))
            self.assertEqual(decode(target.read_bytes())[:2], (880, 560))

    def test_ticks_and_labels_are_round_and_short(self):
        self.assertEqual(pictures.ticks(0, 1), [0, 0.2, 0.4, 0.6000000000000001, 0.8, 1.0])
        self.assertEqual([pictures.label(v) for v in (1e4, 12345.6, 1e6, 2.5e-7, 3)], ['10000', '12346', '1e6', '2.5e-7', '3'])
        self.assertEqual(pictures.label(0.25, 0.05), '0.25')
        self.assertEqual([text for _, text in pictures.tick_labels(-6.2, -0.5, True)], ['1e-6', '1e-5', '1e-4', '0.001', '0.01', '0.1'])


if __name__ == '__main__':
    unittest.main()
