"""new-case: explicit budget and exact source membership for multi-page support."""
import copy
import pytest
from tools.materials.course_grid_cut import assemble_support_pages


def inputs():
    piece = dict(source=['synthetic', 3], joint=True, patch=['synthetic', 3, 0],
                 chart_m=[[0, 0], [.02, 0], [.02, 1], [0, 1]],
                 xyz=[[0, 0, 0], [.02, 0, 0], [.02, 0, 1], [0, 0, 1]])
    parts = [dict(source=piece['source'], pieces=[piece], dropped_faces=[])]
    pages = [dict(key=piece['patch'], tile=1002, translation_m=[1, 1],
                  members=[dict(key=piece['patch'], fold_shift_m=[0, 0])])]
    return parts, dict(faces=[], unplaced=[], dropped_faces=[]), pages


def run(p=None, f=None, pages=None, **kw):
    a, b, c = inputs()
    return assemble_support_pages(a if p is None else p, b if f is None else f,
                                  c if pages is None else pages,
                                  texel_px_m=512.1, tile_px=4096,
                                  tile_budget=kw.get('tile_budget', 2))


def test_second_page_requires_explicit_budget_and_does_not_grant_qa():
    with pytest.raises(ValueError, match='budget'):
        run(tile_budget=1)
    out = run()
    assert out['passed'] is False and len(out['faces']) == 1
    assert out['faces'][0]['tile'] == 1002
    assert out['faces'][0]['uv'][0] == pytest.approx([1+512.1/4096, 512.1/4096])
    assert out['source_faces'] == 1 and not out['dropped_faces']


@pytest.mark.parametrize('mode', ['empty', 'duplicate_source', 'duplicate_member', 'unknown_member',
                                  'missing_member', 'nan', 'inf', 'unsupported_tile', 'boolean_tile',
                                  'missing_patch', 'extra_placement', 'dropped', 'unplaced', 'bad_uv'])
def test_partial_duplicate_unknown_nonfinite_inputs_refuse(mode):
    p, f, pages = inputs()
    if mode == 'empty': p = []
    elif mode == 'duplicate_source': p *= 2
    elif mode == 'duplicate_member': pages[0]['members'] *= 2
    elif mode == 'unknown_member': pages[0]['members'][0]['key'][1] = 999
    elif mode == 'missing_member': pages[0]['members'] = []
    elif mode == 'nan': pages[0]['translation_m'][0] = float('nan')
    elif mode == 'inf': pages[0]['members'][0]['fold_shift_m'][0] = float('inf')
    elif mode == 'unsupported_tile': pages[0]['tile'] = 1011
    elif mode == 'boolean_tile': pages[0]['tile'] = True
    elif mode == 'missing_patch': del p[0]['pieces'][0]['patch']
    elif mode == 'extra_placement': pages.append(copy.deepcopy(pages[0]))
    elif mode == 'dropped': p[0]['dropped_faces'] = [3]
    elif mode == 'unplaced': f['unplaced'] = [3]
    elif mode == 'bad_uv': p[0]['pieces'][0]['chart_m'][1][0] = float('nan')
    with pytest.raises(ValueError): run(p, f, pages)


def test_plain_fold_and_support_keep_every_piece_without_mutating_inputs():
    p, f, pages = inputs()
    brick = copy.deepcopy(p[0]['pieces'][0]);brick['joint'] = False;brick.pop('patch')
    brick['chart_m'] = [[2, 0], [3, 0], [3, 1], [2, 1]]
    brick['xyz'] = [[u, 0, v] for u, v in brick['chart_m']]
    p[0]['pieces'].append(brick)
    f['faces'] = [dict(object='synthetic', face=0, translation_m=[0, 1])]
    frozen = copy.deepcopy((p, f, pages))
    out = run(p, f, pages)
    assert len(out['faces']) == 2
    assert {r['tile'] for r in out['faces']} == {1001, 1002}
    assert (p, f, pages) == frozen


def test_unknown_fold_identity_names_key():
    p, f, pages = inputs()
    f['faces'] = [dict(object='ghost', face=7, translation_m=[0, 0])]
    with pytest.raises(ValueError, match='ghost'):
        run(p, f, pages)
