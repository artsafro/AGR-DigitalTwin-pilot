"""Regression tests for `dt qa visibility` (#1447, backlog Q10).

Fixtures are synthetic (built here); they reproduce the 4bk-k3 incidents of 2026-11-15:
- E2: a post in the 0.3 m gap between the real pylon and the skirt prism outline was deleted as hidden;
- A v007 A_OP12: a reveal visible only from a close eye was deleted as hidden.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from dt_ai.ops import visibility_gate as vg

MATS = {"transparent": ["*glass*", "*grille*"], "opaque": ["brick", "post", "reveal", "context", "stemalit"]}


def box(name, lo, hi, mat="brick"):
    """Closed box, outward normals, 6 quads."""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    v = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                  [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], dtype=np.float64)
    f = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))
    return vg.VPart(name, v, f, (mat,) * 6)


def quads(name, qs, mats):
    v, f = [], []
    for q in qs:
        f.append(tuple(range(len(v), len(v) + 4)))
        v.extend(q)
    return vg.VPart(name, np.array(v, dtype=np.float64), tuple(f), tuple(mats))


def cfg(**over):
    c = {"materials": MATS}
    c.update(over)
    return c


# ---- E2: post in the gap between the real pylon and the prism outline ---------------------------------------------

PYLON = box("Tower_Real", (0, 0, 0), (10, 10, 30), "context")
PRISM = box("Tower_Prism", (-0.3, -0.3, 0), (10.3, 10.3, 30), "context")       # skirt outline, 0.3 m off
POST = box("RoofA_RailPost", (10.1, 4.95, 0.0), (10.2, 5.05, 1.2), "post")      # in the gap, 0.1 m off the pylon


def _visible_faces(rep, part):
    p = next(x for x in rep["parts"] if x["part"] == part)
    hidden = {h["face"] for h in p["hidden"]}
    return set(range(p["faces"])) - hidden, hidden


def test_e2_post_in_prism_gap_is_visible_with_real_tower():
    rep = vg.check([POST], [PYLON], cfg())
    vis, hidden = _visible_faces(rep, "RoofA_RailPost")
    # top (1), -y (2), +x (3, away from the pylon), +y (4) are seen; the bottom (0) faces the ground
    assert {1, 2, 3, 4} <= vis, rep["parts"][0]["hidden"]
    assert 0 in hidden


def test_e2_fixture_reproduces_deletion_with_prism_occluder():
    rep = vg.check([POST], [PRISM], cfg())
    _vis, hidden = _visible_faces(rep, "RoofA_RailPost")
    assert hidden == set(range(6))          # the prism swallows the post: the old method's deletion


# ---- A v007 A_OP12: reveal seen only from a close eye ---------------------------------------------------------------

def _niche_scene():
    """Facade at x=1 with a 1 m deep niche (pane at x=0), a corridor in front closed by context planes."""
    zb, zt, yl, yr = 1.0, 2.5, -0.5, 0.5
    reveal = quads("BodyA_Reveal", [
        [(1, yl, zb), (0, yl, zb), (0, yl, zt), (1, yl, zt)],          # left reveal, normal +y
        [(0, yr, zb), (1, yr, zb), (1, yr, zt), (0, yr, zt)],          # right reveal, normal -y
    ], ["reveal", "reveal"])
    wall = quads("BodyA_Wall", [
        [(1, -6, 0), (1, yl, 0), (1, yl, 6), (1, -6, 6)],
        [(1, yr, 0), (1, 6, 0), (1, 6, 6), (1, yr, 6)],
        [(1, yl, 0), (1, yr, 0), (1, yr, zb), (1, yl, zb)],
        [(1, yl, zt), (1, yr, zt), (1, yr, 6), (1, yl, 6)],
        [(1, yl, zb), (1, yr, zb), (0, yr, zb), (0, yl, zb)],          # sill, normal +z
        [(0, yl, zt), (0, yr, zt), (1, yr, zt), (1, yl, zt)],          # head, normal -z
    ], ["brick"] * 6)
    pane = quads("WinA_Glass", [[(0, yl, zb), (0, yr, zb), (0, yr, zt), (0, yl, zt)]], ["glass"])
    # closed solid behind the facade: a box + fillers around the niche (no void behind the wall plane)
    solids = [box("B0", (-8, -6, 0), (0, 6, 6)), box("B1", (0, -6, 0), (1, yl, 6)), box("B2", (0, yr, 0), (1, 6, 6)),
              box("B3", (0, yl, 0), (1, yr, zb)), box("B4", (0, yl, zt), (1, yr, 6))]
    v, f = [], []
    for s in solids:
        f.extend(tuple(i + len(v) for i in q) for q in s.faces)
        v.extend(s.vertices.tolist())
    building = vg.VPart("Tower_Real", np.array(v, dtype=np.float64), tuple(f), ("context",) * len(f))
    corridor = quads("Corridor", [
        [(3, -6, 0), (3, 6, 0), (3, 6, 6), (3, -6, 6)],                # fence
        [(1, -6, 6), (3, -6, 6), (3, 6, 6), (1, 6, 6)],                # canopy
        [(1, -6, 0), (3, -6, 0), (3, -6, 6), (1, -6, 6)],              # end walls
        [(1, 6, 0), (3, 6, 0), (3, 6, 6), (1, 6, 6)],
    ], ["context"] * 4)
    return [reveal, wall, pane], [building, corridor]


def test_a_op12_reveal_seen_only_from_close_eye_is_visible():
    parts, ctx = _niche_scene()
    rep = vg.check(parts, ctx, cfg())
    p = next(x for x in rep["parts"] if x["part"] == "BodyA_Reveal")
    assert p["hidden"] == [], p["hidden"]
    assert {v["eye"].split(":")[0] for v in p["visible_from"]} == {"close"}


@pytest.mark.parametrize("reverse_pane", [False, True])
@pytest.mark.parametrize("reverse_parts", [False, True])
def test_reversed_pane_close_eyes_preserve_a_op12_and_e2(reverse_pane, reverse_parts):
    """Synthetic combined R2 witness: winding must not repeat A_OP12 or E2 deletion."""
    parts, ctx = _niche_scene()
    if reverse_pane:
        pane = parts[-1]
        parts[-1] = vg.VPart(pane.name, pane.vertices,
                             tuple(tuple(reversed(f)) for f in pane.faces), pane.materials)
    far = np.array([40.0, 0, 0])
    parts.append(vg.VPart(POST.name, POST.vertices + far, POST.faces, POST.materials))
    ctx.append(vg.VPart("Pylon", PYLON.vertices + far, PYLON.faces, PYLON.materials))
    if reverse_parts:
        parts.reverse()
        ctx.reverse()
    rep = vg.check(parts, ctx, cfg())
    assert rep["eyes"]["close"] == 2
    reveal = next(p for p in rep["parts"] if p["part"] == "BodyA_Reveal")
    assert reveal["hidden"] == [], reveal["hidden"]
    assert {v["eye"].split(":")[0] for v in reveal["visible_from"]} == {"close"}
    visible, hidden = _visible_faces(rep, POST.name)
    assert {1, 2, 3, 4} <= visible
    assert 0 in hidden
    assert rep == vg.check(parts, ctx, cfg())


def test_a_op12_fixture_hides_reveal_without_close_eyes():
    parts, ctx = _niche_scene()
    rep = vg.check(parts, ctx, cfg(close={"distance_m": 2.0, "radius_m": 12.0, "pane_materials": []}))
    p = next(x for x in rep["parts"] if x["part"] == "BodyA_Reveal")
    assert len(p["hidden"]) == 2


# ---- determinism ----------------------------------------------------------------------------------------------------

def test_two_runs_identical():
    parts, ctx = _niche_scene()
    far = np.array([40.0, 0, 0])
    post = vg.VPart(POST.name, POST.vertices + far, POST.faces, POST.materials)
    pylon = vg.VPart("Pylon", PYLON.vertices + far, PYLON.faces, PYLON.materials)
    a = json.dumps(vg.check(parts + [post], ctx + [pylon], cfg()), sort_keys=True)
    b = json.dumps(vg.check(parts + [post], ctx + [pylon], cfg()), sort_keys=True)
    assert a == b


def test_jitter_samples_fixed_and_inside_face():
    tri = np.array([[0, 0, 0], [2, 0, 0], [2, 1, 0], [0, 1, 0]], dtype=np.float64)
    s1, s2 = vg.face_samples(tri), vg.face_samples(tri)
    assert s1.shape == (16, 3) and np.array_equal(s1, s2)
    assert (s1[:, 0] > 0).all() and (s1[:, 0] < 2).all() and (s1[:, 1] > 0).all() and (s1[:, 1] < 1).all()
    assert len({tuple(r) for r in s1.round(9)}) == 16


# ---- first hit, front or back; transparency -------------------------------------------------------------------------

def test_back_face_blocks_ray():
    """A single-sided quad seen from its back still stops the ray (first hit, front or back)."""
    target = box("Target", (0, 0, 0), (1, 1, 1), "brick")
    lid = quads("Lid", [[(-5, -5, 3), (-5, 6, 3), (6, 6, 3), (6, -5, 3)]], ["brick"])   # normal -z: back seen from above
    rep = vg.check([target, lid], [], cfg(rings={"radii_m": [], "azimuths": 0}, ground=False,
                                         dome={"elevations_deg": [60, 80], "azimuths": 8, "zenith": True}))
    t = next(x for x in rep["parts"] if x["part"] == "Target")
    assert 1 in {h["face"] for h in t["hidden"]}                  # top of the box under the lid
    lid_r = next(x for x in rep["parts"] if x["part"] == "Lid")
    assert [b["face"] for b in lid_r["back_visible"]] == [0]


def test_glass_transparent_stemalit_opaque_context_glass_opaque():
    target = box("Target", (0, 0, 0), (1, 1, 1), "brick")
    sheet = [[(-3, -3, 2), (4, -3, 2), (4, 4, 2), (-3, 4, 2)]]
    only_dome = dict(rings={"radii_m": [], "azimuths": 0}, close={"pane_materials": []},
                     dome={"elevations_deg": [70], "azimuths": 8, "zenith": True})
    for mat, ctx, top_hidden in (("glass", False, False), ("stemalit", False, True), ("glass", True, True)):
        cover = quads("Cover", sheet, [mat])
        rep = vg.check([target], [cover], cfg(**only_dome)) if ctx else vg.check([target, cover], [], cfg(**only_dome))
        t = next(x for x in rep["parts"] if x["part"] == "Target")
        assert (1 in {h["face"] for h in t["hidden"]}) is top_hidden, (mat, ctx)


# ---- open edges -----------------------------------------------------------------------------------------------------

def _fin(depth_a, depth_b):
    """A vertical fin plane (open edges) whose left edge goes into a wall box at x<=0 by depth_a / depth_b."""
    wall = box("Wall", (-1, -2, 0), (0, 2, 3), "brick")
    fin = quads("Fin", [[(-depth_a, 0, 1), (1, 0, 1), (1, 0, 2), (-depth_b, 0, 2)]], ["post"])
    return wall, fin


def test_open_edge_embedded_class():
    wall, fin = _fin(0.012, 0.015)
    rep = vg.check([wall, fin], [], cfg())
    oe = next(x for x in rep["parts"] if x["part"] == "Fin")["open_edges"]
    assert len(oe["embedded"]) == 1 and len(oe["not_allowed"]) == 3
    d = oe["embedded"][0]["depths_m"]
    assert sorted([d["a"], d["b"]]) == pytest.approx([0.012, 0.015], abs=1e-6)
    assert d["mid"] == pytest.approx(0.0135, abs=1e-6)


@pytest.mark.parametrize("a,b", [(0.012, 0.025), (0.020, 0.012), (0.0, 0.012), (-0.01, 0.012)])
def test_open_edge_end_out_of_range_not_allowed(a, b):
    """Roof B: one end at 25 mm against 20 mm; exactly at the limit and at 0 are not allowed either."""
    wall, fin = _fin(a, b)
    rep = vg.check([wall, fin], [], cfg())
    oe = next(x for x in rep["parts"] if x["part"] == "Fin")["open_edges"]
    assert oe["embedded"] == [] and len(oe["not_allowed"]) == 4
    assert rep["passed"] is False


def test_open_edge_classes_are_data():
    wall, fin = _fin(0.012, 0.025)
    classes = [{"name": "deep_embed", "kind": "embed", "min_m": 0.0, "max_m": 0.03}]
    rep = vg.check([wall, fin], [], cfg(open_edges={"classes": classes}))
    oe = next(x for x in rep["parts"] if x["part"] == "Fin")["open_edges"]
    assert len(oe["deep_embed"]) == 1


# ---- fail-closed ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [
    lambda: vg.check([], [PYLON], cfg()),
    lambda: vg.check([POST, POST], [], cfg()),
    lambda: vg.check([POST], [box("RoofA_RailPost", (20, 0, 0), (21, 1, 1))], cfg()),
    lambda: vg.check([vg.VPart("N", POST.vertices * np.nan, POST.faces, POST.materials)], [], cfg()),
    lambda: vg.check([vg.VPart("I", POST.vertices * np.inf, POST.faces, POST.materials)], [], cfg()),
    lambda: vg.check([box("X", (0, 0, 0), (1, 1, 1), "mystery")], [], cfg()),
    lambda: vg.check([POST], [], cfg(front_n=0)),
    lambda: vg.check([POST], [], cfg(front_n=17)),
    lambda: vg.check([POST], [], cfg(jitter="eye")),
    lambda: vg.check([POST], [], cfg(unknown_key=1)),
    lambda: vg.check([POST], [], cfg(open_edges={"classes": [{"name": "x", "kind": "magic"}]})),
    lambda: vg.check([vg.VPart("F", POST.vertices, POST.faces, POST.materials[:3])], [], cfg()),
])
def test_fail_closed_inputs_raise(bad):
    with pytest.raises(ValueError):
        bad()


def test_unmapped_material_named():
    with pytest.raises(ValueError, match="mystery"):
        vg.check([box("X", (0, 0, 0), (1, 1, 1), "mystery")], [], cfg())


def test_degenerate_face_reported_as_dropped():
    p = vg.VPart("D", np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0], [5, 5, 5], [6, 5, 5], [5, 6, 5]], dtype=np.float64),
                 ((0, 1, 2), (3, 4, 5)), ("brick", "brick"))
    rep = vg.check([p], [], cfg())
    assert [d["face"] for d in rep["dropped"]] == [0]
    assert rep["passed"] is False


# ---- probes: broadphase + culls are exact; repeat runs identical --------------------------------------------------

def _random_scene(seed):
    rng = np.random.default_rng(seed)
    parts = []
    for i in range(6):
        lo = rng.uniform(-5, 5, 3)
        lo[2] = abs(lo[2])
        parts.append(box(f"B{i}", tuple(lo), tuple(lo + rng.uniform(0.2, 3, 3)), "brick"))
    for i in range(4):
        q = rng.uniform(-6, 6, (3, 3))
        q[:, 2] = np.abs(q[:, 2])
        parts.append(vg.VPart(f"T{i}", q, ((0, 1, 2),), ("glass" if i == 0 else "post",)))
    return parts


@pytest.mark.parametrize("seed", range(20))
def test_probe_occluded_matches_brute_force(seed):
    """BVH capsule broadphase + plane cull + nearest-first rounds == brute-force Moller-Trumbore over every triangle."""
    rng = np.random.default_rng(1000 + seed)
    tris = rng.uniform(-5, 5, (300, 3, 3))
    tri_face = np.arange(300) // 2
    bvh = vg.BVH(tris)
    targets = np.stack([vg.face_samples(tris[2 * k]) for k in range(150)])
    normals = np.cross(tris[0::2, 1] - tris[0::2, 0], tris[0::2, 2] - tris[0::2, 0])
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    for eye in rng.uniform(-30, 30, (3, 3)):
        got = bvh.occluded(eye, targets, np.arange(150), tri_face, 1e-4, normals, np.full(150, 1))   # need 1: never decided early, so exact
        d = targets.reshape(-1, 3) - eye
        dist = np.linalg.norm(d, axis=1)
        d /= dist[:, None]
        rr = np.repeat(np.arange(len(d)), 300)
        tt = np.tile(np.arange(300), len(d))
        th, ok = vg._mt(np.broadcast_to(eye, (len(rr), 3)), d[rr], tris[tt, 0], tris[tt, 1] - tris[tt, 0],
                        tris[tt, 2] - tris[tt, 0])
        ok &= (th > 1e-9) & (th < dist[rr] - 1e-4) & (tri_face[tt] != np.repeat(np.arange(150), 16)[rr])
        ref = np.zeros(len(d), bool)
        ref[rr[ok]] = True
        assert np.array_equal(got.reshape(-1), ref)
        for n in (4, 16):         # early decision: the n-of-16 verdict equals the brute-force verdict
            early = bvh.occluded(eye, targets, np.arange(150), tri_face, 1e-4, normals, np.full(150, n))
            assert np.array_equal((~early).sum(1) >= n, (~ref.reshape(150, 16)).sum(1) >= n)


@pytest.mark.parametrize("seed", range(5))
def test_probe_random_scene_runs_identical(seed):
    parts = _random_scene(seed)
    a = json.dumps(vg.check(parts, [], cfg()), sort_keys=True)
    assert a == json.dumps(vg.check(parts, [], cfg()), sort_keys=True)


# ---- CLI, fresh process ---------------------------------------------------------------------------------------------

def _cli(*args):
    env = dict(os.environ)
    return subprocess.run([sys.executable, "-m", "dt_ai.cli.main", "qa", "visibility", *map(str, args)],
                          capture_output=True, text=True, env=env, timeout=600)


def test_cli_npz_report_and_no_clobber(tmp_path):
    parts, ctx = _niche_scene()
    src = tmp_path / "scene.npz"
    vg.save_npz(src, parts + ctx)
    conf = tmp_path / "cfg.json"
    conf.write_text(json.dumps(cfg()), encoding="utf-8")
    out = tmp_path / "rep.json"
    r = _cli(src, "--out", out, "--context", "Tower_Real", "Corridor", "--config", conf)
    assert r.returncode in (0, 1), r.stderr
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["input"]["sha256"] and {p["part"] for p in rep["parts"]} == {"BodyA_Reveal", "BodyA_Wall", "WinA_Glass"}
    before = out.read_bytes()
    r2 = _cli(src, "--out", out, "--context", "Tower_Real", "Corridor", "--config", conf)
    assert r2.returncode == 2 and out.read_bytes() == before
    src_bytes = src.read_bytes()
    r3 = _cli(src, "--out", src, "--config", conf)
    assert r3.returncode == 2 and src.read_bytes() == src_bytes
    r4 = _cli(src, "--out", tmp_path / "r4.json", "--context", "NoSuchObject", "--config", conf)
    assert r4.returncode == 2 and "NoSuchObject" in r4.stderr and not (tmp_path / "r4.json").exists()
