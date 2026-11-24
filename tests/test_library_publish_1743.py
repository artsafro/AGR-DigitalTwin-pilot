"""#1743 skeleton cell library-publish: agr library publish|accept|reject ([D372], [D368]-[D371]).

Synthetic batches only (marked synthetic); FBX readback is replaced by fixed reports (Blender is not needed).
"""
import importlib.util
import json
import math
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


pub = _load("library_publish_1743", "tools/library/publish.py")
core = _load("assets_core_1743", "adapters/max/agr_tools/assets_core.py")

ZIP = "Adanat_KachalkaSynth_19121"


def _report(size=(0.6, 0.6, 0.8), sink=0.0, ngons=0, maps=True, mats=("matid_1",), bounds=None):
    lo = [-size[0] / 2, -size[1] / 2, sink]
    hi = [size[0] / 2, size[1] / 2, sink + size[2]]
    mesh = {"name": "X_GroundEl", "polygons": 10, "triangles": 20, "polygon_degrees": {"4": 10, "5": ngons},
            "bounds_m": bounds or [lo, hi], "materials": list(mats), "topology": {},
            "maf_surface": None}
    return {"readback_ok": True, "meshes": [mesh],
            "materials": [{"name": m, "maps": [{"image": "d", "socket": "Base Color"}] if maps else []}
                          for m in mats]}


def good_readback(fbx, out):
    return _report()


def no_maf_findings(monkeypatch):
    class Stub:
        @staticmethod
        def maf_findings(meshes, role, src):
            return []
    monkeypatch.setattr(pub, "_twinqa_maf", lambda: Stub)


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    no_maf_findings(monkeypatch)


def make_batch(root, zip_low=True, folder=True, article="19121"):
    """SYNTHETIC batch: one A101 zip, its work folder, one own folder object, a script and a texture."""
    b = root / "batch-synth"
    (b / "maf").mkdir(parents=True)
    side = {"identity": {"manufacturer": "Adanat", "object_name": "KachalkaSynth", "article": article},
            "title": "Качалка синтетическая", "geometry": {"high": {"bbox": {"x": 600, "y": 600, "z": 800}}}}
    with zipfile.ZipFile(b / "maf" / f"{ZIP}.zip", "w") as zf:
        zf.writestr(f"{ZIP}.json", json.dumps(side))
        zf.writestr(f"{ZIP}_high.fbx", b"high")
        if zip_low:
            zf.writestr(f"{ZIP}_low.fbx", b"low")
        zf.writestr(f"{ZIP}.png", b"png")
        zf.writestr(f"{ZIP}.max", b"max")
    (b / "LB19121").mkdir()
    (b / "LB19121" / "LB19121_GroundEl_v001.fbx").write_bytes(b"work")
    if folder:
        (b / "M171620" / "source").mkdir(parents=True)
        (b / "M171620" / "M171620_GroundEl_quad.fbx").write_bytes(b"quad")
        (b / "M171620" / "m171620_v001.blend").write_bytes(b"blend")
        (b / "M171620" / "source" / "r.jpg").write_bytes(b"jpg")
    (b / "scripts").mkdir()
    (b / "scripts" / "build.py").write_text("x = 1\n")
    (b / "T_Roza.png").write_bytes(b"tex")
    (b / "desktop.ini").write_text("")
    return b


def _unified(*recs):
    return {"records": list(recs)}


def publish(tmp_path, batch, cat, ids=None, readback=good_readback, ev="ev1", unified=None):
    return pub.publish(batch, "maf", cat, unified or _unified(), tmp_path / "assets", tmp_path / ev, ids or {},
                       "1743", readback, work=tmp_path / ("work_" + ev))


# ---- intake ---------------------------------------------------------------------------------------------------
def test_intake_every_file_is_an_object_file_or_a_reported_drop(tmp_path):
    b = make_batch(tmp_path)
    inv = pub.intake_batch(b, "maf")
    keys = sorted(o["key"] for o in inv["objects"])
    assert keys == sorted(["M171620", ZIP])
    listed = {Path(p).resolve() for o in inv["objects"] for p in o["files"]}
    listed |= {(b / d["path"]).resolve() for d in inv["drops"]}
    every = {p.resolve() for p in b.rglob("*") if p.is_file() and p.name != "desktop.ini"}
    assert listed == every and inv["files"] == len(every)
    reasons = {d["path"]: d["reason"] for d in inv["drops"]}
    assert "superseded by archive " + ZIP in reasons["LB19121/LB19121_GroundEl_v001.fbx"]
    assert "materials library is later" in reasons["T_Roza.png"]
    assert "build script" in reasons["scripts/build.py"]


@pytest.mark.parametrize("kind", ["materials", "", "MAF"])
def test_intake_unsupported_kind_is_an_error(tmp_path, kind):
    with pytest.raises(pub.PublishError, match="not a library kind"):
        pub.intake_batch(make_batch(tmp_path), kind)


def test_intake_empty_or_missing_batch_is_an_error(tmp_path):
    (tmp_path / "empty").mkdir()
    (tmp_path / "empty" / "desktop.ini").write_text("")
    with pytest.raises(pub.PublishError, match="empty"):
        pub.intake_batch(tmp_path / "empty")
    with pytest.raises(pub.PublishError, match="not a folder"):
        pub.intake_batch(tmp_path / "nope")


def test_intake_ambiguous_folder_is_an_error_naming_it(tmp_path):
    b = make_batch(tmp_path)
    (b / "M171620" / "M171620_GroundEl_v002.fbx").write_bytes(b"other")
    with pytest.raises(pub.PublishError, match="M171620.*2 FBX"):
        pub.intake_batch(b)


@pytest.mark.parametrize(
    ("key", "exports", "expected_tris", "findings"),
    [
        pytest.param("M3", {"M3_GroundEl_high.fbx": "high", "M3_GroundEl_low.fbx": "low"},
                     {"vpm": 32, "npm": 12}, [], id="matching-pair"),
        pytest.param("M3", {"M3_GroundEl_HIGH.FBX": "high", "m3_GroundEl_low.fbx": "low"},
                     {"vpm": 32, "npm": 12}, [], id="mixed-case-pair"),
        pytest.param("M4", {"M4_GroundEl_low.fbx": "low"}, {"vpm": None, "npm": 12},
                     ["vpm: no VPM version in the object"], id="lone-npm"),
    ],
)
def test_publish_own_folder_fbx_roles(tmp_path, key, exports, expected_tris, findings):
    batch = make_batch(tmp_path, folder=False)
    folder = batch / key
    folder.mkdir()
    tri_counts = {"high": 32, "low": 12}
    for name, profile in exports.items():
        (folder / name).write_bytes(profile.encode())
    before = {p: p.read_bytes() for p in batch.rglob("*") if p.is_file()}

    def readback(fbx, out):
        report = _report()
        report["meshes"][0]["triangles"] = tri_counts[fbx.read_text()]
        return report

    cat = pub.empty_catalogue()
    publish(tmp_path, batch, cat, readback=readback)
    rec = next(r for r in cat["records"] if r["origin"]["object"] == key)
    assert rec["card"]["tris"] == expected_tris
    assert rec["qa"] == {"verdict": "fail" if findings else "pass", "findings": findings}
    roles = {"high": "vpm", "low": "npm"}
    assert {Path(f["path"]).name: f["role"] for f in rec["files"]} == {
        name: roles[profile] for name, profile in exports.items()
    }
    assert {p: p.read_bytes() for p in batch.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("suffix", ["high", "low", "legacy"])
@pytest.mark.parametrize("pair", [False, True])
def test_probe_own_folder_role_is_case_insensitive_and_unique(tmp_path, suffix, pair):
    folder = tmp_path / "synthetic"
    folder.mkdir()
    fbx = folder / f"X_GroundEl_{suffix.upper()}.FBX"
    fbx.write_bytes(b"first")
    if pair:
        other = folder / f"X_GroundEl_v002_{suffix}.fbx"
        other.write_bytes(b"second")
        with pytest.raises(pub.PublishError, match="synthetic.*ambiguous object.*2 FBX") as exc:
            pub.intake_batch(tmp_path)
        assert fbx.name in str(exc.value) and other.name in str(exc.value)
    else:
        [obj] = pub.intake_batch(tmp_path)["objects"]
        assert obj["members"] == {"npm" if suffix == "low" else "vpm": str(fbx)}


def test_loose_fbx_from_different_objects_are_still_ambiguous(tmp_path):
    for name in ("M3_GroundEl_high.fbx", "M4_GroundEl_low.fbx"):
        (tmp_path / name).write_bytes(b"synthetic")
    with pytest.raises(pub.PublishError, match="ambiguous object, 2 FBX"):
        pub.intake_batch(tmp_path)


@pytest.mark.parametrize(
    ("key", "ambiguous_names"),
    [
        pytest.param("M4", ("M4_GroundEl_v001_low.fbx", "M4_GroundEl_v002_low.fbx"), id="duplicate-role"),
        pytest.param("M5", ("A_GroundEl_high.fbx", "B_GroundEl_low.fbx"), id="different-stems"),
    ],
)
def test_paired_folder_plus_ambiguous_folder_writes_no_version(tmp_path, key, ambiguous_names):
    batch = tmp_path / "synthetic"
    for folder_name, names in [("M3", ("M3_GroundEl_high.fbx", "M3_GroundEl_low.fbx")), (key, ambiguous_names)]:
        folder = batch / folder_name
        folder.mkdir(parents=True)
        for name in names:
            (folder / name).write_bytes(b"synthetic")
    before = {p: p.read_bytes() for p in batch.rglob("*") if p.is_file()}
    cat = pub.empty_catalogue()
    with pytest.raises(pub.PublishError, match=rf"{key}: ambiguous object, 2 FBX files") as exc:
        publish(tmp_path, batch, cat, readback=lambda fbx, out: _report())
    assert all(name in str(exc.value) for name in ambiguous_names)
    assert not (tmp_path / "assets").exists() and cat == pub.empty_catalogue()
    assert {p: p.read_bytes() for p in batch.rglob("*") if p.is_file()} == before


# ---- name -----------------------------------------------------------------------------------------------------
def test_name_manufacturer_rule_translit_and_yo():
    cat = pub.empty_catalogue()
    n = pub.library_name("maf", {"manufacturer": "Место", "title_ru": "Песочная фабрика ёлка", "article": "171620"},
                         cat, "M171620")
    assert n == "Mesto_PesochnayaFabrikaElka_171620"
    assert pub.library_name("maf", {"manufacturer": "Adanat", "object_latin": "Kachalka", "article": "ЛГК-11.21"},
                            cat, "k") == "Adanat_Kachalka_LGK-11.21"
    # a Latin sidecar maker keeps its case (GKVysota, not Gkvysota)
    assert pub.library_name("maf", {"manufacturer": "GKVysota", "object_latin": "Stol", "article": "VST9504-1"},
                            cat, "k") == "GKVysota_Stol_VST9504-1"


def test_name_without_manufacturer_is_agr_kind_counter():
    cat = pub.empty_catalogue()
    assert pub.library_name("flora", {}, cat, "Роза ёжик") == "AGR_flora_RozaEzhik_001"
    cat["records"].append({"name": "AGR_flora_RozaEzhik_001", "origin": {"object": "Роза ёжик"}})
    assert pub.library_name("flora", {}, cat, "Роза ёжик") == "AGR_flora_RozaEzhik_001"  # same object keeps name
    assert pub.library_name("flora", {}, cat, "Роза ёжик2") == "AGR_flora_RozaEzhik2_001"
    cat["records"].append({"name": "AGR_flora_Roza_004", "origin": {"object": "a"}})
    assert pub.library_name("flora", {}, cat, "Роза") == "AGR_flora_Roza_005"


@pytest.mark.parametrize("ident, match", [({"manufacturer": "Adanat"}, "without an article"),
                                          ({"manufacturer": "Adanat", "article": "1"}, "without an object name")])
def test_name_partial_identity_is_an_error(ident, match):
    with pytest.raises(pub.PublishError, match=match):
        pub.library_name("maf", ident, pub.empty_catalogue(), "k")


# ---- identify -------------------------------------------------------------------------------------------------
def _obj(article="19121", maker="Adanat", size=(600, 600, 800)):
    return {"identity": {"manufacturer": maker, "article": article}, "size_mm": dict(zip("xyz", size))}


def test_identify_duplicate_variant_new():
    a101 = {"name": "Adanat_Kachalka_19121", "manufacturer": "Adanat", "article": "19121", "source": "a101",
            "bbox_mm": {"high": {"x": 610, "y": 600, "z": 790}}}
    uni, cat = _unified(a101), pub.empty_catalogue()
    assert pub.identify_object(_obj(), uni, cat)["result"] == "duplicate"
    assert pub.identify_object(_obj(size=(900, 600, 800)), uni, cat)["result"] == "variant"
    assert pub.identify_object(_obj(maker="Leber"), uni, cat)["result"] == "variant"
    assert pub.identify_object(_obj(article="77777"), uni, cat)["result"] == "new"
    assert pub.identify_object(_obj(article=""), uni, cat)["result"] == "new"
    no_size = {"identity": {"manufacturer": "Adanat", "article": "19121"}}
    assert pub.identify_object(no_size, uni, cat)["result"] == "variant"  # unknown size is never a duplicate


# ---- qa -------------------------------------------------------------------------------------------------------
def test_qa_pass_and_each_failure_is_named():
    assert pub.qa_object({}, "maf", {"vpm": _report(), "npm": _report()})["verdict"] == "pass"
    cases = {"no NPM version": {"vpm": _report(), "npm": None},
             "n-gons": {"vpm": _report(ngons=2), "npm": _report()},
             "without texture maps": {"vpm": _report(maps=False), "npm": _report()},
             "pivot/seating": {"vpm": _report(sink=-0.1), "npm": _report()},  # D095 sink is placement, not library
             "not finite": {"vpm": _report(bounds=[[0, 0, math.nan], [1, 1, 1]]), "npm": _report()},
             "no non-empty mesh": {"vpm": {"readback_ok": False, "meshes": []}, "npm": _report()},
             "no material": {"vpm": _report(mats=()), "npm": _report()}}
    for text, reps in cases.items():
        res = pub.qa_object({}, "maf", reps)
        assert res["verdict"] == "fail" and any(text in f for f in res["findings"]), text


def test_qa_pivot_rule_per_kind_and_tolerance_bounds():
    assert pub.qa_profile(_report(sink=-0.004), "maf", "vpm")["verdict"] == "pass"
    assert pub.qa_profile(_report(sink=0.006), "maf", "vpm")["verdict"] == "fail"
    assert pub.qa_profile(_report(sink=-0.096), "flora", "vpm")["verdict"] == "pass"
    assert pub.qa_profile(_report(sink=-0.094), "flora", "vpm")["verdict"] == "fail"
    assert pub.qa_profile(_report(sink=0.0), "flora", "vpm")["verdict"] == "fail"
    assert pub.qa_profile(_report(sink=0.0), "roof_equipment", "vpm")["verdict"] == "pass"
    win = _report(bounds=[[0, 0, 0], [1.2, 0.1, 1.5]])
    assert pub.qa_profile(win, "windows", "vpm")["verdict"] == "pass"
    assert pub.qa_profile(_report(), "windows", "vpm")["verdict"] == "fail"


def test_qa_maf_findings_failure_or_crash_is_never_a_pass(monkeypatch):
    class Boom:
        @staticmethod
        def maf_findings(*a, **k):
            raise RuntimeError("x")
    monkeypatch.setattr(pub, "_twinqa_maf", lambda: Boom)
    res = pub.qa_profile(_report(), "maf", "vpm")
    assert res["verdict"] == "fail" and "maf_findings not run" in res["findings"][0]


# ---- publish / register / immutability -------------------------------------------------------------------------
def test_publish_registers_drafts_with_hashes_and_one_sheet(tmp_path):
    b, cat = make_batch(tmp_path), pub.empty_catalogue()
    res = publish(tmp_path, b, cat, {"M171620": {"manufacturer": "Место", "title_ru": "Песочная фабрика",
                                                 "article": "171620"}})
    names = sorted(r["name"] for r in cat["records"])
    assert names == [ZIP, "Mesto_PesochnayaFabrika_171620"]
    for r in cat["records"]:
        assert r["status"] == "draft" and r["version"] == "v001" and r["files"]
        for f in r["files"]:
            assert pub.sha256_file(tmp_path / "assets" / f["path"]) == f["sha256"]
        assert set(r["card"]) >= {"manufacturer", "article", "size_m", "tris", "materials"}
        assert r["origin"] == {"batch": "batch-synth", "object": r["origin"]["object"], "issue": "1743"}
    zrec = next(r for r in cat["records"] if r["name"] == ZIP)
    assert zrec["qa"]["verdict"] == "pass" and zrec["preview"].endswith(f"{ZIP}.zip#{ZIP}.png")
    frec = next(r for r in cat["records"] if r["name"] != ZIP)
    assert frec["qa"]["verdict"] == "fail" and "no NPM version" in frec["qa"]["findings"][0]
    sheet = Path(res["sheet"]).read_text(encoding="utf-8")
    assert ZIP in sheet and "Mesto_PesochnayaFabrika_171620" in sheet and "T_Roza.png" in sheet
    assert (tmp_path / "ev1" / "SHA256SUMS.txt").is_file() and (tmp_path / "ev1" / "sheet.html").is_file()
    assert not pub.catalogue_problems(cat)


def test_second_publish_creates_next_version_and_never_overwrites(tmp_path):
    b, cat = make_batch(tmp_path), pub.empty_catalogue()
    publish(tmp_path, b, cat)
    v1 = tmp_path / "assets" / "maf" / ZIP / "v001"
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in v1.rglob("*") if p.is_file()}
    with zipfile.ZipFile(b / "maf" / f"{ZIP}.zip", "a") as zf:
        zf.writestr("note.txt", "changed object")
    publish(tmp_path, b, cat, ev="ev2")
    assert [r["version"] for r in cat["records"] if r["name"] == ZIP] == ["v001", "v002"]
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in v1.rglob("*") if p.is_file()} == before
    assert (tmp_path / "assets" / "maf" / ZIP / "v002" / f"{ZIP}.zip").is_file()


def test_probe_n_republishes_give_n_distinct_versions(tmp_path):
    b, cat = make_batch(tmp_path, folder=False), pub.empty_catalogue()
    for i in range(7):
        publish(tmp_path, b, cat, ev=f"e{i}")
    vers = [r["version"] for r in cat["records"]]
    assert vers == ["v{:03d}".format(i + 1) for i in range(7)]
    assert sorted(p.name for p in (tmp_path / "assets" / "maf" / ZIP).iterdir()) == vers


def test_existing_or_partial_version_folder_is_skipped_never_written(tmp_path):
    b, cat = make_batch(tmp_path, folder=False), pub.empty_catalogue()
    stale = tmp_path / "assets" / "maf" / ZIP / "v001.partial"
    stale.mkdir(parents=True)
    (stale / "keep.txt").write_text("stale")
    publish(tmp_path, b, cat)
    assert cat["records"][0]["version"] == "v002" and (stale / "keep.txt").read_text() == "stale"


def test_version_appearing_during_the_run_is_refused(tmp_path, monkeypatch):
    b, cat = make_batch(tmp_path, folder=False), pub.empty_catalogue()
    final = tmp_path / "assets" / "maf" / ZIP / "v001"
    real = os.rename

    def racing(src, dst):
        Path(dst).mkdir(parents=True)
        return real(src, dst)
    monkeypatch.setattr(pub.os, "rename", racing)
    with pytest.raises(pub.PublishError, match="appeared during the run|already exists"):
        publish(tmp_path, b, cat)
    assert not cat["records"] and final.is_dir() and not any(final.iterdir())


def test_duplicate_is_not_registered(tmp_path):
    b, cat = make_batch(tmp_path, folder=False), pub.empty_catalogue()
    uni = _unified({"name": "Adanat_Kachalka_19121", "manufacturer": "Adanat", "article": "19121",
                    "bbox_mm": {"high": {"x": 600, "y": 600, "z": 800}}})
    res = publish(tmp_path, b, cat, unified=uni)
    assert not cat["records"] and res["rows"][0]["skip"].startswith("duplicate")
    assert not (tmp_path / "assets").exists()


@pytest.mark.parametrize("where", ["batch", "inside", "alias", "parent"])
def test_assets_root_overlapping_the_batch_is_refused_and_writes_nothing(tmp_path, where):
    b, cat = make_batch(tmp_path, folder=False), pub.empty_catalogue()
    root = {"batch": b, "inside": b / "maf", "parent": tmp_path,
            "alias": Path(str(b / "maf" / ".." ).upper() if os.name == "nt" else str(b / "maf" / ".."))}[where]
    before = sorted(p for p in b.rglob("*"))
    with pytest.raises(pub.PublishError, match="overlaps"):
        pub.publish(b, "maf", cat, _unified(), root, tmp_path / "ev", {}, None, good_readback, work=tmp_path / "w")
    assert sorted(p for p in b.rglob("*")) == before and not cat["records"]


def test_sheet_folder_is_never_overwritten(tmp_path):
    b, cat = make_batch(tmp_path, folder=False), pub.empty_catalogue()
    (tmp_path / "ev1").mkdir()
    (tmp_path / "ev1" / "sheet.md").write_text("old")
    with pytest.raises(pub.PublishError, match="not empty"):
        publish(tmp_path, b, cat)
    assert (tmp_path / "ev1" / "sheet.md").read_text() == "old"


def test_identity_file_naming_an_unknown_object_is_an_error(tmp_path):
    with pytest.raises(pub.PublishError, match="not in the batch"):
        publish(tmp_path, make_batch(tmp_path), pub.empty_catalogue(), {"NOPE": {"manufacturer": "X"}})


# ---- #1755: a refused batch writes nothing to the assets root ---------------------------------------------------
def two_folders(root, *keys):
    """SYNTHETIC batch of own-folder objects (default M1, M2), one FBX each."""
    b = root / "batch-two"
    for k in keys or ("M1", "M2"):
        (b / k).mkdir(parents=True)
        (b / k / f"{k}_GroundEl_quad.fbx").write_bytes(k.encode())
    return b


def _tree(p):
    return sorted(x.relative_to(p).as_posix() for x in p.rglob("*")) if p.exists() else None


@pytest.mark.parametrize("bad", ["evidence", "identity", "both", "late_identity_after_two"])
def test_refused_batch_leaves_assets_root_unchanged(tmp_path, bad):
    keys = ("M1", "M2", "M3") if bad == "late_identity_after_two" else ("M1", "M2")
    b, cat = two_folders(tmp_path, *keys), pub.empty_catalogue()
    assets = tmp_path / "assets"
    (assets / "maf" / "Other_X_1" / "v001").mkdir(parents=True)  # pre-existing library content stays as it is
    before = _tree(assets)
    ids = {}
    if bad in ("evidence", "both"):
        (tmp_path / "ev1").mkdir()
        (tmp_path / "ev1" / "old.md").write_text("old")
    if bad != "evidence":
        ids = {keys[-1]: {"manufacturer": "Acme"}}  # maker without an article: refused
    with pytest.raises(pub.PublishError, match="not empty|without an article"):
        publish(tmp_path, b, cat, ids)
    assert _tree(assets) == before and cat == pub.empty_catalogue()


def test_same_stem_objects_in_one_batch_keep_distinct_counter_names(tmp_path):
    b, cat = two_folders(tmp_path), pub.empty_catalogue()
    same = {"title_ru": "Скамья"}
    publish(tmp_path, b, cat, {"M1": same, "M2": same})
    assert sorted(r["name"] for r in cat["records"]) == ["AGR_maf_Skamya_001", "AGR_maf_Skamya_002"]


def test_same_library_name_twice_in_one_batch_gives_two_versions(tmp_path):
    b, cat = two_folders(tmp_path), pub.empty_catalogue()
    same = {"manufacturer": "Acme", "title_ru": "Скамья", "article": "777"}
    publish(tmp_path, b, cat, {"M1": same, "M2": same})
    assert [(r["name"], r["version"]) for r in cat["records"]] == [("Acme_Skamya_777", "v001"),
                                                                   ("Acme_Skamya_777", "v002")]
    assert sorted(p.name for p in (tmp_path / "assets" / "maf" / "Acme_Skamya_777").iterdir()) == ["v001", "v002"]


def _corrupt_copy_of(monkeypatch, key):
    real = pub.shutil.copyfile

    def copy(src, dst):
        out = real(src, dst)
        if Path(src).parent.name == key and "assets" in Path(dst).parts:
            Path(dst).write_bytes(b"corrupt")
        return out
    monkeypatch.setattr(pub.shutil, "copyfile", copy)


def test_late_failure_reports_versions_already_made_and_keeps_their_records(tmp_path, monkeypatch):
    b, cat = two_folders(tmp_path), pub.empty_catalogue()
    _corrupt_copy_of(monkeypatch, "M2")
    with pytest.raises(pub.PublishError, match="does not match") as ei:
        publish(tmp_path, b, cat)
    made = tmp_path / "assets" / "maf" / "AGR_maf_M1_001" / "v001"
    assert made.is_dir() and str(made) in str(ei.value)
    assert [r["name"] for r in ei.value.registered] == ["AGR_maf_M1_001"]
    assert [(r["name"], r["version"]) for r in cat["records"]] == [("AGR_maf_M1_001", "v001")]


def test_cli_late_failure_writes_the_catalogue_for_versions_made(tmp_path, monkeypatch):
    b, catp = two_folders(tmp_path), tmp_path / "cat.json"
    catp.write_text(json.dumps(pub.empty_catalogue()))
    monkeypatch.setattr(pub, "blender_readback", lambda f, o, blender=None: _report())
    _corrupt_copy_of(monkeypatch, "M2")
    rc = pub.main(["publish", str(b), "--catalogue", str(catp), "--evidence", str(tmp_path / "ev"),
                   "--assets-root", str(tmp_path / "assets"), "--unified", str(catp)])
    recs = json.loads(catp.read_text(encoding="utf-8"))["records"]
    assert rc == 2 and [(r["name"], r["version"]) for r in recs] == [("AGR_maf_M1_001", "v001")]
    assert sorted(p.name for p in (tmp_path / "assets" / "maf").iterdir()) == ["AGR_maf_M1_001", "AGR_maf_M2_001"]
    assert not (tmp_path / "assets" / "maf" / "AGR_maf_M2_001" / "v001").exists()  # only its .partial is kept


def test_cli_fresh_process_refused_batch_writes_no_version(tmp_path):
    b, catp = two_folders(tmp_path), tmp_path / "cat.json"
    catp.write_text(json.dumps(pub.empty_catalogue()))
    (tmp_path / "ev").mkdir()
    (tmp_path / "ev" / "old.md").write_text("old")
    r = _cli("publish", str(b), "--catalogue", str(catp), "--evidence", str(tmp_path / "ev"),
             "--assets-root", str(tmp_path / "assets"), "--blender", str(tmp_path / "no-blender.exe"))
    assert r.returncode == 2 and "not empty" in r.stderr
    assert json.loads(catp.read_text()) == pub.empty_catalogue() and not (tmp_path / "assets").exists()


def test_probe_every_version_on_disk_is_described_or_none_is_written(tmp_path, monkeypatch):
    """Probe: N objects (1..5), refusal or copy failure at object k (seeded) -> assets root unchanged on a refusal;
    on a late failure every vNNN on disk is in the catalogue and named in the error."""
    import random
    rnd, real, runs = random.Random(1755), pub.shutil.copyfile, 0
    for i in range(40):
        n = rnd.randint(1, 5)
        k = rnd.randrange(n)
        mode = rnd.choice(["identity", "evidence", "copy"])
        base = tmp_path / f"r{i}"
        keys = tuple(f"M{j}" for j in range(n))
        b, cat = two_folders(base, *keys), pub.empty_catalogue()
        ids = {keys[k]: {"manufacturer": "Acme"}} if mode == "identity" else {}
        if mode == "evidence":
            (base / "ev1").mkdir()
            (base / "ev1" / "x").write_text("x")
        bad = keys[k]

        def copy(src, dst, bad=bad):
            out = real(src, dst)
            if mode == "copy" and Path(src).parent.name == bad and "assets" in Path(dst).parts:
                Path(dst).write_bytes(b"corrupt")
            return out
        monkeypatch.setattr(pub.shutil, "copyfile", copy)
        with pytest.raises(pub.PublishError) as ei:
            publish(base, b, cat, ids)
        on_disk = sorted(f"{p.parent.name}/{p.name}" for p in (base / "assets").rglob("v[0-9][0-9][0-9]")
                         if p.is_dir()) if (base / "assets").exists() else []
        described = sorted(f"{r['name']}/{r['version']}" for r in cat["records"])
        assert on_disk == described, (i, mode, n, k)
        if mode != "copy":
            assert not (base / "assets").exists() and not cat["records"]
        else:
            assert len(described) == k and all(d.replace("/", os.sep) in str(ei.value) for d in described)
        runs += 1
    assert runs == 40


# ---- accept / reject / read path --------------------------------------------------------------------------------
def _drafts(tmp_path):
    b, cat = make_batch(tmp_path), pub.empty_catalogue()
    publish(tmp_path, b, cat)
    return b, cat


def test_draft_is_not_available_accept_makes_it_available(tmp_path):
    _b, cat = _drafts(tmp_path)
    assert pub.available(cat) == []
    with pytest.raises(pub.PublishError, match="words"):
        pub.accept_records(cat, [ZIP], "  ")
    pub.accept_records(cat, [ZIP], "ок")
    assert [r["name"] for r in pub.available(cat)] == [ZIP]
    assert pub.accepted_paths(cat) == {f"maf/{ZIP}/v001".lower()}
    with pytest.raises(pub.PublishError, match="0 matching draft"):
        pub.accept_records(cat, [ZIP], "ок")  # already accepted: no draft left


def test_accept_refuses_qa_failed_unless_despite_qa(tmp_path):
    _b, cat = _drafts(tmp_path)
    failed = next(r["name"] for r in cat["records"] if r["qa"]["verdict"] == "fail")
    with pytest.raises(pub.PublishError, match="QA fail"):
        pub.accept_records(cat, [failed, ZIP], "ок")
    assert all(r["status"] == "draft" for r in cat["records"])  # all-or-nothing
    pub.accept_records(cat, [failed], "ок, без НПМ пока", despite_qa=True)
    rec = next(r for r in cat["records"] if r["name"] == failed)
    assert rec["status"] == "accepted" and rec["accepted"]["despite_qa"] is True


def test_reject_writes_remark_to_inbox_and_stays_unavailable(tmp_path):
    b, cat = _drafts(tmp_path)
    pub.reject_record(cat, ZIP, "пропорции не те", tmp_path)
    text = (b / "REJECTED.md").read_text(encoding="utf-8")
    assert ZIP in text and "пропорции не те" in text
    assert pub.available(cat) == []
    with pytest.raises(pub.PublishError):
        pub.accept_records(cat, [f"{ZIP}@v001"], "ок")


def test_catalogue_alternate_form_records_are_rejected():
    good = {"name": "A_B_1", "kind": "maf", "version": "v001", "status": "draft", "files": []}
    assert not pub.catalogue_problems({"schema": pub.SCHEMA, "records": [good]})
    bad = [dict(good, status="ready"), dict(good, version="1"), dict(good, kind="materials"),
           dict(good, status="accepted", accepted=None), dict(good, files=[{"path": "x", "sha256": "abc"}])]
    for rec in bad:
        assert pub.catalogue_problems({"schema": pub.SCHEMA, "records": [good, rec]}), rec
    assert pub.catalogue_problems({"schema": pub.SCHEMA, "records": [good, dict(good)]})  # duplicated input
    assert pub.catalogue_problems({"schema": "agr-library/1", "records": []})


def _zip(path, base):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(base + "_high.fbx", b"h")


def test_assets_browser_scan_shows_only_accepted_published_versions(tmp_path):
    lib = tmp_path / "maf"
    _zip(lib / "a101" / "Adanat_Old_1.zip", "Adanat_Old_1")
    _zip(lib / "Adanat_New_2" / "v001" / "Adanat_New_2.zip", "Adanat_New_2")
    _zip(lib / "Adanat_New_2" / "v002" / "Adanat_New_2.zip", "Adanat_New_2")
    _zip(lib / "Adanat_New_2" / "v003.partial" / "Adanat_New_2.zip", "Adanat_New_2")
    cat = {"schema": pub.SCHEMA, "records": [
        {"name": "Adanat_New_2", "version": "v001", "status": "accepted"},
        {"name": "Adanat_New_2", "version": "v002", "status": "draft"}]}
    (tmp_path / "cat.json").write_text(json.dumps(cat))
    acc = core.published_accepted(str(tmp_path / "cat.json"))
    idx = core.scan_maf(str(lib), str(tmp_path / "c"), lib="maf", published=acc)
    shown = sorted(r["source"]["path"] for r in idx["assets"])
    assert shown == ["Adanat_New_2/v001/Adanat_New_2.zip", "a101/Adanat_Old_1.zip"]
    hidden = {h["path"]: h["reason"] for h in idx["report"]["hidden_unaccepted"]}
    assert "not accepted" in hidden["Adanat_New_2/v002/Adanat_New_2.zip"]
    assert "partial" in hidden["Adanat_New_2/v003.partial/Adanat_New_2.zip"]
    # missing / unreadable catalogue: every published version hidden (fail-closed), A101 still shown
    for bad in (tmp_path / "none.json", tmp_path / "c" ):
        idx = core.scan_maf(str(lib), str(tmp_path / "c2"), lib="maf", published=core.published_accepted(str(bad)))
        assert [r["source"]["path"] for r in idx["assets"]] == ["a101/Adanat_Old_1.zip"]


def test_repo_catalogue_is_valid_and_default_read_path_uses_it():
    cat = pub.load_catalogue(pub.CATALOGUE)
    assert core.published_accepted() == {(r["name"].lower(), r["version"]) for r in pub.available(cat)}
    schema = json.loads((ROOT / "schemas/library_published.schema.json").read_text(encoding="utf-8"))
    assert schema["properties"]["schema"]["const"] == pub.SCHEMA
    assert schema["$defs"]["record"]["properties"]["status"]["enum"] == list(pub.STATUSES)


# ---- CLI (fresh process) and skeleton --------------------------------------------------------------------------
def _cli(*args):
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    return subprocess.run([sys.executable, "-m", "dt_ai.cli.agr", "library", *args], capture_output=True,
                          text=True, encoding="utf-8", env=env, cwd=ROOT)


def test_cli_accept_reject_fresh_process(tmp_path):
    b, cat = _drafts(tmp_path)
    path = tmp_path / "cat.json"
    path.write_text(json.dumps(cat, ensure_ascii=False), encoding="utf-8")
    failed = next(r["name"] for r in cat["records"] if r["qa"]["verdict"] == "fail")
    r = _cli("accept", failed, "--words", "ок", "--catalogue", str(path))
    assert r.returncode == 1 and "QA fail" in r.stderr
    r = _cli("accept", ZIP, "--words", "ок", "--catalogue", str(path))
    assert r.returncode == 0, r.stderr
    r = _cli("reject", failed, "--words", "нет", "--catalogue", str(path), "--inbox-root", str(tmp_path))
    assert r.returncode == 0, r.stderr
    st = {x["name"]: x["status"] for x in json.loads(path.read_text(encoding="utf-8"))["records"]}
    assert st == {ZIP: "accepted", failed: "rejected"}
    path.write_text("{}")
    assert _cli("accept", ZIP, "--words", "ок", "--catalogue", str(path)).returncode == 2


def test_cli_publish_refuses_bad_batch_and_unknown_kind(tmp_path):
    cat = tmp_path / "cat.json"
    cat.write_text(json.dumps(pub.empty_catalogue()))
    r = _cli("publish", str(tmp_path / "none"), "--catalogue", str(cat), "--evidence", str(tmp_path / "e"))
    assert r.returncode == 2 and "not a folder" in r.stderr
    r = _cli("publish", str(tmp_path), "--kind", "materials", "--catalogue", str(cat), "--evidence", str(tmp_path))
    assert r.returncode == 2
    assert json.loads(cat.read_text()) == pub.empty_catalogue()
    only = tmp_path / "tex"
    only.mkdir()
    (only / "T_Roza.png").write_bytes(b"t")
    r = _cli("publish", str(only), "--catalogue", str(cat), "--evidence", str(tmp_path / "e2"),
             "--assets-root", str(tmp_path / "a"))
    assert r.returncode == 1 and "no library object" in r.stderr  # nothing to publish is never a pass


def test_skeleton_cell_library_publish_has_the_six_stages():
    sk = json.loads((ROOT / "docs/agents/skeletons.json").read_text(encoding="utf-8"))
    assert sk["cells"]["library-publish"]["stages"] == ["intake", "identify", "name", "qa", "register", "sheet"]
    for sid in sk["cells"]["library-publish"]["stages"]:
        st = sk["stages"][sid]
        assert st["gap"] is None and "tools/library/publish.py" in st["owners"], sid
    cells = json.loads((ROOT / "docs/scenarios/scenarios.json").read_text(encoding="utf-8"))["cells"]
    assert any(c["id"] == "library-publish" and c["status"] == "ready" for c in cells)
    assert "agr library publish" in (ROOT / "docs/agents/SKELETONS.md").read_text(encoding="utf-8")


def test_decisions_rows_for_the_five_answers():
    text = (ROOT / "docs/decisions.md").read_text(encoding="utf-8")
    for d in ("D368", "D369", "D370", "D371", "D372"):
        assert f"| {d} | 2026-11-21 |" in text and "#1743" in next(l for l in text.splitlines()
                                                                   if l.startswith(f"| {d} |")), d
