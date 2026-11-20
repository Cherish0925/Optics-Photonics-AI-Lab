"""Installed data-only integrations use the ordinary discovery and execution path."""
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from optics_photonics import catalogue, environments, execution, integrations, jobs, programs, studies, worker
from support import workspace

PROGRAM = '''"""A calibrated spectral observable.

A small standard-library program for exercising an independently installed integration.
"""
from optics_photonics.programs import parameters
PROGRAM = {"inputs": {"value": [3, "Measured value"], "gain": [2, "Scale factor"]},
           "domains": ["lab"], "results": "Corrected value", "checks": "Exact multiplication"}
p = parameters(PROGRAM, INPUTS)
RESULT = {"corrected": p["value"] * p["gain"]}
'''


def manifest(tool='addon-spectrometer'):
    return {'schema_version': 1, 'software': [
        {'id': tool, 'name': 'Additional spectrometer', 'summary': 'Calibrated spectral observations',
         'license': 'MIT', 'group': 'open', 'domains': ['lab'],
         'translations': {'zh': {'name': '附加光谱仪', 'summary': '校准后的光谱观测'}},
         'sources': [{'label': 'Documentation', 'url': 'https://example.org/spectrometer'}],
         'connection': {'kind': 'python', 'modules': ['json'], 'pip': ['solver-package==1.0'], 'python': '>=3.10'}}],
        'programs': [{'tool': tool, 'path': 'programs/calibrate.py'}],
        'guides': [{'name': 'acquisition', 'title': 'Acquire a spectrum', 'path': 'guides/acquisition.md'},
                   {'name': 'acquisition', 'title': '采集光谱', 'language': 'zh', 'path': 'guides/acquisition.zh.md'}]}


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.site = self.root / 'site'
        self.site.mkdir()
        actual_distributions = importlib.metadata.distributions
        self.metadata = patch.object(integrations.metadata, 'distributions', lambda: actual_distributions(path=[str(self.site)]))
        self.metadata.start()
        self.addCleanup(self.metadata.stop)
        self.addCleanup(integrations.refresh)
        integrations.refresh()

    def package(self, name='lab-addon', value=None, files=None, editable=None):
        module = name.replace('-', '_')
        info = self.site / (module + '-1.0.dist-info')
        info.mkdir()
        (info / 'METADATA').write_text('Metadata-Version: 2.1\nName: ' + name + '\nVersion: 1.0\n', encoding='utf-8')
        (info / 'entry_points.txt').write_text('[optics_photonics.integrations]\nmain = ' + module + '\n', encoding='utf-8')
        if editable:
            project = self.root / (name + ' editable project')
            (info / 'direct_url.json').write_text(json.dumps({'url': project.as_uri(), 'dir_info': {'editable': True}}))
            root = project / ('src' if editable == 'src' else '') / module
        else:
            root = self.site / module
        root.mkdir(parents=True)
        (root / '__init__.py').write_text("raise RuntimeError('Discovery imported the integration')\n", encoding='utf-8')
        (root / 'optics.json').write_text(json.dumps(value if value is not None else manifest(), ensure_ascii=False), encoding='utf-8')
        for path, text in (files or {'programs/calibrate.py': PROGRAM, 'guides/acquisition.md': 'Keep the raw spectrum.',
                                    'guides/acquisition.zh.md': '保留原始光谱。'}).items():
            file = root / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text, encoding='utf-8')
        return root, info

    def test_search_details_recipe_and_guides_without_importing(self):
        self.package()
        installed = integrations.listing()
        self.assertFalse(installed['errors'])
        self.assertEqual(installed['packages'][0]['id'], 'lab-addon:main')
        self.assertNotIn('lab_addon', sys.modules)
        found = catalogue.search('calibrated spectral', domain='lab')['items'][0]
        self.assertEqual(found['id'], 'addon-spectrometer')
        self.assertEqual(found['program']['name'], 'calibrate')
        details = environments.details('addon-spectrometer', path=self.root / 'home', brief=True)
        self.assertEqual(details['integration']['version'], '1.0')
        self.assertEqual(details['execution']['programs'][0]['integration'], 'lab-addon:main')
        self.assertEqual(details['integration_guides'][0]['topic'], 'acquisition')
        self.assertEqual(environments.recipe('addon-spectrometer', path=self.root / 'home')['pip'], ['solver-package==1.0'])
        self.assertEqual(integrations.guide('lab-addon:main', 'acquisition', 'zh')['text'], '保留原始光谱。')
        self.assertEqual(catalogue.software('addon-spectrometer', 'zh')['name'], '附加光谱仪')
        with self.assertRaisesRegex(ValueError, 'available: acquisition'):
            integrations.guide('lab-addon:main', 'missing')

    def test_add_program_and_guide_to_existing_solver(self):
        value = manifest()
        value['software'] = []
        value['programs'][0]['tool'] = 'scipy'
        value['guides'][0]['tools'] = ['scipy']
        self.package(value=value)
        self.assertEqual(catalogue.software('scipy'), {**catalogue.builtin_catalogue()[next(
            i for i, row in enumerate(catalogue.builtin_catalogue()) if row['id'] == 'scipy')],
            'connection': catalogue.builtin_connections()['scipy']})
        self.assertIn('calibrate', programs.catalog()['scipy'])
        self.assertIn('fit_gaussian', programs.catalog()['scipy'])
        found = catalogue.search('calibrated spectral', domain='lab')['items'][0]
        self.assertEqual((found['id'], found['program']['name']), ('scipy', 'calibrate'))
        self.assertEqual(environments.details('scipy', path=self.root / 'home', brief=True)['integration_guides'][0]['topic'], 'acquisition')

    def test_program_runs_in_interpreter_without_the_integration(self):
        _, info = self.package()
        home = self.root / 'home'
        environments.bind('addon-spectrometer', python=sys.executable, path=home)
        step = {'id': 'measure', 'tool': 'addon-spectrometer', 'action': 'calibrate', 'inputs': {'value': 5}}
        frozen = programs.snapshot(step)
        self.assertNotIn('source', step)
        self.assertEqual(frozen['inputs'], {'value': 5, 'gain': 2})
        self.assertEqual(frozen['_program']['distribution'], 'lab-addon')
        shutil.rmtree(info)
        integrations.refresh()
        self.assertNotIn('addon-spectrometer', catalogue.connections())
        self.assertTrue(environments.page(refresh=True, path=home)['environments'][0]['environment']['available'])
        # The selected interpreter has neither the distribution nor its manifest.
        result = execution.run('addon-spectrometer', frozen, output=self.root / 'run', path=home)
        self.assertEqual(result['record']['result'], {'corrected': 10})
        self.assertEqual((self.root / 'run' / 'program.py').read_text(encoding='utf-8'), PROGRAM)

    def test_direct_execution_freezes_an_action_and_keeps_its_provider(self):
        self.package()
        home = self.root / 'home'
        environments.bind('addon-spectrometer', python=sys.executable, path=home)
        result = execution.run('addon-spectrometer', {'action': 'calibrate', 'inputs': {'value': 5}},
                               output=self.root / 'direct', path=home)
        self.assertEqual(result['record']['result'], {'corrected': 10})
        self.assertEqual(result['record']['operation'], 'calibrate')
        self.assertEqual(result['record']['program']['distribution'], 'lab-addon')

    def test_queued_action_runs_after_its_integration_is_removed(self):
        _, info = self.package()
        with workspace() as home:
            environments.bind('addon-spectrometer', python=sys.executable, path=home)
            step = {'id': 'measure', 'tool': 'addon-spectrometer', 'action': 'calibrate', 'inputs': {'value': 6}}
            with patch.object(jobs, 'start_worker'):
                run = jobs.submit([step], request_id='queued-addon', path=home)['run_id']
            shutil.rmtree(info)
            integrations.refresh()
            self.assertNotIn('addon-spectrometer', catalogue.connections())
            self.assertEqual(jobs.submit([step], request_id='queued-addon', path=home)['run_id'], run)
            for _ in range(20):
                state = jobs.status(run, wait=25, path=home)
                if state['state'] in jobs.TERMINAL:
                    break
            self.assertEqual(state['state'], 'succeeded', state)
            result = state['steps'][0]['result']
            self.assertEqual(result['result'], {'corrected': 12})
            self.assertEqual(result['program']['version'], '1.0')
            with jobs.database(home) as db:
                saved = json.loads(db.execute('SELECT specification FROM steps WHERE run_id=?', (run,)).fetchone()[0])
            self.assertEqual(saved['source'], PROGRAM)

    def test_calculation_retry_precedes_default_expansion_after_integration_removal(self):
        value = manifest()
        value['guides'] = []
        source = PROGRAM.replace('[3, "Measured value"]', '[[3], "Measured value"]').replace(
            'p["value"] * p["gain"]', 'p["value"][0] * p["gain"]')
        _, info = self.package(value=value, files={'programs/calibrate.py': source})
        with workspace() as home:
            environments.bind('addon-spectrometer', python=sys.executable, path=home)
            call = {'action': 'calibrate', 'sweep': {'value.0': [3, 5]}, 'request_id': 'same', 'path': home}
            with patch.object(jobs, 'start_worker'):
                original = studies.submit('addon-spectrometer', **call)
            shutil.rmtree(info)
            integrations.refresh()
            # No catalogue/default lookup is needed for an already accepted call.
            with patch.object(programs, 'catalog', side_effect=AssertionError('Retry expanded a saved calculation')):
                retry = studies.submit('addon-spectrometer', **call, wait=25)
                with self.assertRaisesRegex(ValueError, 'request_id already belongs to different inputs'):
                    studies.submit('addon-spectrometer', **{**call, 'sweep': {'value.0': [99]}})
            self.assertEqual((retry['run_id'], retry['request_id']), (original['run_id'], original['request_id']))
            self.assertEqual(retry['state'], 'succeeded', retry)
            table = studies.table(original['run_id'], values=['corrected'], path=home)
            self.assertEqual([row['values']['corrected'] for row in table['rows']], [6, 10])

    def test_native_session_admits_declared_programs_and_checks_script_language(self):
        value = {'schema_version': 1, 'programs': [{'tool': 'comsol', 'path': 'programs/calibrate.py'}]}
        self.package(value=value, files={'programs/calibrate.py': PROGRAM})
        checked = jobs.validate([{'id': 'fit', 'tool': 'comsol', 'action': 'calibrate', 'inputs': {'value': 4}}])
        self.assertEqual(checked[0]['action'], 'calibrate')
        with self.assertRaisesRegex(ValueError, 'has no input typo'):
            jobs.validate([{'id': 'fit', 'tool': 'comsol', 'action': 'calibrate', 'inputs': {'typo': 4}}])
        connection = self.root / 'connection.json'
        connection.write_text(json.dumps({'language': 'julia'}))
        with patch.dict(os.environ, {'OPTICS_EXECUTABLE_CONNECTION': str(connection),
                                     'OPTICS_PREVIOUS_OUTPUTS': '[]'}), self.assertRaisesRegex(ValueError, 'is a matlab program'):
            worker.execute('octave', {'action': 'calibrate', 'script': 'RESULT = 1;',
                                     '_program': {'language': 'matlab'}}, self.root / 'wrong-language')

    def test_snapshot_native_script_defaults_and_grouped_points(self):
        value = {'schema_version': 1, 'programs': [{'tool': 'octave', 'path': 'programs/calibrate.m'}]}
        declaration = {'inputs': {'gain': [2, 'Scale factor'], 'value': [3, 'Measured value']},
                       'domains': ['lab'], 'results': 'Corrected value'}
        script = '% Calibrate a value.\n% PROGRAM\n% ' + json.dumps(declaration) + '\nRESULT = INPUTS.gain * INPUTS.value;\n'
        self.package(value=value, files={'programs/calibrate.m': script})
        step = {'id': 'measure', 'tool': 'octave', 'action': 'calibrate',
                'points': [{'id': 'first', 'point': {}, 'inputs': {'value': 4}}]}
        frozen = programs.snapshot(step)
        self.assertEqual(frozen['script'], script)
        self.assertEqual(frozen['_program']['language'], 'matlab')
        self.assertEqual(frozen['points'][0]['inputs'], {'gain': 2, 'value': 4})
        self.assertNotIn('gain', step['points'][0]['inputs'])

    def test_refresh_reloads_an_upgrade_and_removal(self):
        root, info = self.package()
        self.assertEqual(programs.details('addon-spectrometer', 'calibrate')['inputs']['gain']['default'], 2)
        (root / 'programs/calibrate.py').write_text(PROGRAM.replace('[2, "Scale factor"]', '[7, "Scale factor"]'))
        (info / 'METADATA').write_text('Metadata-Version: 2.1\nName: lab-addon\nVersion: 1.1\n')
        # Until refreshed, declarations and executable text describe the same version.
        self.assertEqual(programs.source('addon-spectrometer', 'calibrate'), PROGRAM)
        installed = integrations.listing(refresh=True)
        self.assertEqual(installed['packages'][0]['version'], '1.1')
        self.assertEqual(programs.details('addon-spectrometer', 'calibrate')['inputs']['gain']['default'], 7)
        shutil.rmtree(info)
        self.assertFalse(integrations.listing(refresh=True)['packages'])
        self.assertNotIn('addon-spectrometer', programs.catalog())

    def test_snapshot_keeps_source_defaults_and_provider_from_one_version(self):
        root, info = self.package()
        programs.catalog()
        original_copy = programs.copy.deepcopy
        refreshed = False

        def change_after_capture(*args, **kwargs):
            nonlocal refreshed
            if not refreshed:
                refreshed = True
                (root / 'programs/calibrate.py').write_text(PROGRAM.replace('[2, "Scale factor"]', '[7, "Scale factor"]'))
                (info / 'METADATA').write_text('Metadata-Version: 2.1\nName: lab-addon\nVersion: 1.1\n')
                integrations.refresh()
            return original_copy(*args, **kwargs)

        with patch.object(programs.copy, 'deepcopy', side_effect=change_after_capture):
            frozen = programs.snapshot({'tool': 'addon-spectrometer', 'action': 'calibrate'})
        self.assertEqual(frozen['source'], PROGRAM)
        self.assertEqual(frozen['inputs']['gain'], 2)
        self.assertEqual(frozen['_program']['version'], '1.0')
        updated = programs.snapshot({'tool': 'addon-spectrometer', 'action': 'calibrate'})
        self.assertNotEqual(updated['source'], PROGRAM)
        self.assertEqual(updated['inputs']['gain'], 7)
        self.assertEqual(updated['_program']['version'], '1.1')

    def test_search_and_parallel_refresh_keep_the_same_index_and_rows(self):
        original_index = catalogue.ranked_index
        original_index()
        index_read, finish_search = threading.Event(), threading.Event()
        refresh_started, refresh_finished = threading.Event(), threading.Event()
        result, errors = [], []

        def paused_index():
            index = original_index()
            index_read.set()
            if not finish_search.wait(5):
                raise RuntimeError('Search was not released')
            return index

        paused_index.cache_clear = original_index.cache_clear

        def search():
            try:
                result.append(catalogue.search('addon spectrometer'))
            except Exception as error:
                errors.append(error)

        def refresh():
            refresh_started.set()
            try:
                integrations.refresh()
            except Exception as error:
                errors.append(error)
            finally:
                refresh_finished.set()

        with patch.object(catalogue, 'ranked_index', paused_index):
            searching = threading.Thread(target=search)
            refreshing = threading.Thread(target=refresh)
            searching.start()
            try:
                self.assertTrue(index_read.wait(5))
                self.package()
                refreshing.start()
                self.assertTrue(refresh_started.wait(5))
                self.assertFalse(refresh_finished.wait(.05))
            finally:
                finish_search.set()
                searching.join(5)
                if refreshing.ident is not None:
                    refreshing.join(5)
        self.assertFalse(searching.is_alive())
        self.assertFalse(refreshing.is_alive())
        self.assertFalse(errors)
        self.assertNotIn('addon-spectrometer', [row['id'] for row in result[0]['items']])
        self.assertEqual(catalogue.search('addon spectrometer')['items'][0]['id'], 'addon-spectrometer')

    def test_malformed_package_does_not_disable_builtins_or_another_package(self):
        self.package('bad-addon', value={'schema_version': 999})
        self.package()
        installed = integrations.listing()
        self.assertEqual(len(installed['packages']), 1)
        self.assertIn('schema_version', installed['errors'][0]['error'])
        self.assertIn('spectrum', programs.catalog()['tmm'])
        self.assertEqual(catalogue.search('addon spectrometer')['items'][0]['id'], 'addon-spectrometer')

    def test_conflicting_programs_disable_both_packages_not_by_install_order(self):
        value = {'schema_version': 1, 'programs': [{'tool': 'scipy', 'path': 'programs/calibrate.py'}]}
        self.package('first-addon', value=value)
        self.package('second-addon', value=value)
        installed = integrations.listing()
        self.assertFalse(installed['packages'])
        self.assertEqual(len(installed['errors']), 2)
        self.assertTrue(all('program scipy/calibrate' in item['error'] for item in installed['errors']))
        self.assertNotIn('calibrate', programs.catalog()['scipy'])
        self.assertIn('fit_gaussian', programs.catalog()['scipy'])

    def test_builtin_identity_and_program_cannot_be_replaced(self):
        value = manifest('scipy')
        self.package('identity-addon', value=value)
        value = {'schema_version': 1, 'programs': [{'tool': 'scipy', 'name': 'fit_gaussian', 'path': 'programs/calibrate.py'}]}
        self.package('program-addon', value=value)
        errors = integrations.listing()['errors']
        self.assertEqual(len(errors), 2)
        self.assertTrue(any('Software already in the catalogue' in item['error'] for item in errors))
        self.assertTrue(any('Programs already provided' in item['error'] for item in errors))

    def test_native_session_actions_cannot_be_replaced(self):
        value = {'schema_version': 1, 'programs': [{'tool': 'comsol', 'name': 'solve_project', 'path': 'programs/calibrate.py'}]}
        self.package(value=value)
        self.assertIn('comsol/solve_project', integrations.listing()['errors'][0]['error'])

    def test_manifest_paths_stay_in_the_package_and_program_metadata_is_static(self):
        value = manifest()
        value['programs'][0]['path'] = '../elsewhere.py'
        (self.site / 'elsewhere.py').write_text(PROGRAM)
        self.package('outside-addon', value=value)
        self.package('dynamic-addon', files={'programs/calibrate.py': PROGRAM.replace('PROGRAM = {', 'PROGRAM = dict(**{').replace('\np = parameters', ')\np = parameters')})
        errors = integrations.listing()['errors']
        self.assertEqual(len(errors), 2)
        self.assertTrue(any('Missing file inside integration package' in item['error'] for item in errors))
        self.assertNotIn('addon-spectrometer', programs.catalog())
        self.assertIn('scipy', programs.catalog())

    def test_editable_src_and_flat_packages_without_import_finders(self):
        self.package('src-addon', value=manifest('src-spectrometer'), editable='src')
        self.package('flat-addon', value=manifest('flat-spectrometer'), editable='flat')
        installed = integrations.listing()
        self.assertFalse(installed['errors'])
        self.assertEqual(len(installed['packages']), 2)
        self.assertTrue({'src-spectrometer', 'flat-spectrometer'} <= set(catalogue.connections()))
        self.assertNotIn('src_addon', sys.modules)
        self.assertNotIn('flat_addon', sys.modules)

    def test_duplicate_metadata_for_the_same_installation_is_not_a_conflict(self):
        _, info = self.package()
        # Editable source metadata and installed metadata can both be on sys.path.
        shutil.copytree(info, self.site / 'duplicate_source-1.0.dist-info')
        installed = integrations.listing()
        self.assertEqual(len(installed['packages']), 1)
        self.assertFalse(installed['errors'])

    def test_repository_builds_exclude_locally_installed_integrations(self):
        self.package()
        with patch.dict(os.environ, {'OPTICS_BUILTIN_ONLY': '1'}):
            integrations.refresh()
            self.assertFalse(integrations.listing()['packages'])
            self.assertEqual(len(catalogue.catalogue()), len(catalogue.builtin_catalogue()))
        integrations.refresh()
        self.assertIn('addon-spectrometer', catalogue.connections())


if __name__ == '__main__':
    unittest.main()
