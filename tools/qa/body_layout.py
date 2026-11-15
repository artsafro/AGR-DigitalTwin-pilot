"""new-case: per-part BODY pre-show wall_layout + quad_dominance receipt (#1446).

uv run python tools/qa/body_layout.py MASTER.blend --profile VPM --part BODY --out NEW.json
Read-only Blender 5.1.2 via the shared xview polygon adapter (metres, Z up).
JSON accepts a list of work-FBX mesh rows; NPZ accepts the xview dump format.
Exit 0 = measured report published, NOT geometry acceptance. Wall diagnostics
are report-only [D227]; quad_dominance's independent verdict stays in the report.
Invalid/partial/unsupported evidence exits 2, without publishing a clean receipt.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from dt_ai.ops.xview_gate import DUMP_SCRIPT, load_npz, publish, to_metres
from twinqa.look import part_layout_report


def sha(path):
    with path.open('rb') as fh:
        return hashlib.file_digest(fh, 'sha256').hexdigest()


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def run(source, out, profile, *, parts=None, **thresholds):
    """Hash input before/after, preserve all source ids, exclusively publish a new report."""
    src, out = Path(source).resolve(), Path(out).resolve()
    log = out.with_name(out.name + '.blender.log')
    for dest in (out, log):
        if dest == src or (dest.exists() and src.exists() and dest.samefile(src)):
            raise ValueError('report/log aliases input')
        if dest.exists():
            raise ValueError(f'{dest} exists; use a new versioned path')
    if src.suffix.lower() not in ('.json', '.npz', '.blend', '.fbx'):
        raise ValueError('unsupported BODY input: ' + src.suffix)
    if not out.parent.is_dir():
        raise ValueError('report folder does not exist: ' + str(out.parent))
    before = sha(src)
    provenance = dict(path=str(src), sha256=before, coordinates='metres, Z up')
    dropped = []
    if src.suffix.lower() == '.json':
        rows = json.loads(src.read_text(encoding='utf-8'), object_pairs_hook=unique_keys)
        provenance['coverage'] = 'recorded polygon geometry; not native scene freshness'
    else:
        if src.suffix.lower() == '.npz':
            loaded = load_npz(src)
            provenance['coverage'] = 'recorded xview polygon dump; not native scene freshness'
        else:
            from dt_ai.core.blender_runner import run_blender
            # Unique per-invocation workspace; no predictable .partial/dump names.
            with tempfile.TemporaryDirectory(prefix='body-layout-', dir=out.parent) as td:
                tmp = Path(td)
                npz, manifest = tmp/'parts.npz', tmp/'manifest.json'
                dump = run_blender(DUMP_SCRIPT, [src, npz, manifest], output_json=manifest,
                                   outputs=[npz], log_path=tmp/'blender.log')
                loaded = load_npz(npz)
                if [o['name'] for o in dump['objects']] != [p.name for p in loaded]:
                    raise ValueError('Blender manifest/dump object mismatch')
                loaded, units = to_metres(loaded, dump)
                provenance.update(blender=dump['blender'], scene=dump['scene'], units=units,
                                  coverage='evaluated active-scene polygon meshes before export triangulation')
                dropped = dump['dropped']
                publish((tmp/'blender.log').read_bytes(), log)
                provenance['log'] = str(log)
        rows = [dict(name=p.name, face_geometry=dict(vertices=p.vertices.tolist(), polygons=p.faces))
                for p in loaded]
    if not isinstance(rows, list) or not rows:
        raise ValueError('no BODY parts to check')
    # Check names across the complete inventory before selecting BODY objects;
    # unselected objects receive an explicit reasoned drop record below.
    names = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('name'), str):
            raise ValueError('invalid part row')
        if row['name'] in names:
            raise ValueError('duplicate part: ' + row['name'])
        names.append(row['name'])
    if parts is not None:
        if not parts or len(parts) != len(set(parts)):
            raise ValueError('part selection is empty or duplicated')
        missing = sorted(set(parts) - set(names))
        if missing:
            raise ValueError(f'unknown parts: {missing}')
    selected = rows if parts is None else [r for r in rows if r['name'] in parts]
    report = part_layout_report(selected, profile, **thresholds)
    report['input'] = provenance
    report['dropped'] = dropped + [dict(name=n, reason='not selected as BODY part')
                                   for n in names if parts is not None and n not in parts]
    if sha(src) != before:
        raise ValueError('BODY input changed during check')
    publish(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2).encode('utf-8'), out)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('--out', required=True)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--part', action='append')
    for option in ('normal-z-max', 'axis-tol-deg', 'sliver-short-m', 'sliver-long-m'):
        parser.add_argument('--' + option, type=float)
    parser.add_argument('--fan-min-triangles', type=int)
    args = vars(parser.parse_args())
    source, out, profile, parts = (args.pop(k) for k in ('source', 'out', 'profile', 'part'))
    try:
        report = run(source, out, profile, parts=parts, **{k:v for k,v in args.items() if v is not None})
    except (ValueError, OSError, RuntimeError, TypeError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps([dict(part=p['part'], wall_layout=p['wall_layout']['counts'],
                           quad_dominance=p['quad_dominance']['passed']) for p in report['parts']]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
