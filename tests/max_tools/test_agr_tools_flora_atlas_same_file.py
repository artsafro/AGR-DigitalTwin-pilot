"""new-case: atlas.flora accepts an opacity slot that points at the diffuse RGBA PNG itself (#1024, A101 Flora).

A101 FLORIO_221.max materials put the same RGBA PNG in diffuseMap and opacityMap (measured, AGR Lab job
20261106-020154-451ed182). atlas.flora answered `opacity_mismatch` ("both diffuse alpha and an opacity map") for
every species; with the same file it now uses the diffuse alpha (native: job 20261106-031446-91a1235d, 5 species ->
one 2048 atlas + `_o`, every face in the atlas). A different opacity file next to a diffuse alpha still fails.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _glue():
    spec = importlib.util.spec_from_file_location('agr_tools_flora_atlas_max_same',
                                                  ROOT / 'adapters/max/agr_tools/flora_atlas_max.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_same_file_normalises_case_separators_and_relative_parts(tmp_path):
    g = _glue()
    p = tmp_path / 'TextureFlora' / 'lipa_t1_h550_low.png'
    assert g._same_file(str(p), str(p).replace('\\', '/'))
    assert g._same_file(str(p), str(tmp_path / 'TextureFlora' / '..' / 'TextureFlora' / 'lipa_t1_h550_low.png'))
    assert g._same_file(str(p), str(p).upper()) == (str(p).upper() == str(p) or sys.platform == 'win32')
    assert not g._same_file(str(p), str(tmp_path / 'TextureFlora' / 'lipa_t1_h550_low_o.png'))


def test_mismatch_branch_still_present_for_a_different_opacity_file():
    text = (ROOT / 'adapters/max/agr_tools/flora_atlas_max.py').read_text(encoding='utf-8')
    same = text.index("_same_file(oinfo['file'], info['file'])")
    both = text.index("'both diffuse alpha and an opacity map'")
    assert same < both  # the same-file case is decided first; any other file keeps the refusal


def _core():
    spec = importlib.util.spec_from_file_location('agr_tools_atlas_core_same', ROOT / 'adapters/max/agr_tools/atlas_core.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class _Ctx(object):
    def __init__(self, options):
        self.options, self.core = options, _core()


def test_groundel_texel_option_none_only_for_npm_profile():
    import pytest
    g = _glue()
    assert g._groundel_options(_Ctx({'profile': 'npm'}), 'preview', None)['texel'] == 'ground'  # default unchanged
    assert g._groundel_options(_Ctx({'profile': 'npm', 'texel': 'none'}), 'preview', None)['texel'] == 'none'
    with pytest.raises(ValueError, match="needs profile 'npm'"):
        g._groundel_options(_Ctx({'texel': 'none'}), 'preview', None)
    with pytest.raises(ValueError, match="'ground' or 'none'"):
        g._groundel_options(_Ctx({'profile': 'npm', 'texel': 35}), 'preview', None)


def test_texel_none_routes_to_the_oks_mode_of_pack():
    text = (ROOT / 'adapters/max/agr_tools/flora_atlas_max.py').read_text(encoding='utf-8')
    assert "mode='oks' if options.get('texel') == 'none' else 'ground'" in text
