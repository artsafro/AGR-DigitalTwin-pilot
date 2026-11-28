"""Unit checks for the #155 keyplan-arrow reader (synthetic, no fixture inputs)."""
import importlib.util
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location('r155', Path(__file__).with_name('run.py'))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
P = dict(reg_aspect_tol=1.2, reg_min_iou=0.75, reg_min_margin=0.05, fp_res_m=0.25, outer_wall_depth_m=2.0,
         red=[200, 80, 80], grey=[190, 225, 6], tri_area_px=[800, 6000], tri_fill=[0.35, 0.7],
         tri_aspect=[1.5, 2.6], line_min_len_px=60, line_max_thick_px=6, line_max_gap_px=90,
         icon_min_area_px=3000, icon_max_dist_px=600)


def c_shape(h=80, w=200):
    m = np.ones((h, w), bool)
    m[:40, 40:80] = False          # courtyard notch open to the top (+Y), 10 m deep at 0.25 m
    return m


def test_identity_four_sides():
    fp = c_shape()
    for d, az in (((0, -1), 270), ((0, 1), 90), ((-1, 0), 0), ((1, 0), 180)):
        uv = (0.75 if d[0] == 0 else 0.5 - 0.7 * d[0], 0.5 if d[1] == 0 else 0.5 - 0.7 * d[1])
        a = R.answer(fp, d, uv, fp, P)
        assert a['az'] == az and a['wall'] == 'outer', (d, a)


def test_rotated_and_mirrored_icon_keep_face():
    fp = c_shape()
    for flip, k in R.transforms():
        icon = R.apply_mask(fp, flip, k)
        d = R.apply_vec((0, 1), flip, k)              # arrow pointing down onto the top (+Y) side
        uv = R.apply_uv(0.75, -0.2, flip, k)
        a = R.answer(icon, d, uv, fp, P)
        assert a['az'] == 90 and a['wall'] == 'outer', (flip, k, a)


def test_symmetric_icon_abstains_and_inner_wall():
    fp = c_shape()
    assert R.answer(np.ones((80, 200), bool), (0, 1), (0.5, -0.2), fp, P)['az'] is None
    a = R.answer(fp, (0, 1), (0.3, -0.2), fp, P)    # over the notch columns 40-80
    assert a['az'] == 90 and a['wall'] == 'inner' and abs(a['depth_m'] - 10.0) <= 0.5, a
    assert R.fp_inner_depths(fp, P)[90] == 10.0


def test_raster_reader_finds_arrow_line_icon():
    img = np.full((900, 1200, 3), 253, np.uint8)
    icon = np.kron(c_shape(), np.ones((2, 2), bool))          # 160 x 400 px
    img[200:360, 300:700][icon] = (208, 209, 210)
    img[400:402, 300:700] = (255, 0, 0)                       # red line below the icon
    for i in range(30):                                       # triangle under the line, apex up
        img[450 - i // 2 * 2 + 0:452 - i // 2 * 2, 470 + i:530 - i] = (255, 0, 0) if 470 + i < 530 - i else 253
    tri = R.triangles(img, P)
    assert len(tri) == 1 and tri[0]['d'] == (0, -1), [t['d'] for t in tri]
    row = R.read(img, tri[0]['c'], c_shape(), P)
    assert row['status'] == 'read' and row['line'] and row['az'] == 270 and row['wall'] == 'outer', row
