"""new-case: headless agent entry to the AGR Tools window generator [D292, D322].

No DCC is needed for the stdlib OBJ builder. Outputs are new diagnostic bundles,
not deliveries; the same build_type/to_obj functions are used by the Max button.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'adapters/max/agr_tools'))
import windowgen_core as core  # noqa: E402

assign_glass = core.assign_glass


def unique_object(pairs):
    """Refuse duplicate JSON keys instead of accepting the last measurement."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def plan_openings(openings, lib):
    """Library first; unmatched sizes require an explicit source-derived generator record.

    Inset is an explicit measured/requested plan input, not inferred from glass.
    This command generates type meshes and placement instructions, not a building.
    """
    import winplace_core as place
    if not isinstance(openings, list) or not openings:
        raise ValueError('nonempty openings required')
    offered = core.offerable(core.library_report(lib['types'], lib['standard']))
    plans, drafts, seen = [], [], set()
    for o in openings:
        if not isinstance(o, dict) or set(o) - {'id', 'w', 'h', 'inset_m', 'type', 'generator', 'facade', 'rect'}:
            raise ValueError('unknown/invalid opening keys: ' + repr(o))
        oid = o.get('id')
        if not isinstance(oid, str) or not oid or oid in seen:
            raise ValueError('opening id missing or duplicate: ' + repr(oid))
        seen.add(oid)
        for k in ('w', 'h', 'inset_m'):
            core._num(o.get(k), oid + '.' + k)
        entry = o.get('generator')
        if entry is not None:
            if not isinstance(entry, dict):
                raise ValueError(oid + ': generator must be a source record')
            allowed = set().union(*(t.keys() for t in lib['types'])) | {'frame_profile_m', 'grilles_m'}
            if set(entry) - allowed:
                raise ValueError('unknown generator keys: ' + repr(sorted(set(entry) - allowed)))
            # Validate supplied fallback data even when a library fit will win.
            mesh = core.build_type(entry, lib['standard'], {'variant': 'vpm'})
            if mesh['status'] != 'ok':
                raise ValueError(oid + ': invalid generator record ' + repr(mesh['why']))
        wanted = o.get('type')
        if wanted is not None:
            if wanted not in offered:
                raise ValueError('unknown/unofferable type: ' + str(wanted))
            match = place.match(o, [lib['by_id'][wanted]], place.DEFAULTS['fit_tol_m'])
        else:
            match = place.match(o, [lib['by_id'][i] for i in offered], place.DEFAULTS['fit_tol_m'])
        if match['status'] == 'ambiguous':
            raise ValueError(oid + ': ambiguous library types ' + repr(match['others']))
        if match['type'] is not None and (match['fit']['dw'] < -0.0005 or match['fit']['dh'] < -0.0005):
            raise ValueError(oid + ': library frame wider than opening')
        tid, route = match['type'], 'library'
        if tid is None:
            entry = o.get('generator')
            if wanted is not None or not isinstance(entry, dict):
                raise ValueError(oid + ': no library fit; explicit generator record required')
            tid = entry.get('id')
            if tid in lib['by_id'] or any(d.get('id') == tid and d != entry for d in drafts):
                raise ValueError('generator id collides: ' + str(tid))
            q = core.quality(entry, lib['standard'])
            if q['status'] != 'ok' or abs(entry['width_m'] - o['w']) > 1e-9 or abs(entry['height_m'] - o['h']) > 1e-9:
                raise ValueError(oid + ': invalid or nonmatching generator record ' + repr(q))
            if entry not in drafts:
                drafts.append(entry)
            route = 'generator'
        plans.append(dict(o, type=tid, route=route, generator=None))
    return plans, drafts


def generate(ids, library, out, *, drafts=(), run=None, inputs=(), snapshots=None):
    """Build selected types using the complete library's quality/duplicate decisions."""
    snapshots = snapshots if snapshots is not None else {Path(p).resolve(): Path(p).read_bytes() for p in inputs}
    lib = core.load_library(str(library))
    source_hashes = dict(lib['sha256'])
    for entry in drafts:
        if entry['id'] in lib['by_id']:
            raise ValueError('generator id collides: ' + entry['id'])
        lib['types'].append(entry)
        lib['by_id'][entry['id']] = entry
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('ids must be nonempty and unique')
    unknown = set(ids) - set(lib['by_id'])
    if unknown:
        raise ValueError('unknown window ids: ' + ', '.join(sorted(unknown)))
    if any(not i or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in i)
           for i in ids):
        raise ValueError('unsafe window id')
    report = core.library_report(lib['types'], lib['standard'])
    chosen = [lib['by_id'][i] for i in ids]
    sub = dict(report, types=[r for r in report['types'] if r['id'] in ids])
    sub['counts'] = {v: sum(r['verdict'] == v for r in sub['types']) for v in core.VERDICTS}
    bad = [r for r in sub['types'] if r['verdict'] != 'pass']
    if bad:
        raise ValueError('not offerable: ' + repr([(r['id'], r['verdict']) for r in bad]))
    payloads = {'quality.json': core.report_json(sub).encode('utf-8'),
                'sheet.png': core.sheet_png(chosen, lib['standard'], sub)}
    meshes = {}
    for tid in ids:
        m = core.build_type(lib['by_id'][tid], lib['standard'], {'variant': 'vpm'})
        payloads[tid + '.obj'] = core.to_obj(m, tid).encode('utf-8')
        meshes[tid] = {'faces': len(m['faces']), 'glass': len(m['parts']['glass']), 'family': m['family'],
                       'face_axis': m['face_axis'], 'size_m': m['size_m']}
    payloads['meshes.json'] = (json.dumps(meshes, indent=1) + '\n').encode('utf-8')
    import hashlib
    run = dict(run or {}, schema='window-run/1', library_sha256=source_hashes,
               inputs={str(p): hashlib.sha256(b).hexdigest() for p, b in snapshots.items()})
    run.setdefault('status', 'pass')
    payloads['run.json'] = (json.dumps(run, ensure_ascii=False, indent=1, allow_nan=False) + '\n').encode('utf-8')
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('out must be a new directory: ' + str(out))
    out.parent.mkdir(parents=True, exist_ok=True)
    # Private unpredictable staging, no shared .partial name and no input cleanup.
    stage = Path(tempfile.mkdtemp(prefix='.window-', dir=out.parent))
    try:
        for name, data in payloads.items():
            with (stage / name).open('xb') as stream:
                stream.write(data)
        if (core.load_library(str(library))['sha256'] != source_hashes
                or any(p.read_bytes() != b for p, b in snapshots.items())):
            raise ValueError('input/library changed during generation')
        # Windows rename is atomic and refuses existing targets, including empty directories.
        if os.name != 'nt':
            raise ValueError('atomic no-replace directory publication currently requires Windows')
        os.rename(stage, out)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return {'out': str(out), 'files': list(payloads), 'counts': sub['counts']}


def kpp1_openings(spec, inset_m):
    """Adapt the existing KPP1 spec to explicit facade-local generator inputs."""
    core._num(inset_m, 'inset_m')
    if not isinstance(spec, dict) or set(spec) != set('SNWE'):
        raise ValueError('KPP1 spec requires S,N,W,E facades')
    openings = []
    for f, face in spec.items():
        for kind in ('surrounds', 'features'):
            for surround in face[kind]:
                for bay in surround['bays']:
                    r = bay['rect']
                    if not isinstance(r, list) or len(r) != 4:
                        raise ValueError('bay rect must be [u0,u1,z0,z1]')
                    for c in r:
                        core._num(c, 'bay rect', positive=False)
                    openings.append({'id': str(bay['id']), 'facade': f, 'rect': r,
                                     'w': r[1] - r[0], 'h': r[3] - r[2], 'inset_m': inset_m})
    return openings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--ids', nargs='+')
    mode.add_argument('--request', type=Path, help='JSON object: schema window-request/1, openings list')
    mode.add_argument('--kpp1-source', type=Path, help='existing Revit source directory (read only)')
    parser.add_argument('--kpp1-census', type=Path, help='existing object dumps directory (read only)')
    parser.add_argument('--inset-m', type=float, help='explicit inset for KPP1 opening plans, metres')
    parser.add_argument('--library', type=Path, default=ROOT / 'library/windows')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        from collections import Counter
        inputs = [args.library / f for f in core.LIBRARY_FILES] + [
            Path(__file__).resolve(), ROOT / 'adapters/max/agr_tools/windowgen_core.py',
            ROOT / 'adapters/max/agr_tools/winplace_core.py']
        if args.request:
            inputs.append(args.request)
        if args.kpp1_source:
            if args.kpp1_census is None or args.inset_m is None:
                raise ValueError('KPP1 requires --kpp1-census and explicit --inset-m')
            inputs += [ROOT / 'jobs/KPP1/scripts/extract_openings.py', ROOT / 'adapters/max/agr_tools/openings_core.py',
                       args.kpp1_source / 'curtain.export.json',
                       args.kpp1_census / 'curtain.objects.json', args.kpp1_census / 'openings.objects.json',
                       ROOT / 'jobs/KPP1/spec-compare-v002.md']
        elif args.kpp1_census is not None or args.inset_m is not None:
            raise ValueError('KPP1 flags require --kpp1-source')
        resolved = [p.resolve() for p in inputs]
        if len(set(resolved)) != len(resolved) or any(a.samefile(b) for i,a in enumerate(inputs) for b in inputs[i+1:]):
            raise ValueError('aliased input paths')
        snapshots = {p.resolve(): p.read_bytes() for p in inputs}
        lib = core.load_library(str(args.library))
        run, drafts = {'status': 'pass'}, []
        ids = args.ids
        if args.request:
            request = json.loads(snapshots[args.request.resolve()].decode('utf-8-sig'), object_pairs_hook=unique_object)
            if not isinstance(request, dict) or request.get('schema') != 'window-request/1' or set(request) != {'schema','openings'}:
                raise ValueError('expected window-request/1 with openings only')
            openings = request['openings']
        elif args.kpp1_source:
            sys.path.insert(0, str(ROOT / 'jobs/KPP1/scripts'))
            import extract_openings
            spec, drops, ownership = extract_openings.extract(str(args.kpp1_source), str(args.kpp1_census))
            openings = kpp1_openings(spec, args.inset_m)
            unexplained = [d for d in drops if d['reason'] != 'on no exterior facade']
            measured = snapshots[ROOT / 'jobs/KPP1/spec-compare-v002.md'].decode('utf-8')
            run.update(status='fail' if unexplained or ownership['status'] != 'pass' else 'pass',
                       ownership=ownership, dropped_objects=drops, unexplained_drop_count=len(unexplained),
                       drop_counts=dict(Counter(d['reason'] for d in drops)),
                       measured_input={'source': 'jobs/KPP1/spec-compare-v002.md', 'historical': True,
                                       'text': measured, 'action': 'reported only; KPP1 not repaired'})
        if ids is None:
            plans, drafts = plan_openings(openings, lib)
            run['openings'] = plans
            ids = list(dict.fromkeys(p['type'] for p in plans))
        result = generate(ids, args.library, args.out, drafts=drafts, run=run, snapshots=snapshots)
        print(json.dumps(dict(result, status=run['status'])))
        return 0 if run['status'] == 'pass' else 1
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
