"""new-case: AGR Tools 0.2.0 UV nudge and UDIM->NPM atlas button seams.

Pattern: new-case. Probes the guarantees for the two new buttons: bundled
uv_nudge parity, atlas UV parity within 1e-6, fail-closed inputs, distinct
paths, and no silent default for an unmapped material.
"""
import ast
import importlib.util
import json
import math
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'adapters/max/agr_tools'
RUNTIME = PACKAGE / 'runtime.py'
ATLAS_CORE = PACKAGE / 'atlas_core.py'
BUILDER = ROOT / 'tools/max/build_agr_tools.py'


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _quad(u0, v0, w=0.5, h=0.5):
    return [(u0, v0), (u0 + w, v0), (u0 + w, v0 + h), (u0, v0 + h)]


def test_version_macros_and_roadmap_text():
    runtime = RUNTIME.read_text(encoding='utf-8')
    mcr = (PACKAGE / 'agr_tools.mcr').read_text(encoding='utf-8')
    readme = (PACKAGE / 'README.md').read_text(encoding='utf-8')
    startup = (PACKAGE / 'startup.ms').read_text(encoding='utf-8')
    install = (PACKAGE / 'install.ms').read_text(encoding='utf-8')
    assert 'VERSION = "0.2.0"' in runtime
    assert '0.002' in runtime and '0.005' in runtime
    for name in ('AGRToolsNudge', 'AGRToolsNudgeApply', 'AGRToolsAtlas', 'AGRToolsAtlasApply'):
        assert name in mcr
    assert '0.2.0' in startup and 'Nudge' in startup and 'Atlas' in startup
    assert 'AGRTools-0.2.0' in install
    assert 'UV integer-tile nudge' in readme and 'UDIM -> NPM atlas' in readme
    assert 'collision generator' in readme.lower()
    assert 'texel' in readme.lower() and 'checked export' in readme.lower()
    assert 'unsupported map coordinate:' in readme
    assert 'map channel 1' in readme


def test_runtime_parser_accepts_nudge_plan_and_rejects_threshold_pass():
    mod = _load(RUNTIME, 'agr_runtime_uv')
    assert hasattr(mod, 'assert_uv_close'), 'readback tolerance helper missing'
    report = {
        'schema': 1, 'tool': 'nudge', 'status': 'fail',
        'objects': [{'handle': 3, 'name': 'planted', 'findings': [
            {'code': 'tile_move', 'ids': [1], 'detail': '{"steps":[-3,2]}'}]}],
        'plan': {'islands': [{'faces': [1], 'steps': [-3, 2], 'shift': [-3.0, 2.0],
                              'materials': ['brick'], 'reason': 'repeating'}],
                 'dropped': []}}
    assert mod.parse_report(json.dumps(report)) == report
    report['status'] = 'pass'
    with pytest.raises(ValueError):
        mod.parse_report(json.dumps(report))
    report['status'] = 'not_run'
    with pytest.raises(ValueError):
        mod.parse_report(json.dumps(report))
    # Exactly the readback tolerance is an error, never a clean pass.
    with pytest.raises(ValueError, match='threshold'):
        mod.assert_uv_close((0.0, 0.0), (1e-6, 0.0))
    mod.assert_uv_close((0.2, 0.2), (0.2, 0.2 + 1e-9))
    with pytest.raises(ValueError):
        mod.assert_uv_close((0.0, 0.0), (1e-5, 0.0))


def test_nudge_slice_matches_library_and_covers_every_face(tmp_path):
    builder = _load(BUILDER, 'agr_builder_uv')
    out = tmp_path / 'tools.mzp'
    builder.build(out)
    import zipfile
    with zipfile.ZipFile(out) as z:
        source = z.read('agr_tools/uv_nudge_core.py')
        assert b'GridUV' not in source and b'layoutFacesOnGrid' not in source
        ns = {}
        exec(source, ns)
    from dt_ai.geometry.uv_nudge import nudge_repeating_islands
    uv = _quad(3.2, -1.8)
    faces = [[0, 1, 2, 3]]
    got = ns['nudge_repeating_islands'](uv, faces, ['brick'], {'brick': (1.0, 1.0)})
    exp = nudge_repeating_islands(uv, faces, ['brick'], {'brick': (1.0, 1.0)})
    assert got.uv == exp.uv
    assert got.islands[0]['steps'] == exp.islands[0]['steps'] == (-3, 2)
    assert uv == _quad(3.2, -1.8)
    rng = random.Random(722)
    matched = 0
    for _ in range(40):
        u0, v0 = rng.uniform(-8, 8), rng.uniform(-8, 8)
        tile = rng.choice([1001, 1002, 1011])
        period = rng.choice([(1.0, 1.0), (0.5, 0.25), None])
        sample = _quad(u0, v0, 0.2, 0.15)
        mats = {'m': period}
        try:
            a = ns['nudge_repeating_islands'](sample, [[0, 1, 2, 3]], ['m'], mats, target_tile=tile)
            b = nudge_repeating_islands(sample, [[0, 1, 2, 3]], ['m'], mats, target_tile=tile)
        except ValueError as exc:
            with pytest.raises(ValueError):
                nudge_repeating_islands(sample, [[0, 1, 2, 3]], ['m'], mats, target_tile=tile)
            assert 'precision' in str(exc) or 'period' in str(exc) or 'finite' in str(exc)
            continue
        assert a.uv == b.uv
        assert sorted(f for island in a.islands for f in island['faces']) == [0]
        matched += 1
    assert matched >= 30


def test_nudge_slice_fail_closed_and_names_unmapped_material(tmp_path):
    builder = _load(BUILDER, 'agr_builder_uv_fail')
    out = tmp_path / 'tools.mzp'
    builder.build(out)
    import zipfile
    with zipfile.ZipFile(out) as z:
        ns = {}
        exec(z.read('agr_tools/uv_nudge_core.py'), ns)
    fn = ns['nudge_repeating_islands']
    with pytest.raises(ValueError, match='empty'):
        fn([], [], [], {})
    with pytest.raises(ValueError, match='finite'):
        fn([(0.0, math.nan), (1.0, 0.0), (0.0, 1.0)], [[0, 1, 2]], ['brick'], {'brick': (1, 1)})
    with pytest.raises(ValueError, match='brick'):
        fn(_quad(0, 0), [[0, 1, 2, 3]], ['brick'], {})
    with pytest.raises(ValueError, match='precision'):
        fn([(1e16, 0.0), (1e16 + 4, 0.0), (1e16 + 4, 4.0), (1e16, 4.0)],
           [[0, 1, 2, 3]], ['brick'], {'brick': (0.3, 0.3)})
    before = _quad(0.2, 0.2)
    result = fn(before, [[0, 1, 2, 3]], ['glass'], {'glass': None})
    assert result.uv == before and result.islands[0]['steps'] == (0, 0)


def test_atlas_core_matches_python_tool_and_refuses_the_same_inputs():
    assert ATLAS_CORE.is_file(), 'atlas core missing'
    core = _load(ATLAS_CORE, 'agr_atlas_core')
    na = _load(ROOT / 'tools/materials/npm_atlas_udim.py', 'npm_atlas_udim_parity')
    verts = [(0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 3.0, 0.0), (0.0, 3.0, 0.0),
             (6.0, 0.0, 0.0), (8.0, 0.0, 0.0), (8.0, 2.0, 0.0), (6.0, 2.0, 0.0)]
    uvs = [(0.1, 0.2), (0.8, 0.2), (0.8, 0.7), (0.1, 0.7),
           (1.15, 0.2), (1.85, 0.2), (1.85, 0.7), (1.15, 0.7)]
    faces = [(0, 1, 2, 3), (4, 5, 6, 7)]
    fuv = [(0, 1, 2, 3), (4, 5, 6, 7)]
    fmats = ('Grass', 'Curb')
    mats = {
        'Grass': {'color': (20, 140, 40), 'dissolve': 1.0},
        'Curb': {'color': (150, 150, 155), 'dissolve': 1.0},
    }
    got = core.pack(verts, uvs, faces, fuv, fmats, mats, mode='ground', size=2048, pad=8)
    import numpy as np
    mesh = na.UdimMesh(np.array(verts, float), np.array(uvs, float), faces, fuv, fmats)
    pymats = {name: na.MaterialSource(name=name, color=spec['color'], dissolve=spec['dissolve'])
              for name, spec in mats.items()}
    exp = na.pack(mesh, pymats, mode='ground', size=2048, pad=8)
    assert got['tiles'] == sorted({row['udim'] for row in exp['report']['materials'].values()})
    assert got['tiles'] == [1001, 1002]
    for a, b in zip(got['uvs'], exp['uvs'].tolist()):
        assert a == pytest.approx(b, abs=1e-6)
    assert sorted(got['dropped']) == []
    assert len(got['face_uvs']) == len(faces)
    # One plug material stays in tile 1001, so packing its output UVs is a fixed point.
    one_u = got['uvs']
    # Rebuild a single-material pack from the Grass cell only for the fixed-point probe.
    grass = core.pack(verts[:4], uvs[:4], [faces[0]], [fuv[0]], ('Grass',),
                      {'Grass': mats['Grass']}, mode='ground', size=2048, pad=8)
    again = core.pack(verts[:4], grass['uvs'], [faces[0]], grass['face_uvs'], ('Grass',),
                      {'Grass': mats['Grass']}, mode='ground', size=2048, pad=8)
    for a, b in zip(again['uvs'], grass['uvs']):
        assert a == pytest.approx(b, abs=1e-9)
    assert one_u  # two-tile result is still the parity subject above
    with pytest.raises(core.AtlasError, match='Grass'):
        core.pack(verts, uvs, faces, fuv, fmats, {'Curb': mats['Curb']})
    crossed = [(0.2, 0.2), (1.2, 0.2), (1.2, 0.8), (0.2, 0.8)]
    with pytest.raises(core.AtlasError, match='crosses a UDIM'):
        core.pack(verts[:4], crossed, [faces[0]], [fuv[0]], ('Grass',), {'Grass': mats['Grass']})
    with pytest.raises(core.AtlasError, match='empty|no faces'):
        core.pack([], [], [], [], [], {})
    with pytest.raises(core.AtlasError, match='finite'):
        core.pack([(0.0, math.nan, 0.0), verts[1], verts[2], verts[3]], uvs[:4],
                  [faces[0]], [fuv[0]], ('Grass',), {'Grass': mats['Grass']})
    with pytest.raises(core.AtlasError, match='padding'):
        core.pack(verts, uvs, faces, fuv, fmats, mats, pad=7)
    with pytest.raises(core.AtlasError, match='neither map_Kd nor Kd'):
        core.pack(verts[:4], uvs[:4], [faces[0]], [fuv[0]], ('Grass',), {'Grass': {'dissolve': 1.0}})
    # Shared UV vertex across materials is named, not split silently.
    with pytest.raises(core.AtlasError, match='shared'):
        core.pack(verts[:4], uvs[:4], [faces[0], faces[0]], [fuv[0], fuv[0]],
                  ('Grass', 'Curb'), mats)


def test_atlas_random_probe_matches_pack_or_the_same_error():
    assert ATLAS_CORE.is_file(), 'atlas core missing'
    core = _load(ATLAS_CORE, 'agr_atlas_core_probe')
    na = _load(ROOT / 'tools/materials/npm_atlas_udim.py', 'npm_atlas_udim_probe')
    import numpy as np
    rng = random.Random(722)
    ok = 0
    for i in range(24):
        w, d = rng.uniform(0.4, 6.0), rng.uniform(0.4, 5.0)
        verts = [(0.0, 0.0, 0.0), (w, 0.0, 0.0), (w, d, 0.0), (0.0, d, 0.0)]
        u0, v0 = rng.uniform(0.05, 0.4), rng.uniform(0.05, 0.4)
        uvs = [(u0, v0), (u0 + 0.4, v0), (u0 + 0.4, v0 + 0.3), (u0, v0 + 0.3)]
        color = (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
        mats = {'Flat': {'color': color, 'dissolve': 1.0}}
        got = core.pack(verts, uvs, [(0, 1, 2, 3)], [(0, 1, 2, 3)], ('Flat',), mats)
        mesh = na.UdimMesh(np.array(verts, float), np.array(uvs, float),
                           ((0, 1, 2, 3),), ((0, 1, 2, 3),), ('Flat',))
        exp = na.pack(mesh, {'Flat': na.MaterialSource(name='Flat', color=color)}, mode='ground')
        for a, b in zip(got['uvs'], exp['uvs'].tolist()):
            assert a == pytest.approx(b, abs=1e-6)
        assert got['dropped'] == []
        assert len(got['face_uvs']) == 1
        ok += 1
    assert ok == 24


def test_publish_refuses_input_alias_and_deletes_nothing(tmp_path):
    assert ATLAS_CORE.is_file(), 'atlas core missing'
    core = _load(ATLAS_CORE, 'agr_atlas_core_paths')
    src = tmp_path / 'source.json'
    src.write_text('{"keep":true}', encoding='utf-8')
    before = src.read_bytes()
    with pytest.raises(core.AtlasError, match='input'):
        core.publish_report(src, {'ok': False}, [src])
    assert src.read_bytes() == before
    assert not Path(str(src) + '.partial').exists()
    partial = tmp_path / 'report.json.partial'
    partial.write_text('stale', encoding='utf-8')
    dest = tmp_path / 'report.json'
    with pytest.raises(core.AtlasError):
        core.publish_report(dest, {'ok': True}, [src])
    assert partial.read_text(encoding='utf-8') == 'stale'
    assert not dest.exists()
    # Distinct report path writes the payload and leaves the input bytes intact.
    out = tmp_path / 'out' / 'report.json'
    code_path = tmp_path / 'cli.json'
    written = core.publish_report(out, {'tiles': [1001]}, [src])
    assert written == out and out.is_file() and src.read_bytes() == before
    assert not Path(str(out) + '.partial').exists()
    rc = core.publish_main([str(src), str(src)])
    assert rc != 0 and src.read_bytes() == before and not code_path.exists()


def _tri_quad():
    verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
    uvs = [(0.1, 0.2), (0.8, 0.2), (0.8, 0.7), (0.1, 0.7)]
    faces = [(0, 1, 2), (0, 2, 3)]
    fuv = [(0, 1, 2), (0, 2, 3)]
    return verts, uvs, faces, fuv


def _pack_pair(core, na, spec, path, mode='oks', size=2048, opacity=None):
    import numpy as np
    verts, uvs, faces, fuv = _tri_quad()
    got = core.pack(verts, uvs, faces, fuv, ('Wall', 'Wall'), {'Wall': spec}, mode=mode, size=size, pad=8)
    mesh = na.UdimMesh(np.array(verts, float), np.array(uvs, float), faces, fuv, ('Wall', 'Wall'))
    pymat = na.MaterialSource(name='Wall', diffuse=path, color=spec.get('color'), opacity=opacity,
                              dissolve=spec['dissolve'])
    exp = na.pack(mesh, {'Wall': pymat}, mode=mode, size=size, pad=8)
    return got, exp


def _assert_atlas_match(got, exp, pixel_tol=0):
    assert got['cells'] == exp['cells']
    assert got['kinds']['Wall'] == exp['report']['materials']['Wall']['kind']
    assert len(got['uvs']) == len(exp['uvs'])
    for a, b in zip(got['uvs'], exp['uvs'].tolist()):
        assert a == pytest.approx(b, abs=1e-6)
    diff = max(abs(a - b) for a, b in zip(got['rgb'], exp['rgb'].tobytes()))
    if exp['alpha'] is None:
        assert got['alpha'] is None
    else:
        diff = max(diff, max(abs(a - b) for a, b in zip(got['alpha'], exp['alpha'].tobytes())))
    assert diff <= pixel_tol


def test_textured_quad_atlas_pixels_match_python_and_keep_alpha(tmp_path):
    from PIL import Image
    core = _load(ATLAS_CORE, 'agr_atlas_core_pixels')
    na = _load(ROOT / 'tools/materials/npm_atlas_udim.py', 'npm_atlas_pixels')
    red, blue = (255, 0, 0), (0, 0, 255)
    image = Image.new('RGB', (8, 1))
    image.putdata([red] * 4 + [blue] * 4)
    path = tmp_path / 'red-blue.png'
    image.save(path)
    rgb = [[red, red, red, red, blue, blue, blue, blue]]
    got, exp = _pack_pair(core, na, {'rgb': rgb, 'dissolve': 1.0}, path)
    _assert_atlas_match(got, exp)
    assert got['cells'] == {'Wall': [0, 0, 24, 19]}
    assert got['kinds']['Wall'] == 'texture'
    us = [p[0] for p in got['uvs']]
    assert min(us) == pytest.approx(0.00439453125, abs=1e-12)
    assert max(us) == pytest.approx(0.00712890625, abs=1e-12)
    # The blue source corner must address a blue atlas pixel, not the red end of the 8x1 map.
    size = got['size']
    blue_uv = max(got['uvs'], key=lambda p: p[0])
    x = int(blue_uv[0] * size)
    y = int((1.0 - blue_uv[1]) * size)
    pixel = got['rgb'][(y * size + x) * 3:(y * size + x) * 3 + 3]
    assert pixel[2] > pixel[0]
    red_uv = min(got['uvs'], key=lambda p: p[0])
    x = int(red_uv[0] * size)
    y = int((1.0 - red_uv[1]) * size)
    pixel = got['rgb'][(y * size + x) * 3:(y * size + x) * 3 + 3]
    assert pixel == b'\xff\x00\x00'
    alpha = [0, 0, 0, 0, 255, 255, 255, 255]
    white = Image.new('RGBA', (8, 1))
    white.putdata([(255, 255, 255, a) for a in alpha])
    white_path = tmp_path / 'white-alpha.png'
    white.save(white_path)
    spec = {'rgb': [[(255, 255, 255)] * 8], 'alpha': [alpha], 'dissolve': 1.0}
    got_a, exp_a = _pack_pair(core, na, spec, white_path)
    _assert_atlas_match(got_a, exp_a)
    assert got_a['kinds']['Wall'] == 'texture'
    assert got_a['alpha'] is not None
    # Dropping alpha classifies the same white bitmap as a flat plug and moves U by more than 1e-6.
    verts, uvs, faces, fuv = _tri_quad()
    dropped = core.pack(verts, uvs, faces, fuv, ('Wall', 'Wall'),
                        {'Wall': {'rgb': [[(255, 255, 255)] * 8], 'dissolve': 1.0}},
                        mode='oks', size=2048, pad=8)
    assert dropped['kinds']['Wall'] == 'plug'
    assert dropped['cells']['Wall'] == [0, 0, 40, 20]
    assert max(p[0] for p in dropped['uvs']) - max(p[0] for p in got_a['uvs']) == pytest.approx(0.007845052083333332, abs=1e-12)


def test_opacity_without_diffuse_is_rejected_and_random_bitmaps_match(tmp_path):
    from PIL import Image
    core = _load(ATLAS_CORE, 'agr_atlas_core_opacity')
    na = _load(ROOT / 'tools/materials/npm_atlas_udim.py', 'npm_atlas_opacity')
    verts, uvs, faces, fuv = _tri_quad()
    with pytest.raises(core.AtlasError, match='map_d without map_Kd is not supported'):
        core.pack(verts, uvs, faces, fuv, ('Wall', 'Wall'),
                  {'Wall': {'color': (20, 140, 40), 'opacity': [[255] * 8], 'dissolve': 1.0}},
                  mode='oks', size=2048, pad=8)
    with pytest.raises(core.AtlasError, match='both diffuse alpha and map_d opacity'):
        core.pack(verts, uvs, faces, fuv, ('Wall', 'Wall'),
                  {'Wall': {'rgb': [[(255, 0, 0)] * 4 + [(0, 0, 255)] * 4],
                            'alpha': [[0, 0, 0, 0, 255, 255, 255, 255]],
                            'opacity': [[255] * 8], 'dissolve': 1.0}},
                  mode='oks', size=2048, pad=8)
    rng = random.Random(722)
    matched = 0
    for i in range(12):
        w, h = rng.randint(1, 12), rng.randint(1, 9)
        rgb = [[(rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255)) for _ in range(w)] for _ in range(h)]
        alpha = [[rng.choice([0, 255, rng.randint(0, 255)]) for _ in range(w)] for _ in range(h)]
        mode = Image.new('RGBA', (w, h))
        mode.putdata([(px[0], px[1], px[2], a) for row, arow in zip(rgb, alpha) for px, a in zip(row, arow)])
        path = tmp_path / f'rand-{i}.png'
        mode.save(path)
        spec = {'rgb': rgb, 'dissolve': 1.0}
        if any(a < 255 for row in alpha for a in row):
            spec['alpha'] = alpha
        got, exp = _pack_pair(core, na, spec, path)
        # Layout is exact. Lanczos fixed-point in PIL can differ by one level; appearance stays.
        _assert_atlas_match(got, exp, pixel_tol=1)
        matched += 1
    for i in range(8):
        w, h = rng.randint(2, 10), rng.randint(1, 6)
        rgb = [[(rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255)) for _ in range(w)] for _ in range(h)]
        opacity = [[rng.randint(0, 255) for _ in range(w)] for _ in range(h)]
        diffuse = Image.new('RGB', (w, h))
        diffuse.putdata([px for row in rgb for px in row])
        grey = Image.new('L', (w, h))
        grey.putdata([v for row in opacity for v in row])
        diffuse_path = tmp_path / f'd-{i}.png'
        opacity_path = tmp_path / f'o-{i}.png'
        diffuse.save(diffuse_path)
        grey.save(opacity_path)
        spec = {'rgb': rgb, 'opacity': opacity, 'dissolve': 1.0}
        got = core.pack(verts, uvs, faces, fuv, ('Wall', 'Wall'), {'Wall': spec}, mode='oks', size=2048, pad=8)
        import numpy as np
        mesh = na.UdimMesh(np.array(verts, float), np.array(uvs, float), faces, fuv, ('Wall', 'Wall'))
        exp = na.pack(mesh, {'Wall': na.MaterialSource(name='Wall', diffuse=diffuse_path, opacity=opacity_path)},
                      mode='oks', size=2048, pad=8)
        _assert_atlas_match(got, exp, pixel_tol=1)
        matched += 1
    assert matched == 20


def test_bitmap_rows_read_each_scanline():
    runtime = _load(RUNTIME, 'agr_runtime_bitmap_rows')
    rng = random.Random(722)
    matched = 0
    for _ in range(32):
        width, height = rng.randint(1, 24), rng.randint(1, 16)
        buf = [[(rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
                for _ in range(width)] for _ in range(height)]

        def read_span(x, y, count, buf=buf, width=width):
            # A request longer than the row stops at the scanline, the same limit as Max getPixels.
            return buf[y][x:x + min(count, width - x)]

        if height > 1:
            assert len(read_span(0, 0, width * height)) == width
        rgb, alpha = runtime.bitmap_rows(width, height, read_span)
        assert rgb == [[px[:3] for px in row] for row in buf]
        assert alpha == [[px[3] for px in row] for row in buf]
        with pytest.raises(ValueError, match='partial material bitmap'):
            runtime.bitmap_rows(width, height, lambda x, y, count: read_span(x, y, count)[:0])
        matched += 1
    assert matched == 32


def test_map_coordinate_contract_probe():
    """Neutral bitmap coordinates pass. Every other setting value, including NaN, is named."""
    import math
    runtime = _load(RUNTIME, 'agr_runtime_map_coordinates')
    neutral = {name: expected for name, expected, _kind in runtime.NEUTRAL_MAP_COORDINATES}
    accepted = 0
    rejected = 0

    def accept(slot, values):
        nonlocal accepted
        runtime.assert_neutral_map_coordinates('Witness', slot, values)
        accepted += 1

    def reject(slot, values, setting):
        nonlocal rejected
        with pytest.raises(ValueError, match='unsupported map coordinate: Witness ' + slot + ' ' + setting + '='):
            runtime.assert_neutral_map_coordinates('Witness', slot, values)
        rejected += 1

    accept('diffuse', dict(neutral))
    for name, expected, kind in runtime.NEUTRAL_MAP_COORDINATES:
        if kind != 'float':
            continue
        inside = expected
        delta = 1e-9
        for _ in range(8):
            candidate = expected + delta
            if abs(candidate - expected) <= 1e-9:
                inside = candidate
                break
            delta *= 0.5
        trial = dict(neutral)
        trial[name] = inside
        accept('diffuse', trial)
        trial = dict(neutral)
        trial[name] = expected - abs(inside - expected)
        accept('opacity', trial)
    # The combined witness: U tiling 2 is the named error, not a neutral atlas.
    witness = dict(neutral)
    witness['U_Tiling'] = 2
    with pytest.raises(ValueError, match=r'^unsupported map coordinate: Witness diffuse U_Tiling=2$'):
        runtime.assert_neutral_map_coordinates('Witness', 'diffuse', witness)
    rejected += 1
    for name, expected, kind in runtime.NEUTRAL_MAP_COORDINATES:
        if kind == 'float':
            outside = expected + 1e-6
            delta = 1e-9
            for _ in range(8):
                candidate = expected + delta
                if abs(float(candidate) - float(expected)) > 1e-9:
                    outside = candidate
                    break
                delta *= 2.0
            values = (expected + 2.0, expected - 3.0, outside, math.nan, math.inf, -math.inf)
        elif kind == 'bool':
            values = (not expected,)
        else:
            values = tuple(v for v in (0, 2, -5, 1001) if v != expected)
        for value in values:
            trial = dict(neutral)
            trial[name] = value
            reject('diffuse', trial, name)
        missing = dict(neutral)
        del missing[name]
        reject('opacity', missing, name)
    with pytest.raises(ValueError, match=r'^unsupported map coordinate: Witness diffuse coords=unreadable$'):
        runtime.assert_neutral_map_coordinates('Witness', 'diffuse', None)
    rejected += 1
    assert accepted == 15 and rejected == 64, (accepted, rejected)


def test_shipped_archive_contains_atlas_core_text(tmp_path):
    assert ATLAS_CORE.is_file(), 'atlas core missing'
    builder = _load(BUILDER, 'agr_builder_atlas_ship')
    out = tmp_path / 'ship.mzp'
    other = tmp_path / 'ship2.mzp'
    builder.build(out)
    builder.build(other)
    assert out.read_bytes() == other.read_bytes()
    import zipfile
    with zipfile.ZipFile(out) as z:
        shipped = z.read('agr_tools/atlas_core.py').replace(b'\r\n', b'\n')
    assert shipped == ATLAS_CORE.read_bytes().replace(b'\r\n', b'\n')
    tree = ast.parse(shipped)
    doc = ast.get_docstring(tree)
    assert doc and 'new-case' in doc
