"""#1715: the MAF route / context maps describe the checked code, not a proposed pipeline (D293 kept).

Each test pins one acceptance point of the issue to the YAML sources AND to the code fact it describes, so a
map edge that drifts from the code (or code that drifts from the map) fails here.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
import route_map  # noqa: E402

ARCH = ROOT / "docs/architecture"
REPORT = ARCH / "report-routes-maf-flora-package.md"
NPM_LIGHT = "tools/library/maf_npm_light.py"
ATLAS_MAF = "tools/materials/atlas_maf.py"
ATLAS_MAX = "adapters/max/agr_tools/flora_atlas_max.py"
PLACE_CORE = "adapters/max/agr_tools/place_core.py"


def _cmap():
    return route_map.load_context_maps(ROOT)["maf-contexts"]


def _events():
    return route_map.load_routes(ROOT)["maf-route"]


def _ctx(owner):
    found = [c for c in _cmap()["contexts"] if c["owner"] == owner]
    assert len(found) == 1, (owner, [c["id"] for c in found])
    return found[0]


def _rels():
    return _cmap()["relations"]


def _stage(sid):
    return next(s for s in _events()["stages"] if s["id"] == sid)


def _text(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _drawn(stem):
    doc = json.loads((ARCH / f"{stem}.excalidraw").read_text(encoding="utf-8"))
    return "\n".join(e["text"] for e in doc["elements"] if e["type"] == "text")


# ---------------------------------------------------------------- acceptance 1: actual atlas link
def test_atlas_maf_feeds_maf_npm_light_png_and_uv_json_by_material_name():
    atlas, light = _ctx(ATLAS_MAF), _ctx(NPM_LIGHT)
    edges = [r for r in _rels() if r["from"] == atlas["id"] and r["to"] == light["id"]]
    assert len(edges) == 1
    assert "PNG" in edges[0]["ru"] and "UV JSON" in edges[0]["ru"] and "имя материала" in edges[0]["ru"]
    assert "build_atlas" in {f["name"] for f in atlas["functions"]}
    # code facts behind the edge: build_atlas writes PNG + JSON keyed by slot.name; maf_npm_light reads both
    src = (ROOT / ATLAS_MAF).read_text(encoding="utf-8")
    assert "def build_atlas(list_path: str | Path, out_png: str | Path, out_json: str | Path)" in src
    assert "materials[slot.name] = {" in src
    light_src = (ROOT / NPM_LIGHT).read_text(encoding="utf-8")
    assert 'rects = {name: m["uv"] for name, m in atlas["materials"].items()}' in light_src
    assert "Program choice: Blender headless" in light_src


def test_1410_is_a_technical_run_not_delivery_or_v007_proof():
    branch = next(b for b in _stage("npm")["branches"] if b["id"] == "atlas")
    assert "#1410" in branch["ru"] and "технический прогон" in branch["ru"]
    assert "не сдача" in branch["ru"] and "v007" in branch["ru"]
    assert "jobs/SIL13-COLD-1315/maf-npm-light-1410/result.md" in branch["evidence"]
    assert "NOT a delivery" in (ROOT / "jobs/SIL13-COLD-1315/maf-npm-light-1410/result.md").read_text(encoding="utf-8")


def test_atlas_groundel_is_a_separate_max_producer_not_a_consumer_of_the_pair():
    mx = _ctx(ATLAS_MAX)
    assert "atlas_groundel" in {f["name"] for f in mx["functions"]}
    assert mx.get("serves_stage") == "npm"
    atlas = _ctx(ATLAS_MAF)
    assert not [r for r in _rels() if r["from"] == atlas["id"] and r["to"] == mx["id"]]
    assert "не читает" in _text(mx)
    # code fact: the Max tool writes its own atlas PNG from the scene and never opens atlas_maf output
    src = (ROOT / ATLAS_MAX).read_text(encoding="utf-8")
    assert "core.atlas_png(laid)" in src and "atlas_maf" not in src and "uv_json" not in src


def test_no_mandatory_tool_d293():
    npm = _stage("npm")
    assert "D293" in npm["rules"] and npm["actor"] == "agent-dcc"
    branch = next(b for b in npm["branches"] if b["id"] == "atlas")
    assert "D293" in branch["rules"] and "Blender" in branch["ru"] and "Max" in branch["ru"]
    assert not re.search(r"(обязател|только Blender|только Max)", _text(_events()) + _text(_cmap()))


# ---------------------------------------------------------------- acceptance 2: placement-side gap check
def test_place_maf_checks_is_a_separate_gap_check_not_a_duplicate_and_not_d095():
    gap = _ctx(PLACE_CORE)
    assert {"maf_checks", "maf_verdict"} <= {f["name"] for f in gap["functions"]}
    assert gap.get("serves_stage") == "placement"
    assert "duplicates" not in gap and "duplicates" not in _ctx("src/twinqa/maf_checks.py")
    text = _text(gap)
    assert "place.maf_checks" in text and "не дубль" in text and "D095" in text and "не заменяет" in text
    branch = next(b for b in _stage("placement")["branches"] if b["id"] == "gap-check")
    assert PLACE_CORE in branch["evidence"] and "D095" in branch["rules"] and "не заменяет" in branch["ru"]
    # code fact: the default target gap is 0.0 m (not the D095 10 cm sink)
    src = (ROOT / PLACE_CORE).read_text(encoding="utf-8")
    assert "def maf_verdict(gap, gap_m=0.0," in src and "_num(options, 'gap_m', 0.0," in src


# ---------------------------------------------------------------- acceptance 3: no unconditional handoffs
def test_no_size_approved_only_or_points_to_atlas_claims():
    labels = {(r["from"], r["to"]): r["ru"] for r in _rels()}
    assert "модель в допуске" not in labels.values()
    assert "точки МАФ" not in labels.values()
    atlas = _ctx(ATLAS_MAF)["id"]
    assert not [k for k in labels if k == ("maf-checks", atlas)]
    assert not [k for k in labels if k[0] == "placement" and k[1] in {atlas, _ctx(ATLAS_MAX)["id"]}]


def test_placement_input_vs_unverified_conversion_handoff():
    light = _ctx(NPM_LIGHT)["id"]
    labels = {(r["from"], r["to"]): r["ru"] for r in _rels()}
    assert "уже" in labels[("maf-library", "placement")]
    assert "не проверен" in labels[("placement", light)]
    convert = next(b for b in _stage("npm")["branches"] if b["id"] == "convert")
    assert "не проверен" in convert["ru"] and "source_fbx" in convert["ru"]


def test_archived_dimension_verdict_has_no_reproduced_writer():
    hot = {h["id"]: h for h in _events()["hotspots"]}["dims-writer"]
    assert hot["stage"] == "dims" and "jobs/VATUTINO-SITE/maf/site-maf-set.json" in hot["evidence"]
    assert "не воспроизведён" in hot["ru"]
    saved = json.loads((ROOT / "jobs/VATUTINO-SITE/maf/site-maf-set.json").read_text(encoding="utf-8"))
    assert saved["checks"]["dimension_counts"]
    cmds = " ".join(c["cmd"] for c in saved["commands"])
    # recorded commands: atlas, build, readback; none of them is a dimension-verdict writer
    assert len(saved["commands"]) == 3 and "dimension" not in cmds and "maf_site_set.py" not in cmds


# ---------------------------------------------------------------- acceptance 4: placement evidence
def test_legacy_runner_can_pass_with_mismatch_and_archive_omits_parity():
    hot = {h["id"]: h for h in _events()["hotspots"]}["placement-parity"]
    assert hot["stage"] == "placement"
    assert {"jobs/VATUTINO-SITE/place_site.py", "src/dt_ai/placement/site.py",
            "jobs/VATUTINO-SITE/placement-report.json"} <= set(hot["evidence"])
    assert "legacy" in hot["ru"] and "parity" in hot["ru"] and "строг" in hot["ru"]
    # code facts: legacy (strict=False) only records parity; strict stops with code 4; the summary has no parity
    site = (ROOT / "src/dt_ai/placement/site.py").read_text(encoding="utf-8")
    assert site.count('if strict and not par["identical"]:') == 2
    assert 'results["status"] = "qa_failed" if qa_failed else "pass"' in site
    assert "strict=False" in (ROOT / "jobs/VATUTINO-SITE/place_site.py").read_text(encoding="utf-8")
    report = json.loads((ROOT / "jobs/VATUTINO-SITE/placement-report.json").read_text(encoding="utf-8"))
    assert "parity" not in json.dumps(report)


def test_sources_report_and_generated_maps_agree():
    assert route_map.main(["--check"]) == 0
    route, ctx = _drawn("maf-route"), _drawn("maf-contexts")
    for needle in ("place.maf_checks", "atlas_groundel", "PNG + UV JSON", "не проверен"):
        assert needle in ctx, needle
    assert "#1410" in route and "legacy" in route
    section = REPORT.read_text(encoding="utf-8").split("## МАФ", 1)[1].split("\n## ", 1)[0]
    for hid in ("placement-parity", "dims-writer"):
        assert f"- `{hid}`" in section and f"| `{hid}` | открыта |" in section
    assert "place.maf_checks" in section and "atlas_groundel" in section


@pytest.mark.parametrize("label", ["модель в допуске", "точки МАФ"])
def test_removed_claims_are_not_drawn(label):
    doc = json.loads((ARCH / "maf-contexts.excalidraw").read_text(encoding="utf-8"))
    drawn = {" ".join(e["text"].split()) for e in doc["elements"] if e["type"] == "text"}
    assert label not in drawn
