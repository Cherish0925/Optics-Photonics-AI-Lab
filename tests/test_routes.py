"""Routes to installed software: the route records, discovery, bindings, scripts in other languages and driver programs.

Interpreters of other languages (Octave, Julia, Lua), S4 and ADDA run when they
are found on PATH or named by OPTICS_TEST_OCTAVE, OPTICS_TEST_JULIA,
OPTICS_TEST_LUA, OPTICS_TEST_S4 and OPTICS_TEST_ADDA; the other cases use the
running Python as the installed executable.
"""
import json
import io
import math
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import types
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from optics_photonics import catalogue, cli, environments, jobs, languages, native, routes, studies, worker  # noqa: E402
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
        self.assertEqual(languages.lua(value), 'JSON.object{["a"] = 1.5, ["b"] = JSON.array{1, 2}, ["c"] = "x\\"$\\\\", ["d"] = JSON.null, ["e"] = true, ["f"] = JSON.array{1, "two"}}')
        self.assertEqual(languages.lsf('m', [[1, 2], [3, 4.5]]), 'm = [1, 2; 3, 4.5];')
        self.assertEqual(languages.lsf('flag', True), 'flag = 1;')
        for bad in ({'k': 1}, [[1], [1, 2]], 'a"b'):
            with self.assertRaises(ValueError):
                languages.lsf('x', bad)
        with self.assertRaises(ValueError):
            languages.lsf('2x', 1)
        with self.assertRaises(ValueError):
            languages.julia(float('nan'))

    def test_a_program_in_another_language_declares_itself_in_its_leading_comment(self):
        text = '-- Title of the program.\n--\n-- Physics in\n-- two lines.\n--\n-- PROGRAM\n-- {"inputs": {"x": [1.5, "a length"]},\n' \
               '--  "results": "what it returns", "checks": "what it compares"}\nRESULT = {}\n'
        spec = languages.declaration(text, '.lua')
        self.assertEqual((spec['title'], spec['about'], spec['language']), ('Title of the program.', 'Physics in two lines.', 'lua'))
        self.assertEqual((spec['inputs'], spec['results']), ({'x': (1.5, 'a length')}, 'what it returns'))
        with self.assertRaisesRegex(ValueError, 'PROGRAM'):
            languages.declaration('# no declaration\nx = 1\n', '.jl')
        # Every packaged program of another language parses, and Octave runs MATLAB-language programs.
        from optics_photonics import programs
        self.assertEqual(programs.catalog()['quantumoptics']['jaynes_cummings']['language'], 'julia')
        self.assertEqual(programs.details('s4', 'crystal_slab')['language'], 'lua')
        self.assertEqual(languages.family('octave'), 'matlab')
        with self.assertRaisesRegex(ValueError, 'runs in its software'):
            programs.run('s4', 'crystal_slab', {}, Path('unused'))

    def test_arrays_returned_by_a_script_are_saved_with_their_description(self):
        with workspace() as folder:
            result = languages.described({'peak': 2, 'save': {'file': 'field', 'arrays': {
                'x_um': {'values': [0, 0.5, 1.0], 'quantity': 'position', 'unit': 'um'},
                'E': {'values': [[1, 2, 3], [4, None, 6]], 'quantity': 'field', 'unit': 'V/m', 'axes': [{'name': 'row', 'labels': ['a', 'b']}, 'x_um']}}}}, folder)
            self.assertEqual(result, {'peak': 2, 'data': 'field.npz'})
            from optics_photonics import arrays
            read = arrays.read(Path(folder) / 'field.npz', member='E')
            self.assertEqual((read['shape'], read['description']['unit'], read['values'][1][1]), ([2, 3], 'V/m', 'nan'))
            self.assertEqual(languages.described({'x': 1}, folder), {'x': 1})

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

    def test_script_arrays_reject_ragged_rows_without_reshaping_the_values(self):
        from optics_photonics import arrays
        with workspace() as folder:
            result = {'save': {'file': 'field', 'arrays': {'E': {'values': [[1, 2], [3], [4, 5, 6]]}}}}
            with self.assertRaisesRegex(ValueError, 'E: array rows must have the same shape'):
                languages.described(result, folder)
            self.assertIn('save', result)
            self.assertFalse((Path(folder) / 'field.npz').exists())
            result['save']['arrays'] = {'empty': {'values': [[], []]}, 'scalar': {'values': 3}}
            languages.described(result, folder)
            self.assertEqual(arrays.read(Path(folder) / 'field.npz', member='empty')['shape'], [2, 0])
            self.assertEqual(arrays.read(Path(folder) / 'field.npz', member='scalar')['values'], 3)

    def test_lumerical_result_uses_the_same_return_contract_as_other_languages(self):
        with workspace() as folder:
            value = {'RESULT': {'transmission': 0.9}}
            (Path(folder) / languages.RESULT_FILE).write_text(json.dumps(value))
            self.assertEqual(languages.result(folder, 'lsf'), value['RESULT'])
            self.assertEqual(languages.result(folder, 'lua'), value)

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

    def test_lua_round_trip_preserves_nulls_empty_objects_and_sparse_results(self):
        executable = found('OPTICS_TEST_LUA', 'lua', 'lua5.4', 'lua5.3')
        if not executable:
            self.skipTest('lua is not installed')
        inputs = {'missing': None, 'samples': [1, None, 3], 'object': {}, 'list': [], 'text': '\0' + '123 μm'}
        result = self.run_language('lua', executable,
                                   'RESULT = {inputs = INPUTS, object = JSON.object{}, sparse = {[1] = 1, [3] = 3}}', inputs)
        self.assertEqual(result, {'inputs': inputs, 'object': {}, 'sparse': [1, None, 3]})


DRIVER = '''
from pathlib import Path
RUN('-c', 'import sys; open("made.txt", "w").write(sys.argv[1])', INPUTS['value'], log='made.log')
RUN(['-c', 'pass'])
code = RUN('-c', 'import sys; sys.exit(3)', check=False)
RESULT = {'written': (OUTPUT_DIR / 'made.txt').read_text(), 'code': code, 'threads': THREADS, 'executable': Path(EXECUTABLE).name}
'''


class Execution(unittest.TestCase):
    def test_workflow_accepts_long_inline_scripts_and_adjacent_script_files(self):
        with workspace() as folder:
            file = Path(folder) / 'workflow.json'
            long_script = 'RESULT = "' + 'a' * 400 + '"'
            file.write_text(json.dumps([{'id': 'inline', 'tool': 's4', 'script': long_script},
                                        {'id': 'file', 'tool': 's4', 'script': 'slab.lua'}]))
            (Path(folder) / 'slab.lua').write_text('RESULT = 3')
            with patch.object(jobs, 'submit', return_value={}) as submit, redirect_stdout(io.StringIO()):
                cli.main(['submit-workflow', str(file)])
            self.assertEqual([step['script'] for step in submit.call_args.args[0]], [long_script, 'RESULT = 3'])

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
            # The positional Python call keeps the sweep argument of earlier releases.
            reply = studies.submit('adda', {}, '', DRIVER, {'value': [1, 2, 3]}, path=home)
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

    def test_s4_slab_transmission_follows_the_airy_formula(self):
        executable = found('OPTICS_TEST_S4', 'S4')
        if not executable:
            self.skipTest('S4 is not installed')
        script = '''
S = S4.NewSimulation()
S:SetLattice({1,0}, {0,1})
S:SetNumG(1)
S:AddMaterial("Vacuum", {1, 0})
S:AddMaterial("Slab", {INPUTS.epsilon, 0})
S:AddLayer("Above", 0, "Vacuum")
S:AddLayer("Slab", INPUTS.thickness, "Slab")
S:AddLayerCopy("Below", 0, "Above")
S:SetExcitationPlanewave({0, 0}, {1, 0}, {0, 0})
S:SetFrequency(INPUTS.frequency)
local incident, reflected = S:GetPoyntingFlux("Above", 0)
RESULT = {T = S:GetPoyntingFlux("Below", 0) / incident, R = -reflected / incident}
'''
        with workspace() as folder:
            home = Path(folder) / 'home'
            self.assertEqual(native.bind('s4', executable=executable, path=home)['language'], 'lua')
            reply = studies.submit('s4', script=script, inputs={'epsilon': 4.0, 'thickness': 0.3},
                                   sweep={'frequency': [0.3, 0.7, 1.1]}, path=home)
            self.assertEqual(jobs.status(reply['run_id'], wait=25, path=home)['state'], 'succeeded')
            reflectance = ((2 - 1) / (2 + 1)) ** 2
            for row in studies.table(reply['run_id'], values=['T', 'R'], path=home)['rows']:
                phase = 2 * math.pi * 2 * 0.3 * row['point']['frequency']
                airy = 1 / (1 + 4 * reflectance / (1 - reflectance) ** 2 * math.sin(phase) ** 2)
                self.assertAlmostEqual(row['values']['T'], airy, places=12)
                self.assertAlmostEqual(row['values']['R'] + row['values']['T'], 1, places=12)

    def test_s4_crystal_slab_conserves_energy_and_reaches_the_uniform_slab(self):
        executable = found('OPTICS_TEST_S4', 'S4')
        if not executable:
            self.skipTest('S4 is not installed')
        with workspace() as folder:
            home = Path(folder) / 'home'
            native.bind('s4', executable=executable, path=home)
            reply = studies.submit('s4', action='crystal_slab', inputs={'harmonics': 30, 'frequency': {'start': 0.3, 'stop': 0.5, 'points': 21}},
                                   wait=25, path=home)
            self.assertEqual(reply['state'], 'succeeded', reply)
            self.assertLess(reply['result']['checks']['energy_error'], 1e-9)
            self.assertLess(reply['result']['checks']['airy_difference'], 1e-12)
            described = jobs.read_array(reply['run_id'], 'calculate/attempt-1/spectrum.npz', member='T', path=home)
            self.assertEqual((described['description']['quantity'], described['axes'][0]['unit'], len(described['values'])), ('transmittance', 'c/a', 21))
            with self.assertRaisesRegex(ValueError, 's4/crystal_slab has no input radius_um'):
                jobs.submit([{'id': 'a', 'tool': 's4', 'action': 'crystal_slab', 'inputs': {'radius_um': 1}}], path=home)

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
