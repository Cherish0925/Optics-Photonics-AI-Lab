"""Optimize the inputs of a program inside its own process.

The program runs once per evaluation with the variables set in its inputs, in
the same interpreter and, for a commercial solver, the same session, so an
evaluation costs only the calculation. variables maps an input, or one
element inside it addressed with dots as in a sweep, to [low, high] or to
{"low", "high", "scale": "log", "integer": true}. The objective is the value
at a dotted path of RESULT to minimize or maximize. Methods:

- differential-evolution: global search from a Latin-hypercube population
  (DE/rand/1/bin), followed by a Nelder-Mead polish of the best point;
- nelder-mead: local search from the current inputs.

Bounds are enforced by searching the unit cube. An evaluation that fails, or
whose RESULT lacks the objective, counts as infinitely bad and is recorded.
history.jsonl grows with every evaluation. The optimization checkpoint names
the current best files while running or stopped; best/ holds them on completion.
Only the standard library is used.
"""
import json
import math
import os
from pathlib import Path
import random
import shutil

METHODS = ('differential-evolution', 'nelder-mead')


def checked(spec):
    """The optimization request with defaults filled in; a malformed one is an error that says what to change."""
    if not isinstance(spec, dict):
        raise ValueError('optimize is an object with variables and minimize or maximize')
    extra = set(spec) - {'variables', 'minimize', 'maximize', 'method', 'evaluations', 'seed', 'tolerance'}
    if extra:
        raise ValueError('optimize takes variables, minimize or maximize, method, evaluations, seed and tolerance; not ' + ', '.join(sorted(extra)))
    variables = spec.get('variables')
    if not isinstance(variables, dict) or not variables:
        raise ValueError('optimize.variables maps inputs to [low, high] or {"low", "high", "scale", "integer"}')
    bounds = {}
    for key, item in variables.items():
        item = {'low': item[0], 'high': item[1]} if isinstance(item, list) and len(item) == 2 else item
        if not isinstance(item, dict) or set(item) - {'low', 'high', 'scale', 'integer'} or not {'low', 'high'} <= set(item):
            raise ValueError(f'optimize.variables.{key} is [low, high] or {{"low", "high", "scale", "integer"}}')
        low, high = item['low'], item['high']
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (low, high)) or low >= high:
            raise ValueError(f'optimize.variables.{key}: low and high are finite numbers with low < high')
        scale = item.get('scale', 'linear')
        if scale not in ('linear', 'log') or scale == 'log' and low <= 0:
            raise ValueError(f'optimize.variables.{key}: scale is linear or log, and log needs low > 0')
        integer = item.get('integer', False)
        if type(integer) is not bool or integer and math.ceil(low) > math.floor(high):
            raise ValueError(f'optimize.variables.{key}: integer must be boolean and its bounds must contain an integer')
        bounds[str(key)] = {'low': low, 'high': high, 'scale': scale, 'integer': integer}
    if ('minimize' in spec) == ('maximize' in spec) or not isinstance(spec.get('minimize', spec.get('maximize')), str):
        raise ValueError('optimize needs minimize or maximize: the dotted path of a number in RESULT, such as R.0')
    method = spec.get('method', 'differential-evolution')
    if method not in METHODS:
        raise ValueError('optimize.method is ' + ' or '.join(METHODS))
    evaluations = spec.get('evaluations', 100 * len(bounds) + 100)
    if type(evaluations) is not int or not 2 <= evaluations <= 100000:
        raise ValueError('optimize.evaluations is an integer between 2 and 100000')
    seed, tolerance = spec.get('seed', 0), spec.get('tolerance', 1e-8)
    if type(seed) is not int or isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('optimize.seed is an integer and optimize.tolerance a finite positive number')
    goal = 'minimize' if 'minimize' in spec else 'maximize'
    return {'variables': bounds, 'goal': goal, 'path': spec[goal], 'method': method, 'evaluations': evaluations,
            'seed': seed, 'tolerance': float(tolerance)}


def value_of(bound, u):
    """The variable at position u of the unit interval."""
    u = min(1.0, max(0.0, u))
    if bound['scale'] == 'log':
        value = bound['low'] * (bound['high'] / bound['low']) ** u
    else:
        value = bound['low'] + (bound['high'] - bound['low']) * u
    return min(math.floor(bound['high']), max(math.ceil(bound['low']), round(value))) if bound['integer'] else value


def position_of(bound, value):
    """The position in the unit interval of a starting value, or None when it lies outside the bounds."""
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not bound['low'] <= value <= bound['high']:
        return None
    if bound['scale'] == 'log':
        return math.log(value / bound['low']) / math.log(bound['high'] / bound['low'])
    return (value - bound['low']) / (bound['high'] - bound['low'])


def nelder_mead(f, start, evaluations, tolerance=1e-8, step=0.1):
    """Minimize f over the unit cube from start; returns (point, value, evaluations used, converged)."""
    n = len(start)
    clip = lambda x: [min(1.0, max(0.0, v)) for v in x]  # noqa: E731
    simplex = [clip(start)]
    for i in range(n):
        point = list(simplex[0])
        point[i] = point[i] + step if point[i] + step <= 1 else point[i] - step
        simplex.append(point)
    simplex = simplex[:evaluations]
    values = [f(x) for x in simplex]
    used = len(values)
    while used < evaluations:
        order = sorted(range(n + 1), key=values.__getitem__)
        simplex, values = [simplex[i] for i in order], [values[i] for i in order]
        size = max(max(abs(a - b) for a, b in zip(x, simplex[0])) for x in simplex[1:])
        if math.isfinite(values[-1]) and abs(values[-1] - values[0]) <= tolerance * (abs(values[0]) + tolerance) and size <= tolerance ** 0.5:
            return simplex[0], values[0], used, True
        centre = [sum(x[i] for x in simplex[:-1]) / n for i in range(n)]
        worst = simplex[-1]
        reflected = clip([c + (c - w) for c, w in zip(centre, worst)])
        fr = f(reflected)
        used += 1
        if used >= evaluations:
            if fr < values[-1]:
                simplex[-1], values[-1] = reflected, fr
            break
        if values[0] <= fr < values[-2]:
            simplex[-1], values[-1] = reflected, fr
            continue
        if fr < values[0]:
            expanded = clip([c + 2 * (c - w) for c, w in zip(centre, worst)])
            fe = f(expanded)
            used += 1
            simplex[-1], values[-1] = (expanded, fe) if fe < fr else (reflected, fr)
            continue
        outside = fr < values[-1]
        contracted = clip([c + 0.5 * ((r if outside else w) - c) for c, w, r in zip(centre, worst, reflected)])
        fc = f(contracted)
        used += 1
        if fc < min(fr, values[-1]):
            simplex[-1], values[-1] = contracted, fc
            continue
        for k in range(1, n + 1):
            if used >= evaluations:
                break
            simplex[k] = [b + 0.5 * (x - b) for b, x in zip(simplex[0], simplex[k])]
            values[k] = f(simplex[k])
            used += 1
    k = min(range(len(values)), key=values.__getitem__)
    return simplex[k], values[k], used, False


def differential_evolution(f, n, evaluations, seed=0, start=None, tolerance=1e-8, weight=0.7, crossover=0.9):
    """Minimize f over the unit cube by DE/rand/1/bin from a Latin hypercube (and start, if given)."""
    rng = random.Random(seed)
    size = max(8, 10 * n)
    columns = [rng.sample(range(size), size) for _ in range(n)]
    members = [[(columns[d][i] + rng.random()) / size for d in range(n)] for i in range(size)]
    if start is not None:
        members[0] = list(start)
    values = []
    for member in members[:evaluations]:
        values.append(f(member))
    members, used = members[:len(values)], len(values)
    while used < evaluations and len(members) >= 4:
        for i in range(len(members)):
            if used >= evaluations:
                break
            a, b, c = rng.sample([j for j in range(len(members)) if j != i], 3)
            forced = rng.randrange(n)
            trial = []
            for d in range(n):
                if d == forced or rng.random() < crossover:
                    v = members[a][d] + weight * (members[b][d] - members[c][d])
                    if v < 0:
                        v = rng.random() * members[a][d]
                    elif v > 1:
                        v = members[a][d] + rng.random() * (1 - members[a][d])
                    trial.append(v)
                else:
                    trial.append(members[i][d])
            value = f(trial)
            used += 1
            if value <= values[i]:
                members[i], values[i] = trial, value
        if all(map(math.isfinite, values)) and max(values) - min(values) <= tolerance * (abs(min(values)) + tolerance):
            k = min(range(len(values)), key=values.__getitem__)
            return members[k], values[k], used, True
    k = min(range(len(values)), key=values.__getitem__)
    return members[k], values[k], used, False


def run(execute, inputs, spec, output, defaults=None, *, checkpoint=None):
    """Optimize: execute(inputs, folder) runs the program once and returns its RESULT."""
    from . import arrays, studies
    spec = checked(spec)
    output = Path(output).resolve()
    keys = list(spec['variables'])
    bounds = [spec['variables'][key] for key in keys]
    sign = 1.0 if spec['goal'] == 'minimize' else -1.0
    probe = json.loads(json.dumps(inputs))
    for key, bound in zip(keys, bounds):
        studies.assign(probe, key, value_of(bound, 0.5), defaults)  # a key that addresses nothing fails here, once
    final_folder, best_folder = output / 'best', None
    history = []
    best = {'score': math.inf, 'values': None, 'result': None, 'objective': None}
    seen = {}
    restored = checkpoint.load() if checkpoint is not None else None
    if restored is not None:
        if (not isinstance(restored, dict) or restored.get('search') != 1
                or type(restored.get('evaluations')) is not int or restored['evaluations'] < 0
                or not isinstance(restored.get('best'), dict) or 'history' not in checkpoint.files):
            raise ValueError('Saved optimization progress is incomplete; inspect its checkpoint and history')
        with checkpoint.files['history'].open(encoding='utf-8') as stream:
            for number in range(1, restored['evaluations'] + 1):
                try:
                    entry = json.loads(next(stream))
                    if (entry.get('evaluation') != number or not isinstance(entry.get('variables'), dict)
                            or not ('error' in entry or isinstance(entry.get('objective'), (int, float))
                                    and math.isfinite(entry['objective']))):
                        raise ValueError('invalid evaluation')
                except (StopIteration, ValueError, TypeError, AttributeError) as error:
                    raise ValueError(f'Saved optimization history is incomplete at evaluation {number}') from error
                history.append(entry)
                seen[json.dumps(entry['variables'], sort_keys=True)] = sign * entry['objective'] if 'objective' in entry else math.inf
        best.update(restored['best'])
        if best['values'] is not None:
            best['score'] = sign * best['objective']
            best_folder = checkpoint.files.get('best')
            if best_folder is None:
                raise ValueError('Saved optimization progress has no best model files')
    prior = set(seen)
    reused = set()
    log = (output / 'history.jsonl').open('w', encoding='utf-8')
    for entry in history:
        log.write(json.dumps(entry, allow_nan=False) + '\n')
    log.flush()

    def save():
        if checkpoint is not None:
            log.flush()
            os.fsync(log.fileno())
            checkpoint.save({'search': 1, 'evaluations': len(history),
                             'best': {key: value for key, value in best.items() if key != 'score'}},
                            files={'history': output / 'history.jsonl', **({'best': best_folder} if best_folder else {})})

    def objective(u):
        nonlocal best_folder
        chosen = {key: value_of(bound, x) for key, bound, x in zip(keys, bounds, u)}
        tag = json.dumps(chosen, sort_keys=True)
        if tag in seen:  # integer variables can map different positions to one input
            if tag in prior:
                reused.add(tag)
            return seen[tag]
        entry = {'evaluation': len(history) + 1, 'variables': chosen}
        trial = output / 'evaluations' / ('evaluation-' + str(entry['evaluation']).zfill(6))
        old_best = best_folder
        score = math.inf
        try:
            given = json.loads(json.dumps(inputs))
            for key, value in chosen.items():
                studies.assign(given, key, value, defaults)
            shutil.rmtree(trial, ignore_errors=True)
            trial.mkdir(parents=True)
            result = execute(given, trial)
            value = studies.pick(result, spec['path'])
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                raise ValueError(f"RESULT has no finite number at {spec['path']}")
            entry['objective'], score = float(value), sign * float(value)
            if score < best['score']:
                best_folder = trial
                best.update(score=score, values=chosen, result=result, objective=float(value), evaluation=entry['evaluation'])
        except Exception as error:  # a failed evaluation is a bad point, not the end of the search
            entry['error'] = f'{type(error).__name__}: {error}'[-500:]
        history.append(entry)
        log.write(json.dumps(entry, allow_nan=False) + '\n')
        log.flush()
        seen[tag] = score
        save()
        # An older attempt stays intact. Within this attempt the committed state
        # no longer names the previous best, so its large files can be released.
        if old_best and old_best != best_folder and old_best.is_relative_to(output / 'evaluations'):
            shutil.rmtree(old_best, ignore_errors=True)
        if trial != best_folder:
            shutil.rmtree(trial, ignore_errors=True)
        return score

    start = [position_of(bound, studies.pick({**(defaults or {}), **inputs}, key)) for key, bound in zip(keys, bounds)]
    start = None if None in start else start
    budget, tolerance = spec['evaluations'], spec['tolerance']
    try:
        if spec['method'] == 'nelder-mead':
            _, _, _, converged = nelder_mead(objective, start or [0.5] * len(keys), budget, tolerance)
        else:
            polish = max(len(keys) + 2, budget // 5) if budget > 10 * len(keys) + 20 else 0
            point, _, used, converged = differential_evolution(objective, len(keys), budget - polish, spec['seed'], start, tolerance)
            if polish and best['values'] is not None:
                _, _, _, converged = nelder_mead(objective, point, polish, tolerance, step=0.02)
        if best_folder is not None:
            if best_folder != final_folder:
                # Keep the previous snapshot valid until the new one commits.
                shutil.copytree(best_folder, final_folder, dirs_exist_ok=True)
                best_folder = final_folder
            save()
    finally:
        log.close()
    if best['values'] is None:
        failures = [entry.get('error') for entry in history if entry.get('error')]
        raise RuntimeError(f'All {len(history)} evaluations failed; the last: {failures[-1] if failures else "no result"}')
    shutil.rmtree(output / 'evaluations', ignore_errors=True)
    named, taken = {}, set()
    axis = [{'name': 'evaluation', 'start': 1, 'step': 1}]
    columns = {'objective': ([entry.get('objective') for entry in history], f"{spec['path']} of each evaluation")}
    running, trace = math.inf, []
    for entry in history:
        running = min(running, sign * entry['objective']) if 'objective' in entry else running
        trace.append(sign * running if math.isfinite(running) else None)
    columns['best_so_far'] = (trace, f"best {spec['path']} after each evaluation")
    for key in keys:
        columns[key] = ([entry['variables'][key] for entry in history], 'variable ' + key)
    for key, (values, quantity) in columns.items():
        named[studies._array_name(key, taken)] = ([None if v is None else float(v) for v in values], [len(history)], quantity)
    arrays.write(output / 'history', {name: (values, shape) for name, (values, shape, _) in named.items()},
                 {name: {'quantity': quantity, 'axes': axis} for name, (_, _, quantity) in named.items()})
    return {'best': best['values'], 'objective': {'path': spec['path'], 'goal': spec['goal'], 'value': best['objective']},
            'method': spec['method'], 'evaluations': len(history), 'failed': sum('error' in entry for entry in history),
            **({'reused_evaluations': len(reused)} if checkpoint is not None else {}),
            'converged': converged, 'best_evaluation': best['evaluation'], 'result': best['result'],
            'files': 'best/', 'history': 'history.npz'}
