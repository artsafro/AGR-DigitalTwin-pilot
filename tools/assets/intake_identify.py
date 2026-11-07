"""Asset intake step 4 (#1024, library/assets/INTAKE.md): identify a delivered project's MAF and plants.

uv run python tools/assets/intake_identify.py --project BUHV12 --dir C:/x/asset-intake/BUHV12 \
    [--kinds <dir>/scene/<scene>-kinds.json ...] [--scene-map <dir>/scene-map.json]

Reads <dir>/spec/maf-schedule.json and flora-schedule.json (rows as in jobs/VATUTINO-SITE/maf/site-schedule.json),
the unified library (library/assets/maf_unified.json, flora_unified.json), the Vatutino project set and the scene
kinds (one record per unique geometry, with count and size). Writes <dir>/identify.json and identify.md.

Status per row (Artem 07.11.2026):
  exists          library model with the same article / species, size within +-10 %;
  variant         same article / species, size off by > 10 % (never rescaled) or cultivar differs;
  new_model       no library model, the scene has one: normalise it to the A101 standard;
  not_identified  no library model and no scene kind (or ambiguous): a question for Artem.
The scene join is a proposal (name tokens + size); --scene-map {row_key: [kind ids]} overrides it after review.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
TOL = 0.10


def _load(name):
    spec = importlib.util.spec_from_file_location('agr_tools_' + name, ROOT / 'adapters/max/agr_tools' / (name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


lib = _load('assets_library')


def _rows(path):
    if not Path(path).is_file():
        return []
    d = json.loads(Path(path).read_text(encoding='utf-8'))
    return d['rows'] if isinstance(d, dict) else d


def row_key(r):
    return '{}/{}/{}'.format((r.get('table') or '')[:24], r.get('row') or r.get('pos'), r.get('order') or '')


def dims_check(spec_mm, model_mm, tol=TOL):
    """Spec L/W/H vs a model bbox {x, y, z} (mm). Plan sizes compared sorted (a bench may lie along X or Y),
    height directly. Returns None when the spec gives no size, else {'ok', 'worst', 'pairs'}."""
    L, W, H = spec_mm
    if not model_mm:
        return None
    pairs = []
    plan_s = sorted([v for v in (L, W) if v], reverse=True)
    plan_m = sorted([model_mm.get('x') or 0, model_mm.get('y') or 0], reverse=True)[:len(plan_s)]
    pairs += list(zip(plan_s, plan_m))
    if H:
        pairs.append((H, model_mm.get('z') or 0))
    if not pairs:
        return None
    devs = [abs(m - s) / s for s, m in pairs if s]
    worst = max(devs) if devs else 0.0
    return {'ok': worst <= tol, 'worst': round(worst, 3), 'pairs': [[round(s), round(m)] for s, m in pairs]}


# ---- library indexes ------------------------------------------------------------------------------------------------

def maf_library(unified, vatutino_schedule=None, vatutino_set=None):
    by_art, a101 = {}, []
    for r in unified['records']:
        if r.get('source') != 'a101':
            continue
        a101.append(r)
        art = r.get('article') or ''
        for k in {lib._article_key(art), lib._article_key(re.sub(r'-\d+$', '', art))}:
            if len(k) >= 4:
                by_art.setdefault(k, []).append(r)
    project = {}
    if vatutino_schedule and vatutino_set:
        built = {p.get('schedule'): p for p in vatutino_set.get('positions', [])}
        for r in vatutino_schedule.get('rows', []):
            p = built.get('{}/{}'.format(r['table'], r['row']))
            k = lib._article_key(r.get('article'))
            if p and len(k) >= 4:
                project.setdefault(k, []).append({'set_id': p.get('set_id'), 'name': r.get('name'),
                                                  'project': 'VATUTINO-SITE'})
    return by_art, a101, project


def maf_name_candidates(name, a101, cutoff=0.8):
    toks = [t for t in lib.name_tokens(name) if len(t) > 2]
    out = []
    for r in a101:
        cand = lib.name_tokens(' '.join(filter(None, [r.get('title_ru'), r.get('title')])))
        if toks and cand and sum(any(lib._tok_eq(t, c, cutoff) for c in cand) for t in toks) == len(toks):
            out.append(r['name'])
    return out


def flora_library(unified):
    species = {}
    for r in unified['records']:
        slug = r.get('species_slug') or (r.get('catalogue') or {}).get('slug') or r['id'].split(':', 1)[-1]
        species.setdefault(slug, []).append(r)
    return species


# Russian genus spellings that differ from the library slugs (A101 'elka', v003 Latin ids).
GENUS_ALIAS = {'el': 'elka', 'tuia': 'thuja', 'tuya': 'thuja', 'mikrobiota': 'microbiota'}
GROUNDEL_TABLES = ('ограждени', 'ворот', 'калит')  # fences and gates: GroundEl, not the MAF library


def cultivar_of(row):
    """Cultivar named in the row: «…» in the Russian name, or a capitalised non-genus word in the bracket
    ('Сосна горная (Sherwood Compact)' -> 'Sherwood Compact'; 'Physocarpus opulifolius Luteus' -> 'Luteus')."""
    name = row.get('name_ru') or ''
    q = re.findall(r'[«"]([^»"]+)[»"]', name)
    if q:
        return q[0]
    br = name.split('(', 1)[1].rstrip(')') if '(' in name else ''
    words = br.split()
    if words and words[0][:1].isupper() and (len(words) < 2 or words[1][:1].isupper()):
        return br.strip()  # the whole bracket is a cultivar
    if len(words) >= 3:
        return ' '.join(words[2:])
    ru = [w for w in name.split('(')[0].split() if w[:1].isupper()][1:]
    return ' '.join(ru) or None


def flora_match(row, species):
    """Russian name (before the bracket) vs A101 species slugs; Latin vs v003 ids. Returns (level, [record names])."""
    ru = re.split(r'\(', row.get('name_ru') or '')[0]
    ru_t = [lib.skeleton(GENUS_ALIAS.get(t, t)) for t in lib.name_tokens(ru)]
    best, out = None, []
    order = {'exact': 0, 'species': 1, 'genus': 2}
    for slug, recs in species.items():
        st = [lib.skeleton(t) for t in re.split(r'[^a-z0-9]+', slug.lower()) if t]
        level = None
        if ru_t and st and all(lib._tok_eq(a, b) for a, b in zip(st, ru_t)):
            level = 'exact' if len(st) == len(ru_t) else ('species' if len(st) > 1 else 'genus')
        lat = (row.get('latin') or '').lower().replace(' ', '_')
        if level is None and lat and len(lat) > 4 and lat in slug.lower():
            level = 'species'
        if level is None and ru_t and st and lib._tok_eq(st[0], ru_t[0]):
            level = 'genus'  # Latin v003 ids ('Thuja_occidentalis') share only the genus with a Russian name
        if level is None:
            continue
        names = [r.get('name') or r['id'] for r in recs]
        if best is None or order[level] < order[best]:
            best, out = level, names
        elif level == best:
            out += names
    return best, sorted(set(out))


# ---- scene join ------------------------------------------------------------------------------------------------------

def scene_candidates(row, kinds, kind_filter):
    """Kinds whose name/layer tokens share the row's article or name tokens; scored, best first."""
    art = lib._article_key(row.get('article'))
    toks = [t for t in lib.name_tokens(row.get('name') or row.get('name_ru') or '') if len(t) > 2]
    fam = [lib.skeleton(t) for f in (row.get('dwg_families') or []) for t in lib.name_tokens(f) if len(t) > 2]
    out = []
    for k in kinds:
        if kind_filter and k.get('kind') not in kind_filter:
            continue
        label = ' '.join(filter(None, [k.get('example_name'), k.get('name'), k.get('layer'),
                                       ' '.join(k.get('materials') or [])]))
        kt = lib.name_tokens(label)
        kart = lib._article_key(label)
        score = 0.0
        if art and len(art) >= 4 and art in kart:
            score += 3
        score += sum(1 for t in toks if any(lib._tok_eq(t, c) for c in kt)) / max(len(toks), 1)
        score += 0.5 * sum(1 for t in fam if any(lib._tok_eq(t, c) for c in kt)) / max(len(fam), 1)
        if score >= 0.6:
            out.append((score, k))
    out.sort(key=lambda p: -p[0])
    return out


def _kind_size(k):
    s = k.get('size_mm') or k.get('bbox_mm')
    if isinstance(s, (list, tuple)):
        return {'x': s[0], 'y': s[1], 'z': s[2]}
    return s


# ---- main -----------------------------------------------------------------------------------------------------------

def identify(project, maf_rows, flora_rows, kinds, scene_map, maf_unified, flora_unified, vat_sched, vat_set):
    by_art, a101, vat = maf_library(maf_unified, vat_sched, vat_set)
    species = flora_library(flora_unified)
    rows = []
    for r in maf_rows:
        if any(t in (r.get('table') or '').lower() for t in GROUNDEL_TABLES):
            rows.append(({'key': row_key(r), 'kind': 'groundel', 'table': r.get('table'), 'row': r.get('row'),
                          'name': r.get('name'), 'article': r.get('article'), 'qty': r.get('qty'),
                          'unit': r.get('unit'), 'status': 'out_of_scope',
                          'why': 'fence/gate: GroundEl, not the MAF library'}, r))
            continue
        key = row_key(r)
        art = lib._article_key(r.get('article'))
        hits = by_art.get(art, []) if len(art) >= 4 else []
        rec = {'key': key, 'kind': 'maf', 'table': r.get('table'), 'row': r.get('row'), 'name': r.get('name'),
               'article': r.get('article'), 'maker': r.get('maker'), 'qty': r.get('qty'),
               'dims_mm': [r.get('L_mm'), r.get('W_mm'), r.get('H_mm')], 'dwg_count': r.get('dwg_count'),
               'library': [h['name'] for h in hits], 'library_by_name': [] if hits else
               maf_name_candidates(r.get('name'), a101), 'project_sets': vat.get(art, []),
               'proposed_name': lib.propose_maf_name(r.get('maker'), r.get('name'), r.get('article'))}
        rec['library_dims'] = [dims_check(rec['dims_mm'], (h.get('bbox_mm') or {}).get('high')) for h in hits]
        rows.append((rec, r))
    for r in flora_rows:
        if r.get('kind') in ('lawn', 'flowerbed'):
            continue  # surfaces: Ground, not the asset library
        level, names = flora_match(r, species)
        rec = {'key': row_key(r), 'kind': 'flora', 'row': r.get('pos'), 'name': r.get('name_ru'),
               'cultivar': cultivar_of(r),
               'latin': r.get('latin'), 'plant_kind': r.get('kind'), 'qty': r.get('qty'),
               'height_m': r.get('height_m'), 'container': r.get('container'), 'dwg_count': r.get('dwg_count'),
               'library_level': level, 'library': names}
        rows.append((rec, r))

    for rec, r in rows:
        if rec['kind'] == 'groundel':
            continue
        kf = {'maf'} if rec['kind'] == 'maf' else {'flora', 'tree', 'shrub'}
        if scene_map and rec['key'] in scene_map:
            ids = set(scene_map[rec['key']])
            chosen = [k for k in kinds if k.get('id') in ids]
            rec['scene_join'] = 'map'
        else:
            cands = scene_candidates(r, kinds, kf)
            top = [k for s, k in cands if s >= cands[0][0] - 1e-9] if cands else []
            chosen = top
            rec['scene_join'] = 'auto' if len(top) == 1 else ('ambiguous' if top else 'none')
            rec['scene_candidates'] = [{'id': k.get('id'), 'name': k.get('example_name'), 'score': round(s, 2)}
                                       for s, k in cands[:5]]
        rec['scene'] = [{'id': k.get('id'), 'name': k.get('example_name'), 'count': k.get('count'),
                         'size_mm': _kind_size(k), 'tris': k.get('tris'), 'scene': k.get('scene'),
                         'dims': dims_check(rec.get('dims_mm') or [None, None, None], _kind_size(k))}
                        for k in chosen]
        rec['scene_count'] = sum(k.get('count') or 0 for k in chosen) if chosen else None
        rec['status'], rec['why'] = _status(rec)
    out = [rec for rec, _ in rows]
    counts = {}
    for rec in out:
        counts[rec['status']] = counts.get(rec['status'], 0) + 1
    return {'schema': 'agr.assets.intake/1', 'project': project, 'tolerance': TOL, 'counts': counts, 'rows': out}


def _status(rec):
    if rec['kind'] == 'maf':
        if rec['library']:
            dims = [d for d in rec['library_dims'] if d]
            if dims and not any(d['ok'] for d in dims):
                return 'variant', 'A101 article, size off > 10 %'
            return 'exists', 'A101 article' + ('' if dims else ' (no spec size to check)')
        if rec['project_sets']:
            return 'exists', 'project set ' + rec['project_sets'][0]['set_id'] + ' (not yet A101 format)'
    else:
        if rec['library_level'] == 'exact' and rec.get('cultivar') and                 not any(lib.skeleton(rec['cultivar'].split()[0].lower()) in lib.skeleton(n) for n in rec['library']):
            return 'variant', 'species in library, cultivar {} not'.format(rec['cultivar'])
        if rec['library_level'] == 'exact':
            return 'exists', 'species in library'
        if rec['library_level'] == 'species':
            return 'variant', 'library has the species: ' + ', '.join(rec['library'][:3])
    # genus only = another species: build it, the nearest library genus is a hint for Artem
    near = ' (nearest genus: {})'.format(', '.join(rec['library'][:3])) if rec.get('library_level') == 'genus' else ''
    if rec.get('scene_join') in ('auto', 'map') and rec['scene']:
        return 'new_model', 'scene kind ' + ', '.join(str(s['id']) for s in rec['scene']) + near
    if rec.get('scene_join') == 'ambiguous':
        return 'not_identified', 'several scene kinds fit' + near
    return 'not_identified', 'no library model, no scene kind' + near


def to_md(res):
    lines = ['# {} — asset intake identification'.format(res['project']), '',
             'Generated by `tools/assets/intake_identify.py`; tolerance ±{:.0f} %. Counts: {}.'.format(
                 res['tolerance'] * 100, ', '.join('{} {}'.format(k, v) for k, v in sorted(res['counts'].items()))),
             '', '| Row | Kind | Name | Article | Qty | DWG | Scene count | Library | Scene kind | Status | Why |',
             '|---|---|---|---|---|---|---|---|---|---|---|']
    for r in res['rows']:
        scene = '; '.join('{} ×{}'.format(s['name'], s['count']) for s in r.get('scene') or [])
        libs = ', '.join(r.get('library') or []) or ', '.join('~' + n for n in r.get('library_by_name') or [])
        lines.append('| {} | {} | {} | {} | {} | {} | {} | {} | {} | **{}** | {} |'.format(
            r['row'], r['kind'], (r['name'] or '').replace('|', '/')[:70], r.get('article') or r.get('latin') or '',
            r.get('qty') or '', r.get('dwg_count') or '', r.get('scene_count') or '', libs[:80], scene[:80],
            r['status'], r['why']))
    return '\n'.join(lines) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', required=True)
    ap.add_argument('--dir', required=True)
    ap.add_argument('--kinds', nargs='*', default=[])
    ap.add_argument('--scene-map')
    a = ap.parse_args(argv)
    d = Path(a.dir)
    kinds = []
    for p in a.kinds:
        data = json.loads(Path(p).read_text(encoding='utf-8'))
        for k in (data['kinds'] if isinstance(data, dict) else data):
            k.setdefault('scene', Path(p).stem.replace('-kinds', ''))
            kinds.append(k)
    smap = json.loads(Path(a.scene_map).read_text(encoding='utf-8')) if a.scene_map else None
    j = lambda p: json.loads((ROOT / p).read_text(encoding='utf-8'))  # noqa: E731
    res = identify(a.project, _rows(d / 'spec/maf-schedule.json'), _rows(d / 'spec/flora-schedule.json'), kinds,
                   smap, j('library/assets/maf_unified.json'), j('library/assets/flora_unified.json'),
                   j('jobs/VATUTINO-SITE/maf/site-schedule.json'), j('jobs/VATUTINO-SITE/maf/site-maf-set.json'))
    (d / 'identify.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    (d / 'identify.md').write_text(to_md(res), encoding='utf-8')
    print(json.dumps(res['counts'], ensure_ascii=False))


if __name__ == '__main__':
    main()
