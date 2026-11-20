"""Step a setting of a laboratory instrument and read a value at each step (PyVISA, text commands).

Sources, power meters, spectrum analyzers, oscilloscopes and controllers
on GPIB, USB, a serial port or the network exchange text messages, most of
them SCPI. The program opens the instrument at a VISA address, sends the
setup commands, then for each value sends the set command with the value,
waits, and sends the read query; the numbers of each reply are recorded
with the time. Raw replies are saved as they arrive, including a reply
that cannot be parsed. Every finish command is attempted at the end, also
after a Python exception; process cancellation or a timeout can prevent
this cleanup. Commands go to the
instrument as given: its manual states the commands, ranges and settling
times. Without a resource the program talks to a simulated tunable source
(PyVISA-sim) that keeps the wavelength it is given, which shows the flow
without hardware; resource "?" lists the instruments the backend finds
and, when requested, their identifications. Coordinate shared instruments
through a common resource pool or their existing instrument service;
a tool's concurrency setting does not lock a device across libraries.
"""
import csv
import json
import re
import sys
import time
from contextlib import contextmanager
from pathlib import Path
import numpy as np
import pyvisa
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'resource': ('', 'VISA address such as TCPIP0::192.168.1.20::inst0::INSTR, GPIB0::8::INSTR or ASRL3::INSTR; '
                         'empty: the simulated source; "?": list what the backend finds'),
        'backend': ('@py', '@py: the Python backend (network, serial, USB); empty: the installed VISA library (NI, Keysight)'),
        'identify': ('*IDN?', 'identification query; empty skips it'),
        'setup': ([], 'commands sent once before the first step'),
        'set': (':WAV {value:.3f}', 'command that applies a value; {value} is replaced'),
        'read': (':WAV?', 'query sent at each step; the numbers of its reply are recorded'),
        'values': ({'start': 1500.0, 'stop': 1600.0, 'points': 11}, 'values to apply: a list, or {start, stop, points}'),
        'settle_s': (0.0, 'wait between the set command and the read query, in seconds'),
        'finish': ([], 'commands sent at the end, also after a failure'),
        'timeout_s': (5.0, 'time allowed for a reply, in seconds'),
        'termination': ('\n', 'character ending each message'),
        'set_quantity': (['wavelength', 'nm'], 'name and unit of the applied values'),
        'read_quantity': (['wavelength read back', 'nm'], 'name and unit of the recorded numbers'),
    },
    'domains': ['lab'],
    'results': 'sweep.npz/.json and sweep.csv: the applied values, the numbers read at each and the time of each reading; '
               'sweep.raw.jsonl retains each reply and setting even if a later reading fails; cleanup errors, if any, '
               'are in sweep.cleanup.json; the identification; with resource "?", the resources found',
    'checks': 'readback_difference: largest difference of the reading from the applied value, for the simulated source',
}
p = parameters(PROGRAM, INPUTS)
SIMULATED = 'TCPIP0::simulated::inst0::INSTR'
# A source that stores the wavelength it is given, from 1200 to 1700 nm, in the notation of PyVISA-sim.
INSTRUMENT = '''spec: "1.1"
devices:
  source:
    eom:
      TCPIP INSTR: {q: "\\n", r: "\\n"}
    error: ERROR
    dialogues:
      - {q: "*IDN?", r: "Simulated instruments,Tunable source,0001,1.0"}
    properties:
      wavelength:
        default: 1550.0
        getter: {q: ":WAV?", r: "{:.3f}"}
        setter: {q: ":WAV {:.3f}"}
        specs: {min: 1200, max: 1700, type: float}
resources:
  ''' + SIMULATED + ''': {device: source}
'''
NUMBER = re.compile(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')

cleanup_errors = []


@contextmanager
def managed(resource, name, finish=()):
    """Close every acquired VISA resource; cleanup errors never replace an earlier failure."""
    failed = False
    try:
        yield resource
    except BaseException:
        failed = True
        raise
    finally:
        errors = []
        for command in finish:
            try:
                resource.write(command)
            except Exception as error:
                errors.append({'command': command, 'error': f'{type(error).__name__}: {error}'})
        try:
            resource.close()
        except Exception as error:
            errors.append({'operation': name, 'error': f'{type(error).__name__}: {error}'})
        if errors:
            cleanup_errors.extend(errors)
            message = 'Instrument cleanup failed: ' + '; '.join(item['error'] for item in errors)
            try:
                (Path(OUTPUT_DIR) / 'sweep.cleanup.json').write_text(
                    json.dumps(cleanup_errors, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            except OSError as error:
                message += f'; could not save sweep.cleanup.json: {error}'
            if failed:
                print(message, file=sys.stderr)
            else:
                raise RuntimeError(message)


@contextmanager
def opened(manager, address, finish=()):
    commands = []
    with managed(manager.open_resource(address), 'instrument.close', commands) as instrument:
        instrument.timeout = float(p['timeout_s']) * 1000
        instrument.read_termination = instrument.write_termination = p['termination']
        # A session that could not be configured must be closed without sending commands.
        commands.extend(finish)
        yield instrument


simulated = not p['resource']
if simulated:
    description = Path(OUTPUT_DIR) / 'simulated-instrument.yaml'
    description.write_text(INSTRUMENT, encoding='utf-8')
    manager = pyvisa.ResourceManager(str(description) + '@sim')
else:
    manager = pyvisa.ResourceManager(p['backend']) if p['backend'] else pyvisa.ResourceManager()

with managed(manager, 'manager.close'):
    if p['resource'] == '?':
        listed = []
        for address in manager.list_resources():
            entry = {'resource': address}
            if p['identify']:
                try:
                    with opened(manager, address) as instrument:
                        entry['identification'] = instrument.query(p['identify']).strip()
                except Exception as error:   # an instrument that does not answer is still listed
                    entry['error'] = str(error)[:200]
            listed.append(entry)
        RESULT = {'resources': listed, 'backend': p['backend'] or 'installed VISA library', 'checks': {'readback_difference': None}}
    else:
        if isinstance(p['values'], dict):
            values = np.linspace(float(p['values']['start']), float(p['values']['stop']), int(p['values']['points']))
        else:
            values = np.atleast_1d(np.asarray(p['values'], dtype=float))
        if values.size < 1 or '{value' not in p['set'] or not p['read'] or float(p['settle_s']) < 0:
            raise ValueError('values is not empty, set contains {value}, read is a query and settle_s is not negative')
        identification, readings, times = None, [], []
        started = time.monotonic()
        with opened(manager, SIMULATED if simulated else p['resource'], p['finish']) as instrument:
            with (Path(OUTPUT_DIR) / 'sweep.raw.jsonl').open('w', encoding='utf-8') as raw:
                if p['identify']:
                    identification = instrument.query(p['identify']).strip()
                for command in p['setup']:
                    instrument.write(command)
                for value in values:
                    command = p['set'].format(value=float(value))
                    instrument.write(command)
                    if p['settle_s']:
                        time.sleep(float(p['settle_s']))
                    reply = instrument.query(p['read'])
                    elapsed = time.monotonic() - started
                    raw.write(json.dumps({'setting': float(value), 'command': command, 'query': p['read'],
                                          'time_s': elapsed, 'unix_time_s': time.time(), 'reply': reply},
                                         ensure_ascii=False, allow_nan=False) + '\n')
                    raw.flush()
                    numbers = [float(text) for text in NUMBER.findall(reply)]
                    if not numbers:
                        raise ValueError(f'The reply to {p["read"]} holds no number: {reply[:200]!r}')
                    if readings and len(numbers) != len(readings[0]):
                        raise ValueError(f'The reply to {p["read"]} holds {len(numbers)} numbers; '
                                         f'expected {len(readings[0])}. Raw replies are in sweep.raw.jsonl')
                    readings.append(numbers)
                    times.append(elapsed)

if p['resource'] != '?':
    width = len(readings[0])
    table = np.asarray(readings)
    (set_name, set_unit), (read_name, read_unit) = p['set_quantity'], p['read_quantity']
    saved = data.save(OUTPUT_DIR / 'sweep', {
        'reading': data.quantity(table[:, 0] if width == 1 else table, read_name, unit=read_unit,
                                 axes=['setting'] if width == 1 else ['setting', 'number'], instrument=identification, query=p['read']),
        'setting': data.quantity(values, set_name, unit=set_unit, command=p['set']),
        **({} if width == 1 else {'number': data.quantity(np.arange(width), 'position of the number in the reply', unit='1')}),
        'time_s': data.quantity(np.asarray(times), 'time of the reading from the start', unit='s', axes=['setting']),
    })
    with (Path(OUTPUT_DIR) / 'sweep.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow([f'{set_name} ({set_unit})', 'time (s)'] + [f'{read_name} ({read_unit})'] * width)
        writer.writerows([value, moment, *row] for value, moment, row in zip(values.tolist(), times, table.tolist()))
    RESULT = {
        'identification': identification, 'resource': 'simulated source' if simulated else p['resource'], 'steps': int(values.size),
        'first': [float(values[0]), *table[0].tolist()], 'last': [float(values[-1]), *table[-1].tolist()],
        'elapsed_s': times[-1], 'data': saved['data'], 'files': ['sweep.csv', 'sweep.raw.jsonl'],
        'checks': {'readback_difference': float(np.abs(table[:, 0] - values).max()) if simulated else None},
    }
