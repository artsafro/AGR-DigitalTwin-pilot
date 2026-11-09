"""new-case: COD Gate 1 source mapping, independent of workstation DWGs."""
from pathlib import Path

from adapters.cad.spozu import load_config


def test_cod_approved_source_mapping():
    cfg = load_config(Path(__file__).parents[1] / 'adapters/cad/configs/cod_20207.yaml')
    assert cfg.project == 'cod-20207'
    assert cfg.boundary_handle == '69002'
    assert cfg.boundary_layer == 'ГП_Граница участка'
    assert {c.type: c.layers for c in cfg.coverings} == {
        'asphalt': ('ГП_Благо_ТИП_1',),
        'tile': ('ГП_Благо_ТИП_2',),
        'tile_reinforced': ('ГП_Благо_ТИП_3',),
        'geogrid': ('ГП_Благо_ТИП_4',),
        'geogrid_reinforced': ('ГП_Благо_ТИП_5',),
        'type6': ('ГП_Благо_ТИП_6',),
    }
    assert [c.type for c in cfg.coverings if c.repair] == ['tile_reinforced']
    assert not cfg.elevation_layers and not cfg.contour_layers and not cfg.elevation_containers
    assert cfg.ground_elements == {
        'curb_drive': ('ГП_БР дорожный',), 'curb_garden': ('ГП_БР сад',),
    }
