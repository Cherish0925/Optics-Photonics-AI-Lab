"""An isolated scientific program process, used by local and background calculations."""
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import time
from contextlib import contextmanager, nullcontext
import subprocess

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from optics_photonics import __version__, programs
from optics_photonics.catalogue import software


def distributions(native=getattr(importlib.metadata, 'packages_distributions', None)):
    """Installed distribution names by top-level module name."""
    if native:
        return native()
    found = {}  # Python 3.9 has no packages_distributions
    for distribution in importlib.metadata.distributions():
        modules = (distribution.read_text('top_level.txt') or '').split() or [
            file.parts[0].split('.')[0] for file in distribution.files or []
            if not file.parts[0].endswith(('.dist-info', '.egg-info'))]
        for module in set(modules):
            found.setdefault(module, []).append(distribution.metadata['Name'])
    return found


def points(items, calculate, output):
    """Compute the points of a group in turn; points.jsonl records each as it finishes."""
    records = []
    with (output/'points.jsonl').open('w', encoding='utf-8') as log:
        for item in items:
            folder = output/item['id']
            folder.mkdir(parents=True, exist_ok=True)
            entry = {'id': item['id'], 'point': item['point']}
            try:
                entry['result'] = calculate(item['inputs'], folder)
                text = json.dumps(entry, ensure_ascii=False, allow_nan=False)
            except Exception as error:  # one failed point does not stop the others
                entry.pop('result', None)
                entry['error'] = f'{type(error).__name__}: {error}'[-1000:]
                text = json.dumps(entry, ensure_ascii=False)
            log.write(text+'\n'); log.flush()
            records.append(entry)
    failed = [entry for entry in records if 'error' in entry]
    if len(failed) == len(records):
        raise RuntimeError(f"All {len(records)} points failed; the first: {failed[0]['error']}")
    return {'points': records, 'failed': len(failed)}


def connected(variable):
    path = os.environ.get(variable)
    return json.loads(Path(path).read_text(encoding='utf-8')) if path else None


def runner(connection, folder):
    """RUN for a Python program that drives an installed executable; output goes to a log file in OUTPUT_DIR."""
    count = iter(range(1, 1 << 30))

    def RUN(*arguments, program=None, cwd=None, input=None, timeout=None, check=True, log=None):
        """Run the bound executable, or the sibling executable named program, with arguments; returns the exit code.

        The process runs in OUTPUT_DIR unless cwd is given; input is text for its standard input; its standard
        output and errors go to log (run-N.log by default). check raises on a nonzero exit code with the log's end.
        """
        if len(arguments) == 1 and isinstance(arguments[0], (list, tuple)):
            arguments = tuple(arguments[0])
        if program is None:
            executable = connection['executable']
        elif program in connection.get('siblings', {}):
            executable = connection['siblings'][program]
        else:
            raise ValueError('program names one of: ' + ', '.join(connection.get('siblings', {})) if connection.get('siblings')
                             else 'This executable has no sibling executables; omit program')
        name = log or f'run-{next(count)}.log'
        with (Path(folder) / name).open('wb') as stream:
            completed = subprocess.run([executable, *map(str, arguments)], cwd=str(cwd or folder), stdout=stream, stderr=subprocess.STDOUT,
                                       stdin=subprocess.DEVNULL if input is None else None,
                                       input=None if input is None else input.encode('utf-8'), timeout=timeout)
        if check and completed.returncode:
            tail = (Path(folder) / name).read_text(encoding='utf-8', errors='replace')[-2000:]
            raise RuntimeError(f'{Path(executable).name} exited with code {completed.returncode}; {name} ends with:\n{tail}')
        return completed.returncode
    return RUN


def script(tool, connection, text, given, folder):
    """A program in the software's own language, run by its executable; returns its RESULT."""
    from optics_photonics import languages
    name = connection.get('language')
    if not name:
        raise ValueError(tool + ' is bound to an executable without a script language. Submit a Python program as source that '
                         'runs it with RUN(arguments) and reads the files it writes')
    languages.prepare(name, text, given, folder)
    command = languages.command(name, connection['executable'], folder, project=connection.get('project'),
                                threads=connection.get('threads', 1))
    with (Path(folder) / languages.LOG_FILE).open('wb') as log:
        code = subprocess.run(command, cwd=str(folder), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT).returncode
    if code:
        tail = (Path(folder) / languages.LOG_FILE).read_text(encoding='utf-8', errors='replace')[-3000:]
        raise RuntimeError(f'{Path(command[0]).name} exited with code {code}; {languages.LOG_FILE} ends with:\n{tail}')
    return languages.described(languages.result(folder), folder)


@contextmanager
def automation(connection):
    """The automation server of a Windows application, held as APP and released at the end."""
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    application = None
    try:
        application = win32com.client.Dispatch(connection['progid'])
        yield {'APP': application}
    finally:
        application = None
        pythoncom.CoUninitialize()


def execute(tool, request, output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    inputs = request.get('inputs', {})
    if not isinstance(inputs, dict):
        raise ValueError('inputs must be a JSON object')
    (output/'inputs.json').write_text(json.dumps(request, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    started = time.time()
    source, action, text = request.get('source', ''), request.get('action', ''), request.get('script', '')
    native_connection = connected('OPTICS_NATIVE_CONNECTION')
    executable = connected('OPTICS_EXECUTABLE_CONNECTION')
    server = connected('OPTICS_AUTOMATION_CONNECTION')
    if text and executable is None:
        raise ValueError('script runs in the language of an installed software bound to its executable (bind_native_software); '
                         'source runs Python')
    if text and source:
        raise ValueError('Give a script in the software\'s language or a Python source, not both')
    packaged = programs.catalog().get(tool, {}).get(action) if action and not source and not text else None
    defaults = {}
    if packaged and packaged.get('language'):
        # A packaged program in the software's own language runs like a submitted script, with its declared defaults.
        from optics_photonics import languages
        bound = (executable or {}).get('language')
        if bound is None or languages.family(bound) != languages.family(packaged['language']):
            raise ValueError(f"{tool}/{action} is a {packaged['language']} program; connect {tool} by its executable "
                             '(prepare_environment for a recipe, or bind_native_software)')
        text, defaults = programs.source(tool, action), programs.inputs(packaged)
    elif not source and not text and native_connection is None:
        source = programs.source(tool, action)  # a packaged program runs like a submitted one
    if native_connection is not None:
        from optics_photonics import native
    if source:
        (output/'program.py').write_text(source, encoding='utf-8')
        code = compile(source, str(output/'program.py'), 'exec')
    elif request.get('optimize') and not text:
        raise ValueError('optimize runs a program given as source in this session, not a session action')

    def calculate(given, folder, held=None):
        # Each sweep point owns its project and output. An optimization reuses that point's session.
        context = native.session(native_connection, given, folder) if native_connection is not None else nullcontext(held or {})
        with context as session:
            if not source and not text:
                return native.calculate(tool, action, given, {'INPUTS': given, 'OUTPUT_DIR': folder, 'RESULT': None, **session})

            def program(values, target):
                if text:
                    return script(tool, executable, text, {**defaults, **values}, target)
                namespace = {'__name__': '__main__', '__file__': str(output/'program.py'), 'INPUTS': values, 'OUTPUT_DIR': target, 'RESULT': None, **session}
                if native_connection is not None:
                    namespace['EXPORT'] = lambda value, name='data': native.export(value, name, target)
                if executable is not None:
                    namespace.update(EXECUTABLE=executable['executable'], SIBLINGS=executable.get('siblings', {}),
                                     THREADS=executable.get('threads', 1), RUN=runner(executable, target))
                exec(code, namespace)
                if namespace['RESULT'] is None:
                    raise ValueError('Set RESULT to the compact JSON result; write arrays and models under OUTPUT_DIR')
                return namespace['RESULT']

            if not request.get('optimize'):
                return program(given, folder)
            from optics_photonics import optimization
            return optimization.run(program, given, request['optimize'], folder, programs.inputs(packaged) if packaged else None)

    # An automation server is opened once for every point this process computes.
    with (automation(server) if server is not None else nullcontext(None)) as held:
        result = (points(request['points'], lambda given, folder: calculate(given, folder, held), output) if request.get('points')
                  else calculate(inputs, output, held))
    # Distribution names are taken from the active interpreter, including native-program dependencies.
    versions = {}
    package_map = distributions()
    for module in set(name.split('.')[0] for name in sys.modules):
        for distribution in package_map.get(module, []):
            try: versions[distribution] = importlib.metadata.version(distribution)
            except importlib.metadata.PackageNotFoundError: pass
    record = {'software': tool, 'operation': 'script' if text else 'program' if request.get('source') else action,
              'result': result, 'elapsed_s': time.time()-started,
              'environment': {'python': platform.python_version(), 'platform': platform.platform(), 'versions': versions, 'connector': __version__,
                              **({'executable': executable['executable'], 'language': executable.get('language')} if executable else {}),
                              **({'progid': server['progid']} if server else {})},
              'files': sorted(str(p.relative_to(output)) for p in output.rglob('*') if p.is_file() and p.name not in {'result.json','stdout.txt','stderr.txt','progress.json'})}
    text = json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False)+'\n'
    (output/'result.json').write_text(text, encoding='utf-8')
    return record


def main():
    tool = sys.argv[1]
    request_path = os.environ.get('OPTICS_REQUEST_FILE') or sys.argv[2]
    raw = json.loads(Path(request_path).read_text(encoding='utf-8'))
    request = raw.get('arguments', raw)
    if not request.get('source') and not request.get('script'):
        software(tool)
    output = os.environ.get('OPTICS_OUTPUT_DIR') or sys.argv[3]
    execute(tool, request, output)


if __name__ == '__main__':
    main()
