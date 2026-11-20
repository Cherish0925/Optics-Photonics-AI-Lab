"""Research programs that ship with the connector, one file per program.

A program is an ordinary native program: it reads INPUTS, writes files to
OUTPUT_DIR and sets RESULT, using the full API of its software, so it can
be run as it is or adapted. Its PROGRAM dictionary maps every input to a
default value and a description, names the domains the program belongs to,
and states what the program returns and which checks it reports. submit_calculation(tool, action=NAME) runs one;
software_details lists a tool's programs and returns the source of one.

A program is written in Python, or in the language of software bound to its
executable (Julia, MATLAB/Octave, Lua, Wolfram Language, Maple, Lumerical
script): then its leading comment holds the title, the physics and the same
declaration as JSON after a line PROGRAM (languages.declaration).
"""
import ast
import copy
from functools import lru_cache
from pathlib import Path
from .. import integrations

FOLDER = Path(__file__).parent


def describe(file, source=None):
    """Title, physics and PROGRAM dictionary of a program file, read without running it."""
    text = file.read_text(encoding='utf-8') if source is None else source
    if file.suffix != '.py':
        from .. import languages
        return languages.declaration(text, file.suffix)
    tree = ast.parse(text)
    doc = ast.get_docstring(tree) or ''
    spec = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                and any(getattr(target, 'id', None) == 'PROGRAM' for target in node.targets))
    title, _, about = doc.partition('\n')
    return {'title': title.strip(), 'about': ' '.join(about.split()), **spec}


@lru_cache(maxsize=1)
def builtin_catalog():
    """Repository-owned programs by tool and name."""
    from .. import languages
    found = {}
    for file in sorted(FOLDER.glob('*/*.*')):
        if file.suffix == '.py' or file.suffix in languages.COMMENTS:
            found.setdefault(file.parent.name, {})[file.stem] = {**describe(file), 'file': file}
    # Software of one language family shares programs: MATLAB runs those written for Octave.
    for tool, other in languages.FAMILIES.items():
        shared = {name: spec for name, spec in found.get(tool, {}).items() if spec.get('language') == other}
        if shared:
            found[other] = {**shared, **found.get(other, {})}
    return found


@integrations.synchronized
@lru_cache(maxsize=1)
def catalog():
    """Repository-owned and installed integration programs, without executing either."""
    from .. import integrations
    found = {tool: dict(items) for tool, items in builtin_catalog().items()}
    for package in integrations.registry()['packages']:
        for (tool, name), spec in package['programs'].items():
            found.setdefault(tool, {})[name] = spec
    return found


def examples():
    """One runnable example per tool: its first program with default inputs."""
    return {tool: (name, inputs(spec)) for tool, programs in catalog().items()
            for name, spec in list(programs.items())[:1]}


def inputs(spec):
    return {name: value for name, (value, _) in spec['inputs'].items()}


def listing(tool):
    """The programs of a tool as a software_details reply lists them: name, title and the names of the inputs."""
    return [{'name': name, 'title': spec['title'], **({'language': spec['language']} if spec.get('language') else {}),
             'inputs': list(spec['inputs']),
             **({'integration': spec['integration']['id']} if spec.get('integration') else {})}
            for name, spec in catalog().get(tool, {}).items()]


@integrations.synchronized
def details(tool, name=None):
    """Each program of a tool with its inputs (default and meaning), results and checks; with name, that one and its physics."""
    def described(name, spec):
        return {'name': name, 'title': spec['title'], **({'language': spec['language']} if spec.get('language') else {}),
                **({'about': spec['about']} if name == chosen else {}),
                'inputs': {key: {'default': value, 'about': about} for key, (value, about) in spec['inputs'].items()},
                'results': spec['results'], 'checks': spec.get('checks', ''),
                **({'integration': spec['integration']} if spec.get('integration') else {})}
    chosen = name
    found = catalog().get(tool, {})
    if name is not None:
        source(tool, name)   # an unknown name lists the programs of the tool
        return described(name, found[name])
    return [described(key, spec) for key, spec in found.items()]


def source(tool, name):
    found = catalog().get(tool, {})
    if name not in found:
        known = ', '.join(found) or 'none'
        raise ValueError(f'Unknown program {tool}/{name}; programs of {tool}: {known}. software_details lists them')
    spec = found[name]
    return spec['_source'] if '_source' in spec else spec['file'].read_text(encoding='utf-8')


def parameters(spec, given):
    """Default inputs replaced by the given ones; an unknown name lists the accepted names."""
    if not isinstance(given, dict):
        raise ValueError('inputs must be a JSON object')
    unknown = sorted(set(given) - set(spec['inputs']))
    if unknown:
        raise ValueError('Unknown input ' + ', '.join(unknown) + '; this program takes: ' + ', '.join(spec['inputs']))
    return {name: given.get(name, default) for name, (default, _) in spec['inputs'].items()}


def snapshot(step, tool=None):
    """Freeze an integration action for another interpreter and later continuation.

    Call after submission validation. The original action remains named; source,
    defaults and provider version no longer depend on the installed distribution.
    The returned private metadata is produced here, not accepted from clients.
    """
    tool = tool or step.get('tool')
    found = catalog().get(tool, {}).get(step.get('action'))
    if step.get('source') or step.get('script') or not found or not found.get('integration'):
        return dict(step)
    result = copy.deepcopy(step)
    result['script' if found.get('language') else 'source'] = found['_source']
    result['inputs'] = {**copy.deepcopy(inputs(found)), **result.get('inputs', {})}
    for point in result.get('points', []):
        point['inputs'] = {**copy.deepcopy(inputs(found)), **point['inputs']}
    provider = found['integration']
    result['_program'] = {'tool': tool, 'name': step['action'], 'integration': provider['id'],
                          'distribution': provider['distribution'], 'version': provider['version'],
                          **({'language': found['language']} if found.get('language') else {})}
    return result


def run(tool, name, given, output):
    """Run a program in this process, as the worker does; returns its RESULT."""
    from pathlib import Path as _Path
    if catalog().get(tool, {}).get(name, {}).get('language'):
        raise ValueError(f'{tool}/{name} runs in its software; submit it as a calculation')
    folder = _Path(output)
    folder.mkdir(parents=True, exist_ok=True)
    namespace = {'__name__': '__main__', '__file__': str(folder / 'program.py'), 'INPUTS': given,
                 'OUTPUT_DIR': folder, 'RESULT': None}
    exec(compile(source(tool, name), str(catalog()[tool][name]['file']), 'exec'), namespace)
    return namespace['RESULT']
