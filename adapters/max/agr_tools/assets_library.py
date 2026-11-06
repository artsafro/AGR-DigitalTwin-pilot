"""new-case: unified asset library for agents (#1024): A101 as the source of truth + earlier pilot libraries.

Pure stdlib. Inputs are the `assets` indexes (assets_core.scan_flora / scan_maf) and the pilot catalogues already in
git (library/flora/catalogue.json #216, library/maf/catalogue.json #183, library/flora/npm-light.json #347).
Owner decision 06.11.2026: A101 names and articles are the truth; other libraries and agent-made plants that look
fine are added to the one library agents use. Nothing here decides "looks fine": records carry the evidence
(map review status, measurements) and a status; a human accepts.

MAF:   one record per A101 archive (+ the album specification rows that name it); specification rows without an
       A101 model keep their legacy stand-in candidates (dimension only, #183); legacy Union entries stay as
       `legacy_unidentified` records (no manufacturer/article).
Flora: one record per A101 species (+ the #216 catalogue species it corresponds to: Latin/Russian/material ID);
       #216 species without an A101 counterpart are added as `pilot_v003` records (with the agent-made light NPM
       flag). Matching is by transliterated Russian name; genus-only or several candidates are reported, not chosen.
"""
import difflib
import re

UNIFIED_SCHEMA = 'agr.assets.unified/1'

_RU = {'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh', 'з': 'z', 'и': 'i',
       'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
       'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '',
       'э': 'e', 'ю': 'yu', 'я': 'ya'}


def translit(text):
    return ''.join(_RU.get(c, c) for c in str(text).lower())


def skeleton(token):
    """Spelling-insensitive key for transliterations made by different people (ya/ia, zh/j, kh/x/h, ts/c, y/i,
    doubled letters): 'ryabinnik' ~ 'riabinnik', 'mozhzhevelnik' ~ 'mojevelnik', 'cheremukha' ~ 'cheremuxa'."""
    t = str(token).lower()
    for a, b in (('zh', 'j'), ('kh', 'x'), ('ts', 'c'), ('sch', 'sh'), ('yj', 'i'), ('iy', 'i'), ('yy', 'i'),
                 ('y', 'i'), ('h', 'x'), ('w', 'v')):
        t = t.replace(a, b)
    t = re.sub(r'(.)\1+', r'\1', t)
    return t


def name_tokens(text):
    return [skeleton(t) for t in re.split(r'[^a-z0-9]+', translit(text)) if t and not t.isdigit()]


def _tok_eq(a, b, cutoff=0.8):
    return a == b or difflib.SequenceMatcher(None, a, b).ratio() >= cutoff


def match_species(slug, species, cutoff=0.8):
    """A101 species slug (e.g. 'spireya_seraya') vs catalogue species [{'russian', 'latin', ...}].

    'exact'   all slug tokens match the Russian name tokens and the name has no extra tokens;
    'species' slug tokens match the first tokens of the name (the name adds a cultivar);
    'genus'   only the first token matches (slug has one token, e.g. 'lipa' vs 'Липа мелколистная').
    Returns {'level', 'candidates': [indexes]} with the best level; several candidates are left to a human."""
    st = [skeleton(t) for t in slug.split('_') if t]
    best, cands = None, []
    order = {'exact': 0, 'species': 1, 'genus': 2}
    for i, sp in enumerate(species):
        rt = name_tokens(sp.get('russian') or '')
        if not rt or not st:
            continue
        level = None
        if len(rt) >= len(st) and all(_tok_eq(a, b, cutoff) for a, b in zip(st, rt)):
            level = 'exact' if len(rt) == len(st) else ('species' if len(st) > 1 else 'genus')
        if level is None:
            continue
        if best is None or order[level] < order[best]:
            best, cands = level, [i]
        elif level == best:
            cands.append(i)
    return {'level': best, 'candidates': cands}


# ---- Flora --------------------------------------------------------------------------------------------------------
def unify_flora(a101_index, catalogue, npm_light=None):
    """A101 species first (truth), then #216 species without an A101 counterpart."""
    species = catalogue.get('species', [])
    light = {r.get('material_id') for r in (npm_light or {}).get('variants', [])}

    def card(sp):
        return {'material_id': sp.get('material_id'), 'latin': sp.get('latin'), 'russian': sp.get('russian'),
                'type': sp.get('type'), 'maps_review': (sp.get('maps') or {}).get('review_status'),
                'agent_light_npm': sp.get('material_id') in light or bool(sp.get('npm_light'))}
    used = set()
    records, review = [], []
    for a in a101_index['assets']:
        m = match_species(a['species'], species)
        rec = {'id': 'flora_a101:' + a['name'], 'source': 'a101', 'name': a['name'], 'species_slug': a['species'],
               'variant': a['variant'], 'height_cm': a['height_cm'],
               'objects': {v: a['versions'][v]['objects'] for v in a['versions']},
               'file': a['source']['path'], 'sha256': a['source'].get('sha256'), 'preview': a.get('preview'),
               'preview_match': a.get('preview_match'), 'catalogue': None, 'status': 'a101'}
        if m['candidates']:
            cands = [card(species[i]) for i in m['candidates']]
            if len(cands) == 1:
                rec['catalogue'] = dict(cands[0], level=m['level'])
                used.add(m['candidates'][0])
                if m['level'] == 'genus':  # one species of that genus in the catalogue: likely, but confirm
                    review.append({'id': rec['id'], 'level': 'genus', 'candidates': [cands[0]['latin']],
                                   'linked': True})
            else:
                rec['catalogue_candidates'] = {'level': m['level'], 'candidates': cands}
                review.append({'id': rec['id'], 'level': m['level'], 'candidates': [c['latin'] for c in cands]})
                used.update(m['candidates'])  # a candidate is not "missing from A101" either
        else:
            review.append({'id': rec['id'], 'level': None, 'candidates': []})
        records.append(rec)
    for i, sp in enumerate(species):
        if i in used:
            continue
        records.append({'id': 'flora_v003:' + re.sub(r'[^A-Za-z0-9]+', '_', sp.get('latin') or '').strip('_'),
                        'source': 'pilot_v003', 'latin': sp.get('latin'), 'russian': sp.get('russian'),
                        'type': sp.get('type'), 'material_id': sp.get('material_id'),
                        'objects': sp.get('objects'), 'file': catalogue.get('library_file'),
                        'vpm_status': sp.get('vpm_status'),
                        'maps_review': (sp.get('maps') or {}).get('review_status'),
                        'agent_light_npm': sp.get('material_id') in light or bool(sp.get('npm_light')),
                        'status': 'pilot_v003'})
    counts = {'a101': sum(1 for r in records if r['source'] == 'a101'),
              'a101_linked_to_catalogue': sum(1 for r in records if r.get('catalogue')),
              'a101_needs_review': len(review),
              'a101_unlinked': sum(1 for r in records if r['source'] == 'a101' and not r.get('catalogue')),
              'pilot_v003_added': sum(1 for r in records if r['source'] == 'pilot_v003'),
              'agent_light_npm': len({c['material_id'] for r in records
                                  for c in [r] + [r.get('catalogue') or {}] +
                                  list((r.get('catalogue_candidates') or {}).get('candidates', []))
                                  if c.get('agent_light_npm')})}
    return {'schema': UNIFIED_SCHEMA, 'kind': 'flora', 'truth': 'a101', 'records': records, 'review': review,
            'counts': counts}


# ---- MAF ----------------------------------------------------------------------------------------------------------
def _base(name):
    return re.sub(r'_(high|low)$', '', str(name), flags=re.IGNORECASE)


def _article_typo(a, b):
    """Same manufacturer and object, articles differ by one inserted/changed character (spec typo)."""
    pa, pb = a.split('_'), b.split('_')
    if len(pa) < 3 or len(pb) < 3 or pa[:-1] != pb[:-1]:
        return False
    x, y = pa[-1], pb[-1]
    return x != y and difflib.SequenceMatcher(None, x, y).ratio() >= 0.9


def maker_key(m):
    return skeleton(re.sub(r'[^a-z]', '', str(m).lower()).replace('group', ''))


def unify_maf(a101_index, legacy_catalogue):
    """A101 archives (truth) + album specification rows + legacy Union entries."""
    by_lower = {a['name'].lower(): a for a in a101_index['assets']}
    spec_by_asset, spec_no_model, notes = {}, [], []
    for r in legacy_catalogue.get('spec_matches', []):
        bases = sorted({_base(n) for n in (r.get('max_names') or [])})
        row = {'spec_row': r['spec_row'], 'spec_name': r.get('spec_name'), 'type': r.get('type'),
               'availability': r.get('availability'), 'spec_dims': r.get('spec_dims')}
        hit = [by_lower[b.lower()]['name'] for b in bases if b.lower() in by_lower]
        if not hit and bases:
            typo = [a['name'] for b in bases for a in a101_index['assets'] if _article_typo(b, a['name'])]
            if len(typo) == 1:
                hit = typo
                notes.append({'spec_row': r['spec_row'], 'spec_name_in_sheet': bases[0], 'a101': typo[0],
                              'note': 'article differs from A101 by one character: A101 taken as truth'})
        if hit:
            for h in hit:
                spec_by_asset.setdefault(h, []).append(dict(row, spec_max_names=bases))
        else:
            spec_no_model.append(dict(row, spec_max_names=bases,
                                      legacy_candidates=[b['id'] for b in (r.get('best') or [])]))
    records = []
    for a in a101_index['assets']:
        meta = a.get('meta') or {}
        geo = meta.get('geometry') or {}
        records.append({'id': 'maf_a101:' + a['name'], 'source': 'a101', 'name': a['name'],
                        'manufacturer': a.get('manufacturer'), 'title': a.get('title'), 'article': a.get('article'),
                        'versions': sorted(a['versions']), 'file': a['source']['path'],
                        'sidecar': bool(meta), 'units': meta.get('units'),
                        'tris': {v: geo[v].get('tris') for v in geo},
                        'bbox_mm': {v: geo[v].get('bbox') for v in geo},
                        'spec': spec_by_asset.get(a['name'], []), 'preview': a.get('preview'),
                        'warnings': a.get('warnings', []), 'status': 'a101'})
    for e in legacy_catalogue.get('entries', []):
        cat = re.sub(r'[\d_.]+$', '', e.get('source_object') or '') or 'unnamed'
        records.append({'id': 'maf_legacy:' + e['id'], 'source': 'legacy_union', 'name': e.get('slug'),
                        'category_hint': cat, 'tris': e.get('tris'), 'dims_m': e.get('dims_m'),
                        'dup_group': e.get('dup_group') or None, 'file': e.get('max_path'),
                        'preview': e.get('preview_path'), 'status': 'legacy_unidentified'})
    makers = {}
    for a in a101_index['assets']:
        makers.setdefault(maker_key(a.get('manufacturer') or ''), set()).add(a.get('manufacturer'))
    spelling = sorted(sorted(v) for v in makers.values() if len(v) > 1)
    arts = {}
    for a in a101_index['assets']:
        if a.get('article') and a['article'] != '0000':
            arts.setdefault(a['article'], []).append(a['name'])
    counts = {'a101': len(a101_index['assets']), 'a101_with_spec': sum(1 for r in records if r.get('spec')),
              'spec_rows': len(legacy_catalogue.get('spec_matches', [])), 'spec_without_a101_model': len(spec_no_model),
              'spec_without_model_with_legacy_candidates': sum(1 for s in spec_no_model if s['legacy_candidates']),
              'legacy_entries': len(legacy_catalogue.get('entries', []))}
    return {'schema': UNIFIED_SCHEMA, 'kind': 'maf', 'truth': 'a101', 'records': records,
            'spec_without_a101_model': spec_no_model, 'notes': notes,
            'review': {'manufacturer_spellings': spelling,
                       'shared_articles': {k: v for k, v in sorted(arts.items()) if len(v) > 1}},
            'counts': counts}
