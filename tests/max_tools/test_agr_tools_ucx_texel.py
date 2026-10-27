"""new-case: AGR Tools 0.3.0 UCX collision and texel-readout button seams.

Pattern: new-case. Probes the guarantees for the two new buttons: variant choice
from the measured UCX recommendation, exact piece and triangle parity, texel
min/median within a relative 1e-6, fail-closed inputs, distinct paths, and no
silent default for an unmapped kind or material.
"""
import importlib.util
import math
import random
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'adapters/max/agr_tools'
RUNTIME = PACKAGE / 'runtime.py'
UCX_CORE = PACKAGE / 'ucx_core.py'
TEXEL_CORE = PACKAGE / 'texel_core.py'
BUILDER = ROOT / 'tools/max/build_agr_tools.py'

BOX_T = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
         (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _box(lo, hi):
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    return [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
            (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]


def _scene(*boxes):
    verts, tris = [], []
    for lo, hi in boxes:
        tris += [tuple(i + len(verts) for i in tri) for tri in BOX_T]
        verts += _box(lo, hi)
    return verts, tris


def _box_hull(points):
    p = np.asarray(points, float)
    lo, hi = p.min(0), p.max(0)
    return np.array(_box(lo, hi)), np.array(BOX_T)


def _quad(z=0.0, size=1.0):
    return {
        'id': 'f1', 'mesh': 'wall', 'material': 'brick',
        'xyz': [(0.0, 0.0, z), (size, 0.0, z), (size, size, z), (0.0, size, z)],
        'uv': [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
    }


def test_version_macros_and_ucx_texel_readme():
    runtime = RUNTIME.read_text(encoding='utf-8')
    mcr = (PACKAGE / 'agr_tools.mcr').read_text(encoding='utf-8')
    readme = (PACKAGE / 'README.md').read_text(encoding='utf-8')
    startup = (PACKAGE / 'startup.ms').read_text(encoding='utf-8')
    install = (PACKAGE / 'install.ms').read_text(encoding='utf-8')
    assert 'VERSION = "0.3.0"' in runtime
    assert '0.002' in runtime and '0.005' in runtime
    for name in ('AGRToolsUcx', 'AGRToolsUcxApply', 'AGRToolsTexel'):
        assert name in mcr
    assert '0.3.0' in startup and 'Ucx' in startup and 'Texel' in startup
    assert 'AGRTools-0.3.0' in install
    assert 'UCX collision' in readme and 'Texel readout' in readme
    assert 'checked export' in readme.lower()
    assert UCX_CORE.is_file() and TEXEL_CORE.is_file()


def test_ucx_parity_with_python_tool_on_fixed_and_random_meshes():
    core = _load(UCX_CORE, 'agr_ucx_core_parity')
    from tools.methods.ucx import ucx_variants as uv

    cases = {
        'box': _scene(((0, 0, 0), (1, 1, 1))),
        'passage': _scene(((0, 0, 0), (4, 1, 3)), ((0, 1, 0), (1, 4, 3))),
        'few-levels': _scene(((0, 0, 0), (4, 4, 3)), ((0, 0, 3), (4, 4, 6))),
    }
    expected_kind = {'box': 'near-convex-box', 'passage': 'passage', 'few-levels': 'few-levels'}
    matched = 0
    for name, (verts, tris) in cases.items():
        before = (list(map(tuple, verts)), list(map(tuple, tris)))
        got = core.build(verts, tris, mesh='Wall')
        assert (list(map(tuple, verts)), list(map(tuple, tris))) == before
        assert got['kind'] == expected_kind[name]
        exp_pieces, exp = uv.build(got['variant'], np.array(verts, float), np.array(tris, np.int64),
                                    model_triangles=len(tris), hull_fn=_box_hull)
        assert got['pieces_count'] == exp['pieces'] == len(exp_pieces)
        assert got['triangles'] == exp['triangles']
        assert got['names'] == [f'UCX_Wall_{i:02d}' for i in range(1, got['pieces_count'] + 1)]
        assert got['triangles'] < got['limit']
        assert got['status'] == 'pass'
        assert got['audit']['collision'] == []
        matched += 1
    assert matched == 3
    assert cases['passage'] and core.build(*cases['passage'], mesh='Wall')['pieces_count'] == 2
    assert core.build(*cases['passage'], mesh='Wall')['triangles'] == 24

    rng = random.Random(728)
    agreed = 0
    for _ in range(12):
        count = rng.randint(1, 3)
        boxes = []
        cursor = 0.0
        for _item in range(count):
            span = rng.uniform(0.6, 2.5)
            height = rng.uniform(0.6, 3.0)
            boxes.append(((cursor, 0.0, 0.0), (cursor + span, span, height)))
            cursor += span + rng.choice((0.0, 2.0))
        verts, tris = _scene(*boxes)
        got = core.build(verts, tris, mesh='Rand')
        exp_pieces, exp = uv.build(got['variant'], np.array(verts, float), np.array(tris, np.int64),
                                    model_triangles=len(tris), hull_fn=_box_hull)
        assert got['pieces_count'] == exp['pieces'] == len(exp_pieces)
        assert got['triangles'] == exp['triangles']
        agreed += 1
    assert agreed == 12


def test_ucx_fail_closed_names_unmapped_kind_and_refuses_alias(tmp_path):
    core = _load(UCX_CORE, 'agr_ucx_core_fail')
    verts, tris = _scene(((0, 0, 0), (1, 1, 1)))
    with pytest.raises(ValueError, match='empty'):
        core.build([], [], mesh='Wall')
    with pytest.raises(ValueError, match='non-finite'):
        core.build([(0.0, math.nan, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)], [(0, 1, 2)], mesh='Wall')
    with pytest.raises(ValueError, match='non-finite'):
        core.build([(0.0, math.inf, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)], [(0, 1, 2)], mesh='Wall')
    with pytest.raises(ValueError, match='part-boxes'):
        core.build(verts, tris, mesh='Wall', kind='part-boxes')
    with pytest.raises(ValueError, match='at_threshold'):
        core.kind_from_outside(0.05, bands=1)
    verdict = core.budget_verdict(12, 12)
    assert verdict['status'] == 'fail' and verdict['code'] == 'at_threshold'
    assert core.budget_verdict(12, 15000)['status'] == 'pass'
    with pytest.raises(ValueError, match='exceed'):
        core.budget_verdict(13, 12)
    source = tmp_path / 'in.json'
    source.write_bytes(b'{"keep": true}\n')
    before = source.read_bytes()
    with pytest.raises(ValueError, match='input'):
        core.publish(source, source, {'status': 'fail'})
    assert source.read_bytes() == before
    assert not (tmp_path / 'in.json.partial').exists()
    report = tmp_path / 'report.json'
    core.publish(source, tmp_path / 'out.json', {'status': 'pass'}, report=report)
    assert (tmp_path / 'out.json').is_file() and report.is_file()
    assert source.read_bytes() == before


def test_texel_matches_readout_and_fail_closed(tmp_path):
    core = _load(TEXEL_CORE, 'agr_texel_core_parity')
    from dt_ai.ops.texel_density_readout import readout

    face = _quad()
    payload = {'profile': 'VPM', 'materials': [{'name': 'brick', 'map_px': 1024}], 'faces': [face]}
    got = core.summarize(payload)
    exp = readout(payload)
    assert exp['status'] == 'pass'
    assert got['meshes'][0]['min_px_per_m'] == pytest.approx(exp['faces'][0]['px_per_m'], rel=1e-9)
    assert got['meshes'][0]['median_px_per_m'] == pytest.approx(exp['faces'][0]['px_per_m'], rel=1e-9)
    assert got['materials'][0]['min_px_per_m'] == pytest.approx(exp['materials'][0]['min_px_per_m'], rel=1e-9)
    assert got['status'] == 'pass'
    small = dict(face)
    small['uv'] = [(0.0, 0.0), (0.1, 0.0), (0.1, 0.1), (0.0, 0.1)]
    planted_payload = {'profile': 'VPM', 'materials': [{'name': 'brick', 'map_px': 1024}], 'faces': [small]}
    planted = core.summarize(planted_payload)
    planted_exp = readout(planted_payload)
    assert planted['status'] == 'fail'
    assert planted['meshes'][0]['min_px_per_m'] == pytest.approx(planted_exp['faces'][0]['px_per_m'], rel=1e-9)
    assert planted_exp['faces'][0]['px_per_m'] < 512

    rng = random.Random(7281)
    agreed = 0
    for index in range(16):
        span = rng.uniform(0.4, 3.0)
        uv = rng.uniform(0.2, 1.5)
        px = rng.choice((512, 1024, 2048))
        sample = {
            'id': f'f{index}', 'mesh': 'M', 'material': 'brick',
            'xyz': [(0.0, 0.0, 0.0), (span, 0.0, 0.0), (span, span, 0.0), (0.0, span, 0.0)],
            'uv': [(0.0, 0.0), (uv, 0.0), (uv, uv), (0.0, uv)],
        }
        body = {'profile': 'VPM', 'materials': [{'name': 'brick', 'map_px': px}], 'faces': [sample]}
        a = core.summarize(body)
        b = readout(body)
        core.assert_texel_close(a['meshes'][0]['min_px_per_m'], b['faces'][0]['px_per_m'])
        core.assert_texel_close(a['materials'][0]['median_px_per_m'], b['faces'][0]['px_per_m'])
        agreed += 1
    assert agreed == 16

    with pytest.raises(ValueError, match='empty'):
        core.summarize({'profile': 'VPM', 'materials': [{'name': 'brick', 'map_px': 1024}], 'faces': []})
    with pytest.raises(ValueError, match='brick'):
        core.summarize({'profile': 'VPM', 'materials': [], 'faces': [face]})
    with pytest.raises(ValueError, match='stone'):
        core.summarize({'profile': 'NPM', 'materials': [{'name': 'stone'}], 'faces': [dict(face, material='stone')]})
    with pytest.raises(ValueError, match='at_threshold'):
        core.summarize({'profile': 'VPM', 'materials': [{'name': 'brick', 'map_px': 0}], 'faces': [face]})
    nan_face = dict(face, uv=[(0.0, math.nan), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])
    with pytest.raises(ValueError, match='non-finite'):
        core.summarize({'profile': 'VPM', 'materials': [{'name': 'brick', 'map_px': 1024}], 'faces': [nan_face]})
    with pytest.raises(ValueError, match='threshold'):
        core.assert_texel_close(1.0 / (1.0 - 1e-6), 1.0)
    core.assert_texel_close(1.0, 1.0 + 1e-9)
    partial = dict(face)
    partial.pop('mesh')
    dropped = core.summarize({'profile': 'VPM', 'materials': [{'name': 'brick', 'map_px': 1024}], 'faces': [partial, face]})
    assert dropped['status'] == 'fail'
    assert any('mesh' in item['reason'] for item in dropped['dropped'])
    assert {item['face'] for item in dropped['faces']} | {item['face'] for item in dropped['dropped']} == {0, 1}

    source = tmp_path / 'faces.json'
    source.write_text('{"faces": 1}\n', encoding='utf-8')
    before = source.read_bytes()
    with pytest.raises(ValueError, match='input'):
        core.publish(source, source, {'status': 'fail'})
    assert source.read_bytes() == before
    assert not Path(str(source) + '.partial').exists()
