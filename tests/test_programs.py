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
    def test_legacy_operation_discovery_delegates_to_the_same_programs(self):
        from optics_photonics import operations
        name, example = operations.EXAMPLES['scipy']
        self.assertEqual(name, 'fit_gaussian')
        self.assertEqual(example, programs.inputs(programs.catalog()['scipy'][name]))
        details = environments.details('scipy')['execution']
        self.assertEqual(details['operations'][0]['name'], name)
        self.assertTrue(details['operations'][0]['description'])
        self.assertEqual(details['operations'][0]['inputs_example'], example)
        found = catalogue.search('scipy')['items']
        for item in found:
            self.assertEqual(item['operations'], item['programs'])

    def test_every_program_declares_its_physics_inputs_and_results(self):
        connections = catalogue.connections()
        for tool, items in programs.catalog().items():
            # A program runs in its tool's Python environment, or drives the installed executable it is bound to.
            self.assertTrue(connections[tool]['kind'] == 'python' or any(route['route'] == 'executable' for route in connections[tool]['routes']), tool)
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
        self.assertEqual([item['name'] for item in listed['programs']], ['coupler', 'fiber_modes', 'fit_gaussian', 'laser_rates', 'metalens', 'nlse', 'resonator', 'second_harmonic', 'slab_modes'])
        nlse = next(item for item in listed['programs'] if item['name'] == 'nlse')
        self.assertEqual(nlse['inputs']['length_km']['default'], programs.catalog()['scipy']['nlse']['inputs']['length_km'][0])
        self.assertNotIn('about', nlse)   # the listing stays short; one program brings its physics and source
        one = environments.details('scipy', program='nlse')
        self.assertTrue(one['source'].startswith('"""Pulse propagation'))
        self.assertEqual((one['about'], one['inputs']['length_km']['default']),
                         (programs.catalog()['scipy']['nlse']['about'], nlse['inputs']['length_km']['default']))
        with self.assertRaisesRegex(ValueError, 'Unknown program scipy/fft; programs of scipy: coupler, fiber_modes, fit_gaussian'):
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
            record = catalogue.connections()[tool]
            if record['kind'] != 'python' or not all(map(installed, record['modules'])):
                continue  # Meep and MPB come from conda-forge, outside this environment; ADDA's program drives its executable
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

    def test_fiber_modes_are_roots_of_the_bessel_equations_and_give_standard_fiber_dispersion(self):
        # Weak guidance, constant indices: LP01 and LP11 against roots found with 40-digit arithmetic (mpmath).
        fixed = self.run_program('scipy', 'fiber_modes', {'cladding_index': 1.4469, 'wavelength_nm': [1200]})['first']
        self.assertAlmostEqual(fixed['lp']['LP01'], 1.4497386667402692566, places=13)
        self.assertAlmostEqual(fixed['lp']['LP11'], 1.4471099450579007644, places=13)
        self.assertEqual(fixed['vector']['TE01'], fixed['lp']['LP11'])  # TE0m and LP1m obey the same equation
        # High contrast: the exact vector modes, which MPB reproduces at second order in its resolution
        # (frequency mismatch 7e-4, 1.7e-4, 4e-5 at 16, 32, 64 points per um), and the LP modes far from them.
        nanofiber = self.run_program('scipy', 'fiber_modes', {'radius_um': 0.5, 'cladding_index': 1.0, 'core_index': 1.45,
                                                              'wavelength_nm': [1000]})
        self.assertEqual(list(nanofiber['first']['vector']), ['HE11', 'TE01', 'TM01', 'HE21'])
        for mode, value in {'HE11': 1.3091913072159653, 'TE01': 1.138624875571326, 'TM01': 1.0943671099797436, 'HE21': 1.0811637654943793}.items():
            self.assertAlmostEqual(nanofiber['first']['vector'][mode], value, places=12)
        self.assertGreater(nanofiber['checks']['vector_lp_difference'], 0.1)
        # With a constant numerical aperture V = 2 pi a NA / lambda, so LP11 sets in at 2 pi a NA / j01.
        smf = self.run_program('scipy', 'fiber_modes', {'wavelength_nm': [1550, 1600]})
        self.assertAlmostEqual(smf['lp11_cutoff_nm'], 2 * math.pi * 4100 * 0.12 / 2.404825557695773, places=6)
        self.assertLess(smf['checks']['confinement_difference'], 1e-10)
        self.assertLess(smf['checks']['vector_lp_difference'], 2e-3)
        # A fused-silica fiber with the numerical aperture and core of standard single-mode fiber at 1550 nm.
        fundamental = self.run_program('scipy', 'fiber_modes', {'wavelength_nm': [1550]})['fundamental']
        self.assertAlmostEqual(fundamental['dispersion_ps_per_nm_km'], 17, delta=0.5)
        self.assertAlmostEqual(fundamental['group_index'], 1.468, delta=1e-3)
        self.assertAlmostEqual(fundamental['mfd_um'], 10.2, delta=0.2)
        self.assertAlmostEqual(fundamental['beta2_ps2_per_km'], -1550e-9 ** 2 * fundamental['dispersion_ps_per_nm_km'] * 1e-6
                               / (2 * math.pi * 299792458) * 1e27, places=9)
        # A multimode fiber guides about V^2 / 2 modes.
        multimode = self.run_program('scipy', 'fiber_modes', {'radius_um': 25, 'numerical_aperture': 0.22, 'wavelength_nm': [850],
                                                              'vector': False})['first']
        self.assertAlmostEqual(multimode['guided_modes'] / (multimode['V'] ** 2 / 2), 1, delta=0.05)

    def test_the_fiber_feeds_its_dispersion_and_nonlinearity_to_a_pulse_propagation(self):
        from support import workspace
        guide = (Path(__file__).resolve().parents[1] / 'skills/optical-computation/references/programs.md').read_text(encoding='utf-8')
        steps = json.loads(guide.split('**Chaining programs.**')[1].split('```json')[1].split('```')[0])
        with workspace() as home:
            environments.bind('scipy', python=sys.executable, path=home)
            run = jobs.submit(steps, path=home)['run_id']
            for _ in range(20):
                state = jobs.status(run, path=home, wait=25)
                if state['state'] not in ('queued', 'running'):
                    break
            self.assertEqual(state['state'], 'succeeded', state)
            fiber, pulse = (step['result']['result'] for step in state['steps'])
            fundamental = fiber['fundamental']
            # N = sqrt(gamma P0 T0^2 / |beta2|) with the fiber's own beta2 and gamma, T0 = 1 ps.
            self.assertAlmostEqual(pulse['soliton_order'], math.sqrt(fundamental['gamma_per_W_km'] * 16 / abs(fundamental['beta2_ps2_per_km'])), places=12)

    def test_a_lens_has_its_paraxial_focal_length_and_third_order_spherical_aberration(self):
        # Cooke triplet: 50 mm at f/4; chief rays reach f tan(theta); real rays approach the Seidel spherical aberration.
        triplet = self.run_program('optiland', 'lens')
        self.assertAlmostEqual(triplet['first_order']['efl_mm'], 50.0, delta=0.01)
        self.assertAlmostEqual(triplet['first_order']['f_number'], 4.0, delta=1e-3)
        self.assertAlmostEqual(triplet['spots'][-1]['centroid_y_mm'] / (50.0 * math.tan(math.radians(20))), 1, delta=1e-3)
        self.assertLess(triplet['checks']['focal_length_difference'], 1e-12)
        self.assertLess(triplet['checks']['spherical_difference'], 1e-4)
        # A thick biconvex singlet: the lensmaker's equation.
        n, r1, r2, d = 1.5, 50.0, -40.0, 6.0
        singlet = self.run_program('optiland', 'lens', {
            'surfaces': [{'radius_mm': None, 'thickness_mm': None}, {'radius_mm': r1, 'thickness_mm': d, 'index': n, 'stop': True},
                         {'radius_mm': r2, 'thickness_mm': 40}, {'radius_mm': None, 'thickness_mm': 0}],
            'aperture_mm': 5, 'fields_deg': [0, 2], 'wavelengths_um': [0.55], 'primary_um': 0.55})
        power = (n - 1) * (1 / r1 - 1 / r2 + (n - 1) * d / (n * r1 * r2))
        self.assertAlmostEqual(singlet['first_order']['efl_mm'], 1 / power, places=9)

    def test_a_resonator_mode_agrees_with_the_two_mirror_formulas(self):
        # Half-symmetric cavity, g1 g2 = 1/2: mode spacing 1/4 FSR, waist on the flat mirror, sqrt(2) larger spot on the curved one.
        half = self.run_program('scipy', 'resonator', {})
        self.assertAlmostEqual(half['transverse_mode_spacing_fsr'], 0.25, places=12)
        self.assertAlmostEqual(half['spot_mirror2_um'] / half['spot_mirror1_um'], math.sqrt(2), places=12)
        self.assertAlmostEqual(half['waist_um'], math.sqrt(1.064e-3 * 500 / math.pi) * 1e3, places=9)
        # Near-concentric, a convex-concave and a lens-guide cavity; the closed forms hold where they apply.
        for cavity in ({'r1_mm': 260, 'r2_mm': 260}, {'r1_mm': -2000, 'r2_mm': 400, 'length_mm': 300}):
            self.assertLess(self.run_program('scipy', 'resonator', cavity)['checks']['two_mirror_difference'], 1e-12)
        guide = self.run_program('scipy', 'resonator', {'elements': [{'space_mm': 250}, {'lens_mm': 500}, {'space_mm': 250}, {'mirror_mm': None}] * 2})
        self.assertAlmostEqual(guide['transverse_mode_spacing_fsr'], 1 / 3, places=12)   # cos(Gouy) = (A + D) / 2 = -1/2
        self.assertFalse(self.run_program('scipy', 'resonator', {'r1_mm': 200, 'r2_mm': 200})['stable'])

    def test_a_unit_cell_library_becomes_a_metalens_that_focuses(self):
        ideal = self.run_program('scipy', 'metalens')
        self.assertAlmostEqual(ideal['airy_ratio'], 1, delta=0.03)       # NA 0.45: within 3 % of 0.514 lambda / NA
        self.assertAlmostEqual(ideal['strehl'], 1, delta=1e-3)
        self.assertLess(ideal['checks']['energy_error'], 1e-12)
        tight = self.run_program('scipy', 'metalens', {'aperture_um': 25.6, 'window': 1})
        self.assertLess(tight['checks']['energy_error'], 1e-12)
        json.dumps(tight, allow_nan=False)
        from support import workspace
        guide = (Path(__file__).resolve().parents[1] / 'skills/optical-computation/references/programs.md').read_text(encoding='utf-8')
        steps = json.loads(guide.split('A file passes the same way')[1].split('```json')[1].split('```')[0])
        steps[0]['inputs'] = {'diameters_um': {'start': 0.1, 'stop': 0.5, 'points': 21}, 'orders': 121, 'grid': 128}   # a quicker library
        with workspace() as home:
            for tool in ('grcwa', 'scipy'):
                environments.bind(tool, python=sys.executable, path=home)
            run = jobs.submit(steps, path=home)['run_id']
            for _ in range(20):
                state = jobs.status(run, path=home, wait=25)
                if state['state'] not in ('queued', 'running'):
                    break
            self.assertEqual(state['state'], 'succeeded', state)
            lens = state['steps'][1]['result']['result']
            self.assertGreater(lens['strehl'], 0.8)
            self.assertGreater(lens['focusing_efficiency'], 0.6)
            self.assertAlmostEqual(lens['airy_ratio'], 1, delta=0.05)

    def test_second_harmonic_phase_matching_and_conversion(self):
        from optics_photonics import materials
        # BBO, type I (ooe) at 1064 nm: the phase-matching angle 22.8 degrees and walk-off 3.19 degrees of the literature.
        bbo = self.run_program('scipy', 'second_harmonic', {})
        self.assertAlmostEqual(bbo['angle_deg'], 22.8, delta=0.1)
        self.assertAlmostEqual(math.degrees(bbo['walkoff_mrad'] / 1000), 3.19, delta=0.03)
        self.assertAlmostEqual(bbo['indices']['fundamental'], bbo['indices']['harmonic'], places=12)
        # Angle acceptance from the linear mismatch: d(delta k)/d(theta) = (4 pi / lambda) n_e(theta) tan(rho).
        slope = 4 * math.pi / 1.064 * bbo['indices']['harmonic'] * math.tan(bbo['walkoff_mrad'] / 1000)
        self.assertAlmostEqual(bbo['acceptance']['angle_mrad'] / 1000, 4 * 1.3915573782515103 / (5000 * slope), delta=1e-6)
        # The integrated conversion: tanh^2 at phase matching, sinc^2 without depletion.
        self.assertAlmostEqual(bbo['efficiency'], math.tanh(math.sqrt(bbo['eta0'])) ** 2, places=9)
        self.assertLess(abs(bbo['checks']['depletion_difference']), 1e-9)
        self.assertLess(abs(bbo['checks']['undepleted_difference']), 1e-6)
        # Periodically poled lithium niobate: the period lambda / (2 (n_e(lambda/2) - n_e(lambda))).
        ppln = self.run_program('scipy', 'second_harmonic', {'interaction': 'quasi', 'ordinary_index': 'LiNbO3-o',
                                                             'extraordinary_index': 'LiNbO3-e', 'd_eff_pm_per_V': 14, 'length_mm': 10})
        n1, n2 = (materials.index_at('LiNbO3-e', wavelength).real for wavelength in (1.064, 0.532))
        self.assertAlmostEqual(ppln['period_um'], 1.064 / (2 * (n2 - n1)), places=12)
        self.assertNotIn('angle_mrad', ppln['acceptance'])
        detuned = self.run_program('scipy', 'second_harmonic', {'interaction': 'quasi', 'ordinary_index': 'LiNbO3-o', 'extraordinary_index': 'LiNbO3-e',
                                                                'length_mm': 10, 'intensity_MW_per_cm2': 1e-3, 'period_um': ppln['period_um'] * 1.0002})
        mismatch = 2 * math.pi / ppln['period_um'] - 2 * math.pi / (ppln['period_um'] * 1.0002)
        expected = detuned['eta0'] * (math.sin(mismatch * 5000) / (mismatch * 5000)) ** 2
        self.assertAlmostEqual(detuned['efficiency'] / expected, 1, delta=1e-5)
        type2 = self.run_program('scipy', 'second_harmonic', {'interaction': 'type II'})
        self.assertGreater(type2['angle_deg'], bbo['angle_deg'])
        self.assertIsNone(type2['efficiency'])

    def test_a_pillar_metasurface_covers_two_pi_with_high_transmission(self):
        library = self.run_program('grcwa', 'metasurface', {'diameters_um': {'start': 0.1, 'stop': 0.5, 'points': 21}, 'orders': 121, 'grid': 128})
        self.assertTrue(library['checks']['single_order'])
        self.assertLess(library['checks']['energy_error'], 1e-10)
        self.assertLess(library['checks']['fresnel_difference'], 1e-12)   # no pillars: the bare interface
        self.assertGreater(library['phase_coverage_rad'], 2 * math.pi)
        self.assertGreater(library['library_mean_transmission'], 0.85)
        self.assertEqual([entry['phase_rad'] for entry in library['library']], [2 * math.pi * k / 8 for k in range(8)])

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

    def test_zero_dispersion_and_nonlinearity_serialize_and_third_order_drift_has_the_declared_sign(self):
        import numpy as np
        from optics_photonics import data, worker
        folder = Path(self.folder.name)/'third-order'
        record = worker.execute('scipy', {'action': 'nlse', 'inputs': {'shape': 'gaussian', 'beta2_ps2_per_km': 0,
                                'beta3_ps3_per_km': 1, 'gamma_per_W_km': 0, 'length_km': 0.001, 'steps': 1}}, folder)
        self.assertIsNone(record['result']['dispersion_length_km'])
        self.assertIsNone(record['result']['nonlinear_length_km'])
        stored = data.load(folder/'pulse.npz')
        power, time_axis = stored['power'].values[-1], stored['time_ps'].values
        centre = float(np.sum(time_axis*power)/np.sum(power))
        # For a Gaussian, +(beta3/6) d^3 A/dT^3 gives <T> = beta3*z/(4*T0^2).
        self.assertAlmostEqual(centre, 0.00025, delta=1e-10)
        # A known positive physical offset exp(-i*2*pi*f*T) must appear at +f on the stored axis.
        source = programs.source('scipy', 'nlse').replace('w = 2 * np.pi * np.fft.fftfreq',
                                                       'A *= np.exp(-2j * np.pi * 0.5 * T)\nw = 2 * np.pi * np.fft.fftfreq', 1)
        offset = folder/'offset'
        worker.execute('scipy', {'source': source, 'inputs': {'beta2_ps2_per_km': 0, 'gamma_per_W_km': 0, 'steps': 1}}, offset)
        spectrum = data.load(offset/'pulse.npz')
        self.assertAlmostEqual(spectrum['frequency_THz'].values[np.argmax(spectrum['spectrum'].values[0])], 0.5)

    def test_ray_optics_and_polarization(self):
        abcd = self.run_program('raytracing', 'abcd', {'elements': [{'space_m': 0.1}, {'focal_length_m': 0.05}, {'space_m': 0.1}], 'ray': [0.001, 0]})
        self.assertAlmostEqual(abcd['ray_out'][0], -0.001, places=12)
        self.assertAlmostEqual(abcd['matrix'][0][1], 0, places=12)
        trace = self.run_program('optiland', 'trace')
        xy = trace['image_xy_mm']
        self.assertEqual(trace['finite_intersections'], 5)
        self.assertAlmostEqual(xy[1][1], -xy[2][1], places=12)
        self.assertAlmostEqual(abs(xy[1][1]), abs(xy[3][0]), places=12)
        positive = self.run_program('optiland', 'trace', {'field_deg': [0, 5]})['centroid_mm']
        negative = self.run_program('optiland', 'trace', {'field_deg': [0, -5]})['centroid_mm']
        self.assertAlmostEqual(positive[1], -negative[1], places=10)
        first = self.run_program('optiland', 'trace', {'field_deg': [3, 4]})['centroid_mm']
        swapped = self.run_program('optiland', 'trace', {'field_deg': [4, 3]})['centroid_mm']
        self.assertAlmostEqual(first[0], swapped[1], places=10)
        self.assertAlmostEqual(first[1], swapped[0], places=10)
        self.assertLess(first[0], first[1])
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


def environment(module):
    """Cases for a tool whose recipe installs it in an environment of its own; they run in that environment."""
    return unittest.skipUnless(SCIENCE and installed(module), module + ' is installed in its own environment')


def calculate(tool, name, inputs=None):
    with tempfile.TemporaryDirectory() as folder:
        return programs.run(tool, name, inputs or {}, folder)


@environment('sax')
class CircuitCase(unittest.TestCase):
    def test_a_balanced_interferometer_has_no_finite_spectral_period(self):
        result = calculate('sax', 'circuit', {'circuit': 'mzi', 'arm_difference_um': 0})
        self.assertIsNone(result['fsr_nm'])
        self.assertIsNone(result['fsr_expected_nm'])
        self.assertIsNone(result['checks']['fsr_error'])
        self.assertLess(result['checks']['analytic_difference'], 1e-10)
        json.dumps(result, allow_nan=False)

    def test_rings_and_interferometer_follow_their_transfer_functions(self):
        for circuit in ('ring', 'add_drop', 'mzi'):
            result = calculate('sax', 'circuit', {'circuit': circuit, 'wavelength_um': {'start': 1.5, 'stop': 1.6, 'points': 8001}})
            self.assertLess(result['checks']['analytic_difference'], 1e-10, circuit)
            self.assertLess(result['checks']['fsr_error'], 1e-3, circuit)
        # Critical coupling: the coupled power equals the round-trip loss and the through port goes dark.
        loss = 1 - 10 ** (-3.0 * 62.83185307179586e-4 / 10)
        dark = calculate('sax', 'circuit', {'coupling': loss, 'wavelength_um': {'start': 1.545, 'stop': 1.555, 'points': 20001}})
        self.assertGreater(dark['dips'][0]['extinction_db'], 30)

    def test_a_coupler_from_its_supermodes_sets_the_ring_response(self):
        from support import workspace
        guide = (Path(__file__).resolve().parents[1] / 'skills/optical-computation/references/programs.md').read_text(encoding='utf-8')
        steps = json.loads(guide.split('A device becomes a circuit')[1].split('```json')[1].split('```')[0])
        with workspace() as home:
            for tool in ('scipy', 'sax'):
                environments.bind(tool, python=sys.executable, path=home)
            run = jobs.submit(steps, path=home)['run_id']
            for _ in range(20):
                state = jobs.status(run, path=home, wait=25)
                if state['state'] not in ('queued', 'running'):
                    break
            self.assertEqual(state['state'], 'succeeded', state)
            coupler, ring = (step['result']['result'] for step in state['steps'])
            self.assertLess(coupler['checks']['cmt_difference'], 0.01)
            self.assertLess(ring['checks']['analytic_difference'], 1e-10)
            # The ring's free spectral range is lambda^2 / (ng L) with the coupler's group index, near 1.55 um.
            self.assertLess(ring['checks']['fsr_error'], 1e-3)
            self.assertAlmostEqual(ring['fsr_nm'] / (1.55 ** 2 / (coupler['ng_single'] * 60) * 1e3), 1, delta=0.01)


@environment('treams')
class ClusterCase(unittest.TestCase):
    def test_one_sphere_matches_the_mie_series_and_distant_spheres_do_not_couple(self):
        single = calculate('treams', 'cluster', {'spheres': [{'radius_nm': 250, 'index': 1.5}], 'wavelength_nm': [600], 'lmax': 8})
        self.assertLess(single['checks']['mie_difference'], 1e-10)
        self.assertAlmostEqual(single['first']['Cext'] / (math.pi * 250 ** 2), 2.840477, places=5)
        apart = calculate('treams', 'cluster', {'spheres': [{'radius_nm': 100, 'index': 1.5, 'position_nm': [0, 0, -5e4]},
                                                            {'radius_nm': 100, 'index': 1.5, 'position_nm': [0, 0, 5e4]}],
                                                'wavelength_nm': [600], 'average': False})
        self.assertAlmostEqual(apart['first']['coupling'], 1, delta=1e-3)
        dimer = calculate('treams', 'cluster')
        self.assertLess(dimer['checks']['energy_error'], 1e-10)


@environment('solcore')
class SolarCellCase(unittest.TestCase):
    def test_detailed_balance_peaks_near_1_34_ev(self):
        result = calculate('solcore', 'detailed_balance', {'band_gap_ev': {'start': 1.30, 'stop': 1.40, 'points': 11}})
        self.assertEqual(result['best']['band_gap_ev'], 1.34)
        self.assertAlmostEqual(result['best']['efficiency'], 0.331, delta=2e-3)
        self.assertAlmostEqual(result['best_back_mirror']['efficiency'], 0.337, delta=2e-3)
        self.assertLess(result['checks']['jsc_difference'], 5e-3)
        self.assertLess(result['checks']['voc_difference'], 5e-3)


@environment('optic')
class CommunicationCase(unittest.TestCase):
    def test_error_rates_follow_theory(self):
        qpsk = calculate('opticomm', 'ber', {'modulation': 'psk', 'order': 4, 'ebn0_db': [0, 4, 8]})
        bits = 2 * 200000
        for measured, ebn0 in zip(qpsk['ber'], (0, 4, 8)):
            expected = 0.5 * math.erfc(math.sqrt(10 ** (ebn0 / 10)))  # exact for Gray-coded QPSK
            self.assertLess(abs(measured - expected), 4 * math.sqrt(expected / bits), ebn0)  # four standard deviations of the count
        qam = calculate('opticomm', 'ber', {'ebn0_db': [6, 8, 10]})
        self.assertLess(qam['checks']['theory_difference'], 0.05)


@environment('finesse')
class CavityCase(unittest.TestCase):
    def test_cavities_follow_the_airy_function(self):
        for inputs in ({}, {'input_mirror': {'R': 0.9, 'T': 0.1}, 'end_mirror': {'R': 0.8, 'T': 0.15}, 'length_m': 0.1},
                       {'input_mirror': {'R': 0.5, 'T': 0.5}, 'end_mirror': {'R': 0.5, 'T': 0.5}}):
            result = calculate('finesse', 'cavity', inputs)
            self.assertLess(result['checks']['airy_difference'], 1e-12)
            self.assertLess(result['checks']['finesse_error'], 1e-4)
        symmetric = calculate('finesse', 'cavity')
        self.assertAlmostEqual(symmetric['buildup'], 100, places=6)
        self.assertAlmostEqual(symmetric['fsr_hz'], 299792458 / 2, places=3)


@environment('perceval')
class PhotonCase(unittest.TestCase):
    def test_two_photon_interference_and_permanents(self):
        hom = calculate('perceval', 'interference')
        self.assertAlmostEqual(hom['coincidence'], 0, places=12)
        partial = calculate('perceval', 'interference', {'indistinguishability': 0.9, 'reflectivity': 0.3})
        self.assertLess(partial['checks']['hom_difference'], 1e-12)
        for inputs in ({'interferometer': 'fourier', 'input_state': [1, 1, 1]},
                       {'interferometer': 'haar', 'input_state': [2, 1, 0, 1], 'seed': 3}):
            self.assertLess(calculate('perceval', 'interference', inputs)['checks']['permanent_difference'], 1e-12)


@environment('prysm')
class TransferFunctionCase(unittest.TestCase):
    def test_mtf_reaches_the_diffraction_limit_and_loses_contrast_with_aberration(self):
        perfect = calculate('prysm', 'mtf', {'samples': 512})
        self.assertLess(perfect['checks']['diffraction_limit_difference'], 2e-4)
        defocus = calculate('prysm', 'mtf', {'zernike_rms_nm': {'4': 25}})
        self.assertAlmostEqual(defocus['strehl'], math.exp(-(2 * math.pi * 25 / 550) ** 2), delta=2e-3)
        self.assertTrue(all(item['x'] < item['limit'] for item in defocus['mtf_at']))


@environment('diffractio')
class ApertureCase(unittest.TestCase):
    def test_far_field_patterns_follow_fraunhofer(self):
        for inputs, limit in (({}, 2e-3), ({'aperture': 'slit', 'distance_mm': [2000]}, 1e-4),
                              ({'aperture': 'grating', 'distance_mm': [20000], 'window_um': 40000, 'samples': 262144}, 2e-3)):
            result = calculate('diffractio', 'apertures', inputs)
            self.assertLess(result['checks']['fraunhofer_difference'], limit, inputs)


@environment('laserfun')
class FiberCase(unittest.TestCase):
    def test_supercontinuum_conserves_photons_and_a_fundamental_soliton_keeps_its_shape(self):
        broad = calculate('laserfun', 'supercontinuum')
        self.assertAlmostEqual(broad['soliton_order'], 8.65, delta=0.01)
        self.assertLess(broad['checks']['photon_number_error'], 1e-3)
        self.assertGreater(broad['output_width_nm_30db'], 600)
        soliton = calculate('laserfun', 'supercontinuum', {'raman': False, 'self_steepening': False, 'fwhm_ps': 1.0, 'wavelength_nm': 1550,
                                                           'peak_power_w': 1.5535556, 'length_m': 500, 'betas': [-0.02], 'gamma_per_w_m': 0.04,
                                                           'window_ps': 40, 'points': 4096})
        self.assertAlmostEqual(soliton['soliton_order'], 1, delta=1e-6)
        self.assertLess(soliton['checks']['energy_error'], 2e-3)
        self.assertAlmostEqual(soliton['output_peak_power_w'], 1.5535556, delta=0.01)


@environment('strawberryfields')
class SqueezingCase(unittest.TestCase):
    def test_squeezed_vacuum_matches_its_analytic_statistics(self):
        for inputs in ({}, {'transmission': 0.0}, {'transmission': 1.0}, {'squeezing': 0.3, 'transmission': 0.5}):
            self.assertLess(calculate('strawberry', 'gaussian_state', inputs)['checks']['analytic_difference'], 1e-10)
        displaced = calculate('strawberry', 'gaussian_state', {'displacement': [1.5, 0], 'squeezing': 0.3})
        self.assertLess(displaced['mandel_q'], 0)  # amplitude squeezing gives sub-Poissonian light


@environment('ceviche')
class InverseDesignCase(unittest.TestCase):
    def test_the_adjoint_gradient_is_exact_and_the_bend_learns_to_transmit(self):
        result = calculate('ceviche', 'bend', {'iterations': 12})
        self.assertLess(result['checks']['gradient_difference'], 1e-5)
        transmission = result['transmission']
        self.assertLess(transmission['start'], 0.1)
        self.assertGreater(transmission['end'], 0.9)
        self.assertGreater(transmission['binary'], 0.9)
        self.assertLess(transmission['binary'], 1 + 1e-6)   # normalized by a straight waveguide: nothing gains power


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

    def test_a_core_filling_the_cell_is_the_analytic_slab_mode(self):
        slab = 2.8477847997093733  # TE0 of 220 nm silicon in silica at 1.55 um, from the slab dispersion relation
        errors = [self.run_program('mpb', 'waveguide', {'width_um': 1.0, 'cell_um': [1.0, 3.0], 'modes': 1, 'resolution': res})['modes'][0]['neff'] - slab
                  for res in (32, 64)]
        self.assertAlmostEqual(errors[0] / errors[1], 4, delta=0.3)
        self.assertLess(abs(errors[1]), 4e-3)
        strip = self.run_program('mpb', 'waveguide', {})
        self.assertGreater(strip['modes'][0]['te_fraction'], 0.95)
        self.assertLess(strip['modes'][1]['te_fraction'], 0.1)
        self.assertLess(strip['checks']['edge_energy'], 1e-2)


if __name__ == '__main__':
    unittest.main()
