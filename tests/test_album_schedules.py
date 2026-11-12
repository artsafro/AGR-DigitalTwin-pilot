"""Album schedules/legends (#1235): typed CSV, two-engine reconciliation, materials without defaults.

Pattern: n/a | new-case: fail-closed regression probes for page-referenced schedule/legend export.

Engine tables in the pure tests are hand-written dicts; the PDFs are SYNTHETIC, generated at test time with
PyMuPDF (no committed PDF, no user album). The PDF tests need the optional extra and the second engine:
env -u PYTHONPATH -u VIRTUAL_ENV uv run -q --extra pdf-review --with pdfplumber==0.11.10 pytest -q tests/test_album_schedules.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

from dt_ai.album import schedules as S

ELV_LIKE = [
    ["Экспликация помещений 1-го этажа", None, None],
    ["Номер", "Имя", "Площадь,\nм2"],
    ["Административно-бытовые помещения", None, None],
    ["1.D.17", "Гардероб персонала ТЦ", "10.77"],
    ["1.D.18", "Гардероб персонала ТЦ", "11.54"],
    ["ИТОГО площадь помещений этажа 22.31", None, None],
]


def _boxes(cells, x0=0.0, y0=0.0, w=50.0, h=10.0):
    """Cell boxes for a regular grid; a None cell is covered by its left (or upper) neighbour."""
    out = []
    for r, row in enumerate(cells):
        line = []
        for c, value in enumerate(row):
            line.append(None if value is None else [x0 + c * w, y0 + r * h, x0 + (c + 1) * w, y0 + (r + 1) * h])
        # widen a cell over the None cells that follow it in the row (horizontal merge)
        for c in range(len(row)):
            if line[c] is not None:
                k = c + 1
                while k < len(row) and row[k] is None:
                    k += 1
                line[c][2] = x0 + k * w
        out.append(line)
    return out


def _engine(cells, **kw):
    return dict(bbox=[0.0, 0.0, 50.0 * len(cells[0]), 10.0 * len(cells)], cells=cells, cell_boxes=_boxes(cells, **kw))


def _table(prim, sec="same", status="ok"):
    secondary = _engine(prim) if sec == "same" else (None if sec is None else _engine(sec))
    return S.build_table("p1-t1", 1, "27", _engine(prim), secondary, secondary_status=status)


# ---------------------------------------------------------------- row types, units, measures


def test_row_types_header_category_data_total():
    assert S.row_types(ELV_LIKE) == ["header", "header", "category", "data", "data", "total"]


def test_row_types_column_numbering_and_empty_rows():
    cells = [["№", "Наименование", "Кол-во"], ["1", "2", "3"], ["", None, None], ["1", "Лампа", "4"]]
    assert S.row_types(cells) == ["header", "header", "empty", "data"]


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Кол-во", ("quantity", "")),
        ("Количество, шт.", ("quantity", "pcs")),
        ("Длина, м", ("length", "m")),
        ("Длина", ("length", "")),
        ("Площадь,\nм2", ("area", "m2")),
        ("Площадь, м²", ("area", "m2")),
        ("Размер, мм", ("length", "mm")),
        ("Масса, кг", ("mass", "kg")),
        ("Площадь, мм", ("unknown", "")),  # kind/unit conflict is never resolved by a guess
        ("Наименование", ("text", "")),
        ("", ("unknown", "")),
    ],
)
def test_column_unit_quantity_vs_length(label, expected):
    assert S.column_unit(label) == expected


def test_embedded_measures_keep_quantity_and_length_apart():
    text = "Общая длина: 5 505 метров\nСечение: 16x15 мм"
    found = S.cell_measures(text)
    assert {"raw": "5 505 метров", "value_text": "5 505", "unit": "m", "kind": "length"} in found
    assert {"raw": "16x15 мм", "value_text": "16x15", "unit": "mm", "kind": "length"} in found
    table = _table([["Наименование", "Кол-во"], [text, "1"]])
    assert table["columns"][1]["value_kind"] == "quantity"
    assert table["rows"][1]["measures"][0]["kind"] == "length"


# ---------------------------------------------------------------- reconciliation


def test_two_engines_agree():
    table = _table(ELV_LIKE)
    statuses = {c["status"] for row in table["cells"] for c in row}
    assert statuses <= {"agree", "merged", "empty"}
    assert table["suspect_cells"] == []


def test_disagreement_is_listed_never_picked():
    sec = [row[:] for row in ELV_LIKE]
    sec[3][1] = "ГардеробперсоналаТЦ"
    table = _table(ELV_LIKE, sec)
    cell = table["cells"][3][1]
    assert cell["status"] == "suspect"
    assert cell["text"] == "Гардероб персонала ТЦ" and cell["text_alt"] == "ГардеробперсоналаТЦ"
    assert table["suspect_cells"] == [
        dict(row=4, col=2, reason="engines_disagree", primary="Гардероб персонала ТЦ", secondary="ГардеробперсоналаТЦ")
    ]


def test_none_versus_text_is_a_disagreement():
    sec = [row[:] for row in ELV_LIKE]
    sec[0][1] = "лишнее"
    table = _table(ELV_LIKE, sec)
    assert table["cells"][0][1]["status"] == "suspect"


def test_missing_second_engine_marks_every_cell():
    table = _table(ELV_LIKE, None, status="second_engine_unavailable")
    n = sum(len(r) for r in ELV_LIKE)
    assert len(table["suspect_cells"]) == n
    assert {c["status"] for row in table["cells"] for c in row} == {"single_engine"}
    assert {s["reason"] for s in table["suspect_cells"]} == {"second_engine_unavailable"}


def test_shape_mismatch_marks_every_cell_suspect():
    table = _table(ELV_LIKE, ELV_LIKE[:-1])
    assert {c["status"] for row in table["cells"] for c in row} == {"suspect"}
    assert {s["reason"] for s in table["suspect_cells"]} == {"shape_mismatch"}


def test_merged_cell_keeps_provenance_and_stays_empty():
    table = _table(ELV_LIKE)
    cell = table["cells"][0][2]
    assert cell["status"] == "merged" and cell["text"] == "" and cell["merged_from"] == "r1c1"
    assert dict(row=1, col=3, merged_from="r1c1") in table["merged_cells"]


def test_vertical_merge_points_up():
    cells = [["Тип", "Отделка"], ["A", "RAL 7021"], ["B", None]]
    boxes = [[[0, 0, 50, 10], [50, 0, 100, 10]], [[0, 10, 50, 20], [50, 10, 100, 30]], [[0, 20, 50, 30], None]]
    eng = dict(bbox=[0, 0, 100, 30], cells=cells, cell_boxes=boxes)
    table = S.build_table("p1-t1", 1, None, eng, eng, secondary_status="ok")
    assert table["cells"][2][1]["merged_from"] == "r2c2"


def test_unresolved_merge_is_suspect():
    eng = dict(bbox=[0, 0, 100, 20], cells=[["A", "B"], [None, "x"]], cell_boxes=None)
    table = S.build_table("p1-t1", 1, None, eng, eng, secondary_status="ok")
    assert table["cells"][1][0]["status"] == "merged_unresolved"
    assert any(s["reason"] == "merged_source_unresolved" for s in table["suspect_cells"])


# ---------------------------------------------------------------- typed CSV


def test_csv_header_is_the_typed_schema_and_validates(tmp_path):
    path = tmp_path / "p1-t1.csv"
    S.write_table_csv(_table(ELV_LIKE), path)
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    assert tuple(rows[0]) == tuple(name for name, _ in S.CSV_COLUMNS)
    assert len(rows) - 1 == sum(len(r) for r in ELV_LIKE)  # every cell is one line, nothing dropped
    assert S.validate_schedule_csv(path) == []
    data = [r for r in rows[1:] if r[3] == "data" and r[2] == "3"]
    assert {r[S.CSV_NAMES.index("value_kind")] for r in data} == {"area"}
    assert {r[S.CSV_NAMES.index("unit")] for r in data} == {"m2"}


@pytest.mark.parametrize(
    ("column", "bad"),
    [("row_type", "row"), ("row", "x"), ("col", "0"), ("cell_status", "ok"), ("value_kind", "metres"),
     ("unit", "м"), ("page", "-1"), ("x0", "nan"), ("x1", "inf")],
)
def test_csv_validator_rejects_bad_values(tmp_path, column, bad):
    path = tmp_path / "t.csv"
    S.write_table_csv(_table(ELV_LIKE), path)
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    rows[1][S.CSV_NAMES.index(column)] = bad
    with path.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh, lineterminator="\n").writerows(rows)
    errors = S.validate_schedule_csv(path)
    assert errors and column in errors[0]


def test_csv_validator_rejects_wrong_header_and_empty(tmp_path):
    path = tmp_path / "t.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    assert S.validate_schedule_csv(path)
    path.write_text("", encoding="utf-8")
    assert S.validate_schedule_csv(path)


# ---------------------------------------------------------------- materials without defaults

FINISH = [
    ["Элемент", "Отделка"],
    ["Панель 1", "RAL 7021 металл"],
    ["Панель 2", ""],
    ["Панель 3", None],
    ["Панель 4", "RAL 1001 сосна"],
]


def _finish_table(cells):
    """Two columns; a None finish cell is a VERTICAL merge covered by the cell above (realistic finish column)."""
    boxes = []
    for r, row in enumerate(cells):
        boxes.append([[0.0, r * 10.0, 50.0, (r + 1) * 10.0], None if row[1] is None else [50.0, r * 10.0, 100.0, (r + 1) * 10.0]])
    for r in range(len(cells) - 1, 0, -1):
        if cells[r][1] is None:
            k = r - 1
            while cells[k][1] is None:
                k -= 1
            boxes[k][1][3] = max(boxes[k][1][3], (r + 1) * 10.0)
    eng = dict(bbox=[0.0, 0.0, 100.0, 10.0 * len(cells)], cells=cells, cell_boxes=boxes)
    return S.build_table("p1-t1", 1, None, eng, eng, secondary_status="ok")


def test_finish_rows_are_data_not_categories():
    assert [r["row_type"] for r in _finish_table(FINISH)["rows"]] == ["header", "data", "data", "data", "data"]


def test_missing_finish_is_never_filled_from_a_neighbour():
    table = _finish_table(FINISH)
    mats = S.finish_materials(table)
    by_row = {m["binding"]["row"]: m for m in mats}
    assert by_row[2]["code"] == "RAL 7021" and by_row[2]["status"] == "present"
    assert by_row[3]["status"] == "missing" and by_row[3]["code"] is None and by_row[3]["original_label"] is None
    assert by_row[4]["status"] == "merged_unresolved" and by_row[4]["code"] is None
    assert by_row[4]["original_label"] is None and by_row[4]["merged_from"] == "r3c2"
    assert by_row[5]["code"] == "RAL 1001"
    assert all(m["default_material"] is None for m in mats)


def test_probe_finish_never_copied_random_tables():
    """Brute force: 400 random finish columns; every non-present row has no label/code of its own neighbour."""
    rng = random.Random(1235)
    choices = ["RAL 7021", "RAL 1001 сосна", "", None, "окраска", "NCS S 2010-Y30R"]
    for _ in range(400):
        n = rng.randint(1, 8)
        cells = [["Элемент", "Отделка"]] + [[f"E{i}", rng.choice(choices)] for i in range(n)]
        if cells[1][1] is None:
            cells[1][1] = ""
        mats = S.finish_materials(_finish_table(cells))
        assert {m["binding"]["row"] for m in mats} == set(range(2, n + 2))  # every data row accounted
        for m in mats:
            own = cells[m["binding"]["row"] - 1][1]
            if m["status"] == "present":
                assert m["original_label"] == own and own
            else:
                assert m["original_label"] is None and m["code"] is None
            assert m["default_material"] is None


def test_codes_parsed_from_label():
    assert S.material_codes("Панели RAL7021, RAL 1001 и NCS S 2010-Y30R") == ["RAL 7021", "RAL 1001", "NCS S 2010-Y30R"]
    assert S.material_codes("без кода") == []


# ---------------------------------------------------------------- synthetic PDF end to end


def _synthetic_pdf(path: Path) -> Path:
    pymupdf = pytest.importorskip("pymupdf", reason="optional extra 'pdf-review'")
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)
    page.insert_font(fontname="F0", fontbuffer=pymupdf.Font("cjk").buffer)
    rows = [["Спецификация", "", "", ""], ["Наименование", "Кол-во", "Длина, м", "Отделка"],
            ["Лента LED", "1", "5,505", "RAL 9003"], ["Профиль", "2", "3,0", ""],
            ["Итого", "3", "", ""]]
    x0, y0, w, h = 60, 60, 110, 20
    shape = page.new_shape()
    for r in range(len(rows) + 1):
        shape.draw_line((x0, y0 + r * h), (x0 + 4 * w, y0 + r * h))
    for c in range(5):
        top = y0 + h if c not in (0, 4) else y0  # first row is merged across the table
        shape.draw_line((x0 + c * w, top), (x0 + c * w, y0 + len(rows) * h))
    shape.finish(color=(0, 0, 0), width=0.7)
    shape.commit()
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            if text:
                page.insert_text((x0 + c * w + 3, y0 + r * h + 14), text, fontname="F0", fontsize=9)
    # legend: filled swatch + label with a RAL code, outside the table
    sw = page.new_shape()
    sw.draw_rect(pymupdf.Rect(60, 300, 80, 312))
    sw.finish(color=(0, 0, 0), fill=(0.1, 0.2, 0.6), width=0.3)
    sw.commit()
    page.insert_text((90, 310), "Панели фасадные RAL 5023", fontname="F0", fontsize=9)
    page.insert_text((90, 340), "Лист 12", fontname="F0", fontsize=9)
    doc.save(path)
    return path


@pytest.fixture()
def synthetic(tmp_path):
    pytest.importorskip("pdfplumber", reason="second table engine (uv run --with pdfplumber==0.11.10)")
    return _synthetic_pdf(tmp_path / "synthetic.pdf")


def test_export_end_to_end(tmp_path, synthetic):
    jsonschema = pytest.importorskip("jsonschema")
    before = hashlib.sha256(synthetic.read_bytes()).hexdigest()
    out = tmp_path / "out"
    manifest = S.export_schedules(synthetic, out, pages=[1])
    assert hashlib.sha256(synthetic.read_bytes()).hexdigest() == before
    assert manifest["passed"] is False
    assert manifest["pages"][0]["route"] == "table_extraction"
    tables = manifest["tables"]
    assert len(tables) == 1
    tid = tables[0]["table_id"]
    assert S.validate_schedule_csv(out / "schedules" / f"{tid}.csv") == []
    side = json.loads((out / "schedules" / f"{tid}.json").read_text("utf-8"))
    schema = json.loads(Path("schemas/AlbumSchedule.schema.json").read_text("utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(side, schema)
    types = [r["row_type"] for r in side["rows"]]
    assert types == ["header", "header", "data", "data", "total"]
    kinds = {c["label"]: (c["value_kind"], c["unit"]) for c in side["columns"]}
    assert kinds["Кол-во"] == ("quantity", "") and kinds["Длина, м"] == ("length", "m")
    assert side["csv_sha256"] == hashlib.sha256((out / "schedules" / f"{tid}.csv").read_bytes()).hexdigest()
    mats = json.loads((out / "materials.json").read_text("utf-8"))
    mschema = json.loads(Path("schemas/AlbumMaterials.schema.json").read_text("utf-8"))
    jsonschema.validate(mats, mschema)
    assert mats["default_material"] is None and mats["passed"] is False
    legend = [m for m in mats["materials"] if m["source_kind"] == "legend_text"]
    assert [m["code"] for m in legend] == ["RAL 5023"]
    assert legend[0]["binding"] == {"kind": "unbound", "reason": "region_application_requires_review"}
    assert legend[0]["legend_symbol"]["kind"] == "filled_swatch"
    rows = {m["binding"].get("row"): m for m in mats["materials"] if m["source_kind"] == "schedule_finish_cell"}
    assert rows[3]["code"] == "RAL 9003" and rows[4]["status"] == "missing" and rows[4]["code"] is None
    # every RAL code in materials.json occurs in this PDF's own text (no other job)
    import pymupdf

    with pymupdf.open(synthetic) as doc:
        text = " ".join(p.get_text() for p in doc)
    assert all(m["code"] in text for m in mats["materials"] if m["code"])


def test_album_index_routes_and_must_match_source(tmp_path, synthetic):
    sha = hashlib.sha256(synthetic.read_bytes()).hexdigest()
    index = dict(schema="album-index/1", source=dict(sha256=sha), page_count=1, pages=[dict(
        pdf_page=1, printed_sheet="12", regions=[dict(region_id="p1-r9", bbox=[40, 40, 520, 200],
                                                      route="table_extraction",
                                                      reason="schedule_context_candidate_unverified")])])
    ipath = tmp_path / "album_index.json"
    ipath.write_text(json.dumps(index), "utf-8")
    manifest = S.export_schedules(synthetic, tmp_path / "out", album_index=ipath)
    assert manifest["pages"][0]["roi"] == [40, 40, 520, 200]
    assert manifest["pages"][0]["sheet"] == "12"
    index["source"]["sha256"] = "0" * 64
    ipath.write_text(json.dumps(index), "utf-8")
    with pytest.raises(ValueError, match="album_index_source_mismatch"):
        S.export_schedules(synthetic, tmp_path / "out2", album_index=ipath)
    assert not (tmp_path / "out2").exists()
    index["source"]["sha256"] = sha
    index["pages"][0]["regions"][0]["bbox"] = [40, float("nan"), 520, 200]
    ipath.write_text(json.dumps(index), "utf-8")
    with pytest.raises(ValueError):
        S.export_schedules(synthetic, tmp_path / "out3", album_index=ipath)
    assert not (tmp_path / "out3").exists()


def test_unrouted_page_is_accounted_not_dropped(tmp_path, synthetic):
    sha = hashlib.sha256(synthetic.read_bytes()).hexdigest()
    index = dict(schema="album-index/1", source=dict(sha256=sha), page_count=1,
                 pages=[dict(pdf_page=1, printed_sheet=None, regions=[])])
    ipath = tmp_path / "album_index.json"
    ipath.write_text(json.dumps(index), "utf-8")
    manifest = S.export_schedules(synthetic, tmp_path / "out", album_index=ipath)
    assert manifest["pages"] == [dict(pdf_page=1, sheet=None, route="not_routed", reason="no_table_region_in_index",
                                      roi=None, tables=[])]
    assert manifest["tables"] == []
    # legends are still scanned on every page
    mats = json.loads((tmp_path / "out/materials.json").read_text("utf-8"))
    assert any(m["code"] == "RAL 5023" for m in mats["materials"])


def _index_file(tmp_path, pdf, bbox, name="album_index.json"):
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    index = dict(schema="album-index/1", source=dict(sha256=sha), page_count=1, pages=[dict(
        pdf_page=1, printed_sheet=None, regions=[dict(region_id="p1-r1", bbox=bbox, route="table_extraction",
                                                      reason="schedule_context_candidate_unverified")])])
    path = tmp_path / name
    path.write_text(json.dumps(index), "utf-8")
    return path


def test_roi_that_cuts_a_table_keeps_the_whole_table(tmp_path, synthetic):
    """Regression (COD p5): the index text envelope ended inside the table; the table must stay whole."""
    manifest = S.export_schedules(synthetic, tmp_path / "out", album_index=_index_file(tmp_path, synthetic,
                                                                                       [40, 40, 200, 120]))
    assert [(t["n_rows"], t["n_cols"]) for t in manifest["tables"]] == [(5, 4)]
    assert manifest["pages"][0]["outside_roi"] == []


def test_table_outside_roi_is_reported_not_dropped(tmp_path, synthetic):
    manifest = S.export_schedules(synthetic, tmp_path / "out", album_index=_index_file(tmp_path, synthetic,
                                                                                       [600, 400, 800, 500]))
    assert manifest["tables"] == []
    assert {o["engine"] for o in manifest["pages"][0]["outside_roi"]} == {"primary", "secondary"}


def test_cropbox_offset_still_pairs_the_engines(tmp_path):
    """Regression (COD p5): pdfplumber coordinates start at its page origin; both engines must still pair."""
    pytest.importorskip("pdfplumber", reason="second table engine")
    import pymupdf

    src = _synthetic_pdf(tmp_path / "a.pdf")
    doc = pymupdf.open(src)
    doc[0].set_cropbox(pymupdf.Rect(14, 12, 830, 590))
    doc.save(tmp_path / "cropped.pdf")
    doc.close()
    manifest = S.export_schedules(tmp_path / "cropped.pdf", tmp_path / "out", pages=[1])
    assert [t["found_by"] for t in manifest["tables"]] == [["primary", "secondary"]]
    side = json.loads((tmp_path / "out/schedules/p1-t1.json").read_text("utf-8"))
    assert all(s["reason"] != "shape_mismatch" for s in side["suspect_cells"])


def test_rotated_page_gets_no_unaligned_second_engine(tmp_path):
    pytest.importorskip("pdfplumber", reason="second table engine")
    import pymupdf

    src = _synthetic_pdf(tmp_path / "a.pdf")
    doc = pymupdf.open(src)
    doc[0].set_rotation(90)
    doc.save(tmp_path / "rot.pdf")
    doc.close()
    manifest = S.export_schedules(tmp_path / "rot.pdf", tmp_path / "out", pages=[1])
    assert manifest["tables"]
    for t in manifest["tables"]:
        side = json.loads((tmp_path / "out/schedules" / f"{t['table_id']}.json").read_text("utf-8"))
        assert {s["reason"] for s in side["suspect_cells"]} == {"second_engine_coordinates_differ"}
        assert len(side["suspect_cells"]) == t["n_rows"] * t["n_cols"]


@pytest.mark.parametrize("pages", [[0], [2], [1, 1], [], [True]])
def test_bad_pages_fail_and_write_nothing(tmp_path, synthetic, pages):
    with pytest.raises(ValueError):
        S.export_schedules(synthetic, tmp_path / "out", pages=pages)
    assert not (tmp_path / "out").exists()


def test_output_must_be_new_and_not_an_input(tmp_path, synthetic):
    (tmp_path / "out").mkdir()
    with pytest.raises(FileExistsError):
        S.export_schedules(synthetic, tmp_path / "out", pages=[1])
    before = synthetic.read_bytes()
    code = subprocess.run([sys.executable, "-m", "dt_ai.album.schedules", str(synthetic), "--pages", "1",
                           "--output", str(synthetic)], capture_output=True, text=True).returncode
    assert code == 2 and synthetic.read_bytes() == before


def test_cli_fresh_process(tmp_path, synthetic):
    proc = subprocess.run([sys.executable, "-m", "dt_ai.album.schedules", str(synthetic), "--pages", "1",
                           "--output", str(tmp_path / "out")], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    summary = json.loads(proc.stdout.strip().splitlines()[-1])
    assert summary["passed"] is False and summary["tables"] == 1


def test_export_is_deterministic(tmp_path, synthetic):
    S.export_schedules(synthetic, tmp_path / "a", pages=[1])
    S.export_schedules(synthetic, tmp_path / "b", pages=[1])
    for f in sorted((tmp_path / "a").rglob("*")):
        if f.is_file():
            assert f.read_bytes() == (tmp_path / "b" / f.relative_to(tmp_path / "a")).read_bytes(), f.name
