"""new-case: agr npm-ids explicit JSON/FBX copy command and diagnostic evidence.

Input JSON is Blender intake protocol (objects/triangles/polygon UVs/metre verts).
Only a new output directory is accepted. Missing/ambiguous material bindings fail;
manual faces remain ID 0 with exact source polygon indices. No VPM is written.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.library.npm_ids import recover
from adapters.max.agr_tools import npm2vpm_core
from dt_ai.core.blender_runner import run_blender


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def process_document(doc, *, tolerance_px=.5):
    """Compute every assignment and group without publishing files."""
    if not isinstance(doc, dict) or not isinstance(doc.get('objects'), list) or not doc['objects']:
        raise ValueError('empty/partial input: objects required')
    reports, names = [], set()
    for obj in doc['objects']:
        name = obj['name']
        if name in names:
            raise ValueError(f'duplicate object {name}')
        names.add(name)
        polygons = obj['polygons']
        if not polygons:
            raise ValueError(f'{name}: empty polygons')
        ids = [0]*len(polygons)
        groups = []
        offset = 0
        for slot in sorted({p['slot'] for p in polygons}):
            key = str(slot)
            if key not in obj['atlases']:
                raise ValueError(f'{name}: unmapped material slot {slot}')
            indices = [i for i, p in enumerate(polygons) if p['slot'] == slot]
            result = recover(obj['atlases'][key], [polygons[i]['uv'] for i in indices], tolerance_px=tolerance_px)
            for local, mid in enumerate(result.pop('mat_ids')):
                ids[indices[local]] = mid+offset if mid else 0
            for row in result['table']:
                row['id'] += offset
            for k in ('empty_cells', 'non_rectangular_regions'):
                result[k] = [i+offset for i in result[k]]
            for k in ('straddling', 'unassigned', 'ambiguous'):
                result[k] = [indices[i] for i in result[k]]
            index_set = set(indices)
            valid = [f for f, p in enumerate(obj['tri_polygons']) if p in index_set and ids[p]]
            if valid:
                mesh = {k: obj[k] for k in ('verts', 'local', 'uvs')}
                mesh.update(tris=[obj['tris'][f] for f in valid], uv_tris=[obj['uv_tris'][f] for f in valid],
                            mat_ids=[ids[obj['tri_polygons'][f]] for f in valid])
                try:
                    result['udim_fit'] = npm2vpm_core.udim_fit_gate(mesh, dict(zip(('w', 'h'), result['atlas_size_px'])))
                except ValueError as exc:
                    result['udim_fit'] = {'status': 'blocked', 'error': str(exc)}
            else:
                result['udim_fit'] = {'status': 'blocked', 'error': 'no assigned faces'}
            result['gate_coverage'] = {'assigned_triangles': len(valid), 'all_triangles': len(obj['tris']),
                                       'complete': len(valid) == len(obj['tris']) and result['status'] == 'ok'}
            groups.append(result)
            offset += len(result['table'])
        obj['mat_ids'] = ids
        obj['triangle_mat_ids'] = [ids[p] for p in obj['tri_polygons']]
        reports.append({'name': name, 'groups': groups, 'polygons': len(polygons),
                        'unresolved_polygons': sum(i == 0 for i in ids)})
    ok = all(g['status'] == 'ok' and g['udim_fit']['status'] == 'ok' for o in reports for g in o['groups'])
    return {'status': 'ok' if ok else 'blocked', 'objects': reports, 'conversion_written': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path, help='NEW directory, never an input/output alias')
    parser.add_argument('--tolerance-px', type=float, default=.5)
    parser.add_argument('--blender')
    parser.add_argument('--intake-only', action='store_true', help='no .blend copy; JSON and ID table only')
    args = parser.parse_args(argv)
    try:
        source, output = args.source.resolve(), args.output.resolve()
        if not source.is_file() or source.suffix.lower() not in ('.fbx', '.json'):
            raise ValueError('source must be an existing .fbx or intake .json')
        if output.exists() or source == output or output in source.parents:
            raise ValueError('output must be a new directory distinct from all inputs')
        # Reserve the whole namespace exclusively; no predictable .partial files.
        output.mkdir(parents=True, exist_ok=False)
        before = digest(source)
        if source.suffix.lower() == '.fbx':
            doc = run_blender(ROOT/'tools/blender/npm_ids.py', ['extract', source, output/'intake.json'],
                              executable=args.blender, output_json=output/'intake.json', log_path=output/'intake.log')
        else:
            doc = json.loads(source.read_text(encoding='utf-8'))
        atlases = {p for o in doc['objects'] for p in o['atlases'].values()}
        hashes = {p: digest(p) for p in atlases}
        report = process_document(doc, tolerance_px=args.tolerance_px)
        if digest(source) != before or any(digest(p) != h for p, h in hashes.items()):
            raise ValueError('input changed during run')
        report['inputs_sha256'] = {str(source): before, **hashes}
        assignments = output/'mesh_ids.json'
        for path, value in ((assignments, doc), (output/'id_table.json', report)):
            with path.open('x', encoding='utf-8') as stream:
                json.dump(value, stream, ensure_ascii=False, allow_nan=False)
        if report['status'] == 'ok' and source.suffix.lower() == '.fbx' and not args.intake_only:
            run_blender(ROOT/'tools/blender/npm_ids.py', ['apply', source, output/'npm_ids.blend',
                        '--assignments', assignments], executable=args.blender, outputs=[output/'npm_ids.blend'],
                        log_path=output/'apply.log')
        print(json.dumps({'status': report['status'], 'report': str(output/'id_table.json'),
                          'objects': [(o['name'], o['polygons'], o['unresolved_polygons']) for o in report['objects']]}))
        return 0 if report['status'] == 'ok' else 1
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
