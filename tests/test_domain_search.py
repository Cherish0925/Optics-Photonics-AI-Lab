"""Domain filters retain software-name lookups without importing unrelated program matches."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from optics_photonics import catalogue


class DomainSearchCase(unittest.TestCase):
    def test_software_names_find_their_programs_in_an_added_domain(self):
        for query in ('scipy', 'NumPy', 'NumPy / SciPy'):
            for domain, program in (('bio', 'tissue_layers'), ('fiber', 'fiber_modes')):
                with self.subTest(query=query, domain=domain):
                    found = catalogue.search(query, domain=domain)['items']
                    self.assertTrue(found)
                    self.assertEqual((found[0]['id'], found[0]['program']['name']), ('scipy', program))

    def test_program_queries_stay_within_the_requested_domain(self):
        for query in ('fiber modes', 'scipy fiber modes'):
            self.assertEqual(catalogue.search(query, domain='bio')['total'], 0)
        found = catalogue.search('second harmonic', domain='laser')['items']
        self.assertEqual([(item['id'], item['program']['name']) for item in found], [('scipy', 'second_harmonic')])


if __name__ == '__main__':
    unittest.main()
