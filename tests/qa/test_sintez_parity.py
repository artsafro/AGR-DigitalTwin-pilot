"""new-case: synthetic SINTEZ shared-check parity contract (#432)."""
import pytest


def vendor_report(state="verified", errors=0, recommendations=0):
    return {"error": None, "lp": [dict(req_num="1.1.1", state=state, auto=True,
            errors_count=errors, recommendations_count=recommendations)], "hp": []}


def test_compare():
    from tools.sintez_parity import compare
    case = fixtures()[0]
    assert compare(case, vendor_report(), {"status": "pass", "req_num": "1.1.1"})["agreement"]
    assert not compare(case, vendor_report("failed", 1), {"status": "pass", "req_num": "1.1.1"})["agreement"]
    assert not compare(case, vendor_report(), {"status": "not_measured", "req_num": "1.1.1"})["agreement"]


@pytest.mark.parametrize("bad", [
    {}, {"error": "crashed", "lp": [], "hp": []}, vendor_report("undefined"),
    vendor_report("unknown"), vendor_report("verified", 1), vendor_report("failed"),
    vendor_report("verified", float("nan")), vendor_report("verified", float("inf")),
    {"error": None, "lp": vendor_report()["lp"]*2, "hp": []},
])
def test_invalid_vendor_report(bad):
    from tools.sintez_parity import compare
    with pytest.raises(ValueError):
        compare(fixtures()[0], bad, {"status": "pass", "req_num": "1.1.1"})


@pytest.mark.parametrize("state", ["verified", "failed", "undefined", "unknown"])
@pytest.mark.parametrize("errors,recs", [(0,0), (0,1), (1,0), (1,1)])
def test_vendor_state_lattice(state, errors, recs):
    from tools.sintez_parity import compare
    valid = (state == "verified" and errors == recs == 0) or (state == "failed" and bool(errors or recs))
    report = vendor_report(state, errors, recs)
    ours = {"status": "pass", "req_num": "1.1.1"}
    if not valid:
        with pytest.raises(ValueError):
            compare(fixtures()[0], report, ours)
    else:
        result = compare(fixtures()[0], report, ours)
        assert result["agreement"] is (state == "verified")
        assert result["vendor"]["status"] == ("fail" if errors else "review" if recs else "pass")


def test_compare_order_and_repeat():
    from tools.sintez_parity import compare
    report = vendor_report()
    report["lp"].append(dict(report["lp"][0], req_num="other"))
    expected = compare(fixtures()[0], report, {"status":"pass", "req_num":"1.1.1"})
    report["lp"].reverse()
    for _ in range(3):
        assert compare(fixtures()[0], report, {"status":"pass", "req_num":"1.1.1"}) == expected
    assert not compare(fixtures()[0], vendor_report("failed",1), {"status":"pass", "req_num":"1.1.1"})["agreement"]

from tools.sintez_parity import fixtures


@pytest.mark.parametrize("case", fixtures(), ids=lambda c: c["id"])
def test_twinqa_fixture(case):
    from tools.sintez_parity import evaluate, payload

    result = evaluate(case, payload(case))
    expected = "fail" if "transforms" in case["group"] else case["variant"]
    if case["group"] == "hp_polycount" and case["variant"] == "pass":
        expected = "review"
    if case["group"] == "lp_pivot":
        expected = "not_measured"
    assert result["status"] == expected
    assert result["req_num"] == case["req_num"]




@pytest.mark.parametrize("field,value", [("readback", {}), ("images", {}), ("geojson", b""),
    ("uv", []), ("uv", [[float("nan"),0]]*3), ("uv", [[float("inf"),0]]*3)])
def test_invalid_payload(field, value):
    from tools.sintez_parity import evaluate, payload
    g = {"images":"hp_png", "geojson":"hp_json_properties", "uv":"lp_uv", "readback":"lp_polycount"}[field]
    case = next(c for c in fixtures() if c["group"]==g and c["variant"]=="pass")
    data = payload(case); data[field] = value
    with pytest.raises(ValueError):
        evaluate(case,data)


@pytest.mark.parametrize("field,value", [("topology", None), ("topology", {}),
    ("topology", {"isolated_vertices": 0}), ("uv_channels", None)])
def test_partial_topology_evidence(field, value):
    from tools.sintez_parity import evaluate, payload
    case = next(c for c in fixtures() if c["id"] == "lp_duplicates-pass")
    data = payload(case)
    data["readback"]["meshes"][0][field] = value
    with pytest.raises(ValueError):
        evaluate(case, data)


def test_unknown_fixture():
    from tools.sintez_parity import payload
    with pytest.raises(ValueError,match="fixture"):
        payload(dict(fixtures()[0],group="unknown"))


def test_output_safety(tmp_path):
    from tools.sintez_parity import run_live
    source = tmp_path/"fixture.json"
    source.write_text("KEEP")
    alias = tmp_path/"alias.json"
    alias.hardlink_to(source)
    for path in (source,alias,tmp_path):
        with pytest.raises(FileExistsError):
            run_live(fixtures()[0],path,"must-not-launch")
    assert source.read_text() == "KEEP"
    assert alias.read_text() == "KEEP"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["alias.json","fixture.json"]


def test_archive_mutation_is_not_accepted(tmp_path, monkeypatch):
    import json
    import subprocess
    from pathlib import Path
    from tools.sintez_parity import run_live, payload
    case = fixtures()[0]
    out = tmp_path / "owned"

    def fake_blender(cmd, **kwargs):
        # Substitute only the external process seam, including a hostile vendor write.
        if "sintez_parity_fixture.py" in cmd[6]:
            data = payload(case)
            (out / data["readback"]["source"]).write_bytes(data["header"])
            (out / "readback.json").write_text(json.dumps(dict(
                blender="5.1.2", extension_version="1.6.1",
                readback=data["readback"], uv=data["uv"])))
        else:
            archive = next((out / "packages").glob("*.zip"))
            archive.write_bytes(archive.read_bytes() + b"changed")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_blender)
    with pytest.raises(ValueError, match="ZIP changed"):
        run_live(case, out, "synthetic-process-seam")
    assert not (out / "comparison.json").exists()


def test_cli(tmp_path):
    import json
    import subprocess
    import sys
    from tools.sintez_parity import ROOT
    out = tmp_path/"fresh"
    cmd = [sys.executable,"-m","tools.sintez_parity","--output",str(out)]
    done = subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    assert done.returncode == 0,done.stderr
    report = json.loads((out/"summary.json").read_text())
    assert len(report["rows"]) == 30
    assert report["dcc_executed"] is False
    assert all(r["vendor"] == "not_measured" for r in report["rows"])
    before = (out/"summary.json").read_bytes()
    assert subprocess.run(cmd,cwd=ROOT,capture_output=True).returncode != 0
    assert (out/"summary.json").read_bytes() == before


def test_symbol_fixture_survives_blender_name_limit():
    from tools.sintez_parity import payload
    cases = [c for c in fixtures() if c["group"] == "hp_naming_symbols"]
    names = [payload(c)["readback"]["meshes"][0]["name"] for c in cases]
    assert all(len(n.encode("utf-8")) <= 63 for n in names)
    assert all(ord(char) < 128 for char in names[0])
    assert any(ord(char) >= 128 for char in names[1])
    assert {c["req_num"] for c in cases} == {"2.10.1"}


def test_inventory_coverage():
    from tools.sintez_parity import fixtures, inventory

    groups = inventory()
    assert len(groups) == 15  # Inventory has 14 same + 1 stricter, despite issue's 13+1.
    assert {g["status"] for g in groups.values()} == {"same", "stricter"}
    cases = fixtures()
    assert len(cases) == 30
    assert {c["group"] for c in cases} == set(groups)
    for group in groups:
        assert {c["variant"] for c in cases if c["group"] == group} == {"pass", "fail"}
        assert all(c["synthetic"] is True for c in cases if c["group"] == group)
