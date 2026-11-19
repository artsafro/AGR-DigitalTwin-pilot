"""new-case: BODY pre-show CLI publication and native adapter boundary (#1446)."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'tools/qa/body_layout.py'


def load_cli():
    assert SCRIPT.is_file(), 'BODY pre-show CLI is missing'
    spec = importlib.util.spec_from_file_location('body_layout_cli', SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fixture(tmp_path):
    path = tmp_path / 'body.json'
    path.write_text(json.dumps([dict(name='body', face_geometry=dict(
        vertices=[[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]],
        polygons=[[0, 1, 2, 3]]))]), encoding='utf-8')
    return path


def test_cli(tmp_path):
    src = fixture(tmp_path)
    out = tmp_path / 'report.json'
    cli = load_cli()
    report = cli.run(src, out, 'VPM')
    assert report['parts'][0]['quad_dominance']['passed']
    assert report['parts'][0]['wall_layout']['status'] == 'clean'
    assert json.loads(out.read_text()) == report
    result = subprocess.run([sys.executable, str(SCRIPT), str(src), '--out', str(tmp_path/'fresh.json'),
                             '--profile', 'VPM'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads((tmp_path/'fresh.json').read_text())['parts'] == report['parts']


@pytest.mark.parametrize('alias', ['same', 'resolved', 'hardlink', 'log'])
def test_publication_guards(tmp_path, alias):
    src = fixture(tmp_path)
    before = src.read_bytes()
    if alias == 'same': out = src
    if alias == 'resolved': out = tmp_path / 'sub' / '..' / src.name
    if alias == 'hardlink':
        out = tmp_path/'hardlink.json'
        os.link(src, out)
    if alias == 'log':
        out = tmp_path/'other.json'
        os.link(src, out.with_name(out.name+'.blender.log'))
    with pytest.raises((ValueError, FileExistsError)):
        load_cli().run(src, out, 'VPM')
    assert src.read_bytes() == before


def test_repeat_mutation_and_stale_report(tmp_path, monkeypatch):
    cli = load_cli()
    src = fixture(tmp_path)
    out = tmp_path/'new.json'
    cli.run(src, out, 'VPM')
    old = out.read_bytes()
    with pytest.raises(ValueError): cli.run(src, out, 'VPM')
    assert out.read_bytes() == old
    original = cli.part_layout_report
    def mutate(*a, **kw):
        result = original(*a, **kw)
        src.write_text('[]', encoding='utf-8')
        return result
    monkeypatch.setattr(cli, 'part_layout_report', mutate)
    with pytest.raises(ValueError, match='changed'): cli.run(src, tmp_path/'mutated.json', 'VPM')
    assert not (tmp_path/'mutated.json').exists()


@pytest.mark.parametrize('payload', ['[]', '[{}]', '[{"name":"body"}]', '[NaN]', '{}', '{"x":1,"x":2}'])
def test_invalid_fresh_cli(tmp_path, payload):
    load_cli()
    src = tmp_path/'bad.json'
    src.write_text(payload, encoding='utf-8')
    out = tmp_path/'bad-report.json'
    result = subprocess.run([sys.executable, str(SCRIPT), str(src), '--out', str(out), '--profile', 'VPM'],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert not out.exists()


def test_unknown_and_duplicate_selection(tmp_path):
    cli = load_cli()
    src = fixture(tmp_path)
    for parts in (['missing'], ['body', 'body'], []):
        with pytest.raises(ValueError): cli.run(src, tmp_path/'no.json', 'VPM', parts=parts)
    assert not (tmp_path/'no.json').exists()


def test_npz_selection_and_accounting(tmp_path):
    import numpy as np
    from dt_ai.ops.xview_gate import Part, save_npz
    cli = load_cli()
    src = tmp_path/'parts.npz'
    verts = np.array([[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]], dtype=float)
    save_npz(src, [Part(n, verts, ((0, 1, 2, 3),), np.zeros(3)) for n in ['body', 'roof']])
    report = cli.run(src, tmp_path/'selected.json', 'VPM', parts=['body'])
    assert [p['part'] for p in report['parts']] == ['body']
    assert report['dropped'] == [dict(name='roof', reason='not selected as BODY part')]


def test_native_adapter_units_and_log(tmp_path, monkeypatch):
    import numpy as np
    from dt_ai.core import blender_runner
    from dt_ai.ops.xview_gate import Part, save_npz
    cli = load_cli()
    src = tmp_path/'body.blend'
    src.write_bytes(b'synthetic native boundary; real readback is separately measured')
    def native(script, args, **kwargs):
        assert script == cli.DUMP_SCRIPT
        assert args[0] == src
        # Millimetres -> metre conversion through the existing adapter.
        save_npz(args[1], [Part('body', np.array([[0,0,0],[40,0,0],[40,0,1000],[0,0,1000]], float),
                               ((0,1,2,3),), np.zeros(3))])
        Path(kwargs['log_path']).write_bytes(b'native boundary log')
        return dict(objects=[dict(name='body')], dropped=[dict(name='camera', reason='not a mesh object')],
                    blender='synthetic test', scene='Scene', unit_system='METRIC', unit_scale=0.001)
    monkeypatch.setattr(blender_runner, 'run_blender', native)
    out = tmp_path/'native.json'
    result = cli.run(src, out, 'VPM')
    assert result['parts'][0]['wall_layout']['counts']['slivers'] == 1
    assert result['parts'][0]['wall_layout']['slivers'][0]['position_m'] == [0.02,0,0.5]
    assert out.with_name(out.name+'.blender.log').read_bytes() == b'native boundary log'
    assert result['dropped'] == [dict(name='camera', reason='not a mesh object')]


def test_competing_output_and_foreign_partial_preserved(tmp_path, monkeypatch):
    cli = load_cli()
    src = fixture(tmp_path)
    before = src.read_bytes()
    out = tmp_path/'race.json'
    foreign = tmp_path/'race.json.partial'
    foreign.write_bytes(b'foreign partial')
    real_link = os.link
    def race(source, destination, *a, **kw):
        if Path(destination) == out:
            out.write_bytes(b'competing writer')
        return real_link(source, destination, *a, **kw)
    monkeypatch.setattr(os, 'link', race)
    with pytest.raises(ValueError, match='another writer'): cli.run(src, out, 'VPM')
    assert src.read_bytes() == before
    assert out.read_bytes() == b'competing writer'
    assert foreign.read_bytes() == b'foreign partial'
    assert sorted(p.name for p in tmp_path.iterdir()) == ['body.json','race.json','race.json.partial']


def test_report_only_cli_never_claims_acceptance(tmp_path):
    cli = load_cli()
    src = fixture(tmp_path)
    rows = json.loads(src.read_text())
    rows[0]['face_geometry']['polygons'] = [[0,1,2],[0,2,3]]
    src.write_text(json.dumps(rows), encoding='utf-8')
    out = tmp_path/'diagnostic.json'
    result = subprocess.run([sys.executable,str(SCRIPT),str(src),'--out',str(out),'--profile','VPM'],
                            capture_output=True,text=True)
    assert result.returncode == 0
    row = json.loads(out.read_text())['parts'][0]
    assert row['wall_layout']['status'] == 'review' and row['wall_layout']['blocking'] is False
    assert row['quad_dominance']['passed'] is False
    assert not any(k in json.loads(out.read_text()) for k in ('passed','accepted'))


def test_unsupported_and_malformed_part_preserve_inputs(tmp_path):
    cli = load_cli()
    src = tmp_path/'body.txt'
    src.write_bytes(b'unsupported')
    with pytest.raises(ValueError, match='unsupported'): cli.run(src, tmp_path/'out.json', 'VPM')
    assert src.read_bytes() == b'unsupported'
    assert not (tmp_path/'out.json').exists()


def test_prescription_points_to_executable_check():
    for name in ('docs/domain/geometry.md', 'docs/scenarios/oks-vpm.md',
                 'docs/procedure/node-r6-oks-body-facade.md'):
        text = (ROOT/name).read_text(encoding='utf-8')
        assert 'body_layout.py' in text
        assert 'quad_dominance' in text
        assert 'report-only' in text
