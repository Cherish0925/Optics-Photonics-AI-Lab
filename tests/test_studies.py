"""Parameter sweeps as parallel steps, their table, and optimization inside one process."""
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from optics_photonics import arrays, environments, jobs, optimization, studies  # noqa: E402
from support import workspace  # noqa: E402

# A standard-library model: a smooth bowl, a step that fails, and a list input addressed by position.
MODEL = '''import math
x, y = INPUTS["x"], INPUTS.get("y", 0.0)
if x > INPUTS.get("fail_above", math.inf):
    raise ValueError("outside the model")
(OUTPUT_DIR / "value.txt").write_text(str(x))
RESULT = {"f": (x - 3) ** 2 + (y + 1) ** 2, "g": [x * INPUTS["scale"][0], -x], "label": "point"}
'''


def finish(run_id, home):
    for _ in range(40):
        state = jobs.status(run_id, path=home, wait=25, include_results=False)
        if state['state'] not in ('queued', 'running'):
            return state
    raise AssertionError('run did not finish: ' + run_id)


def connect(home):
    environments.register('bowl', 'bowl', 'A standard-library model', modules=['json'], path=home)
    environments.bind('bowl', python=sys.executable, concurrency=4, path=home)


class SweepDefinitionCase(unittest.TestCase):
    def test_values_are_lists_or_ranges(self):
        self.assertEqual(studies.swept([1, 'a'], 'x'), [1, 'a'])
        self.assertEqual(studies.swept({'start': 0, 'stop': 10, 'points': 6}, 'x'), [0, 2, 4, 6, 8, 10])
        self.assertEqual(studies.swept({'start': 0, 'stop': 1, 'points': 3}, 'x'), [0, 0.5, 1])
        logarithmic = studies.swept({'start': 1, 'stop': 100, 'points': 3, 'scale': 'log'}, 'x')
        self.assertAlmostEqual(logarithmic[1], 10, places=12)
        with self.assertRaisesRegex(ValueError, 'x: a logarithmic range needs positive start and stop'):
            studies.swept({'start': 0, 'stop': 1, 'points': 3, 'scale': 'log'}, 'x')
        with self.assertRaisesRegex(ValueError, 'give a nonempty list'):
            studies.swept([], 'x')

    def test_a_key_addresses_one_element_of_an_input_or_its_default(self):
        inputs = {'n': [1, 1.45, 1.52]}
        studies.assign(inputs, 'n.1', 2.0)
        self.assertEqual(inputs['n'], [1, 2.0, 1.52])
        layered = {}
        studies.assign(layered, 'layers.0.n', 3.5, defaults={'layers': [{'n': 3.476, 'thickness_um': 0.22}]})
        self.assertEqual(layered, {'layers': [{'n': 3.5, 'thickness_um': 0.22}]})
        with self.assertRaisesRegex(ValueError, 'n.5: 5 is not a position in a list of 3'):
            studies.assign(inputs, 'n.5', 1)
        with self.assertRaisesRegex(ValueError, 'width.0: width is not among the inputs'):
            studies.assign(inputs, 'width.0', 1)
        self.assertEqual(studies.pick({'a': [{'b': 4}]}, 'a.0.b'), 4)
        self.assertIsNone(studies.pick({'a': [1]}, 'a.3'))

    def test_points_are_every_combination_or_paired(self):
        product = studies.expand({'tool': 't', 'inputs': {'scale': [1]}}, {'x': [1, 2, 3], 'scale.0': [10, 20]})
        self.assertEqual([step['id'] for step in product][:2], ['point-0001', 'point-0002'])
        self.assertEqual(len(product), 6)
        self.assertEqual(product[1]['inputs'], {'scale': [20], 'x': 1})
        self.assertEqual(product[1]['point'], {'x': 1, 'scale.0': 20})
        paired = studies.expand({'tool': 't'}, {'x': [1, 2], 'y': [5, 6]}, 'zip', first=7)
        self.assertEqual([(step['id'], step['point']) for step in paired], [('point-0007', {'x': 1, 'y': 5}), ('point-0008', {'x': 2, 'y': 6})])
        with self.assertRaisesRegex(ValueError, 'pairing zip takes lists of equal length'):
            studies.expand({'tool': 't'}, {'x': [1, 2], 'y': [5]}, 'zip')
        with self.assertRaisesRegex(ValueError, '20000 points; submit at most 10000'):
            studies.expand({'tool': 't'}, {'x': list(range(200)), 'y': list(range(100))})

    def test_a_sweep_of_a_packaged_program_is_checked_at_submission(self):
        with workspace() as home:
            with self.assertRaisesRegex(ValueError, 'tmm/spectrum has no input thickness'):
                studies.submit('tmm', action='spectrum', sweep={'thickness': [1, 2]}, path=home)
            with self.assertRaisesRegex(ValueError, 'thickness_nm.3: 3 is not a position in a list of 1'):
                studies.submit('tmm', action='spectrum', sweep={'thickness_nm.3': [1, 2]}, path=home)


class SweepRunCase(unittest.TestCase):
    def test_a_sweep_runs_in_parallel_and_its_table_finds_the_best_point(self):
        with workspace() as home:
            connect(home)
            first = studies.submit('bowl', source=MODEL, inputs={'scale': [2], 'fail_above': 5.5},
                                   sweep={'x': {'start': 0, 'stop': 6, 'points': 13}, 'y': [-2, -1, 0]}, request_id='bowl-1', path=home)
            self.assertEqual(finish(first['run_id'], home)['counts'], {'succeeded': 36, 'failed': 3})
            table = studies.table(first['run_id'], values=['f', 'g.0', 'label'], minimize='f', save=True, limit=5, path=home)
            self.assertEqual((table['points'], table['swept'], table['states']), (39, ['x', 'y'], {'succeeded': 36, 'failed': 3}))
            self.assertEqual((table['best']['point'], table['best']['values']['f']), ({'x': 3.0, 'y': -1}, 0.0))
            self.assertEqual((table['layout'], table['not_saved']), ('grid', ['label']))
            folder = Path(home) / 'runs' / first['run_id']
            grid = arrays.read(folder / 'sweep.npz', member='f', index=[None, 1])
            self.assertEqual(grid['result_shape'], [13])
            self.assertEqual(grid['values'][6], 0.0)
            self.assertEqual(grid['values'][-1], 'nan')  # x = 6 failed
            self.assertEqual(grid['at'], [{'name': 'y', 'value': -1}])
            self.assertEqual(next(axis['values'] for axis in grid['axes'] if axis['name'] == 'x')[:3], [0, 0.5, 1])
            # A refinement appended to the run; retrying the same request adds nothing.
            for _ in range(2):
                again = studies.submit('bowl', source=MODEL, inputs={'scale': [2], 'y': -1}, sweep={'x': [2.9, 3.1]},
                                       run_id=first['run_id'], request_id='bowl-2', path=home)
            self.assertEqual(again['run_id'], first['run_id'])
            finish(first['run_id'], home)
            refined = studies.table(first['run_id'], values=['f'], maximize='f', save=True, offset=39, path=home)
            self.assertEqual([(row['step'], row['point']) for row in refined['rows']],
                             [('point-0040', {'x': 2.9, 'y': -1}), ('point-0041', {'x': 3.1, 'y': -1})])
            self.assertEqual(refined['layout'], 'list')
            self.assertEqual(refined['best']['point'], {'x': 0.0, 'y': -2})
            with self.assertRaisesRegex(ValueError, 'has no sweep points'):
                single = jobs.submit([{'id': 'one', 'tool': 'bowl', 'source': MODEL, 'inputs': {'x': 1, 'scale': [1]}}], path=home)
                studies.table(single['run_id'], path=home)


class OptimizationCase(unittest.TestCase):
    def evaluate(self, inputs, folder):
        namespace = {'INPUTS': inputs, 'OUTPUT_DIR': Path(folder), 'RESULT': None}
        exec(MODEL, namespace)
        return namespace['RESULT']

    def test_both_methods_find_the_minimum_within_bounds_and_keep_the_best_files(self):
        for method in ('differential-evolution', 'nelder-mead'):
            with tempfile.TemporaryDirectory() as folder:
                spec = {'variables': {'x': [0, 10], 'y': {'low': -4, 'high': 4}}, 'minimize': 'f', 'method': method, 'evaluations': 400}
                result = optimization.run(self.evaluate, {'x': 1.0, 'scale': [1]}, spec, folder)
                self.assertAlmostEqual(result['best']['x'], 3, delta=1e-3, msg=method)
                self.assertAlmostEqual(result['best']['y'], -1, delta=1e-3, msg=method)
                self.assertEqual((Path(folder) / 'best' / 'value.txt').read_text(), str(result['best']['x']))
                self.assertFalse((Path(folder) / 'evaluations').exists())
                lines = (Path(folder) / 'history.jsonl').read_text().splitlines()
                self.assertEqual(len(lines), result['evaluations'])
                trace = arrays.read(Path(folder) / 'history.npz', member='best_so_far', max_elements=100000)['values']
                self.assertTrue(all(a >= b for a, b in zip(trace, trace[1:])))
                self.assertEqual(trace[-1], result['objective']['value'])

    def test_failures_integers_logarithmic_scales_and_maximization(self):
        with tempfile.TemporaryDirectory() as folder:
            spec = {'variables': {'x': {'low': 0, 'high': 9, 'integer': True}, 'scale.0': {'low': 0.1, 'high': 10, 'scale': 'log'}},
                    'maximize': 'g.0', 'evaluations': 200, 'seed': 3}
            result = optimization.run(self.evaluate, {'x': 0, 'scale': [1], 'fail_above': 7}, spec, folder)
            self.assertEqual(result['best']['x'], 7)  # 8 and 9 fail
            self.assertAlmostEqual(result['best']['scale.0'], 10, delta=0.05)
            self.assertGreater(result['failed'], 0)
            errors = [json.loads(line) for line in (Path(folder) / 'history.jsonl').read_text().splitlines()]
            self.assertIn('ValueError: outside the model', next(entry['error'] for entry in errors if 'error' in entry))
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'scale.2: 2 is not a position in a list of 1'):
                optimization.run(self.evaluate, {'x': 0, 'scale': [1]}, {'variables': {'scale.2': [0, 1]}, 'minimize': 'f'}, folder)
            self.assertFalse((Path(folder) / 'history.jsonl').exists())
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError, 'All 5 evaluations failed; the last: ValueError: RESULT has no finite number at h'):
                optimization.run(self.evaluate, {'x': 0, 'scale': [1]}, {'variables': {'x': [0, 1]}, 'minimize': 'h', 'evaluations': 5}, folder)

    def test_requests_are_checked_before_anything_runs(self):
        for spec, message in (({'variables': {'x': [1, 0]}, 'minimize': 'f'}, 'low < high'),
                              ({'variables': {'x': [0, 1]}}, 'needs minimize or maximize'),
                              ({'variables': {'x': [0, 1]}, 'minimize': 'f', 'method': 'bfgs'}, 'differential-evolution or nelder-mead'),
                              ({'variables': {'x': {'low': -1, 'high': 1, 'scale': 'log'}}, 'minimize': 'f'}, 'log needs low > 0')):
            with self.assertRaisesRegex(ValueError, message):
                optimization.checked(spec)
        with workspace() as home:
            with self.assertRaisesRegex(ValueError, 'tmm/spectrum has no input width'):
                studies.submit('tmm', action='spectrum', optimize={'variables': {'width': [0, 1]}, 'minimize': 'first.1'}, path=home)

    def test_an_optimization_runs_as_one_background_step(self):
        with workspace() as home:
            connect(home)
            run = studies.submit('bowl', source=MODEL, inputs={'x': 1, 'scale': [1]},
                                 optimize={'variables': {'x': [0, 10], 'y': [-4, 4]}, 'minimize': 'f', 'evaluations': 300}, path=home)
            state = finish(run['run_id'], home)
            self.assertEqual(state['state'], 'succeeded', state)
            result = jobs.status(run['run_id'], path=home)['steps'][0]['result']['result']
            self.assertLess(result['objective']['value'], 1e-6)
            files = {item['file'] for item in jobs.files(run['run_id'], path=home)['files']}
            self.assertTrue({'calculate/attempt-1/best/value.txt', 'calculate/attempt-1/history.npz'} <= files, files)


@unittest.skipUnless(__import__('os').environ.get('OPTICS_SCIENCE_TESTS') == '1', 'Set OPTICS_SCIENCE_TESTS=1 in the scientific environment')
class CoatingDesignCase(unittest.TestCase):
    def test_optimized_broadband_coating_beats_a_fine_grid(self):
        from optics_photonics import programs
        import numpy as np
        import tmm
        inputs = {'n': [1, 1.38, 2.1, 1.52], 'thickness_nm': [100, 100], 'wavelength_nm': {'start': 450, 'stop': 650, 'points': 21}}
        with tempfile.TemporaryDirectory() as folder:
            result = optimization.run(lambda given, out: programs.run('tmm', 'spectrum', given, out), inputs,
                                      {'variables': {'thickness_nm.0': [0, 300], 'thickness_nm.1': [0, 300]}, 'minimize': 'mean.R',
                                       'evaluations': 600, 'seed': 1}, folder)
        wavelengths = np.linspace(450, 650, 21)

        def mean_reflectance(a, b):
            return np.mean([tmm.coh_tmm('s', inputs['n'], [np.inf, a, b, np.inf], 0, w)['R'] for w in wavelengths])
        grid = min(mean_reflectance(a, b) for a in range(0, 301, 10) for b in range(0, 301, 10))
        self.assertLess(result['objective']['value'], grid)
        best = result['best']
        self.assertAlmostEqual(mean_reflectance(best['thickness_nm.0'], best['thickness_nm.1']), result['objective']['value'], places=12)


if __name__ == '__main__':
    unittest.main()
