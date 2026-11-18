"""Packaged research programs: their declarations, submission and the physics they reproduce."""
import ast
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from optics_photonics import catalogue, environments, jobs, programs  # noqa: E402
from support import workspace  # noqa: E402

SCIENCE = os.environ.get('OPTICS_SCIENCE_TESTS') == '1'


def installed(module):
    try:
        return importlib.util.find_spec(module) is not None
    except ModuleNotFoundError:  # a submodule of a missing package
        return False


class DeclarationCase(unittest.TestCase):
    def test_every_program_declares_its_physics_inputs_and_results(self):
        connections = catalogue.connections()
        for tool, items in programs.catalog().items():
            self.assertEqual(connections[tool]['kind'], 'python', tool)
            for name, spec in items.items():
                with self.subTest(program=tool + '/' + name):
                    self.assertTrue(spec['title'].endswith('.'))
                    self.assertGreater(len(spec['about']), 100)
                    self.assertTrue(spec['results'])
                    for key, (default, about) in spec['inputs'].items():
                        self.assertTrue(about.strip(), key)
                        json.dumps(default, allow_nan=False)
                    source = programs.source(tool, name)
                    ast.parse(source)
                    self.assertIn('parameters(PROGRAM, INPUTS)', source)
                    self.assertIn('RESULT = ', source)

    def test_the_programs_reference_lists_every_program(self):
        import re
        text = (Path(__file__).resolve().parents[1] / 'skills/optical-computation/references/programs.md').read_text(encoding='utf-8')
        listed = set(re.findall(r'^\| `([\w-]+/\w+)`', text, re.M))
        self.assertEqual(listed, {tool + '/' + name for tool, items in programs.catalog().items() for name in items})

    def test_inputs_replace_defaults_and_unknown_names_list_the_accepted_ones(self):
        spec = programs.catalog()['tmm']['spectrum']
        merged = programs.parameters(spec, {'thickness_nm': [80]})
        self.assertEqual(merged['thickness_nm'], [80])
        self.assertEqual(merged['n'], [1, 1.45, 1.52])
        with self.assertRaisesRegex(ValueError, 'Unknown input thickness; this program takes: n, thickness_nm'):
            programs.parameters(spec, {'thickness': [80]})

    def test_details_list_programs_and_return_one_source(self):
        listed = environments.details('scipy')['execution']
        self.assertEqual([item['name'] for item in listed['programs']], ['fit_gaussian', 'laser_rates', 'nlse', 'slab_modes'])
        nlse = next(item for item in listed['programs'] if item['name'] == 'nlse')
        self.assertEqual(nlse['inputs']['length_km']['default'], programs.catalog()['scipy']['nlse']['inputs']['length_km'][0])
        self.assertTrue(environments.details('scipy', program='nlse')['source'].startswith('"""Pulse propagation'))
        with self.assertRaisesRegex(ValueError, 'Unknown program scipy/fft; programs of scipy: fit_gaussian, laser_rates'):
            environments.details('scipy', program='fft')
        native = environments.details('lumerical')['execution']
        self.assertEqual(native['programs'], [])
        self.assertIn('solve_project', native['session_adapter']['actions'])
        self.assertEqual(catalogue.search('tmm')['items'][0]['programs'], ['spectrum'])

    def test_submission_checks_the_program_and_its_inputs(self):
        with workspace() as home:
            with self.assertRaisesRegex(ValueError, 'Unknown program tmm/spectra; programs of tmm: spectrum'):
                jobs.submit([{'id': 'a', 'tool': 'tmm', 'action': 'spectra'}], path=home)
            with self.assertRaisesRegex(ValueError, 'tmm/spectrum has no input thickness; it takes: n, thickness_nm'):
                jobs.submit([{'id': 'a', 'tool': 'tmm', 'action': 'spectrum', 'inputs': {'thickness': [1]}}], path=home)
            with self.assertRaisesRegex(ValueError, 'lumerical session actions: inspect_project, solve_project'):
                jobs.submit([{'id': 'a', 'tool': 'lumerical', 'action': 'spectrum'}], path=home)


@unittest.skipUnless(SCIENCE, 'Set OPTICS_SCIENCE_TESTS=1 in the scientific environment')
class ProgramPhysicsCase(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.count = 0

    def run_program(self, tool, name, inputs=None):
        self.count += 1
        return programs.run(tool, name, inputs or {}, Path(self.folder.name) / f'{tool}-{name}-{self.count}')

    def test_every_program_runs_with_its_defaults(self):
        for tool, items in programs.catalog().items():
            if not all(map(installed, catalogue.connections()[tool]['modules'])):
                continue  # Meep and MPB come from conda-forge, outside this environment
            for name in items:
                with self.subTest(program=tool + '/' + name):
                    result = self.run_program(tool, name)
                    json.dumps(result, allow_nan=False)
                    for file in [result['data']] if isinstance(result.get('data'), str) else result.get('data') or []:
                        self.assertTrue(any(Path(self.folder.name).glob('*/' + file)), file)

    def test_thin_films_agree_between_solvers_and_vanish_for_a_quarter_wave_coating(self):
        for polarization in ('s', 'p'):
            for angle in (0, 35):
                film = self.run_program('tmm', 'spectrum', {'n': [1, 1.45, 1.52], 'thickness_nm': [100], 'wavelength_nm': [550],
                                                            'angle_deg': angle, 'polarization': polarization})
                rcwa = self.run_program('grcwa', 'film', {'epsilon': [1, 1.45 ** 2, 1.52 ** 2], 'thickness_over_wavelength': [0, 100 / 550, 0],
                                                          'angle_deg': angle, 'polarization': polarization})
                self.assertAlmostEqual(film['first'][1], rcwa['R'], places=10)
                self.assertAlmostEqual(rcwa['R'] + rcwa['T'], 1, places=10)
        coating = self.run_program('tmm', 'spectrum', {'n': [1, math.sqrt(1.52), 1.52], 'thickness_nm': [550 / (4 * math.sqrt(1.52))],
                                                       'wavelength_nm': [550]})
        self.assertLess(coating['first'][1], 1e-12)
        # A named material is looked up at each wavelength.
        from optics_photonics import materials
        named = self.run_program('tmm', 'spectrum', {'n': [1, 'SiO2', 1.52], 'thickness_nm': [100], 'wavelength_nm': [633]})
        number = self.run_program('tmm', 'spectrum', {'n': [1, materials.index_at('SiO2', 0.633).real, 1.52], 'thickness_nm': [100],
                                                      'wavelength_nm': [633]})
        self.assertAlmostEqual(named['first'][1], number['first'][1], places=12)
        self.assertEqual(named['materials'], {'SiO2': 'main/SiO2/Malitson'})

    def test_lamellar_grating_conserves_power_and_reaches_the_film_and_effective_medium_limits(self):
        for polarization in ('te', 'tm'):
            grating = self.run_program('grcwa', 'grating', {'polarization': polarization})
            self.assertLess(grating['checks']['energy_error'], 1e-10)
            self.assertAlmostEqual(grating['first_wavelength']['transmitted'][1], grating['first_wavelength']['transmitted'][-1], places=10)
        uniform = self.run_program('grcwa', 'grating', {'fill_factor': 1.0, 'ridge': 1.8, 'depth_um': 0.25, 'wavelength_um': [0.6], 'orders': 11})
        film = self.run_program('tmm', 'spectrum', {'n': [1, 1.8, 1.5], 'thickness_nm': [250], 'wavelength_nm': [600]})
        self.assertAlmostEqual(uniform['R'][0], film['first'][1], places=10)
        # A period far below the wavelength acts as a film of the effective-medium index (TE: E along the lines).
        fine = self.run_program('grcwa', 'grating', {'period_um': 0.02, 'fill_factor': 0.5, 'depth_um': 0.2, 'ridge': 2.0, 'groove': 1.0,
                                                     'substrate': 1.5, 'wavelength_um': [1.0], 'orders': 81, 'grid': 2048})
        effective = self.run_program('tmm', 'spectrum', {'n': [1, math.sqrt(2.5), 1.5], 'thickness_nm': [200], 'wavelength_nm': [1000]})
        self.assertAlmostEqual(fine['R'][0], effective['first'][1], delta=2e-4)

    def test_mie_scattering_reaches_the_rayleigh_limit_and_integrates_to_the_cross_section(self):
        import numpy as np
        lossless = self.run_program('miepython', 'sphere', {'index': [1.5, 0], 'diameter_nm': 200, 'wavelength_nm': [450, 550, 650]})
        self.assertLess(lossless['checks']['extinction_minus_scattering'], 1e-12)
        small = self.run_program('miepython', 'sphere', {'index': 1.5, 'diameter_nm': 10, 'wavelength_nm': [600]})
        x = math.pi * 10 / 600
        self.assertAlmostEqual(small['first'][2] / (8 / 3 * x ** 4 * ((1.5 ** 2 - 1) / (1.5 ** 2 + 2)) ** 2), 1, delta=1e-3)
        angles = list(np.linspace(0, 180, 721))
        pattern = self.run_program('miepython', 'sphere', {'index': [1.5, 0], 'diameter_nm': 500, 'wavelength_nm': [600], 'angles_deg': angles})
        folder = Path(self.folder.name) / f'miepython-sphere-{self.count}'
        with np.load(folder / pattern['data']) as arrays:
            radians = np.radians(arrays['angle_deg'])
            integral = np.trapezoid(arrays['dCsca_dOmega'][0] * 2 * np.pi * np.sin(radians), radians)
            self.assertAlmostEqual(integral / arrays['Csca'][0], 1, delta=1e-4)

    def test_point_spread_functions_match_the_airy_pattern_and_marechal(self):
        # 1 - J0(3.8317)^2 at the first dark ring; pupil pixelation adds a little, falling as samples grow.
        hcipy = self.run_program('hcipy', 'psf', {'samples': 512, 'pixels_per_lambda_over_d': 16})
        self.assertAlmostEqual(hcipy['encircled_energy_1_22'], 0.8378, delta=2e-3)
        aberrated = self.run_program('hcipy', 'psf', {'obstruction': 0, 'zernike_rms_nm': {'4': 25}})
        self.assertAlmostEqual(aberrated['strehl'], math.exp(-(2 * math.pi * 25e-9 / 550e-9) ** 2), delta=3e-3)
        poppy = self.run_program('poppy', 'psf', {'zernike_rms_nm': {'4': 25}})
        self.assertAlmostEqual(poppy['strehl'], aberrated['strehl'], delta=5e-3)

    def test_gaussian_beam_radius_follows_the_analytic_law(self):
        result = self.run_program('lightpipes', 'gaussian', {'distance_m': [0, 1, 5, 10]})
        self.assertLess(result['checks']['radius_error'], 1e-6)

    def test_quantum_optics_reproduces_rabi_vacuum_rabi_and_mollow_physics(self):
        rabi = self.run_program('qutip', 'rabi')
        self.assertAlmostEqual(rabi['maximum'], 1, places=7)
        self.assertLess(rabi['checks']['analytic_error'], 1e-8)
        coupled = self.run_program('qutip', 'jaynes_cummings')
        self.assertLess(coupled['checks']['one_excitation_error'], 1e-5)
        fluorescence = self.run_program('qutip', 'resonance_fluorescence')
        self.assertLess(fluorescence['checks']['population_error'], 1e-10)
        self.assertLess(fluorescence['checks']['g2_zero'], 1e-6)

    def test_fresnel_derivation_matches_numbers_and_identities(self):
        result = self.run_program('sympy', 'fresnel', {'n1': 1, 'n2': 1.5, 'angle_deg': 30})
        self.assertTrue(result['checks']['brewster_identity'])
        self.assertAlmostEqual(result['brewster_deg'], math.degrees(math.atan(1.5)), places=10)
        cos_t = math.sqrt(1 - (math.sin(math.radians(30)) / 1.5) ** 2)
        cos_i = math.cos(math.radians(30))
        rs = (cos_i - 1.5 * cos_t) / (cos_i + 1.5 * cos_t)
        self.assertAlmostEqual(result['power']['R_s'], rs ** 2, places=12)
        abcd = self.run_program('sympy', 'abcd')
        self.assertEqual(abcd['determinant'], '1')

    def test_fiber_soliton_and_waveguide_modes_match_analytic_solutions(self):
        soliton = self.run_program('scipy', 'nlse')
        self.assertLess(soliton['checks']['energy_error'], 1e-9)
        self.assertLess(soliton['checks']['soliton_shape_error'], 1e-4)
        slab = self.run_program('scipy', 'slab_modes')
        self.assertLess(slab['checks']['analytic_error'], 2e-4)
        laser = self.run_program('scipy', 'laser_rates')
        self.assertLess(laser['checks']['threshold_error'], 1e-3)
        self.assertLess(laser['checks']['slope_error'], 1e-3)

    def test_ray_optics_and_polarization(self):
        abcd = self.run_program('raytracing', 'abcd', {'elements': [{'space_m': 0.1}, {'focal_length_m': 0.05}, {'space_m': 0.1}], 'ray': [0.001, 0]})
        self.assertAlmostEqual(abcd['ray_out'][0], -0.001, places=12)
        self.assertAlmostEqual(abcd['matrix'][0][1], 0, places=12)
        trace = self.run_program('optiland', 'trace')
        xy = trace['image_xy_mm']
        self.assertEqual(trace['finite_intersections'], 5)
        self.assertAlmostEqual(xy[1][1], -xy[2][1], places=12)
        self.assertAlmostEqual(abs(xy[1][1]), abs(xy[3][0]), places=12)
        for angle in (0, 30, 45, 90):
            result = self.run_program('py-pol', 'polarization', {'elements': [{'type': 'polarizer', 'azimuth_deg': angle}]})
            self.assertAlmostEqual(result['intensity'], math.cos(math.radians(angle)) ** 2, places=12)
        circular = self.run_program('py-pol', 'polarization', {'elements': [{'type': 'quarter_waveplate', 'azimuth_deg': 45}]})
        ex, ey = [complex(*v) for v in circular['jones_xy']]
        self.assertAlmostEqual(abs(ex), abs(ey), places=12)
        self.assertAlmostEqual((ex * ey.conjugate()).real, 0, places=12)

    def test_photonic_crystal_gap_of_the_rod_lattice(self):
        bands = self.run_program('legume', 'bands', {'structure': 'rods', 'epsilon': 8.9, 'hole_radius_over_period': 0.2,
                                                     'thickness_over_period': None, 'polarization': 'tm', 'gmax': 6})
        gap = bands['gaps'][0]
        self.assertEqual(gap['bands'], [1, 2])
        self.assertAlmostEqual(gap['from'], 0.3225, delta=2e-3)
        self.assertAlmostEqual(gap['to'], 0.4425, delta=2e-3)

    def test_layouts_are_readable_gds(self):
        import klayout.db as kdb
        result = self.run_program('gdsfactory', 'waveguide', {'length_um': 20, 'width_um': 0.5})
        layout = kdb.Layout()
        layout.read(str(next(Path(self.folder.name).glob('gdsfactory-*/' + result['data']))))
        box = layout.top_cell().bbox()
        self.assertAlmostEqual(box.width() * layout.dbu, 20, places=9)
        self.assertAlmostEqual(box.height() * layout.dbu, 0.5, places=9)
        self.assertEqual({port['name'] for port in result['ports']}, {'o1', 'o2'})


@unittest.skipUnless(SCIENCE and installed('meep'), 'Meep and MPB come from conda-forge')
class MeepCase(unittest.TestCase):
    def run_program(self, tool, name, inputs):
        with tempfile.TemporaryDirectory() as folder:
            return programs.run(tool, name, inputs, folder)

    def test_fdtd_stack_converges_to_the_transfer_matrix(self):
        coarse = self.run_program('meep', 'stack', {'resolution': 100})
        fine = self.run_program('meep', 'stack', {'resolution': 200})
        self.assertLess(fine['checks']['energy_error'], 1e-4)
        self.assertLess(fine['checks']['tmm_difference'], 1e-3)
        self.assertAlmostEqual(coarse['checks']['tmm_difference'] / fine['checks']['tmm_difference'], 4, delta=0.5)

    def test_ring_modes_and_rod_lattice_gap(self):
        modes = self.run_program('meep', 'ring', {})['modes']
        self.assertEqual([round(mode['frequency'], 3) for mode in modes], [0.118, 0.147, 0.175])
        self.assertLess(modes[0]['Q'], modes[1]['Q'])
        bands = self.run_program('mpb', 'bands', {'resolution': 32})
        gap = bands['gaps']['tm'][0]
        self.assertAlmostEqual(gap['from'], 0.3225, delta=2e-3)
        self.assertAlmostEqual(gap['to'], 0.4425, delta=2e-3)


if __name__ == '__main__':
    unittest.main()
