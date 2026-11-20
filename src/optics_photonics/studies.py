"""Parameter studies: sweeps that run as parallel steps of one run, and the table of their results.

A sweep maps input names to values. A name may address one element of a list
or object input with dots, such as thickness_nm.0 or layers.1.n; the rest of
that input comes from the step inputs or, for a packaged program, from its
default. Values are a list, or {"start", "stop", "points"} with "scale":
"log" for logarithmic spacing. pairing "product" runs every combination and
"zip" pairs the lists element by element. Each point becomes a step point-N
of the run, which records the swept values as its point; points run in
parallel within the configured capacity. Points are grouped so that one
process computes several in turn: by default about four groups per CPU
slot, so a program that takes milliseconds does not pay a process start
per point while long ones still fill every slot. table() collects chosen result
values of every point, finds the best one and can save the study as a
described array, gridded over the swept inputs when the points form a full
product.

Only the standard library is used: the connector and every solver
environment can import this module.
"""
import copy
import itertools
import json
import math
import re

LIMIT = 10000


def swept(spec, name):
    """The values of one swept input: a list, or an evenly or logarithmically spaced range."""
    if isinstance(spec, list) and spec:
        return spec
    if isinstance(spec, dict) and {'start', 'stop', 'points'} <= set(spec) <= {'start', 'stop', 'points', 'scale'}:
        start, stop, count, scale = spec['start'], spec['stop'], spec['points'], spec.get('scale', 'linear')
        if type(count) is not int or count < 1 or not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                                                         and math.isfinite(v) for v in (start, stop)):
            raise ValueError(f'{name}: start and stop are finite numbers and points a positive integer')
        if count == 1:
            return [start]
        if scale == 'log':
            if start <= 0 or stop <= 0:
                raise ValueError(f'{name}: a logarithmic range needs positive start and stop')
            return [float(f'{start * (stop / start) ** (i / (count - 1)):.12g}') for i in range(count)]
        if scale != 'linear':
            raise ValueError(f'{name}: scale is linear or log')
        if all(type(v) is int for v in (start, stop)) and (stop - start) % (count - 1) == 0:
            return [start + (stop - start) // (count - 1) * i for i in range(count)]
        return [float(f'{start + (stop - start) * i / (count - 1):.12g}') for i in range(count)]  # 1.225, not 1.2249999999999999
    raise ValueError(f'{name}: give a nonempty list of values or {{"start", "stop", "points"}}')


def _part(container, part, key):
    if isinstance(container, list):
        try:
            index = int(part)
            container[index]  # noqa: B018 - raises for a position outside the list
            return index
        except (ValueError, IndexError):
            raise ValueError(f'{key}: {part} is not a position in a list of {len(container)}') from None
    if isinstance(container, dict):
        if part not in container:
            raise ValueError(f'{key}: no key {part}; keys: ' + ', '.join(map(str, container)))
        return part
    raise ValueError(f'{key}: {part} addresses inside a value that is neither a list nor an object')


def assign(inputs, key, value, defaults=None):
    """Set inputs[name] or one element inside it, for a key such as name or name.0.n."""
    name, *path = str(key).split('.')
    if not path:
        inputs[name] = value
        return
    if name in inputs:
        inputs[name] = copy.deepcopy(inputs[name])
    elif defaults and name in defaults:
        inputs[name] = copy.deepcopy(defaults[name])
    else:
        raise ValueError(f'{key}: {name} is not among the inputs and has no default to address inside')
    target = inputs[name]
    for part in path[:-1]:
        target = target[_part(target, part, key)]
    target[_part(target, path[-1], key)] = value


def pick(result, path):
    """The value at a dotted path such as checks.energy_error or R.0; None when it is absent."""
    value = result
    for part in str(path).split('.'):
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list):
            try:
                value = value[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
        if value is None:
            return None
    return value


def expand(step, sweep, pairing='product', first=1, defaults=None):
    """Steps point-N for every point of the sweep, numbered from first."""
    if not isinstance(sweep, dict) or not sweep:
        raise ValueError('sweep maps input names to lists of values')
    lists = {str(key): swept(spec, 'sweep ' + str(key)) for key, spec in sweep.items()}
    if pairing == 'product':
        count = math.prod(len(items) for items in lists.values())
        combinations = itertools.product(*lists.values())
    elif pairing == 'zip':
        if len({len(items) for items in lists.values()}) != 1:
            raise ValueError('pairing zip takes lists of equal length: ' + ', '.join(f'{k} {len(v)}' for k, v in lists.items()))
        count, combinations = len(next(iter(lists.values()))), zip(*lists.values())
    else:
        raise ValueError('pairing is product or zip')
    if count > LIMIT:
        raise ValueError(f'The sweep has {count} points; submit at most {LIMIT} at once')
    width = max(4, len(str(first + count - 1)))
    steps = []
    for number, combination in enumerate(combinations, first):
        point = dict(zip(lists, combination))
        inputs = copy.deepcopy(step.get('inputs', {}))
        for key, value in point.items():
            assign(inputs, key, value, defaults)
        steps.append({**step, 'id': f'point-{number:0{width}d}', 'inputs': inputs, 'point': point})
    return steps


def grouped(points, size):
    """Steps that each compute up to size consecutive points in one process; a single point stays a step of its own."""
    steps = []
    for start in range(0, len(points), size):
        part = points[start:start + size]
        if len(part) == 1:
            steps.append(part[0])
            continue
        common = {key: value for key, value in part[0].items() if key not in ('id', 'inputs', 'point')}
        steps.append({**common, 'id': part[0]['id'] + '-' + part[-1]['id'][len('point-'):], 'inputs': {},
                      'points': [{'id': item['id'], 'point': item['point'], 'inputs': item['inputs']} for item in part]})
    return steps


def submit(tool, inputs=None, action='', source='', sweep=None, pairing='product', optimize=None, chunk=None, name='Optical research',
           request_id=None, run_id=None, timeout=None, requirements=None, wait=0, path=None, cancel=None, *, script=''):
    """One calculation, or a sweep of it, as steps of a new run or appended to run_id.

    wait (up to 25 seconds) returns the run's state after that time or on completion,
    and for one calculation its result, files and output folder, or its error.
    """
    from . import environments, jobs, programs
    if not isinstance(wait, (int, float)) or isinstance(wait, bool) or not 0 <= wait <= 25:
        raise ValueError('wait must be between 0 and 25 seconds')
    step = {'tool': tool, 'inputs': {} if inputs is None else inputs}
    for key, value in (('action', action), ('source', source), ('script', script), ('optimize', optimize), ('timeout', timeout),
                       ('requirements', requirements)):
        if value:
            step[key] = value
    existing = jobs.step_ids(run_id, path) if run_id else set()
    if sweep is None:
        number = 1
        while ('calculate' if number == 1 else f'calculate-{number}') in existing:
            number += 1
        steps = [{'id': 'calculate' if number == 1 else f'calculate-{number}', **step}]
    else:
        spec = programs.catalog().get(tool, {}).get(action) if action and not source and not script else None
        # A group step point-0001-0094 holds points 1 to 94.
        used = [int(found[2] or found[1]) for found in map(re.compile(r'point-(\d+)(?:-(\d+))?$').match, existing) if found]
        points = expand(step, sweep, pairing, max(used, default=0) + 1, programs.inputs(spec) if spec else None)
        if chunk is not None and (type(chunk) is not int or chunk < 1):
            raise ValueError('chunk is a positive number of points per process')
        configuration = environments.read(path)['tools'].get(tool, {})
        # External programs accept one request per invocation; they need not implement our worker's grouping protocol.
        size = 1 if configuration.get('kind') == 'command' else chunk or max(1, math.ceil(len(points) / (4 * jobs.resources(path=path)['cpu'])))
        steps = grouped(points, size)
    # The call, not its numbered steps, identifies a retried request.
    call = {'tool': tool, 'inputs': step['inputs'], 'action': action, 'source': source, **({'script': script} if script else {}), 'sweep': sweep, 'pairing': pairing,
            'optimize': optimize, 'chunk': chunk, 'timeout': timeout, 'requirements': requirements, 'name': name, 'run_id': run_id}
    submitted = jobs.submit(steps, name=name, request_id=request_id, run_id=run_id, path=path, _payload={'calculation': call})
    if not wait:
        return submitted
    original = jobs.submitted_steps(submitted['request_id'], path)
    return {**submitted, **jobs.outcome(submitted['run_id'], original[0] if sweep is None and original else None, wait, path, cancel)}


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def table(run_id, values=None, minimize=None, maximize=None, save=False, offset=0, limit=100, path=None):
    """Swept inputs, state and chosen result values of every point of a run, with the best point."""
    from . import arrays, environments, jobs
    if minimize and maximize:
        raise ValueError('Give minimize or maximize, not both')
    goal = minimize or maximize
    chosen = [str(v) for v in values or []]
    if goal and goal not in chosen:
        chosen.append(goal)
    if offset < 0 or not 1 <= limit <= 1000:
        raise ValueError('Use offset >= 0 and limit between 1 and 1000')
    jobs.identifier(run_id)
    with jobs.database(path) as db:
        if not db.execute('SELECT 1 FROM runs WHERE id=?', (run_id,)).fetchone():
            raise ValueError('Unknown run: ' + run_id)
        rows = db.execute('SELECT id,specification,state,result,error,attempt FROM steps WHERE run_id=? ORDER BY rowid', (run_id,)).fetchall()
    specs, points = [], []
    for row in rows:
        spec = json.loads(row['specification'])
        result = json.loads(row['result']).get('result') if row['state'] == 'succeeded' and row['result'] else None
        if 'point' in spec:
            members = [(row['id'], spec['point'], spec.get('inputs', {}), {'result': result} if result is not None else {})]
        elif 'points' in spec:
            done = {entry['id']: entry for entry in (result or {}).get('points', [])}
            if result is None:  # finished points of a group still running, or stopped
                log = environments.home(path) / 'runs' / run_id / row['id'] / f"attempt-{row['attempt']}" / 'points.jsonl'
                try:
                    lines = log.read_text(encoding='utf-8').splitlines()
                except OSError:
                    lines = []
                for line in lines:
                    try:
                        entry = json.loads(line)
                        done[entry['id']] = entry
                    except (ValueError, KeyError, TypeError):
                        pass  # the line being written
            members = [(item['id'], item['point'], item['inputs'], done.get(item['id'], {})) for item in spec['points']]
        else:
            continue
        for key, point, given, entry in members:
            state = 'succeeded' if 'result' in entry else 'failed' if 'error' in entry else row['state']
            item = {'step': row['id'], 'id': key, 'state': state, 'point': point,
                    'values': {path_: pick(entry['result'], path_) if 'result' in entry else None for path_ in chosen}}
            error = entry.get('error') or (row['error'] if state != 'succeeded' else None)
            if error:
                item['error'] = error[-300:]
            points.append(item)
            specs.append((spec, given))
    if not points:
        raise ValueError(f'Run {run_id} has no sweep points; submit_calculation with sweep creates them')
    keys = sorted({key for item in points for key in item['point']})
    # A point of a later sweep over fewer inputs takes the others from its inputs or the program's defaults.
    for item, (spec, given) in zip(points, specs):
        if len(item['point']) < len(keys):
            from . import programs
            program = programs.catalog().get(spec['tool'], {}).get(spec.get('action')) if not spec.get('source') else None
            known = {**(programs.inputs(program) if program else {}), **given}
            item['point'] = {key: item['point'][key] if key in item['point'] else pick(known, key) for key in keys}
    counts = {}
    for item in points:
        counts[item['state']] = counts.get(item['state'], 0) + 1
    reply = {'run_id': run_id, 'points': len(points), 'states': counts, 'swept': keys, 'values': chosen}
    if goal:
        sign = 1 if minimize else -1
        scored = [(sign * _number(item['values'][goal]), n) for n, item in enumerate(points) if _number(item['values'][goal]) is not None]
        if scored:
            _, n = min(scored)  # the earliest point among equal values
            reply['best'] = {**points[n], 'goal': 'minimize' if minimize else 'maximize', 'path': goal}
        else:
            reply['best'] = None
    reply['rows'] = points[offset:offset + limit]
    reply['next_offset'] = offset + limit if offset + limit < len(points) else None
    if save:
        reply.update(_save(environments.home(path) / 'runs' / run_id / 'sweep', points, keys, chosen, arrays))
    return reply


def _array_name(text, taken):
    name = re.sub(r'[^0-9A-Za-z_]+', '_', text).strip('_') or 'value'
    while name in taken:
        name += '_'
    taken.add(name)
    return name


def _save(file, points, keys, chosen, arrays):
    """sweep.npz/.json: one array per numeric result value, over the swept inputs when they form a grid."""
    encoded = [[json.dumps(item['point'].get(key, None), sort_keys=True) for key in keys] for item in points]
    levels = [list(dict.fromkeys(row[k] for row in encoded)) for k in range(len(keys))]
    grid = len(set(map(tuple, encoded))) == len(points) == math.prod(map(len, levels)) and \
        all(set(item['point']) == set(keys) for item in points)
    taken, numbers, described = set(), {}, {}
    if grid:
        shape = [len(level) for level in levels]
        position = {tuple(row): sum(levels[k].index(row[k]) * math.prod(shape[k + 1:]) for k in range(len(keys)))
                    for row in encoded}
        order = [position[tuple(row)] for row in encoded]
        axes = []
        for key, level in zip(keys, levels):
            coordinates = [json.loads(v) for v in level]
            if all(_number(v) is not None for v in coordinates):
                name = _array_name(key, taken)
                numbers[name] = (coordinates, [len(coordinates)])
                described[name] = {'quantity': 'swept input ' + key}
                axes.append(name)
            else:
                axes.append({'name': key, 'labels': [v if isinstance(v, str) else json.dumps(v) for v in coordinates]})
    else:
        shape, order = [len(points)], list(range(len(points)))
        axes = [{'name': 'point', 'labels': [item['id'] for item in points]}]
        for key in keys:
            column = [_number(item['point'].get(key)) for item in points]
            if all(v is not None for v in column):
                name = _array_name(key, taken)
                numbers[name] = (column, shape)
                described[name] = {'quantity': 'swept input ' + key, 'axes': axes}
    skipped, results = [], 0
    for key in chosen:
        column = [_number(item['values'][key]) for item in points]
        if all(item['values'][key] is None or _number(item['values'][key]) is not None for item in points):
            flat = [None] * len(points)
            for n, value in zip(order, column):
                flat[n] = value
            name = _array_name(key, taken)
            numbers[name] = (flat, shape)
            described[name] = {'quantity': 'result ' + key, 'axes': axes, 'missing': 'NaN where a point failed or lacks the value'}
            results += 1
        else:
            skipped.append(key)
    if not results:
        return {'saved': None, 'not_saved': skipped}
    file.parent.mkdir(parents=True, exist_ok=True)
    written = arrays.write(file, numbers, described)
    return {'saved': 'sweep.npz', 'layout': 'grid' if grid else 'list', 'arrays': written['arrays'], 'not_saved': skipped}
