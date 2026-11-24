"""Replay #58 at its published revision and score fresh renders against v010 VPM."""
import importlib.util
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

PARENT = 'd45e1ea44471de876f577b63a403f1be43c118ec:docs/research/atlas-drift-r58/replay.py'
BLENDER_SHA = '1e6624af112b3c936f4b038b025ebd2bf00ae72c4b62881a6787166d71c58fa5'
LABELS = ('v007', 'v010')
SHIFT = 20


def score_pair(parent, folders):
    pixels = interior_pixels = 0
    totals = {label: dict.fromkeys(('clean', 'unshifted', 'shifted', 'outside'), 0) for label in LABELS}
    views = {}
    controls = []
    for view in parent.VIEWS:
        ref_path = folders['v010'] / f'vpm_{view}.png'
        paths = [folders[label] / f'npm_{view}.png' for label in LABELS]
        ref, *subjects = (parent.rgba(path) for path in (ref_path, *paths))
        if any(image.shape != ref.shape for image in subjects):
            raise ValueError(f'shape mismatch: {view}')
        opaque = [image[..., 3] == 255 for image in (ref, *subjects)]
        common = np.logical_and.reduce(opaque)
        coverage = int(common.sum()) / max(1, int(np.logical_or.reduce(opaque).sum()))
        mask = common & ~np.logical_or.reduce([parent.red(image[..., :3]) for image in (ref, *subjects)])
        inner = mask[:, SHIFT:] & mask[:, :-SHIFT]
        count, inner_count = int(mask.sum()), int(inner.sum())
        if coverage < 0.99 or min(count, inner_count) == 0:
            raise ValueError(f'empty or incomplete coverage: {view}, {coverage}, {count}, {inner_count}')
        pixels += count
        interior_pixels += inner_count
        row = views[view] = dict(mask_pixels=count, interior_pixels=inner_count, opaque_jaccard=coverage,
                                 ref_sha256=parent.sha(ref_path))
        x = ref[..., :3][mask].astype(np.int16)
        xi = ref[:, SHIFT:, :3][inner].astype(np.int16)
        for label, image, path in zip(LABELS, subjects, paths, strict=True):
            rgb = image[..., :3]
            y = rgb[mask].astype(np.int16)
            yi = rgb[:, SHIFT:][inner].astype(np.int16)
            shifted = rgb[:, :-SHIFT][inner].astype(np.int16)
            outside = rgb.copy()
            outside[~mask] = 17
            changed_shift = int(np.any(yi != shifted, axis=1).sum())
            changed_out = int(np.any(outside[~mask] != rgb[~mask], axis=1).sum())
            controls.append(min(changed_shift, changed_out) > 0)
            row[label] = dict(changed_clean=0, changed_shift=changed_shift, changed_outside=changed_out,
                              sha256=parent.sha(path))
            values = totals[label]
            values['clean'] += int(np.abs(x - y).sum())
            values['unshifted'] += int(np.abs(xi - yi).sum())
            values['shifted'] += int(np.abs(xi - shifted).sum())
            values['outside'] += int(np.abs(x - outside[mask].astype(np.int16)).sum())
    scores = {}
    for label, values in totals.items():
        shift_delta = (values['shifted'] - values['unshifted']) / (765 * interior_pixels)
        outside_delta = (values['outside'] - values['clean']) / (765 * pixels)
        scores[label] = dict(clean=values['clean'] / (765 * pixels), shift_delta=shift_delta,
                             outside_delta=outside_delta)
        controls.append(shift_delta >= 0.0005 and outside_delta == 0)
    return dict(scores=scores, views=views, control_pass=all(controls),
                delta=scores['v007']['clean'] - scores['v010']['clean'])


def run(out):
    start = time.monotonic()
    out.mkdir(parents=True)
    receipt = {'hypothesis': 'inconclusive', 'status': 'started', 'pairs': [], 'parent': PARENT}
    try:
        parent_file = out / 'r58_parent.py'
        parent_file.write_bytes(subprocess.check_output(['git', 'show', PARENT]))
        spec = importlib.util.spec_from_file_location('r58_parent', parent_file)
        parent = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(parent)
        receipt.update(parent_sha256=parent.sha(parent_file), reducer_sha256=parent.sha(Path(__file__)),
                       uv_lock_sha256=parent.sha(Path('uv.lock')), blender_sha256=parent.sha(parent.BLENDER))
        if receipt['blender_sha256'] != BLENDER_SHA:
            raise ValueError('Blender executable hash mismatch')
        raw = out / 'native'
        native_exit = parent.run(raw)
        native_file = raw / 'receipt.json'
        native = json.loads(native_file.read_bytes())
        receipt.update(native_status=native['status'], native_receipt_sha256=parent.sha(native_file),
                       native_wall_seconds=native['wall_seconds'], native_attempts=native['attempts'],
                       cameras=native['cameras'], archives=native['archives'], code=native['code'],
                       originals_match_after=native['originals_match_after'])
        if native_exit != 0 or len(native['pairs']) != 3 or not native['originals_match_after']:
            raise ValueError('reused renderer was incomplete or source parity failed')
        scoring_start = time.monotonic()
        for i in range(1, 4):
            pair_start = time.monotonic()
            pair = score_pair(parent, {label: raw / f'r{i}-{label}' / 'renders' for label in LABELS})
            pair.update(round=i, native_pair_seconds=native['pairs'][i-1]['wall_seconds'],
                        reducer_pair_seconds=time.monotonic() - pair_start)
            receipt['pairs'].append(pair)
            if time.monotonic() - scoring_start > 60:
                raise TimeoutError('reducer budget stop')
        ds = [pair['delta'] for pair in receipt['pairs']]
        median, spread = statistics.median(ds), max(ds) - min(ds)
        receipt.update(status='completed', median_delta=median, paired_spread=spread)
        if spread <= 0.0005 and all(pair['control_pass'] for pair in receipt['pairs']):
            receipt['hypothesis'] = 'confirmed' if median >= 0.002 and min(ds) > 0 else 'refuted'
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        receipt.update(status='budget_stop' if isinstance(error, TimeoutError) else 'refused', error=str(error))
    finally:
        receipt['wall_seconds'] = time.monotonic() - start
        (out / 'receipt.json').write_bytes((json.dumps(receipt, indent=2, ensure_ascii=False) + '\n').encode())
        print({k: v for k, v in receipt.items() if k in ('status', 'hypothesis', 'error', 'median_delta',
                                                        'paired_spread', 'wall_seconds')})
    return 0 if receipt['status'] == 'completed' else 1


if __name__ == '__main__':
    sys.exit(run(Path(sys.argv[1]).resolve()))
