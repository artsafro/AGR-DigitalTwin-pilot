"""new-case: the polygon layout is readable for a human (#885 user verdict 2026-11-04 [D194]).

Every specimen sits on its own base rectangle, every base has a top camera, captions are
multi-line and do not overlap each other. Reads polygon_core.load_catalog() (the builder input: the polygon plus
the #979 station fragments test-polygon/stations/<branch>.json), not only the committed catalog.json.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _objects():
    from test_polygon_support import load_catalog
    return load_catalog()['objects']


def _rects(objects):
    out = {}
    for obj in objects:
        if obj['name'].startswith('_base_'):
            version = obj['name'][len('_base_'):].replace('_', '.')
            out[version] = obj
    return out


def _inside(pos, rect):
    return (abs(pos[0] - rect['pos'][0]) <= rect['size'][0] / 2.0
            and abs(pos[1] - rect['pos'][1]) <= rect['size'][1] / 2.0)


def test_every_specimen_sits_on_its_own_base():
    objects = _objects()
    rects = _rects(objects)
    assert rects, 'no base rectangles'
    specimens = [o for o in objects if o['scene'] == 'polygon_all' and not o['name'].startswith('_')]
    assert specimens
    outside = [o['name'] for o in specimens if not _inside(o['pos'], rects[o['base']])]
    assert outside == []


def test_every_base_has_one_top_camera_over_it():
    objects = _objects()
    rects = _rects(objects)
    cams = {o['name']: o for o in objects if o['name'].startswith('_cam_')}
    assert sorted(cams) == sorted('_cam_База ' + v for v in rects)
    for version, rect in rects.items():
        cam = cams['_cam_База ' + version]
        assert cam['superclass'] == 'camera' and cam['layer'] == '_cameras'
        assert _inside(cam['pos'], rect)
        assert cam['camera_span'] == rect['size'][:2]


def _label_box(obj):
    import polygon_core as core
    lines = obj['text'].split('\n')
    size = obj['text_size']
    w, h = core.text_width(lines, size), core.text_height(lines, size)
    x, y = obj['pos'][0], obj['pos'][1]
    return (x, y - h, x + w, y)


def test_captions_are_multiline_and_do_not_overlap():
    import sys
    sys.path.insert(0, str(ROOT / 'test-polygon'))
    objects = _objects()
    rects = _rects(objects)
    captions = [o for o in objects if o['name'].startswith('_label_') and not o['name'].startswith('_label_obj_')]
    assert captions
    for obj in captions:
        assert obj['anchor'] == 'top_left' and obj['text_size'] >= 0.8
        assert '\n' in obj['text'], obj['name']
    boxes = [(o['name'], _label_box(o)) for o in captions]
    clashes = []
    for i, (a, ba) in enumerate(boxes):
        for b, bb in boxes[i + 1:]:
            if ba[0] < bb[2] and bb[0] < ba[2] and ba[1] < bb[3] and bb[1] < ba[3]:
                clashes.append((a, b))
    assert clashes == []
    for obj in captions:
        box = _label_box(obj)
        assert any(_inside((box[0], box[1]), r) and _inside((box[2], box[3]), r) for r in rects.values()), obj['name']
