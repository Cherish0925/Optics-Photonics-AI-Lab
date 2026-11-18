"""Refractive index n and extinction coefficient k from the refractiveindex.info database.

The database (CC0 1.0) holds 3576 n,k pages: measured tables and fitted
dispersion formulas, each with its references and conditions. A page is
named shelf/book/page, for example main/Si/Green-2008; common names such as
SiO2, Si, Au or N-BK7 stand for one page each, and those pages ship with the
connector. Any other page is downloaded once from the pinned database commit
into OPTICS_HOME/materials.

The complex index is n + ik with k >= 0 for absorption, the convention of an
exp(-i omega t) time dependence. Wavelengths are in vacuum. Only the standard
library is used, so the connector and every solver environment can read it.
"""
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import re
import urllib.parse
import urllib.request

from .catalogue import resources

SOURCE = 'https://raw.githubusercontent.com/polyanskiy/refractiveindex.info-database/{commit}/database/data/{path}'


@lru_cache(maxsize=1)
def index():
    record = json.loads((resources() / 'data' / 'materials' / 'index.json').read_text(encoding='utf-8'))
    record['by_id'] = {row[0]: dict(zip(record['fields'], row)) for row in record['pages']}
    return record


def resolve(material):
    """The page ID a name stands for: a page ID, a common name, or either written in another case."""
    if not isinstance(material, str) or not material.strip():
        raise ValueError('Name a material: a page ID such as main/Si/Green-2008 or a common name such as Si')
    record, name = index(), material.strip()
    if name in record['by_id']:
        return name
    if name in record['common']:
        return record['common'][name]
    folded = name.casefold()
    for key, page in [*record['common'].items(), *((page, page) for page in record['by_id'])]:
        if key.casefold() == folded:
            return page
    similar = [page['id'] for page in search(name, limit=5)]
    raise ValueError(f'Unknown material {name}' + ('; similar pages: ' + ', '.join(similar) if similar else '') +
                     '. Common names: ' + ', '.join(record['common']))


def search(query, limit=20):
    """Pages whose ID, book or page name contain every word of the query; common names first."""
    words = [word for word in re.split(r'[\s,;]+', str(query or '').casefold()) if word]
    record = index()
    common = {page: name for name, page in record['common'].items()}
    found = []
    for row in record['by_id'].values():
        text = ' '.join((row['id'], row['book'], row['page'], common.get(row['id'], ''))).casefold()
        if all(word in text for word in words):
            found.append((row['id'] not in common, row['id']))
    return [{'id': key, 'common_name': common.get(key), 'book': record['by_id'][key]['book'],
             'page': record['by_id'][key]['page']} for _, key in sorted(found)[:limit]]


def _block(lines, start):
    """The lines of a YAML block scalar: those indented deeper than the key on line start."""
    indent = len(lines[start]) - len(lines[start].lstrip(' -'))
    body = []
    for line in lines[start + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        body.append(line.strip())
    return body


def parse(text):
    """The parts of a database page used here: references, comments, conditions and data pieces."""
    lines = text.splitlines()
    page = {'references': '', 'comments': '', 'conditions': {}, 'data': []}
    for n, line in enumerate(lines):
        if line.startswith(('REFERENCES:', 'COMMENTS:')):
            key = line.split(':')[0].lower()
            value = line.split(':', 1)[1].strip()
            page[key] = ' '.join(_block(lines, n)) if value in ('|', '>') else value.strip('"')
        elif line.startswith('CONDITIONS:'):
            for item in _block(lines, n):
                if ':' in item:
                    key, value = item.split(':', 1)
                    page['conditions'][key.strip()] = value.strip()
        elif line.startswith('DATA:'):
            pieces, current = [], None
            body = lines[n + 1:]
            for k, item in enumerate(body):
                if item.strip() and not item.startswith((' ', '\t')):
                    break
                found = re.match(r'\s*(- )?\s*(type|wavelength_range|coefficients|data):\s*(.*)$', item)
                if not found:
                    continue
                if found[1] or found[2] == 'type' and current is None:
                    current = {}
                    pieces.append(current)
                key, value = found[2], found[3].strip()
                if key == 'type':
                    current['type'] = value
                elif key in ('wavelength_range', 'coefficients'):
                    current[key] = [float(v) for v in value.split()]
                else:
                    rows = _block(body, k) if value in ('|', '>') else [value]
                    current['data'] = [[float(v) for v in row.split()] for row in rows if row]
            page['data'] = pieces
    page['references'] = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', page['references'])).strip()
    return page


def _download(row, target):
    url = SOURCE.format(commit=index()['commit'], path=urllib.parse.quote(row['data']))
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read()
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + '.partial')
    partial.write_bytes(data)
    os.replace(partial, target)


def page(material, path=None):
    """A parsed page with its ID, names, source and wavelength range in micrometres."""
    key = resolve(material)
    row = index()['by_id'][key]
    bundled = resources() / 'data' / 'materials' / 'pages' / row['data']
    if bundled.is_file():
        file = bundled
    else:
        from .environments import home
        file = home(path) / 'materials' / index()['commit'][:12] / row['data']
        if not file.is_file():
            _download(row, file)
    record = parse(file.read_text(encoding='utf-8'))
    ranges = [piece_range(piece) for piece in record['data'] if piece.get('type', '').split()[0] in ('formula', 'tabulated')]
    low = max(r[0] for r in ranges)
    high = min(r[1] for r in ranges)
    return {'id': key, 'book': row['book'], 'page': row['page'], 'range_um': [low, high],
            'source': SOURCE.format(commit=index()['commit'], path=urllib.parse.quote(row['data'])), **record}


def covers(name, wavelengths):
    """Whether a page name such as 'n,k 0.400–1.31 µm' states a range containing every wavelength."""
    found = re.search(r'([\d.]+(?:e-?\d+)?)\s*[–-]\s*([\d.]+(?:e-?\d+)?)\s*µm', name)
    return bool(found) and all(float(found[1]) <= x <= float(found[2]) for x in wavelengths)


def piece_range(piece):
    if 'wavelength_range' in piece:
        return piece['wavelength_range']
    column = [row[0] for row in piece['data']]
    return [min(column), max(column)]


def _formula(number, c, x):
    """Dispersion formulas 1 to 9 of the database documentation; x in micrometres."""
    c = list(c) + [0.0] * (17 - len(c))
    if number == 1:
        n2 = 1 + c[0] + sum(c[i] * x * x / (x * x - c[i + 1] ** 2) for i in range(1, 17, 2))
        return math.sqrt(n2)
    if number == 2:
        return math.sqrt(1 + c[0] + sum(c[i] * x * x / (x * x - c[i + 1]) for i in range(1, 17, 2)))
    if number == 3:
        return math.sqrt(c[0] + sum(c[i] * x ** c[i + 1] for i in range(1, 17, 2)))
    if number == 4:
        n2 = c[0] + c[1] * x ** c[2] / (x * x - c[3] ** c[4]) + c[5] * x ** c[6] / (x * x - c[7] ** c[8])
        return math.sqrt(n2 + sum(c[i] * x ** c[i + 1] for i in range(9, 17, 2)))
    if number == 5:
        return c[0] + sum(c[i] * x ** c[i + 1] for i in range(1, 11, 2))
    if number == 6:
        return 1 + c[0] + sum(c[i] / (c[i + 1] - x ** -2) for i in range(1, 11, 2))
    if number == 7:
        d = 1 / (x * x - 0.028)
        return c[0] + c[1] * d + c[2] * d * d + c[3] * x ** 2 + c[4] * x ** 4 + c[5] * x ** 6
    if number == 8:
        a = c[0] + c[1] * x * x / (x * x - c[2]) + c[3] * x * x
        return math.sqrt((1 + 2 * a) / (1 - a))
    if number == 9:
        return math.sqrt(c[0] + c[1] / (x * x - c[2]) + c[3] * (x - c[4]) / ((x - c[4]) ** 2 + c[5]))
    raise ValueError(f'Dispersion formula {number} is not defined')


def _table(rows, column, x):
    """Linear interpolation of one column of a table sorted by wavelength."""
    xs = [row[0] for row in rows]
    if x <= xs[0]:
        return rows[0][column]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            t = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return rows[i - 1][column] + t * (rows[i][column] - rows[i - 1][column])
    return rows[-1][column]


def nk(material, wavelength_um, path=None):
    """n and k at each vacuum wavelength in micrometres, as two lists, with the page they came from.

    A wavelength outside the page's range is an error that names other pages of
    the same material.
    """
    record = page(material, path)
    values = [wavelength_um] if isinstance(wavelength_um, (int, float)) else list(wavelength_um)
    low, high = record['range_um']
    outside = [x for x in values if not low * (1 - 1e-9) <= x <= high * (1 + 1e-9)]
    if outside:
        book = record['id'].rsplit('/', 1)[0] + '/'
        others = [row for key, row in index()['by_id'].items() if key.startswith(book) and key != record['id']]
        common = set(index()['common'].values())
        covering = [row['id'] + ' (' + row['page'] + ')' for row in sorted(others, key=lambda row: row['id'] not in common)
                    if covers(row['page'], outside)]
        raise ValueError(f"{record['id']} covers {low:g}-{high:g} µm; {outside[0]:g} µm is outside it. "
                         + ('Pages of this material that cover it: ' + '; '.join(covering[:6]) if covering else
                            f'No other page of this material covers it; materials(query=...) searches others'))
    n, k = [], []
    for x in values:
        n_value, k_value = None, 0.0
        for piece in record['data']:
            kind = piece.get('type', '')
            if kind.startswith('formula'):
                n_value = _formula(int(kind.split()[1]), piece['coefficients'], x)
            elif kind == 'tabulated nk':
                n_value, k_value = _table(piece['data'], 1, x), _table(piece['data'], 2, x)
            elif kind == 'tabulated n':
                n_value = _table(piece['data'], 1, x)
            elif kind == 'tabulated k':
                k_value = _table(piece['data'], 1, x)
        if n_value is None:
            raise ValueError(record['id'] + ' has no refractive index data')
        n.append(n_value)
        k.append(k_value)
    return {'n': n, 'k': k, 'page': record}


def index_at(material, wavelength_um, path=None):
    """The complex index n + ik at each wavelength in micrometres."""
    values = nk(material, wavelength_um, path)
    result = [complex(a, b) for a, b in zip(values['n'], values['k'])]
    return result[0] if isinstance(wavelength_um, (int, float)) else result


def lookup(material=None, query=None, wavelength=None, unit='nm', limit=20, path=None):
    """The materials tool: search pages, or evaluate n and k of one material at wavelengths in unit."""
    if material is None:
        if query is None:
            record = index()
            return {'common': record['common'], 'pages': len(record['by_id']), 'source': record['repository'],
                    'commit': record['commit'], 'license': record['license']}
        found = search(query, limit=limit)
        return {'query': query, 'pages': found, 'total': len(search(query, limit=10 ** 6))}
    if wavelength is None:
        record = page(material, path)
        return {key: record[key] for key in ('id', 'book', 'page', 'range_um', 'references', 'comments', 'conditions', 'source')}
    from .data import convert
    values = [wavelength] if isinstance(wavelength, (int, float)) else list(wavelength)
    if not values or len(values) > 10000:
        raise ValueError('Give between 1 and 10000 wavelengths')
    micrometres = [convert(float(v), unit, 'um') for v in values]
    result = nk(material, micrometres, path)
    record = result['page']
    return {'id': record['id'], 'book': record['book'], 'page': record['page'], 'wavelength': values, 'unit': unit,
            'n': result['n'], 'k': result['k'], 'range_um': record['range_um'], 'references': record['references'],
            'conditions': record['conditions'], 'convention': 'n + ik, k >= 0 absorbs; vacuum wavelength',
            'source': record['source']}
