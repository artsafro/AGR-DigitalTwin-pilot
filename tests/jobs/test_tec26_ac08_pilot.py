"""new-case: TEC26 AC08 pilot (#559) - finish assignment, perimeter drop, VPM/NPM colour parity, Artem's vertical-joint
panel texture at the KPP texel (1000 px/m) and the ring cuts at joint positions that make long panels fit a tile."""
import copy
import hashlib
import json
import math
import random
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "jobs/TEC26-OKS/scripts"
AC08 = ROOT / "jobs/TEC26-OKS/AC08"
sys.path.insert(0, str(SCRIPTS))
import finish_map as fm  # noqa: E402
import make_npm_atlas  # noqa: E402
import make_textures  # noqa: E402
import qa_packages  # noqa: E402

SPEC = fm.load(AC08 / "vpm_textures.json")
KPP = fm.load(ROOT / "jobs/KPP1/scripts/vpm_textures.json")
DUMP = fm.load(AC08 / "max-dump-008.json")
BODY = next(n for n in DUMP["nodes"] if n["multisub"])
SPEC_OK = SPEC  # the delivered spec is contract-valid as is (KPP 1000 px/m, no exception)
USER_TEX = Path(SPEC["finishes"]["PanelVJ_RAL5015"]["source_texture"]["path"])
needs_user_tex = pytest.mark.skipif(not USER_TEX.exists(), reason="Artem's panel texture not on this PC")


def synthetic_user_texture(tmp_path, size=4096, per=600, j=(266, 274), rgb=(34, 113, 179), seed=1):
    """SYNTHETIC stand-in for Artem's panel texture (same layout: dark 8 px joints every 600 px, flat noisy panel)."""
    rng = np.random.default_rng(seed)
    img = np.clip(np.array(rgb, float) + rng.normal(0, 1.5, (size, size, 3)), 0, 255)
    for c in range(j[0], size, per):
        img[:, c:c + j[1] - j[0]] = (12, 40, 63)
    p = tmp_path / "synthetic_panel.png"
    Image.fromarray(img.round().astype(np.uint8), "RGB").save(p)
    t = copy.deepcopy(SPEC["finishes"]["PanelVJ_RAL5015"])
    t["source_texture"].update(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest(), period_px=per,
                               first_joint_px=list(j))
    return t


def test_spec_is_valid_and_matches_kpp_palette():
    assert fm.validate_spec(SPEC_OK, KPP)
    bad = copy.deepcopy(SPEC_OK)
    bad["finishes"]["Panel_RAL5015"]["rgb"] = [34, 113, 180]
    with pytest.raises(ValueError, match="Panel_RAL5015"):
        fm.validate_spec(bad, KPP)


@pytest.mark.parametrize("mutate,match", [
    (lambda s: s["finishes"]["Door_RAL7004"].update(udim=1001), "unique"),
    (lambda s: s["source_ids"]["2"].update(finish="Nope"), "Nope"),
    (lambda s: s["empty_ids"].append(2), "mapped and empty"),
    (lambda s: s.update(zero_m=float("nan")), "zero_m"),
    (lambda s: s["finishes"]["Door_RAL7004"].update(rgb=[1, 2]), "rgb"),
    (lambda s: s.update(finishes={}), "no finishes"),
    (lambda s: s["finishes"]["PanelVJ_RAL5015"].update(P=[0.55, 0.6]), "period 600 px != P 0.55"),
    (lambda s: s["finishes"]["PanelVJ_RAL5015"].update(h_joints=True), "vertical joints only"),
    (lambda s: s["finishes"]["PanelVJ_RAL5015"].update(shift=[True, True]), "vertical joints only"),
    (lambda s: s["finishes"]["PanelVJ_RAL5015"].update(pattern="cassette"), "user_vjoints"),
    (lambda s: s["finishes"]["PanelVJ_RAL5015"].update(S=10.0), "density"),
    (lambda s: s["finishes"]["PanelVJ_RAL5015"].update(S=float("inf")), "S must"),
    (lambda s: s["finishes"]["PanelVJ_RAL5015"].update(P=[float("nan"), 0.6]), "finite periods"),
    (lambda s: s["finishes"]["PanelVJ_RAL5015"]["source_texture"].update(sha256="ABC"), "sha256"),
    (lambda s: s["finishes"]["PanelVJ_RAL5015"]["source_texture"].update(first_joint_px=[266, 273]), "malformed"),
    (lambda s: s["kpp_palette"]["PanelVJ_RAL5015"].pop("density_twin"), "density_twin"),
    (lambda s: s["kpp_palette"]["PanelVJ_RAL5015"]["density_twin"].update(kpp_finish="Metal_RAL5015", kpp_udim=1013),
     "density_twin"),
    (lambda s: s["kpp_palette"].pop("PanelVJ_RAL5015"), "kpp_palette twin"),
])
def test_spec_fail_closed(mutate, match):
    s = copy.deepcopy(SPEC_OK)
    mutate(s)
    with pytest.raises(ValueError, match=match):
        fm.validate_spec(s, KPP)


def test_dump_matches_gate1_census():
    assert (len(BODY["vertices"]), len(BODY["faces"])) == (193, 180)
    ids = {i: BODY["mat_ids"].count(i) for i in set(BODY["mat_ids"])}
    assert ids == {1: 127, 2: 15, 3: 38}


def test_assign_real_building():
    fin = fm.assign_finishes(BODY["vertices"], BODY["faces"], BODY["mat_ids"], SPEC)
    by = {}
    for m, f in zip(BODY["mat_ids"], fin):
        by.setdefault((m, f), 0)
        by[(m, f)] += 1
    # ID1 splits into the 16 perimeter-drop polygons (wall colour) and 111 roof/frame polygons
    assert by == {(1, "Panel_RAL5015"): 16, (1, "Frame_RAL7004"): 111, (2, "PanelVJ_RAL5015"): 15,
                  (3, "Door_RAL7004"): 38}


def test_assign_fail_closed():
    v, f = BODY["vertices"], BODY["faces"]
    ids = list(BODY["mat_ids"])
    with pytest.raises(ValueError, match="material ID 11 has no finish"):
        fm.assign_finishes(v, f, ids[:-1] + [11], SPEC)
    with pytest.raises(ValueError, match="ID 4 is declared empty"):
        fm.assign_finishes(v, f, [4] + ids[1:], SPEC)
    with pytest.raises(ValueError, match="no polygons"):
        fm.assign_finishes(v, [], [], SPEC)
    with pytest.raises(ValueError, match="material IDs"):
        fm.assign_finishes(v, f, ids[:-1], SPEC)
    for bad in (float("nan"), float("inf")):
        vv = copy.deepcopy(v)
        vv[0][2] = bad
        with pytest.raises(ValueError, match="non-finite"):
            fm.assign_finishes(vv, f, ids, SPEC)


def test_below_zero_threshold_is_inclusive():
    v = [[0, 0, -2.0], [1, 0, -2.0], [1, 0, 0.0], [0, 0, 0.0], [1, 0, 1e-9], [0, 0, 1e-9]]
    out = fm.assign_finishes(v, [[0, 1, 2, 3], [0, 1, 4, 5]], [1, 1], SPEC)
    assert out == ["Panel_RAL5015", "Frame_RAL7004"]  # drop below ±0.000: plain panel colour, no joints


def test_probe_random_ids_never_default():
    """Generated probe: 300 random ID vectors; every result is the declared finish or an error naming the ID."""
    rng = random.Random(559)
    v, f = BODY["vertices"], BODY["faces"]
    ok = err = 0
    for _ in range(300):
        ids = [rng.choice([1, 2, 3, 3, 2, 1, 4, 11]) if rng.random() < 0.02 else rng.choice([1, 2, 3]) for _ in f]
        bad = [i for i in ids if i not in (1, 2, 3)]
        if bad:
            with pytest.raises(ValueError, match=f"ID {bad[0]}"):
                fm.assign_finishes(v, f, ids, SPEC)
            err += 1
            continue
        out = fm.assign_finishes(v, f, ids, SPEC)
        for face, m, name in zip(f, ids, out):
            rule = SPEC["source_ids"][str(m)]
            if "finish" in rule:
                assert name == rule["finish"]
            else:
                below = max(v[k][2] for k in face) <= 0.0
                assert name == (rule["below"] if below else rule["above"])
        ok += 1
    assert ok > 0 and err > 0


def test_scope_colour_only_no_geometry_edits():
    """Artem 2026-10-22: «геометрию менять не надо» - no quadify/texel cut/weld/rebuild; the one allowed edit is the
    ring cut at joints («можно аккуратно порезать через loop или ring»), only when the spec carries ring_cuts."""
    import ast
    src = (SCRIPTS / "build_master.py").read_text(encoding="utf-8")
    calls = {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
             for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call)}
    forbidden = {"texel_cut", "pair_triangles", "join_triangles", "remove_doubles", "weld_verts", "triangulate",
                 "convex_hull", "dissolve_degenerate", "quadify"}
    assert not calls & forbidden, calls & forbidden
    assert "apply_cuts" in calls and 'spec.get("ring_cuts")' in src
    assert not hasattr(fm, "pair_triangles")
    exp = (SCRIPTS / "export_vpm.py").read_text(encoding="utf-8")
    ucx_block = exp[exp.index("for o in ucx:\n    # TEC26"):]
    assert "triangulate" not in ucx_block.split("\nfor m in")[0]


def test_perimeter_drop_real_building():
    fin = fm.assign_finishes(BODY["vertices"], BODY["faces"], BODY["mat_ids"], SPEC)
    rep = fm.perimeter_drop(BODY["vertices"], BODY["faces"], fin, "Panel_RAL5015")
    assert set(rep) == {"x-", "x+", "y-", "y+"} and all(r["ok"] for r in rep.values()), rep
    drop = [i for i, f in enumerate(BODY["faces"]) if max(BODY["vertices"][k][2] for k in f) <= 0.0]
    for i in drop:  # removing any one drop polygon opens its side
        faces = [f for j, f in enumerate(BODY["faces"]) if j != i]
        fins = [x for j, x in enumerate(fin) if j != i]
        assert not all(r["ok"] for r in fm.perimeter_drop(BODY["vertices"], faces, fins, "Panel_RAL5015").values())


def test_fresh_out_dir_refuses_aliases(tmp_path):
    spec = tmp_path / "spec.json"
    spec.write_text("{}")
    with pytest.raises(ValueError, match="aliases"):
        fm.fresh_out_dir(str(tmp_path), [str(spec)])
    with pytest.raises(ValueError, match="aliases"):
        fm.fresh_out_dir(str(spec), [str(spec)])
    (tmp_path / "old").mkdir()
    with pytest.raises(FileExistsError):
        fm.fresh_out_dir(str(tmp_path / "old"), [str(spec)])
    assert Path(fm.fresh_out_dir(str(tmp_path / "new"), [str(spec)])).is_dir()


def test_facade_uv_phase_and_winding():
    lo, hi = [0.0, 0.0], [6.0, 2.0]
    v = [[1, 0, 0], [3, 0, 0], [3, 0, 2], [1, 0, 2],          # south wall, normal -y
         [5, 2, 0], [3, 2, 0], [3, 2, 2], [5, 2, 2],          # north wall, normal +y
         [6, 0.5, -1], [6, 1.5, -1], [6, 1.5, 1], [6, 0.5, 1],  # east wall, normal +x
         [0, 0, 0], [1, 0, 0], [1, 1, 0]]                      # floor
    assert fm.facade_uv(v, [0, 1, 2, 3], lo, hi) == [(1, 0), (3, 0), (3, 2), (1, 2)]
    assert fm.facade_uv(v, [4, 5, 6, 7], lo, hi) == [(1, 0), (3, 0), (3, 2), (1, 2)]   # from the NE corner
    assert fm.facade_uv(v, [8, 9, 10, 11], lo, hi) == [(0.5, -1), (1.5, -1), (1.5, 1), (0.5, 1)]
    with pytest.raises(ValueError, match="not vertical"):
        fm.facade_uv(v, [12, 13, 14], lo, hi)
    for f in ([0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11]):  # counter-clockwise = not mirrored
        uv = fm.facade_uv(v, f, lo, hi)
        assert sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(uv, uv[1:] + uv[:1])) > 0


def _joint_columns(d):
    col = d.astype(int).sum(2).mean(0)
    return np.where(col < 0.6 * np.median(col))[0]


def test_user_vjoints_texture_synthetic(tmp_path):
    """Vertical joints only, every 600 px from tile column 0 (u' = n * 0.6 m at 1000 px/m), 8 px wide, colour kept."""
    t = synthetic_user_texture(tmp_path)
    d, alpha, erm, nrm = make_textures.make_full(t, 4096)
    assert alpha is None and d.shape == nrm.shape == erm.shape == (4096, 4096, 3)
    jc = _joint_columns(d)
    want = np.array([x for x in range(4096) if abs((x + 300) % 600 - 300 + 0.5) < 4])
    assert np.array_equal(jc, want)                       # joint centres on the 0.6 m grid, phase 0
    rows = d.astype(int).sum(2)[:, 100:200].mean(1)       # no horizontal joints anywhere
    assert rows.min() > 0.9 * np.median(rows)
    assert np.median(d.reshape(-1, 3), 0).tolist() == pytest.approx([34, 113, 179], abs=1)
    assert (nrm[:, want[0]] != [128, 128, 255]).any() and (nrm[:, 300] == [128, 128, 255]).all()
    wide = dict(t, joint_half_mm=8)                       # NPM: 16 mm joints (>= 1.5 px on the atlas)
    assert len(_joint_columns(make_textures.make_full(wide, 4096)[0])) == 2 * len(want)


def test_user_vjoints_fail_closed(tmp_path):
    t = synthetic_user_texture(tmp_path)
    bad = copy.deepcopy(t)
    bad["source_texture"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="sha256"):
        make_textures.make_full(bad, 4096)
    (tmp_path / "b").mkdir()
    off = synthetic_user_texture(tmp_path / "b", rgb=(40, 113, 179), seed=2)   # user colour != KPP: no silent fix
    with pytest.raises(ValueError, match="panel median"):
        make_textures.make_full(off, 4096)
    wrong = copy.deepcopy(t)
    wrong["source_texture"]["first_joint_px"] = [100, 108]                  # declared joint columns are not dark
    with pytest.raises(ValueError, match="not dark"):
        make_textures.make_full(wrong, 4096)
    with pytest.raises(ValueError, match="height"):
        make_textures.make_full(t, 2048)


@needs_user_tex
def test_user_vjoints_texture_artem():
    t = SPEC["finishes"]["PanelVJ_RAL5015"]
    assert hashlib.sha256(USER_TEX.read_bytes()).hexdigest() == t["source_texture"]["sha256"]
    d, _, _, _ = make_textures.make_full(t, 4096)
    want = np.array([x for x in range(4096) if abs((x + 300) % 600 - 300 + 0.5) < 4])  # half joint at 0, 6 full
    assert np.array_equal(_joint_columns(d), want) and len(want) == 4 + 6 * 8
    assert np.median(d.reshape(-1, 3), 0).tolist() == pytest.approx(KPP["finishes"]["Metal_RAL5015"]["rgb"], abs=1)
    assert round(SPEC["size_full"] / t["S"]) == round(KPP["size_full"] / KPP["finishes"]["Cassette_RAL5015"]["S"]) == 1000


@needs_user_tex
def test_vpm_and_npm_colours_match_and_kpp(tmp_path):
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(SPEC_OK), encoding="utf-8")
    vpm, npm = tmp_path / "vpm", tmp_path / "npm"
    make_textures.main(str(spec), str(vpm))
    make_npm_atlas.main(str(spec), str(npm))
    a = SPEC["address"]
    assert len(list(vpm.glob("*.png"))) == 3 * len(SPEC["finishes"])
    d = Image.open(npm / f"T_{a}_001_Main_d_1.png")
    o = Image.open(npm / f"T_{a}_001_Main_o_1.png")
    assert d.mode == "RGB" and o.mode == "RGB" and d.size == o.size == (2048, 2048)  # no alpha anywhere in NPM
    layout = json.loads((npm / "npm_atlas.json").read_text(encoding="utf-8"))
    da = np.asarray(d)
    for name, t in SPEC["finishes"].items():
        tile = np.asarray(Image.open(vpm / f"T_{a}_Diffuse_1.{t['udim']}.png"))
        r = layout["finishes"][name]
        x0, y1 = round(r["u0"] * 2048), round((1 - r["v0"]) * 2048)
        n = round(r["size"] * 2048)
        region = da[y1 - n:y1, x0:x0 + n]
        if t["kind"] == "placeholder":
            assert tile.shape == (256, 256, 3) and (tile == t["rgb"]).all()
            assert (region == t["rgb"]).all(), name
        else:  # joints survive in NPM (>= 1.5 px) and the base colour reads the same as VPM
            assert tile.shape == (4096, 4096, 3)
            assert np.abs(np.median(region.reshape(-1, 3), 0) - np.median(tile.reshape(-1, 3), 0)).max() <= 3
            col = region[n // 2, :].astype(int).sum(1)
            dark = col < 0.75 * np.median(col)
            runs = int(dark[0]) + int((dark[1:] & ~dark[:-1]).sum())
            assert runs >= int(t["S"] / t["P"][0]) - 1, runs  # every 0.6 m vertical joint is still visible in NPM
            rows = region[:, n // 2 + 5].astype(int).sum(1)
            assert rows.min() > 0.75 * np.median(rows)          # and no horizontal joint appears
            assert (np.asarray(Image.open(vpm / f"T_{a}_Normal_1.{t['udim']}.png")).shape == (4096, 4096, 3))
        kpp = KPP["finishes"][SPEC["kpp_palette"][name]["kpp_finish"]]["rgb"]
        assert t["rgb"] == kpp
    assert (np.asarray(o) == 255).all()  # no alpha-cut finish on AC08: opacity all solid
    with pytest.raises(FileExistsError):  # never overwrite a previous version
        make_npm_atlas.main(str(spec), str(npm))


# --- review #574 round 1 -------------------------------------------------------------------------------------------
def test_density_contract_is_kpp_1000():
    """P1-1 resolved by Artem 2026-10-22 («текстель как КПП VPM 1000 px/m»; cuts allowed): the panel finish delivers the
    density of KPP's patterned twin; 750 px/m (the old v006 spec) is rejected unless an approved exception exists."""
    assert fm.validate_spec(SPEC, KPP)
    old = copy.deepcopy(SPEC)
    old["finishes"]["PanelVJ_RAL5015"]["S"] = 5.461333
    with pytest.raises(ValueError, match=r"PanelVJ_RAL5015: (texel density 750.0 px/m != contract 1000.0|source period)"):
        fm.validate_spec(old, KPP)
    with pytest.raises(ValueError, match="KPP spec"):
        fm.validate_spec(SPEC)  # a KPP-twin spec cannot skip the KPP comparison
    for exc, match in (({"px_per_m": 1000.0}, "decision"), ({"px_per_m": 1000.0, "decision": "ok by me"}, "decision"),
                       ({"px_per_m": 800.0, "decision": "D1"}, "contract 800.0"),
                       ({"px_per_m": float("nan"), "decision": "D1"}, "finite"),
                       ({"px_per_m": 400.0, "decision": "D1"}, "512..1706")):
        s = copy.deepcopy(SPEC)
        s["density_exception"] = {"PanelVJ_RAL5015": exc}
        with pytest.raises(ValueError, match=match):
            fm.validate_spec(s, KPP)


# --- ring cuts at joint positions (Artem 2026-10-22) ---------------------------------------------------------------
def _real_cut():
    fins = fm.assign_finishes(BODY["vertices"], BODY["faces"], BODY["mat_ids"], SPEC)
    lo, hi = fm.body_plan_bbox(BODY["vertices"], SPEC["zero_m"])
    return fins, lo, hi, fm.apply_cuts(BODY["vertices"], BODY["faces"], fins, SPEC, lo, hi)


def _poly_area(V, f):
    n = np.zeros(3)
    p = np.asarray([V[k] for k in f], float)
    for i in range(len(p)):
        n += np.cross(p[i], p[(i + 1) % len(p)])
    return np.linalg.norm(n) / 2


def _cut_invariants(V0, F0, fins, spec, r):
    """Invariants of every ring-cut result: source vertices kept, new vertices on source edges, parent areas preserved,
    every cut polygon a quad from a source quad, no T-junction, every patterned piece fits its tile, joints at cuts."""
    V, F, par = r["vertices"], r["faces"], r["parents"]
    assert V[:len(V0)] == [list(c) for c in V0]
    edges = {tuple(sorted((f[k], f[(k + 1) % len(f)]))) for f in F0 for k in range(len(f))}
    sv = np.asarray(V0, float)
    for q in np.asarray(V[len(V0):], float):
        assert any(qa_packages._on_edge(q, sv[a], sv[b], 1e-6) for a, b in edges)
    area = {}
    for f, p in zip(F, par):
        area[p] = area.get(p, 0.0) + _poly_area(V, f)
        assert len(f) == len(F0[p])
    for p, a in area.items():
        assert a == pytest.approx(_poly_area(V0, F0[p]), abs=1e-9)
    assert sorted(set(par)) == list(range(len(F0)))
    vv = np.asarray(V, float)                                    # no vertex inside another polygon's edge
    oe = {tuple(sorted((f[k], f[(k + 1) % len(f)]))) for f in F for k in range(len(f))}
    for a, b in oe:
        for k in range(len(V)):
            if k not in (a, b):
                assert not qa_packages._on_edge(vv[k], vv[a], vv[b], 1e-7), (k, a, b)
    lo, hi = fm.body_plan_bbox(V0, spec["zero_m"])
    for f, p in zip(F, par):
        fr = r["frames"][p]
        if fr is None:
            continue
        us = [u for u, _ in fm.facade_joint_uv(V, f, fr)]
        assert fm.piece_fits(max(us) - min(us), spec, fins[p])
    for c in r["cuts"]:
        assert abs(c["u_joint_m"] / 0.6 - round(c["u_joint_m"] / 0.6)) < 1e-9


def test_ring_cut_real_building():
    fins, lo, hi, r = _real_cut()
    _cut_invariants(BODY["vertices"], BODY["faces"], fins, SPEC, r)
    assert len(r["cuts"]) == 1 and r["cuts"][0]["u_joint_m"] in (2.4, -2.4)
    c = r["cuts"][0]
    assert {34, 72, 71, 84} <= set(c["source_faces"])          # both long facades, upper + lower panel rows
    assert len(r["faces"]) == 180 + c["ring_faces"] and len(r["vertices"]) == 193 + c["new_vertices"]
    # the shared joint grid: the cut is a joint on every patterned face it crosses
    expected = fins
    shift = np.zeros(3)
    rep = qa_packages.cut_joint_report(BODY["vertices"], BODY["faces"], expected, SPEC, r["vertices"], shift)
    assert rep["ok"] and rep["new_vertices"] == c["new_vertices"] and rep["checked_on_patterned_edges"] >= 8


def _strip(xs, mirrored=False):
    """SYNTHETIC wall strip y = 0 (or its mirror y = 2 seen from +y), columns xs, rows drop/panel/frame + roof."""
    zs = [-1.2, 0.0, 2.2, 2.4]
    V, F, ids = [], [], []
    idx = {}
    for i, x in enumerate(xs):
        for j, z in enumerate(zs):
            idx[i, j] = len(V)
            V.append([x, 2.0 if mirrored else 0.0, z])
    for i in range(len(xs) - 1):
        for j in range(len(zs) - 1):
            q = [idx[i, j], idx[i + 1, j], idx[i + 1, j + 1], idx[i, j + 1]]
            F.append(q[::-1] if mirrored else q)
            ids.append({0: 1, 1: 2, 2: 1}[j])
    return V, F, ids


def test_ring_cut_probe_generated():
    """Generated probe: 200 random wall strips (both facing directions, 1..6 columns, 0.3..14 m): every result keeps the
    cut invariants, or the run fails closed with a named ValueError - never a silent partial cut."""
    rng = random.Random(55907)
    ok = err = cut = 0
    for n in range(200):
        L = rng.uniform(0.3, 14.0)
        inner = sorted(rng.uniform(0.05, L - 0.05) for _ in range(rng.randint(0, 5)))
        xs = [0.0] + inner + [L]
        if min(b - a for a, b in zip(xs, xs[1:])) < 0.02:
            continue
        V, F, ids = _strip(xs, mirrored=n % 2 == 1)
        fins = fm.assign_finishes(V, F, ids, SPEC)
        lo, hi = fm.body_plan_bbox(V, 0.0)
        try:
            r = fm.apply_cuts(V, F, fins, SPEC, lo, hi)
        except ValueError as e:
            assert "vertex" in str(e) or "fits" in str(e), e
            err += 1
            continue
        _cut_invariants(V, F, fins, SPEC, r)
        ok += 1
        cut += bool(r["cuts"])
    assert ok >= 150 and cut >= 50, (ok, err, cut)


def test_ring_cut_fail_closed():
    V, F, ids = _strip([0.0, 5.0])
    par = list(range(len(F)))
    with pytest.raises(ValueError, match="finite"):
        fm.ring_cut(V, F, par, 1, 0, float("nan"))
    with pytest.raises(ValueError, match="through a vertex"):
        fm.ring_cut(V, F, par, 1, 0, 5.0)
    with pytest.raises(ValueError, match="not crossed"):
        fm.ring_cut(V, F, par, 1, 0, 7.0)                       # plane outside the face
    tri = copy.deepcopy(F)                                     # a triangle in the ring (frame row)
    tri[2] = tri[2][:3]
    with pytest.raises(ValueError, match="not a quad"):
        fm.ring_cut(V, tri, par, 1, 0, 2.4)
    bent = copy.deepcopy(V)
    bent[F[2][2]][1] += 0.01                                   # 10 mm out of plane: cutting would change the shape
    with pytest.raises(ValueError, match="planar"):
        fm.ring_cut(bent, F, par, 1, 0, 2.4)
    nm_F = F + [[F[1][0], F[1][1], len(V), len(V) + 1]]       # third face on the panel's bottom edge
    nm_V = V + [[5.0, -1.0, -0.5], [0.0, -1.0, -0.5]]
    with pytest.raises(ValueError, match="non-manifold"):
        fm.ring_cut(nm_V, nm_F, par + [len(F)], 1, 0, 2.4)
    r = fm.ring_cut(V, F, par, 1, 0, 2.4)                      # control: whole strip cut, 3 rings faces, 4 new verts
    assert r[3]["ring_faces"] == 3 and r[3]["new_vertices"] == 4 and V == _strip([0.0, 5.0])[0]


def test_qa_ownership_after_ring_cuts():
    """Delivered = ring-cut mesh, fan triangulated, pivot shift: every triangle owns its parent polygon, areas cover each
    source polygon; a cut vertex moved 10 mm out of its face plane is unmatched; a cut moved 50 mm off the joint is
    caught by cut_joint_report; the uncut source (control) has no new vertex."""
    fins, lo, hi, r = _real_cut()
    v = np.asarray(r["vertices"], float)
    shift = np.array([(v[:193, 0].min() + v[:193, 0].max()) / 2, (v[:193, 1].min() + v[:193, 1].max()) / 2, 0.0])
    ov = (v - shift).tolist()
    of, src_of = [], []
    for f, p in zip(r["faces"], r["parents"]):
        for k in range(1, len(f) - 1):
            of.append([f[0], f[k], f[k + 1]])
            src_of.append(p)
    owners = qa_packages.match_source_faces(BODY["vertices"], BODY["faces"], ov, of, shift)
    assert [o for o in owners] == [(p,) for p in src_of]
    good = [fins[p] for p in src_of]
    pa = qa_packages.poly_areas(BODY["vertices"], BODY["faces"])
    rep = qa_packages.source_finish_report(fins, BODY["faces"], owners, good, qa_packages.tri_areas(ov, of), pa)
    assert rep["ok"], rep
    part = qa_packages.source_finish_report(fins, BODY["faces"], owners[:-1], good[:-1],
                                            qa_packages.tri_areas(ov, of[:-1]), pa)
    assert not part["ok"] and part["source_polygons_not_covered"] == 1
    g = qa_packages.geometry_report(BODY["vertices"], BODY["faces"], ov, shift, True)
    assert g["ok"] and g["new_vertices"] == r["cuts"][0]["new_vertices"]
    assert not qa_packages.geometry_report(BODY["vertices"], BODY["faces"], ov, shift, False)["ok"]  # cuts not allowed
    out = copy.deepcopy(ov)
    k = len(BODY["vertices"])                                  # first cut vertex
    out[k][1] += 0.01
    own2 = qa_packages.match_source_faces(BODY["vertices"], BODY["faces"], out, of, shift)
    assert sum(1 for o in own2 if not o) >= 1
    moved = copy.deepcopy(ov)
    for q in moved[k:]:
        q[0] += 0.05
    j = qa_packages.cut_joint_report(BODY["vertices"], BODY["faces"], fins, SPEC, moved, shift)
    assert not j["ok"] and j["off_joint_count"] >= 8
    assert qa_packages.cut_joint_report(BODY["vertices"], BODY["faces"], fins, SPEC, ov, shift)["ok"]
    src = np.asarray(BODY["vertices"], float) - shift
    ctrl = qa_packages.geometry_report(BODY["vertices"], BODY["faces"], src.tolist(), shift, False)
    assert ctrl["ok"] and ctrl["new_vertices"] == 0
    miss = qa_packages.geometry_report(BODY["vertices"], BODY["faces"], src[1:].tolist(), shift, False)
    assert not miss["ok"] and miss["missing_source_vertices"] == 1


def _delivered_from_source(split=True):
    """Export-like triangulation of the real AC08 dump: fan triangles, pivot shift, optional per-face vertex split."""
    v = np.asarray(BODY["vertices"], float)
    shift = np.array([(v[:, 0].min() + v[:, 0].max()) / 2, (v[:, 1].min() + v[:, 1].max()) / 2, 0.0])
    out_v, out_f, src_of = [], [], []
    for pi, f in enumerate(BODY["faces"]):
        if split:
            base = len(out_v)
            out_v += (v[f] - shift + 1e-5).tolist()  # FBX float noise below tolerance
            loc = list(range(base, base + len(f)))
        else:
            loc = list(f)
        for k in range(1, len(f) - 1):
            out_f.append([loc[0], loc[k], loc[k + 1]])
            src_of.append(pi)
    if not split:
        out_v = (v - shift).tolist()
    return shift, out_v, out_f, src_of


@pytest.mark.parametrize("split", [True, False])
def test_source_finish_report_catches_joint_loss(split):
    """P1-2: a delivery whose cassette triangles all show plain Panel_RAL5015 must fail against the source IDs,
    even when VPM and NPM agree; the faithful delivery (control) passes."""
    expected = fm.assign_finishes(BODY["vertices"], BODY["faces"], BODY["mat_ids"], SPEC)
    shift, ov, of, src_of = _delivered_from_source(split)
    owners = qa_packages.match_source_faces(BODY["vertices"], BODY["faces"], ov, of, shift)
    good = [expected[i] for i in src_of]
    r = qa_packages.source_finish_report(expected, BODY["faces"], owners, good)
    assert r["ok"] and r["tris"] == 348 and r["wrong_finish"] == r["ambiguous"] == r["unmatched"] == 0
    cas = sum(g == "PanelVJ_RAL5015" for g in good)
    assert cas == 30
    mut = ["Panel_RAL5015" if g == "PanelVJ_RAL5015" else g for g in good]
    r = qa_packages.source_finish_report(expected, BODY["faces"], owners, mut)
    assert not r["ok"] and r["wrong_finish"] == 30
    # below-zero split: ID1 faces at/below ±0.000 must be Panel_RAL5015, above Frame_RAL7004 - swap one of each
    below = next(t for t, i in enumerate(src_of) if BODY["mat_ids"][i] == 1 and expected[i] == "Panel_RAL5015")
    above = next(t for t, i in enumerate(src_of) if BODY["mat_ids"][i] == 1 and expected[i] == "Frame_RAL7004")
    sw = list(good)
    sw[below], sw[above] = "Frame_RAL7004", "Panel_RAL5015"
    assert qa_packages.source_finish_report(expected, BODY["faces"], owners, sw)["wrong_finish"] == 2


def test_source_finish_report_fail_closed():
    expected = fm.assign_finishes(BODY["vertices"], BODY["faces"], BODY["mat_ids"], SPEC)
    shift, ov, of, src_of = _delivered_from_source()
    good = [expected[i] for i in src_of]
    owners = qa_packages.match_source_faces(BODY["vertices"], BODY["faces"], ov, of, shift)
    assert not qa_packages.source_finish_report(expected, BODY["faces"], [], [])["ok"]  # empty
    r = qa_packages.source_finish_report(expected, BODY["faces"], owners[:-1], good[:-1])  # partial
    assert not r["ok"] and r["source_polygons_not_covered"] == 1
    moved = copy.deepcopy(ov)
    moved[of[0][0]] = [c + 0.01 for c in moved[of[0][0]]]  # a corner 10 mm off the source
    r = qa_packages.source_finish_report(
        expected, BODY["faces"], qa_packages.match_source_faces(BODY["vertices"], BODY["faces"], moved, of, shift), good)
    assert not r["ok"] and r["unmatched"] >= 1
    r = qa_packages.source_finish_report(expected, BODY["faces"], owners, [None] + good[1:])  # unmapped finish
    assert not r["ok"] and r["wrong_finish"] == 1


PILOT = Path("C:/x/tec26-oks/AC08/pilot-v007")


@pytest.mark.skipif(not (PILOT / "readback/vpm.readback.json").exists(), reason="pilot-v007 outputs not on this PC")
@pytest.mark.parametrize("variant", ["baseline", "joint_loss", "cut_off_joint", "density_750"])
def test_qa_packages_on_pilot_v007(tmp_path, variant):
    """Acceptance rows on the real pilot-v007 readbacks: the delivery passes every check; the joint-loss mutant (every
    panel triangle -> plain blue, identically in VPM and NPM) fails the source-ID checks; cut vertices moved 50 mm off
    the joint fail cuts_at_joints; the old 750 px/m spec fails the KPP texel contract."""
    spec = copy.deepcopy(SPEC)
    if variant == "density_750":
        spec["finishes"]["PanelVJ_RAL5015"]["S"] = 5.461333
    sp = tmp_path / "spec.json"
    sp.write_text(json.dumps(spec), encoding="utf-8")
    v, n = json.loads((PILOT / "readback/vpm.readback.json").read_text(encoding="utf-8")), \
        json.loads((PILOT / "readback/npm.readback.json").read_text(encoding="utf-8"))
    atlas = json.loads((PILOT / "textures-npm/npm_atlas.json").read_text(encoding="utf-8"))
    vm = next(o for o in v["objects"] if o["name"] == "SM_Nku_1_Main")
    nm = n["objects"][0]
    if variant == "joint_loss":
        r0, r1 = atlas["finishes"]["PanelVJ_RAL5015"], atlas["finishes"]["Panel_RAL5015"]
        for uv in vm["face_uvs"]:
            c = np.mean(uv, 0)
            if int(1001 + np.floor(c[0]) + 10 * np.floor(c[1])) == 1001:
                for z in uv:
                    z[0] += 1
        for uv in nm["face_uvs"]:
            c = np.mean(uv, 0)
            if r0["u0"] <= c[0] <= r0["u0"] + r0["size"] and r0["v0"] <= c[1] <= r0["v0"] + r0["size"]:
                for z in uv:
                    z[0] += r1["u0"] - r0["u0"]
                    z[1] += r1["v0"] - r0["v0"]
    if variant == "cut_off_joint":
        src = np.asarray(BODY["vertices"], float)
        shift = np.array([(src[:, 0].min() + src[:, 0].max()) / 2, (src[:, 1].min() + src[:, 1].max()) / 2, 0.0])
        for o in (vm, nm):
            for q in o["vertices"]:
                if np.abs(src - shift - np.asarray(q)).max(1).min() > 2e-4:
                    q[0] += 0.05
    (tmp_path / "v.json").write_text(json.dumps(v), encoding="utf-8")
    (tmp_path / "n.json").write_text(json.dumps(n), encoding="utf-8")
    out = tmp_path / "qa.json"
    rc = qa_packages.main([str(sp), str(PILOT / "package-vpm/SM_Nku_1.zip"), str(tmp_path / "v.json"),
                          str(PILOT / "package-npm/0000_Nku_1.zip"), str(tmp_path / "n.json"),
                          str(PILOT / "textures-npm/npm_atlas.json"), str(PILOT / "textures-vpm"),
                          str(PILOT / "textures-npm"), str(AC08 / "max-dump-008.json"), str(out)])
    failed = json.loads(out.read_text(encoding="utf-8"))["failed"]
    if variant == "baseline":
        assert (rc, failed) == (0, [])
    elif variant == "joint_loss":
        assert rc == 1 and {"source_finish_vpm", "source_finish_npm"} <= set(failed)
    elif variant == "cut_off_joint":
        assert rc == 1 and {"cuts_at_joints_vpm", "cuts_at_joints_npm"} <= set(failed)
    else:
        assert rc == 1 and "spec_contract_kpp" in failed
