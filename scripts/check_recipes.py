"""Prepare tools from their recipes in a scratch home and report what each installed.

    python scripts/check_recipes.py [TOOL ...] [--home DIR] [--jobs N]

Without tools, every catalogue tool whose recipe installs on this platform is
prepared. Each line of output is JSON: tool, state, seconds, installer and
versions, or the error. The exit code is the number of tools that failed.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from optics_photonics import catalogue, environments  # noqa: E402


def candidates():
    for tool in sorted(catalogue.connections()):
        item = environments.recipe(tool)
        if item and (not item['platforms'] or environments.here() in item['platforms']):
            yield tool


def check(tool, home):
    started = time.time()
    try:
        record = environments.prepare(tool, path=home)
        return {'tool': tool, 'state': 'installed', 'seconds': round(time.time() - started),
                'installer': record['installer'], 'python': environments.probe(tool, record['python'], home)['python_version'],
                'versions': record['versions']}
    except Exception as error:  # report every failure and continue with the other tools
        return {'tool': tool, 'state': 'failed', 'seconds': round(time.time() - started), 'error': str(error)[-800:]}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('tools', nargs='*')
    parser.add_argument('--home')
    parser.add_argument('--jobs', type=int, default=4)
    options = parser.parse_args()
    home = options.home or tempfile.mkdtemp(prefix='optics-recipes-')
    tools = options.tools or list(candidates())
    failed = 0
    # Tools sharing an environment wait for each other through its lock.
    with ThreadPoolExecutor(options.jobs) as pool:
        for result in pool.map(lambda tool: check(tool, home), tools):
            failed += result['state'] == 'failed'
            print(json.dumps(result, ensure_ascii=False), flush=True)
    print(json.dumps({'platform': environments.here(), 'tools': len(tools), 'failed': failed, 'home': home}), flush=True)
    sys.exit(min(failed, 100))


if __name__ == '__main__':
    main()
