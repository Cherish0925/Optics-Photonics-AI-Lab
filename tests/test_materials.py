"""Refractive index data from the refractiveindex.info database, offline and downloaded."""
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from optics_photonics import materials  # noqa: E402
from optics_photonics.mcp import invoke  # noqa: E402
from support import workspace  # noqa: E402


class MaterialCase(unittest.TestCase):
    def test_bundled_formulas_give_published_indices(self):
        # Catalogue values at the helium d line, 587.56 nm.
        for name, expected in (('SiO2', 1.4585), ('N-BK7', 1.5168), ('sapphire', 1.7682), ('CaF2', 1.4338)):
            self.assertAlmostEqual(materials.nk(name, 0.5875618)['n'][0], expected, delta=1.5e-4, msg=name)
        self.assertAlmostEqual(materials.nk('air', 0.5876)['n'][0], 1.000277, delta=2e-6)
        self.assertAlmostEqual(materials.nk('Si-IR', 1.55)['n'][0], 3.4757, delta=5e-4)

    def test_tables_are_interpolated_linearly_and_k_is_absorption(self):
        page = materials.page('Au')
        rows = page['data'][0]['data']
        x, n, k = rows[10]
        values = materials.nk('Au', x)
        self.assertAlmostEqual(values['n'][0], n, places=12)
        self.assertAlmostEqual(values['k'][0], k, places=12)
        middle = (rows[10][0] + rows[11][0]) / 2
        self.assertAlmostEqual(materials.nk('Au', middle)['n'][0], (rows[10][1] + rows[11][1]) / 2, places=12)
        self.assertGreater(materials.index_at('Au', 0.62).imag, 3)
        self.assertEqual(materials.nk('SiO2', [0.5, 1.0])['k'], [0.0, 0.0])

    def test_names_resolve_and_mistakes_point_to_the_right_page(self):
        self.assertEqual(materials.resolve('si3n4'), 'main/Si3N4/Luke')
        self.assertEqual(materials.resolve('main/Si/Li-293K'), 'main/Si/Li-293K')
        with self.assertRaisesRegex(ValueError, 'Unknown material unobtainium'):
            materials.resolve('unobtainium')
        with self.assertRaisesRegex(ValueError, '2 µm is outside it. Pages of this material that cover it: main/Si/Li-293K'):
            materials.nk('Si', 2.0)
        self.assertEqual(materials.search('silicon nitride')[0]['id'], 'main/Si3N4/Luke')

    def test_the_tool_converts_spectral_units(self):
        by_energy = materials.lookup('Si3N4', wavelength=[0.8], unit='eV')
        by_length = materials.lookup('Si3N4', wavelength=[1549.802], unit='nm')
        self.assertAlmostEqual(by_energy['n'][0], by_length['n'][0], places=6)
        self.assertEqual(by_energy['convention'], 'n + ik, k >= 0 absorbs; vacuum wavelength')
        listed = invoke('materials', {})
        self.assertEqual(listed['common']['Au'], 'main/Au/Johnson')
        self.assertIn('Green', invoke('materials', {'material': 'Si'})['references'])

    def test_other_pages_are_downloaded_once_from_the_pinned_commit(self):
        text = (Path(materials.resources()) / 'data/materials/pages/main/SiO2/nk/Malitson.yml').read_text(encoding='utf-8')
        requested = []

        def respond(url, timeout):
            requested.append(url)
            return io.BytesIO(text.encode())
        with workspace() as home, patch.object(materials.urllib.request, 'urlopen', respond):
            first = materials.nk('main/SiO2/Ghosh-o', 0.6, path=home)
            again = materials.nk('main/SiO2/Ghosh-o', 0.6, path=home)
            self.assertEqual(first['n'], again['n'])
            self.assertEqual(len(requested), 1)
            self.assertIn(materials.index()['commit'], requested[0])
            self.assertTrue(any(Path(home, 'materials').rglob('Ghosh-o.yml')))

    def test_every_bundled_page_parses_and_evaluates_across_its_range(self):
        record = materials.index()
        for name, key in record['common'].items():
            with self.subTest(material=name):
                page = materials.page(key)
                low, high = page['range_um']
                values = materials.nk(key, [low, (low + high) / 2, high])
                self.assertTrue(all(value > 0 for value in values['n']), values)
                self.assertTrue(page['references'])
        self.assertEqual(json.loads(json.dumps(materials.lookup()))['pages'], len(record['by_id']))


if __name__ == '__main__':
    unittest.main()
