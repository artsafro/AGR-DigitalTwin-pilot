"""#63: fresh native rerenders; #62 staging/oracle, signed shift grid on v010, v007 clean as rejected label."""
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
R62 = '75257229cb561c64bace8250f632c13bc4d694af'
R62_DIR = 'docs/research/atlas-native-phase-r62/'
TOTAL, FIRST = 600, 180
HOOK = b'    if tag == "vpm":\n'
INJECT = b'''    if tag == "npm":
        from phase63 import mutate
        mutate(meshes, os.environ["ATLAS_LAYOUT"], float(os.environ["SHIFT_PX"]), os.environ["UV_RECEIPT"])
'''


def state_name(px):
    return 'clean' if px == 0 else f"{'p' if px > 0 else 'm'}{abs(px):g}"


def run(out):
    out.mkdir(parents=True)
    start = time.monotonic()
    report = dict(status='running', hypothesis='inconclusive', rounds=[], attempts=[])
    archives, originals = {}, {}
    try:
        r62 = None
        raw = subprocess.check_output(['git', 'show', f'{R62}:{R62_DIR}replay.py'])
        (out / 'r62_replay.py').write_bytes(raw)
        spec62 = importlib.util.spec_from_file_location('r62_replay', out / 'r62_replay.py')
        r62 = importlib.util.module_from_spec(spec62)
        spec62.loader.exec_module(r62)
        if r62.BLENDER_SHA != '1e6624af112b3c936f4b038b025ebd2bf00ae72c4b62881a6787166d71c58fa5':
            raise ValueError('#62 pin drift')
        r61 = r62.load(r62.stage_git(out, r62.R61, 'docs/research/atlas-joint-oracle-r61/replay.py', 'r61_replay.py'))
        r58 = r61.load_r58(out)
        r62.stage_git(out, R62, R62_DIR + 'phase.py', 'phase.py')
        shutil.copyfile(HERE / 'phase63.py', out / 'phase63.py')
        sys.path.insert(0, str(out))
        import phase63
        archives = {r58.DRIVE / f'559-tec26-oks-ac08-pilot-{v}' / name: digest
                    for v, hashes in r58.ZIPS.items() for name, digest in zip(r58.FILES, hashes, strict=True)}
        originals = archives | {r61.SLIDE: r61.SLIDE_SHA, r58.BLENDER: r62.BLENDER_SHA}
        if any(r58.sha(p) != h for p, h in originals.items()):
            raise ValueError('full input hash preflight failed')
        report['originals'] = {str(p): h for p, h in originals.items()}
        code = out / 'code'
        staged = [r62.stage_git(code, r61.ORACLE_REV, rel) for rel in r61.CODE]
        rb_script = code / r61.CODE[3]
        sys.path.insert(0, str(rb_script.parent))
        cf, jc = (importlib.import_module(n) for n in ('compare_facades', 'joint_count'))
        ref = 'jobs/TEC26-OKS/AC08/'
        spec = r62.stage_git(out, r61.ORACLE_REV, ref + 'vpm_textures.json', 'oracle_spec.json')
        spec_data = r62.read_json(spec)
        slide = out / 'slide49.png'
        shutil.copyfile(r61.SLIDE, slide)
        spec_data['presentation']['image'] = slide.as_posix()
        spec.write_text(json.dumps(spec_data, ensure_ascii=False), encoding='utf-8')
        sheet = r62.stage_git(out, r61.ORACLE_REV, ref + 'sheet-facades.json', 'sheet.json')
        layouts = {v: r62.stage_git(out, rev, ref + f'pilot-{v}/npm_atlas.json', f'layout-{v}.json')
                   for v, rev in r58.SPECS.items()}
        render, vpm_uv = [r62.stage_git(out, r58.RENDER_REV, 'jobs/TEC26-OKS/scripts/' + n, n)
                          for n in ('render_facades.py', 'vpm_uv.py')]
        probe = out / 'render_probe.py'
        raw = render.read_bytes()
        if raw.count(HOOK) != 1:
            raise ValueError('renderer import hook drift')
        probe.write_bytes(raw.replace(HOOK, INJECT + HOOK))
        pinned = staged + [spec, sheet, slide, render, probe, vpm_uv, out / 'phase.py', out / 'phase63.py',
                           out / 'r62_replay.py', out / 'r61_replay.py', out / 'r58_replay.py',
                           *layouts.values(), Path(__file__)]
        frozen = {p: r58.sha(p) for p in pinned}
        report['code_and_oracle'] = {str(p.relative_to(out) if p.is_relative_to(out) else p.name): h
                                     for p, h in frozen.items()}
        plan = {'v007': (0.0,), 'v010': (0.0, *phase63.GRID)}
        report['plan'] = {v: list(s) for v, s in plan.items()}
        cameras, repeats = {}, {}

        def blender(script, args, folder, **env):
            folder.mkdir()
            with (folder / 'blender.log').open('wb') as log:
                subprocess.run([str(r58.BLENDER), '--background', '--factory-startup', '--disable-autoexec',
                                '--threads', '1', '--python-exit-code', '1', '--python', str(script), '--',
                                *map(str, args)], stdout=log, stderr=subprocess.STDOUT, check=True,
                               env=os.environ | dict(PX_PER_M='400', TEMP=str(folder), TMP=str(folder),
                                                      TMPDIR=str(folder)) | env,
                               timeout=max(1, TOTAL - (time.monotonic() - start)))

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
                for px in plan[v]:
                    name = state_name(px)
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
                    meta = r62.read_json(renders / 'renders.json')
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
                            repeat_count = int(np.any(r58.rgba(prior) != img, axis=2).sum())
                            if prof == 'vpm' and repeat_count:
                                raise ValueError(f'VPM round repeat drift: {v}/{view}')
                            pixels[view][prof] = dict(changed_rgb=count, changed_rgba_vs_round1=repeat_count,
                                                      sha256=r58.sha(file))
                    score = r61.score_version(code, cf, jc, spec, sheet, rb, renders, folder / 'compare')
                    if score['compare_exit'] not in (0, 1) or any(
                            f['slide_joints'] != f['contract_joints'] for f in score['facades'].values()):
                        raise ValueError(f'checker/slide contract mismatch: {v}/{name}')
                    rnd[v][name] = dict(shift_px=px, JE=score['JE'], JE_vpm=score['JE_vpm'],
                                        compare_exit=score['compare_exit'], views=pixels, facades=score['facades'],
                                        uv=r62.read_json(uv) if px else None)
                    case['status'] = 'scored'
            je = {px: rnd['v010'][state_name(px)]['JE'] for px in phase63.GRID}
            rnd['JE_v010'] = {state_name(px): n for px, n in je.items()}
            lim = phase63.limit(je)
            rnd['L63'] = None if math.isinf(lim) else lim
            rnd['verdict'] = phase63.verdict(je, rnd['v007']['clean']['JE'], rnd['v010']['clean']['JE'])
            rnd['seconds'] = time.monotonic() - tick
            report['rounds'].append(rnd)
            print(f"Round {i}: L63={rnd['L63']} JE={rnd['JE_v010']} wall={rnd['seconds']:.3f}s", flush=True)
            if i == 1 and (rnd['seconds'] > FIRST or TOTAL - (time.monotonic() - start) < 2 * rnd['seconds'] + 15):
                report['status'] = 'budget_stop'
                break
        if len(report['rounds']) == 3:
            rows = report['rounds']
            stable = all(r['JE_v010'] == rows[0]['JE_v010'] and
                         r['v007']['clean']['JE'] == rows[0]['v007']['clean']['JE'] for r in rows)
            witness = all(r['JE_v010']['p5'] == 320 for r in rows)
            limits = [math.inf if r['L63'] is None else r['L63'] for r in rows]
            med = statistics.median(limits)
            verdicts = {r['verdict'] for r in rows}
            report.update(status='completed', median_L63=None if math.isinf(med) else med,
                          stable=stable, witness_p5_320=witness,
                          hypothesis=verdicts.pop() if stable and witness and len(verdicts) == 1 else 'inconclusive')
        report['cameras'] = cameras
        if any(r58.sha(p) != h for p, h in frozen.items()):
            raise ValueError('code/oracle input changed during run')
    except Exception as err:
        report.update(status='timeout' if isinstance(err, subprocess.TimeoutExpired) else 'refused',
                      hypothesis='inconclusive', error=f'{type(err).__name__}: {err}')
    finally:
        try:
            unchanged = bool(archives) and all(r58.sha(p) == h for p, h in originals.items())
        except (OSError, NameError):
            unchanged = False
        report.update(originals_match_after=unchanged, seconds=time.monotonic() - start)
        if not unchanged and report['status'] == 'completed':
            report.update(status='input_parity_failure', hypothesis='inconclusive')
        (out / 'receipt.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print({k: report[k] for k in ('status', 'hypothesis', 'median_L63', 'error', 'seconds') if k in report},
              flush=True)
    return 0 if report['status'] == 'completed' else 1


if __name__ == '__main__':
    sys.exit(run(Path(sys.argv[1]).resolve()))
