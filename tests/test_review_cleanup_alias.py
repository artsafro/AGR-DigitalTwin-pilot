"""Public cleanup contract: real library directories survive manifest aliases."""
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from test_review_publish import _load


@pytest.mark.parametrize('relative', [False, True])
def test_cleanup_protects_manifest_library_through_directory_alias(tmp_path, relative):
    review = _load('common')
    scratch = tmp_path / 'x'
    library = scratch / 't_assets' / 'surface'
    library.mkdir(parents=True)
    scene = library / 'model.max'
    scene.write_bytes(b'SYNTHETIC-LIBRARY')
    alias = tmp_path / 'library-alias'
    if os.name == 'nt':
        # Directory junctions need no Windows symlink privilege.
        proc = subprocess.run(['cmd', '/c', 'mklink', '/J', str(alias), str(library)],
                              capture_output=True, text=True, errors='replace')
        assert proc.returncode == 0, proc.stdout + proc.stderr
    else:
        alias.symlink_to(library, target_is_directory=True)
    target = alias / 'model.max'
    manifest = tmp_path / 'library.json'
    manifest.write_text(json.dumps({'scene': str(target.relative_to(tmp_path) if relative else target)}),
                        encoding='utf-8')
    old_scratch = scratch / 'ci-receipt-delete'
    old_scratch.mkdir()
    for directory in (library.parent, old_scratch):
        os.utime(directory, (0, 0))
    try:
        for apply, expected in ((False, ['ci-receipt-delete']),
                                (True, ['ci-receipt-delete']), (True, [])):
            result = review.cleanup(days=1, scratch=scratch, manifests=[manifest],
                                    now=datetime.now(), apply=apply)
            assert [p.name for p in result] == expected
            assert library.is_dir(), 'manifest alias lost its physical library'
            assert scene.read_bytes() == b'SYNTHETIC-LIBRARY'
    finally:
        if os.name == 'nt':
            alias.rmdir()
        else:
            alias.unlink()
