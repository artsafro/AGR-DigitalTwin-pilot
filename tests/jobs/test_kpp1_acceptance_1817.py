"""new-case: replay immutable KPP1 delivery acceptance against synthetic evidence."""

import hashlib
import json
from pathlib import Path
import runpy
import warnings
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "jobs/KPP1/lattice-1609/acceptance_1817.py"
GROUND = "0000_Kpp_1_Ground.fbx"


def digest(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def packet(tmp_path):
    # Synthetic evidence, never a delivery approval. Only the expected pins are
    # replaced at the API seam; report projection and verification are real.
    paths = {}
    for profile, archive_name in (("npm", "0000_Kpp_1.zip"), ("vpm", "SM_Kpp_1.zip")):
        folder = tmp_path / profile
        folder.mkdir()
        archive_key = f"{profile}/{archive_name}"
        with ZipFile(tmp_path / archive_key, "w") as archive:
            archive.writestr(GROUND if profile == "npm" else "SM_Kpp_1.fbx", b"synthetic")
        paths[archive_key] = (tmp_path / archive_key).read_bytes()
        stages = [
            {"id": "V001", "status": "fail", "gate": "blocking", "findings": [
                {"name": "GeoJSON", "status": "fail"}]},
            {"id": "V004", "status": "fail", "gate": "blocking", "findings": [
                {"name": "co-directional clearance", "status": "review"},
                {"name": "co-directional clearance", "status": "fail"}]},
            {"id": "V011", "status": "not_run", "gate": "blocking", "findings": []},
            {"id": "V012", "status": "review", "gate": "blocking", "findings": [
                {"name": "archive name", "status": "review"}]},
        ]
        for stage_id in (["V015", "V017"] if profile == "npm" else ["V015", "V016", "V017"]):
            stages.append({"id": stage_id, "status": "not_run", "gate": "manual_review", "findings": [
                {"name": "Flora dimensions", "status": "not_run"}
            ] if profile == "npm" and stage_id == "V015" else []})
        for variant in ("", "-work"):
            key = f"{profile}/validate-{profile}{variant}.json"
            data = {"profile": profile, "passed": False, "exit_code": 1,
                    "target_sha256": digest(paths[archive_key]), "stages": stages}
            paths[key] = json.dumps(data).encode()
            (tmp_path / key).write_bytes(paths[key])
    return paths


def replay(root, packet):
    assert SCRIPT.is_file(), "missing job-local acceptance replay"
    run = runpy.run_path(str(SCRIPT))["replay"]
    pins = {path: digest(data) for path, data in packet.items()}
    rows = {path: {("V004", 0): "accepted_exception", ("V012", 0): "name_accepted_manual_review"}
            for path in packet if path.endswith(".json")}
    return run(root, pins=pins, approved_rows=rows, ground_sha256=digest(b"synthetic"))


def test_overlay_preserves_raw_and_sibling_findings(tmp_path, packet):
    item = replay(tmp_path, packet)["reports"]["npm/validate-npm.json"]
    assert item["raw"] == json.loads(packet["npm/validate-npm.json"])
    assert item["raw"]["passed"] is False
    assert {(r["stage"], r["index"]): (r["raw_status"], r["disposition"])
            for r in item["findings"]} == {
        ("V001", 0): ("fail", "open"),
        ("V004", 0): ("review", "accepted_exception"),
        ("V004", 1): ("fail", "open"),
        ("V012", 0): ("review", "name_accepted_manual_review"),
        ("V015", 0): ("not_run", "open"),
    }
    assert item["manual_accepted"] == ["V015", "V017"]
    assert item["open_stages_without_findings"] == ["V011"]


def test_readiness_exception_is_not_a_missing_geojson_waiver(tmp_path, packet):
    result = replay(tmp_path, packet)
    assert result["readiness"]["s_podz"] == {
        "projects": ["KPP1", "ELV"], "profile": "vpm", "stage": "V011",
        "disposition": "accepted_exception", "decision": "D377", "request_customer_data": False,
    }
    item = result["reports"]["vpm/validate-vpm-work.json"]
    assert item["manual_accepted"] == ["V015", "V016", "V017"]
    assert item["open_stages_without_findings"] == ["V011"]
    assert [(row["stage"], row["raw_status"], row["disposition"]) for row in item["findings"]
            if row["stage"] in {"V012", "V001"}] == [
        ("V001", "fail", "open"), ("V012", "review", "name_accepted_manual_review")]


@pytest.mark.parametrize("mode", ["empty", "missing", "swapped"])
def test_mixed_evidence_refuses_and_resets(tmp_path, packet, mode):
    expected = replay(tmp_path, packet)
    for key, data in reversed(list(packet.items())):
        path = tmp_path / key
        alternative = next(value for value in packet.values() if data != value)
        if mode == "missing":
            path.unlink()
        else:
            path.write_bytes(b"" if mode == "empty" else alternative)
        for _ in range(2):
            with pytest.raises(ValueError, match=key.replace(".", r"\.")):
                replay(tmp_path, packet)
        path.write_bytes(data)
        assert replay(tmp_path, packet) == expected
    assert {p.relative_to(tmp_path).as_posix(): p.read_bytes() for p in tmp_path.rglob("*")
            if p.is_file()} == packet


@pytest.mark.parametrize("replacement", [b"NaN", b"Infinity", b"5.0", b"[]", b"{}", b"null",
                                         b'false, "passed": true'])
def test_changed_report_is_not_recognized(tmp_path, packet, replacement):
    key = "npm/validate-npm.json"
    (tmp_path / key).write_bytes(packet[key].replace(b'"passed": false', b'"passed": ' + replacement, 1))
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        replay(tmp_path, packet)


@pytest.mark.parametrize("duplicate", [False, True])
def test_ground_member_must_be_byte_identical(tmp_path, packet, duplicate):
    key = "npm/0000_Kpp_1.zip"
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Duplicate name")
        with ZipFile(tmp_path / key, "w") as archive:
            archive.writestr(GROUND, b"synthetic" if duplicate else b"changed!!")
            if duplicate:
                archive.writestr(GROUND, b"synthetic")
    packet[key] = (tmp_path / key).read_bytes()
    with pytest.raises(ValueError, match=GROUND):
        replay(tmp_path, packet)
