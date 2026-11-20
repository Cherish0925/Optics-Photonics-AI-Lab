"""Run an intentionally interrupted optical calculation, then continue it."""
import argparse
import json
from pathlib import Path
import sys

from optics_photonics import environments, jobs, studies

parser = argparse.ArgumentParser()
parser.add_argument('--home', required=True, help='A directory for this example environment and its results')
args = parser.parse_args()
home = Path(args.home).expanduser().resolve()
environments.register('slit-quadrature', 'Slit quadrature', 'Scalar far-field diffraction', modules=['cmath'], path=home)
environments.bind('slit-quadrature', python=sys.executable, path=home)
source = Path(__file__).with_name('diffraction.py').read_text(encoding='utf-8')
run = studies.submit('slit-quadrature', source=source, path=home)['run_id']

def finish():
    while True:
        status = jobs.status(run, wait=25, path=home)
        if status['state'] in jobs.TERMINAL:
            return status

first = finish()
if first['state'] != 'failed' or 'Example pause' not in first['steps'][0]['error']:
    raise RuntimeError(first)
print(json.dumps({'run_id': run, 'state': first['state'], 'progress': first['steps'][0]['progress']}, indent=2))
jobs.resume(run, path=home)
result = finish()
if result['state'] != 'succeeded':
    raise RuntimeError(result)
print(json.dumps(result['steps'][0]['result'], indent=2))
