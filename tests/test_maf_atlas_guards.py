"""Review round 1 regressions for #524 (PR #543): output boundary, UV-dump completeness, ID-corner keep-out.

Each test is one row of the PR's Acceptance table. Every witness runs through the CLI ``main`` of the tool.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools' / 'library'))
sys.path.insert(0, str(ROOT / 'tests'))

import maf_atlas_ids as ids_mod  # noqa: E402
import maf_atlas_layout as lay  # noqa: E402
from test_maf_atlas_ids import _outs, _setup, _write  # noqa: E402
from test_maf_atlas_layout import POS, SPEC, _ids_run  # noqa: E402


def _arg(args, name):
    return Path(args[args.index(name) + 1])


def _snapshot(paths):
    return {str(p): Path(p).read_bytes() for p in paths}


def _no_temps(d: Path):
    return [p.name for p in d.rglob('*') if p.name.endswith('.partial') or p.name.endswith('.tmp')]


# ---------------------------------------------------------------- P1-2 output boundary: ids CLI

def test_ids_seed_named_like_the_old_temp_of_the_output_survives(tmp_path):
    args = _setup(tmp_path)
    seed = _arg(args, '--seed')
    alias = tmp_path / 'out.json.partial'
    seed.rename(alias)
    args[args.index('--seed') + 1] = str(alias)
    before = alias.read_bytes()
    assert ids_mod.main(args + _outs(tmp_path)) == 0
    assert alias.read_bytes() == before and (tmp_path / 'out.json').is_file()
    assert _no_temps(tmp_path) == ['out.json.partial']  # only the input itself, no leftover temp


def test_ids_unrelated_partial_sentinel_is_preserved(tmp_path):
    for n in ('out.json.partial', 'out.md.partial'):
        (tmp_path / n).write_bytes(b'SENTINEL ' + n.encode())
    assert ids_mod.main(_setup(tmp_path) + _outs(tmp_path)) == 0
    for n in ('out.json.partial', 'out.md.partial'):
        assert (tmp_path / n).read_bytes() == b'SENTINEL ' + n.encode()


@pytest.mark.parametrize('target', ['material_ids_v005_contact_sheet.png', 'tiles/ID_01_paint_red.png',
                                    'overlay_T_Atlas.png'])
def test_ids_evidence_target_on_an_input_fails_before_any_write(tmp_path, capsys, target):
    args = _setup(tmp_path)
    ev = tmp_path / 'ev'
    alias = ev / target
    alias.parent.mkdir(parents=True)
    seed = _arg(args, '--seed')
    alias.write_bytes(seed.read_bytes())
    args[args.index('--seed') + 1] = str(alias)
    before = _snapshot([alias])
    assert ids_mod.main(args + _outs(tmp_path) + ['--evidence-dir', str(ev)]) == 2
    assert 'resolves to an input' in capsys.readouterr().err
    assert _snapshot([alias]) == before
    assert not (tmp_path / 'out.json').exists() and not (tmp_path / 'out.md').exists()
    assert sorted(p.relative_to(ev).as_posix() for p in ev.rglob('*') if p.is_file()) == [target]


def test_ids_json_output_on_an_evidence_target_fails(tmp_path, capsys):
    ev = tmp_path / 'ev'
    args = _setup(tmp_path) + ['--out-json', str(ev / 'material_ids_v005_contact_sheet.png'),
                               '--out-md', str(tmp_path / 'out.md'), '--evidence-dir', str(ev)]
    assert ids_mod.main(args) == 2
    assert 'same file' in capsys.readouterr().err and not ev.exists()


def test_ids_found_atlas_image_as_evidence_target_fails(tmp_path, capsys):
    """The atlas found through --maps-dir is an input, too: a tile path on it must be refused."""
    args = _setup(tmp_path)
    maps = _arg(args, '--maps-dir')
    ev = tmp_path / 'ev'
    (ev / 'tiles').mkdir(parents=True)
    # the maps dir is the tiles dir of the evidence: tile ID_01 would land on a found image of the same name
    img = maps / 'T_Atlas.png'
    target = ev / 'tiles' / 'ID_01_paint_red.png'
    target.write_bytes(img.read_bytes())
    args[args.index('--maps-dir') + 1] = str(ev / 'tiles')
    mats = json.loads(_arg(args, '--materials').read_text(encoding='utf-8'))
    for f in mats['files']:
        for m in f['materials']:
            for t in m['textures']:
                t['filepath'] = t['filepath'].replace('T_Atlas.png', 'ID_01_paint_red.png')
    _write(_arg(args, '--materials'), mats)
    uv = json.loads(_arg(args, '--uv-dump').read_text(encoding='utf-8'))
    for f in uv['files']:
        for m in f['materials'].values():
            for t in m['images']:
                t['filepath'] = t['filepath'].replace('T_Atlas.png', 'ID_01_paint_red.png')
    _write(_arg(args, '--uv-dump'), uv)
    before = target.read_bytes()
    assert ids_mod.main(args + _outs(tmp_path) + ['--evidence-dir', str(ev)]) == 2
    assert 'resolves to an input' in capsys.readouterr().err and target.read_bytes() == before


def test_ids_cli_fresh_process_distinct_paths_control(tmp_path):
    args = _setup(tmp_path) + _outs(tmp_path) + ['--evidence-dir', str(tmp_path / 'ev')]
    p = subprocess.run([sys.executable, str(ROOT / 'tools' / 'library' / 'maf_atlas_ids.py'), *args],
                       capture_output=True, text=True, encoding='utf-8')
    assert p.returncode == 0, p.stderr
    assert (tmp_path / 'out.json').is_file() and _no_temps(tmp_path) == []


# ---------------------------------------------------------------- P1-2 output boundary: layout CLI

def _layout(tmp_path, ids_json, ev, spec=None):
    return ['--ids', str(ids_json), '--spec', _write(tmp_path / 'spec.json', spec or SPEC),
            '--tiles-dir', str(ev), '--site-set', 's=' + _write(tmp_path / 'set.json', POS),
            '--out-json', str(tmp_path / 'layout.json')]


def test_layout_spec_named_like_the_old_temp_survives_and_sentinel_kept(tmp_path):
    ids_json, ev = _ids_run(tmp_path)
    spec = tmp_path / 'layout.json.partial'
    _write(spec, SPEC)
    (tmp_path / 'layout.md.partial').write_bytes(b'SENTINEL')
    args = _layout(tmp_path, ids_json, ev)
    args[args.index('--spec') + 1] = str(spec)
    before = spec.read_bytes()
    assert lay.main(args + ['--out-md', str(tmp_path / 'layout.md')]) == 0
    assert spec.read_bytes() == before and (tmp_path / 'layout.md.partial').read_bytes() == b'SENTINEL'
    assert (tmp_path / 'layout.json').is_file()


def test_layout_png_on_the_ids_input_fails_and_ids_survive(tmp_path, capsys):
    """Reviewer witness: ids JSON named ids.png, evidence dir png/, profile file ../ids.png."""
    ids_json, ev = _ids_run(tmp_path)
    ids_png = tmp_path / 'ids.png'
    ids_png.write_bytes(ids_json.read_bytes())
    spec = json.loads(json.dumps(SPEC))
    spec['library']['profiles']['vpm']['file'] = '../ids.png'
    args = _layout(tmp_path, ids_png, ev, spec=spec) + ['--evidence-dir', str(tmp_path / 'png')]
    before = ids_png.read_bytes()
    assert lay.main(args) == 2
    assert ids_png.read_bytes() == before and not (tmp_path / 'layout.json').exists()
    assert not (tmp_path / 'png').exists() or not any((tmp_path / 'png').iterdir())
    assert 'file name' in capsys.readouterr().err


@pytest.mark.parametrize('name, msg', [('set.json', 'resolves to an input'), ('layout.json', 'same file'),
                                       ('npm.png', 'same file')])
def test_layout_png_target_aliases_fail_before_any_write(tmp_path, capsys, name, msg):
    ids_json, ev = _ids_run(tmp_path)
    spec = json.loads(json.dumps(SPEC))
    spec['library']['profiles']['vpm']['file'] = name
    args = _layout(tmp_path, ids_json, ev, spec=spec) + ['--evidence-dir', str(tmp_path)]
    pos_before = (tmp_path / 'set.json').read_bytes() if (tmp_path / 'set.json').exists() else None
    assert lay.main(args) == 2
    assert msg in capsys.readouterr().err
    assert not (tmp_path / 'layout.json').exists() and not (tmp_path / 'npm.png').exists()
    if pos_before is not None:
        assert (tmp_path / 'set.json').read_bytes() == pos_before


def test_layout_png_on_a_tile_input_fails(tmp_path, capsys):
    ids_json, ev = _ids_run(tmp_path)
    tile = next((ev / 'tiles').glob('ID_01_*.png'))
    spec = json.loads(json.dumps(SPEC))
    spec['library']['profiles']['vpm']['file'] = tile.name
    before = tile.read_bytes()
    args = _layout(tmp_path, ids_json, ev, spec=spec) + ['--evidence-dir', str(ev / 'tiles')]
    assert lay.main(args) == 2
    assert 'resolves to an input' in capsys.readouterr().err and tile.read_bytes() == before


def test_layout_cli_fresh_process_distinct_paths_control(tmp_path):
    ids_json, ev = _ids_run(tmp_path)
    args = _layout(tmp_path, ids_json, ev) + ['--evidence-dir', str(tmp_path / 'png'),
                                               '--out-md', str(tmp_path / 'layout.md')]
    p = subprocess.run([sys.executable, str(ROOT / 'tools' / 'library' / 'maf_atlas_layout.py'), *args],
                       capture_output=True, text=True, encoding='utf-8')
    assert p.returncode == 0, p.stderr
    assert sorted(x.name for x in (tmp_path / 'png').iterdir()) == ['npm.png', 'site.png', 'vpm.png']
    assert _no_temps(tmp_path) == []


# ---------------------------------------------------------------- P1-3 UV dump completeness

def _edit_uv(args, fn):
    p = _arg(args, '--uv-dump')
    uv = json.loads(p.read_text(encoding='utf-8'))
    fn(uv)
    _write(p, uv)


@pytest.mark.parametrize('edit, msg', [
    (lambda uv: uv['files'].__setitem__(0, {'fbx': 'MAF_0001_A.fbx', 'error': 'import failed'}),
     'MAF_0001_A.fbx: import failed'),
    (lambda uv: uv['files'].pop(1), 'no row for MAF_0002'),
    (lambda uv: uv['files'][0]['materials']['Red'].update(uv_layer=None, faces=[]), 'no UV layer'),
    (lambda uv: uv['files'][0].pop('materials'), 'MAF_0001_A.fbx: no materials'),
    (lambda uv: uv['files'][1]['materials'].clear(), 'MAF_0002_B.fbx: no materials'),
    (lambda uv: uv.__setitem__('files', []), 'no files'),
    (lambda uv: uv['files'].append({'fbx': 'MAF_0001_A.fbx', 'materials': {
        'X': {'images': [], 'uv_layer': 'UVMap', 'faces': []}}}), 'twice'),
])
def test_failed_or_incomplete_uv_dump_fails_closed_and_publishes_nothing(tmp_path, capsys, edit, msg):
    args = _setup(tmp_path)
    _edit_uv(args, edit)
    ev = tmp_path / 'ev'
    assert ids_mod.main(args + _outs(tmp_path) + ['--evidence-dir', str(ev)]) == 2
    assert msg in capsys.readouterr().err
    assert not (tmp_path / 'out.json').exists() and not (tmp_path / 'out.md').exists() and not ev.exists()


def test_maf_whose_atlas_material_is_on_no_face_is_listed_unmeasured_not_zero(tmp_path):
    args = _setup(tmp_path)
    # MAF_0002 keeps a row, but no polygon uses its atlas-bound material (unused slot in the FBX)
    _edit_uv(args, lambda uv: uv['files'][1].__setitem__('materials', {
        '<none>': {'images': [], 'uv_layer': 'UVMap', 'faces': [[0.1, 0.1, 0.2, 0.1, 0.2, 0.2]]}}))
    assert ids_mod.main(args + _outs(tmp_path)) == 0
    uvr = json.loads((tmp_path / 'out.json').read_text(encoding='utf-8'))['atlases'][0]['uv']
    assert [(u['maf'], u['fbx']) for u in uvr['unmeasured']] == [('MAF_0002', 'MAF_0002_B.fbx')]
    assert 'not measured' in uvr['unmeasured'][0]['reason']
    assert all('MAF_0002' not in c['mafs'] for c in uvr['cells'].values())
    assert 'no UV face read back (not measured, not 0): 1 - MAF_0002' in \
        (tmp_path / 'out.md').read_text(encoding='utf-8')


def test_complete_uv_dump_control_has_no_unmeasured_maf(tmp_path):
    assert ids_mod.main(_setup(tmp_path) + _outs(tmp_path)) == 0
    assert json.loads((tmp_path / 'out.json').read_text(encoding='utf-8'))['atlases'][0]['uv']['unmeasured'] == []


def test_uv_error_row_of_a_maf_without_atlas_textures_is_still_a_failure(tmp_path, capsys):
    args = _setup(tmp_path)
    _edit_uv(args, lambda uv: uv['files'].append({'fbx': 'MAF_0009_Z.fbx', 'error': 'file missing'}))
    assert ids_mod.main(args + _outs(tmp_path)) == 2
    assert 'MAF_0009_Z.fbx: file missing' in capsys.readouterr().err


# ---------------------------------------------------------------- P1-4 ID-corner keep-out

def _uv_one(face, w=100, h=100, cell=None):
    atlas = {'size': [w, h], 'cells': [cell or {'x': 0, 'y': 0, 'w': w, 'h': h, 'kind': 'flat'}]}
    uvd = {'files': [{'fbx': 'MAF_0001_A.fbx', 'materials': {
        'M': {'images': [{'filepath': 'a.png'}], 'uv_layer': 'UVMap', 'faces': [face]}}}]}
    return ids_mod.uv_cells(uvd, 'a.png', atlas)


def _px(pts, w, h):
    """pixel (x, y) with y down -> flat UV list."""
    return [c for x, y in pts for c in (x / w, 1 - y / h)]


@pytest.mark.parametrize('pts, size, corner', [
    # reviewer witness: no vertex in the corner, the interior crosses it
    ([(0, 100), (100, 0), (100, 87)], 100, 1),
    # an edge crossing the corner, vertices on both sides of it
    ([(80, 99), (99, 80), (70, 70)], 100, 1),
    # big face covering the whole corner, all vertices far outside it
    ([(-50, -50), (300, -50), (-50, 300)], 100, 1),
    # vertex inside the corner
    ([(90, 90), (95, 90), (95, 95)], 100, 1),
    # small 512-set cell: 56 px content -> 16 px minimum corner (the old 12% zone was 6.7 px)
    ([(42, 42), (46, 42), (46, 46)], 56, 1),
    # boundary touch: the face ends exactly on the corner edge (x = 84) - no overlap
    ([(10, 90), (84, 90), (84, 99)], 100, 0),
    # clean control
    ([(10, 10), (50, 10), (50, 50)], 100, 0),
])
def test_corner_occupancy_is_polygon_rectangle_intersection(pts, size, corner):
    u = _uv_one(_px(pts, size, size), size, size)['cells'][0]
    assert u['faces'] == 1 and u['corner_faces'] == corner


def test_corner_uses_the_layout_id_corner_contract():
    assert ids_mod.id_corner([0, 0, 100, 100]) == lay.id_corner([0, 0, 100, 100]) == [84, 84, 16, 16]
    assert lay.id_corner is ids_mod.id_corner


def test_require_keepout_fails_naming_the_cell_and_passes_when_clean(tmp_path, capsys):
    # the red cell of the synthetic atlas: one face crossing its bottom-right corner, no vertex in it
    (tmp_path / 'a').mkdir()
    (tmp_path / 'b').mkdir()
    clean = _setup(tmp_path / 'a')
    assert ids_mod.main(clean + _outs(tmp_path / 'a') + ['--require-keepout']) == 0
    r = json.loads((tmp_path / 'a' / 'out.json').read_text(encoding='utf-8'))
    c = next(c for c in r['atlases'][0]['cells'] if c.get('id') == 1)
    W, H = r['atlases'][0]['size']
    x0, y0, x1, y1 = c['x'], c['y'], c['x'] + c['w'], c['y'] + c['h']
    face = _px([(x0 + 1, y1 - 1), (x1 - 1, y0 + 1), (x1 - 1, y1 - 0.13 * c['h'])], W, H)
    bad = _setup(tmp_path / 'b', faces=[face, [0.4, 0.0, 0.6, 0.0, 0.5, 0.0]])
    assert ids_mod.main(bad + _outs(tmp_path / 'b') + ['--require-keepout']) == 1
    err = capsys.readouterr().err
    assert 'keep-out' in err and 'T_Atlas.png' in err and 'MAF_0001' in err
    assert not (tmp_path / 'b' / 'out.json').exists()
