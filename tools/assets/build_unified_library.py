"""new-case: build the unified asset library for agents (#1024): A101 truth + pilot catalogues.

uv run python tools/assets/build_unified_library.py --flora-index <cache>/flora_assets_index.json \
    --maf-index <cache>/maf_assets_index.json --out library/assets
Indexes come from the `assets` scan (AGR Tools window or assets_core.scan_*); they hold names and metadata only.
Writes flora_unified.json, maf_unified.json and UNIFIED.md; refuses to overwrite unless --replace is given.
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(name):
    spec = importlib.util.spec_from_file_location('agr_tools_' + name, ROOT / 'adapters/max/agr_tools' / (name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def read(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def summary_md(fl, mf, fl_idx, mf_idx):
    c, m = fl['counts'], mf['counts']
    out = ['# Общая библиотека ассетов для агентов (#1024)', '',
           'Сгенерировано `tools/assets/build_unified_library.py`; правки — в источниках, не здесь.',
           'Истина по названиям и артикулам — A101 (решение Артёма 06.11.2026).', '',
           '## Flora', '',
           '- Источник A101: `{}` ({}), SHA256 `{}`.'.format(
               fl_idx['root'], next(iter(fl_idx['sources'])), next(iter(fl_idx['sources'].values()))['sha256']),
           '- Видов A101: {a101}; связано с каталогом пилота (Latin, material ID): {a101_linked_to_catalogue}; '
           'без связи: {a101_unlinked}; на подтверждение: {a101_needs_review}.'.format(**c),
           '- Добавлено из библиотеки пилота v003 (нет в A101): {pilot_v003_added}; облегчённых НПМ от агентов '
           '(#347): {agent_light_npm}.'.format(**c), '',
           '### На подтверждение (A101 → вид каталога)', '', '| A101 | Уровень | Кандидаты | Связано |', '|---|---|---|---|']
    for r in fl['review']:
        out.append('| `{}` | {} | {} | {} |'.format(r['id'].split(':', 1)[1], r['level'] or 'нет совпадения',
                                                   ', '.join(r['candidates']) or '—', 'да' if r.get('linked') else ''))
    out += ['', '### Добавлены из v003', '']
    out += ['- {} — {} (ID {}, карты: {}{})'.format(r['latin'], r['russian'], r['material_id'], r['maps_review'],
                                                   ', облегчённый НПМ агента' if r.get('agent_light_npm') else '')
            for r in fl['records'] if r['source'] == 'pilot_v003']
    out += ['', '## МАФ', '',
            '- Источник A101: `{}`, архивов {a101}; привязано к ведомости: {a101_with_spec} из {spec_rows} строк.'.format(
                mf_idx['root'], **m),
            '- Строк ведомости без модели A101: {spec_without_a101_model}; из них с кандидатами-заменами из старой '
            'библиотеки Union (только по габаритам, #183): {spec_without_model_with_legacy_candidates}.'.format(**m),
            '- Старая библиотека Union: {legacy_entries} записей, статус `legacy_unidentified` (нет производителя и '
            'артикула; бинарники на ПК `C:/x/t_3e6ff1b3/library`).'.format(**m),
            '- Геометрических совпадений A101 ↔ Union (треугольники + габарит ±1 см): 0 из 100 архивов с описанием.', '']
    if mf['notes']:
        out += ['### Ведомость ↔ A101', '']
        out += ['- строка {spec_row}: в ведомости `{spec_name_in_sheet}`, в A101 `{a101}` — {note}'.format(**n)
                for n in mf['notes']]
        out.append('')
    out += ['### На подтверждение', '', '- Написание производителей: ' + '; '.join(
        ' / '.join(v) for v in mf['review']['manufacturer_spellings']),
        '- Один артикул у разных объектов: ' + '; '.join(
            '{}: {}'.format(k, ', '.join(v)) for k, v in mf['review']['shared_articles'].items()), '']
    return '\n'.join(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--flora-index', required=True)
    ap.add_argument('--maf-index', required=True)
    ap.add_argument('--flora-catalogue', default=str(ROOT / 'library/flora/catalogue.json'))
    ap.add_argument('--npm-light', default=str(ROOT / 'library/flora/npm-light.json'))
    ap.add_argument('--maf-catalogue', default=str(ROOT / 'library/maf/catalogue.json'))
    ap.add_argument('--out', required=True)
    ap.add_argument('--replace', action='store_true')
    a = ap.parse_args(argv)
    lib = _load('assets_library')
    fl_idx, mf_idx = read(a.flora_index), read(a.maf_index)
    fl = lib.unify_flora(fl_idx, read(a.flora_catalogue), read(a.npm_light))
    mf = lib.unify_maf(mf_idx, read(a.maf_catalogue))
    fl['sources'] = {'a101_root': fl_idx['root'], 'a101_files': {k: v.get('sha256') for k, v in fl_idx['sources'].items()},
                     'catalogue': 'library/flora/catalogue.json', 'npm_light': 'library/flora/npm-light.json'}
    mf['sources'] = {'a101_root': mf_idx['root'], 'catalogue': 'library/maf/catalogue.json'}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    files = {'flora_unified.json': fl, 'maf_unified.json': mf}
    for name in list(files) + ['UNIFIED.md']:
        if (out / name).exists() and not a.replace:
            raise SystemExit('exists (use --replace): ' + str(out / name))
    for name, data in files.items():
        (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    (out / 'UNIFIED.md').write_text(summary_md(fl, mf, fl_idx, mf_idx) + '\n', encoding='utf-8')
    print(json.dumps({'flora': fl['counts'], 'maf': mf['counts']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
