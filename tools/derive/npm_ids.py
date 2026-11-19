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
import copy
import math
from shapely.geometry import Polygon
from shapely.ops import unary_union
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.library.npm_ids import recover
from adapters.max.agr_tools import npm2vpm_core
from dt_ai.core.blender_runner import run_blender


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_document(doc):
    """Validate the complete intake before segmentation; indices never use Python wraparound."""
    if not isinstance(doc, dict) or not isinstance(doc.get('objects'), list) or not doc['objects']:
        raise ValueError('empty/partial input: objects required')
    names = set()
    for obj in doc['objects']:
        if not isinstance(obj, dict) or not isinstance(obj.get('name'), str) or not obj['name'].strip():
            raise ValueError('object name required')
        name = obj['name']
        if name in names:
            raise ValueError(f'duplicate object {name}')
        names.add(name)
        def pairs(key, width):
            rows = obj.get(key)
            if not isinstance(rows, list) or not rows or any(not isinstance(r, list) or len(r) != width or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in r) for r in rows):
                raise ValueError(f'{name}: invalid/nonfinite {key}')
        pairs('verts', 3); pairs('local', 3); pairs('uvs', 2)
        if len(obj['verts']) != len(obj['local']):
            raise ValueError(f'{name}: incomplete local vertices')
        polygons, atlases = obj.get('polygons'), obj.get('atlases')
        if not isinstance(polygons, list) or not polygons or not isinstance(atlases, dict) or not atlases:
            raise ValueError(f'{name}: polygons/atlases required')
        for p in polygons:
            if not isinstance(p, dict) or type(p.get('slot')) is not int or p['slot'] < 0:
                raise ValueError(f'{name}: invalid material slot')
            if str(p['slot']) not in atlases:
                raise ValueError(f'{name}: unmapped material slot {p["slot"]}')
            uv = p.get('uv')
            if not isinstance(uv, list) or len(uv) < 3 or any(not isinstance(r, list) or len(r) != 2 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in r) for r in uv):
                raise ValueError(f'{name}: invalid polygon UV')
        for key, path in atlases.items():
            if not isinstance(key, str) or not key.isdecimal() or str(int(key)) != key or not isinstance(path, str) or not path:
                raise ValueError(f'{name}: invalid atlas binding {key}')
        for key, size in [('tris', len(obj['verts'])), ('uv_tris', len(obj['uvs']))]:
            rows = obj.get(key)
            if not isinstance(rows, list) or not rows or any(not isinstance(r, list) or len(r) != 3 or
                any(type(i) is not int or not 0 <= i < size for i in r) or len(set(r)) != 3 for r in rows):
                raise ValueError(f'{name}: invalid {key} indices')
        tp = obj.get('tri_polygons')
        if not isinstance(tp, list) or len(tp) != len(obj['tris']) or len(obj['uv_tris']) != len(tp) or any(
            type(i) is not int or not 0 <= i < len(polygons) for i in tp) or set(tp) != set(range(len(polygons))):
            raise ValueError(f'{name}: incomplete triangle/polygon accounting')
        by_polygon = [[] for _ in polygons]
        for f, p in enumerate(tp):
            uv = [tuple(obj['uvs'][i]) for i in obj['uv_tris'][f]]
            if any(v not in {tuple(v) for v in polygons[p]['uv']} for v in uv):
                raise ValueError(f'{name}: triangle {f} UV disagrees with polygon {p}')
            by_polygon[p].append(tuple(sorted(uv)))
        for p, triangles in enumerate(by_polygon):
            if len(triangles) != len(polygons[p]['uv'])-2 or len(set(triangles)) != len(triangles):
                raise ValueError(f'{name}: incomplete/duplicated UV triangulation of polygon {p}')
            if len(polygons[p]['uv']) > 3:
                # Count n-2 is not a coverage proof (e.g. duplicated half-quads).
                poly = Polygon(polygons[p]['uv'])
                pieces = [Polygon(uv) for uv in triangles]
                union = unary_union(pieces)
                if (not poly.is_valid or any(not t.is_valid or t.area <= 0 for t in pieces)
                        or not union.equals(poly) or any(pieces[i].intersection(pieces[j]).area > 0
                        for i in range(len(pieces)) for j in range(i))):
                    raise ValueError(f'{name}: incomplete/overlapping UV coverage of polygon {p}')


def drop_zero_area(doc, approved):
    """Explicit source-index approval only; return a copy and complete drop lineage.

    No implicit cleanup. Every triangle of an approved polygon must have exactly
    zero cross product in world metres, never a tolerance-based deletion.
    """
    out = copy.deepcopy(doc)
    if not isinstance(approved, dict) or not approved:
        raise ValueError('explicit nonempty approved drops required')
    objects = {o['name']: o for o in out['objects']}
    if set(approved) - set(objects):
        raise ValueError(f'unknown drop objects: {sorted(set(approved)-set(objects))}')
    drops = []
    for name, requested in approved.items():
        obj = objects[name]
        if not isinstance(requested, list) or not requested or any(type(i) is not int or
            not 0 <= i < len(obj['polygons']) for i in requested) or len(set(requested)) != len(requested):
            raise ValueError(f'{name}: invalid/duplicate approved polygons')
        for p in requested:
            fs = [i for i, poly in enumerate(obj['tri_polygons']) if poly == p]
            if not fs:
                raise ValueError(f'{name}: polygon {p} has no triangles')
            for f in fs:
                xyz = [obj['verts'][i] for i in obj['tris'][f]]
                a, b = [[xyz[j][k]-xyz[0][k] for k in range(3)] for j in (1, 2)]
                cr = [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
                if any(not math.isfinite(v) or v != 0 for v in cr):
                    raise ValueError(f'{name}: approved polygon {p} has nonzero world area')
            drops.append({'object': name, 'source_polygon': p, 'reason': 'approved_zero_world_area', 'source_triangles': fs})
        keep = [p for p in range(len(obj['polygons'])) if p not in requested]
        mapping = {p: i for i, p in enumerate(keep)}
        fs = [f for f, p in enumerate(obj['tri_polygons']) if p in mapping]
        obj['source_polygons'] = keep
        obj['source_triangles'] = fs
        obj['polygons'] = [obj['polygons'][p] for p in keep]
        for key in ('tris', 'uv_tris'):
            obj[key] = [obj[key][f] for f in fs]
        obj['tri_polygons'] = [mapping[obj['tri_polygons'][f]] for f in fs]
        obj.pop('mat_ids', None); obj.pop('triangle_mat_ids', None)
    validate_document(out)
    return out, drops


def process_document(doc, *, tolerance_px=.5, segmentation=None):
    """Compute every assignment and group without publishing files."""
    validate_document(doc)
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
            result = recover(obj['atlases'][key], [polygons[i]['uv'] for i in indices],
                             tolerance_px=tolerance_px, segmentation=segmentation)
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
    parser.add_argument('--profile', choices=['maf', 'facade'], default='maf')
    parser.add_argument('--intake-only', action='store_true', help='no .blend copy; JSON and ID table only')
    args = parser.parse_args(argv)
    try:
        source, output = args.source.resolve(), args.output.resolve()
        if not source.is_file() or source.suffix.lower() not in ('.fbx', '.json'):
            raise ValueError('source must be an existing .fbx or intake .json')
        if output.exists() or source == output or output in source.parents:
            raise ValueError('output must be a new directory distinct from all inputs')
        before = digest(source)
        with tempfile.TemporaryDirectory(prefix='npm-ids-') as private:
            stage = Path(private)
            if source.suffix.lower() == '.fbx':
                doc = run_blender(ROOT/'tools/blender/npm_ids.py', ['extract', source, stage/'intake.json'],
                                  executable=args.blender, output_json=stage/'intake.json', log_path=stage/'intake.log')
            else:
                doc = json.loads(source.read_text(encoding='utf-8'))
            validate_document(doc)
            atlases = {Path(p).resolve() for o in doc['objects'] for p in o['atlases'].values()}
            inputs = {source, *atlases}
            if any(output == p or output in p.parents for p in inputs):
                raise ValueError('output aliases/contains an input')
            hashes = {str(p): digest(p) for p in inputs}
            if hashes[str(source)] != before:
                raise ValueError('source changed during intake')
            segmentation = (dict(profile='facade', work=2048, min_cell=32,
                                 edge_t=3, mat_diff=10, line_share=.8)
                            if args.profile == 'facade' else None)
            report = process_document(doc, tolerance_px=args.tolerance_px, segmentation=segmentation)
            report['inputs_sha256'] = hashes
            report['diagnostic_only'] = report['status'] != 'ok'
            assignments = stage/'mesh_ids.json'
            assignments.write_text(json.dumps(doc, ensure_ascii=False, allow_nan=False), encoding='utf-8')
            if report['status'] == 'ok' and source.suffix.lower() == '.fbx' and not args.intake_only:
                run_blender(ROOT/'tools/blender/npm_ids.py', ['apply', source, stage/'npm_ids.blend',
                            '--assignments', assignments], executable=args.blender, outputs=[stage/'npm_ids.blend'],
                            log_path=stage/'apply.log')
            if any(digest(p) != h for p, h in hashes.items()):
                raise ValueError('input changed during run')
            (stage/'id_table.json').write_text(json.dumps(report, ensure_ascii=False, allow_nan=False), encoding='utf-8')
            # Exclusive files, no overwrite/replace or predictable partial paths.
            # The report is committed last. Failed publication never leaves a valid receipt.
            output.mkdir(parents=True, exist_ok=False)
            published = []
            try:
                files = sorted(stage.iterdir(), key=lambda p: p.name == 'id_table.json')
                for path in files:
                    dest = output/path.name
                    with dest.open('xb') as stream:
                        published.append((dest.stat().st_ino, dest))
                        with path.open('rb') as src:
                            shutil.copyfileobj(src, stream)
            except BaseException:
                for inode, dest in reversed(published):
                    if dest.exists() and dest.stat().st_ino == inode:
                        dest.unlink()
                try:
                    output.rmdir()
                except OSError:
                    pass
                raise
        print(json.dumps({'status': report['status'], 'report': str(output/'id_table.json'),
                          'objects': [(o['name'], o['polygons'], o['unresolved_polygons']) for o in report['objects']]}))
        return 0 if report['status'] == 'ok' else 1
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
