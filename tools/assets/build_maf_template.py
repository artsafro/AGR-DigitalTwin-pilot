"""new-case: bring every A101 MAF to one library template (#1024, owner 07.11.2026).

uv run python tools/assets/build_maf_template.py --maf-index <cache>/maf_assets_index.json \
    --research <dir with maf_meta_*.json> --fixes <run>/out/fixes.json --fixed-dir <run>/out/fixed \
    --out-json library/assets/maf_template.json --out-meta-dir <new dir> --out-zip-dir <new dir>
Joins: archive sidecar or Max measurement (library/assets/maf_measured.json), web research (title, category,
description, manufacturer/product URLs, dimensions, materials), project schedules (VATUTINO-SITE links and
materials), the library audit and the geometry fixes. Writes the template list (git), one <name>.json per MAF
(for the Drive `a101_meta/` folder) and the corrected archives (for `a101_fixed/`): the original member list with
the fixed .max/FBX and the template JSON. Never overwrites an existing output file.
"""
import argparse
import glob
import importlib.util
import json
import os
from pathlib import Path
import sys
import zipfile

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


def repack(src_zip, fixed_dir, template, dst_zip):
    """Original member list and order; members present in fixed_dir (fixed .max/FBX) replace the originals; the
    sidecar <name>.json is the template (added when the archive had none)."""
    name = template['name']
    side = name + '.json'
    with zipfile.ZipFile(src_zip) as zin, zipfile.ZipFile(str(dst_zip) + '.tmp', 'x', zipfile.ZIP_DEFLATED) as zout:
        names = [i.filename for i in zin.infolist() if not i.is_dir()]
        for n in names:
            base = n.replace('\\', '/').rsplit('/', 1)[-1]
            if base.lower() == side.lower():
                continue
            fixed = Path(fixed_dir) / base
            if fixed.is_file():
                zout.write(str(fixed), base)
            else:
                zout.writestr(base, zin.read(n))
        zout.writestr(side, json.dumps(template, ensure_ascii=False, indent=2))
    os.replace(str(dst_zip) + '.tmp', str(dst_zip))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--maf-index', required=True)
    ap.add_argument('--measured', default=str(ROOT / 'library/assets/maf_measured.json'))
    ap.add_argument('--research', help='folder with maf_meta_*.json (web research)')
    ap.add_argument('--project-schedule', default=str(ROOT / 'jobs/VATUTINO-SITE/maf/site-schedule.json'))
    ap.add_argument('--project-set', default=str(ROOT / 'jobs/VATUTINO-SITE/maf/site-maf-set.json'))
    ap.add_argument('--fixes')
    ap.add_argument('--fixed-dir')
    ap.add_argument('--out-json', required=True)
    ap.add_argument('--out-meta-dir')
    ap.add_argument('--out-zip-dir')
    ap.add_argument('--replace', action='store_true', help='allow replacing --out-json only')
    a = ap.parse_args(argv)
    lib = _load('assets_library')
    idx = read(a.maf_index)
    if a.measured and os.path.isfile(a.measured):
        idx, _unknown = lib.attach_measured(idx, read(a.measured)['measured'])
    audit = {r['name']: r for r in lib.audit_maf(idx)['rows']}
    research = {}
    if a.research:
        for p in sorted(glob.glob(os.path.join(a.research, 'maf_meta_*.json'))):
            for r in read(p):
                research[r['name']] = r
    proj = lib.project_maf('VATUTINO-SITE', read(a.project_schedule), read(a.project_set), idx) \
        if os.path.isfile(a.project_schedule) else {'a101_enrich': {}, 'rows': [], 'counts': {}}
    fixes = {r['name']: r for r in read(a.fixes)['results']} if a.fixes else {}
    out, written = [], {'meta': 0, 'zips': []}
    for asset in idx['assets']:
        n = asset['name']
        fix = fixes.get(n) if fixes.get(n, {}).get('fixes') else None
        t = lib.maf_template(asset, asset.get('meta'), research.get(n), proj['a101_enrich'].get(n), audit.get(n), fix)
        # the fixed archive's own audit state: re-judge pivot findings from the fixed values
        if fix:
            t['agr']['audit']['findings'] = [c for c in t['agr']['audit']['findings']
                                             if c not in ('pivot_offset_xy', 'pivot_height')]
            t['agr']['audit']['warnings'] = [c for c in t['agr']['audit']['warnings'] if c != 'material_name']
        out.append(t)
        if a.out_meta_dir:
            os.makedirs(a.out_meta_dir, exist_ok=True)
            p = os.path.join(a.out_meta_dir, n + '.json')
            with open(p, 'x', encoding='utf-8') as f:
                json.dump(t, f, ensure_ascii=False, indent=2)
            written['meta'] += 1
        if fix and a.out_zip_dir and a.fixed_dir:
            os.makedirs(a.out_zip_dir, exist_ok=True)
            dst = Path(a.out_zip_dir) / (n + '.zip')
            if dst.exists():
                raise SystemExit('exists, not overwritten: ' + str(dst))
            repack(os.path.join(idx['root'], asset['source']['path']), os.path.join(a.fixed_dir, n), t, dst)
            written['zips'].append(str(dst))
    # project MAF (Kanban cards): built positions without an A101 archive join the library as template records;
    # positions without any model become the to-model list
    project_records, to_model = [], []
    for r in proj['rows']:
        if r['status'] == 'project_built':
            b = r['built']
            project_records.append({
                'schema': 3, 'name': lib.propose_maf_name(r.get('maker'), r.get('name'), r.get('article')),
                'title': r.get('name'), 'category': None, 'units': 'm',
                'download_url': r.get('link'), 'dimensions_text': 'x'.join(str(d) for d in r['dims_mm'] if d),
                'agr': {'template': lib.MAF_TEMPLATE, 'source': {'project': proj['project'], 'set_id': b['set_id'],
                                                                 'library_source': b['source']},
                        'status': 'files_on_project_pc', 'files': {'npm_fbx': b['npm_fbx'], 'vpm_fbx': b['vpm_fbx']},
                        'tris': {'npm': b['tris_npm'], 'vpm': b['tris_vpm']}, 'materials_v005': b['materials'],
                        'verdict': b['verdict'], 'materials_text': r.get('material'), 'qty_in_project': r.get('qty'),
                        'missing_for_template': ['High 4K textures (D/ERM/N)', '.max', 'preview', 'archive']}})
        elif r['status'] == 'missing':
            to_model.append({'project': proj['project'], 'table': r['table'], 'row': r['row'], 'name': r['name'],
                             'article': r.get('article'), 'maker': r.get('maker'), 'dims_mm': r['dims_mm'],
                             'link': r.get('link'), 'custom': r.get('custom'),
                             'proposed_name': lib.propose_maf_name(r.get('maker'), r.get('name'), r.get('article'))})
    doc = {'schema': 'agr.assets.maf_template_list/1', 'template': lib.MAF_TEMPLATE, 'count': len(out),
           'project_records': project_records, 'to_model': to_model,
           'research_confidence': {k: sum(1 for t in out if ((t['agr'].get('research') or {}).get('confidence')) == k)
                                   for k in ('found', 'partial', 'inferred')},
           'project': {'name': 'VATUTINO-SITE', 'counts': proj['counts'], 'rows': proj['rows']},
           'records': out}
    if os.path.exists(a.out_json) and not a.replace:
        raise SystemExit('exists (use --replace): ' + a.out_json)
    with open(a.out_json, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print(json.dumps({'records': len(out), 'research': doc['research_confidence'], 'project': proj['counts'],
                      'project_records': len(project_records), 'to_model': len(to_model),
                      'meta_written': written['meta'], 'zips': len(written['zips'])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
