"""new-case: TEC26 AC08 pilot (#559) - finish assignment, quad pairing, perimeter drop, VPM/NPM colour parity."""
import copy
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
# SYNTHETIC test fixture: the delivered 750 px/m spec with a made-up approved exception, used only where a test needs a
# contract-valid spec (texture generators, fail-closed mutations). It is NOT a user decision.
SPEC_OK = copy.deepcopy(SPEC)
SPEC_OK["density_exception"] = {"Cassette_RAL5015": {"px_per_m": 750.0, "decision": "D0"}}


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
    (lambda s: s["finishes"]["Cassette_RAL5015"].update(P=[0.6, 0.6]), "P"),
    (lambda s: s["finishes"]["Cassette_RAL5015"].update(h_joints=False), "h_joints"),
    (lambda s: s["finishes"]["Cassette_RAL5015"].update(S=10.0), "density"),
    (lambda s: s["finishes"]["Cassette_RAL5015"].update(S=float("inf")), "S must"),
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
    assert by == {(1, "Panel_RAL5015"): 16, (1, "Frame_RAL7004"): 111, (2, "Cassette_RAL5015"): 15,
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
    """Artem 2026-10-22: «геометрию менять не надо» - the build keeps source polygons; no quadify/cut/weld/rebuild."""
    import ast
    src = (SCRIPTS / "build_master.py").read_text(encoding="utf-8")
    calls = {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
             for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call)}
    forbidden = {"texel_cut", "pair_triangles", "join_triangles", "remove_doubles", "weld_verts", "triangulate",
                 "convex_hull", "dissolve_degenerate", "quadify"}
    assert not calls & forbidden, calls & forbidden
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


def test_cassette_is_the_kpp_recipe_at_750px():
    t, k = SPEC["finishes"]["Cassette_RAL5015"], KPP["finishes"]["Cassette_RAL5015"]
    assert {x: t[x] for x in ("pattern", "P", "h_joints", "rgb", "rough", "metal")} == \
        {x: k[x] for x in ("pattern", "P", "h_joints", "rgb", "rough", "metal")}
    assert t["phase"] == [0.0, 0.0] and round(SPEC["size_full"] / t["S"]) == 750
    d, _, _, _ = make_textures.make_full(t, 4096)
    v = (4096 - np.arange(4096) - 0.5) * t["S"] / 4096        # metres per image row (v up)
    joint_rows = np.abs(((v * 1000 + 4) % 550) - 4) < 4        # 8 mm joints every 0.55 m from v = 0
    assert (d[joint_rows, 2000:2100] < 100).all() and (d[~joint_rows][:, 50:51] > 100).any()
    assert np.median(d.reshape(-1, 3), 0).tolist() == pytest.approx([34, 113, 179], abs=3)


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
            col = region[:, n // 2].astype(int).sum(1)
            dark = col < 0.75 * np.median(col)
            runs = int(dark[0]) + int((dark[1:] & ~dark[:-1]).sum())
            assert runs >= int(t["S"] / t["P"][1]) - 1, runs  # every 0.55 m joint row is still visible in NPM
            assert (np.asarray(Image.open(vpm / f"T_{a}_Normal_1.{t['udim']}.png")).shape == (4096, 4096, 3))
        kpp = KPP["finishes"][SPEC["kpp_palette"][name]["kpp_finish"]]["rgb"]
        assert t["rgb"] == kpp
    assert (np.asarray(o) == 255).all()  # no alpha-cut finish on AC08: opacity all solid
    with pytest.raises(FileExistsError):  # never overwrite a previous version
        make_npm_atlas.main(str(spec), str(npm))


# --- review #574 round 1 -------------------------------------------------------------------------------------------
def test_density_contract_rejects_750_without_a_user_decision():
    """P1-1: Artem 2026-10-22 «такой же тексель, как в VPM КПП» = KPP 1000 px/m; the delivered 750 px/m spec is
    rejected until an approved exception citing the decision exists."""
    with pytest.raises(ValueError, match=r"Cassette_RAL5015: texel density 750.0 px/m != contract 1000.0"):
        fm.validate_spec(SPEC, KPP)
    with pytest.raises(ValueError, match="KPP spec"):
        fm.validate_spec(SPEC)  # a KPP-twin spec cannot skip the KPP comparison
    assert fm.validate_spec(SPEC_OK, KPP)
    kpp_dens = copy.deepcopy(SPEC)
    kpp_dens["finishes"]["Cassette_RAL5015"]["S"] = KPP["finishes"]["Cassette_RAL5015"]["S"]
    assert fm.validate_spec(kpp_dens, KPP)  # exactly the KPP density needs no exception
    for exc, match in (({"px_per_m": 750.0}, "decision"), ({"px_per_m": 750.0, "decision": "ok by me"}, "decision"),
                       ({"px_per_m": 800.0, "decision": "D1"}, "contract 800.0"),
                       ({"px_per_m": float("nan"), "decision": "D1"}, "finite"),
                       ({"px_per_m": 400.0, "decision": "D1"}, "512..1706")):
        s = copy.deepcopy(SPEC)
        s["density_exception"] = {"Cassette_RAL5015": exc}
        with pytest.raises(ValueError, match=match):
            fm.validate_spec(s, KPP)


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
    cas = sum(g == "Cassette_RAL5015" for g in good)
    assert cas == 30
    mut = ["Panel_RAL5015" if g == "Cassette_RAL5015" else g for g in good]
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


PILOT = Path("C:/x/tec26-oks/AC08/pilot-v006")


@pytest.mark.skipif(not (PILOT / "readback/vpm.readback.json").exists(), reason="pilot-v006 outputs not on this PC")
@pytest.mark.parametrize("variant", ["baseline", "joint_loss", "approved_750"])
def test_qa_packages_on_pilot_v006(tmp_path, variant):
    """Acceptance rows on the real pilot-v006 readbacks (reviewer probe): the joint-loss mutant fails the source-ID
    checks; the 750 px/m delivery fails the KPP density contract until an approved exception exists."""
    spec = SPEC_OK if variant == "approved_750" else SPEC
    sp = tmp_path / "spec.json"
    sp.write_text(json.dumps(spec), encoding="utf-8")
    v, n = json.loads((PILOT / "readback/vpm.readback.json").read_text(encoding="utf-8")), \
        json.loads((PILOT / "readback/npm.readback.json").read_text(encoding="utf-8"))
    atlas = json.loads((PILOT / "textures-npm/npm_atlas.json").read_text(encoding="utf-8"))
    if variant == "joint_loss":  # every cassette triangle -> plain blue, identically in VPM and NPM
        r0, r1 = atlas["finishes"]["Cassette_RAL5015"], atlas["finishes"]["Panel_RAL5015"]
        vm = next(o for o in v["objects"] if o["name"] == "SM_Nku_1_Main")
        for uv in vm["face_uvs"]:
            c = np.mean(uv, 0)
            if int(1001 + np.floor(c[0]) + 10 * np.floor(c[1])) == 1001:
                for z in uv:
                    z[0] += 1
        for uv in n["objects"][0]["face_uvs"]:
            c = np.mean(uv, 0)
            if r0["u0"] <= c[0] <= r0["u0"] + r0["size"] and r0["v0"] <= c[1] <= r0["v0"] + r0["size"]:
                for z in uv:
                    z[0] += r1["u0"] - r0["u0"]
                    z[1] += r1["v0"] - r0["v0"]
    (tmp_path / "v.json").write_text(json.dumps(v), encoding="utf-8")
    (tmp_path / "n.json").write_text(json.dumps(n), encoding="utf-8")
    out = tmp_path / "qa.json"
    rc = qa_packages.main([str(sp), str(PILOT / "package-vpm/SM_Nku_1.zip"), str(tmp_path / "v.json"),
                          str(PILOT / "package-npm/0000_Nku_1.zip"), str(tmp_path / "n.json"),
                          str(PILOT / "textures-npm/npm_atlas.json"), str(PILOT / "textures-vpm"),
                          str(PILOT / "textures-npm"), str(AC08 / "max-dump-008.json"), str(out)])
    failed = json.loads(out.read_text(encoding="utf-8"))["failed"]
    want = {"baseline": ["spec_contract_kpp", "vpm_texel_contract"],
            "joint_loss": ["spec_contract_kpp", "source_finish_vpm", "source_finish_npm", "vpm_texel_contract"],
            "approved_750": []}[variant]
    assert (rc, failed) == (1 if want else 0, want)
