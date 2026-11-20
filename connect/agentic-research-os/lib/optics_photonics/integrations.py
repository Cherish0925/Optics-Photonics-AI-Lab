"""Data-only software integrations installed beside the connector.

An ``optics_photonics.integrations`` entry point names a package containing
``optics.json``. Discovery reads its manifest and program declarations without
importing the package. Scientific dependencies remain in the selected solver
environment. Install, upgrade and remove these distributions with pip.
"""
from functools import lru_cache, wraps
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import re
from threading import RLock
from urllib.parse import urlsplit
from urllib.request import url2pathname

GROUP = 'optics_photonics.integrations'
IDENTIFIER = re.compile(r'[a-z0-9][a-z0-9_.-]{0,99}\Z')
MODULE = re.compile(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\Z')
TEXT = ('name', 'method', 'summary', 'api', 'license', 'compute', 'usage', 'limit')
_metadata_lock = RLock()


def synchronized(function):
    """Keep related metadata reads in one refresh interval, never solver work."""
    @wraps(function)
    def read(*args, **kwargs):
        with _metadata_lock:
            return function(*args, **kwargs)
    # The lock also surrounds cache insertion: a computation started before a
    # refresh cannot repopulate a cleared cache with an older catalogue.
    for name in ('cache_clear', 'cache_info', 'cache_parameters'):
        if hasattr(function, name):
            setattr(read, name, getattr(function, name))
    return read


def identifier(value, what):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError(what + ' uses lowercase letters, digits, dots, hyphens or underscores')
    return value


def strings(value, what):
    if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value):
        raise ValueError(what + ' must be an array of nonempty strings')
    return value


def file_at(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError('A manifest file path must be relative to its package')
    file = (root / relative).resolve()
    if not file.is_relative_to(root.resolve()) or not file.is_file():
        raise ValueError('Missing file inside integration package: ' + relative)
    return file


def package_root(distribution, entry):
    if not MODULE.fullmatch(entry.value):
        raise ValueError('The entry point names a package, without a callable or extras')
    relative = Path(*entry.value.split('.'))
    candidates = [Path(distribution.locate_file(relative))]
    # Editable installs do not necessarily list source files in RECORD. Read the
    # standard direct-url metadata; do not execute an editable import finder.
    raw = distribution.read_text('direct_url.json')
    if raw:
        direct = json.loads(raw)
        url = urlsplit(direct.get('url', ''))
        if direct.get('dir_info', {}).get('editable') and url.scheme == 'file' and url.netloc in ('', 'localhost'):
            project = Path(url2pathname(url.path))
            candidates.extend((project / relative, project / 'src' / relative))
    for root in candidates:
        if (root / 'optics.json').is_file():
            return root.resolve()
    raise ValueError('Cannot find ' + str(relative / 'optics.json') +
                     '; include it as package data (editable installs support flat and src layouts)')


def connection(value):
    if not isinstance(value, dict) or value.get('kind') not in ('python', 'native', 'command', 'manual', 'data'):
        raise ValueError('connection.kind is python, native, command, manual or data')
    result = {'modules': [], 'distributions': [], 'pip': [], **value}
    known = {'kind', 'modules', 'distributions', 'pip', 'conda', 'julia', 'python', 'platforms', 'sources', 'routes',
             'environment_of', 'executable', 'environment', 'execution', 'installation', 'installation_note',
             'interface', 'native_program', 'session_adapter', 'upstream'}
    if set(result) - known:
        raise ValueError('Unknown connection fields: ' + ', '.join(sorted(set(result) - known)))
    for key in ('modules', 'distributions', 'pip', 'conda', 'julia', 'platforms', 'sources'):
        if key in result:
            strings(result[key], 'connection.' + key)
    routes = result.get('routes', [])
    if not isinstance(routes, list) or any(not isinstance(route, dict) or route.get('route') not in
            ('python', 'session', 'executable', 'automation', 'service', 'inside') for route in routes):
        raise ValueError('connection.routes lists python, session, executable, automation, service or inside routes')
    from . import languages
    for route in routes:
        if route.get('route') == 'executable' and route.get('language') and route['language'] not in languages.LANGUAGES:
            raise ValueError('An executable route uses a supported script language: ' + ', '.join(languages.LANGUAGES))
        for key in ('modules', 'platforms', 'sources', 'progids', 'pip'):
            if key in route:
                strings(route[key], 'connection.routes.' + key)
        for key in ('executables', 'locations', 'folders', 'siblings'):
            if key in route:
                if not isinstance(route[key], dict) or set(route[key]) - {'linux', 'macos', 'windows'}:
                    raise ValueError('connection.routes.' + key + ' maps linux, macos and windows to arrays')
                for names in route[key].values():
                    strings(names, 'connection.routes.' + key)
        if 'variables' in route and (not isinstance(route['variables'], dict) or
                                    any(not isinstance(v, str) for v in route['variables'].values())):
            raise ValueError('connection.routes.variables maps environment variable names to paths')
        if 'credentials' in route:
            credentials = route['credentials']
            if not isinstance(credentials, dict) or set(credentials) - {'variables', 'files'}:
                raise ValueError('connection.routes.credentials contains variables and/or files arrays')
            for values in credentials.values():
                strings(values, 'connection.routes.credentials')
        for key in ('marker', 'progid_pattern', 'server', 'language', 'about'):
            if key in route and not isinstance(route[key], str):
                raise ValueError('connection.routes.' + key + ' must be text')
        if 'progid_pattern' in route:
            re.compile(route['progid_pattern'])
    return result


def software(value, provider):
    if not isinstance(value, dict):
        raise ValueError('Each software entry must be an object')
    unknown = set(value) - {*TEXT, 'id', 'domains', 'group', 'sources', 'connection', 'translations'}
    if unknown:
        raise ValueError('Unknown software fields: ' + ', '.join(sorted(unknown)))
    key = identifier(value.get('id'), 'Software id')
    for field in ('name', 'summary', 'license'):
        if not isinstance(value.get(field), str) or not value[field].strip():
            raise ValueError(key + ' needs ' + field)
    domains = strings(value.get('domains', []), key + '.domains')
    for domain in domains:
        identifier(domain, 'Domain')
    group = value.get('group', 'limited')
    if group not in ('open', 'paid', 'limited'):
        raise ValueError(key + '.group is open, paid or limited')
    sources = value.get('sources', [])
    if not isinstance(sources, list) or any(not isinstance(source, dict) or not isinstance(source.get('label'), str)
            or not isinstance(source.get('url'), str) or not source['url'].startswith('https://') for source in sources):
        raise ValueError(key + '.sources lists {label, url} with https URLs')
    base = {'id': key, 'name': value['name'], 'group': group, 'cats': domains,
            'method': value.get('method', value['summary']), 'summary': value['summary'],
            'api': value.get('api', ''), 'license': value['license'], 'compute': value.get('compute', ''),
            'usage': value.get('usage', ''), 'limit': value.get('limit', ''), 'sources': sources,
            'route': 'api', 'mcp': {'kind': 'unverified'}, 'skill': {'kind': 'unverified'},
            'origin': 'integration', 'integration': provider}
    if any(not isinstance(base[field], str) for field in TEXT):
        raise ValueError(key + ' descriptions must be text')
    translations = value.get('translations', {})
    if not isinstance(translations, dict) or set(translations) - {'en', 'zh'}:
        raise ValueError(key + '.translations contains en and/or zh objects')
    descriptions = {}
    for language in ('en', 'zh'):
        translated = translations.get(language, {})
        if not isinstance(translated, dict) or set(translated) - set(TEXT) or any(not isinstance(v, str) for v in translated.values()):
            raise ValueError(key + '.translations.' + language + ' changes only text descriptions')
        descriptions[language] = {**base, **translated}
    return descriptions, connection(value.get('connection'))


def read(distribution, entry, provider):
    from . import programs
    root = package_root(distribution, entry)
    manifest = json.loads(file_at(root, 'optics.json').read_text(encoding='utf-8'))
    json.dumps(manifest, allow_nan=False)
    if not isinstance(manifest, dict) or type(manifest.get('schema_version')) is not int or manifest['schema_version'] != 1:
        raise ValueError('optics.json needs schema_version: 1')
    extra = set(manifest) - {'schema_version', 'software', 'programs', 'guides'}
    if extra:
        raise ValueError('Unknown integration fields: ' + ', '.join(sorted(extra)))
    result = {**provider, '_root': root, 'software': {}, 'connections': {}, 'programs': {}, 'guides': []}
    for field in ('software', 'programs', 'guides'):
        if not isinstance(manifest.get(field, []), list):
            raise ValueError(field + ' must be an array')
    for value in manifest.get('software', []):
        descriptions, configured = software(value, provider)
        tool = descriptions['en']['id']
        if tool in result['software']:
            raise ValueError('Duplicate software: ' + tool)
        result['software'][tool] = descriptions
        result['connections'][tool] = configured
    for value in manifest.get('programs', []):
        if not isinstance(value, dict) or set(value) - {'tool', 'name', 'path'}:
            raise ValueError('A program takes tool, path and an optional name')
        tool = identifier(value.get('tool'), 'Program tool')
        file = file_at(root, value.get('path'))
        name = identifier(value.get('name', file.stem), 'Program name')
        if (tool, name) in result['programs']:
            raise ValueError('Duplicate program: ' + tool + '/' + name)
        source = file.read_text(encoding='utf-8')
        spec = programs.describe(file, source)
        if not isinstance(spec.get('title'), str) or not spec['title'].strip() or not isinstance(spec.get('about'), str) or \
                not isinstance(spec.get('results'), str) or not spec['results'].strip():
            raise ValueError(tool + '/' + name + ' needs a title and results description')
        strings(spec.get('domains'), tool + '/' + name + '.domains')
        from . import languages
        if spec.get('language') and spec['language'] not in languages.LANGUAGES:
            raise ValueError(tool + '/' + name + ' declares an unsupported language')
        if not isinstance(spec.get('inputs'), dict) or any(not isinstance(key, str) or not key or
                not isinstance(pair, (list, tuple)) or len(pair) != 2 or not isinstance(pair[1], str)
                for key, pair in spec['inputs'].items()):
            raise ValueError(tool + '/' + name + '.inputs maps input names to [default, description]')
        if not isinstance(spec.get('checks', ''), str):
            raise ValueError(tool + '/' + name + '.checks must be text')
        json.dumps(spec, allow_nan=False)
        result['programs'][tool, name] = {**spec, 'file': file, '_source': source, 'integration': provider}
    seen = set()
    for value in manifest.get('guides', []):
        if not isinstance(value, dict) or set(value) - {'name', 'title', 'language', 'path', 'tools'}:
            raise ValueError('A guide takes name, title, path, language and optional tools')
        name = identifier(value.get('name'), 'Guide name')
        language = value.get('language', 'en')
        if language not in ('en', 'zh') or (name, language) in seen:
            raise ValueError('Guide names are unique within each language, en or zh')
        if not isinstance(value.get('title'), str) or not value['title'].strip():
            raise ValueError('A guide needs a title')
        seen.add((name, language))
        result['guides'].append({'name': name, 'title': value['title'], 'language': language,
                                'tools': strings(value.get('tools', []), 'Guide tools'),
                                'file': file_at(root, value.get('path'))})
    return result


@synchronized
def registry():
    # Repository generators publish repository-owned content, independently of
    # integration packages installed on the maintainer's machine.
    return {'packages': [], 'errors': []} if os.environ.get('OPTICS_BUILTIN_ONLY') == '1' else _registry()


@lru_cache(maxsize=1)
def _registry():
    from . import catalogue, native, programs
    builtin_tools = {item['id'] for item in catalogue.builtin_catalogue()}
    builtin_programs = {(tool, name) for tool, found in programs.builtin_catalog().items() for name in found}
    builtin_programs |= {(tool, name) for tool in native.ADAPTERS for name in native.details(tool)['actions']}
    packages, errors, seen = [], [], set()
    entries = [(distribution, entry) for distribution in metadata.distributions()
               for entry in distribution.entry_points if entry.group == GROUP]
    entries.sort(key=lambda pair: (pair[0].metadata.get('Name', '').casefold(), pair[1].name))
    for distribution, entry in entries:
        distribution_name = distribution.metadata.get('Name') or entry.name
        normalized = re.sub(r'[-_.]+', '-', distribution_name).lower()
        provider = {'id': normalized + ':' + entry.name, 'distribution': distribution_name,
                    'version': distribution.version, 'entry': entry.name}
        try:
            package = read(distribution, entry, provider)
            identity = (package['id'], package['version'], package['_root'])
            if identity in seen:
                continue  # editable sources and site metadata can describe the same installation
            seen.add(identity)
            collisions = set(package['software']) & builtin_tools
            if collisions:
                raise ValueError('Software already in the catalogue: ' + ', '.join(sorted(collisions)) +
                                 '; add distinct programs to it without declaring its identity again')
            collisions = set(package['programs']) & builtin_programs
            if collisions:
                raise ValueError('Programs already provided: ' + ', '.join('/'.join(key) for key in sorted(collisions)))
            packages.append(package)
        except (ValueError, TypeError, KeyError, OSError, SyntaxError, StopIteration, re.error) as error:
            errors.append({**provider, 'error': str(error) or type(error).__name__})
    # No installation order decides which package owns an identity. All sides of
    # a conflicting declaration are excluded; unrelated integrations keep working.
    owners = {}
    for package in packages:
        keys = [('integration', package['id']), *(('software', name) for name in package['software']),
                *(('program', tool + '/' + name) for tool, name in package['programs'])]
        for key in keys:
            owners.setdefault(key, []).append(package)
    conflicts = {}
    for key, providers in owners.items():
        if len(providers) > 1:
            for package in providers:
                conflicts.setdefault(id(package), []).append(' '.join(key))
    active = []
    for package in packages:
        if id(package) in conflicts:
            errors.append({key: package[key] for key in ('id', 'distribution', 'version', 'entry')} |
                          {'error': 'Conflicting declarations: ' + ', '.join(conflicts[id(package)])})
        else:
            active.append(package)
    while True:
        known = builtin_tools | {tool for package in active for tool in package['software']}
        remaining = []
        for package in active:
            missing = {tool for tool, _ in package['programs']} - known
            missing |= {tool for guide in package['guides'] for tool in guide['tools']} - known
            if missing:
                errors.append({key: package[key] for key in ('id', 'distribution', 'version', 'entry')} |
                              {'error': 'Unknown software: ' + ', '.join(sorted(missing))})
            else:
                remaining.append(package)
        if len(remaining) == len(active):
            return {'packages': active, 'errors': errors}
        active = remaining


@synchronized
def _refresh():
    """Reload metadata after installing, upgrading or removing a distribution."""
    from . import catalogue, programs
    _registry.cache_clear()
    programs.catalog.cache_clear()
    for name in ('catalogue', 'connections', 'program_texts', 'search_index', 'ranked_index', 'domain_programs', 'route_kinds'):
        getattr(catalogue, name).cache_clear()


refresh = _refresh


@synchronized
def listing(refresh=False):
    if refresh:
        _refresh()
    found = registry()
    return {'packages': [{key: package[key] for key in ('id', 'distribution', 'version', 'entry')} |
                         {'software': list(package['software']),
                          'programs': [tool + '/' + name for tool, name in package['programs']],
                          'guides': [{key: value for key, value in guide.items() if key != 'file'}
                                     for guide in package['guides']]}
                         for package in found['packages']], 'errors': list(found['errors'])}


def references(tool, language='en'):
    """Short links to installed guides relevant to one software entry."""
    return [{'integration': package['id'], 'topic': guide['name'], 'title': guide['title'], 'language': language}
            for package in registry()['packages'] for guide in package['guides']
            if guide['language'] == language and (tool in guide['tools'] or not guide['tools'] and
                (tool in package['software'] or any(key[0] == tool for key in package['programs'])))]


@synchronized
def guide(integration, topic, language='en'):
    if language not in ('en', 'zh'):
        raise ValueError('Use en or zh for language')
    package = next((package for package in registry()['packages'] if package['id'] == integration), None)
    if package is None:
        raise ValueError('Unknown integration: ' + str(integration) + '; software_integrations lists installed packages and errors')
    found = next((guide for guide in package['guides'] if guide['name'] == topic and guide['language'] == language), None)
    if found is None:
        topics = ', '.join(guide['name'] + ' (' + guide['language'] + ')' for guide in package['guides']) or 'none'
        raise ValueError('Unknown integration guide: ' + str(topic) + '; available: ' + topics)
    return {'integration': integration, 'topic': topic, 'language': language,
            'text': found['file'].read_text(encoding='utf-8')}
