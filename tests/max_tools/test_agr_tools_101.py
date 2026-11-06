"""AGR Tools 1.0.1 (#1024): regressions of the KPP1 end-to-end run of 1.0.0 (job 20261106-075555-c179f5f0, Max 2024).

Each blocker of the release run is a test that was RED on the 1.0.0 tree and is GREEN after its fix (one commit per
fix). The modules belong to several branches (L, M, N, P, Q, S, 0.8 checks); a patch release touches them together.
"""
import importlib.util
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'
LIB = ROOT / 'library/materials/materials.json'


def _load(filename, name):
    mod = sys.modules.get(name)
    if mod is None:
        spec = importlib.util.spec_from_file_location(name, PKG / filename)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return mod


ml = _load('matlib_core.py', 'agr_tools_matlib_core')
tc = _load('tex_core.py', 'agr_tools_tex_core')
vc = _load('vpmmaps_core.py', 'agr_tools_vpmmaps_core')


# ---- stage 6: one scale of roughness / metallic / emissive ------------------------------------------------------
# Contract (1.0.1): the library record is the single source and keeps 8-bit levels 0..255 (materials_v001.json
# "byte_fields", dt_ai MaterialRegistry `Byte`, tiles_core ERM). Consumers that write an 8-bit ERM texel take the
# level as it is; only the Physical material (0..1 float) normalises, at its own boundary (matlib_core.sub_spec).
def test_vpm_maps_from_the_real_library_kpp1_ids(tmp_path):
    """RED on 1.0.0: «roughness must be a number in 0..1: 150» (vpm.build step 6 with library_path, KPP1 e2e)."""
    lib = ml.load_library(str(LIB))
    ids = [1, 3, 9, 12, 16, 29, 35]
    table = {'SM_Kpp_1_Main': {lid: 1001 + i for i, lid in enumerate(ids)}}
    res = vc.build_maps(table, lib, str(tmp_path))
    erm = [m for m in res['maps'] if m['kind'] == 'ERM']
    assert len(erm) == len(ids)
    for m in erm:
        lid = ids[m['udim'] - 1001]
        rec = lib['by_id'][lid]
        px = tc.decode_png(Path(m['path']).read_bytes())[0].px
        assert tuple(px[0:3]) == (rec['emissive'], rec['roughness'], rec['metallic'])   # the level itself, no rescale


def test_erm_level_contract_bytes_only():
    rec = {'emissive': 0, 'roughness': 150, 'metallic': 255}
    assert vc.erm_colour(rec) == (0, 150, 255)
    for bad in (0.5, 256, -1, True, '150'):
        with pytest.raises(ValueError):
            vc.erm_colour(dict(rec, roughness=bad))


def test_physical_boundary_still_normalises():
    lib = ml.load_library(str(LIB))
    rec = lib['by_id'][12]
    sub = ml.sub_spec(rec)
    assert sub['roughness'] == rec['roughness'] / 255.0 and 0 <= sub['metallic'] <= 1
