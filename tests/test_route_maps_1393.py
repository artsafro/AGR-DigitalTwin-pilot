"""#1393: MAF, Flora and package/delivery route maps + their context maps, generated from YAML by
tools/architecture/route_map.py (same method as #1383 / #1392). Every box cites a source; repo gaps are RED boxes."""
import copy
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
import mini_yaml  # noqa: E402
import route_map  # noqa: E402

ARCH = ROOT / "docs/architecture"
REPORT = ARCH / "report-routes-maf-flora-package.md"
ROUTES = {"maf-route": "maf-contexts", "flora-route": "flora-contexts", "package-route": "package-contexts"}
STEMS = {"maf-route": "maf-route", "flora-route": "flora-route", "package-route": "package-route",
         "maf-contexts": "maf-contexts", "flora-contexts": "flora-contexts", "package-contexts": "package-contexts"}
TITLES = {"maf-route": "МАФ", "flora-route": "Флора", "package-route": "Пакет и сдача"}
DCC_ACTOR = "Агент: Blender / Max / AGR Tools"
MAF_STAGES = ["sources", "library", "pick", "dims", "ids", "vpm", "placement", "npm", "ucx", "checks", "showcase",
              "package"]
FLORA_STAGES = ["sources", "beds", "species", "size", "maps", "star", "lod", "placement", "npm", "atlas", "checks",
                "gate", "package"]
PACKAGE_STAGES = ["export", "meta", "readback", "geojson", "package", "validate", "sintez", "report", "accept",
                  "upload", "customer"]
QUESTIONS = {"maf-route": "ucx-fences", "flora-route": "stand-in-replace", "package-route": "customer-channel"}
# #1412: red blocks closed by Artem's 2026-11-15 decisions -> block id: (stage that cites it, D-row)
RESOLVED = {"maf-route": {"ucx-fences": ("ucx", "D298")},
            "flora-route": {"stand-in-replace": ("maps", "D299"), "lod-rule": ("lod", "D301")},
            "package-route": {"customer-channel": ("customer", "D300")}}


def _routes():
    return route_map.load_routes(ROOT)


def _maps():
    return route_map.load_context_maps(ROOT)


def _contexts():
    return mini_yaml.load(ROOT / route_map.CONTEXTS)


def _stage(events, sid):
    return next(s for s in events["stages"] if s["id"] == sid)


def _texts(name):
    doc = json.loads((ROOT / route_map.OUTPUTS[name].with_suffix(".excalidraw")).read_text(encoding="utf-8"))
    return doc, [e["text"] for e in doc["elements"] if e["type"] == "text"]


# ---------------------------------------------------------------- acceptance 1: 3 routes + 3 maps from YAML
def test_generator_writes_three_routes_and_three_context_maps():
    files = route_map.render_all(ROOT)[2]
    assert len(files) == 24
    for name, stem in STEMS.items():
        assert route_map.OUTPUTS[name] == Path("docs/architecture") / stem
        for suffix in (".excalidraw", ".svg"):
            rel = route_map.OUTPUTS[name].with_suffix(suffix)
            assert (ROOT / rel).read_bytes() == files[rel].encode("utf-8"), f"{rel} drifted"
    for route, cmap in ROUTES.items():
        assert route_map.ROUTE_MAP_OF[route] == cmap
        assert route_map.route_events()[route].name == f"{route}.events.yaml"
        assert route_map.context_maps()[cmap].name == f"{cmap}.yaml"


@pytest.mark.parametrize("name", sorted(STEMS))
def test_every_drawn_label_is_russian(name):
    doc, texts = _texts(name)
    assert len(texts) > 15
    assert [t for t in texts if not route_map.CYRILLIC.search(t)] == []


def test_check_cli_passes_and_fresh_process_agrees():
    assert route_map.main(["--check"]) == 0
    out = subprocess.run([sys.executable, str(ROOT / "tools/architecture/route_map.py"), "--check"],
                         capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stdout + out.stderr


# ---------------------------------------------------------------- acceptance 2: every box cites its source
@pytest.mark.parametrize("name", sorted(ROUTES))
def test_every_stage_branch_and_red_box_cites_an_existing_source(name):
    events = _routes()[name]
    assert route_map.verify_references(ROOT, events, _contexts()) == []
    for s in events["stages"]:
        assert s["rules"] and s["evidence"], s["id"]
        for b in s.get("branches", []):
            assert b["rules"] and b["evidence"], (s["id"], b["id"])
    for h in events["hotspots"]:
        assert h["evidence"], h["id"]


@pytest.mark.parametrize("name", sorted(ROUTES))
def test_brute_force_every_cited_source_is_checked(name):
    """Probe: replace each cited D-row / path one at a time with a missing one -> each is reported (N/N)."""
    events = _routes()[name]
    slots = []
    for i, s in enumerate(events["stages"]):
        slots += [("stages", i, None, k, j) for k in ("rules", "evidence") for j in range(len(s[k]))]
        for b_i, b in enumerate(s.get("branches", [])):
            slots += [("stages", i, b_i, k, j) for k in ("rules", "evidence") for j in range(len(b[k]))]
    for i, h in enumerate(events["hotspots"]):
        slots += [("hotspots", i, None, k, j) for k in ("rules", "evidence") for j in range(len(h.get(k, [])))]
    caught = 0
    for part, i, b_i, key, j in slots:
        mutated = copy.deepcopy(events)
        node = mutated[part][i] if b_i is None else mutated[part][i]["branches"][b_i]
        node[key][j] = "D999" if key == "rules" else "docs/no-such-file-1393.md"
        if route_map.verify_references(ROOT, mutated, _contexts()):
            caught += 1
    assert caught == len(slots) >= 50


@pytest.mark.parametrize("name", sorted(ROUTES))
def test_stage_without_a_source_is_a_schema_error(name):
    for key in ("rules", "evidence"):
        events = copy.deepcopy(_routes()[name])
        events["stages"][0][key] = []
        with pytest.raises(route_map.SchemaError, match=key):
            route_map.check_schema(events, _contexts())


@pytest.mark.parametrize("name", sorted(ROUTES))
def test_red_boxes_are_drawn_one_per_hotspot(name):
    events = _routes()[name]
    board = route_map.route_board(events, _contexts())
    pink = [e for e in board.elements if e["type"] == "rectangle" and e["backgroundColor"] == route_map.COLORS["hotspot"]]
    assert len(pink) == len(events["hotspots"]) >= 5


@pytest.mark.parametrize("name", sorted(ROUTES))
def test_undefined_steps_are_red_questions_not_inventions(name):
    # #1412: Artem answered every open question; none may stay drawn as a question or as a red box
    hot = {h["id"]: h for h in _routes()[name]["hotspots"]}
    assert QUESTIONS[name] not in hot
    assert {h for h, v in hot.items() if v["ru"].startswith("ВОПРОС")} == set()


@pytest.mark.parametrize("name", sorted(ROUTES))
def test_resolved_red_blocks_cite_their_d_row_1412(name):
    rows = {m for m in re.findall(r"^\| (D\d+) \|", (ROOT / "docs/decisions.md").read_text(encoding="utf-8"), re.M)}
    hot = {h["id"] for h in _routes()[name]["hotspots"]}
    section = _section(TITLES[name])
    for block, (stage, d) in RESOLVED[name].items():
        assert block not in hot, block
        assert d in rows and d in _stage(_routes()[name], stage)["rules"], (block, d)
        assert re.search(rf"^\| `{block}` \| снята \| .*\[{d}\]", section, re.M), block


def test_task_to_model_has_delivery_to_artem_step_1412():
    text = (ROOT / "docs/procedure/TASK_TO_MODEL.md").read_text(encoding="utf-8")
    step = re.search(r"\*\*Delivery to Artem \[D300\]\.\*\*(.*?)\n\n", text, re.S)
    assert step, "TASK_TO_MODEL lacks the Delivery to Artem [D300] step"
    body = " ".join(step.group(1).split())
    assert "archive" in body and "3ds Max scene with quads" in body and "Artem does the acceptance" in body


# ---------------------------------------------------------------- route content (issue scope)
def test_stage_orders():
    routes = _routes()
    assert [s["id"] for s in routes["maf-route"]["stages"]] == MAF_STAGES
    assert [s["id"] for s in routes["flora-route"]["stages"]] == FLORA_STAGES
    assert [s["id"] for s in routes["package-route"]["stages"]] == PACKAGE_STAGES


@pytest.mark.parametrize("name", sorted(ROUTES))
def test_tool_agnostic_actor_d293(name):
    actors = {a["id"]: a["ru"] for a in _routes()[name]["actors"]}
    assert actors["agent-dcc"] == DCC_ACTOR
    assert [ru for ru in actors.values() if ru.endswith("(AGR Tools)") or ru == "3ds Max"] == []
    assert any(s["actor"] == "agent-dcc" for s in _routes()[name]["stages"])


@pytest.mark.parametrize("name", ["maf-route", "flora-route"])
def test_npm_stage_has_convert_and_parallel_and_comes_before_package(name):
    ids = [s["id"] for s in _routes()[name]["stages"]]
    assert ids.index("placement") < ids.index("npm") < ids.index("package")
    npm = _stage(_routes()[name], "npm")
    assert {"convert", "parallel"} <= {b["id"] for b in npm["branches"]}
    assert "D293" in npm["rules"]
    assert {"agr package-npm", "agr package-vpm"} <= set(_stage(_routes()[name], "package")["commands"])


def test_maf_library_lookup_ucx_and_no_substitution():
    events = _routes()["maf-route"]
    assert "G:/Мой диск/AGR-assets/maf" in _stage(events, "library")["event_ru"]
    assert "манифест" in _stage(events, "library")["event_ru"]
    assert "D164" in _stage(events, "pick")["rules"]
    assert "UCX" in _stage(events, "ucx")["event_ru"]
    assert "D094" in _stage(events, "dims")["rules"] and "D095" in _stage(events, "placement")["rules"]


def test_flora_interim_maps_and_lod_on_copies():
    events = _routes()["flora-route"]
    maps = _stage(events, "maps")
    assert {"approved", "stand-in", "new"} == {b["id"] for b in maps["branches"]}
    assert "D245" in maps["rules"]
    assert "копи" in _stage(events, "lod")["event_ru"]
    assert "library/flora/README.md" in _stage(events, "lod")["evidence"]
    assert "G:/Мой диск/AGR-assets/flora" in _stage(events, "species")["event_ru"]


def test_package_route_covers_export_meta_packagers_checker_and_delivery():
    events = _routes()["package-route"]
    assert "schemas/ExportMeta.schema.json" in _stage(events, "meta")["evidence"]
    assert {b["id"] for b in _stage(events, "package")["branches"]} == {"npm", "vpm"}
    assert _stage(events, "sintez")["actor"] == "checker"
    assert [_stage(events, s)["actor"] for s in ("accept", "upload", "customer")] == ["artem"] * 3
    assert "D163" in _stage(events, "customer")["rules"]


# ---------------------------------------------------------------- context maps
@pytest.mark.parametrize("route,cmap", sorted(ROUTES.items()))
def test_context_map_covers_every_stage_context_with_the_same_owner(route, cmap):
    assert route_map.route_coverage(_routes()[route], _contexts(), _maps()[cmap]) == []
    assert route_map.verify_references(ROOT, {"stages": [], "hotspots": []}, _maps()[cmap]) == []


@pytest.mark.parametrize("route,cmap", sorted(ROUTES.items()))
def test_coverage_fails_closed_for_every_stage_context(route, cmap):
    """Probe: drop each stage context from the map / change its owner -> named problem (N/N)."""
    events, cm = _routes()[route], _maps()[cmap]
    ids = list(dict.fromkeys(s["context"] for s in events["stages"]))
    caught = 0
    for cid in ids:
        m = copy.deepcopy(cm)
        if m["shared_kernel"]["id"] == cid:
            m["shared_kernel"]["owner"] = "src/dt_ai/core/build.py"
            needle = "owner"
        else:
            m["contexts"] = [c for c in m["contexts"] if c["id"] != cid]
            m["relations"] = [r for r in m["relations"] if cid not in (r["from"], r["to"])]
            needle = "missing"
        caught += any(cid in p and needle in p for p in route_map.route_coverage(events, _contexts(), m))
    assert caught == len(ids) >= 5


@pytest.mark.parametrize("cmap", sorted(set(ROUTES.values())))
def test_context_map_arrows_and_labels(cmap):
    doc, texts = _texts(cmap)
    arrows = [e for e in doc["elements"] if e["type"] == "arrow"]
    assert len(arrows) == len(_maps()[cmap]["relations"]) > 5


# ---------------------------------------------------------------- report <-> YAML
def _section(title):
    text = REPORT.read_text(encoding="utf-8")
    m = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert m, f"report has no section {title!r}"
    return m.group(1)


@pytest.mark.parametrize("name", sorted(ROUTES))
def test_report_lists_every_bare_stage_and_every_red_box(name):
    events, section = _routes()[name], _section(TITLES[name])
    bare = {s["id"] for s in events["stages"] if not s.get("commands")}
    assert set(re.findall(r"^\| `([a-z0-9-]+)` \| нет команды", section, re.M)) == bare
    hot = {h["id"] for h in events["hotspots"]}
    assert set(re.findall(r"^- `([a-z0-9-]+)`", section, re.M)) == hot
    status = dict(re.findall(r"^\| `([a-z0-9-]+)` \| (открыта|снята|обновлена) \|", section, re.M))
    assert set(status) == hot | set(RESOLVED[name])
    assert {k for k, v in status.items() if v == "снята"} == set(RESOLVED[name])
    assert "Предлагаемые" in section


# ---------------------------------------------------------------- CLI fail-closed on a copy
@pytest.mark.parametrize("name", sorted(STEMS))
def test_malformed_new_yaml_exits_2_and_writes_nothing(tmp_path, name):
    shutil.copytree(ARCH, tmp_path / "docs/architecture")
    rel = route_map.route_events().get(name) or route_map.context_maps()[name]
    (tmp_path / rel).write_text("stages: [a, b]\n", encoding="utf-8")
    before = {p.name: p.read_bytes() for p in (tmp_path / "docs/architecture").iterdir()}
    assert route_map.main(["--root", str(tmp_path)]) == 2
    assert before == {p.name: p.read_bytes() for p in (tmp_path / "docs/architecture").iterdir()}


@pytest.mark.parametrize("name", sorted(STEMS))
def test_missing_new_yaml_is_an_error_not_a_pass(tmp_path, name):
    shutil.copytree(ARCH, tmp_path / "docs/architecture")
    rel = route_map.route_events().get(name) or route_map.context_maps()[name]
    (tmp_path / rel).unlink()
    assert route_map.main(["--root", str(tmp_path), "--check"]) == 2


@pytest.mark.parametrize("const,alias", [("MAF_EVENTS", "maf-route.svg"), ("PACKAGE_CONTEXTS", "package-contexts.svg")])
def test_new_yaml_as_output_is_refused(tmp_path, monkeypatch, const, alias):
    shutil.copytree(ARCH, tmp_path / "docs/architecture")
    target = tmp_path / "docs/architecture" / alias
    target.write_bytes((tmp_path / getattr(route_map, const)).read_bytes())
    before = target.read_bytes()
    monkeypatch.setattr(route_map, const, Path("docs/architecture") / alias)
    assert route_map.main(["--root", str(tmp_path)]) == 2
    assert target.read_bytes() == before
    assert not list((tmp_path / "docs/architecture").glob("*.partial"))


@pytest.mark.parametrize("name", sorted(STEMS))
def test_check_detects_drift_of_a_new_output(tmp_path, capsys, name):
    shutil.copytree(ARCH, tmp_path / "docs/architecture")
    shutil.copy2(ROOT / "docs/decisions.md", tmp_path / "docs/decisions.md")
    svg = tmp_path / route_map.OUTPUTS[name].with_suffix(".svg")
    svg.write_bytes(svg.read_bytes() + b" ")
    assert route_map.main(["--root", str(tmp_path), "--check"]) == 1
    assert f"drift: docs/architecture/{STEMS[name]}.svg" in capsys.readouterr().out


def test_write_mode_is_idempotent_for_the_new_files(tmp_path):
    shutil.copytree(ARCH, tmp_path / "docs/architecture")
    before = {p.name: p.read_bytes() for p in (tmp_path / "docs/architecture").iterdir()}
    assert route_map.main(["--root", str(tmp_path)]) == 0
    assert before == {p.name: p.read_bytes() for p in (tmp_path / "docs/architecture").iterdir()}


def test_new_yamls_match_pyyaml():
    yaml = pytest.importorskip("yaml")
    for name in STEMS:
        rel = route_map.route_events().get(name) or route_map.context_maps()[name]
        assert mini_yaml.load(ROOT / rel) == yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))
