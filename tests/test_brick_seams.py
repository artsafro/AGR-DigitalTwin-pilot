"""new-case: shared course-grid command; synthetic fixtures, no DCC acceptance."""
import json
import subprocess
import sys
import pytest


def mesh_config():
    points = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
              [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]]
    rows = [dict(object='synthetic', face=i, vertices=ids, xyz=[points[j] for j in ids])
            for i, ids in enumerate([[0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]])]
    return dict(schema='brick-seams/1', mode='mesh', course_height_m=.25, panel_step_m=.5,
                repeat_m=1, texel_px_m=512, tile_px=2048, tile_budget=1,
                data=dict(rows=rows, seam_edges=[], z0_m=0, border_px=16, udim_tile=1001))


def test_fresh_command_builds_one_tile_and_continuous_courses(tmp_path):
    source = tmp_path / 'config.json'; out = tmp_path / 'out.json'
    source.write_text(json.dumps(mesh_config()))
    result = subprocess.run([sys.executable, '-m', 'dt_ai.cli.agr', 'brick-seams',
                             '--config', str(source), '--out', str(out)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text())
    plan = payload['plan']
    assert plan['passed'] is False
    assert len(plan['faces']) == 4
    assert plan['vertical_edges'] == 4
    assert plan['max_course_residual'] == 0
    assert {f['tile'] for f in plan['faces']} == {1001}
    assert plan['faces'][0]['course_panel'][2] == [2, 4]
    assert all(0 < x < 1 for f in plan['faces'] for p in f['uv'] for x in p)


def test_brick_seams_help_is_real_shared_command():
    result = subprocess.run([sys.executable, '-m', 'dt_ai.cli.agr', 'brick-seams', '--help'],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert '--config' in result.stdout
    assert '--out' in result.stdout


def test_shared_pages_keep_source_coordinates_and_explicit_budget():
    from adapters.max.agr_tools.seams_core import assemble_support_pages
    part = dict(source=['synthetic', 3], pieces=[dict(source=['synthetic', 3], joint=True,
                patch=['synthetic', 3, 0], chart_m=[[0, 0], [.02, 0], [.02, 1], [0, 1]],
                xyz=[[0, 0, 0], [.02, 0, 0], [.02, 0, 1], [0, 0, 1]])], dropped_faces=[])
    placement = dict(key=['synthetic', 3, 0], tile=1001, translation_m=[1, 1],
                     members=[dict(key=['synthetic', 3, 0], fold_shift_m=[0, 0])])
    result = assemble_support_pages([part], dict(faces=[], unplaced=[], dropped_faces=[]),
                                   [placement], texel_px_m=512.1, tile_px=4096, tile_budget=1)
    assert result['faces'][0]['uv'][0] == [512.1/4096, 512.1/4096]
    assert result['faces'][0]['xyz'] == part['pieces'][0]['xyz']
    assert result['source_faces'] == 1 and result['passed'] is False


@pytest.mark.parametrize('name,bad', [(k, v) for k in ('course_height_m', 'panel_step_m', 'repeat_m')
                                     for v in (0, -1, True, float('nan'), float('inf'), '1')])
def test_invalid_physical_parameters_fail_closed(name, bad):
    from adapters.max.agr_tools.seams_core import calculate
    config = mesh_config(); config[name] = bad
    with pytest.raises((ValueError, TypeError)):
        calculate(config)


@pytest.mark.parametrize('mode', ['empty', 'partial', 'unknown', 'duplicate', 'overflow', 'noninteger',
                                  'tile', 'budget', 'boundary', 'nonfinite'])
def test_bad_configs_do_not_write(mode, tmp_path):
    from tools.materials.brick_seams import run
    config = mesh_config()
    if mode == 'empty': config['data']['rows'] = []
    elif mode == 'partial': del config['course_height_m']
    elif mode == 'unknown': config['ghost'] = 1
    elif mode == 'duplicate': config['data']['rows'] *= 2
    elif mode == 'overflow': config['data']['border_px'] = 1000
    elif mode == 'noninteger': config['course_height_m'] = .3
    elif mode == 'tile': config['data']['udim_tile'] = 1002
    elif mode == 'budget': config['tile_budget'] = True
    elif mode == 'boundary': config['data']['border_px'] = 1024
    elif mode == 'nonfinite': config['data']['rows'][0]['xyz'][0][0] = float('nan')
    source = tmp_path/'in.json'; source.write_text(json.dumps(config))
    with pytest.raises((ValueError, TypeError)):
        run(source, tmp_path/'out.json')
    assert list(tmp_path.iterdir()) == [source]


@pytest.mark.parametrize('kind', ['same', 'resolved', 'hardlink', 'partial', 'existing'])
def test_path_aliases_and_foreign_partials_preserve_bytes(kind, tmp_path):
    import os
    from tools.materials.brick_seams import run
    source = tmp_path/'in.json'; source.write_text(json.dumps(mesh_config()))
    out = tmp_path/'out.json'
    if kind == 'same': out = source
    elif kind == 'resolved': out = tmp_path/'sub'/'..'/'in.json'
    elif kind == 'hardlink': os.link(source, out)
    elif kind == 'partial': (tmp_path/'out.json.partial').write_text('foreign')
    elif kind == 'existing': out.write_text('foreign')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    with pytest.raises((ValueError, OSError)):
        run(source, out)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()} == before


def test_mutated_input_during_calculation_refuses(tmp_path, monkeypatch):
    from tools.materials import brick_seams as command
    source = tmp_path/'in.json'; source.write_text(json.dumps(mesh_config()))
    real = command.calculate
    def mutate(config):
        result = real(config); source.write_text('{}'); return result
    monkeypatch.setattr(command, 'calculate', mutate)
    with pytest.raises(ValueError, match='changed'):
        command.run(source, tmp_path/'out.json')
    assert not (tmp_path/'out.json').exists()


def test_competing_output_is_never_clobbered(tmp_path, monkeypatch):
    from tools.materials import brick_seams as command
    source = tmp_path/'in.json'; source.write_text(json.dumps(mesh_config()))
    operation = 'rename' if command.os.name == 'nt' else 'link'
    real = getattr(command.os, operation)
    def compete(src, dst):
        dst.write_text('foreign'); return real(src, dst)
    monkeypatch.setattr(command.os, operation, compete)
    with pytest.raises(FileExistsError):
        command.run(source, tmp_path/'out.json')
    assert (tmp_path/'out.json').read_text() == 'foreign'


def test_windows_publication_does_not_require_hardlink_support(tmp_path, monkeypatch):
    import os
    if os.name != 'nt':
        pytest.skip('Windows no-replace rename contract')
    from tools.materials import brick_seams as command
    source = tmp_path/'in.json'; source.write_text(json.dumps(mesh_config()))
    def no_links(*args):
        raise OSError('Drive filesystem does not support hardlinks')
    monkeypatch.setattr(command.os, 'link', no_links)
    command.run(source, tmp_path/'out.json')
    assert json.loads((tmp_path/'out.json').read_text())['status'] == 'candidate_calculated'


def test_generated_one_tile_course_phase_and_input_preservation():
    import copy
    import random
    from adapters.max.agr_tools.seams_core import calculate
    rng = random.Random(1510)
    for _ in range(150):
        config = mesh_config(); shift = [rng.uniform(-10, 10) for _ in range(3)]
        for row in config['data']['rows']:
            row['xyz'] = [[p[k]+shift[k] for k in range(3)] for p in row['xyz']]
        frozen = copy.deepcopy(config)
        result = calculate(config)
        assert result['max_course_residual'] < 1e-10
        assert len(result['faces']) == 4 and result['dropped_faces'] == []
        assert all(0 < x < 1 for f in result['faces'] for p in f['uv'] for x in p)
        assert config == frozen


def test_core_works_without_site_packages():
    result = subprocess.run([sys.executable, '-S', '-c',
                            'from adapters.max.agr_tools.seams_core import calculate; import json; '
                            'c=json.loads(input()); print(len(calculate(c)["faces"]))'],
                            input=json.dumps(mesh_config()), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '4'


@pytest.mark.parametrize('kind', ['stale', 'duplicate', 'alias', 'unknown', 'changed'])
def test_hash_bound_inputs_fail_closed(kind, tmp_path, monkeypatch):
    import hashlib
    from tools.materials import brick_seams as command
    mesh = mesh_config(); data = mesh.pop('data')
    asset = tmp_path/'mesh.json'; asset.write_text(json.dumps(data))
    mesh['inputs'] = dict(mesh=dict(path=str(asset), sha256=hashlib.sha256(asset.read_bytes()).hexdigest()))
    if kind == 'stale': mesh['inputs']['mesh']['sha256'] = '0'*64
    elif kind == 'duplicate':
        mesh['mode'] = 'pages'
        mesh['inputs'] = {k: mesh['inputs']['mesh'] for k in ('partitions', 'brick_fold', 'placements')}
    elif kind == 'unknown': mesh['inputs']['ghost'] = mesh['inputs']['mesh']
    source = tmp_path/'config.json'; source.write_text(json.dumps(mesh))
    output = asset if kind == 'alias' else tmp_path/'out.json'
    if kind == 'changed':
        real = command.calculate
        def mutate(c):
            result = real(c); asset.write_text('{}'); return result
        monkeypatch.setattr(command, 'calculate', mutate)
    with pytest.raises(ValueError):
        command.run(source, output)
    if kind != 'alias': assert not output.exists()
    assert source.exists() and asset.exists()


def test_fresh_relative_paths_and_stale_receipt_refusal(tmp_path):
    source = tmp_path/'config.json'; source.write_text(json.dumps(mesh_config()))
    args = [sys.executable, '-m', 'dt_ai.cli.agr', 'brick-seams', '--config', 'config.json', '--out', 'out.json']
    first = subprocess.run(args, cwd=tmp_path, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    before = (tmp_path/'out.json').read_bytes()
    source.write_text('{}')
    for _ in range(2):
        failure = subprocess.run(args, cwd=tmp_path, capture_output=True, text=True)
        assert failure.returncode == 2
        assert (tmp_path/'out.json').read_bytes() == before
    assert json.loads(before)['passed'] is False


def test_duplicate_page_piece_is_not_silently_replicated():
    from adapters.max.agr_tools.seams_core import assemble_support_pages
    piece = dict(source=['synthetic', 0], joint=True, patch=['synthetic', 0, 0],
                 chart_m=[[0, 0], [1, 0], [1, 1]], xyz=[[0, 0, 0], [1, 0, 0], [1, 0, 1]])
    part = dict(source=['synthetic', 0], pieces=[piece, piece], dropped_faces=[])
    place = dict(key=['synthetic', 0, 0], tile=1001, translation_m=[1, 1],
                 members=[dict(key=['synthetic', 0, 0], fold_shift_m=[0, 0])])
    with pytest.raises(ValueError, match='duplicate piece'):
        assemble_support_pages([part], dict(faces=[], unplaced=[], dropped_faces=[]), [place],
                               texel_px_m=512, tile_px=2048, tile_budget=1)


def test_json_duplicate_keys_refused_without_output(tmp_path):
    from tools.materials.brick_seams import run
    source = tmp_path/'in.json'; source.write_text('{"schema":"brick-seams/1","schema":"brick-seams/1"}')
    with pytest.raises(ValueError, match='duplicate JSON key'):
        run(source, tmp_path/'out.json')
    assert not (tmp_path/'out.json').exists()
