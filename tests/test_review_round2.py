"""Review round 2 regressions (#348): bare manifest filenames and camera-name collisions."""
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from test_review_publish import _load, review  # noqa: F401  (fixture: tools/review on sys.path)


def _junction(alias: Path, target: Path) -> None:
    if os.name == 'nt':
        proc = subprocess.run(['cmd', '/c', 'mklink', '/J', str(alias), str(target)],
                              capture_output=True, text=True, errors='replace')
        assert proc.returncode == 0, proc.stdout + proc.stderr
    else:
        alias.symlink_to(target, target_is_directory=True)


@pytest.mark.parametrize('form', ['bare', 'dot', 'bare-dir', 'absolute-junction', 'relative-junction'])
def test_cleanup_protects_bare_and_aliased_manifest_assets(tmp_path, form):
    """Dry-run, apply and repeat keep the library for every manifest path form."""
    review = _load('common')
    scratch = tmp_path / 'x'
    library = scratch / 't_assets'
    library.mkdir(parents=True)
    scene = library / 'model.max'
    scene.write_bytes(b'SYNTHETIC-LIBRARY')
    (library / 'textures').mkdir()
    alias = tmp_path / 'library-alias'
    manifest = library / 'library.json'
    if form == 'bare':
        text = 'model.max'
    elif form == 'dot':
        text = './model.max'
    elif form == 'bare-dir':
        text = 'textures'
    else:
        _junction(alias, library)
        manifest = tmp_path / 'library.json'
        target = alias / 'model.max'
        text = str(target.relative_to(tmp_path) if form == 'relative-junction' else target)
    manifest.write_text(json.dumps({'scene': text}), encoding='utf-8')
    old_scratch = scratch / 'ci-receipt-delete'
    old_scratch.mkdir()
    for directory in (library, old_scratch):
        os.utime(directory, (0, 0))
    try:
        for apply, expected in ((False, ['ci-receipt-delete']),
                                (True, ['ci-receipt-delete']), (True, [])):
            result = review.cleanup(days=1, scratch=scratch, manifests=[manifest],
                                    now=datetime.now(), apply=apply)
            assert [p.name for p in result] == expected
            assert scene.read_bytes() == b'SYNTHETIC-LIBRARY'
    finally:
        if alias.exists() or os.path.lexists(alias):
            alias.rmdir() if os.name == 'nt' else alias.unlink()


def test_max_job_never_deletes_source_nodes_named_like_review_camera(review):
    """Static contract: the job allocates a free camera name instead of deleting nodes."""
    source = (Path(__file__).resolve().parents[1] / 'tools' / 'review' / 'max_job.py').read_text(encoding='utf-8')
    template = source.split("TEMPLATE = r'''", 1)[1]
    assert 'delete' not in template
    assert 'getNodeByName "Review_Camera"' not in template
    script = _load('max_job').script(dict(source='a.fbx', max_out='a.max', result='r.json',
                                         preview_png='p.png'))
    assert 'render camera:reviewCam' in script
    assert 'sourceInventory' in script


def _run_max(script: Path, card: str) -> None:
    adapter = _load('max_adapter')
    executable = adapter.max_batch_path()
    version = executable.parent.name.rsplit(' ', 1)[-1]
    proc = adapter._call([adapter.SCRIPTS / 'dcc_batch.py', 'max', '--file', script, '--card', card,
                          '--timeout', '600', '--wait', '120', '--version', version])
    assert proc.returncode == 0, (proc.stdout + proc.stderr)[-2000:]


@pytest.mark.max
def test_real_max_keeps_fbx_mesh_named_review_camera(review, tmp_path):
    adapter = _load('max_adapter')
    if adapter.max_batch_path() is None:
        pytest.skip('3ds Max is not installed')
    card = os.environ.get('HERMES_KANBAN_TASK', 'review-publisher')
    fbx = (tmp_path / 'collision.fbx').as_posix()
    make = tmp_path / 'make.ms'
    make.write_text(
        '(resetMaxFile #noPrompt; units.SystemType = #meters; units.SystemScale = 1.0\n'
        'local a = Box name:"Review_Camera" length:2 width:2 height:2; a.material = Standardmaterial name:"A"\n'
        'local b = Box name:"Control_Box" length:1 width:1 height:1 pos:[5,0,0]; b.material = Standardmaterial name:"B"\n'
        'local t = Box name:"Review_Target" length:1 width:1 height:1 pos:[-5,0,0]; t.material = Standardmaterial name:"C"\n'
        f'if not (exportFile {json.dumps(fbx)} #noPrompt using:FBXEXP) do throw "export failed")\n',
        encoding='utf-8')
    _run_max(make, card)
    assert Path(fbx).is_file()
    out = tmp_path / 'scene.max'
    info = adapter.BatchAdapter().build(Path(fbx), out, None)
    assert info['ok'] and info['meshes'] == 3
    report = (tmp_path / 'readback.json').as_posix()
    read = tmp_path / 'read.ms'
    read.write_text(
        f'(loadMaxFile {json.dumps(out.as_posix())} quiet:true\n'
        f'local f = createFile {json.dumps(report)}\n'
        'local names = for g in geometry collect g.name\n'
        'sort names\n'
        'format "{\\"geometry\\":[" to:f\n'
        'for i = 1 to names.count do format "%\\"%\\"" (if i > 1 then "," else "") names[i] to:f\n'
        'format "],\\"cameras\\":%}" (for c in cameras where superClassOf c == camera collect c).count to:f\n'
        'close f)\n',
        encoding='utf-8')
    _run_max(read, card)
    back = json.loads(Path(report).read_text(encoding='utf-8-sig'))
    assert back['geometry'] == ['Control_Box', 'Review_Camera', 'Review_Target']
    assert back['cameras'] == 1


@pytest.mark.parametrize('failures, ok', [(0, True), (3, True), (10_000, False)])
def test_pending_replace_retries_transient_windows_sharing_denial(review, tmp_path, monkeypatch, failures, ok):
    """A reader/scanner briefly holding pending.json (WinError 5 under load) must not fail a
    publication; a persistent denial still fails closed with the queue bytes untouched."""
    from test_review_publish import FakeAdapter, _publish
    root = tmp_path / 'review'
    root.mkdir()
    pending = root / 'pending.json'
    original = '[{"task": "#2", "path": "C:/x/review/keep.max", "what": "keep"}]'
    pending.write_text(original, encoding='utf-8')
    real = os.replace
    calls = {'n': 0}

    def flaky(src, dst):
        if str(dst).endswith('pending.json') and calls['n'] < failures:
            calls['n'] += 1
            raise PermissionError(5, 'Access is denied', str(dst))
        return real(src, dst)

    monkeypatch.setattr(review.os, 'replace', flaky)
    monkeypatch.setattr(review.time, 'sleep', lambda s: None)
    if ok:
        assert _publish(review, tmp_path, FakeAdapter(), review_root=root) == 0
        rows = json.loads(pending.read_text(encoding='utf-8'))
        assert [r['task'] for r in rows] == ['#2', '#348']
    else:
        with pytest.raises(review.ReviewError):
            _publish(review, tmp_path, FakeAdapter(), review_root=root)
        assert pending.read_text(encoding='utf-8') == original
        assert not (root / '2026-10-20').exists()
        assert 0 < calls['n'] < 1000, 'retry must be bounded'
    assert [p.name for p in root.iterdir() if p.suffix == '.tmp'] == []
