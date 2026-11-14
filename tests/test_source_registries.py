"""Customer source store and job source registries (#1239).

Read-only checks of the committed `jobs/<ID>/sources.json` registries (KPP1, ELV, Flora run-v004)
and of the store line in AGENTS.md / TASK_TO_MODEL.md. The walker run hashes the files on this
machine when they are reachable; elsewhere the rows are `unreachable`, never `mismatch`.
"""
import hashlib
import json
from pathlib import Path

import pytest

from dt_ai import procedure as p

ROOT = Path(__file__).resolve().parents[1]
TAG = "external-inputs/1"
STORE = "G:/Мой диск/AGR-assets/"
OBJECT_STORE = "G:/Мой диск/AGR-assets/<object>/source/"
REGISTRIES = {
    "KPP1": "jobs/KPP1/sources.json",
    "ELV": "jobs/elv-tc-vpm/sources.json",
    "Flora": "jobs/VATUTINO-SITE/sources.json",
}
KINDS = ("customer-source", "delivered-output")


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def file_ref(rel):
    return {"path": rel, "sha256": hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), "manifest": TAG}


def test_agents_and_procedure_name_the_object_source_store():
    for doc in ("AGENTS.md", "docs/procedure/TASK_TO_MODEL.md"):
        text = (ROOT / doc).read_text(encoding="utf-8")
        assert OBJECT_STORE in text, doc
        assert "SHA256SUMS.txt" in text, doc


@pytest.mark.parametrize("name", sorted(REGISTRIES))
def test_registry_format(name):
    rel = REGISTRIES[name]
    reg = load(rel)
    assert reg["manifest"] == TAG and reg["registry"] == "job-sources/1"
    assert reg["job"] == Path(rel).parent.name and reg["synthetic"] is False
    assert reg["asset_store"] == STORE
    rows = p.parse_external_manifest((ROOT / rel).read_bytes())
    assert rows, rel
    for row in reg["files"]:
        assert row["location"] in ("asset-store", "named-folder"), row["path"]
        assert (row["location"] == "asset-store") == row["path"].startswith(STORE), row["path"]
        assert row["kind"] in KINDS, row["path"]
        assert row["folder"] and row["path"].startswith(row["folder"].split(" (")[0]), row["path"]


def test_kpp1_dwgs_live_in_the_object_store_with_cold_run_hashes():
    reg = load(REGISTRIES["KPP1"])
    cold = {r["path"]: r["sha256"] for r in load("jobs/KPP1/cold-run-1172/inputs-manifest.json")["files"]}
    dwgs = [r for r in reg["files"] if r["path"].endswith(".dwg")]
    assert len(dwgs) == 3
    for row in dwgs:
        assert row["path"].startswith(STORE + "KPP1/source/") and row["location"] == "asset-store"
        assert row["path"].rsplit("/", 1)[1] == row["original_path"].rsplit("/", 1)[1]
        assert cold[row["original_path"]] == row["sha256"]
    # every cold-run source is in the registry exactly once (by hash)
    assert sorted(r["sha256"] for r in reg["files"]) == sorted(cold.values())


def test_elv_registry_covers_task_sources():
    reg = load(REGISTRIES["ELV"])
    names = {r["path"].rsplit("/", 1)[1]: r for r in reg["files"]}
    assert set(names) == {
        "00900-МСК-ЭЛВ-ГП1-Р-АР_building (1).fbx",
        "ЭЛВ_ИД_АГР_45-4-25-С_Буклет АГР от 27.01.2025 (1) (1).pdf",
        "TC_Sreda-04-11-2026-1.pur", "SREDA_fasad_v0.6.blend", "SM_Elevatornaya_Vl_1_A_001.zip",
    }
    passport = load("jobs/elv-tc-vpm/passport.json")
    assert names["00900-МСК-ЭЛВ-ГП1-Р-АР_building (1).fbx"]["sha256"] in json.dumps(passport)
    # TASK.md abbreviates the customer TZ hashes as <first 8>…<last 4>
    task = (ROOT / "jobs/elv-tc-vpm/TASK.md").read_text(encoding="utf-8")
    for name in ("TC_Sreda-04-11-2026-1.pur", "SREDA_fasad_v0.6.blend", "SM_Elevatornaya_Vl_1_A_001.zip"):
        digest = names[name]["sha256"]
        assert f"{digest[:8]}…{digest[-4:]}" in task, name


def test_flora_registry_is_the_run_v004_delivered_output():
    reg = load(REGISTRIES["Flora"])
    run = "G:/Мой диск/AGR-evidence/1146-flora-star/run-v004/"
    assert all(r["path"].startswith(run) and r["kind"] == "delivered-output" for r in reg["files"])
    sums = next(r for r in reg["files"] if r["path"] == run + "SHA256SUMS.txt")
    assert sums["sha256"].startswith("21a13860") and sums["sha256"].endswith("1d75ae2")  # flora-route-a-v004.md
    assert {r["path"].rsplit("/", 1)[1] for r in reg["files"]} >= {
        "SM_VATUTINO-SITE_Flora_NPM_v007.fbx", "SM_VATUTINO-SITE_Flora_VPM_v007.fbx"}


def test_walker_passes_on_every_registry():
    """The #1229 walker re-hashes every row: equal here, unreachable elsewhere, never mismatch."""
    refs = [file_ref(rel) for rel in REGISTRIES.values()]
    job = {"schema_version": "1.0.0", "job_id": "REGISTRY-CHECK", "run_id": "issue-1239", "synthetic": True,
           "path": "standard", "inputs": refs, "artifacts": [], "deviations": [],
           "gates": {g: {"status": "missing", "note": "SYNTHETIC", "evidence": []} for g in p.GATES}}
    job["gates"]["inputs"] = {"status": "review", "note": "SYNTHETIC wrapper", "evidence": refs}
    report = p.inspect_job(job, ROOT)
    row = next(r for r in report["gates"] if r["gate"] == "inputs")
    assert row["errors"] == []
    total = sum(len(load(rel)["files"]) for rel in REGISTRIES.values())
    assert len(row["external_inputs"]) == total
    assert {r["status"] for r in row["external_inputs"]} <= {"equal", "unreachable"}


def test_tampered_registry_row_never_passes_as_equal(tmp_path):
    """Probe: flip one hash at a time in every registry row (12 rows): never `equal`."""
    seen = 0
    for rel in REGISTRIES.values():
        reg = load(rel)
        for i in range(len(reg["files"])):
            bad = json.loads(json.dumps(reg))
            digest = bad["files"][i]["sha256"]
            bad["files"][i]["sha256"] = ("0" if digest[0] != "0" else "1") + digest[1:]
            data = json.dumps(bad, ensure_ascii=False).encode("utf-8")
            target = tmp_path / f"{seen}" / rel
            target.parent.mkdir(parents=True)
            target.write_bytes(data)
            ref = {"path": rel, "sha256": hashlib.sha256(data).hexdigest(), "manifest": TAG}
            job = {"schema_version": "1.0.0", "job_id": "SYNTHETIC", "run_id": "probe", "synthetic": True,
                   "path": "standard", "inputs": [ref], "artifacts": [], "deviations": [],
                   "gates": {g: {"status": "missing", "note": "SYNTHETIC", "evidence": []} for g in p.GATES}}
            job["gates"]["inputs"] = {"status": "pass", "note": "SYNTHETIC", "evidence": [ref]}
            row = next(r for r in p.inspect_job(job, tmp_path / f"{seen}")["gates"] if r["gate"] == "inputs")
            status = row["external_inputs"][i]["status"]
            assert status in ("mismatch", "unreachable"), (rel, i, status)
            assert row["ready"] is False and (status == "unreachable" or row["errors"]), (rel, i)
            seen += 1
    assert seen == sum(len(load(rel)["files"]) for rel in REGISTRIES.values())


def test_kpp1_store_sha256sums_matches_registry():
    sums = Path(STORE + "KPP1/source/SHA256SUMS.txt")
    if not sums.is_file():
        pytest.skip("asset store not on this machine")
    listed = {}
    for line in sums.read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        listed[name] = digest
    reg = load(REGISTRIES["KPP1"])
    dwgs = {r["path"].rsplit("/", 1)[1]: r["sha256"] for r in reg["files"] if r["path"].endswith(".dwg")}
    assert listed == dwgs
