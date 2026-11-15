"""new-case: agent CLI for the shared AGR Tools pre-export master check (#1420).

Usage: uv run python tools/qa/master_topology.py MASTER.blend --out NEW.json
Also accepts non-triangulated work .fbx or a Max/agent JSON polygon-degree inventory.
JSON snapshots are diagnostic evidence, not proof of a current native scene.
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


def load_core():
    spec = importlib.util.spec_from_file_location('agr_master_topology', ROOT / 'adapters/max/agr_tools/master_topology_core.py')
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


def run(source, out):
    """Read once, verify source freshness, publish exclusively; never reuse a report."""
    from dt_ai.ops.xview_gate import publish
    src, out = Path(source).resolve(), Path(out).resolve()
    if src == out or (out.exists() and src.exists() and src.samefile(out)):
        raise ValueError('report aliases input')
    if out.exists():
        raise ValueError('report exists; use a new versioned path')
    if src.suffix.lower() not in ('.json', '.fbx', '.blend'):
        raise ValueError('unsupported master format: ' + src.suffix)
    before = sha(src)
    provenance = {'path': str(src), 'sha256': before, 'kind': src.suffix[1:]}
    if src.suffix.lower() == '.json':
        inventory = json.loads(src.read_text(encoding='utf-8'), object_pairs_hook=unique_keys)
        provenance['coverage'] = 'recorded polygon-degree inventory, not native freshness'
        dropped = []
    else:
        from dt_ai.core.blender_runner import run_blender
        script = ROOT / 'tools/blender/master_topology_dump.py'
        with tempfile.TemporaryDirectory(prefix='master-topology-', dir=out.parent) as td:
            tmp = Path(td)
            dump = run_blender(script, [src, tmp / 'manifest.json'],
                               output_json=tmp / 'manifest.json', log_path=tmp / 'blender.log')
            inventory = dump['objects']
            provenance['blender'] = dump['blender']
            provenance['coverage'] = 'evaluated active-scene meshes before export triangulation'
            dropped = dump['dropped']
    report = load_core().check(inventory)
    if sha(src) != before:
        raise ValueError('master input changed during check')
    report['input'] = provenance
    report['dropped'] = dropped
    publish(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2).encode('utf-8'), out)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('master')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    try:
        report = run(args.master, args.out)
    except (ValueError, OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({'status': report['status'], 'objects': report['objects']}, ensure_ascii=False))
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
