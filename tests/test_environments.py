"""Installation recipes, automatic preparation and binding every tool of one interpreter."""
import io
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from optics_photonics import environments, jobs, languages, routes  # noqa: E402
from support import workspace  # noqa: E402


def finish(run_id, home):
    for _ in range(40):
        state = jobs.status(run_id, path=home, wait=25)
        if state['state'] not in ('queued', 'running'):
            return state
    raise AssertionError('run did not finish: ' + run_id)


class RecipeCase(unittest.TestCase):
    def test_python_version_specifiers(self):
        for version, specifier, expected in (
                ('3.12.4', '>=3.10,<3.13', True), ('3.13.0', '>=3.10,<3.13', False), ('3.11.9', '==3.11', True),
                ('3.10.2', '>=3.11', False), ('3.9.25', '!=3.9', False), ('3.14.1', None, True), ('3.12', '<3.12.1', True)):
            self.assertEqual(environments.satisfies(version, specifier), expected, (version, specifier))
        with self.assertRaisesRegex(ValueError, 'version specifier'):
            environments.satisfies('3.12', '~3.12')

    def test_published_recipes_are_complete(self):
        from optics_photonics.catalogue import connections
        for tool, record in connections().items():
            item = environments.recipe(tool)
            if item is None:
                continue
            with self.subTest(tool=tool):
                if item['julia'] or item['executable']:
                    # An executable from conda-forge, or Julia packages: the tool runs programs in that language.
                    route = next(r for r in routes.routes(tool) if r['route'] == 'executable')
                    self.assertIn(route['language'], languages.LANGUAGES)
                    self.assertTrue(item['julia'] or item['executable']['path'])
                    continue
                self.assertEqual(record['kind'], 'python')
                self.assertTrue(record['modules'])
                if item['platforms']:
                    self.assertLessEqual(set(item['platforms']), set(environments.PLATFORMS))
                if item['python']:
                    self.assertTrue(any(environments.satisfies(v, item['python']) for v in ('3.9', '3.10', '3.11', '3.12', '3.13')))
                if item['environment'] != tool:
                    self.assertEqual(environments.recipe(item['environment'])['conda'], item['conda'])
        self.assertEqual(environments.recipe('mpb')['environment'], 'meep')

    def test_the_reason_a_tool_cannot_be_installed_is_stated(self):
        with patch.object(environments, 'here', return_value='win-64'):
            with self.assertRaisesRegex(ValueError, 'meep installs on linux-64.*not on win-64'):
                environments.installable('meep')
        with self.assertRaisesRegex(ValueError, 'pynx uses its own installer.*unrelated'):
            environments.installable('pynx')
        with self.assertRaisesRegex(ValueError, 'lumerical uses its own installer'):
            environments.installable('lumerical')
        self.assertEqual(environments.installable('tmm')['pip'][0], 'tmm==0.2.0')

    def test_search_shows_how_each_tool_installs(self):
        from optics_photonics import catalogue
        install = {item['id']: item['install'] for item in catalogue.search(limit=100)['items']}
        self.assertEqual((install['tmm'], install['meep'], install['lumerical']), ('pip', 'conda', 'manual'))

    def test_micromamba_is_used_only_when_its_checksum_matches(self):
        with workspace() as home:
            replies = iter([io.BytesIO(b'binary'), io.BytesIO(b'0' * 64)])
            with patch.dict(os.environ, {'PATH': '', 'OPTICS_CONDA': ''}), \
                 patch.object(environments.urllib.request, 'urlopen', lambda *a, **k: next(replies)):
                with self.assertRaisesRegex(RuntimeError, 'does not match its published SHA-256'):
                    environments.conda(home)
            self.assertFalse((Path(home) / 'bin').exists() and any((Path(home) / 'bin').iterdir()))


@unittest.skipIf(os.name == 'nt', 'The stand-in conda below is a POSIX shell script')
class CondaRecipeCase(unittest.TestCase):
    def test_conda_recipe_creates_a_shared_environment_and_binds_each_tool(self):
        with workspace() as home:
            calls = Path(home) / 'calls.jsonl'
            fake = Path(home) / 'conda'
            # Records its arguments, makes an environment whose python is this interpreter and lists one package.
            fake.write_text('#!/bin/sh\n'
                            f'printf "%s\\n" "$*" >> "{calls}"\n'
                            'if [ "$1" = list ]; then echo \'[{"name": "solver", "version": "1.2"}]\'; exit 0; fi\n'
                            'while [ "$1" != "-p" ]; do shift; done\n'
                            f'mkdir -p "$2/bin" && ln -s "{sys.executable}" "$2/bin/python"\n')
            fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
            for tool in ('solver-a', 'solver-b'):
                environments.register(tool, tool, 'conda-forge software', modules=['json'], conda=['solver'],
                                      python='>=3.9', path=home)
            definition = environments.read(home)['software']['solver-b']
            definition['connection']['environment_of'] = 'solver-a'
            environments.update('software', 'solver-b', definition, home)
            with patch.dict(os.environ, {'OPTICS_CONDA': str(fake)}):
                first = environments.prepare('solver-a', path=home)
                second = environments.prepare('solver-b', path=home)
            created = [line for line in calls.read_text().splitlines() if line.startswith('create')]
            self.assertEqual(len(created), 1)  # the second tool reuses the environment
            self.assertIn('-c conda-forge --override-channels python>=3.9 solver', created[0])
            self.assertEqual((first['managed'], second['managed'], first['installer']), ('solver-a', 'solver-a', 'conda'))
            self.assertEqual(first['python'], second['python'])
            self.assertEqual(first['versions'], {'solver': '1.2'})


class PreparationCase(unittest.TestCase):
    """Installs a small package from PyPI with uv or pip."""

    def test_a_submission_prepares_its_tool_first_and_then_reuses_it(self):
        with workspace() as home:
            environments.register('six-model', 'six model', 'A tool installed from its recipe', modules=['six'],
                                  distributions=['six'], pip=['six'], path=home)
            program = 'import six\nRESULT = {"version": six.__version__, "value": INPUTS["x"] * 2}'
            first = jobs.submit([{'id': 'calculate', 'tool': 'six-model', 'source': program, 'inputs': {'x': 3}}], path=home)
            state = finish(first['run_id'], home)
            self.assertEqual(state['state'], 'succeeded', state)
            steps = {step['id']: step for step in state['steps']}
            self.assertEqual(list(steps), ['prepare.six-model', 'calculate'])
            self.assertEqual(steps['calculate']['result']['result']['value'], 6)
            binding = environments.read(home)['tools']['six-model']
            self.assertEqual(binding['managed'], 'six-model')
            self.assertTrue(binding['versions']['six'])
            second = jobs.submit([{'id': 'again', 'tool': 'six-model', 'source': program, 'inputs': {'x': 4}}], path=home)
            state = finish(second['run_id'], home)
            self.assertEqual([step['id'] for step in state['steps']], ['again'])
            with self.assertRaisesRegex(ValueError, 'prepare.other names the step that prepares other'):
                environments.register('other', 'other', 'A tool', modules=['six'], pip=['six'], path=home)
                jobs.submit([{'id': 'prepare.other', 'tool': 'other', 'source': program}], path=home)
            # New settings keep the prepared environment; packages extend it.
            environments.bind('six-model', python=binding['python'], threads=2, path=home)
            extended = environments.prepare('six-model', packages=['attrs'], path=home)
            self.assertEqual((extended['managed'], extended['packages'], extended['threads']), ('six-model', ['attrs'], 2))

    def test_a_tool_without_a_recipe_explains_itself_at_submission(self):
        with workspace() as home:
            with self.assertRaisesRegex(ValueError, 'No environment is connected for lumerical. lumerical uses its own installer'):
                jobs.submit([{'id': 'solve', 'tool': 'lumerical', 'source': 'RESULT = 1'}], path=home)


class BindEveryCase(unittest.TestCase):
    def test_one_interpreter_binds_every_tool_it_provides_and_keeps_existing_bindings(self):
        with workspace() as home:
            environments.register('stdlib-model', 'stdlib model', 'Needs only the standard library', modules=['json'], path=home)
            environments.register('missing-model', 'missing model', 'Needs an absent module',
                                  modules=['module_that_does_not_exist'], path=home)
            environments.bind('stdlib-model', python=sys.executable, threads=3, path=home)
            environments.register('fresh-model', 'fresh model', 'Unbound', modules=['json', 'csv'], path=home)
            result = environments.bind(python=sys.executable, path=home)
            self.assertIn('fresh-model', result['bound'])
            self.assertIn('stdlib-model', result['kept'])
            self.assertNotIn('missing-model', result['bound'])
            tools = environments.read(home)['tools']
            self.assertEqual(tools['stdlib-model']['threads'], 3)
            self.assertEqual(tools['fresh-model']['definition']['id'], 'fresh-model')
            with self.assertRaisesRegex(ValueError, 'Name the tool, or give python alone'):
                environments.bind(path=home)


if __name__ == '__main__':
    unittest.main()
