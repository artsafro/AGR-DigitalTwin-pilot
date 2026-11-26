"""new-case: tests for #1980 [D421]: agent-made library drafts are visible to other agents (marked `status: draft`), the MAF search index
is rebuilt at the end of every `agr library publish|accept|reject`, and a job with an unpublished MAF master fails.

Synthetic catalogues / batches only (marked synthetic); no Blender, no Max, no Drive.
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


pub = _load("library_publish_1980", "tools/library/publish.py")
ii = _load("intake_identify_1980", "tools/assets/intake_identify.py")

SHA = "a" * 64


def rec(name, status, version="v001", kind="maf", article="19121", obj=None, sha=SHA):
    """SYNTHETIC catalogue record."""
    return {"name": name, "kind": kind, "version": version, "status": status, "published": "2026-11-26T00:00:00+01:00",
            "origin": {"batch": "synth", "object": obj or name, "issue": "1980"},
            "identify": {"result": "new", "of": [], "reason": "synthetic"},
            "card": {"manufacturer": "Adanat", "title_ru": "Синтетика", "article": article, "size_m": [0.6, 0.6, 0.8],
                     "tris": {"vpm": 100, "npm": 50}, "materials": {"vpm": [], "npm": []}},
            "preview": f"{kind}/{name}/{version}/prev.png",
            "files": [{"path": f"{kind}/{name}/{version}/{obj or name}_GroundEl_v001.fbx", "sha256": sha}],
            "qa": {"verdict": "pass", "findings": []},
            "accepted": {"date": "2026-11-26", "by": "Artem", "words": "ок"} if status == "accepted" else None,
            "rejected": {"date": "2026-11-26", "by": "Artem", "words": "нет"} if status == "rejected" else None}


def catalogue(*recs):
    return {"schema": pub.SCHEMA, "records": list(recs)}


A101 = {"id": "maf_a101:Adanat_Old_1", "source": "a101", "name": "Adanat_Old_1", "manufacturer": "Adanat",
        "article": "1111", "status": "a101", "bbox_mm": {"high": {"x": 600, "y": 600, "z": 800}}}


def unified_file(tmp_path, *extra):
    p = tmp_path / "maf_unified.json"
    p.write_text(json.dumps({"schema": "agr.assets.unified/1", "kind": "maf", "truth": "a101",
                             "records": [A101, *extra], "counts": {"a101": 1}, "sources": {"a101_root": "x"}},
                            ensure_ascii=False), encoding="utf-8")
    return p


# ---- read path: drafts visible, marked, accepted first ---------------------------------------------------------
def test_available_returns_drafts_marked_and_accepted_first():
    cat = catalogue(rec("Adanat_Draft_1", "draft"), rec("Adanat_Ok_2", "accepted"), rec("Adanat_No_3", "rejected"))
    got = pub.available(cat)
    assert [(r["name"], r["status"]) for r in got] == [("Adanat_Ok_2", "accepted"), ("Adanat_Draft_1", "draft")]
    assert [r["name"] for r in pub.available(cat, drafts=False)] == ["Adanat_Ok_2"]
    assert pub.accepted_paths(cat) == {"maf/adanat_ok_2/v001"}  # the frozen Max browser gate stays accepted-only


# ---- search index ------------------------------------------------------------------------------------------------
def test_rebuild_index_lists_published_drafts_with_status_and_keeps_a101(tmp_path):
    stale = {"id": "maf_published:Gone@v001", "source": "published", "name": "Gone", "status": "draft"}
    path = unified_file(tmp_path, stale)
    cat = catalogue(rec("Adanat_Draft_1", "draft"), rec("Adanat_Ok_2", "accepted"), rec("Adanat_No_3", "rejected"))
    out = pub.rebuild_index(cat, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == out
    assert [r["name"] for r in data["records"] if r["source"] == "a101"] == ["Adanat_Old_1"]
    published = {r["name"]: r for r in data["records"] if r["source"] == "published"}
    assert set(published) == {"Adanat_Draft_1", "Adanat_Ok_2"}
    d = published["Adanat_Draft_1"]
    assert d["status"] == "draft" and d["version"] == "v001" and d["path"] == "maf/Adanat_Draft_1/v001"
    assert d["article"] == "19121" and d["bbox_mm"]["high"] == {"x": 600.0, "y": 600.0, "z": 800.0}
    assert data["counts"]["published_draft"] == 1 and data["counts"]["published_accepted"] == 1
    assert pub.rebuild_index(cat, path) == out  # idempotent


def test_rebuild_index_refuses_to_write_into_the_catalogue(tmp_path):
    p = tmp_path / "cat.json"
    p.write_text(json.dumps(catalogue()), encoding="utf-8")
    with pytest.raises(pub.PublishError, match="catalogue"):
        pub.rebuild_index(catalogue(), p, catalogue_path=p)


def test_identify_does_not_count_an_indexed_draft_twice(tmp_path):
    cat = catalogue(rec("Adanat_Draft_1", "draft"))
    unified = pub.rebuild_index(cat, unified_file(tmp_path))
    obj = {"identity": {"manufacturer": "Adanat", "article": "19121"}, "size_mm": {"x": 600, "y": 600, "z": 800}}
    got = pub.identify_object(obj, unified, cat, "maf", "Adanat_Other_9")
    assert got["result"] == "duplicate" and [h["from"] for h in got["of"]] == ["published:draft"]


def test_intake_search_offers_drafts_with_their_status(tmp_path):
    unified = pub.rebuild_index(catalogue(rec("Adanat_Draft_1", "draft")), unified_file(tmp_path))
    by_art, a101, _ = ii.maf_library(unified)
    hits = by_art[ii.lib._article_key("19121")]
    assert [(h["name"], h["status"]) for h in hits] == [("Adanat_Draft_1", "draft")]
    assert [r["name"] for r in a101] == ["Adanat_Old_1"]


def _two_objects(root):
    b = root / "batch-synth"
    for k in ("M1", "M2"):
        (b / k).mkdir(parents=True)
        for role in ("high", "low"):
            (b / k / f"{k}_GroundEl_{role}.fbx").write_bytes((k + role).encode())
    return b


def _report():
    mesh = {"name": "X_GroundEl", "polygons": 10, "triangles": 20, "polygon_degrees": {"4": 10},
            "bounds_m": [[-0.3, -0.3, 0.0], [0.3, 0.3, 0.8]], "materials": ["m"], "topology": {}, "maf_surface": None}
    return {"readback_ok": True, "meshes": [mesh],
            "materials": [{"name": "m", "maps": [{"image": "d", "socket": "Base Color"}]}]}


@pytest.fixture
def stub_qa(monkeypatch):
    class Stub:
        @staticmethod
        def maf_findings(meshes, role, src):
            return []
    monkeypatch.setattr(pub, "_twinqa_maf", lambda: Stub)
    monkeypatch.setattr(pub, "blender_readback", lambda f, o, blender=None: _report())


def test_cli_publish_and_accept_rebuild_the_index(tmp_path, stub_qa):
    catp = tmp_path / "cat.json"
    catp.write_text(json.dumps(pub.empty_catalogue()), encoding="utf-8")
    (tmp_path / "idx").mkdir()
    index = unified_file(tmp_path / "idx")
    repo_index = (ROOT / "library/assets/maf_unified.json").read_bytes()
    rc = pub.main(["publish", str(_two_objects(tmp_path)), "--catalogue", str(catp), "--index", str(index),
                   "--evidence", str(tmp_path / "ev"), "--assets-root", str(tmp_path / "assets"),
                   "--unified", str(index)])
    assert rc == 0
    st = {r["name"]: r["status"] for r in json.loads(index.read_text(encoding="utf-8"))["records"]
          if r["source"] == "published"}
    assert st == {"AGR_maf_M1_001": "draft", "AGR_maf_M2_001": "draft"}
    assert pub.main(["accept", "AGR_maf_M1_001", "--words", "ок", "--catalogue", str(catp),
                     "--index", str(index)]) == 0
    st = {r["name"]: r["status"] for r in json.loads(index.read_text(encoding="utf-8"))["records"]
          if r["source"] == "published"}
    assert st == {"AGR_maf_M1_001": "accepted", "AGR_maf_M2_001": "draft"}
    # a catalogue outside the repo never rewrites the repo index; its default index lies next to it
    assert pub.main(["accept", "AGR_maf_M2_001", "--words", "ок", "--catalogue", str(catp)]) == 0
    side = json.loads((tmp_path / "maf_unified.json").read_text(encoding="utf-8"))
    assert {r["name"]: r["status"] for r in side["records"] if r["source"] == "published"}["AGR_maf_M2_001"] \
        == "accepted"
    assert (ROOT / "library/assets/maf_unified.json").read_bytes() == repo_index


def test_rebuild_index_rescans_a101_root_when_given(tmp_path):
    import zipfile
    a101 = tmp_path / "a101"
    a101.mkdir()
    with zipfile.ZipFile(a101 / "GKVysota_Stol_VST9504-1.zip", "w") as zf:
        zf.writestr("GKVysota_Stol_VST9504-1_high.fbx", b"h")
        zf.writestr("GKVysota_Stol_VST9504-1_low.fbx", b"l")
    path = unified_file(tmp_path)
    out = pub.rebuild_index(catalogue(rec("Adanat_Draft_1", "draft")), path, a101_root=a101,
                            cache=tmp_path / "cache", legacy={"entries": [], "spec_matches": []})
    names = [r["name"] for r in out["records"]]
    assert "GKVysota_Stol_VST9504-1" in names and "Adanat_Old_1" not in names and "Adanat_Draft_1" in names
    assert out["sources"]["a101_root"] == a101.as_posix() and out["counts"]["a101"] == 1


def test_repo_index_is_current_with_the_repo_catalogue(tmp_path):
    """No stale index [D421]: the repo search index lists exactly the repo catalogue's draft + accepted records."""
    data = json.loads((ROOT / "library/assets/maf_unified.json").read_text(encoding="utf-8"))
    cat = pub.load_catalogue(pub.CATALOGUE)
    want = sorted((r["name"], r["version"], r["status"]) for r in pub.available(cat, kind="maf"))
    got = sorted((r["name"], r["version"], r["status"]) for r in data["records"] if r.get("source") == "published")
    assert got == want and want  # the #1949 drafts are there
    assert any(r.get("name") == "GKVysota_StolSoSkameykoyIDivanom_VST9504-1" for r in data["records"])


# ---- job close-out guard -----------------------------------------------------------------------------------------
def _outputs(tmp_path):
    out = tmp_path / "outputs" / "maf-v001"
    (out / "M1").mkdir(parents=True)
    (out / "M1" / "M1_GroundEl_v001.fbx").write_bytes(b"m1")
    (out / "SM_Addr_GroundEl.fbx").write_bytes(b"delivery")  # delivery package object, not a library master
    (out / "notes.txt").write_text("x")
    return out


def test_closeout_guard_fails_on_an_unpublished_maf_master(tmp_path):
    out = _outputs(tmp_path)
    miss = pub.unpublished_maf([out], catalogue(), {"records": [A101]})
    assert [(m["key"], Path(m["path"]).name) for m in miss] == [("M1", "M1_GroundEl_v001.fbx")]
    # a draft with that object as origin is a library entry; so is the same file by SHA-256 under another name
    assert pub.unpublished_maf([out], catalogue(rec("AGR_maf_M1_001", "draft", obj="M1")), {"records": []}) == []
    sha = hashlib.sha256(b"m1").hexdigest()
    assert pub.unpublished_maf([out], catalogue(rec("Adanat_X_5", "accepted", obj="Other", sha=sha)),
                               {"records": []}) == []
    assert pub.unpublished_maf([out], catalogue(rec("AGR_maf_M1_001", "rejected", obj="M1")), {"records": []}) == []


def test_closeout_guard_cli_reads_job_yaml_artifacts(tmp_path):
    out = _outputs(tmp_path)
    job = tmp_path / "jobs" / "SYNTH-MAF"
    job.mkdir(parents=True)
    (job / "job.yaml").write_text(yaml.safe_dump({"job_id": "SYNTH-MAF", "artifacts": [
        {"path": str(out / "M1" / "M1_GroundEl_v001.fbx"), "sha256": SHA}]}), encoding="utf-8")
    catp = tmp_path / "cat.json"
    catp.write_text(json.dumps(catalogue()), encoding="utf-8")
    idx = unified_file(tmp_path)
    assert pub.main(["check-job", str(job), "--catalogue", str(catp), "--index", str(idx)]) == 1
    catp.write_text(json.dumps(catalogue(rec("AGR_maf_M1_001", "draft", obj="M1"))), encoding="utf-8")
    assert pub.main(["check-job", str(job), "--catalogue", str(catp), "--index", str(idx)]) == 0
    assert pub.main(["check-job", str(job), "--outputs", str(out), "--catalogue", str(catp),
                     "--index", str(idx)]) == 0


def test_repo_jobs_have_no_unpublished_maf_master():
    cat = pub.load_catalogue(pub.CATALOGUE)
    unified = json.loads((ROOT / "library/assets/maf_unified.json").read_text(encoding="utf-8"))
    for y in sorted((ROOT / "jobs").rglob("job.yaml")):
        paths = pub.job_artifacts(y.parent)
        assert pub.unpublished_maf(paths, cat, unified) == [], y


def test_closeout_guard_refuses_when_nothing_to_check(tmp_path, capsys):
    """Review r1 P1-2: a job with no job.yaml artifacts and no --outputs is not 'clean', it is unchecked."""
    job = tmp_path / "jobs" / "EMPTY"
    job.mkdir(parents=True)
    catp = tmp_path / "cat.json"
    catp.write_text(json.dumps(catalogue()), encoding="utf-8")
    idx = unified_file(tmp_path)
    assert pub.main(["check-job", str(job), "--catalogue", str(catp), "--index", str(idx)]) == 2
    assert "nothing to check: no job.yaml artifacts and no --outputs" in capsys.readouterr().err
    (job / "job.yaml").write_text(yaml.safe_dump({"job_id": "EMPTY", "artifacts": []}), encoding="utf-8")
    assert pub.main(["check-job", str(job), "--catalogue", str(catp), "--index", str(idx)]) == 2


def test_closeout_guard_refuses_a_missing_output_path(tmp_path, capsys):
    job = tmp_path / "jobs" / "MISS"
    job.mkdir(parents=True)
    catp = tmp_path / "cat.json"
    catp.write_text(json.dumps(catalogue()), encoding="utf-8")
    idx = unified_file(tmp_path)
    gone = tmp_path / "no_such_dir"
    assert pub.main(["check-job", str(job), "--outputs", str(gone), "--catalogue", str(catp),
                     "--index", str(idx)]) == 2
    assert f"output path not found: {gone}" in capsys.readouterr().err


def test_closeout_guard_prints_scanned_counts(tmp_path, capsys):
    out = _outputs(tmp_path)
    job = tmp_path / "jobs" / "CNT"
    job.mkdir(parents=True)
    catp = tmp_path / "cat.json"
    catp.write_text(json.dumps(catalogue(rec("AGR_maf_M1_001", "draft", obj="M1"))), encoding="utf-8")
    idx = unified_file(tmp_path)
    assert pub.main(["check-job", str(job), "--outputs", str(out), "--catalogue", str(catp),
                     "--index", str(idx)]) == 0
    line = capsys.readouterr().out
    n_files = sum(1 for p in out.rglob("*") if p.is_file())
    assert f"scanned {n_files} file(s), {len(pub.maf_masters([out]))} MAF master(s)" in line
