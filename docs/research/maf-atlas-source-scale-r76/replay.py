"""Replay the frozen R1 source-scale observation via the existing MAF baker."""
from __future__ import annotations

import hashlib
import io
import json
import runpy
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
R1 = '88535418e4e259e29f1d2bff9d9dbf3a55bbb92f'
R2 = '01e48513aa9bba11553bc3c0c296414e7ba26c6d'
LAYOUT = 'library/maf/atlas_512_v007.json'
BAKER = 'jobs/maf-atlas-512/scripts/atlas_maf_from_source.py'
OWNERS = (BAKER, 'tools/materials/atlas_maf.py', 'tools/library/maf_atlas_ids.py',
          'tools/library/maf_atlas_layout.py', 'uv.lock')
LIMIT = 120.0
EPS = 1e-12


def git_blob(rev, path):
    return subprocess.check_output(['git', 'show', f'{rev}:{path}'], cwd=ROOT)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked(ref):
    data = Path(ref['path']).read_bytes()
    if digest(data) != ref['sha256']:
        raise ValueError(f"SHA-256 mismatch: {ref['path']}")
    return data


def decode(data, size):
    with Image.open(io.BytesIO(data)) as img:
        if list(img.size) != size or img.format != 'PNG':
            raise ValueError('unexpected PNG format/dimensions')
        return np.asarray(img.convert('RGB'))


def score(crop, width, height):
    return 1 - min(crop.shape[1] / width, crop.shape[0] / height)


def changed(left, right):
    return int(np.count_nonzero(np.any(left != right, axis=2)))


def round_once(out):
    start = time.perf_counter()
    out.mkdir()
    for name in OWNERS:
        if (ROOT / name).read_bytes().replace(b'\r\n', b'\n') != git_blob(R2, name):
            raise ValueError(f'owner/lock differs from {R2}: {name}')
    baker = runpy.run_path(str(ROOT / BAKER))
    core = baker['atlas_maf']
    layouts = [json.loads(git_blob(rev, LAYOUT)) for rev in (R1, R2)]
    source = layouts[0]['inputs']['source']
    if source != layouts[1]['inputs']['source']:
        raise ValueError('different source identity')
    refs = [source, *(layout['atlas'] for layout in layouts)]
    src, *published = [decode(checked(ref), ref['size']) for ref in refs]
    rows, controls = [], []

    def render(crop, cell, pad):
        path = out / 'scratch_crop.png'
        Image.fromarray(crop).save(path)
        m = core.Material(cell['key'], 'patterned', cell['slot_px'][2], 0, texture=path)
        s = core.Slot(m.name, m.kind, 0, 0, m.size)
        return np.asarray(core.render_atlas([s], [m], m.size, pad))

    for rev, lay, png in zip(('r1', 'r2'), layouts, published, strict=True):
        slots = {s['id']: s for s in lay['slots']}
        pad = lay['padding_px']
        for c in lay['cells']:
            sid = c['id']
            spec = slots[sid]
            row = {'revision': rev, 'id': sid, 'kind': spec['kind']}
            if c['kind'] != spec['kind'] or c['key'] != spec['key']:
                raise ValueError('slot/cell identity mismatch')
            rows.append(row)
            if spec['kind'] == 'solid':
                row['state'] = 'not_exercised'
                continue
            crop = baker['crop_slot'](src, spec)
            ox, oy, sw, sh = c['slot_px']
            x, y, w, h = c['content_px']
            zx, zy, zw, zh = c['id_corner_px']
            i, j = x - ox, y - oy
            if (x, y, w, h) != core._content_box(ox, oy, sw, pad) or sw != sh:
                raise ValueError('content rectangle differs from rasterizer')
            if not (0 <= ox <= x <= zx < zx + zw <= x+w <= ox+sw <= png.shape[1] and
                    0 <= oy <= y <= zy < zy + zh <= y+h <= oy+sh <= png.shape[0]):
                raise ValueError('bad slot/content/marker extent')
            rendered = render(crop, c, pad)
            mask = np.ones((sw, sw), dtype=bool)
            mask[zy-oy:zy-oy+zh, zx-ox:zx-ox+zw] = False
            diff = np.any(rendered != png[oy:oy+sw, ox:ox+sw], axis=2)
            e = score(crop, w, h)
            row.update(label='rejected' if (rev, sid) == ('r1', 18) else 'accepted',
                       source_size=list(crop.shape[1::-1]), content_size=[w, h], E76=e, flagged=e > 0,
                       parity_changed_px=int(np.count_nonzero(diff & mask)),
                       parity_compared_px=int(mask.sum()), control_state='exercised' if sid == 18 else 'not_exercised')
            if sid != 18:
                continue
            clean = rendered[j:j+h, i:i+w]
            sizes = [107] if rev == 'r1' else [247, 248, 249]
            variants = [('brightness_plus_8', np.minimum(crop.astype(np.uint16) + 8, 255).astype(np.uint8), e)]
            for n in sizes:
                cy, cx = [(m - n) // 2 for m in crop.shape[:2]]
                delta = 13/120 if rev == 'r1' else (248-n)/248
                variants.append((f'center_trim_{n}', crop[cy:cy+n, cx:cx+n], delta))
            for name, variant, expected in variants:
                new = render(variant, c, pad)[j:j+h, i:i+w]
                count = changed(new, clean)
                v = score(variant, w, h)
                controls.append({'revision': rev, 'id': sid, 'variant': name, 'E76': v,
                                 'expected': expected, 'flagged': v > 0, 'expected_flagged': expected > 0,
                                 'source_size': list(variant.shape[1::-1]), 'changed_px': count,
                                 'unchanged_px': w*h-count, 'state': 'exercised' if count else 'not_exercised'})
    for ref in refs:
        checked(ref)
    (out / 'scratch_crop.png').unlink()
    acc = [r for r in rows if r.get('label') == 'accepted']
    rej = [r for r in rows if r.get('label') == 'rejected']
    if (len(acc), len(rej), len(controls)) != (5, 1, 6):
        raise ValueError('fixture cardinality changed')
    return {'inputs': refs, 'D76': rej[0]['E76'] - max(r['E76'] for r in acc), 'rows': rows, 'controls': controls,
            'clean_flags_ok': rej[0]['flagged'] and not any(r['flagged'] for r in acc),
            'parity_ok': all(r['parity_changed_px'] == 0 for r in acc + rej),
            'controls_ok': all(c['changed_px'] and abs(c['E76']-c['expected']) <= EPS and
                               c['flagged'] == c['expected_flagged'] for c in controls),
            'wall_s': time.perf_counter() - start}


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--round':
        print(json.dumps(round_once(Path(sys.argv[2])), ensure_ascii=True))
        return
    if len(sys.argv) != 2:
        raise SystemExit('usage: replay.py NEW_OUTPUT_DIR')
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    rounds = []
    stop = 'series_completed'
    for n in range(1, 4):
        remaining = LIMIT - (time.perf_counter() - start)
        if remaining <= 0:
            stop = 'budget_stop'
            break
        pair_start = time.perf_counter()
        try:
            p = subprocess.run([sys.executable, __file__, '--round', str(out / f'pair-{n}')],
                               cwd=ROOT, capture_output=True, text=True, timeout=remaining)
        except subprocess.TimeoutExpired:
            stop = 'budget_stop'
            break
        if p.returncode:
            stop = 'pair_error'
            (out / f'pair-{n}.stderr.txt').write_text(p.stderr, encoding='utf-8')
            break
        data = json.loads(p.stdout)
        data['process_wall_s'] = time.perf_counter() - pair_start
        rounds.append(data)
        (out / f'pair-{n}.json').write_text(p.stdout, encoding='utf-8', newline='\n')
        if n == 1 and 2 * data['process_wall_s'] > LIMIT - (time.perf_counter() - start):
            stop = 'budget_stop'
            break
    differences = [r['D76'] for r in rounds]
    spread = max(differences) - min(differences) if len(differences) == 3 else None
    verdict = 'inconclusive'
    if stop == 'series_completed' and all(r['parity_ok'] and r['controls_ok'] for r in rounds):
        if min(differences) >= 0.10 and spread <= EPS and all(r['clean_flags_ok'] for r in rounds):
            verdict = 'confirmed_fixture_only'
        elif max(differences) <= 0:
            verdict = 'refuted'
    result = {'status': stop, 'hypothesis': verdict, 'D76_median': statistics.median(differences) if spread is not None else None,
              'paired_spread': spread, 'wall_s': time.perf_counter() - start, 'rounds': rounds}
    (out / 'summary.json').write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'rounds'}))
    if stop == 'pair_error':
        raise SystemExit(2)


if __name__ == '__main__':
    main()
