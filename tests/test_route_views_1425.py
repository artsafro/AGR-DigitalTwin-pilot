"""new-case: #1425 generated short-route and owner/migration view contracts."""
import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/architecture"))
import route_map  # noqa: E402


def test_two_views_for_every_route():
    routes, _, files = route_map.render_all(ROOT)
    for name in routes:
        stem = route_map.OUTPUTS[name]
        scheme = stem.with_name(stem.name + "-scheme")
        table = stem.with_name(stem.name + "-owners.md")
        assert scheme.with_suffix(".svg") in files
        doc = json.loads(files[scheme.with_suffix(".excalidraw")])
        texts = "\n".join(e.get("text", "") for e in doc["elements"])
        assert "Редакция" in texts and "Ревизия исходников" in texts
        assert "Владелец экспорта" in texts
        assert "export_core.py" in texts
        assert not re.search(r"\.py:[0-9]|\.py::", texts)
        assert "Живых обходов" in texts
        assert table in files
        assert "Критерий завершения миграции" in files[table]
        assert "Причина различий" in files[table]
        assert "Живые обходы" in files[table]


@pytest.mark.parametrize("name", list(route_map.route_events()))
def test_all_arrows_bind_steps_or_artifacts_never_pink_lists(name):
    events = route_map.load_routes(ROOT)[name]
    maps = route_map.load_context_maps(ROOT)
    cmap = maps[route_map.ROUTE_MAP_OF.get(name, "contexts")]
    for board in (route_map.short_route_board(events, cmap, maps), route_map.contexts_board(None, cmap)):
        by_id = {e["id"]: e for e in board.elements}
        for arrow in (e for e in board.elements if e["type"] == "arrow"):
            for key in ("startBinding", "endBinding"):
                box = by_id[arrow[key]["elementId"]]
                assert box["type"] == "rectangle"
                assert box["backgroundColor"] != route_map.COLORS["hotspot"]
        texts = "\n".join(e.get("text", "") for e in board.elements)
        assert not re.search(r"\.py:[0-9]|\.py::", texts)


@pytest.mark.parametrize("kind", ["empty", "partial", "unknown", "repeat", "reorder", "nan", "inf", "eight", "extra"])
def test_malformed_short_view_fails_closed(kind):
    events = route_map.load_routes(ROOT)["route"]
    maps = route_map.load_context_maps(ROOT)
    steps = events["scheme"]["steps"]
    if kind == "empty":
        events["scheme"] = {}
    elif kind == "partial":
        steps[0].pop("artifact_ru")
    elif kind in ("unknown", "repeat", "reorder"):
        steps[0]["stages"] = {"unknown": "unmapped", "repeat": "sources,sources", "reorder": "parts,sources,gate1"}[kind]
    elif kind in ("nan", "inf"):
        steps[0]["ru"] = float(kind)
    elif kind == "extra":
        steps[0]["unmapped"] = "Неизвестное поле"
    else:
        steps.extend(copy.deepcopy(steps[:3]))
    with pytest.raises(route_map.SchemaError):
        route_map.short_route_board(events, maps["contexts"], maps)


def test_every_stage_drop_is_rejected_generated_probe():
    events = route_map.load_routes(ROOT)
    maps = route_map.load_context_maps(ROOT)
    caught = total = 0
    for name, ev in events.items():
        for i, step in enumerate(ev["scheme"]["steps"]):
            for stage in step["stages"].split(","):
                bad = copy.deepcopy(ev)
                bad["scheme"]["steps"][i]["stages"] = ",".join(s for s in step["stages"].split(",") if s != stage)
                total += 1
                with pytest.raises(route_map.SchemaError):
                    route_map.short_route_board(bad, maps[route_map.ROUTE_MAP_OF.get(name, "contexts")], maps)
                caught += 1
    assert caught == total == 74


def test_status_counts_use_existing_registry_and_deduplicate_repeated_map_rows():
    maps = route_map.load_context_maps(ROOT)
    ev = route_map.load_routes(ROOT)["package-route"]
    # Synthetic rows: one live bypass, one history, wrapper and own-duty; repeat across maps counts once.
    base = maps["package-contexts"]["contexts"][1]
    base["duplicates"] = [dict(at=f"jobs/synthetic/{s}.py:1", issue="#1425", match="synthetic", ru="Причина",
                               status=s, **({"step": "#1429"} if s == "live-bypass" else {}),
                               **({"why": "Отдельная обязанность"} if s == "own-duty" else {}))
                          for s in ("live-bypass", "historical", "wrapper", "own-duty")]
    maps["repeat"] = copy.deepcopy(maps["package-contexts"])
    text = route_map.owners_markdown(ev, maps["package-contexts"], maps)
    assert "[1 — записи]" in text
    assert text.count("[`jobs/synthetic/live-bypass.py:1`]") == 1
    assert "issues/1429" in text
    base["duplicates"][0]["status"] = "unsupported"
    with pytest.raises(route_map.SchemaError, match="unsupported"):
        route_map.owners_markdown(ev, maps["package-contexts"], maps)


def _segment_hits_rect(p, q, rect):
    """Independent closed slab intersection; touching an unrelated list counts too."""
    lo, hi = 0.0, 1.0
    for axis, size in (("x", "width"), ("y", "height")):
        i = 0 if axis == "x" else 1
        delta = q[i] - p[i]
        left, right = rect[axis], rect[axis] + rect[size]
        if delta == 0:
            if not left <= p[i] <= right:
                return False
        else:
            a, b = sorted(((left - p[i]) / delta, (right - p[i]) / delta))
            lo, hi = max(lo, a), min(hi, b)
            if lo > hi:
                return False
    return True


@pytest.mark.parametrize("name", list(route_map.OUTPUTS))
def test_arrow_polylines_never_intersect_pink_lists(name):
    _, _, files = route_map.render_all(ROOT)
    # Include detailed routes, context maps and the new short schemes.
    stem = route_map.OUTPUTS[name]
    paths = [stem.with_suffix(".excalidraw")]
    scheme = stem.with_name(stem.name + "-scheme").with_suffix(".excalidraw")
    if scheme in files:
        paths.append(scheme)
    for path in paths:
        elements = json.loads(files[path])["elements"]
        pink = [e for e in elements if e["type"] == "rectangle"
                and e["backgroundColor"] == route_map.COLORS["hotspot"]]
        hits = []
        for arrow in (e for e in elements if e["type"] == "arrow"):
            ends = {arrow[key]["elementId"] for key in ("startBinding", "endBinding")}
            points = [(arrow["x"] + x, arrow["y"] + y) for x, y in arrow["points"]]
            for rect in pink:
                if rect["id"] not in ends and any(_segment_hits_rect(p, q, rect)
                                                 for p, q in zip(points, points[1:])):
                    hits.append((arrow["id"], rect["id"]))
        assert not hits, f"{path}: pink crossings {hits}"
        # Verify the actual SVG uses the full same route, not just its first segment.
        import xml.etree.ElementTree as ET
        svg = ET.fromstring(files[path.with_suffix(".svg")])
        rendered = []
        for element in svg:
            if element.tag.endswith("}line"):
                rendered.append([(float(element.attrib[f"x{i}"]), float(element.attrib[f"y{i}"])) for i in (1, 2)])
            elif element.tag.endswith("}polyline"):
                rendered.append([tuple(map(float, point.split(","))) for point in element.attrib["points"].split()])
        expected = [[(round(e["x"] + x, 2), round(e["y"] + y, 2)) for x, y in e["points"]]
                    for e in elements if e["type"] == "arrow"]
        assert rendered == expected


def test_generated_obstacle_sizes_keep_side_routes_clear():
    # Synthetic layouts: different rows, aligned rows, reversed direction and several list sizes.
    for offset in (-200, 0, 200, 400):
        for height in (40, 100, 200, 300):
            board = route_map.Board()
            a = board.box("a", 0, 100, 100, "Шаг", route_map.COLORS["owner"])
            b = board.box("b", 400, 100 + offset, 100, "Артефакт", route_map.COLORS["owner"])
            pink = board.box("pink", 180, -50, 100, "Дубли", route_map.COLORS["hotspot"], min_h=height)
            for source, target in ((a, b), (b, a)):
                arrow = board.arrow(f"{source['id']}->{target['id']}", source, target, side_route=True)
                points = [(arrow["x"] + x, arrow["y"] + y) for x, y in arrow["points"]]
                assert not any(_segment_hits_rect(p, q, pink) for p, q in zip(points, points[1:]))
                assert arrow["startBinding"]["elementId"] == source["id"]
                assert arrow["endBinding"]["elementId"] == target["id"]


def test_blocked_side_port_fails_closed():
    board = route_map.Board()
    a = board.box("a", 0, 0, 100, "Шаг", route_map.COLORS["owner"])
    b = board.box("b", 400, 0, 100, "Артефакт", route_map.COLORS["owner"])
    board.box("blocked", 110, -20, 100, "Дубли", route_map.COLORS["hotspot"], min_h=200)
    with pytest.raises(route_map.SchemaError, match="no clear arrow route"):
        board.arrow("blocked-arrow", a, b, side_route=True)
    assert not any(e["type"] == "arrow" for e in board.elements)


def _copy_arch(tmp_path):
    import shutil
    shutil.copytree(ROOT / "docs/architecture", tmp_path / "docs/architecture")
    return tmp_path


@pytest.mark.parametrize("kind", ["input", "output", "partial", "hardlink"])
def test_aliases_and_foreign_partial_refused_before_any_write(tmp_path, monkeypatch, kind):
    root = _copy_arch(tmp_path)
    target = root / route_map.OUTPUTS["route"].with_suffix(".svg")
    if kind == "partial":
        target.with_name(target.name + ".partial").write_bytes(b"foreign")
    elif kind == "hardlink":
        target.unlink()
        target.hardlink_to(root / route_map.EVENTS)
    elif kind == "input":
        # Rename the configured input onto the exact output path; portable without symlink privileges.
        target.write_bytes((root / route_map.EVENTS).read_bytes())
        monkeypatch.setattr(route_map, "EVENTS", route_map.OUTPUTS["route"].with_suffix(".svg"))
    else:
        monkeypatch.setitem(route_map.OUTPUTS, "vpm-route", route_map.OUTPUTS["route"])
    before = {p: p.read_bytes() for p in (root / "docs/architecture").iterdir() if p.is_file()}
    assert route_map.main(["--root", str(root)]) == 2
    assert before == {p: p.read_bytes() for p in before}


def test_input_change_during_render_is_refused(tmp_path, monkeypatch):
    root = _copy_arch(tmp_path)
    original = route_map.render_all
    target = root / route_map.OUTPUTS["route"].with_suffix(".svg")
    before = target.read_bytes()
    def changing(path):
        result = original(path)
        with (root / route_map.EVENTS).open("a", encoding="utf-8") as fh:
            fh.write("\n# source changed during run\n")
        return result
    monkeypatch.setattr(route_map, "render_all", changing)
    assert route_map.main(["--root", str(root)]) == 2
    assert target.read_bytes() == before


def test_seven_groups_boundary_is_supported_and_revision_tracks_source():
    events = route_map.load_routes(ROOT)["route"]
    maps = route_map.load_context_maps(ROOT)
    steps = events["scheme"]["steps"]
    first = steps[0]
    steps[:1] = [dict(first, stages=s) for s in first["stages"].split(",")]
    assert len(steps) == 7
    old = route_map.view_revision(events, maps)
    board = route_map.short_route_board(events, maps["contexts"], maps)
    assert old in route_map.owners_markdown(events, maps["contexts"], maps)
    events["scheme"]["source_ru"] += " новая ревизия"
    assert route_map.view_revision(events, maps) != old
    assert board.elements


@pytest.mark.parametrize("suffix", ["-scheme.svg", "-scheme.excalidraw", "-owners.md"])
def test_new_view_stale_output_is_reported(tmp_path, capsys, suffix):
    import shutil
    root = _copy_arch(tmp_path)
    shutil.copy2(ROOT / "docs/decisions.md", root / "docs/decisions.md")
    stem = route_map.OUTPUTS["route"]
    target = root / stem.with_name(stem.name + suffix)
    target.write_bytes(b"synthetic stale output")
    assert route_map.main(["--root", str(root), "--check"]) == 1
    assert f"drift: {target.relative_to(root).as_posix()}" in capsys.readouterr().out


def test_conflicting_duplicate_status_cannot_silently_win():
    maps = route_map.load_context_maps(ROOT)
    cmap = maps["contexts"]
    maps["repeated"] = copy.deepcopy(cmap)
    row = maps["repeated"]["shared_kernel"]["duplicates"][0]
    row["status"] = "wrapper"
    with pytest.raises(route_map.SchemaError, match="conflicting statuses"):
        route_map.owners_markdown(route_map.load_routes(ROOT)["route"], cmap, maps)
