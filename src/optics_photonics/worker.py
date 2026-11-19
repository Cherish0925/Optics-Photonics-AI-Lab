"""An isolated scientific program process, used by local and background calculations."""
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import time
from contextlib import nullcontext

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


def execute(tool, request, output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    inputs = request.get('inputs', {})
    if not isinstance(inputs, dict):
        raise ValueError('inputs must be a JSON object')
    (output/'inputs.json').write_text(json.dumps(request, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    started = time.time()
    source, action = request.get('source', ''), request.get('action', '')
    native_path = os.environ.get('OPTICS_NATIVE_CONNECTION')
    if not source and not native_path:
        source = programs.source(tool, action)  # a packaged program runs like a submitted one
    if native_path:
        from optics_photonics import native
        connection = json.loads(Path(native_path).read_text(encoding='utf-8'))
    if source:
        (output/'program.py').write_text(source, encoding='utf-8')
        code = compile(source, str(output/'program.py'), 'exec')
    elif request.get('optimize'):
        raise ValueError('optimize runs a program given as source in this session, not a session action')

    def calculate(given, folder):
        # Each sweep point owns its project and output. An optimization reuses that point's session.
        context = native.session(connection, given, folder) if native_path else nullcontext({})
        with context as session:
            if not source:
                return native.calculate(tool, action, given, {'INPUTS': given, 'OUTPUT_DIR': folder, 'RESULT': None, **session})

            def program(values, target):
                namespace = {'__name__': '__main__', '__file__': str(output/'program.py'), 'INPUTS': values, 'OUTPUT_DIR': target, 'RESULT': None, **session}
                if native_path:
                    namespace['EXPORT'] = lambda value, name='data': native.export(value, name, target)
                exec(code, namespace)
                if namespace['RESULT'] is None:
                    raise ValueError('Set RESULT to the compact JSON result; write arrays and models under OUTPUT_DIR')
                return namespace['RESULT']

            if not request.get('optimize'):
                return program(given, folder)
            from optics_photonics import optimization
            spec = None if request.get('source') else programs.catalog().get(tool, {}).get(action)
            return optimization.run(program, given, request['optimize'], folder, programs.inputs(spec) if spec else None)

    result = points(request['points'], calculate, output) if request.get('points') else calculate(inputs, output)
    # Distribution names are taken from the active interpreter, including native-program dependencies.
    versions = {}
    package_map = distributions()
    for module in set(name.split('.')[0] for name in sys.modules):
        for distribution in package_map.get(module, []):
            try: versions[distribution] = importlib.metadata.version(distribution)
            except importlib.metadata.PackageNotFoundError: pass
    record = {'software': tool, 'operation': 'program' if request.get('source') else action,
              'result': result, 'elapsed_s': time.time()-started,
              'environment': {'python': platform.python_version(), 'platform': platform.platform(), 'versions': versions, 'connector': __version__},
              'files': sorted(str(p.relative_to(output)) for p in output.rglob('*') if p.is_file() and p.name not in {'result.json','stdout.txt','stderr.txt','progress.json'})}
    text = json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False)+'\n'
    (output/'result.json').write_text(text, encoding='utf-8')
    return record


def main():
    tool = sys.argv[1]
    request_path = os.environ.get('OPTICS_REQUEST_FILE') or sys.argv[2]
    raw = json.loads(Path(request_path).read_text(encoding='utf-8'))
    request = raw.get('arguments', raw)
    if not request.get('source'):
        software(tool)
    output = os.environ.get('OPTICS_OUTPUT_DIR') or sys.argv[3]
    execute(tool, request, output)


if __name__ == '__main__':
    main()
