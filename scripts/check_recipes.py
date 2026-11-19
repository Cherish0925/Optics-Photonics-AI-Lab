"""Prepare tools from their recipes in a scratch home and report what each installed.

    python scripts/check_recipes.py [TOOL ...] [--home DIR] [--jobs N] [--programs]

Without tools, every catalogue tool whose recipe installs on this platform is
prepared. With --programs each packaged program of a prepared tool then runs
with its default inputs in that environment, through the worker, and its
checks are reported. Each line of output is JSON: tool, state, seconds,
installer and versions, or the error, and the programs. The exit code is the
number of tools that failed to install or to run a program.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from optics_photonics import catalogue, environments, execution, programs  # noqa: E402


def candidates():
    here = environments.here()
    julia = environments.julia() or here in (environments.recipe('julia')['platforms'] or [here])
    for tool in sorted(catalogue.connections()):
        item = environments.recipe(tool)
        # Julia packages install where a Julia exists or conda-forge has one.
        if item and (not item['platforms'] or here in item['platforms']) and (julia or not item['julia']):
            yield tool


def check(tool, home, run_programs=False):
    started = time.time()
    try:
        record = environments.prepare(tool, path=home)
        result = {'tool': tool, 'state': 'installed', 'seconds': round(time.time() - started), 'installer': record['installer']}
        if record['kind'] == 'executable':
            result.update(executable=record['executable'], language=record['language'], packages=record['packages'])
        else:
            result.update(python=environments.probe(tool, record['python'], home)['python_version'], versions=record['versions'])
    except Exception as error:  # report every failure and continue with the other tools
        return {'tool': tool, 'state': 'failed', 'seconds': round(time.time() - started), 'error': str(error)[-800:]}
    if run_programs and programs.catalog().get(tool):
        result['programs'] = [program(tool, name, home) for name in programs.catalog()[tool]]
        if any(item['state'] == 'failed' for item in result['programs']):
            result['state'] = 'failed'
    return result


def program(tool, name, home):
    """Run one packaged program with its defaults in the prepared environment."""
    started = time.time()
    try:
        record = execution.run(tool, {'action': name, 'inputs': {}}, path=home, timeout=1800)['record']
        checks = record['result'].get('checks') if isinstance(record.get('result'), dict) else None
        return {'program': name, 'state': 'succeeded', 'seconds': round(time.time() - started, 1), 'checks': checks}
    except Exception as error:
        return {'program': name, 'state': 'failed', 'seconds': round(time.time() - started, 1), 'error': str(error)[-800:]}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('tools', nargs='*')
    parser.add_argument('--home')
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--programs', action='store_true', help='also run every packaged program with its defaults')
    options = parser.parse_args()
    home = options.home or tempfile.mkdtemp(prefix='optics-recipes-')
    tools = options.tools or list(candidates())
    failed = 0
    # Tools sharing an environment wait for each other through its lock.
    with ThreadPoolExecutor(options.jobs) as pool:
        for result in pool.map(lambda tool: check(tool, home, options.programs), tools):
            failed += result['state'] == 'failed'
            print(json.dumps(result, ensure_ascii=False), flush=True)
    print(json.dumps({'platform': environments.here(), 'tools': len(tools), 'failed': failed, 'home': home}), flush=True)
    sys.exit(min(failed, 100))


if __name__ == '__main__':
    main()
