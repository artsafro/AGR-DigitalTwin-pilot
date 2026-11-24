"""#1853: Ground route map — correct atlas evidence, UDIM ownership and v015 reference.

Documentation contracts, not geometry checks or delivery acceptance. Pins the corrections verified on main:
- the Ground `npm` / `convert` stages no longer cite the OKS atlas recipe `tools/derive/npm_atlas.py`, and describe
  the real scope of the `atlas.groundel` npm profile (GroundEl / MAF only, no end-to-end Flora conversion);
- the shared UDIM kernel serves `ground` (`udim_of_cell`, `udim -> ground`) and the Ground context map shows the
  existing `npm_atlas_udim.py` live bypass under the shared atlas owner `atlas_core.py`;
- GND-09 links the NPM atlas contract to UV-08 while keeping GND-08 as the density reference;
- `xview-parked` cites Vatutino v015 as the 2026-11-09 delivery report names it, without clearing the xView findings.

Pattern: n/a | new-case: Ground route-map documentation regression test (#1853).
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
import route_map  # noqa: E402

ARCH = ROOT / "docs/architecture"
REPORT = ARCH / "report-routes-vpm-ground.md"
SHEET = ROOT / "docs/domain/areas/ground-surface.md"


def _routes():
    return route_map.load_routes(ROOT)


def _maps():
    return route_map.load_context_maps(ROOT)


def _stage(events, sid):
    return next(s for s in events["stages"] if s["id"] == sid)


# ---------------------------------------------------------------- npm / convert atlas evidence
def test_1853_npm_and_convert_do_not_cite_the_oks_atlas_recipe():
    events = _routes()["ground-route"]
    npm = _stage(events, "npm")
    assert "tools/derive/npm_atlas.py" not in npm["evidence"]
    # npm_atlas_udim.py is a job-specific live bypass of atlas_core with no Ground master->atlas->NPM
    # FBX run; it is NOT working evidence for "Ground на атласе" and must stay out of npm.evidence.
    assert "tools/materials/npm_atlas_udim.py" not in npm["evidence"]
    assert "adapters/max/agr_tools/flora_atlas_max.py" in npm["evidence"]
    branches = {b["id"]: b for b in npm["branches"]}
    assert "tools/derive/npm_atlas.py" not in branches["convert"]["evidence"]
    assert branches["convert"]["evidence"] == ["adapters/max/agr_tools/flora_atlas_max.py"]


def test_1853_npm_atlas_udim_cited_on_ground_atlas_hotspot_as_unproven_bypass():
    events = _routes()["ground-route"]
    hotspot = next(h for h in events["hotspots"] if h["id"] == "ground-atlas")
    assert hotspot["stage"] == "npm"
    # the live bypass is shown under the shared atlas owner, not as a working Ground->atlas handoff
    assert "tools/materials/npm_atlas_udim.py" in hotspot["evidence"]
    for token in ("job-specific", "обход atlas_core", "не доказан", "не измерен"):
        assert token in hotspot["ru"], token


def test_1853_convert_describes_atlas_groundel_real_scope_not_end_to_end_flora():
    convert = {b["id"]: b for b in _stage(_routes()["ground-route"], "npm")["branches"]}["convert"]
    for token in ("atlas.groundel", "профиль npm", "GroundEl", "2048", "заглушк"):
        assert token in convert["ru"], token
    # no end-to-end Flora conversion is asserted, and the Ground surface is explicitly out of these tools' scope
    assert "сквозная конвертация Флоры" in convert["ru"]
    assert "поверхность Ground эти инструменты не покрывают" in convert["ru"]


# ---------------------------------------------------------------- shared UDIM ownership
def test_1853_ground_map_shows_udim_to_ground_and_udim_of_cell():
    cmap = _maps()["ground-contexts"]
    kernel = cmap["shared_kernel"]
    assert kernel["id"] == "udim" and kernel["owner"] == "adapters/max/agr_tools/udimtile_core.py"
    funcs = {f["name"]: f["contract"] for f in kernel["functions"]}
    assert "udim_of_cell" in funcs
    assert "номер тайла" in funcs["udim_of_cell"]
    udim_rels = [r for r in cmap["relations"] if r["from"] == "udim"]
    assert any(r["to"] == "ground" for r in udim_rels), udim_rels
    assert any(r["to"] == "ground-export" for r in udim_rels)


def test_1853_npm_atlas_udim_live_bypass_under_the_shared_atlas_owner():
    cmap = _maps()["ground-contexts"]
    uv_atlas = next(c for c in cmap["contexts"] if c["id"] == "uv-atlas")
    assert uv_atlas["owner"] == "adapters/max/agr_tools/atlas_core.py"
    dup = next(d for d in uv_atlas["duplicates"] if d["at"] == "tools/materials/npm_atlas_udim.py:785")
    assert dup["status"] == "live-bypass" and dup["step"] == "#1380"
    assert dup["issue"] == "#1141" and "def main(" in dup["match"]


def test_1853_rendered_ground_context_map_shows_udim_of_cell():
    svg = (ARCH / "ground-contexts.svg").read_text(encoding="utf-8")
    assert "udim_of_cell" in svg


# ---------------------------------------------------------------- GND-09 -> UV-08
def test_1853_gnd09_links_npm_atlas_contract_to_uv08_and_keeps_gnd08_density():
    row = next(s for s in SHEET.read_text(encoding="utf-8").splitlines() if s.startswith("| GND-09 —"))
    assert "NPM atlas contract" in row
    assert "GND-08 (density)" in row
    assert "UV-08" in row and "uv-atlas.md" in row
    assert "baking vs slicing" in row


# ---------------------------------------------------------------- xview-parked v015 reference
def test_1853_xview_parked_cites_v015_without_clearing_findings():
    events = _routes()["ground-route"]
    note = next(h for h in events["hotspots"] if h["id"] == "xview-parked")
    assert note["stage"] == "validate"
    assert "v015" in note["ru"]
    assert "docs/deliveries/vatutino-site-2026-11-09.md" in note["evidence"]
    for token in ("называет v015", "не сняты", "приёмка не подтверждена"):
        assert token in note["ru"], token
    # the version question is answered by the delivery report, not left to Artem
    assert "сверить с Артёмом" not in note["ru"]
    report = REPORT.read_text(encoding="utf-8")
    assert re_search_2026_11_09(report)


def re_search_2026_11_09(text):
    import re
    return re.search(r"`xview-parked`.*2026-11-09", text) is not None


# ---------------------------------------------------------------- reconciliation + schema
def test_1853_ground_route_and_maps_still_pass_route_map_checks():
    events, maps = _routes()["ground-route"], _maps()
    route_map.check_schema(events, maps["contexts"])
    assert route_map.route_coverage(events, maps["contexts"], maps["ground-contexts"]) == []
    assert route_map.verify_references(ROOT, events, maps["contexts"]) == []
    assert route_map.verify_references(ROOT, {"stages": [], "hotspots": []}, maps["ground-contexts"]) == []
