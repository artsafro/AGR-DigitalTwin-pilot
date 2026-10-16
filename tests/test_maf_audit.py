"""Synthetic tests for MAF catalogue finalisation and audit (issue #227)."""

import ast
import hashlib
import importlib.util
import json
import random
import re
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("maf_audit", ROOT / "tools" / "library" / "maf_audit.py")
audit = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(audit)


def _sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_json(path, doc) -> None:
    Path(path).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8", newline="\n")


def _entry(eid, tris=100, fbx=True, style="source-material"):
    return {
        "id": eid,
        "slug": eid,
        "tris": tris,
        "dims_m": [1.0, 2.0, 3.0],
        "fbx_path": f"C:/build/fbx/{eid}.fbx" if fbx else None,
        "preview_style": style,
        "element_first_faces": [1, 2],
        "source_object": eid,
    }


def _catalogue(*entries):
    return {
        "gap_m": 0.5,
        "scene": "library.max",
        "unit_to_m": 1.0,
        "counts": {"maf_entries": len(entries)},
        "excluded": [],
        "entries": list(entries),
        "duplicates": [],
        "overlaps": [],
        "spec_matches": [],
    }


def _readback_row(eid, tris, dims=None, loose=(0,), error=None, meshes=1, directory="D:/moved"):
    if error:
        return {"fbx": f"{directory}/{eid}.fbx", "error": error}
    objects = []
    for count in loose:
        objects.append({
            "name": eid,
            "triangles": tris,
            "loose_vertices": count,
            "non_triangle_faces": 0,
            "zero_area_triangles": 0,
            "uv_layers": ["UVMap"],
            "materials": ["wood"],
            "unassigned_faces": 0,
        })
    return {
        "fbx": f"{directory}/{eid}.fbx",
        "meshes": meshes,
        "tris": tris,
        "all_vertices": {"bbox_m": [[0, 0, 0], dims or [1, 2, 3]], "dims_m": list(dims or [1, 2, 3])},
        "referenced_vertices": {"bbox_m": [[0, 0, 0], dims or [1, 2, 3]], "dims_m": list(dims or [1, 2, 3])},
        "objects": objects,
    }


def _plan(ids):
    return {
        "entries": [
            {"id": eid, "slug": eid, "tris": 10 + index, "dims_m": [1.0, 1.0, 1.0]}
            for index, eid in enumerate(ids)
        ]
    }


def _built(ids, ok=True):
    return [{"id": eid, "ok": ok, "seconds": float(index + 1)} for index, eid in enumerate(ids)]


def test_merge_override_updates_fields_and_later_manifest_wins():
    base = [
        {"id": "A", "preview_style": "source-material", "keep": 1},
        {"id": "B", "preview_style": "source-material"},
    ]
    first = [{"id": "B", "preview_style": "neutral-shape-only"}, {"id": "A", "preview_style": "neutral-shape-only"}]
    second = [{"id": "A", "preview_style": "later", "extra": True}]
    merged, provenance = audit.merge_manifests(base, [("first.jsonl", first), ("second.jsonl", second)])
    assert [row["id"] for row in merged] == ["A", "B"]
    assert merged[0]["preview_style"] == "later"
    assert merged[0]["keep"] == 1
    assert merged[0]["extra"] is True
    assert merged[1]["preview_style"] == "neutral-shape-only"
    assert base[0]["preview_style"] == "source-material"
    assert provenance["base_rows"] == 2
    assert provenance["overrides"][0]["ids"] == ["A", "B"]
    assert provenance["overrides"][0]["fields"] == ["id", "preview_style"]
    assert provenance["overrides"][1]["manifest"] == "second.jsonl"
    assert provenance["overrides"][1]["fields"] == ["extra", "id", "preview_style"]


def test_merge_rejects_override_id_missing_from_base():
    with pytest.raises(ValueError, match="Z"):
        audit.merge_manifests([{"id": "A"}], [("override.jsonl", [{"id": "Z", "preview_style": "x"}])])


def test_read_jsonl_rejects_duplicate_ids(tmp_path):
    base = tmp_path / "base.jsonl"
    base.write_bytes(b'{"id": "A", "n": 1}\r\n\r\n{"id": "A", "n": 2}\r\n')
    with pytest.raises(ValueError, match="A"):
        audit.read_jsonl_unique(base)
    override = tmp_path / "override.jsonl"
    override.write_text('{"id": "B"}\n{"id": "B"}\n', encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="B"):
        audit.read_jsonl_unique(override)
    ok = tmp_path / "ok.jsonl"
    ok.write_bytes(b'{"id": "A"}\r\n{"id": "B", "k": 1}\r\n')
    rows = audit.read_jsonl_unique(ok)
    assert [row["id"] for row in rows] == ["A", "B"]


def test_finalize_rejects_duplicate_entry_ids():
    catalogue = _catalogue(_entry("A"), _entry("A"))
    with pytest.raises(ValueError, match="A"):
        audit.finalize_catalogue(catalogue)


def test_index_readback_rejects_duplicate_file_names():
    doc = {"files": [_readback_row("A", 10, directory="C:/one"), _readback_row("A", 11, directory="D:/two")]}
    with pytest.raises(ValueError, match="A.fbx"):
        audit.index_readback(doc)


def test_finalize_measured_fields_from_readback():
    entry = _entry("MAF_0001_X", tris=3000)
    catalogue = _catalogue(entry)
    readback = {
        "blender": "5.1.2",
        "seconds": 1.5,
        "files": [_readback_row("MAF_0001_X", 3050, dims=[1.5, 2.5, 3.5], loose=(1, 2))],
    }
    out = audit.finalize_catalogue(catalogue, readback)
    assert catalogue["entries"][0]["element_first_faces"] == [1, 2]
    got = out["entries"][0]
    assert "element_first_faces" not in got
    assert got["fbx_readback_status"] == "measured"
    assert got["fbx_readback_tris"] == 3050
    assert got["fbx_readback_dims_m"] == [1.5, 2.5, 3.5]
    assert got["fbx_readback_triangle_delta"] == 50
    assert got["fbx_readback_loose_vertices"] == 3
    assert "fbx_readback_error" not in got
    tail = [
        "preview_blank",
        "fbx_readback_tris",
        "fbx_readback_dims_m",
        "fbx_readback_triangle_delta",
        "fbx_readback_loose_vertices",
        "fbx_readback_status",
    ]
    keys = list(got)
    assert keys[-len(tail):] == tail
    assert out["counts"]["fbx_readback_measured"] == 1


def test_finalize_absent_readback_is_not_measured():
    catalogue = _catalogue(_entry("A"), _entry("B"), _entry("C"))
    out = audit.finalize_catalogue(catalogue, None)
    assert out["counts"]["fbx_readback_measured"] == 0
    assert out["counts"]["fbx_readback_not_measured"] == 3
    for entry in out["entries"]:
        assert entry["fbx_readback_status"] == "not measured"
        assert entry["fbx_readback_tris"] is None
        assert entry["fbx_readback_dims_m"] is None
        assert entry["fbx_readback_triangle_delta"] is None
        assert entry["fbx_readback_loose_vertices"] is None
        assert "fbx_readback_error" not in entry


def test_finalize_entry_missing_from_readback_is_not_measured():
    catalogue = _catalogue(_entry("A", tris=10), _entry("B", tris=20), _entry("C", tris=30))
    readback = {"blender": "5.1.2", "seconds": 1, "files": [
        _readback_row("A", 10),
        _readback_row("C", 30),
    ]}
    out = audit.finalize_catalogue(catalogue, readback)
    by_id = {entry["id"]: entry for entry in out["entries"]}
    assert by_id["B"]["fbx_readback_status"] == "not measured"
    assert by_id["B"]["fbx_readback_tris"] is None
    assert by_id["A"]["fbx_readback_status"] == "measured"
    assert by_id["C"]["fbx_readback_status"] == "measured"
    assert out["counts"]["fbx_readback_measured"] == 2
    assert out["counts"]["fbx_readback_not_measured"] == 1


def test_finalize_readback_error_row_is_not_a_pass():
    catalogue = _catalogue(_entry("A", tris=10))
    readback = {"files": [_readback_row("A", 10, error="import failed")]}
    out = audit.finalize_catalogue(catalogue, readback)
    entry = out["entries"][0]
    assert entry["fbx_readback_status"] == "error"
    assert entry["fbx_readback_error"] == "import failed"
    assert entry["fbx_readback_tris"] is None
    assert entry["fbx_readback_dims_m"] is None
    assert entry["fbx_readback_triangle_delta"] is None
    assert entry["fbx_readback_loose_vertices"] is None
    assert out["counts"]["fbx_readback_errors"] == 1
    assert out["counts"]["fbx_readback_measured"] == 0


def test_preview_blank_is_none_without_preview_check():
    out = audit.finalize_catalogue(_catalogue(_entry("A"), _entry("B")), None, None)
    assert all(entry["preview_blank"] is None for entry in out["entries"])
    assert all(entry["preview_blank"] is not False for entry in out["entries"])
    assert out["counts"]["preview_blank"] is None
    assert out["counts"]["preview_not_checked"] == 2


def test_preview_blank_from_report():
    catalogue = _catalogue(_entry("A"), _entry("B"), _entry("C"))
    report = {"checked": ["A", "B"], "blank": ["B"]}
    out = audit.finalize_catalogue(catalogue, None, report)
    by_id = {entry["id"]: entry for entry in out["entries"]}
    assert by_id["A"]["preview_blank"] is False
    assert by_id["B"]["preview_blank"] is True
    assert by_id["C"]["preview_blank"] is None
    assert out["counts"]["preview_blank"] == 1
    assert out["counts"]["preview_not_checked"] == 1


def test_preview_check_detects_blank_and_missing(tmp_path):
    uniform = tmp_path / "uniform.png"
    Image.new("RGB", (64, 64), (240, 240, 240)).save(uniform)
    drawn_path = tmp_path / "drawn.png"
    drawn = Image.new("RGB", (64, 64), (240, 240, 240))
    ImageDraw.Draw(drawn).rectangle([8, 8, 40, 40], fill=(0, 0, 0))
    drawn.save(drawn_path)
    missing = tmp_path / "gone.png"
    entries = [
        {"id": "blank", "preview_path": str(uniform)},
        {"id": "drawn", "preview_path": str(drawn_path)},
        {"id": "gone", "preview_path": str(missing)},
        {"id": "skip", "preview_path": None},
    ]
    report = audit.preview_check(entries)
    assert report["checked"] == ["blank", "drawn"]
    assert report["blank"] == ["blank"]
    assert report["missing"] == ["gone"]
    assert report["threshold"] == 12
    assert report["min_fg"] == 8


def test_dump_catalogue_json_round_trips():
    catalogue = _catalogue(_entry("A", tris=3))
    catalogue["entries"][0]["source_object"] = "Лавка"
    text = audit.dump_catalogue_json(catalogue)
    assert "\r" not in text
    assert text.endswith("\n")
    assert json.loads(text) == catalogue
    empty = {"gap_m": 0.5, "entries": [], "excluded": [], "spec_matches": []}
    empty_text = audit.dump_catalogue_json(empty)
    assert json.loads(empty_text) == empty
    assert '"entries": [' in empty_text


def test_contact_sheet_counts_come_from_data(tmp_path):
    preview_a = tmp_path / "a.png"
    preview_b = tmp_path / "b.png"
    max_a = tmp_path / "a.max"
    entries = [
        {
            "id": "A<1>",
            "preview_path": str(preview_a),
            "max_path": str(max_a),
            "source_object": "Bench & <b>",
            "preview_style": "neutral-shape-only",
        },
        {
            "id": "B",
            "preview_path": str(preview_b),
            "max_path": None,
            "source_object": "Urn",
            "preview_style": "source-material",
        },
        {
            "id": "C",
            "preview_path": None,
            "source_object": "Skip",
            "preview_style": "source-material",
        },
    ]
    page = audit.render_contact_sheet_html(entries)
    assert "2 MAF audit previews" in page
    assert "1 previews use neutral materials" in page
    assert "A&lt;1&gt;" in page
    assert "Bench &amp; &lt;b&gt;" in page
    assert "Skip" not in page
    assert page.count("<a href=") == 1
    assert Path(preview_a).as_uri() in page
    assert "<br>neutral shape only" in page


def test_provenance_records_sha256_of_inputs(tmp_path):
    catalogue = _catalogue(_entry("A", tris=10))
    cat_path = tmp_path / "raw.json"
    rb_path = tmp_path / "readback.json"
    _write_json(cat_path, catalogue)
    _write_json(rb_path, {"blender": "5.1.2", "seconds": 1, "files": [_readback_row("A", 10)]})
    out_json = tmp_path / "catalogue.json"
    out_html = tmp_path / "contact_sheet.html"
    assert audit.main([
        "finalize", "--catalogue", str(cat_path), "--readback", str(rb_path),
        "--out-json", str(out_json), "--out-html", str(out_html),
    ]) == 0
    doc = json.loads(out_json.read_text(encoding="utf-8"))
    by_path = {item["path"]: item for item in doc["provenance"]}
    assert by_path[cat_path.as_posix()]["sha256"] == _sha(cat_path)
    assert by_path[rb_path.as_posix()]["sha256"] == _sha(rb_path)
    assert by_path[cat_path.as_posix()]["bytes"] == cat_path.stat().st_size
    catalogue["gap_m"] = 0.25
    _write_json(cat_path, catalogue)
    out_json2 = tmp_path / "catalogue2.json"
    out_html2 = tmp_path / "contact_sheet2.html"
    audit.main([
        "finalize", "--catalogue", str(cat_path), "--readback", str(rb_path),
        "--out-json", str(out_json2), "--out-html", str(out_html2),
    ])
    doc2 = json.loads(out_json2.read_text(encoding="utf-8"))
    changed = {item["path"]: item["sha256"] for item in doc2["provenance"]}
    assert changed[cat_path.as_posix()] == _sha(cat_path)
    assert changed[cat_path.as_posix()] != by_path[cat_path.as_posix()]["sha256"]
    assert changed[rb_path.as_posix()] == by_path[rb_path.as_posix()]["sha256"]


def _library(tmp_path):
    library = tmp_path / "library"
    (library / "max").mkdir(parents=True)
    (library / "fbx").mkdir(parents=True)
    (library / "max" / "a.max").write_bytes(b"12345")
    (library / "max" / "b.max").write_bytes(b"abc")
    (library / "fbx" / "a.fbx").write_bytes(b"xyzxyz")
    (library / "max" / "note.txt").write_text("skip", encoding="utf-8")
    return library


def test_audit_counts_follow_inputs_not_constants(tmp_path):
    library = _library(tmp_path)
    ids = ["A", "B", "C"]
    result, matches = audit.build_audit(
        plan=_plan(ids),
        built_rows=_built(ids),
        library_dir=library,
    )
    assert result["build"]["entries"] == 3
    assert result["build"]["ok"] == 3
    built = _built(ids)
    assert result["build"]["sum_entry_seconds"] == round(sum(row["seconds"] for row in built), 2)
    assert result["build"]["slowest_entry_seconds"] == max(row["seconds"] for row in built)
    assert result["files"]["max"] == {"count": 2, "bytes": 8}
    assert result["files"]["fbx"] == {"count": 1, "bytes": 6}
    assert result["scope"] == "internal library audit, not NPM/VPM delivery or user acceptance"
    assert matches is None
    assert "provenance" not in result


def test_audit_absent_readback_is_not_measured(tmp_path):
    result, _matches = audit.build_audit(
        plan=_plan(["A"]),
        built_rows=_built(["A"]),
        library_dir=_library(tmp_path),
    )
    assert result["fbx_readback"] == {"status": "not measured"}
    assert result["blend_matching"] == {"status": "not measured"}
    assert result["native_sample_readback"] == {"status": "not measured"}
    assert result["preview_repair"] == {"count": 0}


def test_audit_partial_readback_excludes_missing_from_pass_counts(tmp_path):
    plan = _plan(["A", "B", "C"])
    files = [
        _readback_row("A", 10, dims=[1, 1, 1]),
        _readback_row("B", 11, dims=[1, 1, 1]),
    ]
    readback = {"blender": "5.1.2", "seconds": 4.0, "files": files}
    result, _matches = audit.build_audit(
        plan=plan,
        built_rows=_built(["A", "B", "C"]),
        library_dir=_library(tmp_path),
        readback_doc=readback,
        readback_path=str(tmp_path / "fbx_readback.json"),
    )
    section = result["fbx_readback"]
    assert section["files"] == 2
    assert section["tris_exact"] <= 2
    assert section["tris_exact"] == 2
    assert section["not_measured"] == ["C"]
    assert "errors" not in section
    assert section["one_mesh"] == 2
    assert section["referenced_dims_within_5mm"] == 2


def test_audit_rejects_duplicate_and_unknown_built_ids(tmp_path):
    library = tmp_path
    with pytest.raises(ValueError, match="duplicate plan id"):
        audit.build_audit(
            plan={"entries": [
                {"id": "A", "slug": "A", "tris": 1, "dims_m": [1, 1, 1]},
                {"id": "A", "slug": "A2", "tris": 1, "dims_m": [1, 1, 1]},
            ]},
            built_rows=[],
            library_dir=library,
        )
    plan = _plan(["A"])
    with pytest.raises(ValueError, match="duplicate built id"):
        audit.build_audit(
            plan=plan,
            built_rows=[
                {"id": "A", "ok": True, "seconds": 1},
                {"id": "A", "ok": True, "seconds": 2},
            ],
            library_dir=library,
        )
    with pytest.raises(ValueError, match="not in plan"):
        audit.build_audit(
            plan=plan,
            built_rows=[{"id": "Z", "ok": True, "seconds": 1}],
            library_dir=library,
        )


def test_hash_sources_detects_changed_source(tmp_path):
    original = tmp_path / "scene.max"
    original.write_bytes(b"max-bytes")
    copy = tmp_path / "src.max"
    copy.write_bytes(b"max-bytes")
    manifest = tmp_path / "hash_before.txt"
    manifest.write_text(f"{_sha(original)} *{original.as_posix()}\n", encoding="utf-8", newline="\n")
    rows = audit.hash_sources(manifest, [str(copy)])
    assert rows[0]["sha256_before"] == rows[0]["sha256_after"] == rows[0]["copy_sha256"]
    original.write_bytes(b"changed")
    with pytest.raises(ValueError, match="source changed"):
        audit.hash_sources(manifest, [str(copy)])


def test_hash_sources_matches_copy_by_suffix(tmp_path):
    max_src = tmp_path / "lib.max"
    blend_src = tmp_path / "lib.blend"
    max_src.write_bytes(b"max")
    blend_src.write_bytes(b"blend")
    max_copy = tmp_path / "nested" / "src.max"
    blend_copy = tmp_path / "nested" / "src.blend"
    max_copy.parent.mkdir()
    max_copy.write_bytes(b"max")
    blend_copy.write_bytes(b"blend")
    manifest = tmp_path / "hash_before.txt"
    lines = [
        f"{_sha(max_src)} *{max_src.as_posix()}",
        f"{_sha(blend_src)} *{blend_src.as_posix()}",
    ]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    rows = audit.hash_sources(manifest, [str(blend_copy), str(max_copy)])
    assert rows[0]["copy"].endswith("src.max")
    assert rows[1]["copy"].endswith("src.blend")
    assert rows[0]["copy_sha256"] == _sha(max_copy)
    assert rows[1]["copy_sha256"] == _sha(blend_copy)


def test_cli_refuses_to_overwrite_existing_output(tmp_path):
    catalogue = _catalogue(_entry("A", tris=4))
    cat_path = tmp_path / "raw.json"
    _write_json(cat_path, catalogue)
    out_json = tmp_path / "catalogue.json"
    out_html = tmp_path / "sheet.html"
    out_json.write_text("keep", encoding="utf-8")
    with pytest.raises(SystemExit, match="overwrite"):
        audit.main([
            "finalize", "--catalogue", str(cat_path),
            "--out-json", str(out_json), "--out-html", str(out_html),
        ])
    assert out_json.read_text(encoding="utf-8") == "keep"
    assert not out_html.exists()


def test_semantic_diff_reports_changed_missing_and_extra_ids(tmp_path):
    old = {"entries": [{"id": "A", "tris": 1}, {"id": "B", "tris": 2}, {"id": "C", "tris": 3}]}
    new = {
        "entries": [
            {"id": "B", "tris": 5},
            {"id": "A", "tris": 1.0, "fbx_readback_status": "not measured"},
            {"id": "D", "tris": 4},
        ]
    }
    diff = audit.semantic_diff(old, new)
    assert diff["equal"] is False
    assert diff["missing_ids"]["entries"] == ["C"]
    assert diff["extra_ids"]["entries"] == ["D"]
    changed = diff["paths"]["entries[*].tris"]
    assert changed["kind"] == "changed"
    assert changed["count"] == 1
    assert changed["examples"] == [{"id": "B", "old": 2, "new": 5}]
    added = diff["paths"]["entries[*].fbx_readback_status"]
    assert added["kind"] == "added"
    assert added["examples"][0]["id"] == "A"
    assert added["examples"][0]["new"] == "not measured"
    same = audit.semantic_diff(
        {"entries": [{"id": "A", "n": 1.0}, {"id": "B", "n": 2}]},
        {"entries": [{"id": "B", "n": 2}, {"id": "A", "n": 1.0 + 1e-12}]},
    )
    assert same["equal"] is True
    old_path = tmp_path / "old.json"
    new_path = tmp_path / "new.json"
    out_path = tmp_path / "diff.json"
    _write_json(old_path, old)
    _write_json(new_path, new)
    assert audit.main(["compare", "--old", str(old_path), "--new", str(new_path), "--out", str(out_path)]) == 0
    assert json.loads(out_path.read_text(encoding="utf-8"))["missing_ids"]["entries"] == ["C"]


def test_blender_inventory_script_is_parameterised():
    path = ROOT / "tools" / "library" / "maf_blender_inventory.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
    assert "bpy" in imported
    assert "AGR_MAF_BLEND_INVENTORY" in source
    assert "C:/x" not in source
    assert "C:\\x" not in source
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"save_as_mainfile", "save_mainfile"}
        if isinstance(node, ast.Name):
            assert node.id not in {"save_as_mainfile", "save_mainfile"}


def test_no_snapshot_totals_in_code():
    source = (ROOT / "tools" / "library" / "maf_audit.py").read_text(encoding="utf-8")
    assert re.search(r"\b931\b", source) is None
    assert "== 24" not in source
    assert "count': 24" not in source
    assert 'count": 24' not in source


def test_finalize_never_manufactures_pass_random():
    for seed in range(200):
        rng = random.Random(seed)
        count = rng.randint(3, 4)
        entries = []
        for index in range(count):
            entries.append({
                "id": f"MAF_{index}",
                "tris": rng.randint(10, 400),
                "fbx_path": f"C:/build/fbx/MAF_{index}.fbx",
                "preview_style": "source-material",
            })
        files = []
        measured_names = set()
        error_names = set()
        for entry in entries:
            if rng.random() >= 0.65:
                continue
            name = Path(entry["fbx_path"]).name
            if rng.random() < 0.25:
                files.append({"fbx": f"E:/other/{name}", "error": "boom"})
                error_names.add(name)
            else:
                tris = entry["tris"] + rng.choice([-2, 0, 3])
                files.append({
                    "fbx": f"E:/other/{name}",
                    "meshes": 1,
                    "tris": tris,
                    "referenced_vertices": {"dims_m": [1.0, 2.0, 3.0]},
                    "objects": [{"loose_vertices": 1}, {"loose_vertices": 4}],
                })
                measured_names.add(name)
        readback = None if rng.random() < 0.2 else {"blender": "5.1.2", "seconds": 2.0, "files": files}
        if rng.random() < 0.25:
            preview = None
            checked = set()
        else:
            checked = {entry["id"] for entry in entries if rng.random() < 0.7}
            blank = {eid for eid in checked if rng.random() < 0.4}
            preview = {"checked": sorted(checked), "blank": sorted(blank)}
        out = audit.finalize_catalogue(_catalogue_from(entries), readback, preview)
        by_name = {}
        if readback is not None:
            for row in readback["files"]:
                by_name[Path(row["fbx"]).name] = row
        measured = 0
        for entry in out["entries"]:
            name = Path(entry["fbx_path"]).name
            row = by_name.get(name) if readback is not None else None
            has_measured = row is not None and not row.get("error")
            assert (entry["fbx_readback_status"] == "measured") is has_measured
            if has_measured:
                measured += 1
                assert entry["fbx_readback_tris"] == row["tris"]
                assert entry["fbx_readback_triangle_delta"] == row["tris"] - entries_by_id(entries)[entry["id"]]["tris"]
                assert entry["fbx_readback_loose_vertices"] == 5
            else:
                assert entry["fbx_readback_tris"] is None
                assert entry["fbx_readback_triangle_delta"] is None
            assert (entry["preview_blank"] is None) is (entry["id"] not in checked)
            if entry["preview_blank"] is False:
                assert entry["id"] in checked
                assert entry["id"] not in set(preview["blank"])
        assert out["counts"]["fbx_readback_measured"] == measured
        if preview is None or not checked:
            assert out["counts"]["preview_blank"] is None


def _catalogue_from(entries):
    return {
        "counts": {},
        "entries": [dict(entry) for entry in entries],
        "excluded": [],
        "spec_matches": [],
    }


def entries_by_id(entries):
    return {entry["id"]: entry for entry in entries}


def test_preview_repair_zero_blank_is_measured_zero_not_not_measured():
    """A preview-check with no blank ids measures 0; an empty blank-before list is 0 (regression #227)."""
    overrides = [("preview-v002.jsonl", [{"id": "MAF_0001", "preview_style": "neutral-shape-only"}])]
    report = {"checked": ["MAF_0001", "MAF_0002"], "blank": [], "missing": []}
    section = audit._preview_repair_section(overrides, [], report, None)
    assert section["blank_after"] == 0
    assert section["blank_before"] == 0
    assert section["verified_by"] == "maf_audit.py preview-check over 2 preview paths"
    absent = audit._preview_repair_section(overrides, None, None, None)
    assert absent["blank_after"] == "not measured"
    assert absent["blank_before"] == "not measured"
    assert absent["wrapper_seconds"] == "not measured"


def test_catalogue_markdown_uses_lf_newlines(tmp_path):
    """The committed catalogue.md is LF; the catalogue command must not write CRLF on Windows."""
    spec = importlib.util.spec_from_file_location("maf_catalogue_lf", ROOT / "tools" / "library" / "maf_catalogue.py")
    cat = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cat)
    plan = {"gap_m": 0.5, "scene": "s.max", "unit_to_m": 1.0, "counts": {}, "excluded": [],
            "entries": [{"id": "MAF_0001", "slug": "MAF_0001_A", "source_object": "A", "tris": 12,
                         "dims_m": [1.0, 1.0, 1.0], "bbox_m": [[0, 0, 0], [1, 1, 1]], "material": None}]}
    _write_json(tmp_path / "plan.json", plan)
    _write_json(tmp_path / "blend.json", {"objects": []})
    (tmp_path / "built.jsonl").write_text("", encoding="utf-8")
    cat.main(["catalogue", "--plan", str(tmp_path / "plan.json"), "--built", str(tmp_path / "built.jsonl"),
              "--blend", str(tmp_path / "blend.json"), "--out-json", str(tmp_path / "c.json"),
              "--out-md", str(tmp_path / "c.md")])
    assert b"\r\n" not in (tmp_path / "c.md").read_bytes()
