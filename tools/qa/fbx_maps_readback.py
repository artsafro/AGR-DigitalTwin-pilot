"""Pattern: n/a | new-case: #1729 host CLI over agr_tools/fbxmaps_core.py: metallic-channel check of an exported
FBX and the unconnected-maps readback after a 3ds Max FBX import.

    python tools/qa/fbx_maps_readback.py channels FBX [FBX ...]          -> metallic channel findings, exit 1 on any
    python tools/qa/fbx_maps_readback.py import FBX --scene IMPORT.json --output NEW.json
        IMPORT.json: {'connected': [{'file': ...}, ...]} as written by tools/max/metallic_channel_probe_max.py
        (fbxmaps_max.connected_maps). Exit 0 pass, 1 an embedded map is unconnected, 2 bad input.
The output must be a new file that is not an input; nothing is written on refusal.
"""
import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _core():
    spec = importlib.util.spec_from_file_location('agr_tools_fbxmaps_core', ROOT / 'adapters/max/agr_tools/fbxmaps_core.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _same(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def main(argv=None):
    ap = argparse.ArgumentParser(prog='fbx_maps_readback')
    sub = ap.add_subparsers(dest='cmd', required=True)
    ch = sub.add_parser('channels')
    ch.add_argument('fbx', nargs='+', type=Path)
    im = sub.add_parser('import')
    im.add_argument('fbx', type=Path)
    im.add_argument('--scene', type=Path, required=True)
    im.add_argument('--output', type=Path, required=True)
    a = ap.parse_args(argv)
    core = _core()
    try:
        if a.cmd == 'channels':
            bad = 0
            for f in a.fbx:
                rows = core.metallic_channel_findings(core.read_fbx(f))
                bad += len(rows)
                print('{}: {}'.format(f.name, 'pass' if not rows else 'fail'))
                for r in rows:
                    print('  ' + r['reason'])
            return 1 if bad else 0
        for p in (a.fbx, a.scene):
            if a.output.exists() and _same(a.output, p):
                raise ValueError('--output is an input: ' + str(p))
        if a.output.exists():
            raise ValueError('--output exists (never reused): ' + str(a.output))
        scene = json.loads(a.scene.read_text(encoding='utf-8'))
        if not isinstance(scene.get('connected'), list):
            raise ValueError('--scene has no "connected" list')
        doc = core.read_fbx(a.fbx)
        rb = core.import_readback(doc, scene['connected'])
        rb.update({'fbx': str(a.fbx), 'scene': str(a.scene), 'issue': 1729})
    except (OSError, ValueError, KeyError) as exc:
        print('ERROR: {}'.format(exc), file=sys.stderr)
        return 2
    a.output.write_text(json.dumps(rb, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print('status={} embedded={} connected={} unconnected={}'.format(rb['status'], rb['embedded'], rb['connected'],
                                                                      len(rb['unconnected'])))
    for r in rb['unconnected']:
        print('  unconnected {} role={} {}'.format(r['file'], r['role'], [m[:2] for m in r['materials']]))
    return 0 if rb['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
