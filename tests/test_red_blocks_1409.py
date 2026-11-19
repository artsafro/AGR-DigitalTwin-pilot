"""#1409: route red blocks fixed without a new decision -- library README v007, `agr export-meta`,
L2 coverage of the MAF / Flora sheets named where a repo check exists. Documentation + thin CLI contracts."""
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
import route_map  # noqa: E402

from adapters.max.agr_tools import export_meta  # noqa: E402

REPORT = ROOT / "docs/architecture/report-routes-maf-flora-package.md"
SCENE = (ROOT / "src/twinqa/scene.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------- (1) library-version
def test_library_readme_names_v007_and_pine_id_33():
    text = (ROOT / "library/README.md").read_text(encoding="utf-8")
    current = [line for line in text.splitlines() if "Актуальная версия" in line and "material_ids" in line]
    assert len(current) == 1, current
    assert "material_ids_v007.json" in current[0] and "v005" not in current[0]
    assert "33" in text and "wood_pine" in text and "D240" in text
    data = json.loads((ROOT / "library/maf/material_ids_v007.json").read_text(encoding="utf-8"))
    assert "wood_pine" in json.dumps(data, ensure_ascii=False)
    for rel in re.findall(r"`(library/maf/[^`]+)`", text):
        assert (ROOT / rel).exists(), rel


# ---------------------------------------------------------------- (2) agr export-meta
def _fbx(tmp_path, name="SM_Synthetic.fbx"):
    fbx = tmp_path / name
    fbx.write_bytes(b"synthetic fbx")
    return fbx


def test_agr_export_meta_is_an_existing_route_command():
    assert route_map.command_exists("agr export-meta")
    assert not route_map.command_exists("agr export-meta record")
    stage = next(s for s in route_map.load_routes(ROOT)["package-route"]["stages"] if s["id"] == "meta")
    assert "agr export-meta" in stage["commands"]


def test_record_then_check_roundtrip(tmp_path, capsys):
    fbx = _fbx(tmp_path)
    out = tmp_path / "meta.json"
    assert export_meta.main(["record", str(fbx), "--source", "synthetic", "--top", "3.5", "--out", str(out)]) == 0
    data = export_meta.load_meta(out)
    assert data["h_otn_model_max_z_m"] == 3.5 and data["address"] == "Synthetic" and data["profile"] == "vpm"
    assert export_meta.main(["check", str(out)]) == 0
    assert export_meta.main([str(out)]) == 0  # legacy positional form unchanged
    assert fbx.read_bytes() == b"synthetic fbx"


def test_record_default_sidecar_and_unknown_top(tmp_path):
    fbx = _fbx(tmp_path, "0000_Synthetic_Ground.fbx")
    assert export_meta.main(["record", str(fbx), "--source", "synthetic"]) == 0
    data = export_meta.load_meta(tmp_path / "0000_Synthetic_Ground.fbx.export_meta.json")
    assert data["h_otn_model_max_z_m"] == "unknown" and data["profile"] == "npm"


@pytest.mark.parametrize("top", ["nan", "NaN", "inf", "-inf", "1e400", "", "abc", "0x10"])
def test_record_refuses_nonfinite_or_bad_top_and_writes_nothing(tmp_path, top):
    fbx = _fbx(tmp_path)
    with pytest.raises((ValueError, SystemExit)):
        export_meta.main(["record", str(fbx), "--source", "s", "--top", top])
    assert sorted(p.name for p in tmp_path.iterdir()) == ["SM_Synthetic.fbx"]


@pytest.mark.parametrize("alias", ["same", "dotted", "upper"])
def test_record_output_resolving_to_input_is_refused(tmp_path, alias):
    fbx = _fbx(tmp_path)
    out = {"same": str(fbx), "dotted": str(tmp_path / "." / "SM_Synthetic.fbx"),
           "upper": str(tmp_path / "SM_SYNTHETIC.FBX")}[alias]
    if alias == "upper" and not Path(out).exists():
        pytest.skip("case-sensitive filesystem")
    with pytest.raises((ValueError, OSError)):
        export_meta.main(["record", str(fbx), "--source", "s", "--out", out])
    assert fbx.read_bytes() == b"synthetic fbx"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["SM_Synthetic.fbx"]


def test_record_never_replaces_existing_metadata(tmp_path):
    fbx = _fbx(tmp_path)
    out = tmp_path / "meta.json"
    out.write_text("keep", encoding="utf-8")
    with pytest.raises(OSError):
        export_meta.main(["record", str(fbx), "--source", "s", "--out", str(out)])
    assert out.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("argv", [["record"], ["record", "x.fbx"], ["check"], ["record", "--source", "s"]])
def test_partial_arguments_fail(tmp_path, argv):
    with pytest.raises(SystemExit) as exc:
        export_meta.main(argv)
    assert exc.value.code != 0


def test_missing_fbx_and_unsupported_profile_fail(tmp_path):
    with pytest.raises(ValueError, match="exported FBX missing"):
        export_meta.main(["record", str(tmp_path / "SM_None.fbx"), "--source", "s"])
    fbx = _fbx(tmp_path)
    with pytest.raises(SystemExit):
        export_meta.main(["record", str(fbx), "--source", "s", "--profile", "ifc"])
    assert sorted(p.name for p in tmp_path.iterdir()) == ["SM_Synthetic.fbx"]


def _agr(*args):
    return subprocess.run([sys.executable, "-m", "dt_ai.cli.agr", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=ROOT, timeout=120)


def test_fresh_process_agr_export_meta(tmp_path):
    fbx = _fbx(tmp_path)
    out = tmp_path / "meta.json"
    rec = _agr("export-meta", "record", str(fbx), "--source", "synthetic", "--top", "2.25", "--out", str(out))
    assert rec.returncode == 0, rec.stderr
    assert export_meta.load_meta(out)["h_otn_model_max_z_m"] == 2.25
    chk = _agr("export-meta", "check", str(out))
    assert chk.returncode == 0 and "export_meta valid" in chk.stdout
    bad = tmp_path / "bad.json"
    bad.write_text('{"address": "A", "h_otn_model_max_z_m": NaN, "thumbnail": "unknown"}', encoding="utf-8")
    refused = _agr("export-meta", "check", str(bad))
    assert refused.returncode != 0 and "refused" in refused.stderr
    nan = _agr("export-meta", "record", str(fbx), "--source", "s", "--top", "nan", "--out", str(tmp_path / "n.json"))
    assert nan.returncode != 0 and not (tmp_path / "n.json").exists()
    assert "export-meta" in _agr("--help").stdout


# ---------------------------------------------------------------- (3) checks-coverage
def _rows(rel, prefix):
    text = (ROOT / rel).read_text(encoding="utf-8")
    rows = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip("|").split("|")]
        if line.startswith("|") and cells[0].startswith(prefix):
            rows[cells[0].split(" —")[0]] = cells
    return text, rows


# Rows the repo already checks (partially): row -> finding names that must exist in twinqa.scene_findings.
CLOSED = {
    ("docs/domain/areas/groundel-maf.md", "MAF-"): {
        "MAF-05": ["object types"], "MAF-08": ["triangle count", "ground_triangle_limit"],
        "MAF-15": ["material assignments", "color attributes"], "MAF-17": ["texel density"],
        "MAF-22": ["UCX vs MAF/Flora intersection"], "MAF-24": ["object types"]},
    ("docs/domain/areas/flora.md", "FLO-"): {
        "FLO-07": ["triangle count", "ground_triangle_limit"], "FLO-09": ["texel density"],
        "FLO-12": ["mesh_name_findings"], "FLO-15": ["UCX vs MAF/Flora intersection", "UCX present"]},
}


@pytest.mark.parametrize("sheet", sorted(CLOSED))
def test_existing_checks_are_named_in_l2_coverage(sheet):
    _, rows = _rows(*sheet)
    for row_id, names in CLOSED[sheet].items():
        coverage = rows[row_id][5]
        assert coverage != "none", row_id
        for name in names:
            assert name in SCENE, name
            assert name in coverage, (row_id, name)


@pytest.mark.parametrize("sheet,total", [(("docs/domain/areas/groundel-maf.md", "MAF-"), 24),
                                         (("docs/domain/areas/flora.md", "FLO-"), 17)])
def test_remaining_gaps_counted_and_each_has_a_reason(sheet, total):
    text, rows = _rows(*sheet)
    assert len(rows) == total
    none = {k for k, cells in rows.items() if cells[5] == "none"}
    gaps = text.split("## L2 gaps\n", 1)[1]
    m = re.search(r"\*\*(\d+)\*\* with `none` and \*\*(\d+)\*\*", gaps)
    assert m and (int(m.group(1)), int(m.group(2))) == (len(none), total - len(none))
    listed = dict(re.findall(rf"^- \*\*({sheet[1]}\d\d):\*\* (.*)$", gaps, re.M))
    assert set(listed) == none
    for row_id, line in listed.items():
        assert "No repo check:" in line, row_id


# ---------------------------------------------------------------- report statuses
def test_report_statuses_after_fix():
    text = REPORT.read_text(encoding="utf-8")
    status = dict(re.findall(r"^\| `([a-z0-9-]+)` \| (открыта|снята|обновлена) \|", text, re.M))
    assert status["library-version"] == "снята"
    assert status["meta-v013"] == "обновлена" and status["checks-coverage"] == "обновлена"
    assert not re.search(r"^\| `meta` \| нет команды", text, re.M)
    assert "1. Исправить `library/README.md`" not in text
    assert "2. Команда `agr export-meta`" not in text
    hot = {h["id"]: h["ru"] for h in route_map.load_routes(ROOT)["maf-route"]["hotspots"]}
    assert "library-version" not in hot and "14 из 24" not in hot["checks-coverage"]


def test_float_parse_matches_python_finite_rule():
    # independent oracle for --top parsing: finite floats accepted, everything else refused
    for raw in ["0", "-1.5", "8.65", "1e3", "unknown", "nan", "inf", "1e400", "x"]:
        try:
            value = float(raw)
            ok = math.isfinite(value)
        except ValueError:
            ok = raw == "unknown"
        if ok:
            assert export_meta.parse_top(raw) == ("unknown" if raw == "unknown" else float(raw))
        else:
            with pytest.raises(ValueError):
                export_meta.parse_top(raw)
