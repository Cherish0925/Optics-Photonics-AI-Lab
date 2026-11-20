"""Continue actual worker attempts and costly deterministic searches after interruption."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from optics_photonics import environments, execution, jobs, optimization, studies
from optics_photonics.progress import Checkpoint, identity
from support import workspace


PROGRAM = '''from pathlib import Path
state = CHECKPOINT.load({'next': 0, 'values': []})
files = dict(CHECKPOINT.files)
for name, file in files.items():
    assert file.read_text() == str(int(name) ** 2)
for i in range(state['next'], INPUTS['points']):
    with Path(INPUTS['calls']).open('a') as log:
        log.write(str(i) + '\\n')
    file = OUTPUT_DIR / ('point-' + str(i) + '.txt')
    file.write_text(str(i ** 2))
    files[str(i)] = file
    state['values'].append(i ** 2)
    state['next'] = i + 1
    CHECKPOINT.save(state, files=files)
    if i == 2 and CHECKPOINT.restored_from is None:
        raise RuntimeError('Pause after three completed points')
RESULT = {'values': state['values'], 'files': len(files)}
'''


def finish(run_id, home):
    for _ in range(20):
        result = jobs.status(run_id, path=home, wait=25)
        if result['state'] in jobs.TERMINAL:
            return result
    raise AssertionError('Calculation did not finish')


class ProgramContinuation(unittest.TestCase):
    def test_resume_uses_saved_position_and_previous_files_without_repeating_points(self):
        with workspace() as home:
            root = Path(home)
            environments.register('progress-model', 'Progress model', 'Standard-library calculation', modules=['json'], path=home)
            environments.bind('progress-model', python=sys.executable, path=home)
            step = {'id': 'series', 'tool': 'progress-model', 'source': PROGRAM,
                    'inputs': {'points': 6, 'calls': str(root / 'calls.txt')}}
            run = jobs.submit([step], path=home)['run_id']
            first = finish(run, home)
            self.assertEqual(first['state'], 'failed', first)
            progress = first['steps'][0]['progress'][0]
            self.assertEqual((progress['kind'], progress['files']), ('program', 3))
            stored = json.loads(jobs.read_result(run, progress['path'], path=home)['data'])
            self.assertEqual(stored['state']['next'], 3)
            original = (root / 'runs' / run / 'series' / 'attempt-1' / 'checkpoints' / 'program.json').read_bytes()
            jobs.resume(run, path=home)
            final = finish(run, home)
            self.assertEqual(final['state'], 'succeeded', final)
            self.assertEqual(final['steps'][0]['result']['result'], {'values': [0, 1, 4, 9, 16, 25], 'files': 6})
            self.assertEqual((root / 'calls.txt').read_text().splitlines(), ['0', '1', '2', '3', '4', '5'])
            self.assertEqual((root / 'runs' / run / 'series' / 'attempt-1' / 'checkpoints' / 'program.json').read_bytes(), original)
            # A new run receives no state from an earlier run with the same source and inputs.
            other = jobs.submit([step], path=home)['run_id']
            self.assertEqual(finish(other, home)['state'], 'failed')
            self.assertEqual((root / 'calls.txt').read_text().splitlines()[-3:], ['0', '1', '2'])

    def test_changed_source_inputs_or_environment_cannot_reuse_saved_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = {'kind': 'python', 'python': sys.executable, 'threads': 1}
            request = {'source': 'state=CHECKPOINT.load(0)\nCHECKPOINT.save(state+1)\nRESULT=state+1', 'inputs': {'x': 1}}
            execution.run('model', request, output=root / 'first', configuration=config)
            changed = [('source', {**request, 'source': request['source'] + '\n# changed'}, config),
                       ('inputs', {**request, 'inputs': {'x': 2}}, config),
                       ('environment', request, {**config, 'threads': 2})]
            for name, value, environment in changed:
                with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, 'source, inputs or environment changed'):
                    execution.run('model', value, output=root / name, configuration=environment, previous=[root / 'first'])

    def test_invalid_save_preserves_state_and_damaged_state_is_not_replayed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = Checkpoint(root / 'attempt-1', identity({'model': 1}))
            first.save({'position': 4})
            original = first.file.read_bytes()
            with self.assertRaises(ValueError):
                first.save({'position': float('nan')})
            self.assertEqual(first.file.read_bytes(), original)
            outside = root / 'outside.txt'
            outside.write_text('outside')
            with self.assertRaisesRegex(ValueError, 'outside this calculation'):
                first.save({'position': 5}, files={'file': outside})
            first.file.write_text('{truncated')
            second = Checkpoint(root / 'attempt-2', first.compatible, [first.output])
            with self.assertRaisesRegex(ValueError, 'Cannot continue'):
                second.load()


class OptimizationContinuation(unittest.TestCase):
    def test_abrupt_worker_exit_resumes_after_completed_evaluations(self):
        with workspace() as home:
            root = Path(home)
            environments.register('resumable-bowl', 'Resumable bowl', 'Standard-library calculation', modules=['json'], path=home)
            environments.bind('resumable-bowl', python=sys.executable, path=home)
            source = '''import json, os
from pathlib import Path
calls = Path(INPUTS['calls'])
previous = calls.read_text().splitlines() if calls.exists() else []
with calls.open('a') as log:
    log.write(json.dumps(INPUTS['x']) + '\\n')
if len(previous) == 7:
    os._exit(23)
(OUTPUT_DIR / 'x.txt').write_text(str(INPUTS['x']))
RESULT = {'f': (INPUTS['x'] - 2) ** 2}
'''
            run = jobs.submit([{'id': 'search', 'tool': 'resumable-bowl', 'source': source,
                                'inputs': {'calls': str(root / 'calls.jsonl')},
                                'optimize': {'variables': {'x': [0, 10]}, 'minimize': 'f', 'evaluations': 40}}], path=home)['run_id']
            first = finish(run, home)
            self.assertEqual(first['state'], 'failed', first)
            self.assertEqual(first['steps'][0]['progress'][0]['kind'], 'optimization')
            jobs.resume(run, path=home)
            second = finish(run, home)
            self.assertEqual(second['state'], 'succeeded', second)
            result = second['steps'][0]['result']['result']
            calls = [json.loads(line) for line in (root / 'calls.jsonl').read_text().splitlines()]
            self.assertEqual(result['reused_evaluations'], 7)
            self.assertEqual(len(calls), result['evaluations'] + 1)
            self.assertEqual(calls[7], calls[8])  # Only the interrupted, uncommitted evaluation runs again.

    def test_replay_retains_search_sequence_failures_budget_and_best_files(self):
        class Interrupted(BaseException):
            pass

        for method in optimization.METHODS:
            with self.subTest(method=method), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                spec = {'variables': {'x': [0, 10], 'scale': {'low': 0.1, 'high': 10, 'scale': 'log'}},
                        'minimize': 'f', 'method': method, 'evaluations': 80, 'seed': 13}
                calls = []
                def model(given, folder):
                    calls.append(dict(given))
                    if given['x'] > 8:
                        raise ValueError('outside model')
                    (folder / 'model.txt').write_text(json.dumps(given, sort_keys=True))
                    return {'f': (given['x'] - 2) ** 2 + (given['scale'] - 3) ** 2}
                def interrupted(given, folder):
                    if len(calls) == 7:
                        raise Interrupted()
                    return model(given, folder)
                one, two, baseline = root / 'attempt-1', root / 'attempt-2', root / 'baseline'
                for folder in (one, two, baseline):
                    folder.mkdir()
                first = Checkpoint(one, 'same-program-and-inputs', kind='optimization')
                with self.assertRaises(Interrupted):
                    optimization.run(interrupted, {}, spec, one, checkpoint=first)
                self.assertEqual(len(calls), 7)
                first_history = (one / 'history.jsonl').read_bytes()
                # A complete line beyond the committed snapshot is never taken as a finished evaluation.
                with (one / 'history.jsonl').open('a') as log:
                    log.write('{"uncommitted": true}\n')
                second = Checkpoint(two, first.compatible, [one], kind='optimization')
                resumed = optimization.run(model, {}, spec, two, checkpoint=second)
                resumed_calls = list(calls)
                calls.clear()
                uninterrupted = optimization.run(model, {}, spec, baseline)
                self.assertEqual(resumed_calls, calls)
                self.assertEqual(resumed['evaluations'], uninterrupted['evaluations'])
                self.assertEqual(resumed['failed'], uninterrupted['failed'])
                self.assertEqual(resumed['best'], uninterrupted['best'])
                self.assertEqual(resumed['objective'], uninterrupted['objective'])
                self.assertEqual(resumed['converged'], uninterrupted['converged'])
                self.assertEqual(resumed['reused_evaluations'], 7)
                self.assertEqual((two / 'history.jsonl').read_bytes(), (baseline / 'history.jsonl').read_bytes())
                self.assertEqual((two / 'best' / 'model.txt').read_bytes(), (baseline / 'best' / 'model.txt').read_bytes())
                self.assertTrue((one / 'history.jsonl').read_bytes().startswith(first_history))


class GroupContinuation(unittest.TestCase):
    def test_two_interruptions_keep_later_successes_and_return_original_file_paths(self):
        with workspace() as home:
            root = Path(home)
            environments.register('group-model', 'Group model', 'Standard-library calculation', modules=['json'], path=home)
            environments.bind('group-model', python=sys.executable, path=home)
            source = '''import os
from pathlib import Path
x = INPUTS['x']
calls = Path(INPUTS['calls'])
before = calls.read_text().splitlines().count(str(x)) if calls.exists() else 0
with calls.open('a') as log:
    log.write(str(x) + '\\n')
if x == 1 and before == 0:
    raise ValueError('Transient failed point')
if (x == 3 and before == 0) or (x == 1 and before == 1):
    os._exit(23)
(OUTPUT_DIR / 'value.txt').write_text(str(x))
RESULT = {'value': x}
'''
            run = studies.submit('group-model', source=source, inputs={'calls': str(root / 'group-calls.txt')},
                                 sweep={'x': [1, 2, 3, 4]}, chunk=4, path=home)['run_id']
            for attempt in (1, 2):
                stopped = finish(run, home)
                self.assertEqual(stopped['state'], 'failed', stopped)
                self.assertEqual(stopped['steps'][0]['attempt'], attempt)
                jobs.resume(run, path=home)
            completed = finish(run, home)
            self.assertEqual(completed['state'], 'succeeded', completed)
            result = completed['steps'][0]['result']['result']
            self.assertEqual((result['reused_points'], result['failed']), (1, 0))
            calls = (root / 'group-calls.txt').read_text().splitlines()
            self.assertEqual({key: calls.count(key) for key in ('1', '2', '3', '4')}, {'1': 3, '2': 1, '3': 2, '4': 1})
            rows = studies.table(run, values=['value'], path=home)['rows']
            self.assertEqual([row['values']['value'] for row in rows], [1, 2, 3, 4])
            self.assertIn('/attempt-1/', rows[1]['output'])
            for row in rows:
                self.assertEqual(jobs.read_result(run, row['output'] + 'value.txt', path=home)['data'], str(row['values']['value']))
            self.assertFalse((root / 'runs' / run / rows[1]['step'] / 'attempt-3' / rows[1]['id']).exists())


if __name__ == '__main__':
    unittest.main()
