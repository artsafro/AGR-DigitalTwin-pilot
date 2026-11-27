"""#1930: context maps warn (review hint, not a failure) on context nodes without relations, and the Ground map
names the real export -> package / export -> placement handoffs and the UDIM core it actually uses."""
import copy
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
import route_map  # noqa: E402

HINT = "has no relation (review hint, not proof of completeness)"


def _ctx(cid, **extra):
    return {"id": cid, "ru": "Контекст", "owner": f"{cid}.py", "owner_ru": "владелец",
            "functions": [{"name": "f", "contract": "вход -> выход"}], **extra}


def _synthetic(relations, **extra_by_id):
    """Synthetic map: kernel k serves stage s; contexts a, b, c; every context is a stage context."""
    cmap = {"title_ru": "Синтетическая карта", "rules": [{"id": "r", "ru": "правило"}],
            "shared_kernel": _ctx("k", serves_stage="s", **extra_by_id.get("k", {})),
            "contexts": [_ctx(c, **extra_by_id.get(c, {})) for c in ("a", "b", "c")],
            "relations": [{"from": f, "to": t, "ru": "передача"} for f, t in relations]}
    events = {"stages": [{"id": "s", "context": c} for c in ("a", "b", "c")]}
    contexts = {"shared_kernel": _ctx("npm-kernel"), "contexts": [_ctx(c) for c in ("a", "b", "c")]}
    return events, contexts, cmap


def _hints(problems):
    return [p for p in problems if HINT in p]


def _check(events, contexts, cmap):
    """What `route_map.py --check` evaluates per map: stage/owner coverage, then the #1930 relation hints."""
    return route_map.route_coverage(events, contexts, cmap) + route_map.relation_hints(cmap)


def test_route_coverage_contract_is_unchanged():
    events, contexts, cmap = _synthetic([])
    assert route_map.route_coverage(events, contexts, cmap) == []   # hints live only in relation_hints


# ---------------------------------------------------------------- checker controls
def test_linked_control_has_no_relation_warning():
    events, contexts, cmap = _synthetic([("k", "a"), ("a", "b"), ("c", "b")])
    assert _check(events, contexts, cmap) == []


def test_accidental_isolation_warns_once_per_node_and_stays_a_warning():
    events, contexts, cmap = _synthetic([("k", "a"), ("a", "b")])
    for _ in range(2):   # repeat: same input, same single warning
        problems = _check(events, contexts, cmap)
        assert problems == [f"WARNING: context map: context 'c' {HINT}"]
    # no relations at all: every node (kernel included) is a hint, none an error
    events, contexts, cmap = _synthetic([])
    problems = _check(events, contexts, cmap)
    assert sorted(problems) == sorted(f"WARNING: context map: context {c!r} {HINT}" for c in "kabc")
    cmap.pop("relations")
    assert len(_hints(_check(events, contexts, cmap))) == 4


def test_documented_isolation_is_silent():
    events, contexts, cmap = _synthetic([("k", "a"), ("a", "b")], c={"isolated_ru": "ручной шаг без передачи"})
    assert _check(events, contexts, cmap) == []


def test_self_loop_counts_as_incident():
    events, contexts, cmap = _synthetic([("k", "a"), ("a", "b"), ("c", "c")])
    assert _check(events, contexts, cmap) == []


def test_generated_probe_hint_iff_unlinked_and_unexplained():
    """Seeded brute force: 400 random relation sets x random isolation notes over k, a, b, c."""
    import random
    rng = random.Random(1930)
    nodes = "kabc"
    for _ in range(400):
        rels = [(rng.choice(nodes), rng.choice(nodes)) for _ in range(rng.randint(0, 4))]
        incident = {e for r in rels for e in r}
        notes = {n: {"isolated_ru": "намеренно"} for n in nodes if n not in incident and rng.random() < 0.5}
        events, contexts, cmap = _synthetic(rels, **notes)
        expected = sorted(f"WARNING: context map: context {n!r} {HINT}"
                          for n in nodes if n not in incident and n not in notes)
        assert sorted(_check(events, contexts, cmap)) == expected
        linked = sorted(incident)
        if linked:   # a note on any linked node turns the same input into a schema error
            stale = {**notes, linked[0]: {"isolated_ru": "устарело"}}
            with pytest.raises(route_map.SchemaError, match="stale"):
                _check(*_synthetic(rels, **stale))


@pytest.mark.parametrize("value", ["", "   ", "no cyrillic", None, [], float("nan"), float("inf"), 1])
def test_bad_isolation_explanation_is_a_schema_error(value):
    events, contexts, cmap = _synthetic([("k", "a"), ("a", "b")], c={"isolated_ru": value})
    with pytest.raises(route_map.SchemaError, match="isolated_ru"):
        _check(events, contexts, cmap)


def test_stale_isolation_explanation_on_a_linked_node_is_a_schema_error():
    events, contexts, cmap = _synthetic([("k", "a"), ("a", "b"), ("b", "c")], b={"isolated_ru": "устарело"})
    with pytest.raises(route_map.SchemaError, match="context b: isolated_ru .*relation"):
        _check(events, contexts, cmap)


def test_schema_and_owner_errors_are_preserved_next_to_the_hint():
    events, contexts, cmap = _synthetic([("k", "a"), ("a", "b")])
    cmap["contexts"][1]["owner"] = "other.py"           # owner mismatch stays a problem (not a WARNING)
    problems = _check(events, contexts, cmap)
    assert "context map: 'b' owner other.py differs from the route's b.py" in problems
    assert _hints(problems) == [f"WARNING: context map: context 'c' {HINT}"]
    events["stages"].append({"id": "t", "context": "missing"})   # stage coverage stays a problem
    assert "context map: stage context 'missing' is missing" in _check(events, contexts, cmap)
    events, contexts, cmap = _synthetic([("k", "ghost")])   # unknown relation end stays a schema error
    with pytest.raises(route_map.SchemaError, match="unknown context 'ghost'"):
        _check(events, contexts, cmap)


def test_isolation_explanation_is_not_inherited_through_ref():
    maps = route_map.load_context_maps(ROOT)
    target = next(c for c in maps["package-contexts"]["contexts"] if c["id"] == "sintez")
    target["isolated_ru"] = "объяснение другой карты"
    assert "isolated_ru" not in route_map.resolve_context({"ref": "package-contexts.yaml#sintez"}, maps)
    local = route_map.resolve_context({"ref": "package-contexts.yaml#sintez", "isolated_ru": "своё"}, maps)
    assert local["isolated_ru"] == "своё"


def test_check_cli_exits_zero_on_hint_only(capsys, monkeypatch):
    routes = route_map.load_routes(ROOT)
    maps = route_map.load_context_maps(ROOT)
    victim = next(c for c in maps["ground-contexts"]["contexts"] if c["id"] == "heights")
    maps["ground-contexts"]["relations"] = [r for r in maps["ground-contexts"]["relations"]
                                            if "heights" not in (r["from"], r["to"])]
    victim.pop("isolated_ru", None)
    monkeypatch.setattr(route_map, "load_context_maps", lambda root: copy.deepcopy(maps))
    monkeypatch.setattr(route_map, "render_all", lambda root: (routes, maps["contexts"], {}))
    assert route_map.main(["--check"]) == 0
    out = capsys.readouterr().out
    assert f"WARNING: ground-contexts.yaml: context map: context 'heights' {HINT}" in out


# ---------------------------------------------------------------- Ground map: real handoffs
def _ground():
    return route_map.load_context_maps(ROOT)["ground-contexts"]


def _rel(cmap, a, z):
    rows = [r["ru"] for r in cmap["relations"] if (r["from"], r["to"]) == (a, z)]
    assert len(rows) == 1, (a, z, rows)
    return rows[0]


def test_ground_map_has_no_unexplained_isolated_node():
    events = route_map.load_routes(ROOT)["ground-route"]
    cmap = _ground()
    contexts = route_map.load_context_maps(ROOT)["contexts"]
    assert _hints(_check(events, contexts, cmap)) == []
    incident = {e for r in cmap["relations"] for e in (r["from"], r["to"])}
    documented = {c["id"] for c in cmap["contexts"] if "isolated_ru" in c}
    assert documented == {"dcc", "uv-atlas", "npm", "ucx"}
    assert not documented & incident


def test_ground_export_to_package_is_not_a_complete_package_input():
    label = _rel(_ground(), "ground-export", "package")
    for need in ("export_meta", "T_<A>_*.png", "--object", "превью", "--no-geojson", "не сводный FBX участка"):
        assert need in label, need


def test_ground_export_to_placement_names_readback_and_its_limits():
    cmap = _ground()
    label = _rel(cmap, "ground-export", "placement")
    for need in ("JSON-мастер", "readback", "placement_offset", "не хешируется", "OBJ"):
        assert need in label, need
    # the OBJ path of ground_site never reaches the JSON master: no ground -> ground-export / placement handoff
    assert not [r for r in cmap["relations"] if r["from"] == "ground" and r["to"] in ("ground-export", "placement")]


def test_udim_core_attribution_is_only_udim_of_cell_and_face_tol():
    label = _rel(_ground(), "udim", "ground-export")
    assert "udim_of_cell" in label and "FACE_TOL" in label and "локальн" in label and "не face_tile" in label
    assert "udim_tile" not in label.replace("udim_of_cell", "")
    assert re.findall(r"\bface_tile\b", label) == ["face_tile"]   # only in the negation


def test_removed_1915_handoffs_stay_removed():
    pairs = {(r["from"], r["to"]) for r in _ground()["relations"]}
    assert not pairs & {("dcc", "heights"), ("placement", "npm")}


# ---------------------------------------------------------------- code evidence behind the labels
def _src(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_code_evidence_readback_uses_only_udim_of_cell_and_face_tol():
    used = set(re.findall(r"_udimtile\.(\w+)", _src("tools/blender/ground_json_to_fbx.py")))
    assert used == {"FACE_TOL", "UdimCrossTileError", "udim_of_cell"}   # error type only; no face_tile/udim_tile


def test_code_evidence_package_and_placement_inputs():
    pkg = _src("tools/derive/package_vpm.py")
    assert 'meta["thumbnail"]' in pkg and "--no-geojson" in pkg and "T_{A}_" in pkg
    build = _src("tools/blender/ground_json_to_fbx.py")
    call = build[build.index("record_export(out"):]
    assert "thumbnail" not in call[:call.index(")\n")]   # helper records thumbnail 'unknown'
    site = _src("src/dt_ai/placement/site.py")
    assert '.get("placement_offset")' in site
    assert "readback_sha256" not in site and '"readback":' not in site   # readback file is neither hashed nor kept
