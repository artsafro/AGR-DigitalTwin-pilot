"""#1375: branching stages of the NPM/OKS route (Artem's decisions 2026-11-14, D289)."""
import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
import mini_yaml  # noqa: E402
import route_map  # noqa: E402

EXPECTED = {
    "model": {"vpm-npm-master", "npm-only-direct", "window-library", "window-generator"},
    "uv": {"atlas-udim", "atlas-material-ids"},
    "export": {"package-vpm", "package-npm"},
}


def _events():
    return mini_yaml.load(ROOT / route_map.EVENTS), mini_yaml.load(ROOT / route_map.CONTEXTS)


def _branches(events):
    return {s["id"]: {b["id"] for b in s.get("branches", [])} for s in events["stages"] if s.get("branches")}


def test_route_has_the_decided_branches_each_citing_d289():
    events, _ = _events()
    assert _branches(events) == EXPECTED
    for s in events["stages"]:
        for b in s.get("branches", []):
            assert "D289" in b["rules"], (s["id"], b["id"])
    roof = next(h for h in events["hotspots"] if h["id"] == "parapet-roof-seam")
    assert "D289" in roof["rules"]


def test_d289_row_records_the_five_decisions():
    rows = re.findall(r"^\| D289 \|.*$", (ROOT / "docs/decisions.md").read_text(encoding="utf-8"), re.M)
    assert len(rows) == 1
    row = rows[0]
    for needle in ("NPM-only", "mid-poly", "UDIM", "material ID", "library", "#1361", "parapet", "window generator"):
        assert needle in row, needle


def test_every_branch_is_drawn_with_its_condition_and_rules():
    events, contexts = _events()
    doc = json.loads(route_map.route_board(events, contexts).excalidraw())
    texts = {e["id"]: e["text"] for e in doc["elements"] if e["type"] == "text"}
    joined = "\n".join(texts.values())
    for s in events["stages"]:
        for b in s.get("branches", []):
            assert b["when_ru"] in joined and b["ru"] in joined, b["id"]
    assert "зелёный — ветка" in joined


def test_board_without_branches_is_unchanged_by_the_branch_feature():
    """A route with no `branches` (e.g. VPM/Ground of #1388) draws the same bytes as before #1375."""
    events, contexts = _events()
    plain = copy.deepcopy(events)
    for s in plain["stages"]:
        s.pop("branches", None)
    svg = route_map.route_board(plain, contexts).svg()
    assert "ветка" not in svg
    assert "#b2f2bb" not in svg


@pytest.mark.parametrize("mutate,needle", [
    (lambda e: e["stages"][3].update(branches=[]), "'branches'"),
    (lambda e: e["stages"][3]["branches"][0].update(ru="Build VPM"), "no Russian"),
    (lambda e: e["stages"][3]["branches"][0].update(when_ru="VPM + NPM"), "no Russian"),
    (lambda e: e["stages"][3]["branches"][0].pop("when_ru"), "'when_ru'"),
    (lambda e: e["stages"][3]["branches"][0].update(rules=[]), "'rules'"),
    (lambda e: e["stages"][3]["branches"][0].pop("evidence"), "'evidence'"),
    (lambda e: e["stages"][3]["branches"][0].update(commands=[]), "'commands'"),
    (lambda e: e["stages"][3]["branches"][1].update(id=e["stages"][3]["branches"][0]["id"]), "duplicate branch"),
    (lambda e: e["stages"][3]["branches"].append("x"), "branches[4]"),
])
def test_branch_schema_errors_name_the_key(mutate, needle):
    events, contexts = _events()
    mutate(events)
    with pytest.raises(route_map.SchemaError, match=re.escape(needle)):
        route_map.check_schema(events, contexts)


@pytest.mark.parametrize("mutate,needle", [
    (lambda e: e["stages"][3]["branches"][0]["rules"].append("D999"), "D999"),
    (lambda e: e["stages"][3]["branches"][0]["evidence"].append("jobs/KPP1/nope.md"), "jobs/KPP1/nope.md"),
    (lambda e: e["stages"][5]["branches"][1].update(commands=["agr package-npm"]), "agr package-npm"),
])
def test_unknown_branch_reference_is_reported(mutate, needle):
    events, contexts = _events()
    mutate(events)
    problems = route_map.verify_references(ROOT, events, contexts)
    assert any(needle in p and "branch" in p for p in problems), problems


def test_route_and_recipes_cite_d289_and_drop_the_unconditional_mid_poly_master():
    route = (ROOT / "routes/npm-oks.md").read_text(encoding="utf-8")
    assert "[D289]" in route
    assert "One mid-poly master;" not in route
    assert "NPM-only" in route
    for rel in ("docs/procedure/node-r4-window-glazing.md", "docs/procedure/node-r6-oks-body-facade.md"):
        assert "D289" in (ROOT / rel).read_text(encoding="utf-8"), rel
    r4 = (ROOT / "docs/procedure/node-r4-window-glazing.md").read_text(encoding="utf-8")
    assert "library/windows/window_types.json" in r4 and "windowgen_core" in r4
