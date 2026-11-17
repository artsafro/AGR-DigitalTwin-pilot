"""new-case: agent CLI for the OKS master mesh quality score by the [D336] split rule (#1616).

Usage:
  uv run python tools/qa/mesh_quality_score.py MASTER.(blend|fbx|obj|json) --out NEW.json
         [--zone X0,Y0,X1,Y1 ...] [--exclude-zone X0,Y0,X1,Y1 ...] [--param key=value ...]

The master is read in a fresh headless Blender (tools/blender/mesh_quality_dump.py) or from a
recorded dump JSON; the score and its components come from tools/qa/mesh_quality_core.py.
Read-only: the input hash is checked before/after; the report is published exclusively to a
new path that must not alias the input. Exit 0 = measured, 1 = fail (n-gons / empty), 2 = error.
The score ranks masters; it is not an acceptance.
Explicit --rejoin-rectangles reconstructs rectangle-like coplanar pairs within 1 degree
on diagnostic copies of triangulated deliveries (#1634); default raw scoring is unchanged.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
FORMATS = ('.blend', '.fbx', '.obj', '.json')


def load_core():
    spec = importlib.util.spec_from_file_location('agr_mesh_quality_core', ROOT / 'tools/qa/mesh_quality_core.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


def parse_zone(text):
    parts = text.split(',')
    if len(parts) != 4:
        raise ValueError('zone must be X0,Y0,X1,Y1: ' + text)
    return [float(v) for v in parts]


def parse_param(text):
    key, sep, value = text.partition('=')
    if not sep:
        raise ValueError('param must be key=value: ' + text)
    try:
        return key, float(value)
    except ValueError:
        return key, value


def run(source, out, zones=None, params=None, blender=None, exclude_zones=None, *, rejoin_rectangles=False):
    """Read once, verify source freshness, publish exclusively; never reuse a report."""
    from dt_ai.ops.xview_gate import publish
    src, out = Path(source).resolve(), Path(out).resolve()
    if src == out or (out.exists() and src.exists() and src.samefile(out)):
        raise ValueError('report aliases input')
    if out.exists():
        raise ValueError('report exists; use a new versioned path')
    if src.suffix.lower() not in FORMATS:
        raise ValueError('unsupported master format: ' + src.suffix)
    if not src.is_file():
        raise ValueError('master not found: ' + str(src))
    if rejoin_rectangles and src.suffix.lower() == '.json':
        raise ValueError('rectangle rejoin requires a native mesh input, not a recorded JSON dump')
    before = sha(src)
    provenance = {'path': str(src), 'sha256': before, 'kind': src.suffix[1:].lower()}
    if src.suffix.lower() == '.json':
        dump = json.loads(src.read_text(encoding='utf-8'), object_pairs_hook=unique_keys)
        provenance['coverage'] = 'recorded geometry dump, not native freshness'
    else:
        from dt_ai.core.blender_runner import run_blender
        script = ROOT / 'tools/blender/mesh_quality_dump.py'
        with tempfile.TemporaryDirectory(prefix='mesh-quality-', dir=out.parent) as td:
            tmp = Path(td)
            args = [src, tmp / 'dump.json'] + (['--rejoin-rectangles'] if rejoin_rectangles else [])
            dump = run_blender(script, args, executable=blender,
                               output_json=tmp / 'dump.json', log_path=tmp / 'blender.log')
        provenance['blender'] = dump.get('blender')
        provenance['coverage'] = 'evaluated scene meshes before export triangulation'
        if rejoin_rectangles:
            provenance['coverage'] = 'diagnostic reconstructed rectangles; not original editable topology'
            provenance['normalization'] = dump['normalization']
    if not isinstance(dump, dict) or not isinstance(dump.get('objects'), list):
        raise ValueError('dump has no objects list')
    report = load_core().score(dump['objects'], params=params, zones=zones, exclude_zones=exclude_zones)
    if sha(src) != before:
        raise ValueError('master input changed during measure')
    report['input'] = provenance
    report['dropped'] = list(dump.get('dropped', [])) + report['dropped']
    publish(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2).encode('utf-8'), out)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('master')
    parser.add_argument('--out', required=True)
    parser.add_argument('--zone', action='append', default=[], help='X0,Y0,X1,Y1 plan box (repeatable)')
    parser.add_argument('--exclude-zone', action='append', default=[],
                        help='X0,Y0,X1,Y1 plan box left out of the measure (repeatable)')
    parser.add_argument('--param', action='append', default=[], help='key=value core parameter')
    parser.add_argument('--blender', default=None)
    parser.add_argument('--rejoin-rectangles', action='store_true',
                        help='diagnostic only: rejoin coplanar rectangular triangle pairs within 1 degree; '
                             'never saves geometry; raw master scoring remains the default')
    args = parser.parse_args(argv)
    try:
        zones = [parse_zone(z) for z in args.zone] or None
        exclude = [parse_zone(z) for z in args.exclude_zone] or None
        params = dict(parse_param(p) for p in args.param)
        report = run(args.master, args.out, zones, params, args.blender, exclude,
                     rejoin_rectangles=args.rejoin_rectangles)
    except (ValueError, OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({'score': report['score'], 'status': report['status'],
                      'components': report['components']}, ensure_ascii=False))
    return 0 if report['status'] == 'measured' else 1


if __name__ == '__main__':
    raise SystemExit(main())
