"""new-case: AGR Tools 0.9 (#979) branch B: atlas.groundel, atlas.flora and the atlas.npm rework (atlas_core.py).

Defects of #979 §5/§6 and the atlas.npm row of «Доработки» are RED on behaviour models written from the
measurements (no team code, #853):
* GroundEl: A101AGRLP.ms (sha256 86c43d4d…6926) lab L06 job 20261105-125803-b4879f91 — the 512 rule never runs
  from «Find errors», a missing map is skipped silently, any alpha channel is an error;
* Flora: FloraAtlas.ms / Flora Atlas V1.2.mcr (T05, Max 2024/2026) — tile per object, padding 2 px without bleed,
  upscale up to x3, RGBA diffuse;
* VPM_to_NPM.ms (sha256 613925939568…10e8, T06) — 32-bit ARGB, padding 6 px, the atlas is not reduced.
GREEN on atlas_core.
"""
import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'


def _load(name, alias):
    spec = importlib.util.spec_from_file_location(alias, PKG / name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


ac = _load('atlas_core.py', 'agr_tools_atlas_core_t9')
tq = ac.texqa()


def red_green(prop, source, impl):
    assert not prop(source()), 'source model already satisfies the property: not a regression'
    assert prop(impl())


def ctype(png):
    return png[25]


# ---- GroundEl map rule (L06 acceptance) -------------------------------------------------------------------------
def info(w, h, fmt='png', depth=8, alpha_min=None, name='m.png'):
    return {'file': name, 'format': fmt, 'w': w, 'h': h, 'depth': depth, 'alpha_min': alpha_min}


def a101_model(i):
    """Find errors as measured: the handler throws before GroundEl (rule never runs from the button)."""
    return {'ran': False, 'codes': []}


@pytest.mark.parametrize('case,expected', [
    (info(128, 128), []), (info(256, 256), []), (info(512, 512), []), (info(512, 512, 'jpeg'), []),
    (info(513, 513), ['groundel_size']), (info(1024, 1024), ['groundel_size']),
    (info(512, 256), ['groundel_not_square']), (info(64, 64), ['groundel_size']),
    (info(512, 512, alpha_min=128), ['groundel_alpha']), (info(512, 512, alpha_min=255), []),
    (None, ['map_missing']),
])
def test_groundel_512_rule(case, expected):
    got, _ = ac.groundel_map_rule(case)
    assert sorted({c for c, _ in got}) == expected


def test_groundel_rule_runs_and_reports_missing_and_16_bit():
    red_green(lambda r: r['ran'] and r['codes'] == ['groundel_size'],
              lambda: a101_model(info(1024, 1024)),
              lambda: {'ran': True, 'codes': [c for c, _ in ac.groundel_map_rule(info(1024, 1024))[0]]})
    f, w = ac.groundel_map_rule(info(512, 512, depth=16))
    assert f == [] and w and '16 bits' in w[0]


# ---- GroundEl atlas through pack(profile='groundel') ----------------------------------------------------------
def texture(side, seed):
    return tq.Picture(side, side, 3, bytes(v for y in range(side) for x in range(side)
                                           for v in ((x * 7 + seed * 40) % 256, (y * 5 + seed * 20) % 256,
                                                     (x + y + seed * 9) % 256)))


def elements(sides, metres):
    verts, uvs, faces, fuv, fmats, mats = [], [], [], [], [], {}
    for k, (side, m) in enumerate(zip(sides, metres)):
        b = len(verts)
        ox = k * (m + 1.0)
        verts += [(ox, 0, 0), (ox + m, 0, 0), (ox + m, m, 0), (ox, m, 0)]
        uvs += [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        faces.append((b, b + 1, b + 2, b + 3))
        fuv.append((b, b + 1, b + 2, b + 3))
        name = 'GroundEl_{}'.format(k + 1)
        fmats.append(name)
        rows, _ = ac.rows_rgb(texture(side, k))
        mats[name] = {'rgb': rows, 'dissolve': 1.0}
    return verts, uvs, faces, fuv, fmats, mats


def test_six_groundel_elements_one_atlas_at_most_512_rgb24():
    v, u, f, fu, fm, mats = elements((16, 24, 32, 48, 64, 32), (0.4, 0.6, 0.8, 1.0, 1.2, 0.5))
    laid = ac.pack(v, u, f, fu, fm, mats, mode='ground', size=512, pad=8, profile='groundel', shrink=True)
    assert laid['size'] <= 512 and len(laid['cells']) == 6
    diffuse, opacity = ac.atlas_png(laid)
    assert ctype(diffuse) == 2 and opacity is None
    for t in laid['texel_px_per_m'].values():
        assert ac.GROUND_MIN <= t <= ac.GROUND_MAX


def test_groundel_overflow_fails_with_the_calculation_not_a_smaller_texel():
    v, u, f, fu, fm, mats = elements((16,) * 6, (25.0,) * 6)
    with pytest.raises(ac.AtlasFitError) as exc:
        ac.pack(v, u, f, fu, fm, mats, mode='ground', size=512, pad=8, profile='groundel')
    calc = exc.value.calc
    assert calc['atlas_px'] == 512 and calc['cells_area_px2'] > 0 and calc['lowest_texel_px_per_m'] >= ac.GROUND_MIN
    assert len(calc['cells']) == 6
    with pytest.raises(ac.AtlasError):
        ac.pack(v, u, f, fu, fm, mats, mode='ground', size=1024, profile='groundel')


# ---- atlas.npm rework (VPM_to_NPM) ----------------------------------------------------------------------------
def vpm_to_npm_model(size):
    """As measured: the atlas keeps the requested size (not reduced), 32-bit ARGB, padding 6 px."""
    return {'size': size, 'ctype': 6, 'pad': 6}


def test_npm_atlas_is_reduced_at_the_same_texel_and_written_24_bit():
    v, u, f, fu, fm, mats = elements((32, 32, 32), (1.0, 1.0, 1.0))
    big = ac.pack(v, u, f, fu, fm, mats, mode='ground', size=2048, pad=8, profile='npm')
    small = ac.pack(v, u, f, fu, fm, mats, mode='ground', size=2048, pad=8, profile='npm', shrink=True)
    red_green(lambda r: r['size'] < 2048 and r['ctype'] == 2 and r['pad'] >= 8,
              lambda: vpm_to_npm_model(2048),
              lambda: {'size': small['size'], 'ctype': ctype(ac.atlas_png(small)[0]), 'pad': 8})
    assert small['texel_px_per_m'] == big['texel_px_per_m']
    for t in small['texel_px_per_m'].values():
        assert abs(t - 35.0) <= 0.1
    # the 0.2 contract is unchanged without a profile
    assert ac.pack(v, u, f, fu, fm, mats, mode='ground', size=2048, pad=8)['size'] == 2048


# ---- Flora --------------------------------------------------------------------------------------------------
def flora_model(objects, textures):
    """FloraAtlas as measured: one tile per object, padding 2 px, small tiles upscaled to the largest, RGBA."""
    largest = max(t['w'] for t in textures.values())
    return {'tiles': len(objects), 'pad': 2, 'max_scale': largest / min(t['w'] for t in textures.values()),
            'ctype': 6}


def flora_set():
    """T05 set: RGBA leaf (+ an instance), 512x256 RGB + a separate opacity, 128 RGB, Plane+Bend with the leaf."""
    leaf_rgba = bytes(v for y in range(64) for x in range(64) for v in (40, 120 + x % 50, 30, 255 if x < 48 else 0))
    textures = {
        'leaf.png': {'w': 64, 'h': 64, 'rgb': tq.Picture(64, 64, 4, leaf_rgba).rgb(),
                     'alpha': tq.Picture(64, 64, 4, leaf_rgba).alpha()},
        'bark.png': {'w': 128, 'h': 64, 'rgb': bytes((90, 60, 30)) * (128 * 64),
                     'alpha': bytes(255 if y < 50 else 0 for y in range(64) for x in range(128))},
        'grass.png': {'w': 32, 'h': 32, 'rgb': bytes((30, 140, 40)) * 1024, 'alpha': None},
    }
    objects = {'Leaf': 'leaf.png', 'Leaf_inst': 'leaf.png', 'Bark': 'bark.png', 'Grass': 'grass.png',
               'Plane_Bend': 'leaf.png'}
    uses = {'leaf.png': [(0.0, 0.0), (1.0, 1.0)], 'bark.png': [(0.0, 0.0), (1.0, 0.5)],
            'grass.png': [(0.25, 0.25), (0.75, 0.75)]}
    return textures, objects, uses


def test_flora_one_tile_per_texture_no_upscale_padding_bleed_rgb24():
    textures, objects, uses = flora_set()
    plan = ac.flora_plan(textures, uses, max_size=2048, pad=8)
    red_green(lambda r: r['tiles'] == 3 and r['pad'] >= 8 and r['max_scale'] <= 1.0 and r['ctype'] == 2,
              lambda: flora_model(objects, textures),
              lambda: {'tiles': len(plan['tiles']), 'pad': 8, 'max_scale': max(t['scale'] for t in plan['tiles']),
                       'ctype': ctype(tq.write_png(plan['size'], plan['size'],
                                                   ac.flora_raster(dict((k, dict(t, crop=plan['crops'][k]))
                                                                        for k, t in textures.items()),
                                                                   plan['layout'])['rgb'], 3))})
    assert plan['size'] == 256 and 0 < plan['fill'] <= 1
    assert plan['crops']['bark.png'] == (0, 32, 128, 64)   # lower half of the 512x256 stand-in
    assert plan['crops']['grass.png'] == (8, 8, 24, 24)


def test_flora_raster_bleeds_into_padding_and_keeps_pixels():
    textures, _, uses = flora_set()
    plan = ac.flora_plan(textures, uses, pad=8)
    tex = {k: dict(t, crop=plan['crops'][k]) for k, t in textures.items()}
    img = ac.flora_raster(tex, plan['layout'], pad=8)
    size = img['size']
    x, y, iw, ih = plan['layout']['cells']['grass.png']
    inside = img['rgb'][(y * size + x) * 3:(y * size + x) * 3 + 3]
    bled = img['rgb'][((y - 8) * size + x - 8) * 3:((y - 8) * size + x - 8) * 3 + 3]
    assert inside == bled == bytes((30, 140, 40))
    assert img['alpha'] is not None   # leaf alpha + bark opacity -> a separate opacity atlas
    lx, ly, _, _ = plan['layout']['cells']['leaf.png']
    assert img['alpha'][ly * size + lx + 60] == 0 and img['alpha'][ly * size + lx + 10] == 255


def test_flora_uv_remap_keeps_every_face_of_an_instance_in_its_tile():
    textures, _, uses = flora_set()
    plan = ac.flora_plan(textures, uses)
    cell = plan['layout']['cells']['leaf.png']
    size = plan['size']
    grid = [(i / 4.0, j / 8.0) for i in range(5) for j in range(9)]   # 32 quads of a leaf card
    inside = 0
    for u, v in grid:
        au, av = ac.flora_uv(u, v, 64, 64, plan['crops']['leaf.png'], cell, size, plan['layout']['scale'])
        px, py = au * size, (1 - av) * size
        inside += cell[0] - 1e-6 <= px <= cell[0] + cell[2] + 1e-6 and cell[1] - 1e-6 <= py <= cell[1] + cell[3] + 1e-6
    assert inside == len(grid)


def test_flora_downscale_is_uniform_when_the_atlas_is_full():
    textures = {'a.png': {'w': 2048, 'h': 2048}, 'b.png': {'w': 2048, 'h': 2048}}
    uses = {'a.png': [(0, 0), (1, 1)], 'b.png': [(0, 0), (1, 1)]}
    plan = ac.flora_plan(textures, uses, max_size=2048)
    assert plan['size'] == 2048 and 0 < plan['layout']['scale'] < 1.0


def test_flora_tiling_uv_is_refused():
    with pytest.raises(ac.AtlasError, match='tiling'):
        ac.flora_plan({'a.png': {'w': 64, 'h': 64}}, {'a.png': [(0, 0), (2.0, 1.0)]})


def test_png_is_identical_for_identical_pixels():
    textures, _, uses = flora_set()
    plan = ac.flora_plan(textures, uses)
    tex = {k: dict(t, crop=plan['crops'][k]) for k, t in textures.items()}
    a = ac.flora_raster(tex, plan['layout'])
    b = ac.flora_raster(tex, plan['layout'])
    pa = tq.write_png(a['size'], a['size'], a['rgb'], 3)
    assert hashlib.md5(pa).hexdigest() == hashlib.md5(tq.write_png(b['size'], b['size'], b['rgb'], 3)).hexdigest()
