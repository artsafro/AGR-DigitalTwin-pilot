"""#62: fresh native rerenders using pinned #58 staging and #61 oracle."""
import importlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
R61 = 'd45346548e06847167b386c2c0c71b50ccdfb18e'
BLENDER_SHA = '1e6624af112b3c936f4b038b025ebd2bf00ae72c4b62881a6787166d71c58fa5'
HOOK = b'    if tag == "vpm":\n'
INJECT = b'''    if tag == "npm":
        from phase import mutate
        mutate(meshes, os.environ["ATLAS_LAYOUT"], float(os.environ["SHIFT_PX"]), os.environ["UV_RECEIPT"])
'''


def stage_git(root, rev, rel, name=None):
    path = root / (name or rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(subprocess.check_output(['git', 'show', f'{rev}:{rel}']))
    return path


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path):
    return json.loads(path.read_bytes())


def run(out):
    out.mkdir(parents=True)
    start = time.monotonic()
    report = dict(status='running', hypothesis='inconclusive', rounds=[], attempts=[])
    archives = {}
    r58 = None
    try:
        r61 = load(stage_git(out, R61, 'docs/research/atlas-joint-oracle-r61/replay.py', 'r61_replay.py'))
        r58 = r61.load_r58(out)
        archives = {r58.DRIVE / f'559-tec26-oks-ac08-pilot-{v}' / name: digest
                    for v, hashes in r58.ZIPS.items() for name, digest in zip(r58.FILES, hashes, strict=True)}
        originals = archives | {r61.SLIDE: r61.SLIDE_SHA, r58.BLENDER: BLENDER_SHA}
        if any(r58.sha(p) != h for p, h in originals.items()):
            raise ValueError('full input hash preflight failed')
        report['originals'] = {str(p): h for p, h in originals.items()}
        code = out / 'code'
        staged = [stage_git(code, r61.ORACLE_REV, rel) for rel in r61.CODE]
        rb_script = code / r61.CODE[3]
        sys.path.insert(0, str(rb_script.parent))
        cf, jc = (importlib.import_module(n) for n in ('compare_facades', 'joint_count'))
        ref = 'jobs/TEC26-OKS/AC08/'
        spec = stage_git(out, r61.ORACLE_REV, ref + 'vpm_textures.json', 'oracle_spec.json')
        spec_data = read_json(spec)
        slide = out / 'slide49.png'
        shutil.copyfile(r61.SLIDE, slide)
        spec_data['presentation']['image'] = slide.as_posix()
        spec.write_text(json.dumps(spec_data, ensure_ascii=False), encoding='utf-8')
        sheet = stage_git(out, r61.ORACLE_REV, ref + 'sheet-facades.json', 'sheet.json')
        layouts = {v: stage_git(out, rev, ref + f'pilot-{v}/npm_atlas.json', f'layout-{v}.json')
                   for v, rev in r58.SPECS.items()}
        render, vpm_uv = [stage_git(out, r58.RENDER_REV, 'jobs/TEC26-OKS/scripts/' + n, n)
                          for n in ('render_facades.py', 'vpm_uv.py')]
        probe = out / 'render_probe.py'
        raw = render.read_bytes()
        if raw.count(HOOK) != 1:
            raise ValueError('renderer import hook drift')
        probe.write_bytes(raw.replace(HOOK, INJECT + HOOK))
        shutil.copyfile(HERE / 'phase.py', out / 'phase.py')
        pinned = staged + [spec, sheet, slide, render, probe, vpm_uv, out / 'phase.py', out / 'r61_replay.py',
                           out / 'r58_replay.py', *layouts.values(), Path(__file__)]
        frozen = {p: r58.sha(p) for p in pinned}
        report['code_and_oracle'] = {str(p.relative_to(out) if p.is_relative_to(out) else p.name): h
                                     for p, h in frozen.items()}
        cameras, repeats = {}, {}

        def blender(script, args, folder, **env):
            folder.mkdir()
            with (folder / 'blender.log').open('wb') as log:
                subprocess.run([str(r58.BLENDER), '--background', '--factory-startup', '--disable-autoexec',
                                '--threads', '1', '--python-exit-code', '1', '--python', str(script), '--',
                                *map(str, args)], stdout=log, stderr=subprocess.STDOUT, check=True,
                               env=os.environ | dict(PX_PER_M='400', TEMP=str(folder), TMP=str(folder),
                                                      TMPDIR=str(folder)) | env,
                               timeout=max(1, 360 - (time.monotonic() - start)))

        for i in range(1, 4):
            tick = time.monotonic()
            rnd = dict(round=i)
            stage = {v: out / f'r{i}-{v}-inputs' for v in layouts}
            hashes = {v: r58.stage(p, v) for v, p in stage.items()}
            rb_dir = out / f'r{i}-readback'
            rb = rb_dir / 'vpm.json'
            blender(rb_script, (stage['v010'] / 'SM_Nku_1.fbx', rb), rb_dir)
            rnd['readback_sha256'] = r58.sha(rb)
            rnd['staged_inputs'] = hashes
            for v, p in stage.items():
                rnd[v] = {}
                for name, px in (('clean', 0), ('small', 0.5), ('trigger', 5.0)):
                    case = dict(round=i, label=v, state=name, status='started')
                    report['attempts'].append(case)
                    folder = out / f'r{i}-{v}-{name}'
                    renders = folder / 'renders'
                    uv = folder / 'uv.json'
                    then = time.monotonic()
                    blender(probe if px else render, (p / 'spec.json', p / 'SM_Nku_1.fbx', p,
                                                      p / '0000_Nku_1_01.fbx', renders), folder,
                            ATLAS_LAYOUT=str(layouts[v]), SHIFT_PX=str(px), UV_RECEIPT=str(uv))
                    case.update(status='rendered', seconds=time.monotonic() - then)
                    if {f.name: r58.sha(f) for f in p.iterdir()} != hashes[v]:
                        raise ValueError(f'staged input changed: {v}')
                    meta = read_json(renders / 'renders.json')
                    pixels = {}
                    for view in r58.VIEWS:
                        pixels[view] = {}
                        for prof in ('vpm', 'npm'):
                            info = meta[prof]['views'][view]
                            cam = [meta[prof]['bbox'], {k: x for k, x in info.items() if k != 'png'}]
                            if cameras.setdefault(view, cam) != cam:
                                raise ValueError(f'camera mismatch: {v}/{name}/{prof}/{view}')
                            file = renders / info['png']
                            img = r58.rgba(file)
                            clean = r58.rgba(out / f'r{i}-{v}-clean' / 'renders' / info['png']) if px else img
                            count = r61.changed(clean, img)
                            if not np.array_equal(clean[..., 3], img[..., 3]) or (prof == 'vpm' and count):
                                raise ValueError(f'pixel parity: {v}/{name}/{prof}/{view}')
                            if prof == 'npm' and px and not count:
                                raise ValueError(f'not_exercised: {v}/{name}/{view}')
                            prior = repeats.setdefault((v, name, prof, view), file)
                            repeat = r58.rgba(prior)
                            repeat_count = int(np.any(repeat != img, axis=2).sum())
                            if prof == 'vpm' and repeat_count:
                                raise ValueError(f'VPM round repeat drift: {v}/{view}')
                            pixels[view][prof] = dict(changed_rgb=count, changed_rgba_vs_round1=repeat_count,
                                                      sha256=r58.sha(file))
                    score = r61.score_version(code, cf, jc, spec, sheet, rb, renders, folder / 'compare')
                    if score['compare_exit'] not in (0, 1) or any(
                            f['slide_joints'] != f['contract_joints'] for f in score['facades'].values()):
                        raise ValueError(f'checker/slide contract mismatch: {v}/{name}')
                    rnd[v][name] = dict(JE=score['JE'], JE_vpm=score['JE_vpm'], compare_exit=score['compare_exit'],
                                        views=pixels, facades=score['facades'], uv=read_json(uv) if px else None)
                    case['status'] = 'scored'
            rnd['delta'] = rnd['v010']['trigger']['JE'] - rnd['v010']['clean']['JE']
            rnd['seconds'] = time.monotonic() - tick
            report['rounds'].append(rnd)
            print(f"Round {i}: D={rnd['delta']} wall={rnd['seconds']:.3f}s", flush=True)
            if i == 1 and (rnd['seconds'] > 105 or 360 - (time.monotonic() - start) < 2 * rnd['seconds'] + 15):
                report['status'] = 'budget_stop'
                break
        if len(report['rounds']) == 3:
            ds = [r['delta'] for r in report['rounds']]
            valid = all(r['v007']['clean']['JE'] > r['v010']['clean']['JE'] == 0 and
                        r['v010']['small']['JE'] == 0 for r in report['rounds']) and min(ds) == max(ds)
            report.update(status='completed', median_delta=statistics.median(ds), paired_spread=max(ds) - min(ds),
                          hypothesis=('confirmed' if ds[0] >= 8 else 'refuted') if valid else 'inconclusive')
        report['cameras'] = cameras
        if any(r58.sha(p) != h for p, h in frozen.items()):
            raise ValueError('code/oracle input changed during run')
    except Exception as err:
        report.update(status='timeout' if isinstance(err, subprocess.TimeoutExpired) else 'refused',
                      hypothesis='inconclusive', error=f'{type(err).__name__}: {err}')
    finally:
        try:
            unchanged = bool(archives) and all(r58.sha(p) == h for p, h in originals.items())
        except OSError:
            unchanged = False
        report.update(originals_match_after=unchanged, seconds=time.monotonic() - start)
        if not unchanged and report['status'] == 'completed':
            report.update(status='input_parity_failure', hypothesis='inconclusive')
        (out / 'receipt.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print({k: report[k] for k in ('status', 'hypothesis', 'error', 'seconds') if k in report}, flush=True)
    return 0 if report['status'] == 'completed' else 1


if __name__ == '__main__':
    sys.exit(run(Path(sys.argv[1]).resolve()))
