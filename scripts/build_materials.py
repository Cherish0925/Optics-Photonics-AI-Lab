"""Write the material index and the bundled pages from a refractiveindex.info database checkout.

    git clone --depth 1 https://github.com/polyanskiy/refractiveindex.info-database DATABASE
    python scripts/build_materials.py DATABASE

The database is in the public domain (CC0 1.0). data/materials/index.json lists
every n,k page with its book and page names and the commit it was read from;
the pages behind COMMON are copied unchanged into data/materials/pages, so
that they work offline. Other pages are downloaded from that commit when
first used.
"""
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
# Common names and the page each one means; ranges are in micrometres.
COMMON = {
    'air': 'other/air/Ciddor',                         # 0.23-1.69, 15 °C dry air
    'water': 'main/H2O/Hale',                          # 0.2-200
    'SiO2': 'main/SiO2/Malitson',                      # fused silica 0.21-6.7
    'N-BK7': 'popular_glass/BK7/SCHOTT',               # 0.3-2.5
    'sapphire': 'main/Al2O3/Malitson-o',               # ordinary ray 0.2-5.5
    'CaF2': 'main/CaF2/Malitson',
    'MgF2': 'main/MgF2/Dodge-o',
    'TiO2': 'main/TiO2/Devore-o',
    'Ta2O5': 'main/Ta2O5/Gao',
    'HfO2': 'main/HfO2/Al-Kuhaili',
    'Si3N4': 'main/Si3N4/Luke',
    'AlN': 'main/AlN/Pastrnak-o',
    'GaN': 'main/GaN/Barker-o',
    'ZnSe': 'main/ZnSe/Connolly',
    'LiNbO3-o': 'main/LiNbO3/Zelmon-o',
    'LiNbO3-e': 'main/LiNbO3/Zelmon-e',
    'BBO-o': 'main/BaB2O4/Tamosauskas-o',              # beta barium borate 0.188-5.2
    'BBO-e': 'main/BaB2O4/Tamosauskas-e',
    'diamond': 'main/C/Phillip',
    'SiC': 'main/SiC/Larruquert',
    'Si': 'main/Si/Green-2008',                        # 0.25-1.45, absorbing
    'Si-IR': 'main/Si/Li-293K',                        # 1.2-14
    'Ge': 'main/Ge/Burnett',
    'GaAs': 'main/GaAs/Skauli',                        # 0.97-17, transparent
    'GaAs-visible': 'main/GaAs/Aspnes',                # 0.21-0.83, absorbing
    'InP': 'main/InP/Pettit',
    'ITO': 'other/In2O3-SnO2/Konig',
    'PMMA': 'organic/poly_methyl_methacrylate/Sultanova',
    'polystyrene': 'organic/polystyrene/Sultanova',
    'Au': 'main/Au/Johnson', 'Ag': 'main/Ag/Johnson', 'Cu': 'main/Cu/Johnson',
    'Al': 'main/Al/Rakic', 'Cr': 'main/Cr/Johnson', 'Ti': 'main/Ti/Johnson', 'TiN': 'main/TiN/Pfluger',
}


def text(value):
    return html.unescape(re.sub(r'<[^>]+>', '', value)).strip()


def pages(catalog):
    lines = catalog.read_text(encoding='utf-8').splitlines()
    shelf = book = book_name = None
    for n, line in enumerate(lines):
        found = re.match(r'\s*- (SHELF|BOOK|PAGE): (.+)', line)
        if not found:
            continue
        key = found[2].strip().strip('"')
        name = re.match(r'\s*name: "?(.*?)"?\s*$', lines[n + 1])[1] if 'name:' in lines[n + 1] else ''
        if found[1] == 'SHELF':
            shelf = key
        elif found[1] == 'BOOK':
            book, book_name = key, text(name)
        else:
            data = next(re.match(r'\s*data: "?(.*?)"?\s*$', other)[1] for other in lines[n + 1:n + 4] if 'data:' in other)
            yield [f'{shelf}/{book}/{key}', book_name, text(name), data]


def main():
    database = Path(sys.argv[1]) / 'database'
    commit = subprocess.run(['git', '-C', str(database), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    listed = list(pages(database / 'catalog-nk.yml'))
    by_id = {page[0]: page for page in listed}
    missing = sorted(name for name, page in COMMON.items() if page not in by_id)
    if missing:
        sys.exit('Common names without a page: ' + ', '.join(missing))
    target = ROOT / 'data' / 'materials'
    shutil.rmtree(target / 'pages', ignore_errors=True)
    for page in COMMON.values():
        source = database / 'data' / by_id[page][3]
        destination = target / 'pages' / by_id[page][3]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    index = {'repository': 'https://github.com/polyanskiy/refractiveindex.info-database', 'commit': commit,
             'license': 'CC0 1.0 (public domain)', 'common': COMMON, 'fields': ['id', 'book', 'page', 'data'], 'pages': listed}
    (target / 'index.json').write_text(json.dumps(index, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(len(listed), 'pages;', len(COMMON), 'common names bundled; commit', commit)


if __name__ == '__main__':
    main()
