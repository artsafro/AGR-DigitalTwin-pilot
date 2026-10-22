"""new-case: TEC26 AC08 pilot (#559) - finish assignment, perimeter drop, VPM/NPM colour parity, Artem's vertical-joint
panel texture at the KPP texel (1000 px/m), the ring cuts at joint positions that make long panels fit a tile, and the
rework contract (Artem 2026-10-22, PR #574 issuecomment-6342141336): rib COUNT per facade from the colour-solution sheet
(long 30 / short 12 ribs, evenly and symmetrically over the panel field, no horizontal joints), grey plinth as drawn,
counted on the delivered VPM/NPM meshes and on the renders; the old 0.60 m v007 delivery is the failing input
[D169]; the wall edging around every panel field is blue RAL 5015 with a dark outline, RAL 7004 only for door and
plinth [D170]."""
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
import joint_count  # noqa: E402
import make_npm_atlas  # noqa: E402
import make_textures  # noqa: E402
import qa_packages  # noqa: E402

SPEC = fm.load(AC08 / "vpm_textures.json")
KPP = fm.load(ROOT / "jobs/KPP1/scripts/vpm_textures.json")
DUMP = fm.load(AC08 / "max-dump-008.json")
BODY = next(n for n in DUMP["nodes"] if n["multisub"])
SPEC_OK = SPEC  # the delivered spec is contract-valid as is (KPP 1000 px/m, no exception)
SHEET = fm.load(AC08 / "sheet-facades.json")
VJ30, VJ12 = "PanelVJ30_RAL5015", "PanelVJ12_RAL5015"
P30, P12 = SPEC["finishes"][VJ30]["P"][0], SPEC["finishes"][VJ12]["P"][0]
USER_TEX = Path(SPEC["finishes"]["PanelVJ30_RAL5015"]["source_texture"]["path"])
needs_user_tex = pytest.mark.skipif(not USER_TEX.exists(), reason="Artem's panel texture not on this PC")


def synthetic_user_texture(tmp_path, size=4096, per=600, j=(266, 274), rgb=(34, 113, 179), seed=1):
    """SYNTHETIC stand-in for Artem's panel texture (same layout: dark 8 px joints every 600 px, flat noisy panel)."""
    rng = np.random.default_rng(seed)
    img = np.clip(np.array(rgb, float) + rng.normal(0, 1.5, (size, size, 3)), 0, 255)
    for c in range(j[0], size, per):
        img[:, c:c + j[1] - j[0]] = (12, 40, 63)
    p = tmp_path / "synthetic_panel.png"
    Image.fromarray(img.round().astype(np.uint8), "RGB").save(p)
    t = copy.deepcopy(SPEC["finishes"]["PanelVJ30_RAL5015"])
    t["source_texture"].update(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest(), period_px=per,
                               first_joint_px=list(j))
    return t


def test_spec_is_valid_and_matches_kpp_palette():
    assert fm.validate_spec(SPEC_OK, KPP)
    bad = copy.deepcopy(SPEC_OK)
    bad["finishes"][VJ12]["rgb"] = [34, 113, 180]
    with pytest.raises(ValueError, match=VJ12):
        fm.validate_spec(bad, KPP)


@pytest.mark.parametrize("mutate,match", [
    (lambda s: s["finishes"]["Door_RAL7004"].update(udim=1001), "unique"),
    (lambda s: s["facades"]["1-2"].update(finish="Nope"), "Nope"),
    (lambda s: s["empty_ids"].append(2), "mapped and empty"),
    (lambda s: s.update(zero_m=float("nan")), "zero_m"),
    (lambda s: s["finishes"]["Door_RAL7004"].update(rgb=[1, 2]), "rgb"),
    (lambda s: s.update(finishes={}), "no finishes"),
    (lambda s: s["finishes"]["PanelVJ30_RAL5015"].update(P=[0.55, 0.6]), r"period P \[0.55, 0.6\] != field"),
    # the superseded v007 contract: 0.60 m joints, i.e. the texture image's own 600 px spacing instead of the sheet
    (lambda s: [s["finishes"][n].update(P=[0.6, 0.6]) for n in (VJ30, VJ12)], "ribs"),
    (lambda s: s["facades"]["1-2"].update(ribs=29), "30 ribs|29 ribs"),
    (lambda s: s["facades"]["А-Б"].update(ribs=0), "ribs must be"),
    (lambda s: s["facades"]["А-Б"].update(ribs=12.0), "ribs must be"),
    (lambda s: s["facades"]["Б-А"].update(normal="-x"), "once each"),
    (lambda s: s["facades"]["2-1"].update(field_m=float("nan")), "field_m"),
    (lambda s: s["facades"]["2-1"].update(finish="Door_RAL7004"), "user_vjoints"),
    (lambda s: s.pop("facades"), "facades block|rib contract"),
    (lambda s: [s["facades"].pop(k) for k in ("А-Б", "Б-А")], "rib contract"),
    (lambda s: s["finishes"]["PanelVJ30_RAL5015"]["source_texture"].update(period_px=4), "period_px"),
    (lambda s: s["finishes"]["PanelVJ30_RAL5015"].update(h_joints=True), "vertical joints only"),
    (lambda s: s["finishes"]["PanelVJ30_RAL5015"].update(shift=[True, True]), "vertical joints only"),
    (lambda s: s["finishes"]["PanelVJ30_RAL5015"].update(pattern="cassette"), "user_vjoints"),
    (lambda s: s["finishes"]["PanelVJ30_RAL5015"].update(S=10.0), "density"),
    (lambda s: s["finishes"]["PanelVJ30_RAL5015"].update(S=float("inf")), "S must"),
    (lambda s: s["finishes"]["PanelVJ30_RAL5015"].update(P=[float("nan"), 0.6]), "finite periods|period P"),
    (lambda s: s["finishes"]["PanelVJ30_RAL5015"]["source_texture"].update(sha256="ABC"), "sha256"),
    (lambda s: s["finishes"]["PanelVJ30_RAL5015"]["source_texture"].update(first_joint_px=[266, 273]), "malformed"),
    (lambda s: s["kpp_palette"]["PanelVJ30_RAL5015"].pop("density_twin"), "density_twin"),
    (lambda s: s["kpp_palette"]["PanelVJ30_RAL5015"]["density_twin"].update(kpp_finish="Metal_RAL5015", kpp_udim=1013),
     "density_twin"),
    (lambda s: s["kpp_palette"].pop("PanelVJ30_RAL5015"), "kpp_palette twin"),
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
    # ID1 splits into the 16 perimeter-drop polygons (plinth RAL 7004) and 111 roof/frame polygons (blue RAL 5015); ID2 panels
    # by facade: long 1-2 / 2-1 (6 + 5 polygons, the door interrupts 2-1) and short A-B / B-A (2 + 2)
    assert by == {(1, "Plinth_RAL7004"): 16, (1, "Frame_RAL5015"): 111, (2, VJ30): 11, (2, VJ12): 4,
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
    assert out == ["Plinth_RAL7004", "Frame_RAL5015"]  # below ±0.000: plain plinth 7004; above: blue wall edging


def _not_vertical(v, face):
    try:
        fm.facade_key(v, face)
        return False
    except ValueError:
        return True


def test_probe_random_ids_never_default():
    """Generated probe: 300 random ID vectors; every result is the declared finish or an error naming the ID."""
    rng = random.Random(559)
    v, f = BODY["vertices"], BODY["faces"]
    ok = err = 0
    for _ in range(300):
        ids = [rng.choice([1, 2, 3, 3, 2, 1, 4, 11]) if rng.random() < 0.002
               else rng.choice([1, 3] if _not_vertical(v, face) else [1, 2, 3]) for face in f]
        # ID 2 (split facade) on a non-vertical polygon has no facade: it must fail closed naming ID 2 as well
        bad = [i for face, i in zip(f, ids) if i not in (1, 2, 3) or (i == 2 and _not_vertical(v, face))]
        if bad:
            with pytest.raises(ValueError, match=f"ID {bad[0]}"):
                fm.assign_finishes(v, f, ids, SPEC)
            err += 1
            continue
        out = fm.assign_finishes(v, f, ids, SPEC)
        for face, m, name in zip(f, ids, out):
            rule = SPEC["source_ids"][str(m)]
            if rule.get("split") == "facade":
                assert name == fm.facade_of(SPEC, fm.facade_key(v, face))[1]["finish"]
            elif "finish" in rule:
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
    rep = fm.perimeter_drop(BODY["vertices"], BODY["faces"], fin, "Plinth_RAL7004")
    assert set(rep) == {"x-", "x+", "y-", "y+"} and all(r["ok"] for r in rep.values()), rep
    drop = [i for i, f in enumerate(BODY["faces"]) if max(BODY["vertices"][k][2] for k in f) <= 0.0]
    for i in drop:  # removing any one drop polygon opens its side
        faces = [f for j, f in enumerate(BODY["faces"]) if j != i]
        fins = [x for j, x in enumerate(fin) if j != i]
        assert not all(r["ok"] for r in fm.perimeter_drop(BODY["vertices"], faces, fins, "Plinth_RAL7004").values())


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


def _want_joint_columns(P_m, size=4096, half=4):
    """Tile columns of joints at u' = k * P (k integer) with the 1:1 integer source offset floor(d)."""
    Pp = P_m * 1000
    d = (np.arange(size) + 0.5 + Pp / 2) % Pp - Pp / 2
    return np.where(np.abs(np.floor(d) + 0.5) < half)[0]


@pytest.mark.parametrize("P", [P30, P12, 0.6])
def test_user_vjoints_texture_synthetic(tmp_path, P):
    """Vertical joints only at u' = k * P from tile column 0 (1000 px/m), 8 px wide, colour kept - for the sheet pitches
    (0.19532 / 0.18628 m, NOT integer px) as well as for the source image's own 0.60 m: a period that differs from the
    image's 600 px joint spacing is not rejected, the one-joint look is repeated at the sheet contract."""
    t = synthetic_user_texture(tmp_path)
    t["P"] = [P, P]
    t.pop("outline_z_m")                                  # joints only here; the field outline is tested below
    d, alpha, erm, nrm = make_textures.make_full(t, 4096)
    assert alpha is None and d.shape == nrm.shape == erm.shape == (4096, 4096, 3)
    jc = _joint_columns(d)
    want = _want_joint_columns(P)
    assert np.array_equal(jc, want)                       # joint centres on the P grid, phase 0
    starts = [a for a, b in joint_count.runs(np.isin(np.arange(4096), jc))]
    gaps = np.diff([a for a in starts if a > 0])
    assert np.abs(gaps - P * 1000).max() <= 1.0           # even pitch to 1 px (1 mm)
    rows = d.astype(int).sum(2)[:, 100:200].mean(1)       # no horizontal joints anywhere
    assert rows.min() > 0.9 * np.median(rows)
    assert np.median(d.reshape(-1, 3), 0).tolist() == pytest.approx([34, 113, 179], abs=1)
    mid = int(round(P * 500))                             # middle of the first rib: flat normal
    edge = next(c for c in want if c > 10)                # first column of the first full joint
    assert (nrm[:, edge] != [128, 128, 255]).any() and (nrm[:, mid] == [128, 128, 255]).all()
    wide = dict(t, joint_half_mm=8)                       # NPM: 16 mm joints (>= 1.5 px on the atlas)
    wj = _joint_columns(make_textures.make_full(wide, 4096)[0])
    assert set(want) <= set(wj) and 1.8 * len(want) <= len(wj) <= 2.2 * len(want)


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
    t = SPEC["finishes"][VJ30]
    assert hashlib.sha256(USER_TEX.read_bytes()).hexdigest() == t["source_texture"]["sha256"]
    d, _, _, _ = make_textures.make_full(t, 4096)
    want = _want_joint_columns(P30)                     # half joint at 0, then every 195.32 px (sheet: 30 ribs)
    assert np.array_equal(_joint_columns(d), want) and len(want) == 4 + 20 * 8
    # Artem's ONE joint look is copied 1:1: the tile column at offset k from a joint is his column at offset k
    src = np.asarray(Image.open(USER_TEX).convert("RGB"))
    j0, j1 = t["source_texture"]["first_joint_px"]
    ce = (j0 + j1) // 2 + t["source_texture"]["period_px"]
    k = int(round(5 * P30 * 1000))                         # a tile joint centre (pixel edge) near x = 977
    oz = t["outline_z_m"]                                  # field outline rows (top / bottom edge, 4 mm inside)
    rows = d.astype(int).sum(2)[:, 100:150].mean(1)
    z = (4096 - np.arange(4096) - 0.5) / 1000
    dark = np.where(rows < 0.6 * np.median(rows))[0]
    assert set(dark) == set(np.where(((z >= oz[0]) & (z <= oz[0] + 0.004)) | ((z >= oz[1] - 0.004) & (z <= oz[1])))[0])
    assert len(dark) == 8
    inner = (z > oz[0] + 0.004) & (z < oz[1] - 0.004)
    assert np.array_equal(d[inner][:, k - 6:k + 6], src[inner][:, ce - 6:ce + 6])
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
            assert runs >= int(t["S"] / t["P"][0]) - 1, runs  # every sheet-pitch vertical joint is visible in NPM
            rows = region[:, n // 2 + 5].astype(int).sum(1)
            zr = (n - np.arange(n) - 0.5) / n * t["S"]           # world z of each region row
            dark = np.where(rows < 0.75 * np.median(rows))[0]   # only the field outline rows, no horizontal joint
            assert len(dark) and all(min(abs(zr[r] - z) for z in t["outline_z_m"]) < 1.5 * t["S"] / n for r in dark)
            assert (np.asarray(Image.open(vpm / f"T_{a}_Normal_1.{t['udim']}.png")).shape == (4096, 4096, 3))
        assert t["rgb"] == KPP["finishes"][SPEC["kpp_palette"][name]["kpp_finish"]]["rgb"]
    assert (np.asarray(o) == 255).all()  # no alpha-cut finish on AC08: opacity all solid
    with pytest.raises(FileExistsError):  # never overwrite a previous version
        make_npm_atlas.main(str(spec), str(npm))


# --- review #574 round 1 -------------------------------------------------------------------------------------------
def test_density_contract_is_kpp_1000():
    """P1-1 resolved by Artem 2026-10-22 («текстель как КПП VPM 1000 px/m»; cuts allowed): the panel finish delivers the
    density of KPP's patterned twin; 750 px/m (the old v006 spec) is rejected unless an approved exception exists."""
    assert fm.validate_spec(SPEC, KPP)
    old = copy.deepcopy(SPEC)
    old["finishes"]["PanelVJ30_RAL5015"]["S"] = 5.461333
    with pytest.raises(ValueError, match=r"PanelVJ30_RAL5015: texel density 750.0 px/m != contract 1000.0"):
        fm.validate_spec(old, KPP)
    with pytest.raises(ValueError, match="KPP spec"):
        fm.validate_spec(SPEC)  # a KPP-twin spec cannot skip the KPP comparison
    for exc, match in (({"px_per_m": 1000.0}, "decision"), ({"px_per_m": 1000.0, "decision": "ok by me"}, "decision"),
                       ({"px_per_m": 800.0, "decision": "D1"}, "contract 800.0"),
                       ({"px_per_m": float("nan"), "decision": "D1"}, "finite"),
                       ({"px_per_m": 400.0, "decision": "D1"}, "512..1706")):
        s = copy.deepcopy(SPEC)
        s["density_exception"] = {"PanelVJ30_RAL5015": exc}
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
        P = spec["finishes"][c["finish"]]["P"][0]
        assert abs(c["u_joint_m"] / P - round(c["u_joint_m"] / P)) < 1e-5     # u_joint_m is rounded to 1 um


def test_ring_cut_real_building():
    fins, lo, hi, r = _real_cut()
    _cut_invariants(BODY["vertices"], BODY["faces"], fins, SPEC, r)
    # one ring at joint 12 of the 30-rib long field (v007: 2.4 m on the superseded 0.6 m grid)
    assert len(r["cuts"]) == 1 and abs(abs(r["cuts"][0]["u_joint_m"]) - 12 * P30) < 1e-6
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


def _strip_spec(L, ribs):
    """SPEC with the long-facade rib contract re-measured for a synthetic strip of panel field L."""
    s = copy.deepcopy(SPEC)
    for k in ("1-2", "2-1"):
        s["facades"][k].update(field_m=L, ribs=ribs)
    s["finishes"][VJ30]["P"] = [L / ribs, L / ribs]
    s["finishes"][VJ30].pop("outline_z_m")     # the strip's own field heights, not AC08's
    assert fm.validate_spec(s, KPP)
    return s


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
        spec = _strip_spec(L, max(2, round(L / 0.2)))
        fins = fm.assign_finishes(V, F, ids, spec)
        lo, hi = fm.body_plan_bbox(V, 0.0)
        try:
            r = fm.apply_cuts(V, F, fins, spec, lo, hi)
        except ValueError as e:
            assert "vertex" in str(e) or "fits" in str(e), e
            err += 1
            continue
        _cut_invariants(V, F, fins, spec, r)
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
    cas = sum(g in (VJ30, VJ12) for g in good)
    assert cas == 30
    mut = ["Plinth_RAL7004" if g in (VJ30, VJ12) else g for g in good]
    r = qa_packages.source_finish_report(expected, BODY["faces"], owners, mut)
    assert not r["ok"] and r["wrong_finish"] == 30
    # pitch swap: long facades with the short facades' tile (12-rib pitch) and vice versa - same colour, wrong count
    sw = [VJ12 if g == VJ30 else VJ30 if g == VJ12 else g for g in good]
    r = qa_packages.source_finish_report(expected, BODY["faces"], owners, sw)
    assert not r["ok"] and r["wrong_finish"] == 30
    # below-zero split: ID1 faces at/below ±0.000 must be Panel_RAL5015, above Frame_RAL5015 - swap one of each
    below = next(t for t, i in enumerate(src_of) if BODY["mat_ids"][i] == 1 and expected[i] == "Plinth_RAL7004")
    above = next(t for t, i in enumerate(src_of) if BODY["mat_ids"][i] == 1 and expected[i] == "Frame_RAL5015")
    sw = list(good)
    sw[below], sw[above] = "Frame_RAL5015", "Plinth_RAL7004"
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


PILOT7 = Path("C:/x/tec26-oks/AC08/pilot-v007")   # superseded 0.60 m delivery: the FAILING input
PILOT = Path("C:/x/tec26-oks/AC08/pilot-v009")    # sheet rib counts + blue wall edging: the passing control


def _qa_run(tmp_path, pilot, spec, mutate=None):
    sp = tmp_path / "spec.json"
    sp.write_text(json.dumps(spec), encoding="utf-8")
    v, n = json.loads((pilot / "readback/vpm.readback.json").read_text(encoding="utf-8")), \
        json.loads((pilot / "readback/npm.readback.json").read_text(encoding="utf-8"))
    atlas = json.loads((pilot / "textures-npm/npm_atlas.json").read_text(encoding="utf-8"))
    vm = next(o for o in v["objects"] if o["name"] == "SM_Nku_1_Main")
    nm = n["objects"][0]
    if mutate:
        mutate(vm, nm, atlas)
    (tmp_path / "v.json").write_text(json.dumps(v), encoding="utf-8")
    (tmp_path / "n.json").write_text(json.dumps(n), encoding="utf-8")
    out = tmp_path / "qa.json"
    rc = qa_packages.main([str(sp), str(pilot / "package-vpm/SM_Nku_1.zip"), str(tmp_path / "v.json"),
                          str(pilot / "package-npm/0000_Nku_1.zip"), str(tmp_path / "n.json"),
                          str(pilot / "textures-npm/npm_atlas.json"), str(pilot / "textures-vpm"),
                          str(pilot / "textures-npm"), str(AC08 / "max-dump-008.json"), str(out)])
    return rc, json.loads(out.read_text(encoding="utf-8"))


def _in_region(uv, r):
    c = np.mean(uv, 0)
    return r["u0"] <= c[0] <= r["u0"] + r["size"] and r["v0"] <= c[1] <= r["v0"] + r["size"]


def _remap(vm, nm, atlas, pairs):
    """Mutant: triangles of finish a show finish b for every (a, b) in pairs - identically in VPM (UDIM) and NPM."""
    fin = SPEC["finishes"]
    for uv in vm["face_uvs"]:
        c = np.mean(uv, 0)
        t = int(1001 + np.floor(c[0]) + 10 * np.floor(c[1]))
        for a, b in pairs:
            if t == fin[a]["udim"]:
                for z in uv:
                    z[0] += fin[b]["udim"] - fin[a]["udim"]
                break
    for uv in nm["face_uvs"]:
        for a, b in pairs:
            r0, r1 = atlas["finishes"][a], atlas["finishes"][b]
            if _in_region(uv, r0):
                for z in uv:
                    z[0] += r1["u0"] - r0["u0"]
                    z[1] += r1["v0"] - r0["v0"]
                break


def _cut_off_joint(vm, nm, atlas):
    src = np.asarray(BODY["vertices"], float)
    shift = np.array([(src[:, 0].min() + src[:, 0].max()) / 2, (src[:, 1].min() + src[:, 1].max()) / 2, 0.0])
    for o in (vm, nm):
        for q in o["vertices"]:
            if np.abs(src - shift - np.asarray(q)).max(1).min() > 2e-4:
                q[0] += 0.05


@pytest.mark.skipif(not (PILOT / "readback/vpm.readback.json").exists(), reason="pilot-v009 outputs not on this PC")
@pytest.mark.parametrize("variant", ["baseline", "joint_loss", "pitch_swap", "cut_off_joint", "density_750",
                                     "spec_0p6"])
def test_qa_packages_on_pilot_v009(tmp_path, variant):
    """Acceptance rows on the real pilot-v009 readbacks: the delivery passes every check incl. the per-facade rib counts
    (VPM and NPM: 29 / 11 joints = 30 / 12 ribs, symmetric, no horizontal joint); mutants fail - joint loss (panels ->
    plain grey plinth), pitch swap (long facades on the 12-rib tile and vice versa: same colour, wrong count), cut
    vertices 50 mm off the joint, the old 750 px/m density, and the superseded 0.60 m spec."""
    spec = copy.deepcopy(SPEC)
    mutate = None
    if variant == "density_750":
        spec["finishes"][VJ30]["S"] = 5.461333
    if variant == "spec_0p6":
        for n in (VJ30, VJ12):
            spec["finishes"][n]["P"] = [0.6, 0.6]
    if variant == "joint_loss":
        mutate = lambda vm, nm, a: _remap(vm, nm, a, [(VJ30, "Plinth_RAL7004"), (VJ12, "Plinth_RAL7004")])  # noqa
    if variant == "pitch_swap":
        mutate = lambda vm, nm, a: _remap(vm, nm, a, [(VJ30, VJ12), (VJ12, VJ30)])  # noqa: E731
    if variant == "cut_off_joint":
        mutate = _cut_off_joint
    rc, qa = _qa_run(tmp_path, PILOT, spec, mutate)
    failed = qa["failed"]
    if variant == "baseline":
        assert (rc, failed) == (0, [])
        for tag in ("vpm", "npm"):
            d = qa["checks"][f"facade_joints_{tag}"]["detail"]
            assert set(d) == set(SPEC["facades"])
            for name, r in d.items():
                want = SPEC["facades"][name]["ribs"] - 1
                full = [row for row in r["rows"].values() if not row["hidden_by_other_finish"]]
                assert full and all(row["joints_found"] == want for row in full), (tag, name)
                assert r["symmetric"] and r["no_horizontal_joints"]
            hidden = [len(row["hidden_by_other_finish"]) for row in d["2-1"]["rows"].values()]
            assert sorted(hidden) == [0, 4]                                    # the door hides 4 joints, as drawn
    elif variant in ("joint_loss", "pitch_swap"):
        assert rc == 1 and {"source_finish_vpm", "source_finish_npm", "facade_joints_vpm",
                            "facade_joints_npm"} <= set(failed)
        for tag in ("vpm", "npm"):
            assert not any(r["ok"] for r in qa["checks"][f"facade_joints_{tag}"]["detail"].values())
    elif variant == "cut_off_joint":
        assert rc == 1 and {"cuts_at_joints_vpm", "cuts_at_joints_npm"} <= set(failed)
    else:
        assert rc == 1 and "spec_contract_kpp" in failed


@pytest.mark.skipif(not (PILOT7 / "readback/vpm.readback.json").exists(), reason="pilot-v007 outputs not on this PC")
def test_superseded_v007_delivery_fails_rib_counts():
    """The old 0.60 m v007 delivery (Artem rejected it against his facade colour reference) must fail the per-facade
    rib counts when measured exactly like v009: its VPM/NPM meshes show far fewer joints than the sheet's 29 / 11."""
    v = json.loads((PILOT7 / "readback/vpm.readback.json").read_text(encoding="utf-8"))
    n = json.loads((PILOT7 / "readback/npm.readback.json").read_text(encoding="utf-8"))
    vm = next(o for o in v["objects"] if o["name"] == "SM_Nku_1_Main")
    nm = n["objects"][0]
    atlas = json.loads((PILOT7 / "textures-npm/npm_atlas.json").read_text(encoding="utf-8"))
    tiles = {u: np.asarray(Image.open(PILOT7 / f"textures-vpm/T_Nku_1_Diffuse_1.{u}.png").convert("RGB"))
             for u in (1001, 1002, 1003, 1004)}
    a_img = np.asarray(Image.open(PILOT7 / "textures-npm/T_Nku_1_001_Main_d_1.png").convert("RGB"))
    old = copy.deepcopy(SPEC)       # v007 had ONE panel finish on tile 1001 / region PanelVJ_RAL5015 for all facades
    for k in old["facades"]:
        old["facades"][k]["finish"] = "PanelVJ_RAL5015"
    old["finishes"]["PanelVJ_RAL5015"] = dict(SPEC["finishes"][VJ30], udim=1001)
    atlas7 = {"finishes": {"PanelVJ_RAL5015": atlas["finishes"]["PanelVJ_RAL5015"]}}
    rep = qa_packages.facade_joint_checks(old, vm, nm, tiles, a_img, atlas7)
    for tag in ("vpm", "npm"):
        assert set(rep[tag]) == set(SPEC["facades"])
        for name, r in rep[tag].items():
            assert not r["ok"], (tag, name)
            found = max(row["joints_found"] for row in r["rows"].values())
            assert found < SPEC["facades"][name]["ribs"] - 1 - 3, (tag, name, found)   # 0.6 m: ~9 / ~3 joints


# --- the colour-solution sheet and the rendered counts ---------------------------------------------------------------
def test_sheet_contract_matches_spec():
    """The rib contract is read from the building's own colour-solution sheet (DWG), not from the texture image:
    long 1-2 / 2-1 = 29 joint lines = 30 ribs, short A-B / B-A = 11 = 12, inside 100 mm posts and 150 mm rails;
    spec facades carry exactly those counts, the model field within 3 mm of the sheet field, P = field / ribs."""
    f = SHEET["facades"]
    assert list(f) == ["А-Б", "1-2", "Б-А", "2-1"]
    for name, sf in f.items():
        sp = SPEC["facades"][name]
        assert sf["joints"] == sp["sheet_joints"] == sp["ribs"] - 1 and sf["ribs"] == sp["ribs"]
        assert sf["frame_bands_mm"] == {"left": 100.0, "right": 100.0, "bottom": 150.0, "top": 150.0}
        assert sf["field_width_mm"] == sp["sheet_field_mm"] and abs(sp["field_m"] * 1000 - sf["field_width_mm"]) < 3
        assert sf["drawn_steps_mm"] == [200.0] and sf["panel_rgb"] == [0, 124, 176]
        assert SPEC["finishes"][sp["finish"]]["P"][0] == pytest.approx(sp["field_m"] / sp["ribs"], abs=1e-6)
        assert {tuple(p["rgb"]) for p in sf["plinth"]} == {(155, 155, 155)}
    assert (f["1-2"]["ribs"], f["А-Б"]["ribs"]) == (30, 12)
    assert f["2-1"]["door_mm"] is not None and f["2-1"]["full_height_joints"] == 25   # the door hides 4 joints
    assert all(f[k]["door_mm"] is None for k in ("1-2", "А-Б", "Б-А"))
    assert SPEC["finishes"]["Door_RAL7004"]["rgb"] == KPP["finishes"]["Door_RAL7004"]["rgb"]


DXF = Path(SPEC["sheet"]["dxf"])


@pytest.mark.skipif(not DXF.exists(), reason="AC08 DWG readback not on this PC")
def test_sheet_reader_reproduces_committed_json():
    pytest.importorskip("ezdxf")
    import sheet_facades
    assert hashlib.sha256(DXF.read_bytes()).hexdigest() == SPEC["sheet"]["dxf_sha256"]
    got = sheet_facades.read_sheet(str(DXF))
    assert got["facades"] == SHEET["facades"]


def test_field_frames_even_symmetric_real_building():
    """Joints of the real AC08 panel fields: ribs - 1 positions at field_lo + k * field / ribs, symmetric about the
    field centre, the same grid on both long facades (one ring cut is a joint on both); the 2-1 door hides 4."""
    fins = fm.assign_finishes(BODY["vertices"], BODY["faces"], BODY["mat_ids"], SPEC)
    lo, hi = fm.body_plan_bbox(BODY["vertices"], SPEC["zero_m"])
    frames, rep = fm.field_frames(BODY["vertices"], BODY["faces"], fins, SPEC, lo, hi)
    assert set(rep) == set(SPEC["facades"])
    for name, r in rep.items():
        js = r["joints_world"]
        assert len(js) == SPEC["facades"][name]["ribs"] - 1
        mid = (r["field_lo"] + r["field_hi"]) / 2
        assert all(abs((a - mid) + (b - mid)) < 1e-5 for a, b in zip(js, js[::-1]))       # symmetric
        assert abs(js[0] - r["field_lo"] - r["pitch_m"]) < 1e-5 and abs(r["field_hi"] - js[-1] - r["pitch_m"]) < 1e-5
        assert 0.18 < r["pitch_m"] < 0.21                                               # ~0.20 m per the operator
    assert rep["1-2"]["joints_world"] == rep["2-1"]["joints_world"]
    door = [i for i, m in enumerate(BODY["mat_ids"]) if m == 3]
    dx = [BODY["vertices"][k][0] for i in door for k in BODY["faces"][i]]
    hidden = [x for x in rep["2-1"]["joints_world"] if min(dx) + 0.006 < x < max(dx) - 0.006]
    assert len(hidden) == 4
    bad = copy.deepcopy(SPEC)
    bad["facades"]["А-Б"]["field_m"] = bad["facades"]["Б-А"]["field_m"] = 2.4
    bad["finishes"][VJ12]["P"] = [0.2, 0.2]
    with pytest.raises(ValueError, match="measured panel field"):
        fm.field_frames(BODY["vertices"], BODY["faces"], fins, bad, lo, hi)


def _profile(field, P_joint, phase=None, half=0.004, step=0.0005):
    """SYNTHETIC luminance profile: Artem's panel (326) with dark 8 mm joints (115) every P_joint from `phase`."""
    s = np.arange(field[0] + step / 2, field[1], step)
    lum = np.full(s.shape, 326.0)
    x0 = field[0] if phase is None else phase
    for k in range(-1, int((field[1] - field[0]) / P_joint) + 3):
        lum[np.abs(s - (x0 + k * P_joint)) < half] = 115.0
    return s, lum


def test_count_joints_contract_and_counterexamples():
    """count_joints on SYNTHETIC profiles of the long field: the sheet contract (30 ribs evenly) passes and is
    symmetric; the superseded 0.60 m grid, a 29-rib layout and a shifted phase fail; the sheet's literal drawing
    (lines every 200 mm from the field's left edge, 58 mm last strip) is not symmetric; a door gap is hidden, not
    missing."""
    field = (0.0, 5.859505)
    s, lum = _profile(field, P30)
    r = joint_count.count_joints(s, lum, *field, 30, tol=0.003)
    assert r["ok"] and r["joints_found"] == 29 and joint_count.symmetric(r, 0.003)
    for bad in (_profile(field, 0.6), _profile(field, field[1] / 29), _profile(field, P30, phase=0.05)):
        assert not joint_count.count_joints(*bad, *field, 30, tol=0.003)["ok"]
    lit = _profile(field, 0.2, phase=0.0)                       # as drawn: 0.2 + k 0.2 from the field's left edge
    rl = joint_count.count_joints(*lit, *field, 30, tol=0.003)
    assert rl["joints_found"] == 29 and not joint_count.symmetric(rl, 0.003)
    ld = lum.copy()
    ld[(s > 4.86) & (s < 5.66)] = np.nan                        # the door
    rd = joint_count.count_joints(s, ld, *field, 30, tol=0.003)
    assert rd["ok"] and len(rd["hidden_by_other_finish"]) == 4 and rd["joints_found"] == 25


COMPARE = PILOT / "compare/compare.json"
VIEW = {"+y": "north", "-y": "south", "+x": "east", "-x": "west"}


@pytest.mark.skipif(not COMPARE.exists(), reason="pilot-v009 comparison sheets not on this PC")
def test_rendered_counts_match_sheet():
    """Mandatory before Artem's acceptance: every facade render next to its sheet facade at the same scale, counts
    written below both; the counts are MEASURED on the rendered pixels (VPM and NPM) and equal the sheet."""
    c = json.loads(COMPARE.read_text(encoding="utf-8"))
    assert set(c["facades"]) == set(SPEC["facades"]) and c["px_per_m"] == 200.0
    for name, r in c["facades"].items():
        want = SHEET["facades"][name]["joints"]
        assert r["match"] and r["sheet_dwg_joints"] == r["sheet_jpg_joints_confirmed"] == want
        assert r["vpm_render_joints"] == r["npm_render_joints"] == want and r["sheet_jpg_extra_runs"] == 0
        assert (PILOT / "compare" / r["png"]).exists()
    meta = json.loads((PILOT / "renders/renders.json").read_text(encoding="utf-8"))
    vr = json.loads((PILOT / "readback/vpm.readback.json").read_text(encoding="utf-8"))
    vm = next(o for o in vr["objects"] if o["name"] == "SM_Nku_1_Main")
    V, uvs = np.asarray(vm["vertices"], float), [np.asarray(u, float) for u in vm["face_uvs"]]
    for tag in ("vpm", "npm"):                               # independent re-measure on the rendered PNGs
        for name, fc in SPEC["facades"].items():
            view = meta[tag]["views"][VIEW[fc["normal"]]]
            img = np.asarray(Image.open(PILOT / "renders" / view["png"]).convert("RGB"))
            axis = 1 if fc["normal"] in ("+x", "-x") else 0
            ud = SPEC["finishes"][fc["finish"]]["udim"]
            tris = joint_count.facade_triangles(
                V, vm["faces"], lambda t: int(1001 + np.floor(uvs[t].mean(0)[0]) + 10 * np.floor(uvs[t].mean(0)[1])) == ud,
                fc["normal"])
            lo, hi, _, _ = joint_count.field_extent(V, vm["faces"], tris, fc["normal"])   # delivered panel field
            assert abs((hi - lo) - fc["field_m"]) < 1e-3, (tag, name, hi - lo)
            s, lum = joint_count.render_row(img, view, axis, 2.285, lo, hi)
            r = joint_count.count_joints(s, lum, lo, hi, fc["ribs"], tol=0.012, dark=0.85)
            assert r["joints_found"] == fc["ribs"] - 1 and r["ok"], (tag, name, r["joints_found"])


def test_frame_bands_outline_every_panel_field():
    """The wall edging (ID1 above ±0.000) bounds every facade panel field on all four sides - top rail, bottom rail,
    both corner posts - and is BLUE RAL 5015 like the panels (Artem 2026-10-22 on v008, all TEC26: not 7004); the
    field carries the sheet's thin dark outline (outline_z_m = the field's z range); everything at or below ±0.000 is
    the plain RAL 7004 plinth (no joints); 7004 otherwise only on the door."""
    V, F = BODY["vertices"], BODY["faces"]
    fins = fm.assign_finishes(V, F, BODY["mat_ids"], SPEC)
    lo, hi = fm.body_plan_bbox(V, SPEC["zero_m"])
    _, rep = fm.field_frames(V, F, fins, SPEC, lo, hi)
    span = lambda f, a: (min(V[k][a] for k in f), max(V[k][a] for k in f))  # noqa: E731
    for name, r in rep.items():
        key, ax = r["normal"], 0 if r["axis"] == "x" else 1
        pf = [f for f, n in zip(F, fins) if n == SPEC["facades"][name]["finish"] and fm.facade_key(V, f) == key]
        zlo, zhi = min(span(f, 2)[0] for f in pf), max(span(f, 2)[1] for f in pf)
        fr = [f for f, n in zip(F, fins) if n == "Frame_RAL5015" and not _not_vertical(V, f)
              and fm.facade_key(V, f) == key]
        sides = {"bottom": any(span(f, 2)[1] <= zlo + 1e-3 and span(f, 2)[1] > 0 for f in fr),
                 "top": any(span(f, 2)[0] >= zhi - 1e-3 for f in fr),
                 "left": any(span(f, ax)[1] <= r["field_lo"] + 1e-3 and span(f, 2)[0] < zhi for f in fr),
                 "right": any(span(f, ax)[0] >= r["field_hi"] - 1e-3 and span(f, 2)[0] < zhi for f in fr)}
        assert all(sides.values()), (name, sides)
    below = [n for f, n in zip(F, fins) if max(V[k][2] for k in f) <= SPEC["zero_m"]]
    assert below and set(below) == {"Plinth_RAL7004"} and SPEC["finishes"]["Plinth_RAL7004"]["kind"] == "placeholder"
    fin = SPEC["finishes"]
    assert fin["Frame_RAL5015"]["rgb"] == fin[VJ30]["rgb"] == fin[VJ12]["rgb"] == KPP["finishes"]["Metal_RAL5015"]["rgb"]
    assert {n for n, t in fin.items() if t["rgb"] == KPP["finishes"]["Door_RAL7004"]["rgb"]} == {"Door_RAL7004",
                                                                                                 "Plinth_RAL7004"}
    assert SPEC["source_ids"]["1"]["above"] == "Frame_RAL5015"
    for n in (VJ30, VJ12):
        assert fin[n]["outline_z_m"] == pytest.approx([min(span(f, 2)[0] for f, x in zip(F, fins) if x == n),
                                                       max(span(f, 2)[1] for f, x in zip(F, fins) if x == n)], abs=1e-5)
