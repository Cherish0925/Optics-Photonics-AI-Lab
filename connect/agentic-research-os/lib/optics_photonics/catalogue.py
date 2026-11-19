"""One catalogue for the website, command line, plugins and MCP."""
import difflib
from functools import lru_cache
import json
import re
import unicodedata
from pathlib import Path

from . import programs


def resources():
    installed = Path(__file__).parent / 'resources'
    return installed if installed.is_dir() else Path(__file__).resolve().parents[2]


@lru_cache(maxsize=2)
def catalogue(language='en'):
    if language not in {'en', 'zh'}:
        raise ValueError('Use en or zh for language')
    return json.loads((resources() / 'data' / f'catalogue.{language}.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def connections():
    return json.loads((resources() / 'data' / 'connections.json').read_text(encoding='utf-8'))


def software(tool, language='en'):
    item = next((x for x in catalogue(language) if x['id'] == tool), None)
    if item is None:
        similar = difflib.get_close_matches(str(tool), [x['id'] for x in catalogue(language)], n=3)
        raise ValueError('Unknown software ID: ' + str(tool) + ('. Similar: ' + ', '.join(similar) if similar else '') +
                         '. software_search finds IDs; register_software adds a tool outside the catalogue')
    return {**item, 'connection': connections()[tool]}


def normalized(value):
    return re.sub(r'[\W_]+', ' ', unicodedata.normalize('NFKC', value).casefold()).strip()


SUFFIXES = ('ical', 'ation', 'ing', 'ies', 'es', 'al', 'ed', 's', 'e')


def stem(term):
    """A short form shared by related words: bands/band, scattering/scatterer, sphere/spherical."""
    for suffix in SUFFIXES:
        if term.endswith(suffix) and len(term) - len(suffix) >= 4:
            return term[:-len(suffix)]
    return term


def words(text):
    """Normalized words, then each adjacent pair joined, so x-ray is also found as xray."""
    parts = normalized(text).split()
    return ' ' + ' '.join(parts + [a + b for a, b in zip(parts, parts[1:])]) + ' '


CJK = re.compile(r'[\u3400-\u9fff]')


# A word of at most four letters matches itself with one of these endings, so mode finds modes but not modeling.
ENDINGS = '(?:s|es|e|ed|er|ers|ing|ings|al|ic|y)?'


def ending(word):
    """The regular expression of the last word of a term: in related forms after a word start."""
    root = stem(word)
    return re.escape(root) + (ENDINGS + ' ' if len(root) <= 4 else '')


def pattern(term):
    """What to look for in indexed text: Chinese anywhere, one or two characters as a whole word, else a word start."""
    if CJK.search(term):
        return re.compile(re.escape(term))
    return re.compile(' ' + re.escape(term) + ' ' if len(term) < 3 else ' ' + ending(term))


def phrase(name):
    """The pattern of a vocabulary name: an abbreviation (in capitals) as a whole word, the last word of a phrase in related forms."""
    parts = normalized(name).split()
    if CJK.search(name):
        return re.compile(re.escape(''.join(parts)))  # the index also holds adjacent words joined
    if len(parts) == 1:
        return re.compile(' ' + re.escape(parts[0]) + ' ') if name.isupper() else pattern(parts[0])
    last = parts[-1]
    return re.compile(' ' + re.escape(' '.join(parts[:-1])) + ' ' + (ending(last) if len(last) >= 3 else re.escape(last) + ' '))


# Words that state the task rather than the physics; a query does not require them.
STOP = frozenset('''a an and are as at be by can do does find for from get how i in into is it its me my of on or our software
the this to tool tools use used using via we what which with compute computing computation calculate calculating calculation
calculations simulate simulating simulation simulations 用于 如何 怎么 怎样 计算 仿真 模拟 求解 软件 工具 程序 一个 我们'''.split())
STOP_CHARACTERS = frozenset('的了中和与及或在用是为对将把个我请')  # Chinese between names: dropped when nothing else is left


@lru_cache(maxsize=1)
def vocabulary():
    """Groups of equivalent names of optical concepts, and the group of each name in stemmed form."""
    groups = json.loads((resources() / 'data' / 'vocabulary.json').read_text(encoding='utf-8'))['groups']
    known = {}
    for number, group in enumerate(groups):
        for name in group:
            parts = normalized(name).split()
            known.setdefault(''.join(parts) if CJK.search(name) else ' '.join(map(stem, parts)), number)
    return groups, known


def concepts(query):
    """The terms of a query, each with the patterns that match it.

    A phrase or word of the vocabulary matches any name of its group, longest
    phrase first; Chinese text is split into the vocabulary names it contains.
    """
    groups, known = vocabulary()
    tokens, terms, seen = [], [], set()
    for token in normalized(query).split():  # Chinese is written without spaces; join what punctuation split
        if tokens and CJK.search(token) and CJK.search(tokens[-1]): tokens[-1] += token
        else: tokens.append(token)

    def add(label, group=None):
        if (group if group is not None else label) in seen: return
        seen.add(group if group is not None else label)
        terms.append((label, [phrase(name) for name in groups[group]] if group is not None else [pattern(label)]))

    position = 0
    while position < len(tokens):
        for length in range(min(4, len(tokens) - position), 0, -1):
            words_ = tokens[position:position + length]
            group = known.get(' '.join(map(stem, words_)))
            if group is not None:
                add(' '.join(words_), group); position += length; break
        else:
            token = tokens[position]; position += 1
            if not CJK.search(token):
                if token not in STOP: add(token)
                continue
            start, rest = 0, ''
            while start < len(token):  # the longest vocabulary name or task word at each place
                end = next((end for end in range(len(token), start, -1) if token[start:end] in known or token[start:end] in STOP), None)
                if end is None:
                    rest += token[start]; start += 1; continue
                if rest.strip(''.join(STOP_CHARACTERS)): add(rest)
                rest = ''
                if token[start:end] in known: add(token[start:end], known[token[start:end]])
                start = end
            if rest.strip(''.join(STOP_CHARACTERS)): add(rest)
    return terms


def domain_names(language):
    rows = json.loads((resources() / 'data' / f'domains.{language}.json').read_text(encoding='utf-8'))
    return {row[0]: ' '.join(row[1:]) for row in rows}


@lru_cache(maxsize=None)
def program_texts(tool):
    """Per packaged program of a tool, as indexed words: its title, and its physics, inputs and results."""
    return {name: (words(spec['title']), words(' '.join([spec['about'], spec.get('results', ''),
                                                          *(key + ' ' + about for key, (_, about) in spec['inputs'].items())])))
            for name, spec in programs.catalog().get(tool, {}).items()}


@lru_cache(maxsize=1)
def search_index():
    """Per software ID, all searchable text in both languages and its programs' titles and physics; the web pages embed it."""
    index = {}
    fields = ('id', 'name', 'method', 'summary', 'api', 'usage', 'compute', 'license')
    for language in ('en', 'zh'):
        domains = domain_names(language)
        for item in catalogue(language):
            text = ' '.join(str(item[key]) for key in fields)
            text += ' ' + ' '.join(domains[key] for key in item['cats'])
            index[item['id']] = index.get(item['id'], '') + ' ' + normalized(text)
    for tool, found in programs.catalog().items():
        index[tool] += ' ' + normalized(' '.join(spec['title'] + ' ' + spec['about'] for spec in found.values()))
    # The pages match typed words as substrings; adding every name of each concept an entry mentions lets
    # them find synonyms, abbreviations and Chinese terms as software_search does.
    groups, _ = vocabulary()
    for tool in index:
        text = ''.join(ranked_index()[tool])
        names = {normalized(name) for group in groups if any(phrase(name).search(text) for name in group) for name in group}
        index[tool] += ' ' + ' '.join(sorted(names - {''}))
    return index


@lru_cache(maxsize=1)
def ranked_index():
    """Per software ID, in both languages: its names; method, summary and program titles; domains; other text and program details."""
    index = {}
    for language in ('en', 'zh'):
        domains = domain_names(language)
        for item in catalogue(language):
            texts = (item['id'] + ' ' + item['name'], item['method'] + ' ' + item['summary'],
                     ' '.join(domains[key] for key in item['cats']),
                     ' '.join(str(item[key]) for key in ('api', 'usage', 'compute', 'license')))
            before = index.get(item['id'], ('', '', '', ''))
            index[item['id']] = tuple(a + words(b) for a, b in zip(before, texts))
    for tool, (names, summary, domains, other) in index.items():
        found = program_texts(tool).values()
        index[tool] = (names, summary + ''.join(title for title, _ in found), domains, other + ''.join(details for _, details in found))
    return index


def best_program(tool, terms):
    """The packaged program of a tool matching the most query terms, then the most in its title, with those counts."""
    best, chosen = (0, 0), None
    for name, (title, details) in program_texts(tool).items():
        score = (sum(any(p.search(title) or p.search(details) for p in patterns) for _, patterns in terms),
                 sum(any(p.search(title) for p in patterns) for _, patterns in terms))
        if score > best:
            best, chosen = score, name
    return best, chosen


@lru_cache(maxsize=None)
def route_kinds(tool):
    """The kinds of route by which the environment reaches a catalogued tool, unattended ones first."""
    from . import routes
    return list(dict.fromkeys(route['route'] for route in routes.routes(tool, record=connections()[tool])))


def search(query='', domain=None, license_group=None, offset=0, limit=20, language='en'):
    """Rank software by the concepts of the query it matches.

    A query word matches the start of a word, in related forms; a word or
    phrase of the optical vocabulary (data/vocabulary.json) matches any name
    of its group: synonyms, abbreviations and Chinese terms. Software matching
    every term comes first; a match in the name outranks one in the method,
    summary or a packaged program's title, then the domain, then other text
    and program details. Among equal matches, software whose packaged program
    matches more terms comes first, then software that runs here: with
    packaged programs, then with an installation recipe. A query
    of three or more terms also returns software one term short, which lists
    the terms it lacks in ``missing``. ``program`` is the packaged program
    that matches the most terms.
    """
    if not isinstance(limit, int) or not 1 <= limit <= 100 or not isinstance(offset, int) or offset < 0:
        raise ValueError('Use offset >= 0 and limit from 1 to 100')
    terms = concepts(query)
    index = ranked_index()
    ranked = []
    for position, item in enumerate(catalogue(language)):
        if domain and domain not in item['cats'] or license_group and item['group'] != license_group:
            continue
        fields = index[item['id']]
        weights = [next((weight for weight, text in zip((4, 3, 2, 1), fields) if any(p.search(text) for p in patterns)), 0)
                   for _, patterns in terms]
        connection = connections()[item['id']]
        installs = connection.get('pip') or connection.get('conda') or connection.get('julia')
        packaged = programs.catalog().get(item['id'])
        # Packaged programs that install themselves, then packaged programs or a recipe, then the rest.
        runs = 0 if packaged and installs else 1 if packaged or installs else 2
        fit, program = best_program(item['id'], terms) if terms else ((0, 0), None)
        ranked.append((sum(map(bool, weights)), sum(weights), fit, runs, position, item, weights, program))
    best = max((entry[0] for entry in ranked), default=0)
    need = best if len(terms) < 3 else min(best, max(best - 1, (len(terms) + 1) // 2))
    ranked = sorted((entry for entry in ranked if entry[0] >= need and (best or not terms)),
                    key=lambda entry: (-entry[0], -entry[1], -entry[2][0], -entry[2][1], entry[3], entry[4]))
    matches = []
    for count, _, _, _, _, item, weights, program in ranked:
        connection = connections()[item['id']]
        missing = [] if count == len(terms) else [label for (label, _), weight in zip(terms, weights) if not weight]
        program = {'name': program, 'title': programs.catalog()[item['id']][program]['title']} if program else None
        matches.append({k: item[k] for k in ('id', 'name', 'group', 'cats', 'summary')} |
                       {'connection': connection['kind'], 'routes': route_kinds(item['id']), 'programs': list(programs.catalog().get(item['id'], {})),
                        'operations': list(programs.catalog().get(item['id'], {})),
                        'install': 'conda' if connection.get('conda') else 'pip' if connection.get('pip') else 'julia' if connection.get('julia') else 'manual',
                        'upstream_mcp': item['mcp']['kind']} | ({'program': program} if program else {}) |
                       ({'missing': missing} if missing else {}))
    found = {'total': len(matches), 'items': matches[offset:offset + limit],
             'next_offset': offset + limit if offset + limit < len(matches) else None}
    if terms and not matches:
        found['hint'] = ('No catalogued software or packaged program names ' + ', '.join(label for label, _ in terms) +
                         '. A program of your own runs with submit_calculation(tool="scipy", source=...) on NumPy and SciPy, '
                         'with materials for refractive indices; register_software adds other software.')
    return found
