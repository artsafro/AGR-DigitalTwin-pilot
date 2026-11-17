"""new-case: tests of the mesh quality score by the OKS [D336] split rule (#1616): fixtures for slivers, n-gons, poles,
long faces and a welded vs inset element; fail-closed inputs; CLI publication; Blender read-back."""
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'qa'))
import mesh_quality_core as mq  # noqa: E402
import mesh_quality_score as cli  # noqa: E402

BLENDER = Path('C:/Program Files/Blender Foundation/Blender 5.1/blender.exe')


def _newell(pts):
    return mq._newell(pts)


class Builder:
    """Indexed mesh builder; faces are flipped to face ``want`` so concavity is well defined."""

    def __init__(self, name):
        self.name, self.verts, self.faces, self.index = name, [], [], {}

    def v(self, p, ns):
        key = (ns,) + tuple(float(c) for c in p)
        if key not in self.index:
            self.verts.append([float(c) for c in p])
            self.index[key] = len(self.verts) - 1
        return self.index[key]

    def face(self, pts, want, ns='body'):
        """Vertices are shared (welded) only inside one namespace ``ns``."""
        n = _newell(pts)
        if mq._dot(n, want) < 0:
            pts = list(reversed(pts))
        self.faces.append([self.v(p, ns) for p in pts])

    def obj(self):
        return {'name': self.name, 'verts': self.verts, 'faces': self.faces,
                'materials': ['M'] * len(self.faces)}


def wall(b, skip_col=None):
    for i in range(4):
        for k in range(4):
            if i == skip_col:
                continue
            b.face([(i, 0, k), (i + 1, 0, k), (i + 1, 0, k + 1), (i, 0, k + 1)], (0, -1, 0))


def post(b, ns):
    """A 1 m wide, 0.5 m deep post in front of wall column x=1..2, z=0..4 (4 rows)."""
    for k in range(4):
        b.face([(1, -0.5, k), (2, -0.5, k), (2, -0.5, k + 1), (1, -0.5, k + 1)], (0, -1, 0), ns)
        b.face([(1, 0, k), (1, -0.5, k), (1, -0.5, k + 1), (1, 0, k + 1)], (-1, 0, 0), ns)
        b.face([(2, 0, k), (2, -0.5, k), (2, -0.5, k + 1), (2, 0, k + 1)], (1, 0, 0), ns)


def welded_master():
    b = Builder('SM_Fixture_Main')
    wall(b, skip_col=1)
    post(b, ns='body')
    return [b.obj()]


def inset_master():
    b = Builder('SM_Fixture_Main')
    wall(b)
    post(b, ns='post')
    return [b.obj()]


def test_welded_post_scores_worse_than_inset_post():
    welded, inset = mq.score(welded_master()), mq.score(inset_master())
    assert welded['totals']['elements'] == 1 and welded['totals']['inset_elements'] == 0
    assert inset['totals']['elements'] == 2 and inset['totals']['inset_elements'] == 1
    assert welded['totals']['welded_edges'] == 8          # two concave wall/post creases x 4 rows
    assert inset['totals']['welded_edges'] == 0
    assert welded['components']['one_mesh_share'] == 1.0
    assert inset['components']['one_mesh_share'] == pytest.approx(16 / 28)
    assert welded['score'] < inset['score']
    assert welded['status'] == inset['status'] == 'measured'


def unwelded_master():
    """The post split off the wall along the same edges: the wall has a hole, nothing is inset."""
    b = Builder('SM_Fixture_Main')
    wall(b, skip_col=1)
    post(b, ns='post')
    return [b.obj()]


def test_unwelded_seam_scores_no_better_than_welded_and_below_inset():
    """Review r1 P1-2: un-welding alone must not raise the score ([D336]: the body keeps its opening)."""
    welded, unwelded, inset = (mq.score(m()) for m in (welded_master, unwelded_master, inset_master))
    assert unwelded['totals']['open_seam_edges'] == 8
    assert welded['totals']['open_seam_edges'] == inset['totals']['open_seam_edges'] == 0
    assert unwelded['totals']['elements'] == 1                     # seam-joined = one element
    assert unwelded['totals']['welded_edges'] == welded['totals']['welded_edges'] == 8
    assert unwelded['components']['open_seam_share'] > 0
    assert unwelded['score'] <= welded['score'] < inset['score']
    assert unwelded['score'] < welded['score']                     # strictly: the seam itself costs


def test_unwelded_into_another_object_is_still_a_seam():
    wall_obj, post_obj = Builder('SM_Fixture_Main'), Builder('SM_Fixture_Post')
    wall(wall_obj, skip_col=1)
    post(post_obj, ns='post')
    r = mq.score([wall_obj.obj(), post_obj.obj()])
    welded = mq.score(welded_master())
    assert r['totals']['open_seam_edges'] == 8
    assert r['totals']['elements'] == 1                             # seam-joined across objects
    assert r['totals']['welded_edges'] == welded['totals']['welded_edges'] == 8
    assert r['score'] < welded['score']                             # review r3 P1-1
    assert r['score'] < mq.score(inset_master())['score']


def cross_object_post(dy=0.0, zs=(0, 1, 2, 3, 4)):
    """Review r3 P1-1 witness: the post in ANOTHER object, ``dy`` m off the wall, rows cut at ``zs``;
    the wall keeps the hole."""
    wall_obj, post_obj = Builder('SM_Fixture_Main'), Builder('SM_Fixture_Post')
    wall(wall_obj, skip_col=1)
    for z0, z1 in zip(zs, zs[1:]):
        post_obj.face([(1, -0.5 - dy, z0), (2, -0.5 - dy, z0), (2, -0.5 - dy, z1), (1, -0.5 - dy, z1)],
                      (0, -1, 0), 'post')
        post_obj.face([(1, -dy, z0), (1, -0.5 - dy, z0), (1, -0.5 - dy, z1), (1, -dy, z1)], (-1, 0, 0), 'post')
        post_obj.face([(2, -dy, z0), (2, -0.5 - dy, z0), (2, -0.5 - dy, z1), (2, -dy, z1)], (1, 0, 0), 'post')
    return [wall_obj.obj(), post_obj.obj()]


@pytest.mark.parametrize('witness', ['dy_0', 'dy_1mm', 'dy_2mm_inclusive', 'tjunction_z0.5'])
def test_cross_object_unweld_witnesses_r3_score_below_welded_and_inset(witness):
    """Review r3 P1-1: a split into a separate object never raises the score by itself."""
    master = {'dy_0': lambda: cross_object_post(0.0), 'dy_1mm': lambda: cross_object_post(0.001),
              'dy_2mm_inclusive': lambda: cross_object_post(mq.DEFAULTS['seam_gap_m']),
              'tjunction_z0.5': lambda: cross_object_post(0.0, (0, 0.5, 1.5, 2.5, 3.5, 4))}[witness]()
    r, welded, inset = mq.score(master), mq.score(welded_master()), mq.score(inset_master())
    assert r['totals']['open_seam_edges'] >= 8
    assert r['totals']['elements'] == 1
    assert r['totals']['welded_edges'] >= welded['totals']['welded_edges']
    assert r['score'] <= welded['score'] < inset['score']
    assert r['score'] < welded['score']


def test_cross_object_inset_and_glass_controls_unchanged():
    """D336 inset is not penalised: an inset post as its own object on an intact wall keeps the inset
    score; a MainGlass pane in the opening joins nothing."""
    wall_obj, post_obj = Builder('SM_Fixture_Main'), Builder('SM_Fixture_Post')
    wall(wall_obj)
    post(post_obj, ns='post')
    r = mq.score([wall_obj.obj(), post_obj.obj()])
    assert r['totals']['open_seam_edges'] == 0 and r['totals']['elements'] == 2
    assert r['totals']['welded_edges'] == 0
    # r3 value kept (no join, no crease); one_mesh_share is per object, so a one-element object counts
    # as its own body - a pre-existing trait, not changed by r4
    assert r['score'] == 85.714 > mq.score(welded_master())['score']
    wall_obj, glass = Builder('SM_Fixture_Main'), Builder('SM_Fixture_MainGlass')
    wall(wall_obj, skip_col=1)
    for k in range(4):
        glass.face([(1, 0, k), (2, 0, k), (2, 0, k + 1), (1, 0, k + 1)], (0, -1, 0), 'glass')
    g = mq.score([wall_obj.obj(), glass.obj()])
    assert g['totals']['elements'] == 3 and g['totals']['open_seam_edges'] == 0  # wall col 0 | cols 2-3 | glass


@pytest.mark.parametrize('seed', range(30))
def test_probe_cross_object_unwelds_never_beat_welded(seed):
    """Generated probe (review r3 P1-1): post in another object, random dy in [0, seam_gap_m], random cuts."""
    import random
    rnd = random.Random(2000 + seed)
    dy = rnd.choice([0.0, mq.DEFAULTS['seam_gap_m'], rnd.uniform(0.0, mq.DEFAULTS['seam_gap_m'])])
    zs = sorted({0.0, 4.0} | {round(rnd.uniform(0.05, 3.95), 4) for _ in range(rnd.randint(0, 6))})
    r = mq.score(cross_object_post(dy, zs))
    welded, inset = mq.score(welded_master()), mq.score(inset_master())
    assert r['totals']['open_seam_edges'] >= 8 and r['totals']['elements'] == 1
    assert r['score'] < welded['score'] < inset['score']


def test_glass_pane_in_an_opening_is_not_a_seam():
    """A MainGlass pane on the edges of a body opening fills it by regulation; the wall-post case is not."""
    wall_obj, glass = Builder('SM_Fixture_Main'), Builder('SM_Fixture_MainGlass')
    wall(wall_obj, skip_col=1)
    for k in range(4):
        glass.face([(1, 0, k), (2, 0, k), (2, 0, k + 1), (1, 0, k + 1)], (0, -1, 0), 'glass')
    r = mq.score([wall_obj.obj(), glass.obj()])
    assert r['totals']['open_seam_edges'] == 0


def offset_post_master(dy):
    """Review r2 P1-1 witness: the post un-welded and moved ``dy`` m off the wall; the wall keeps the hole."""
    b = Builder('SM_Fixture_Main')
    wall(b, skip_col=1)
    for k in range(4):
        b.face([(1, -0.5 - dy, k), (2, -0.5 - dy, k), (2, -0.5 - dy, k + 1), (1, -0.5 - dy, k + 1)],
               (0, -1, 0), 'post')
        b.face([(1, -dy, k), (1, -0.5 - dy, k), (1, -0.5 - dy, k + 1), (1, -dy, k + 1)], (-1, 0, 0), 'post')
        b.face([(2, -dy, k), (2, -0.5 - dy, k), (2, -0.5 - dy, k + 1), (2, -dy, k + 1)], (1, 0, 0), 'post')
    return [b.obj()]


def interior_hole_master(dy=0.0, mode='offset'):
    """Synthetic connected wall with a true interior cell opening and a five-sided post."""
    b = Builder('SM_Interior_Main')
    for i in range(4):
        for k in range(4):
            if (i, k) != (1, 1) or mode == 'inset':
                b.face([(i, 0, k), (i + 1, 0, k), (i + 1, 0, k + 1), (i, 0, k + 1)], (0, -1, 0))
    if mode == 'empty':
        return [b.obj()]
    ns = 'body' if mode == 'welded' else 'post'
    y = -dy
    b.face([(1, y-.5, 1), (2, y-.5, 1), (2, y-.5, 2), (1, y-.5, 2)], (0, -1, 0), ns)
    for x, want in [(1, (-1, 0, 0)), (2, (1, 0, 0))]:
        b.face([(x, y, 1), (x, y-.5, 1), (x, y-.5, 2), (x, y, 2)], want, ns)
    for z, want in [(1, (0, 0, -1)), (2, (0, 0, 1))]:
        b.face([(1, y, z), (2, y, z), (2, y-.5, z), (1, y-.5, z)], want, ns)
    return [b.obj()]


@pytest.mark.parametrize('dy', [0.0, 0.002, math.nextafter(0.002, math.inf), 0.0025, 0.005, 0.01, 1.0, 100.0])
def test_body_hole_beyond_seam_gap_cannot_beat_welded(dy):
    """#1631: only a true inner loop, not a slot reaching the outer contour, is a hole."""
    result = mq.score(interior_hole_master(dy))
    welded = mq.score(interior_hole_master(mode='welded'))
    inset = mq.score(interior_hole_master(mode='inset'))
    assert result['score'] <= welded['score'] < inset['score']


def test_body_hole_without_post_is_penalized():
    r = mq.score(interior_hole_master(mode='empty'))
    assert r['score'] <= mq.score(interior_hole_master(mode='welded'))['score']


def test_open_slot_is_separate_surfaces_not_an_interior_hole():
    """REPAIR scope: no new silhouette or distance policy for separate surfaces."""
    for dy in (.0025, .005, .01, .1, 1.0):
        assert mq.score(offset_post_master(dy))['score'] == 100.0


@pytest.mark.parametrize('seed', range(30))
def test_probe_interior_hole_gap_and_frame_invariance(seed):
    """Generated independent distance/rotation/winding/object-partition probes, seed 163100..29."""
    import copy
    import random
    rnd = random.Random(163100 + seed)
    dy = 10 ** rnd.uniform(-2.6, 3)
    models = [interior_hole_master(dy), interior_hole_master(mode='welded'), interior_hole_master(mode='inset')]
    angle = rnd.uniform(-math.pi, math.pi)
    for model in models:
        obj = model[0]
        for v in obj['verts']:
            x, y, z = v
            v[:] = [x*math.cos(angle)-y*math.sin(angle), x*math.sin(angle)+y*math.cos(angle), z]
        if seed % 2:
            obj['faces'] = [list(reversed(f)) for f in obj['faces']]
    if seed % 3 == 0:
        obj = models[0][0]
        models[0] = [dict(obj, faces=obj['faces'][:15], materials=['M']*15),
                     dict(obj, name='SM_Post', faces=obj['faces'][15:], materials=['M']*5)]
    snapshot = copy.deepcopy(models)
    hole, welded, inset = [mq.score(m) for m in models]
    assert hole['totals']['body_holes'] == 1
    assert hole['score'] <= welded['score'] < inset['score']
    assert models == snapshot


@pytest.mark.parametrize('glass_kind', ['full', 'tiled', 'recessed', 'partial', 'remote', 'duplicate_half'])
def test_interior_hole_requires_complete_glass_coverage(glass_kind):
    models = interior_hole_master(mode='empty')
    g = Builder('SM_Interior_MainGlass')
    if glass_kind == 'tiled':
        ranges = [(1, 1.5), (1.5, 2)]
    elif glass_kind in ('partial', 'duplicate_half'):
        ranges = [(1, 1.5)] * (2 if glass_kind == 'duplicate_half' else 1)
    elif glass_kind == 'remote':
        ranges = [(10, 11)]
    else:
        ranges = [(1, 2)]
    y = .2 if glass_kind == 'recessed' else 0
    for i, (a, b) in enumerate(ranges):
        g.face([(a, y, 1), (b, y, 1), (b, y, 2), (a, y, 2)], (0, -1, 0), str(i))
    r = mq.score(models + [g.obj()])
    assert r['totals']['body_holes'] == int(glass_kind in ('partial', 'remote', 'duplicate_half'))
    assert r['totals']['open_seam_edges'] == 0


def test_window_reveal_is_not_missing_coplanar_body():
    obj = interior_hole_master(mode='empty')[0]
    b = Builder('SM_Reveal_Main')
    b.verts, b.faces = obj['verts'], obj['faces']
    # Preserve indexed body vertices when adding the four reveal surfaces.
    b.index = {('body',) + tuple(v): i for i, v in enumerate(b.verts)}
    loop = [(1, 0, 1), (2, 0, 1), (2, 0, 2), (1, 0, 2)]
    for a, c in zip(loop, loop[1:] + loop[:1]):
        d, e = (c[0], .2, c[2]), (a[0], .2, a[2])
        want = (1.5-(a[0]+c[0])/2, 0, 1.5-(a[2]+c[2])/2)
        b.face([a, c, d, e], want)
    r = mq.score([b.obj()])
    assert r['totals']['body_holes'] == 0
    assert r['totals']['open_seam_edges'] == 0


@pytest.mark.parametrize('height, slope, expected', [
    (0.0, 0.0, 0), (.001, 0.0, 0), (.002, 0.0, 0),
    (math.nextafter(.002, math.inf), 0.0, 1), (.003, 0.0, 1),
    (1.0, 0.0, 1), (0.0, .001, 1), (0.0, -.001, 1), (0.0, 'warped', 1),
])
def test_open_shell_base_is_an_exterior_boundary_not_a_body_hole(height, slope, expected):
    """PSU275 readback reduction: bottom rim's inner circuit is the shell's exterior opening.

    It has no enclosing coplanar FREE boundary loop; the other free contour is at the top.
    """
    b = Builder('SM_OpenShell_Main')
    outer = [(0, 0), (4, 0), (4, 4), (0, 4)]
    inner = [(.4, .4), (3.6, .4), (3.6, 3.6), (.4, 3.6)]
    for i in range(4):
        j = (i+1) % 4
        a, c = outer[i], outer[j]
        b.face([(*a, height), (*c, height), (*c, 4), (*a, 4)], (a[0]+c[0]-4, a[1]+c[1]-4, 0))
        if height:
            b.face([(*a, 0), (*c, 0), (*c, height), (*a, height)],
                   (a[0]+c[0]-4, a[1]+c[1]-4, 0))
        b.face([(*a, height), (*c, height), (*inner[j], height), (*inner[i], height)], (0, 0, -1))
    for v in b.verts:
        if .3 < v[0] < 3.7 and .3 < v[1] < 3.7:
            v[2] = height + (.001 if v[0] < 1 and v[1] < 1 else 0) if slope == 'warped' else height + slope*v[0]
    result = mq.score([b.obj()])
    assert result['totals']['body_holes'] == expected
    if expected:
        assert result['penalties']['weld_share'] == 1.0


def tjunction_post_master():
    """Review r2 P1-1 witness: post rows cut at z+0.5, so no post edge coincides with a wall hole edge."""
    b = Builder('SM_Fixture_Main')
    wall(b, skip_col=1)
    zs = [0, 0.5, 1.5, 2.5, 3.5, 4]
    for z0, z1 in zip(zs, zs[1:]):
        b.face([(1, -0.5, z0), (2, -0.5, z0), (2, -0.5, z1), (1, -0.5, z1)], (0, -1, 0), 'post')
        b.face([(1, 0, z0), (1, -0.5, z0), (1, -0.5, z1), (1, 0, z1)], (-1, 0, 0), 'post')
        b.face([(2, 0, z0), (2, -0.5, z0), (2, -0.5, z1), (2, 0, z1)], (1, 0, 0), 'post')
    return [b.obj()]


@pytest.mark.parametrize('witness', ['offset_0.2mm', 'offset_1mm', 'tjunction_z0.5'])
def test_unweld_witnesses_r2_score_no_better_than_welded_and_below_inset(witness):
    """Review r2 P1-1: near (not coincident) and T-junction seams are seams too."""
    master = {'offset_0.2mm': lambda: offset_post_master(0.0002), 'offset_1mm': lambda: offset_post_master(0.001),
              'tjunction_z0.5': tjunction_post_master}[witness]()
    r, welded, inset = mq.score(master), mq.score(welded_master()), mq.score(inset_master())
    assert r['totals']['open_seam_edges'] >= 8
    assert r['totals']['elements'] == 1                             # seam-joined = one element
    assert r['totals']['welded_edges'] >= welded['totals']['welded_edges']
    assert r['score'] <= welded['score'] < inset['score']
    assert r['score'] < welded['score']


def test_seam_gap_is_inclusive_and_beyond_is_inset():
    gap = mq.DEFAULTS['seam_gap_m']
    assert mq.score(offset_post_master(gap))['totals']['open_seam_edges'] == 8
    assert mq.score(offset_post_master(gap * 1.5))['totals']['open_seam_edges'] == 0


def test_intact_wall_and_glass_controls_have_no_near_seams():
    """Inset post on an intact wall and a pane in a body opening 1 mm off stay seam-free."""
    assert mq.score(inset_master())['totals']['open_seam_edges'] == 0
    wall_obj, glass = Builder('SM_Fixture_Main'), Builder('SM_Fixture_MainGlass')
    wall(wall_obj, skip_col=1)
    for k in range(4):
        glass.face([(1, -0.001, k), (2, -0.001, k), (2, -0.001, k + 1), (1, -0.001, k + 1)], (0, -1, 0), 'glass')
    assert mq.score([wall_obj.obj(), glass.obj()])['totals']['open_seam_edges'] == 0


def test_thin_strip_of_one_element_is_not_a_seam():
    """Two parallel boundary edges 1 mm apart inside ONE element (a thin trim) are not a seam."""
    b = Builder('SM_Strip')
    b.face([(0, 0, 0), (1, 0, 0), (1, 0, 0.001), (0, 0, 0.001)], (0, -1, 0))
    b.face([(1, 0, 0), (2, 0, 0), (2, 0, 0.001), (1, 0, 0.001)], (0, -1, 0))
    assert mq.score([b.obj()])['totals']['open_seam_edges'] == 0


@pytest.mark.parametrize('gap,seam', [(0.0, 8), (0.00004, 8), (0.001, 8), (0.05, 0)])
def test_seam_tolerance(gap, seam):
    """Within seam_gap_m (2 mm) of a body hole edge is a seam (review r2: 1 mm with the hole kept is
    gaming); a real 5 cm gap is an inset contact."""
    b = Builder('SM_Fixture_Main')
    wall(b, skip_col=1)
    for k in range(4):
        b.face([(1 + gap, -0.5, k), (2 - gap, -0.5, k), (2 - gap, -0.5, k + 1), (1 + gap, -0.5, k + 1)],
               (0, -1, 0), 'post')
        b.face([(1 + gap, -gap, k), (1 + gap, -0.5, k), (1 + gap, -0.5, k + 1), (1 + gap, -gap, k + 1)],
               (-1, 0, 0), 'post')
        b.face([(2 - gap, -gap, k), (2 - gap, -0.5, k), (2 - gap, -0.5, k + 1), (2 - gap, -gap, k + 1)],
               (1, 0, 0), 'post')
    assert mq.score([b.obj()])['totals']['open_seam_edges'] == seam


def test_irregular_area_share_by_area_not_count():
    """Non-rectangular quads (a corner more than 15 deg off 90) weighted by area (review r1 P1-1)."""
    b = Builder('SM_Irr')
    b.face([(0, 0, 0), (3, 0, 0), (3, 0, 3), (0, 0, 3)], (0, -1, 0))             # 9 m2 rectangle
    b.face([(5, 0, 0), (6, 0, 0), (6.5, 0, 1), (5.5, 0, 1)], (0, -1, 0))         # 1 m2, 63.4 deg corner
    t = math.tan(math.radians(15.0))
    b.face([(10, 0, 0), (11, 0, 0), (11 + t, 0, 1), (10 + t, 0, 1)], (0, -1, 0))  # exactly 15 deg: regular
    r = mq.score([b.obj()])
    assert r['totals']['irregular_faces'] == 1
    assert r['components']['irregular_area_share'] == pytest.approx(1 / 11)


def test_exclude_zone_complements_zone():
    full = mq.score(inset_master())
    z = [[0.5, -1, 2.5, 1]]
    inside, outside = mq.score(inset_master(), zones=z), mq.score(inset_master(), exclude_zones=z)
    assert inside['totals']['faces'] + outside['totals']['faces'] == full['totals']['faces']
    with pytest.raises(ValueError):
        mq.score(inset_master(), exclude_zones=[[1, 1, 0, 0]])


def _split_faces(obj, chosen):
    """Un-weld: faces in ``chosen`` get their own copies of their vertices (positions unchanged)."""
    verts = [list(v) for v in obj['verts']]
    copy, faces = {}, []
    for fi, f in enumerate(obj['faces']):
        if fi in chosen:
            g = []
            for i in f:
                if i not in copy:
                    verts.append(list(verts[i]))
                    copy[i] = len(verts) - 1
                g.append(copy[i])
            faces.append(g)
        else:
            faces.append(list(f))
    return {'name': obj['name'], 'verts': verts, 'faces': faces, 'materials': ['M'] * len(faces)}


@pytest.mark.parametrize('seed', range(40))
def test_probe_unwelding_any_face_subset_never_raises_the_score(seed):
    """Generated probe (review r1 P1-2): split a random face subset off a welded master -> score drops."""
    import random
    rnd = random.Random(seed)
    b = Builder('SM_Probe_Main')
    cols, rows = rnd.randint(3, 6), rnd.randint(2, 5)
    pc = rnd.randrange(cols)
    for i in range(cols):
        for k in range(rows):
            if i != pc:
                b.face([(i, 0, k), (i + 1, 0, k), (i + 1, 0, k + 1), (i, 0, k + 1)], (0, -1, 0))
    for k in range(rows):
        b.face([(pc, -0.5, k), (pc + 1, -0.5, k), (pc + 1, -0.5, k + 1), (pc, -0.5, k + 1)], (0, -1, 0))
        b.face([(pc, 0, k), (pc, -0.5, k), (pc, -0.5, k + 1), (pc, 0, k + 1)], (-1, 0, 0))
        b.face([(pc + 1, 0, k), (pc + 1, -0.5, k), (pc + 1, -0.5, k + 1), (pc + 1, 0, k + 1)], (1, 0, 0))
    welded = b.obj()
    n = len(welded['faces'])
    chosen = set(rnd.sample(range(n), rnd.randint(1, n - 1)))
    base, split = mq.score([welded]), mq.score([_split_faces(welded, chosen)])
    assert split['totals']['open_seam_edges'] > 0
    for key in ('one_mesh_share', 'weld_share', 'pole_share', 'sliver_share', 'irregular_area_share'):
        assert split['components'][key] == base['components'][key], key
    assert split['score'] < base['score']


def test_cli_exclude_zone_fail_closed(tmp_path):
    src = tmp_path / 'dump.json'
    _write_dump(src, inset_master())
    assert cli.main([str(src), '--out', str(tmp_path / 'a.json'), '--exclude-zone', '1,2,3']) == 2
    assert cli.main([str(src), '--out', str(tmp_path / 'b.json'), '--exclude-zone', '2,0,1,1']) == 2
    assert cli.main([str(src), '--out', str(tmp_path / 'c.json'), '--exclude-zone=-100,-100,100,100']) == 1
    assert not (tmp_path / 'a.json').exists() and not (tmp_path / 'b.json').exists()
    assert json.loads((tmp_path / 'c.json').read_text(encoding='utf-8'))['status'] == 'fail'


def test_sliver_triangle_and_threshold_is_strict():
    b = Builder('SM_Tri')
    b.face([(0, 0, 0), (1, 0, 0), (0, 0, 1)], (0, -1, 0))                     # 45/45/90: clean
    b.face([(5, 0, 0), (6, 0, 0), (5.5, 0, 0.02)], (0, -1, 0))                # ~2.3 deg: sliver
    t = math.tan(math.radians(10.0))
    b.face([(10, 0, 0), (11, 0, 0), (11, 0, t)], (0, -1, 0))                  # exactly 10 deg: not a sliver
    r = mq.score([b.obj()])
    assert r['totals']['tris'] == 3 and r['totals']['slivers'] == 1
    assert r['totals']['elements_not_all_quads'] == 3 and r['objects'][0]['min_element_quad_share'] == 0.0
    assert mq.score(inset_master())['objects'][0]['min_element_quad_share'] == 1.0
    assert r['components']['tri_share'] == 1.0


def test_sliver_quad_by_corner_angle():
    b = Builder('SM_Quad')
    b.face([(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)], (0, -1, 0))
    b.face([(3, 0, 0), (4, 0, 0), (7, 0, 1), (6, 0, 1)], (0, -1, 0))          # 18 deg corner
    r = mq.score([b.obj()])
    assert r['totals']['slivers'] == 1 and r['totals']['quads'] == 2


def test_ngon_is_an_error_status_fail():
    b = Builder('SM_Ngon')
    b.face([(0, 0, 0), (1, 0, 0), (2, 0, 0.5), (1, 0, 1), (0, 0, 1)], (0, -1, 0))
    r = mq.score([b.obj()])
    assert r['status'] == 'fail' and r['totals']['ngons'] == 1
    assert any('n-gon' in p for p in r['problems'])


def test_pole_from_triangle_split_into_three_quads():
    b = Builder('SM_Pole')
    a, c, e = (0, 0, 0), (2, 0, 0), (1, 0, 1.7)
    m_ac, m_ce, m_ea = (1, 0, 0), (1.5, 0, 0.85), (0.5, 0, 0.85)
    g = (1, 0, 1.7 / 3)
    for quad in ([a, m_ac, g, m_ea], [m_ac, c, m_ce, g], [g, m_ce, e, m_ea]):
        b.face(quad, (0, -1, 0))
    r = mq.score([b.obj()])
    assert r['totals']['flat_vertices'] == 1 and r['totals']['poles'] == 1
    grid = Builder('SM_Grid')
    wall(grid)
    g = mq.score([grid.obj()])
    assert g['totals']['flat_vertices'] == 9 and g['totals']['poles'] == 0


def test_long_face_limit_is_strict():
    b = Builder('SM_Long')
    b.face([(0, 0, 0), (3.9, 0, 0), (3.9, 0, 1), (0, 0, 1)], (0, -1, 0))
    b.face([(10, 0, 0), (14.0, 0, 0), (14.0, 0, 1), (10, 0, 1)], (0, -1, 0))
    assert mq.score([b.obj()])['totals']['long_faces'] == 1


def test_zone_and_collision_drop():
    objs = inset_master() + [{'name': 'UCX_SM_Fixture_Main_001', 'verts': [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                              'faces': [[0, 1, 2]]}]
    r = mq.score(objs, zones=[[0.5, -1, 2.5, 1]])
    assert r['dropped'] == [{'name': 'UCX_SM_Fixture_Main_001', 'reason': 'collision hull (UCX_)'}]
    assert 0 < r['totals']['faces'] < 28
    empty = mq.score(objs, zones=[[100, 100, 101, 101]])
    assert empty['status'] == 'fail' and empty['score'] == 0.0


@pytest.mark.parametrize('objects', [
    [],
    [{'name': 'A', 'verts': [[0, 0, float('nan')], [1, 0, 0], [0, 1, 0]], 'faces': [[0, 1, 2]]}],
    [{'name': 'A', 'verts': [[0, 0, float('inf')], [1, 0, 0], [0, 1, 0]], 'faces': [[0, 1, 2]]}],
    [{'name': 'A', 'verts': [[0, 0, 0], [1, 0, 0]], 'faces': [[0, 1, 2]]}],
    [{'name': 'A', 'verts': [[0, 0, 0], [1, 0, 0], [0, 1, 0]], 'faces': [[0, 1]]}],
    [{'name': 'A', 'verts': [[0, 0, 0], [1, 0, 0], [0, 1, 0]], 'faces': [[0, 1, 2]], 'materials': []}],
    [{'name': 'A', 'verts': [[0, 0, 0], [1, 0, 0], [0, 1, 0]], 'faces': [[0, 1, 2]]}] * 2,
    [{'name': 'A', 'verts': [], 'faces': []}],
])
def test_fail_closed_inputs(objects):
    try:
        r = mq.score(objects)
    except ValueError:
        return
    assert r['status'] == 'fail' and r['score'] == 0.0


@pytest.mark.parametrize('params', [{'nope': 1}, {'weld_deg': float('nan')}, {'side_limit_m': 0},
                                    {'tri_min_angle_deg': True}, {'body_share_ok': 1.0},
                                    {'irregular_deg': float('inf')}, {'seam_tol_m': 0}, {'seam_tol_m': -1e-4},
                                    {'seam_gap_m': 0}, {'seam_gap_m': float('nan')}, {'seam_angle_deg': 0},
                                    {'seam_angle_deg': 90}, {'seam_min_overlap_m': -1}])
def test_bad_params_and_zones_raise(params):
    with pytest.raises(ValueError):
        mq.score(inset_master(), params=params)
    with pytest.raises(ValueError):
        mq.score(inset_master(), zones=[[1, 1, 0, 0]])


def _write_dump(path, objects):
    path.write_text(json.dumps({'objects': objects, 'dropped': [], 'blender': 'recorded'}), encoding='utf-8')


def test_cli_publishes_new_report_and_refuses_aliases(tmp_path):
    src = tmp_path / 'dump.json'
    _write_dump(src, welded_master())
    before = src.read_bytes()
    out = tmp_path / 'score.json'
    assert cli.main([str(src), '--out', str(out)]) == 0
    rep = json.loads(out.read_text(encoding='utf-8'))
    assert rep['input']['sha256'] and rep['score'] == mq.score(welded_master())['score']
    assert cli.main([str(src), '--out', str(out)]) == 2            # never reuse a report
    assert cli.main([str(src), '--out', str(src)]) == 2            # alias of the input
    assert cli.main([str(tmp_path / 'm.max'), '--out', str(tmp_path / 'x.json')]) == 2
    assert cli.main([str(src), '--out', str(tmp_path / 'z.json'), '--zone', '1,2,3']) == 2
    assert src.read_bytes() == before
    assert not list(tmp_path.glob('*.partial'))


def test_cli_ngon_exits_one_fresh_process(tmp_path):
    b = Builder('SM_Ngon')
    b.face([(0, 0, 0), (1, 0, 0), (2, 0, 0.5), (1, 0, 1), (0, 0, 1)], (0, -1, 0))
    src = tmp_path / 'dump.json'
    _write_dump(src, [b.obj()])
    proc = subprocess.run([sys.executable, str(ROOT / 'tools/qa/mesh_quality_score.py'), str(src),
                           '--out', str(tmp_path / 'r.json')], capture_output=True, text=True)
    assert proc.returncode == 1 and '"fail"' in proc.stdout


def _write_obj(path, objects):
    lines, base = [], 1
    for o in objects:
        lines.append('o ' + o['name'])
        lines += ['v %r %r %r' % tuple(v) for v in o['verts']]
        lines += ['f ' + ' '.join(str(i + base) for i in f) for f in o['faces']]
        base += len(o['verts'])
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


@pytest.mark.skipif(not BLENDER.exists(), reason='Blender 5.1 not installed')
def test_blender_reads_obj_fixture_like_the_core(tmp_path):
    welded, inset = tmp_path / 'welded.obj', tmp_path / 'inset.obj'
    _write_obj(welded, welded_master())
    _write_obj(inset, inset_master())
    rw = cli.run(welded, tmp_path / 'welded.json')
    ri = cli.run(inset, tmp_path / 'inset.json')
    assert rw['totals']['elements'] == 1 and ri['totals']['elements'] == 2
    assert rw['totals']['welded_edges'] == 8 and ri['totals']['welded_edges'] == 0
    assert rw['score'] == pytest.approx(mq.score(welded_master())['score'], abs=1e-3)
    assert rw['score'] < ri['score']


@pytest.mark.skipif(not BLENDER.exists(), reason='Blender 5.1 not installed')
def test_explicit_rectangle_rejoin_restores_triangulated_grid(tmp_path):
    b = Builder('SM_Grid')
    wall(b)
    grid = b.obj()
    triangles = dict(grid, faces=[t for a, b, c, d in grid['faces'] for t in ([a, b, c], [a, c, d])])
    src = tmp_path / 'triangles.obj'
    _write_obj(src, [triangles])
    before = src.read_bytes()
    raw = cli.run(src, tmp_path / 'raw.json')
    proc = subprocess.run([sys.executable, str(ROOT / 'tools/qa/mesh_quality_score.py'),
                           str(src), '--out', str(tmp_path / 'joined.json'), '--rejoin-rectangles'],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    joined = json.loads((tmp_path / 'joined.json').read_text())
    assert raw['components']['tri_share'] == 1
    assert joined['totals']['quads'] == 16 and joined['totals']['tris'] == 0
    assert joined['score'] == mq.score([grid])['score']
    assert joined['input']['normalization']['mode'] == 'rejoin_rectangles_1deg'
    assert src.read_bytes() == before


@pytest.mark.skipif(not BLENDER.exists(), reason='Blender 5.1 not installed')
def test_rejoin_generated_rectangles_keeps_skew_and_all_objects(tmp_path):
    objects = []
    for i in range(12):
        b = Builder('Rectangle_%02d' % i)
        x, y = i * 10, i % 3
        b.face([(x, y, 0), (x + 1 + i / 10, y, 0),
                (x + 1 + i / 10, y, 1 + i / 20), (x, y, 1 + i / 20)], (0, -1, 0))
        o = b.obj()
        o['faces'] = [[0, 1, 2], [0, 2, 3]]
        objects.append(o)
    skew = Builder('Skew')
    skew.face([(150, 0, 0), (152, 0, 0), (153, 0, 1), (151, 0, 1)], (0, -1, 0))
    o = skew.obj()
    o['faces'] = [[0, 1, 2], [0, 2, 3]]
    objects.append(o)
    src = tmp_path / 'generated.obj'
    _write_obj(src, objects)
    before = cli.sha(src)
    r = cli.run(src, tmp_path / 'generated.json', rejoin_rectangles=True)
    assert {o['name'] for o in r['objects']} == {o['name'] for o in objects}
    assert r['totals']['quads'] == 12 and r['totals']['tris'] == 2
    assert r['dropped'] == [] and cli.sha(src) == before


def test_rejoin_path_aliases(tmp_path):
    src = tmp_path / 'mesh.obj'
    _write_obj(src, inset_master())
    before = src.read_bytes()
    alias = tmp_path / 'alias.obj'
    import os
    os.link(src, alias)
    with pytest.raises(ValueError, match='aliases input'):
        cli.run(src, alias, rejoin_rectangles=True)
    with pytest.raises(ValueError, match='aliases input'):
        cli.run(src, src.parent / '.' / src.name, rejoin_rectangles=True)
    assert src.read_bytes() == alias.read_bytes() == before


def test_rejoin_source_change_refuses_publication(tmp_path, monkeypatch):
    src, out = tmp_path / 'mesh.obj', tmp_path / 'score.json'
    _write_obj(src, inset_master())
    import dt_ai.core.blender_runner as runner
    def changed(*args, **kwargs):
        src.write_text('changed externally', encoding='utf-8')
        return {'objects': inset_master(), 'normalization': {'mode': 'rejoin_rectangles_1deg'}}
    monkeypatch.setattr(runner, 'run_blender', changed)
    with pytest.raises(ValueError, match='changed during measure'):
        cli.run(src, out, rejoin_rectangles=True)
    assert not out.exists()


def test_rectangle_rejoin_refuses_recorded_json(tmp_path):
    src = tmp_path / 'dump.json'
    _write_dump(src, inset_master())
    with pytest.raises(ValueError, match='native'):
        cli.run(src, tmp_path / 'out.json', rejoin_rectangles=True)
    assert not (tmp_path / 'out.json').exists()


def test_committed_g22_calibration():
    cal = json.loads((ROOT / 'docs/research/mesh-quality-1616/calibration.json').read_text(encoding='utf-8'))
    rows = {r['id']: r for r in cal['rows']}
    for suffix in ('01', '02'):
        row = rows['g22-' + suffix]
        assert row['acceptance'] == 'accepted'
        assert row['score'] >= rows['kpp1-quad-v003']['score'] + 10
        assert row['raw']['components']['tri_share'] == 1
        assert row['normalization']['mode'] == 'rejoin_rectangles_1deg'
        assert set(row['components']) == set(mq.WEIGHTS)
        assert row['typical_facade']['mode'] == 'WARN-only'
        assert row['typical_facade']['quad_share'] >= 0.95
        assert row['typical_facade']['faces'] == sum(p['faces'] for p in row['typical_facade']['parts'])
        for part in row['typical_facade']['parts']:
            assert part['quad_share'] == 1 - part['tris'] / part['faces']
            assert part['sliver_share'] == part['slivers'] / part['faces']
            assert part['quad_warning'] == (part['quad_share'] < .95)
            assert part['sliver_warning'] == (part['sliver_share'] > .005)
    assert rows['g22-02']['typical_facade']['sliver_warning'] is True
    assert len(rows['g22-02']['normalization']['objects']) == 2
    assert len(rows['g22-02']['typical_facade']['parts']) == 2


def test_committed_calibration_ranks_rejected_corners_below_accepted():
    cal = json.loads((ROOT / 'docs/research/mesh-quality-1616/calibration.json').read_text(encoding='utf-8'))
    rows = {r['id']: r for r in cal['rows']}
    rejected = rows['kpp1-quad-v003-corners']
    accepted = [r for r in rows.values() if r['acceptance'] == 'accepted']
    assert {'kpp1-quad-v003-rest', 'psu275-main'} <= {r['id'] for r in accepted}
    margin = cal['margin_points']
    assert margin > 0
    # review r1 P1-1: the corners Artem rejected rank below the v003 rest he accepted, by the stated margin
    assert all(rejected['score'] <= r['score'] - margin for r in accepted)
    assert all(r['status'] == 'measured' for r in rows.values())
    assert rows['kpp1-quad-v003-rest']['exclude_zones'] == rejected['zones'] != []
    assert cal['weights'] == mq.WEIGHTS and cal['params'] == mq.DEFAULTS
    # review r2: PSU275 (accepted) stays on top after the near-seam pass
    assert rows['psu275-main']['score'] == max(r['score'] for r in rows.values())
    assert rows['psu275-main']['totals']['open_seam_edges'] == 0


@pytest.mark.parametrize('seed', range(30))
def test_probe_near_and_tjunction_unwelds_never_beat_welded(seed):
    """Generated probe (review r2 P1-1): the post moved off by a random dy in [0, seam_gap_m] and cut at
    random heights (T-junctions) scores <= welded and < inset."""
    import random
    rnd = random.Random(1000 + seed)
    dy = rnd.uniform(0.0, mq.DEFAULTS['seam_gap_m'])
    zs = sorted({0.0, 4.0} | {round(rnd.uniform(0.05, 3.95), 4) for _ in range(rnd.randint(1, 6))})
    b = Builder('SM_Probe_Main')
    wall(b, skip_col=1)
    for z0, z1 in zip(zs, zs[1:]):
        b.face([(1, -0.5 - dy, z0), (2, -0.5 - dy, z0), (2, -0.5 - dy, z1), (1, -0.5 - dy, z1)], (0, -1, 0), 'post')
        b.face([(1, -dy, z0), (1, -0.5 - dy, z0), (1, -0.5 - dy, z1), (1, -dy, z1)], (-1, 0, 0), 'post')
        b.face([(2, -dy, z0), (2, -0.5 - dy, z0), (2, -0.5 - dy, z1), (2, -dy, z1)], (1, 0, 0), 'post')
    r = mq.score([b.obj()])
    welded, inset = mq.score(welded_master()), mq.score(inset_master())
    assert r['totals']['open_seam_edges'] >= 8 and r['totals']['elements'] == 1
    assert r['score'] <= welded['score'] < inset['score']


def test_observe_loop_uses_shared_fail_closed_command(tmp_path, monkeypatch):
    """Rule-11 guard repair only; no native improvement loop runs in this test."""
    import mesh_quality_observe as obs
    from types import SimpleNamespace
    from dt_ai.core.blender_runner import blender_command
    src = tmp_path / 'input' / 'm.blend'
    src.parent.mkdir()
    src.write_bytes(b'synthetic')
    run = tmp_path / 'run'
    monkeypatch.setattr(obs.mqs, 'run', lambda *a, **k: {'score': 80, 'components': {}})
    calls = []
    def failed(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=1, stderr='synthetic child failure')
    monkeypatch.setattr(obs.subprocess, 'run', failed)
    assert obs.main([str(src), str(run), '--angles', '80', '--blender', 'synthetic-blender']) == 0
    assert calls == [blender_command(ROOT / 'tools/blender/split_welded_parts_candidate.py',
                                    [src, run / 'round-01', '80.0'], executable='synthetic-blender')]
    rows = [json.loads(line) for line in (run / 'observe-log.jsonl').read_text().splitlines()]
    assert rows[1]['kept'] is False and rows[1]['error'] == 'synthetic child failure'
    assert src.read_bytes() == b'synthetic'


def test_observe_loop_refuses_existing_or_source_run_dir(tmp_path):
    import mesh_quality_observe as obs
    src = tmp_path / 'm.blend'
    src.write_bytes(b'x')
    with pytest.raises(SystemExit, match='exists'):
        obs.main([str(src), str(tmp_path)])
    with pytest.raises(SystemExit, match='inside the source'):
        obs.main([str(src), str(tmp_path / 'run')])
    assert src.read_bytes() == b'x'
