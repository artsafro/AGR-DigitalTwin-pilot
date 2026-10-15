"""Verify real #189 artifacts and original hashes; emit text-only receipts.

No Max run and no source writes. Run after export_assets.py finishes, then regenerate
catalogue.py first so TextPlus payloads are included in the committed catalogue.
"""
import hashlib
import json
import statistics
from pathlib import Path

from catalogue import ROOT

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    native = json.loads((ROOT / 'readback-v001.json').read_text(encoding='utf-8'))
    catalogue = json.loads((HERE / 'catalogue.json').read_text(encoding='utf-8'))
    entries = [e for s in catalogue['scenes'] for e in s['entries']]
    exported = {e['id']: e for e in native['exports']}
    readbacks = {e['id']: e for e in native['readbacks']}
    assert len(exported) == len(entries) == len(readbacks) == 136
    assert len(native['exports']) == len(exported) and len(native['readbacks']) == len(readbacks)
    assert not native['failures']
    rows = []
    for entry in entries:
        exp = exported[entry['id']]
        rb = readbacks[entry['id']]
        assert exp['name'] == entry['source_name']
        assert rb['equal'] and rb['node_count'] == 1
        assert sha(exp['file']) == exp['sha256']
        assert sha(exp['preview']) == exp['preview_sha256']
        assert exp['file'] == entry['file'] and exp['preview'] == entry['preview']
        assert exp['expected']['triangles'] == entry['triangles']
        actual = rb['actual']
        bbox_mm = max(abs(a-b) * 1000 for ca, cb in zip(exp['expected']['bbox'], actual['bbox']) for a, b in zip(ca, cb))
        rows.append({'id': entry['id'], 'source_name': entry['source_name'], 'triangles': entry['triangles'],
                     'max_bbox_deviation_mm': bbox_mm, 'mesh_uv_material_ids_sha256': actual['mesh_sha256'],
                     'file_sha256': exp['sha256'], 'preview_sha256': exp['preview_sha256'],
                     'node_count': rb['node_count'], 'readback_equal': rb['equal']})
    sources = []
    for source in catalogue['sources']:
        after = sha(source['source'])
        copy_after = sha(source['copy'])
        assert after == copy_after == source['sha256'] == source['sha256_after'] == source['copy_sha256']
        sources.append(dict(source, sha256_after_audit=after, copy_sha256_after_audit=copy_after))
    evidence = {'application': 'headless 3ds Max 2026.3 (28.3.0.30732)', 'source_integrity': sources,
                'textplus': native['textplus'], 'artifact_count': len(rows), 'readbacks_equal': sum(r['readback_equal'] for r in rows),
                'max_bbox_deviation_mm': max(r['max_bbox_deviation_mm'] for r in rows),
                'internal_native_seconds': native['seconds_total'],
                'median_export_and_preview_seconds': statistics.median(e['seconds'] for e in native['exports']),
                'median_readback_seconds': statistics.median(e['seconds'] for e in native['readbacks']),
                'artifacts': rows, 'delivery_passed': False}
    for name in ['inspect-batch', 'inspect-detailed-batch', 'export-batch-v001']:
        path = ROOT / (name + '.json')
        if path.exists():
            result = json.loads(path.read_text(encoding='utf-8'))
            evidence[name] = {k: result[k] for k in ['status', 'exit_code', 'seconds', 'warnings']}
    (HERE / 'verification.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in evidence.items() if k not in ('artifacts', 'source_integrity', 'textplus')}, indent=2))


if __name__ == '__main__':
    main()
