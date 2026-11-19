"""Routes to installed software: the route records, discovery, bindings, scripts in other languages and driver programs.

Interpreters of other languages (Octave, Julia, Lua) and ADDA run when they are
found on PATH or named by OPTICS_TEST_OCTAVE, OPTICS_TEST_JULIA, OPTICS_TEST_LUA
and OPTICS_TEST_ADDA; the other cases use the running Python as the installed
executable.
"""
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from optics_photonics import catalogue, environments, jobs, languages, native, routes, studies, worker  # noqa: E402
from support import workspace  # noqa: E402

KINDS = {'python', 'session', 'executable', 'automation', 'service', 'inside'}


def found(variable, *names):
    explicit = os.environ.get(variable)
    if explicit:
        return explicit
    return next((path for path in map(shutil.which, names) if path), None)


def program(folder, name):
    """A file that discovery accepts as an executable: on Windows by its name, elsewhere by its mode."""
    file = Path(folder) / name
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text('')
    file.chmod(file.stat().st_mode | stat.S_IXUSR)
    return file


class RouteRecords(unittest.TestCase):
    def test_every_tool_has_a_way_in_with_sources(self):
        for item in catalogue.catalogue():
            tool = item['id']
            with self.subTest(tool=tool):
                found = routes.routes(tool)
                record = catalogue.connections()[tool]
                if record['kind'] == 'data':
                    continue
                self.assertTrue(found)
                for route in found:
                    self.assertIn(route['route'], KINDS)
                    for url in route.get('sources', []):
                        self.assertRegex(url, r'^https://')
                    if route['route'] == 'executable':
                        self.assertTrue(route.get('executables') or route.get('uses') or record['kind'] == 'command')
                        if route.get('language'):
                            self.assertIn(route['language'], languages.LANGUAGES)
                            self.assertEqual(route['program']['language'], route['language'])
                    if route['route'] == 'automation':
                        self.assertTrue(route.get('progids') or route.get('progid_pattern'))
                        if route.get('progid_pattern'):
                            re.compile(route['progid_pattern'])
                    if route['route'] == 'inside':
                        self.assertTrue(route['language'])
        # The commercial products the catalogue lists all say how they are reached.
        for tool in ('matlab', 'mathematica', 'maple', 'comsol', 'lumerical', 'cst', 'opticstudio', 'fred', 'codev', 'jcm', 'photond',
                     'tidy3d', 'speos', 'tracepro', 'rsoft', 'vpi', 'optisystem'):
            self.assertTrue(any(route['route'] != 'inside' or route.get('language') for route in routes.routes(tool)), tool)

    def test_search_and_details_report_routes(self):
        details = environments.details('lumerical')
        self.assertEqual([route['route'] for route in details['routes']], ['python', 'session', 'executable'])
        self.assertNotIn('routes', details['connection'])
        self.assertEqual(details['routes'][2]['program']['language'], 'lsf')
        self.assertEqual(catalogue.search('quantumoptics')['items'][0]['install'], 'julia')
        self.assertEqual(catalogue.search('octave')['items'][0]['id'], 'octave')


class Discovery(unittest.TestCase):
    def test_installations_are_found_in_roots_variables_and_path(self):
        here = routes.system()
        suffix = '.exe' if here == 'windows' else ''
        with workspace() as folder:
            root = Path(folder)
            matlab = program(root / 'MATLAB' / 'R2099a' / 'bin', 'matlab' + suffix)
            adda = program(root / 'adda' / 'src' / 'seq', 'adda' + suffix)
            program(root / 'adda' / 'src' / 'seq', 'adda_ocl' + suffix)
            jcm = root / 'JCMsuite' / 'ThirdPartySupport' / 'Python' / 'jcmwave'
            jcm.mkdir(parents=True)
            (jcm / '__init__.py').write_text('')
            fimm = root / 'PhotonD' / 'Python'
            fimm.mkdir(parents=True)
            (fimm / 'pdPythonLib.py').write_text('')
            julia = program(root / 'elsewhere', 'julia' + suffix)
            with patch.dict(os.environ, {'JCMROOT': str(root / 'JCMsuite'), 'PATH': str(julia.parent) + os.pathsep + os.environ.get('PATH', ''),
                                         'SIMCLOUD_APIKEY': 'not read'}):
                entries = native.discover([str(root)])['installations']
                one = native.discover([str(root)], tool='adda')
        def entry(tool, route, **fields):
            return next(item for item in entries if item['tool'] == tool and item['route'] == route
                        and all(item.get(key) == value for key, value in fields.items()))
        self.assertEqual(entry('matlab', 'executable', executable=str(matlab))['bind'],
                         {'tool': 'matlab', 'route': 'executable', 'executable': str(matlab)})
        self.assertIn('adda_ocl' + suffix, entry('adda', 'executable', executable=str(adda))['siblings'])
        self.assertEqual(entry('jcm', 'python', sdk_path=str(jcm.parent.resolve()))['found_by'], 'JCMROOT')
        self.assertEqual(entry('photond', 'service', sdk_path=str(fimm.resolve()))['bind']['route'], 'python')
        self.assertEqual(entry('julia', 'executable', executable=str(julia))['found_by'], 'PATH')
        self.assertTrue(entry('tidy3d', 'service')['credentials']['SIMCLOUD_APIKEY'])
        self.assertNotIn('not read', json.dumps(entries))
        self.assertEqual({entry['tool'] for entry in one['installations']}, {'adda'})
        self.assertEqual([route['route'] for route in one['routes']], ['executable'])

    def test_automation_servers_are_read_from_the_registry(self):
        names = ['FRED.Application', 'CodeV.Command', 'Excel.Application', 'LightTools.LTAPI4']
        with patch.object(routes, 'registered', side_effect=lambda name: name in names):
            fred = routes.servers('fred', routes.first('fred', 'automation'), lambda: names)
            codev = routes.servers('codev', routes.first('codev', 'automation'), lambda: names)
            lighttools = routes.servers('lighttools', routes.first('lighttools', 'automation'), lambda: names)
        self.assertEqual([entry['progid'] for entry in fred], ['FRED.Application'])
        self.assertEqual([entry['progid'] for entry in codev], ['CodeV.Command'])
        self.assertEqual([entry['progid'] for entry in lighttools], ['LightTools.LTAPI4'])
        with patch.object(routes, 'system', return_value='linux'):
            with self.assertRaisesRegex(ValueError, 'Windows'):
                routes.bind('fred', route='automation', progid='FRED.Application', path=Path('unused'))


class Bridges(unittest.TestCase):
    def test_inputs_become_literals_of_each_language(self):
        value = {'a': 1.5, 'b': [1, 2], 'c': 'x"$\\', 'd': None, 'e': True, 'f': [1, 'two']}
        self.assertEqual(languages.julia(value),
                         'Dict{String,Any}("a" => 1.5, "b" => [1, 2], "c" => "x\\"\\$\\\\", "d" => nothing, "e" => true, "f" => Any[1, "two"])')
        self.assertEqual(languages.lua(value), '{["a"] = 1.5, ["b"] = {1, 2}, ["c"] = "x\\"$\\\\", ["d"] = nil, ["e"] = true, ["f"] = {1, "two"}}')
        self.assertEqual(languages.lsf('m', [[1, 2], [3, 4.5]]), 'm = [1, 2; 3, 4.5];')
        self.assertEqual(languages.lsf('flag', True), 'flag = 1;')
        for bad in ({'k': 1}, [[1], [1, 2]], 'a"b'):
            with self.assertRaises(ValueError):
                languages.lsf('x', bad)
        with self.assertRaises(ValueError):
            languages.lsf('2x', 1)
        with self.assertRaises(ValueError):
            languages.julia(float('nan'))

    def test_main_files_and_commands(self):
        with workspace() as folder:
            target = Path(folder) / "it's"
            target.mkdir()
            for name in languages.LANGUAGES:
                main = languages.prepare(name, 'RESULT = 1', {'x': 1}, target)
                text = main.read_text(encoding='utf-8')
                self.assertTrue(text.strip(), name)
                command = languages.command(name, '/bin/tool', target, project='/p', threads=3)
                self.assertEqual(command[0], '/bin/tool')
                self.assertTrue(any(main.stem in part for part in command), name)
                self.assertEqual(json.loads((target / languages.INPUT_FILE).read_text()), {'x': 1})
            self.assertIn("it''s", (target / 'optics_main.m').read_text())
            self.assertIn('--project=/p', languages.command('julia', 'julia', target, project='/p'))
            self.assertIn('--threads=3', languages.command('julia', 'julia', target, threads=3))
            self.assertEqual(languages.command('matlab', 'matlab', target)[1:4], ['-sd', target.as_posix(), '-batch'])
            with self.assertRaisesRegex(RuntimeError, 'without RESULT'):
                languages.result(target)

    def run_language(self, name, executable, script, inputs, env=None):
        with workspace() as folder:
            target = Path(folder)
            languages.prepare(name, script, inputs, target)
            import subprocess
            command = languages.command(name, executable, target)
            completed = subprocess.run(command, cwd=target, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                       env={**os.environ, **(env or {})}, timeout=600)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            return languages.result(target)

    def test_julia_program(self):
        executable = found('OPTICS_TEST_JULIA', 'julia')
        if not executable:
            self.skipTest('julia is not installed')
        result = self.run_language('julia', executable, 'RESULT = Dict("sum" => sum(INPUTS["n"]), "name" => INPUTS["name"], '
                                   '"m" => [1 2; 3 4], "t" => (a=1, b=nothing), "type" => string(eltype(INPUTS["n"])))',
                                   {'n': [1.0, 2.5], 'name': 'a"b$c'})
        self.assertEqual(result, {'sum': 3.5, 'name': 'a"b$c', 'm': [[1, 2], [3, 4]], 't': {'a': 1, 'b': None}, 'type': 'Float64'})

    def test_octave_program(self):
        executable = found('OPTICS_TEST_OCTAVE', 'octave-cli')
        if not executable:
            self.skipTest('octave-cli is not installed')
        prefix = Path(executable).resolve().parents[1]
        env = {'OCTAVE_HOME': str(prefix)} if (prefix / 'conda-meta').is_dir() else {}
        result = self.run_language('octave', executable, "RESULT = struct('s', sum(INPUTS.n), 'name', INPUTS.name, 'out', OUTPUT_DIR);\n"
                                   'function y = unused(x)\n y = x;\nend\n', {'n': [1, 2, 3], 'name': "it's"}, env)
        self.assertEqual((result['s'], result['name']), (6, "it's"))

    def test_lua_program(self):
        executable = found('OPTICS_TEST_LUA', 'lua', 'lua5.4', 'lua5.3')
        if not executable:
            self.skipTest('lua is not installed')
        result = self.run_language('lua', executable, 'RESULT = {s = INPUTS.n[1] + INPUTS.n[2], name = INPUTS.name, list = {1, 2.5}, empty = {}}',
                                   {'n': [1, 2.5], 'name': 'q"\\'})
        self.assertEqual(result, {'s': 3.5, 'name': 'q"\\', 'list': [1, 2.5], 'empty': []})


DRIVER = '''
from pathlib import Path
RUN('-c', 'import sys; open("made.txt", "w").write(sys.argv[1])', INPUTS['value'], log='made.log')
RUN(['-c', 'pass'])
code = RUN('-c', 'import sys; sys.exit(3)', check=False)
RESULT = {'written': (OUTPUT_DIR / 'made.txt').read_text(), 'code': code, 'threads': THREADS, 'executable': Path(EXECUTABLE).name}
'''


class Execution(unittest.TestCase):
    def test_a_python_program_drives_a_bound_executable(self):
        with workspace() as folder:
            home = Path(folder) / 'home'
            bound = native.bind('adda', executable=sys.executable, python=sys.executable, threads=2, path=home)
            self.assertEqual((bound['kind'], bound['language']), ('executable', None))
            reply = studies.submit('adda', source=DRIVER, inputs={'value': 7}, wait=25, path=home)
            self.assertEqual(reply['state'], 'succeeded', reply)
            self.assertEqual(reply['result'], {'written': '7', 'code': 3, 'threads': 2, 'executable': Path(sys.executable).name})
            files = jobs.files(reply['run_id'], path=home)['files']
            self.assertTrue(any(item['file'].endswith('made.log') for item in files))
            # A sweep of a driver program computes its points in one process each group.
            reply = studies.submit('adda', source=DRIVER, sweep={'value': [1, 2, 3]}, path=home)
            done = jobs.status(reply['run_id'], wait=25, path=home)
            self.assertEqual(done['state'], 'succeeded', done)
            table = studies.table(reply['run_id'], values=['written'], path=home)
            self.assertEqual(sorted(row['values']['written'] for row in table['rows']), ['1', '2', '3'])
            # A failing executable reports its log; a script needs a language.
            failing = studies.submit('adda', source="RUN('-c', 'import sys; print(\"bad input\"); sys.exit(2)')\nRESULT = {}", wait=25, path=home)
            self.assertEqual(failing['state'], 'failed')
            self.assertIn('bad input', failing['error'])
            script = studies.submit('adda', script='anything', wait=25, path=home)
            self.assertIn('without a script language', script['error'])
            # Software outside the catalogue takes a script language at binding.
            environments.register('lab-solver', 'Lab solver', 'An executable of the lab', kind='command', path=home)
            bound = native.bind('lab-solver', executable=sys.executable, language='lua', path=home)
            self.assertEqual((bound['kind'], bound['language']), ('executable', 'lua'))
            with self.assertRaisesRegex(ValueError, 'Script languages'):
                native.bind('lab-solver', executable=sys.executable, language='fortran', path=home)
            environments.register('local-python', 'Local Python', 'A Python tool', modules=['json'], path=home)
            environments.bind('local-python', python=sys.executable, path=home)
            self.assertIn('bind_native_software', studies.submit('local-python', script='RESULT = 1', wait=25, path=home)['error'])

    def test_bound_executables_without_language_and_missing_ones(self):
        with workspace() as folder:
            home = Path(folder) / 'home'
            with self.assertRaisesRegex(ValueError, 'not found'):
                native.bind('matlab', executable=str(Path(folder) / 'missing'), path=home)
            with self.assertRaisesRegex(ValueError, 'No executable of pbrt'):
                with patch.object(routes, 'discover', return_value=[]):
                    native.bind('pbrt', route='executable', path=home)
            self.assertEqual(environments.read(home)['tools'], {})
            with self.assertRaisesRegex(ValueError, 'discover_native_software and bind_native_software'):
                environments.installable('adda')

    def test_automation_server_is_held_as_app(self):
        made = []

        class Server:
            def __init__(self, name):
                self.name = name
                made.append(self)

        client = types.ModuleType('win32com.client')
        client.Dispatch = Server
        package = types.ModuleType('win32com')
        package.client = client
        calls = []
        com = types.ModuleType('pythoncom')
        com.CoInitialize = lambda: calls.append('init')
        com.CoUninitialize = lambda: calls.append('done')
        with workspace() as folder:
            connection = Path(folder) / 'automation-connection.json'
            connection.write_text(json.dumps({'kind': 'automation', 'progid': 'FRED.Application'}))
            request = {'source': 'RESULT = {"server": APP.name, "point": INPUTS["x"]}',
                       'points': [{'id': 'point-1', 'point': {'x': 1}, 'inputs': {'x': 1}}, {'id': 'point-2', 'point': {'x': 2}, 'inputs': {'x': 2}}]}
            with patch.dict(sys.modules, {'win32com': package, 'win32com.client': client, 'pythoncom': com}), \
                    patch.dict(os.environ, {'OPTICS_AUTOMATION_CONNECTION': str(connection)}):
                record = worker.execute('fred', request, Path(folder) / 'out')
        self.assertEqual([point['result'] for point in record['result']['points']],
                         [{'server': 'FRED.Application', 'point': 1}, {'server': 'FRED.Application', 'point': 2}])
        self.assertEqual((len(made), calls), (1, ['init', 'done']))

    def test_adda_particle_converges_to_the_exact_series(self):
        executable = found('OPTICS_TEST_ADDA', 'adda')
        if not executable:
            self.skipTest('adda is not installed')
        with workspace() as folder:
            home = Path(folder) / 'home'
            native.bind('adda', executable=executable, python=sys.executable, path=home)
            coarse = studies.submit('adda', action='particle', inputs={'dipoles_per_wavelength': 8}, wait=25, path=home)
            fine = studies.submit('adda', action='particle', inputs={'dipoles_per_wavelength': 16}, wait=25, path=home)
            for reply in (coarse, fine):
                self.assertEqual(reply['state'], 'succeeded', reply)
            self.assertLess(fine['result']['checks']['mie_difference'], coarse['result']['checks']['mie_difference'])
            self.assertLess(fine['result']['checks']['mie_difference'], 0.005)
            self.assertLess(fine['result']['checks']['s11_difference'], 0.02)


if __name__ == '__main__':
    unittest.main()
