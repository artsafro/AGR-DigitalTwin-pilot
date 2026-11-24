"""Standing #58: replay the historical renderer; reduce only its paired pixel output."""
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

DRIVE = Path('G:/Мой диск/AGR-evidence')
BLENDER = Path('C:/Program Files/Blender Foundation/Blender 5.1/blender.exe')
RENDER_REV = 'a1f41ee216ba881ada1d1460e6b67f048446e14e'
SPECS = {'v007': '5febf7cda4d0155a27f51d615333997392d085eb',
         'v010': '543652498f34756feef1a729a364c569b3dc8663'}
ZIPS = {'v007': ('271ee11bf78200ef883814a4ac108ef289098d0f106da01e8d9fc57da888c295',
                 '0d1fa6c036bb553459dd0e9baec8be4ace8bc61d5acea6aab585d713f2292d0f'),
        'v010': ('2fe983791566477e297aeefa09f04a1b7d176312c3fce1a8c9f1cf26138013bb',
                 '8f0cb8b7e922850eab15198d0bd40cf2ca1e2bfed12e9c4912173b4aef565ab3')}
VIEWS = ('south', 'east', 'north', 'west')
FILES = ('SM_Nku_1.zip', '0000_Nku_1.zip')


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def stage(path, version):
    path.mkdir()
    for zipname, expected in zip(FILES, ZIPS[version], strict=True):
        source = DRIVE / f'559-tec26-oks-ac08-pilot-{version}' / zipname
        with zipfile.ZipFile(source) as z:
            main = 'SM_Nku_1.fbx' if zipname == FILES[0] else '0000_Nku_1_01.fbx'
            files = z.namelist()
            if files.count(main) != 1 or len(files) != len(set(files)):
                raise ValueError((source, files))
            for member in files:
                if member != main and not (zipname == FILES[0] and re.fullmatch(
                        r'T_Nku_1_(Diffuse|ERM|Normal)_1\.10[0-9][0-9]\.png', member)):
                    raise ValueError((source, member))
                (path / member).write_bytes(z.read(member))
        if sha(source) != expected:
            raise ValueError(f'archive changed: {source}')
    spec = f'{SPECS[version]}:jobs/TEC26-OKS/AC08/vpm_textures.json'
    (path / 'spec.json').write_bytes(subprocess.check_output(['git', 'show', spec]))
    return {p.name: sha(p) for p in sorted(path.iterdir())}


def rgba(path):
    with Image.open(path) as im:
        if im.mode != 'RGBA':
            raise ValueError((path, im.mode))
        return np.asarray(im)


def red(rgb):
    return (rgb[..., 0] > 200) & (rgb[..., 1] < 30) & (rgb[..., 2] < 30)


def score(folder, camera_ref):
    meta = json.loads((folder / 'renders.json').read_bytes())
    hist = np.zeros(766, dtype=np.int64)
    rows = {}
    positive = 0
    for view in VIEWS:
        cameras = [(m['bbox'], {k: val for k, val in m['views'][view].items() if k != 'png'})
                   for m in (meta['vpm'], meta['npm'])]
        ref = camera_ref.setdefault(view, cameras[0])
        if any(c != ref for c in cameras):
            raise ValueError(f'camera mismatch {view}: {cameras!r} != {ref!r}')
        a, b = (rgba(folder / f'{p}_{view}.png') for p in ('vpm', 'npm'))
        if a.shape != b.shape or list(a.shape[:2][::-1]) != ref[1]['res']:
            raise ValueError(f'render dimensions mismatch {view}')
        v, n = a[..., 3] == 255, b[..., 3] == 255
        both = v & n
        coverage = int(both.sum()) / max(1, int((v | n).sum()))
        av, bv = a[..., :3], b[..., :3]
        mask = both & ~red(av) & ~red(bv)
        if coverage < 0.99 or not mask.any():
            raise ValueError(f'coverage refusal {view}: {coverage}, mask={mask.sum()}')
        x, y = av[mask].astype(np.int16), bv[mask].astype(np.int16)
        errors = np.abs(x - y).sum(axis=1)
        hist += np.bincount(errors, minlength=766)
        worst = np.where(x < 128, 255, 0)
        positive += int(np.abs(x - worst).sum())
        changed_pos = int(np.any(worst != y, axis=1).sum())
        masked_npm = bv.copy()
        masked_npm[~mask] = 17
        changed_neg = int(np.any(masked_npm != bv, axis=2).sum())
        if not np.array_equal(masked_npm[mask], bv[mask]) or not min(changed_pos, changed_neg):
            raise ValueError(f'negative parity or trigger not exercised: {view}')
        rows[view] = dict(opaque_jaccard=coverage, pixels=int(mask.sum()),
                          changed_clean=0, changed_injected=changed_pos, changed_outside=changed_neg,
                          sha256={p: sha(folder / f'{p}_{view}.png') for p in ('vpm', 'npm')})
    denominator = int(hist.sum()) * 765
    mean = float(hist @ np.arange(766)) / denominator
    injected = positive / denominator
    if injected - mean < 0.10:
        raise ValueError('positive trigger bound')
    return dict(mean=mean, p95=int(np.searchsorted(hist.cumsum(), hist.sum() * .95)) / 765,
                injected_mean=injected, outside_delta=0.0, views=rows)


def run(out):
    out.mkdir(parents=True)
    start = time.monotonic()
    receipt = {'pairs': [], 'attempts': [], 'cameras': {}, 'status': 'running', 'hypothesis': 'inconclusive'}
    originals = {DRIVE / f'559-tec26-oks-ac08-pilot-{v}' / name: digest
                 for v in ZIPS for name, digest in zip(FILES, ZIPS[v], strict=True)}
    def check_originals():
        return all(sha(p) == digest for p, digest in originals.items())
    try:
        if not check_originals():
            raise ValueError('archive preflight mismatch')
        version = subprocess.check_output([str(BLENDER), '--version'], text=True)
        if 'Blender 5.1.2' not in version or 'ec6e62d40fa9' not in version:
            raise ValueError('Blender build mismatch')
        receipt['blender'] = version.splitlines()[0] + ' ec6e62d40fa9'
        receipt['blender_exe_sha256'] = sha(BLENDER)
        receipt['reducer_sha256'] = sha(Path(__file__))
        receipt['archives'] = {str(p): h for p, h in originals.items()}
        receipt['code'] = {}
        for name in ('render_facades.py', 'vpm_uv.py'):
            blob = f'{RENDER_REV}:jobs/TEC26-OKS/scripts/{name}'
            (out / name).write_bytes(subprocess.check_output(['git', 'show', blob]))
            receipt['code'][blob] = sha(out / name)
        for i in range(1, 4):
            begin = time.monotonic()
            pair = {'round': i}
            for v in SPECS:
                folder = out / f'r{i}-{v}'
                inputs = folder / 'inputs'
                folder.mkdir()
                tmp = folder / 'temp'
                tmp.mkdir()
                hashes = stage(inputs, v)
                renders = folder / 'renders'
                argv = [str(BLENDER), '--background', '--factory-startup', '--disable-autoexec',
                        '--threads', '1', '--python-exit-code', '1', '--python', str(out / 'render_facades.py'), '--',
                        str(inputs / 'spec.json'), str(inputs / 'SM_Nku_1.fbx'), str(inputs),
                        str(inputs / '0000_Nku_1_01.fbx'), str(renders)]
                case = dict(round=i, version=v, inputs=hashes, argv=argv, status='started')
                receipt['attempts'].append(case)
                case_start = time.monotonic()
                with (folder / 'blender.log').open('wb') as log:
                    done = subprocess.run(argv, env=os.environ | {k: str(tmp) for k in ('TEMP', 'TMP', 'TMPDIR')} |
                                          {'PX_PER_M': '400'}, stdout=log, stderr=subprocess.STDOUT,
                                          timeout=max(1, 270 - (time.monotonic() - start)))
                case.update(exit=done.returncode, wall_seconds=time.monotonic() - case_start)
                done.check_returncode()
                if {p.name: sha(p) for p in inputs.iterdir()} != hashes:
                    raise ValueError('staged operand parity failure')
                pair[v] = score(renders, receipt['cameras'])
                case['status'] = 'scored'
            pair['delta'] = pair['v007']['mean'] - pair['v010']['mean']
            pair['wall_seconds'] = time.monotonic() - begin
            receipt['pairs'].append(pair)
            if i == 1 and (pair['wall_seconds'] > 90 or
                           270 - (time.monotonic() - start) < 2 * pair['wall_seconds'] + 15):
                receipt['status'] = 'budget_stop'
                break
        if len(receipt['pairs']) == 3:
            ds = [pair['delta'] for pair in receipt['pairs']]
            median, spread = statistics.median(ds), max(ds) - min(ds)
            receipt.update(status='completed', median_delta=median, paired_spread=spread)
            if spread <= 0.0005:
                receipt['hypothesis'] = 'confirmed' if median >= 0.002 and min(ds) > 0 else 'refuted'
    except (ValueError, OSError, subprocess.SubprocessError) as err:
        receipt.update(status='timeout' if isinstance(err, subprocess.TimeoutExpired) else 'refused', error=str(err))
    finally:
        receipt['originals_match_after'] = check_originals()
        receipt['wall_seconds'] = time.monotonic() - start
        if not receipt['originals_match_after']:
            receipt.update(status='input_parity_failure', hypothesis='inconclusive')
        (out / 'receipt.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print({k: v for k, v in receipt.items() if k in ('status', 'hypothesis', 'median_delta', 'paired_spread', 'error', 'wall_seconds')})
    return 0 if receipt['status'] == 'completed' else 1


if __name__ == '__main__':
    sys.exit(run(Path(sys.argv[1]).resolve()))
