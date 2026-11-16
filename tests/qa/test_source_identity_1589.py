"""new-case: synthetic stable source identity and complete source-use accounting (#1589)."""
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from adapters.max.agr_tools import build_manifest as bm
from tools.derive import build_manifest as cli


def bundle(tmp_path, unused=False):
    sources, records = [], []
    pkg = tmp_path / '0000_Syn.zip'
    with zipfile.ZipFile(pkg, 'w') as z:
        for name, filename in [('0000_Syn_Ground.fbx', 'ground_mesh_v1.json'),
                               ('T_Syn_Ground_d_1.png', 'ground_mesh_v2.json')]:
            source = tmp_path / filename
            source.write_bytes(('synthetic ' + filename).encode())
            artifact = tmp_path / name
            artifact.write_bytes(('synthetic ' + name).encode())
            rec = bm.derivation_record([artifact], source, 'unknown', role='ground')
            rec['source_id'] = 'site.mesh'
            records.append(rec)
            sources.append(source)
            z.write(artifact, name)
    if unused:
        records = records[:1]
        with zipfile.ZipFile(pkg, 'w') as z:
            z.write(tmp_path / '0000_Syn_Ground.fbx', '0000_Syn_Ground.fbx')
    return pkg, [str(p) for p in sources], records


def test_two_revisions_refused(tmp_path):
    pkg, sources, records = bundle(tmp_path)
    with pytest.raises(ValueError, match='two revisions.*site.mesh'):
        bm.make_manifest(pkg, {'ground': sources}, 'unknown', records, bm.transform_entry('identity'))


def test_unused_source_refused(tmp_path):
    pkg, sources, records = bundle(tmp_path, unused=True)
    with pytest.raises(ValueError, match='unused.*ground_mesh_v2.json'):
        bm.make_manifest(pkg, {'ground': sources}, 'unknown', records, bm.transform_entry('identity'))
