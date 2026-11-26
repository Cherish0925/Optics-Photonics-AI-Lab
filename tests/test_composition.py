import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from optics_photonics import composition, environments, jobs
from optics_photonics.mcp import tool_result
from support import workspace


class CompositionTests(unittest.TestCase):
    def test_catalogue_references_and_read_only_plan(self):
        view = composition.catalogue_view()
        ids = {module['id'] for module in view['modules']}
        tools = {item['id'] for item in view['components']}
        self.assertNotIn('opticstudio', tools)
        self.assertNotIn('codev', tools)
        for module in view['modules']:
            self.assertLessEqual(set(module['components']), tools)
            self.assertTrue(module['resources'])
        for field in view['fields']:
            for direction in field['directions']:
                self.assertLessEqual(set(direction['modules']), ids)
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'OPTICS_HOME': str(Path(tmp) / 'home')}):
            result = composition.plan(['tmm', 'opticstudio'])
            self.assertEqual([item['action'] for item in result['actions']], ['install', 'connect'])
            self.assertFalse(environments.home().exists())

    def test_domain_navigation_includes_programs_from_shared_software(self):
        view = composition.catalogue_view()
        directions = {row['id']: row for field in view['fields'] for row in field['directions']}
        for domain, name in (('bio', 'tissue-transport'), ('fiber', 'fiber-propagation'), ('laser', 'lasers-resonators')):
            self.assertIn(name, directions[domain]['modules'])
        tissue = next(row for row in view['modules'] if row['id'] == 'tissue-transport')
        self.assertIn('skills/optical-research/references/bio.md', tissue['resources'])
        self.assertIn('tissue_layers', [row['name'] for row in tissue['programs']])
        meep = next(row for row in view['components'] if row['id'] == 'meep')
        self.assertNotIn('win-64', meep['installation']['platforms'])
        self.assertEqual(meep['installation']['method'], 'conda')

    def test_shared_software_is_resolved_once_and_kept_for_other_modules(self):
        with workspace() as tmp, patch.dict(os.environ, {'OPTICS_HOME': tmp}):
            environments.save({'tools': {'scipy': {'kind': 'python', 'python': sys.executable}}})
            names = ['tissue-transport', 'measured-spectra']
            self.assertEqual(composition.plan(names)['modules'], names)
            self.assertEqual([row['component'] for row in composition.plan(names)['actions']], ['scipy'])
            with patch.object(jobs, 'submit', return_value={'run_id': 'reuse'}):
                composition.prepare(names)
            self.assertTrue(set(names) <= set(composition.installed()['ready_modules']))
            result = composition.remove(['tissue-transport'])
            self.assertEqual(result['removed'], ['tissue-transport'])
            self.assertIn('scipy', environments.read()['tools'])
            self.assertNotIn('tissue-transport', composition.installed()['ready_modules'])
            self.assertIn('measured-spectra', composition.installed()['ready_modules'])
            result = composition.remove(['measured-spectra'])
            self.assertEqual(result['removed'], ['measured-spectra'])
            self.assertNotIn('scipy', environments.read()['tools'])
            self.assertTrue(Path(sys.executable).exists())

    def test_plan_names_the_workstation_for_windows_interfaces(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'OPTICS_HOME': tmp}), \
                patch('optics_photonics.routes.system', return_value='linux'):
            result = composition.plan(['opticstudio', 'lighttools', 'labview'])
            for action in result['actions']:
                self.assertEqual(action['action'], 'connect')
                self.assertIn('windows', action['instructions'])
                self.assertIn('SSH', action['instructions'])
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_native_ready_command_is_the_solver_not_its_python_driver(self):
        binding = {'kind': 'executable', 'executable': sys.executable, 'python': '/missing/driver'}
        self.assertEqual(composition.invocation('octave', binding)['command'], [sys.executable])
        self.assertTrue(composition.available(binding))
        binding.update(executable='/missing/solver', python=sys.executable)
        self.assertFalse(composition.available(binding))

    def test_prepare_local_wheel_and_preserve_manual_connections(self):
        with workspace() as tmp, patch.dict(os.environ, {'OPTICS_HOME': str(Path(tmp) / 'home'),
                'OPTICS_SOFTWARE_HOME': str(Path(tmp) / 'software'), 'UV': '/unavailable/uv'}):
            wheels = Path(tmp) / 'wheels'
            wheels.mkdir()
            files = {'optics_fixture/__init__.py': 'def square(x): return x*x\n',
                     'optics_fixture-1.0.dist-info/METADATA': 'Metadata-Version: 2.1\nName: optics-fixture\nVersion: 1.0\n',
                     'optics_fixture-1.0.dist-info/WHEEL': 'Wheel-Version: 1.0\nGenerator: local\nRoot-Is-Purelib: true\nTag: py3-none-any\n'}
            files['optics_fixture-1.0.dist-info/RECORD'] = '\n'.join(name + ',,' for name in files) + '\n'
            with zipfile.ZipFile(wheels / 'optics_fixture-1.0-py3-none-any.whl', 'w') as wheel:
                for name, value in files.items():
                    wheel.writestr(name, value)
            environments.register('fixture-wheel', 'Local wheel', 'Offline calculation', modules=['optics_fixture'],
                                  pip=['optics-fixture==1.0'])
            with patch.dict(os.environ, {'PIP_NO_INDEX': '1', 'PIP_FIND_LINKS': str(wheels)}):
                response = tool_result({'name': 'environment_prepare', 'task': {}, 'arguments': {
                    'selections': ['fixture-wheel', 'opticstudio'], 'request_id': 'local-wheel'}})
                task = response['task']['taskId']
                result = composition.task_rpc('tasks/result', task)
                self.assertFalse(result['isError'], result)
                prepared = result['structuredContent']
                self.assertEqual(prepared['pending'][0]['component'], 'opticstudio')
                command = prepared['ready'][0]['command']
                self.assertTrue(Path(command[0]).is_relative_to((Path(tmp) / 'software').resolve()))
                actual = subprocess.check_output([*command, '-c', 'from optics_fixture import square; print(square(6))'], text=True)
                self.assertEqual(actual.strip(), '36')
                self.assertEqual(composition.prepare(['fixture-wheel', 'opticstudio'], request_id='local-wheel')['run_id'], task)
                self.assertIn('fixture-wheel', composition.installed()['ready_modules'])
                self.assertNotIn('opticstudio', composition.installed()['ready_modules'])
                removed = tool_result({'name': 'environment_remove', 'arguments': {'selections': ['fixture-wheel']}})
                self.assertEqual(removed['structuredContent']['removed'], ['fixture-wheel'])
                self.assertFalse(Path(command[0]).exists())
                retry = composition.prepare(['fixture-wheel'], request_id='install-again')['run_id']
                composition.task_rpc('tasks/result', retry)
                release = Path(tmp) / 'continue-calculation'
                research = jobs.submit([{'id': 'square', 'tool': 'fixture-wheel',
                                         'source': 'import time\nfrom pathlib import Path\n'
                                         f'while not Path({str(release)!r}).exists(): time.sleep(0.01)\n'
                                         'from optics_fixture import square\nRESULT={"square": square(7)}'}])['run_id']
                active = composition.remove(['fixture-wheel'])
                release.touch()
                self.assertEqual(active['removed'], [])
                self.assertIn('fixture-wheel', environments.read()['tools'])
                deadline = time.monotonic() + 15
                while (state := jobs.status(research))['state'] not in jobs.TERMINAL and time.monotonic() < deadline:
                    time.sleep(.05)
                self.assertEqual(state['state'], 'succeeded', state)
                preserved = composition.remove(['fixture-wheel'])
                self.assertEqual(preserved['removed'], ['fixture-wheel'])
                self.assertEqual(preserved['files'], [])
                self.assertTrue(Path(command[0]).exists())
                self.assertTrue((environments.home() / 'runs' / research).is_dir())
                self.assertEqual(jobs.status(research)['state'], 'succeeded')

    def test_existing_software_keeps_its_location_after_storage_is_separated(self):
        with workspace() as tmp, patch.dict(os.environ, {'OPTICS_HOME': str(Path(tmp) / 'state'),
                'OPTICS_SOFTWARE_HOME': str(Path(tmp) / 'software')}):
            old = environments.home() / 'environments' / 'tmm'
            new = environments.software_home() / 'tmm'
            for prefix in (old, new):
                prefix.mkdir(parents=True)
                (prefix / 'solver').write_text('installed solver')
            environments.save({'tools': {'tmm': {'kind': 'command', 'command': [str(old / 'solver')], 'managed': 'tmm'}}})
            self.assertEqual(environments.environment_prefix('tmm'), old)
            action = composition.plan(['thin-film-spectra'])['actions'][0]
            self.assertEqual(action['action'], 'reuse')
            self.assertEqual(action['command'], [str(old / 'solver')])
            result = composition.remove(['tmm'])
            self.assertEqual(result['files'], [str(old)])
            self.assertTrue((new / 'solver').exists())

    def test_uninstall_shared_and_external_connections(self):
        with workspace() as tmp, patch.dict(os.environ, {'OPTICS_HOME': tmp}):
            prefix = environments.home() / 'environments/shared'
            prefix.mkdir(parents=True)
            executable = prefix / 'solver'
            executable.write_text('owned solver')
            environments.save({'tools': {
                'tmm': {'kind': 'command', 'command': [str(executable)], 'managed': 'shared'},
                'grcwa': {'kind': 'command', 'command': [str(executable)], 'managed': 'shared'},
                'external': {'kind': 'python', 'python': sys.executable}}})
            result = composition.remove(['tmm', 'external'])
            self.assertTrue(executable.exists())
            self.assertTrue(Path(sys.executable).exists())
            self.assertIn(str(prefix), result['retained'])
            result = composition.remove(['grcwa'])
            self.assertFalse(prefix.exists())
            self.assertEqual(result['files'], [str(prefix)])
            prefix.mkdir()
            executable.write_text('owned solver')
            environments.save({'tools': {name: {'kind': 'command', 'command': [str(executable)], 'managed': 'shared'}
                                         for name in ('tmm', 'grcwa')}})
            result = composition.remove(['tmm', 'grcwa'])
            self.assertEqual(result['removed'], ['grcwa', 'tmm'])
            self.assertEqual(result['files'], [str(prefix)])

    def test_connection_only_and_empty_selections_keep_results(self):
        with workspace() as tmp, patch.dict(os.environ, {'OPTICS_HOME': tmp}):
            for names in ([], ['opticstudio']):
                response = tool_result({'name': 'environment_prepare', 'task': {}, 'arguments': {'selections': names}})
                task = response['task']['taskId']
                result = composition.task_rpc('tasks/result', task)
                self.assertEqual(result['structuredContent']['modules'], names)
                self.assertEqual(result['structuredContent']['ready'], [])
                self.assertEqual(composition.task(task)['status'], 'completed')
                with self.assertRaises(ValueError):
                    composition.task_rpc('tasks/cancel', task)


if __name__ == '__main__':
    unittest.main()
