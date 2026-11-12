"""Run the #1235 schedule/legend export on the frozen research corpus and score it against reference.json.

Pattern: n/a | new-case: corpus receipt runner for dt_ai.album.schedules (research tooling, not production).

uv run --extra pdf-review --with pdfplumber==0.11.10 python tools/research/pdf_album/run_schedules.py \
  --sources C:/x/pdf-album-research/t_5b23c219 \
  --index-root "G:/Мой диск/AGR-evidence/pdf-album/1233/t_3996e752-v002" \
  --evidence NEW_EVIDENCE_DIRECTORY --receipts NEW_RECEIPT_DIRECTORY

Sources are read only and hash-checked against results/<album>.json; the album index is the #1233 output for the
same hash. Scores: a reference row is found only when its key and its value are cells of ONE ``data`` row of a
table on the reference page (neighbour pages give no credit); cell recall counts key / value / exact description
cells; RAL recall counts reference codes extracted on the reference page. Precision is reported only as
"extracted codes on the reference page that are in the reference" because the references are samples, not
exhaustive lists. Timings are wall seconds of export_schedules in this process.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import time
from pathlib import Path

from dt_ai.album.schedules import export_schedules

HERE = Path(__file__).resolve().parent
ALBUMS = ("elv", "cod20207", "tec26")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(out: Path, page: int) -> list[tuple[str, int, list[dict[str, str]]]]:
    found = []
    for path in sorted((out / "schedules").glob(f"p{page}-t*.csv")):
        with path.open(encoding="utf-8", newline="") as fh:
            lines = list(csv.DictReader(fh))
        by_row = collections.defaultdict(list)
        for line in lines:
            by_row[int(line["row"])].append(line)
        found += [(path.stem, r, cells) for r, cells in sorted(by_row.items())]
    return found


def _score_rows(out: Path, refs: list[dict]) -> dict:
    samples, cells_ok, cells_all = [], 0, 0
    for ref in refs:
        best = None
        for tid, r, cells in _rows(out, ref["page"]):
            texts = [c["text"].replace("\n", " ") for c in cells]
            key_hit = any(t == ref["key"] or t.startswith(ref["key"] + " ") or ref["key"] in t.split("\n")
                          or ref["key"] in t for t in texts)
            if not key_hit:
                continue
            want = "area" if ref.get("unit") == "m2" else "quantity" if "quantity" in ref.get("unit", "") else None
            values = [c for c in cells if c["text"] == ref["value"]]
            value = next((c for c in values if c["value_kind"] == want), values[0] if values else None)
            desc = "description" in ref and any(t == ref["description"] for t in texts)
            n = 1 + (value is not None) + bool(desc)
            hit = dict(table_id=tid, row=r, row_type=cells[0]["row_type"], value_found=value is not None,
                       value_kind=None if value is None else value["value_kind"],
                       unit=None if value is None else value["unit"],
                       value_status=None if value is None else value["cell_status"], description_exact=desc,
                       cells_found=n)
            if best is None or n > best["cells_found"]:
                best = hit
        expected = 3 if ref.get("unit") == "m2" else 2  # ELV description is an exact cell; COD's is a narrative
        cells_all += expected
        cells_ok += min(expected, best["cells_found"]) if best else 0
        row_ok = bool(best and best["value_found"] and best["row_type"] == "data")
        samples.append(dict(reference=ref, found=row_ok, match=best))
    return dict(rows_correct=sum(s["found"] for s in samples), rows_denominator=len(refs), cells_correct=cells_ok,
                cells_denominator=cells_all, samples=samples)


def _score_materials(mats: dict, refs: list[dict]) -> dict:
    pages = {r["page"] for r in refs}
    on_pages = {(m["page"], m["code"]) for m in mats["materials"] if m["code"] and m["page"] in pages}
    ref_keys = {(r["page"], r["code"]) for r in refs}
    hits = [dict(reference=r, found=(r["page"], r["code"]) in on_pages) for r in refs]
    return dict(codes_correct=sum(h["found"] for h in hits), codes_denominator=len(refs),
                extracted_on_reference_pages=len(on_pages),
                extracted_in_reference=len(on_pages & ref_keys), samples=hits)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", type=Path, required=True)
    ap.add_argument("--index-root", type=Path, required=True)
    ap.add_argument("--evidence", type=Path, required=True)
    ap.add_argument("--receipts", type=Path, required=True)
    args = ap.parse_args()
    for path in (args.evidence, args.receipts):
        if path.exists():
            raise SystemExit(f"must be new: {path}")
    reference = json.loads((HERE / "reference.json").read_text("utf-8"))
    args.receipts.mkdir(parents=True)
    for album in ALBUMS:
        frozen = json.loads((HERE / "results" / f"{album}.json").read_text("utf-8"))
        pdf = args.sources / f"{album}.pdf"
        index = args.index_root / album / "first" / "album_index.json"
        if _sha(pdf) != frozen["sha256"]:
            raise SystemExit(f"source hash mismatch: {pdf}")
        out = args.evidence / album
        t0 = time.perf_counter()
        manifest = export_schedules(pdf, out, album_index=index)
        seconds = round(time.perf_counter() - t0, 3)
        if _sha(pdf) != frozen["sha256"]:
            raise SystemExit(f"source changed: {pdf}")
        mats = json.loads((out / "materials.json").read_text("utf-8"))
        reasons = collections.Counter()
        row_types = collections.Counter()
        for t in manifest["tables"]:
            side = json.loads((out / "schedules" / f"{t['table_id']}.json").read_text("utf-8"))
            reasons.update(s["reason"] for s in side["suspect_cells"])
            row_types.update(r["row_type"] for r in side["rows"])
        ref = reference[album]
        receipt = dict(
            album=album, source_sha256=frozen["sha256"], album_index_sha256=_sha(index), seconds=seconds,
            engines=manifest["engines"], secondary_status=manifest["secondary_status"],
            pages_routed=[p["pdf_page"] for p in manifest["pages"] if p["route"] == "table_extraction"],
            pages_not_routed=len([p for p in manifest["pages"] if p["route"] != "table_extraction"]),
            pages_accounted=len(manifest["pages"]), summary=manifest["summary"],
            suspect_reasons=dict(sorted(reasons.items())), row_types=dict(sorted(row_types.items())),
            materials=mats["summary"], tables=manifest["tables"],
            rows=_score_rows(out, ref["rows"]), ral=_score_materials(mats, ref["materials"]),
            output_sha256={p.relative_to(out).as_posix(): _sha(p) for p in sorted(out.rglob("*")) if p.is_file()},
            passed=False)
        (args.receipts / f"{album}.json").write_bytes(
            (json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        print(album, seconds, manifest["summary"], receipt["rows"]["rows_correct"], "/",
              receipt["rows"]["rows_denominator"], receipt["ral"]["codes_correct"], "/",
              receipt["ral"]["codes_denominator"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
