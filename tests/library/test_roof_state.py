"""new-case: a persistent source rewrite must prevent final roof catalogue publication."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest


def test_changed_source_cannot_publish_catalogue(monkeypatch, tmp_path):
    real_repo = Path(__file__).resolve().parents[2]
    repo = tmp_path/'repo'
    scripts = repo/'tools/library'
    scripts.mkdir(parents=True)
    for name in ['roof_parts.py', 'check_library.py', 'build_roof_blender.py']:
        shutil.copy2(real_repo/'tools/library'/name, scripts/name)
    source = tmp_path/'synthetic-source.fbx'
    source.write_bytes(b'synthetic fixture; native extraction is mocked')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assets = [dict(id=f'R{i}', name='Synthetic part', component=f'S-c{i}', source_object='Synthetic',
                   faces=[i], triangles=2, material_slot=0) for i in range(8)]
    plan = {'schema': 'roof-extraction-set/1', 'plans': [
        {'schema': 'roof-extraction/1', 'source_sha256': digest, 'assets': assets}]}
    folder = repo/'library/roof_equipment'
    folder.mkdir(parents=True)
    (folder/'extraction.json').write_text(json.dumps(plan), encoding='utf-8')
    monkeypatch.setitem(sys.modules, 'bpy', SimpleNamespace(app=SimpleNamespace(version=(5, 1, 2))))
    monkeypatch.setitem(sys.modules, 'mathutils', SimpleNamespace(Matrix=object, Vector=object))
    spec = importlib.util.spec_from_file_location('roof_state_test', scripts/'build_roof_blender.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'extract', lambda *args: [(a, [], [], []) for a in assets])
    monkeypatch.setattr(module, 'save_asset', lambda *args: {'synthetic': True})
    monkeypatch.setattr(module, 'showcase', lambda *args: {'synthetic': True})
    original_sha, reads = module.sha, 0

    def changed_sha(path):
        nonlocal reads
        if Path(path) == source:
            reads += 1
            if reads == 2:
                source.write_bytes(b'synthetic adversarial persistent rewrite')
        return original_sha(path)

    monkeypatch.setattr(module, 'sha', changed_sha)
    output = tmp_path/'candidate'
    monkeypatch.setattr(sys, 'argv', ['builder', '--', str(repo), str(output), str(source)])
    old_path = list(sys.path)
    try:
        with pytest.raises(ValueError, match='input changed during build'):
            module.main()
    finally:
        sys.path[:] = old_path
    assert output.exists()  # partial geometry may exist; final publication must not.
    assert not (output/'catalogue.json').exists()
    assert not (output/'SHA256SUMS.txt').exists()
