"""New case #189: fail-closed v003 verifier; --partial is NOT acceptance."""
import argparse
import json
import statistics
import subprocess
from collections import Counter
from pathlib import Path
from catalogue import ROOT, portable
from checkpoints import load_valid, sha

HERE = Path(__file__).resolve().parent


def inspect_paths(names, root=Path('.')):
    forbidden = {'.max', '.fbx', '.png', '.jpg', '.jpeg', '.svg', '.tga', '.tif', '.tiff', '.pyc'}
    for name in set(names):
        p = root / name
        assert p.suffix.lower() not in forbidden, name
        if p.is_file():
            assert b'\x00' not in p.read_bytes(), name
    return sorted(set(names))


def verify_diff():
    names = subprocess.check_output(['git', 'diff', '--name-only', '7840deb'], text=True).splitlines()
    names += subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], text=True).splitlines()
    return inspect_paths(names)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--partial', action='store_true')
    args = ap.parse_args()
    catalog = json.loads((HERE / 'catalogue.json').read_text(encoding='utf-8'))
    sources = json.loads((ROOT / 'sources-verified.json').read_text(encoding='utf-8'))
    integrity = []
    for source in sources:
        a, b = sha(source['source']), sha(source['copy'])
        assert a == b == source['sha256'] == source['copy_sha256'] == source['sha256_after']
        integrity.append(dict(source, sha256_after_audit=a, copy_sha256_after_audit=b))
    rows, exported, readbacks, missing, failed, accounting = [], [], [], [], [], []
    for index, scene in enumerate(catalog['scenes']):
        counts = Counter(l['status'] for l in scene['labels'])
        assert sum(counts.values()) == scene['counts']['label']
        assert set(counts) <= {'paired', 'ambiguous', 'unpaired', 'category_heading'}
        accounting.append(dict(total=len(scene['labels']), **counts))
        for entry in scene['entries']:
            root = ROOT / 'out/verified-v004'
            exp = load_valid(root / (entry['id'] + '.json'), entry, sources[index]['copy_sha256'])
            if exp is None:
                missing.append(entry['id'])
                continue
            exported.append(exp)
            assert exp['coordinate_convention'] == 'snapshotAsMesh_world_no_extra_node_transform'
            assert exp['expected']['bbox_probe_error_mm'] <= .05
            assert max(abs(a-b) for x,y in zip(exp['expected']['snapshot_bbox'], entry['bbox_m']) for a,b in zip(x,y)) <= .00005
            assert entry['file'] in (None, entry['planned_file'])
            assert entry['preview'] in (None, entry['planned_preview'])
            assert Path(exp['file']) == ROOT / entry['planned_file']
            assert Path(exp['preview']) == ROOT / entry['planned_preview']
            assert len(exp['expected']['triangles']) == entry['triangles']
            header = Path(exp['file']).read_bytes()[:27]
            assert header[:23] == b'Kaydara FBX Binary  \x00\x1a\x00'
            assert int.from_bytes(header[23:27], 'little') == 7400
            rb_path = root / (entry['id'] + '-readback.json')
            rb = json.loads(rb_path.read_text(encoding='utf-8')) if rb_path.exists() else None
            if rb:
                assert rb['id'] == entry['id'] and rb['file_sha256'] == exp['sha256']
                readbacks.append(rb)
                if not rb['equal'] or rb['node_count'] != 1:
                    failed.append(entry['id'])
            rows.append({'id': entry['id'], 'source_name': entry['source_name'], 'triangles': entry['triangles'],
                         'source_snapshot_bbox_error_mm': exp['expected']['bbox_probe_error_mm'],
                         'corrected_signature_preview_seconds': exp['corrected_signature_preview_seconds'],
                         'file': entry['planned_file'], 'preview': entry['planned_preview'], 'file_sha256': exp['sha256'],
                         'preview_sha256': exp['preview_sha256'], 'export_seconds': exp['seconds'], 'readback': rb})
    complete = len(exported) == len(readbacks) == 136 and not missing and not failed
    if not args.partial:
        assert complete, 'Archive incomplete; --partial is not acceptance'
    deviations = [r['comparison']['max_deviation_mm'] for r in readbacks if r['equal']]
    result = portable({'application': 'headless 3ds Max 2026.3', 'acceptance_complete': complete,
        'delivery_passed': False, 'source_integrity': integrity, 'label_accounting': accounting,
        'export_count': len(exported), 'readback_count': len(readbacks), 'readbacks_equal': sum(r['equal'] for r in readbacks),
        'missing_export_ids': missing, 'failed_readback_ids': failed,
        'max_matched_corner_deviation_mm': max(deviations) if deviations else None,
        'max_uv_deviation': max((r['comparison']['max_uv_deviation'] for r in readbacks if r['equal']), default=None),
        'exported_triangles': sum(r['triangles'] for r in rows),
        'median_corrected_signature_preview_seconds': statistics.median(e['corrected_signature_preview_seconds'] for e in exported) if exported else None,
        'source_snapshot_bbox_max_error_mm': max((e['expected']['bbox_probe_error_mm'] for e in exported), default=None),
        'median_export_and_preview_seconds': statistics.median(e['seconds'] for e in exported) if exported else None,
        'median_readback_seconds': statistics.median(e['seconds'] for e in readbacks) if readbacks else None,
        'no_binary_diff_probe': {'checked_paths': verify_diff(), 'binary_count': 0}, 'artifacts': rows})
    assert isinstance(result, dict)
    measured_path = ROOT / 'readback-v004.json'
    if measured_path.exists():
        measured = json.loads(measured_path.read_text(encoding='utf-8'))
        result['coordinate_convention'] = measured['coordinate_convention']
        result['synthetic_snapshot_world_probe'] = measured['synthetic_snapshot_world_probe']
    native_path = ROOT / 'verify-fbx-batch-v004.json'
    if native_path.exists():
        native = json.loads(native_path.read_text(encoding='utf-8'))
        result['native_runner'] = portable({k:native[k] for k in ['status', 'exit_code', 'seconds', 'warnings']})
    filename = 'partial-verification.json' if args.partial else 'verification.json'
    (HERE / filename).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ['artifacts', 'source_integrity', 'missing_export_ids', 'no_binary_diff_probe']}, indent=2))


if __name__ == '__main__':
    main()
