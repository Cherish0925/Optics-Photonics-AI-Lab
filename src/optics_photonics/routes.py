"""How the environment reaches each software, finding installations of it, and binding them.

A route is one way to drive a software:

  python      an interpreter imports its module: from a pip or conda recipe, or a
              module that ships inside the installation (sdk_path)
  session     a background job owns a COMSOL, Lumerical, OpticStudio or CST session
  executable  its executable runs a program in its own language (script), or a Python
              program drives it with RUN
  automation  a Windows automation (COM) server that a Python program holds as APP
  service     a client library reaches a running application, a server or a cloud
  inside      its scripts run inside its own application; files carry inputs and results

Discovery reads PATH, the usual installation folders, the variables that name an
installation, folders given as roots and, on Windows, the registry. It starts nothing.
"""
import glob
import os
from pathlib import Path
import platform
import re
import shutil
import sys
from . import environments, languages

RUNNABLE = ('python', 'session', 'executable', 'automation', 'service')


def system():
    return {'Windows': 'windows', 'Darwin': 'macos'}.get(platform.system(), 'linux')


def routes(tool, path=None, record=None):
    """Every route of a tool, the first ones run unattended."""
    from . import native
    record = record or environments.software(tool, path=path)['connection']
    listed = [dict(route) for route in record.get('routes', [])]
    found = []
    if record['kind'] == 'python' and record.get('modules') and not any(r['route'] == 'python' for r in listed):
        found.append({'route': 'python', 'modules': record['modules'],
                      'install': 'conda' if record.get('conda') else 'pip' if record.get('pip') else None})
    if record['kind'] == 'command':
        found.append({'route': 'executable', 'language': None, 'about': 'A registered executable that reads the request itself.'})
    if tool in native.ADAPTERS:
        adapter = native.ADAPTERS[tool]
        found.append({'route': 'session', 'platforms': adapter['platforms'], 'modules': adapter['modules'], 'sources': adapter['sources']})
    if record.get('julia'):
        for route in listed:
            if route['route'] == 'executable': route['install'] = 'julia: ' + ', '.join(record['julia'])
    if record.get('executable') and record.get('conda'):
        for route in listed:
            if route['route'] == 'executable': route['install'] = 'conda on ' + ', '.join(record.get('platforms') or ['every platform'])
    found += listed
    if not any(route['route'] in RUNNABLE for route in found) and not any(route['route'] == 'inside' for route in found) \
            and record['kind'] != 'data':
        found.append({'route': 'inside', 'language': record.get('interface', ''), 'sources': record.get('sources', [])[:1]})
    for route in found:
        if route.get('language') and route['route'] == 'executable':
            route['program'] = languages.guide(route['language'])
    return found


def expand(pattern):
    """A location pattern with {VARIABLE} placeholders, or None when a variable is not set."""
    values = {'HOME': str(Path.home())}
    def value(match):
        name = match.group(1)
        found = os.environ.get(name) or values.get(name)
        if not found: raise KeyError(name)
        return found.replace('\\', '/')
    try:
        return re.sub(r'\{([A-Za-z_][A-Za-z0-9_()]*)\}', value, pattern)
    except KeyError:
        return None


def runnable(file):
    file = Path(file)
    return file.is_file() and (os.name == 'nt' or os.access(file, os.X_OK))


def nested(root, relative, depth=4):
    """Files root/relative, root/*/relative, ... down to depth folders; bounded so that discovery stays fast."""
    root = Path(root).expanduser()
    if not root.is_dir():
        return []
    found = []
    for level in range(depth + 1):
        found += root.glob('*/' * level + relative)
    return found


def executables(tool, route, roots, here):
    names = route.get('executables', {}).get(here, [])
    candidates = []
    for name in names:
        located = shutil.which(name)
        if located: candidates.append((Path(located), 'PATH'))
        for pattern in route.get('locations', {}).get(here, []):
            folder = expand(pattern)
            if folder:
                candidates += [(Path(match) / name, 'location') for match in glob.glob(folder)]
        for root in roots:
            candidates += [(match, 'root') for match in nested(root, name) + nested(root, 'bin/' + name)]
    found, seen = [], set()
    for file, how in candidates:
        if not runnable(file):
            continue
        key = os.path.normcase(str(file.resolve()))
        if key in seen:
            continue
        seen.add(key)
        siblings = {name: str(file.parent / name) for name in route.get('siblings', {}).get(here, []) if runnable(file.parent / name)}
        entry = {'tool': tool, 'route': 'executable', 'executable': str(file), 'language': route.get('language'), 'found_by': how,
                 'bind': {'tool': tool, 'route': 'executable', 'executable': str(file)}}
        if siblings: entry['siblings'] = siblings
        found.append(entry)
    return found


def folders(tool, route, roots, here):
    """Folders that hold a Python module shipped with an installation."""
    marker = route['marker']
    candidates = []
    for variable, relative in route.get('variables', {}).items():
        if os.environ.get(variable):
            candidates.append((Path(os.environ[variable]) / relative, variable))
    for pattern in route.get('folders', {}).get(here, []):
        folder = expand(pattern)
        if folder: candidates += [(Path(match), 'location') for match in glob.glob(folder)]
    for root in roots:
        candidates += [(match.parents[len(Path(marker).parts) - 1], 'root') for match in nested(root, marker)]
    found, seen = [], set()
    for folder, how in candidates:
        if not (folder / marker).exists():
            continue
        key = os.path.normcase(str(folder.resolve()))
        if key in seen:
            continue
        seen.add(key)
        found.append({'tool': tool, 'route': route['route'], 'sdk_path': str(folder.resolve()), 'modules': route.get('modules', []),
                      'found_by': how, 'bind': {'tool': tool, 'route': 'python', 'sdk_path': str(folder.resolve())}})
    return found


def registry():
    """Names of the automation servers registered on this Windows computer."""
    import winreg
    names, index = [], 0
    while True:
        try:
            name = winreg.EnumKey(winreg.HKEY_CLASSES_ROOT, index)
        except OSError:
            break
        index += 1
        if '.' in name and not name.startswith('.'):
            names.append(name)
    return names


def registered(progid):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, progid + '\\CLSID'):
            return True
    except OSError:
        return False


def servers(tool, route, names):
    found = [progid for progid in route.get('progids', []) if registered(progid)]
    if route.get('progid_pattern'):
        pattern = re.compile(route['progid_pattern'])
        found += [name for name in names() if pattern.search(name) and name not in found and registered(name)]
    return [{'tool': tool, 'route': 'automation', 'progid': progid, 'found_by': 'registry',
             'bind': {'tool': tool, 'route': 'automation', 'progid': progid}} for progid in found]


def credentials(tool, route):
    """Whether the credentials of a service are configured; their values are not read."""
    present = {variable: bool(os.environ.get(variable)) for variable in route['credentials'].get('variables', [])}
    for pattern in route['credentials'].get('files', []):
        file = expand(pattern)
        if file: present[file] = Path(file).is_file()
    return {'tool': tool, 'route': 'service', 'credentials': present, 'configured': any(present.values()),
            'server': route.get('server')}


def discover(roots=None, tool=None, path=None):
    """Installed software of every route, each with the arguments that bind it."""
    from .catalogue import catalogue
    tools = [tool] if tool else [item['id'] for item in catalogue()] + [item['id'] for item in environments.registered(path)]
    here, roots = system(), [Path(root).expanduser() for root in roots or []]
    names = []
    def listed():
        if not names: names.extend(registry())
        return names
    found = []
    for name in tools:
        for route in environments.software(name, path=path)['connection'].get('routes', []):
            if route['route'] == 'executable' and route.get('executables'):
                found += executables(name, route, roots, here)
            elif route['route'] in ('python', 'service') and route.get('marker'):
                found += folders(name, route, roots, here)
            elif route['route'] == 'automation' and here == 'windows':
                found += servers(name, route, listed)
            elif route['route'] == 'service' and route.get('credentials'):
                found.append(credentials(name, route))
    return found


def first(tool, route_kind, path=None):
    return next((route for route in routes(tool, path) if route['route'] == route_kind), None)


def driver_python(path=None):
    """The interpreter of driver programs: the scipy environment when one is connected, else the connector's own."""
    bound = environments.read(path)['tools'].get('scipy')
    return bound['python'] if bound and bound.get('kind') == 'python' else sys.executable


def bind(tool, *, route=None, executable=None, python=None, sdk_path=None, progid=None, project=None, language=None,
         threads=1, concurrency=1, cwd=None, requirements=None, env=None, path=None):
    """Connect an installed software by one of its routes; without a route, the one its arguments or discovery name.

    language selects the script language of an executable, for software outside the catalogue or another build.
    """
    chosen = environments.settings(threads, concurrency, cwd, requirements, env)
    if language is not None:
        languages.language(language)
    if route is None:
        route = 'executable' if executable else 'automation' if progid else 'python' if (sdk_path or python) else None
    if route is None:
        found = [entry for entry in discover(tool=tool, path=path) if 'bind' in entry]
        if not found:
            ways = ', '.join(sorted({r['route'] for r in routes(tool, path)}))
            raise ValueError(f'No installation of {tool} was found on PATH or in its usual folders (routes: {ways}). '
                             'Give executable, sdk_path or progid, or roots to discover_native_software')
        arguments = {k: v for k, v in found[0]['bind'].items() if k != 'tool'}
        return bind(tool, threads=threads, concurrency=concurrency, cwd=cwd, requirements=requirements, env=env, path=path,
                    python=python, project=project, language=language, **arguments)
    if route == 'executable':
        spec = first(tool, 'executable', path) or {}
        if not executable:
            located = [entry['executable'] for entry in discover(tool=tool, path=path) if entry['route'] == 'executable']
            if not located:
                raise ValueError(f'No executable of {tool} was found on PATH or in its usual folders; give executable')
            executable = located[0]
        found = shutil.which(executable) or (str(Path(executable).expanduser().resolve()) if runnable(Path(executable).expanduser()) else None)
        if not found:
            raise ValueError('Executable was not found: ' + str(executable))
        here = system()
        siblings = {name: str(Path(found).parent / name) for name in spec.get('siblings', {}).get(here, [])
                    if runnable(Path(found).parent / name)}
        connection = {'kind': 'executable', 'executable': found, 'language': language or spec.get('language'), 'siblings': siblings,
                      'python': os.path.abspath(os.path.expanduser(python)) if python else driver_python(path)}
        if project:
            connection['project'] = str(Path(project).expanduser().resolve())
        # A conda environment's executable may need the variables its activation would set (Octave reads OCTAVE_HOME).
        prefix = Path(found).resolve().parents[1]
        variables = environments.software(tool, path=path)['connection'].get('executable', {}).get('variables', {})
        if variables and (prefix / 'conda-meta').is_dir():
            chosen['env'] = {**{k: v.replace('{prefix}', str(prefix)) for k, v in variables.items()}, **chosen['env']}
    elif route == 'automation':
        if system() != 'windows':
            raise ValueError('Automation servers run on Windows; run the MCP connection on the Windows workstation')
        spec = first(tool, 'automation', path) or {}
        progid = progid or next((entry['progid'] for entry in servers(tool, spec, registry)), None)
        if not progid or not registered(progid):
            raise ValueError(f'No registered automation server{" " + progid if progid else ""} for {tool}')
        interpreter = os.path.abspath(os.path.expanduser(python or sys.executable))
        inspected = environments.inspect(interpreter, ['win32com.client', 'pythoncom'], ['pywin32'])
        if not all(inspected['modules'].values()):
            raise ValueError('The interpreter needs pywin32: python -m pip install pywin32')
        connection = {'kind': 'automation', 'progid': progid, 'python': inspected['python']}
    elif route == 'python':
        return environments.bind(tool, python=python, paths=[sdk_path] if sdk_path else None, threads=threads,
                                 concurrency=concurrency, cwd=cwd, requirements=requirements, env=env, path=path)
    else:
        raise ValueError('route is executable, automation or python; sessions bind with python and sdk_path')
    connection.update(chosen)
    item = environments.software(tool, path=path)
    if item.get('origin') in ('local', 'integration'):
        connection['definition'] = item
    environments.update('tools', tool, connection, path)
    return {'tool': tool, **connection}
