"""#1383: VPM OKS and Ground route maps from YAML by the #1359 generator (drift / existence / report)."""
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
NEW = {"vpm-route": "vpm-oks-route", "ground-route": "ground-route"}
REPORT = ARCH / "report-routes-vpm-ground.md"

# v2 (#1392, D293): an NPM stage before the export; Ground relief after the flat ground (tests/test_route_maps_1392.py)
VPM_STAGES = ["sources", "parts", "gate1", "body", "openings", "roof", "decor", "uv", "ucx", "master-topology", "npm", "package",
              "readback", "validate", "sintez", "delivered"]
GROUND_STAGES = ["sources", "zero", "surfaces", "quads", "textures", "relief", "skirt", "ucx", "placement", "npm",
                 "package", "validate", "sintez"]


def _routes():
    return route_map.load_routes(ROOT)


def _contexts():
    return mini_yaml.load(ROOT / route_map.CONTEXTS)


# ---------------------------------------------------------------- the two new routes
def test_generator_knows_three_routes_and_writes_eight_files():
    # #1393 adds the MAF, Flora and package routes and their context maps (tests/test_route_maps_1393.py)
    assert set(route_map.route_events()) == {"route", "vpm-route", "ground-route", "maf-route", "flora-route",
                                             "package-route"}
    files = route_map.render_all(ROOT)[2]
    names = sorted(p.name for p in files)
    detailed = [f"{n}.{s}" for n in ("npm-oks-route", "vpm-oks-route", "ground-route", "contexts",
                                    "vpm-oks-contexts", "ground-contexts", "maf-route", "flora-route",
                                    "package-route", "maf-contexts", "flora-contexts", "package-contexts")
                for s in ("excalidraw", "svg")]
    short = [f"{n}-scheme.{s}" for n in ("npm-oks-route", "vpm-oks-route", "ground-route", "maf-route",
                                      "flora-route", "package-route") for s in ("excalidraw", "svg")]
    tables = [f"{n}-owners.md" for n in ("npm-oks-route", "vpm-oks-route", "ground-route", "maf-route",
                                      "flora-route", "package-route")]
    assert names == sorted(detailed + short + tables)


@pytest.mark.parametrize("name", sorted(NEW))
def test_new_route_files_equal_generator_output(name):
    files = route_map.render_all(ROOT)[2]
    for suffix in (".excalidraw", ".svg"):
        rel = route_map.OUTPUTS[name].with_suffix(suffix)
        assert (ROOT / rel).read_bytes() == files[rel].encode("utf-8"), f"{rel} drifted; rerun route_map.py"


def test_stage_order_follows_the_issue():
    routes = _routes()
    assert [s["id"] for s in routes["vpm-route"]["stages"]] == VPM_STAGES
    assert [s["id"] for s in routes["ground-route"]["stages"]] == GROUND_STAGES
    for name in NEW:
        assert routes[name]["issue"] == "#1392"   # v2 of the #1383 maps


@pytest.mark.parametrize("name", sorted(NEW))
def test_every_reference_of_the_new_routes_exists(name):
    routes, contexts = _routes(), _contexts()
    assert route_map.verify_references(ROOT, routes[name], contexts) == []


def test_vpm_master_topology_before_export():
    events = _routes()["vpm-route"]
    ids = [s["id"] for s in events["stages"]]
    master = [s for s in events["stages"] if "D312" in s["rules"]]
    assert len(master) == 1
    stage = master[0]
    assert stage["id"] == "master-topology"
    assert ids.index("ucx") < ids.index(stage["id"]) < ids.index("npm") < ids.index("package")
    assert stage["commands"] == [
        "uv run python tools/qa/master_topology.py <master> --out <new.json>",
        "dt qa xview",
    ]
    assert "tools/qa/master_topology.py" in stage["evidence"]
    assert "триангуляц" in stage["event_ru"].lower()
    for sid in ("readback", "validate"):
        assert "dt qa xview" in next(s for s in events["stages"] if s["id"] == sid)["commands"]


@pytest.mark.parametrize("command,expected", [
    ("uv run python tools/qa/master_topology.py <master> --out <new.json>", True),
    ("", False),
    ("uv run python tools/qa/master_topology.py", False),
    ("uv run python tools/qa/master_topology.py <master>", False),
    ("uv run python tools/qa/master_topology.py <master> --out", False),
    ("uv run python tools/qa/master_topology.py <master> --out <master>", False),
    ("uv run python tools/qa/master_topology.py <master> --out NaN", False),
    ("uv run python tools/qa/master_topology.py <master> --out inf", False),
    ("uv run python tools/qa/master_topology.py <master> --out <new.json> --out <new.json>", False),
    ("uv run python tools/qa/master_topology.py <master> --out <new.json> ; dt qa xview", False),
    ("uv run python tools/qa/unknown.py <master> --out <new.json>", False),
    ("python tools/qa/master_topology.py <master> --out <new.json>", False),
])
def test_master_topology_command_template(command, expected):
    assert route_map.command_exists(command) is expected


def test_master_topology_command_generated_mutations():
    words = "uv run python tools/qa/master_topology.py <master> --out <new.json>".split()
    mutations = []
    for i in range(len(words)):
        mutations.extend([
            words[:i] + words[i + 1:],
            words[:i] + ["unsupported"] + words[i + 1:],
            words[:i] + [words[i]] + words[i:],
        ])
    assert len(mutations) == 21
    for tokens in mutations:
        assert not route_map.command_exists(" ".join(tokens)), tokens


def test_vpm_master_topology_rendered():
    for suffix in (".excalidraw", ".svg"):
        text = (ROOT / route_map.OUTPUTS["vpm-route"].with_suffix(suffix)).read_text(encoding="utf-8")
        assert "tools/qa/master_topology.py" in text
        assert "D312" in text


def test_vpm_hotspots_cover_the_named_objects():
    """KPP1, PSU275, TEC26, ELV and 4BK evidence each back at least one VPM hot spot."""
    hot = _routes()["vpm-route"]["hotspots"]
    text = " ".join(" ".join(h["evidence"]) + " " + h["ru"] for h in hot)
    for needle in ("jobs/KPP1/", "jobs/PSU275/", "jobs/TEC26-OKS/", "jobs/elv-tc-vpm/", "vpm-course-grid-1314"):
        assert needle in text, needle
    assert all(h["evidence"] for h in hot)


def test_ground_hotspots_cover_the_named_evidence():
    hot = _routes()["ground-route"]["hotspots"]
    text = " ".join(" ".join(h["evidence"]) + " " + h["ru"] for h in hot)
    for needle in ("jobs/VATUTINO-SITE/", "placement-heights-1330", "#1315", "jobs/KPP1/", "jobs/TEC26-OKS/",
                   "node-r5-ground"):
        assert needle in text, needle


@pytest.mark.parametrize("name", sorted(NEW))
def test_every_drawn_label_is_russian(name):
    doc = json.loads((ROOT / route_map.OUTPUTS[name].with_suffix(".excalidraw")).read_text(encoding="utf-8"))
    texts = [e["text"] for e in doc["elements"] if e["type"] == "text"]
    assert len(texts) > 30
    assert [t for t in texts if not route_map.CYRILLIC.search(t)] == []


@pytest.mark.parametrize("name", sorted(NEW))
def test_stage_without_command_is_drawn_dashed(name):
    events = _routes()[name]
    bare = [s["id"] for s in events["stages"] if not s.get("commands")]
    assert bare, "each new route has stages without an agr/dt command"
    board = route_map.route_board(events, _contexts())
    dashed = [e for e in board.elements if e["type"] == "rectangle" and e["strokeStyle"] == "dashed"]
    assert len(dashed) == len(bare)
    texts = {e["text"] for e in board.elements if e["type"] == "text"}
    assert "Нет команды agr/dt" in texts


# ---------------------------------------------------------------- report <-> YAML (drift probe)
def _report_section(title):
    text = REPORT.read_text(encoding="utf-8")
    m = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert m, f"report has no section {title!r}"
    return m.group(1)


@pytest.mark.parametrize("name,title", [("vpm-route", "ВПМ ОКС"), ("ground-route", "Ground")])
def test_report_lists_every_stage_without_command_and_every_hotspot(name, title):
    events = _routes()[name]
    section = _report_section(title)
    bare = {s["id"] for s in events["stages"] if not s.get("commands")}
    listed = set(re.findall(r"^\| `([a-z0-9-]+)` \| нет команды", section, re.M))
    assert listed == bare, (sorted(listed), sorted(bare))
    hot_listed = set(re.findall(r"^- `([a-z0-9-]+)`", section, re.M))
    assert hot_listed == {h["id"] for h in events["hotspots"]}
    assert "Предлагаемые" in section
    assert route_map.CYRILLIC.search(section)


# ---------------------------------------------------------------- route-local contexts (fail closed)
def test_local_context_owner_must_exist():
    routes, contexts = _routes(), _contexts()
    events = copy.deepcopy(routes["ground-route"])
    events["local_contexts"][0]["owner"] = "src/dt_ai/nope_ground.py"
    problems = route_map.verify_references(ROOT, events, contexts)
    assert any("nope_ground.py" in p for p in problems), problems


@pytest.mark.parametrize("mutate,needle", [
    (lambda e: e["local_contexts"].append({"id": "body", "ru": "Корпус", "owner": "x.py"}), "duplicate context"),
    (lambda e: e["local_contexts"].append(dict(e["local_contexts"][0])), "duplicate context"),
    (lambda e: e["local_contexts"][0].update(ru="Ground"), "no Russian"),
    (lambda e: e["local_contexts"][0].pop("owner"), "'owner'"),
    (lambda e: e.update(local_contexts=[]), "'local_contexts'"),
    (lambda e: e["stages"][1].update(context="nowhere"), "unknown context"),
])
def test_local_context_schema_errors_name_the_key(mutate, needle):
    events = copy.deepcopy(_routes()["ground-route"])
    mutate(events)
    with pytest.raises(route_map.SchemaError, match=re.escape(needle)):
        route_map.check_schema(events, _contexts())


def test_npm_route_cannot_use_a_ground_local_context():
    """A route-local context is visible only inside its own YAML."""
    npm = copy.deepcopy(_routes()["route"])
    npm["stages"][0]["context"] = _routes()["ground-route"]["local_contexts"][0]["id"]
    with pytest.raises(route_map.SchemaError, match="unknown context"):
        route_map.check_schema(npm, _contexts())


# ---------------------------------------------------------------- CLI on a copy
def _tmp_arch(tmp_path):
    shutil.copytree(ARCH, tmp_path / "docs/architecture")
    shutil.copy2(ROOT / "docs/decisions.md", tmp_path / "docs/decisions.md")
    return tmp_path


@pytest.mark.parametrize("name", sorted(NEW))
def test_check_detects_missing_or_edited_new_output(tmp_path, capsys, name):
    root = _tmp_arch(tmp_path)
    rel = route_map.OUTPUTS[name]
    (root / rel.with_suffix(".svg")).unlink()
    ex = root / rel.with_suffix(".excalidraw")
    ex.write_bytes(ex.read_bytes().replace("Нет команды".encode(), "Нет кoманды".encode(), 1))
    assert route_map.main(["--root", str(root), "--check"]) == 1
    out = capsys.readouterr().out
    assert f"drift: {rel.with_suffix('.svg').as_posix()}" in out
    assert f"drift: {rel.with_suffix('.excalidraw').as_posix()}" in out


def test_check_reports_unknown_reference_in_a_new_route(tmp_path, capsys):
    root = _tmp_arch(tmp_path)
    path = root / route_map.route_events()["vpm-route"]
    text = path.read_text(encoding="utf-8").replace('"agr package-vpm"', '"agr brick-seams"', 1)
    assert '"agr brick-seams"' in text
    path.write_text(text, encoding="utf-8")
    route_map.main(["--root", str(root)])          # regenerate so only the reference problem remains
    capsys.readouterr()
    assert route_map.main(["--root", str(root), "--check"]) == 1
    assert "command 'agr brick-seams' is not an existing agr/dt command" in capsys.readouterr().out


@pytest.mark.parametrize("name", sorted(NEW))
def test_malformed_new_yaml_exits_2_and_writes_nothing(tmp_path, name):
    root = _tmp_arch(tmp_path)
    (root / route_map.route_events()[name]).write_text("stages: [a, b]\n", encoding="utf-8")
    before = {p.name: p.read_bytes() for p in (root / "docs/architecture").iterdir()}
    assert route_map.main(["--root", str(root)]) == 2
    after = {p.name: p.read_bytes() for p in (root / "docs/architecture").iterdir()}
    assert before == after


def test_missing_new_yaml_is_an_error_not_a_pass(tmp_path):
    root = _tmp_arch(tmp_path)
    (root / route_map.route_events()["ground-route"]).unlink()
    assert route_map.main(["--root", str(root), "--check"]) == 2


def test_new_events_yaml_as_output_is_refused(tmp_path, monkeypatch):
    root = _tmp_arch(tmp_path)
    alias = root / "docs/architecture/ground-route.svg"
    alias.write_bytes((root / route_map.route_events()["ground-route"]).read_bytes())
    before = alias.read_bytes()
    monkeypatch.setattr(route_map, "GROUND_EVENTS", Path("docs/architecture/ground-route.svg"))
    assert route_map.main(["--root", str(root)]) == 2
    assert alias.read_bytes() == before
    assert not list((root / "docs/architecture").glob("*.partial"))


def test_write_mode_is_idempotent(tmp_path):
    root = _tmp_arch(tmp_path)
    before = {p.name: p.read_bytes() for p in (root / "docs/architecture").iterdir()}
    assert route_map.main(["--root", str(root)]) == 0
    assert before == {p.name: p.read_bytes() for p in (root / "docs/architecture").iterdir()}


def test_check_fresh_process_cli():
    proc = subprocess.run([sys.executable, str(ROOT / "tools/architecture/route_map.py"), "--check"],
                          cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_new_yamls_match_pyyaml():
    yaml = pytest.importorskip("yaml")
    for rel in route_map.route_events().values():
        assert mini_yaml.load(ROOT / rel) == yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))
