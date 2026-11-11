# Executed commands — #1228 / t_5b23c219

Run from `C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/.worktrees/t_5b23c219`.
Bash shell, native Windows paths. These are the commands actually executed, not a production
CLI. Outputs are versioned: reruns must use NEW names/directories; do not overwrite sealed evidence.
Package versions observed are in the report. All original PDF paths and hashes are in `*-inventory.json`.

## Setup / source discovery

```bash
git fetch origin
git log -1 --format='%h %s' origin/main
# 35e531f9 at intake; no pdf-album-pipeline report/prototypes on origin/main
uv sync
uv run --extra pdf-review --with ezdxf --with pdfplumber python -c "import pymupdf,ezdxf,pdfplumber; print('PyMuPDF',pymupdf.VersionBind,'ezdxf',ezdxf.__version__,'pdfplumber',pdfplumber.__version__)"
uv run --extra pdf-review python tools/research/pdf_album/discover.py
```

Discovery stdout was redirected to the profile's card-specific scratch log. It created exactly
`elv.pdf`, `cod20207.pdf`, `tec26.pdf` and inventories under
`C:/x/pdf-album-research/t_5b23c219/`. A supplementary `22E56.pdf` AS.02 source was copied with
`shutil.copy2` to `psu275-sheet1.pdf`; this is not counted as a fourth full album.

## A — existing reader, all pages

```bash
for spec in 'elv 42' 'cod20207 5' 'tec26 6'; do
  set -- $spec
  uv run --extra pdf-review python tools/research/pdf_album/probe.py \
    --pdf C:/x/pdf-album-research/t_5b23c219/$1.pdf \
    --out C:/x/pdf-album-research/t_5b23c219/$1-A-all-v001 \
    --route A --pages $(seq 1 $2)
done
```

The same runner was first exercised on ELV p18/p27, COD p1/p5 and TEC26 p1/p3 with `*-A-v001`
outputs. The report uses the complete `*-A-all-v001` timing/recall receipts, not a mixture.

## B — headless AutoCAD 2025, one process at a time

```bash
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py acad --ping --wait 0 --timeout 60 --max-chars 1800
```

ELV p18 initially used `import_elv.scr` and `pdfimport-elv-v001.json`: PDFIMPORT succeeded,
`-SAVEAS` failed despite wrapper exit 0. That script was corrected to `SAVEAS` and executed:

```bash
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py acad \
  --file tools/research/pdf_album/import_elv.scr --card t_5b23c219 \
  --wait 30 --timeout 180 \
  --out C:/x/pdf-album-research/t_5b23c219/pdfimport-elv-v002.json --max-chars 2700
```

The exact successful SCR is archived as `elv-p18-import-v002.scr` in evidence, not installed as
an overwrite-prone fixed-output command. It writes `elv-p18-import-v002.dwg/.dxf`.
The next three imports used `acad_script.py` with these exact argument rows:

| PDF | Page | `--out` basename | `--script` basename | wrapper `--out` log |
|---|---:|---|---|---|
| cod20207.pdf | 5 | cod20207-p5-v001 | cod20207-p5-v001.scr | pdfimport-cod-v001.json |
| tec26.pdf | 3 | tec26-p3-v001 | tec26-p3-v001.scr | pdfimport-tec26-v001.json |
| cod20207.pdf | 1 | cod20207-p1-v001 | cod20207-p1-v001.scr | pdfimport-cod-p1-v001.json |

Every path in that table is under `C:/x/pdf-album-research/t_5b23c219/`. Command form actually run:

```bash
uv run --extra pdf-review python tools/research/pdf_album/acad_script.py \
  --pdf C:/x/pdf-album-research/t_5b23c219/cod20207.pdf --page 5 \
  --out C:/x/pdf-album-research/t_5b23c219/cod20207-p5-v001 \
  --script C:/x/pdf-album-research/t_5b23c219/cod20207-p5-v001.scr
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py acad \
  --file C:/x/pdf-album-research/t_5b23c219/cod20207-p5-v001.scr \
  --card t_5b23c219 --wait 30 --timeout 180 \
  --out C:/x/pdf-album-research/t_5b23c219/pdfimport-cod-v001.json --max-chars 1600
```

DXF readback ran `free_dxf.inspect_dxf` on each generated DXF and wrote
`elv-B-inspected.json`, `cod20207-B-inspected.json`, `cod20207-B1-inspected.json`,
`tec26-B-inspected.json`; these retain all MTEXT strings/coordinates, entity counts, layers,
units and extents. Source-to-DXF paper-coordinate consistency was measured by comparing the
X-distance between ELV p18's two `5300` label positions in A and B (ratio 72.0001765).

## B2 — free conversion comparator

```bash
for pair in 'elv 18' 'cod20207 5' 'tec26 3'; do
  set -- $pair
  uv run --extra pdf-review python tools/research/pdf_album/free_dxf.py \
    --pdf C:/x/pdf-album-research/t_5b23c219/$1.pdf --page $2 \
    --out C:/x/pdf-album-research/t_5b23c219/$1-B2-v001
done
```

## C — two table extractors, all pages

```bash
for spec in 'elv 42' 'cod20207 5' 'tec26 6'; do
  set -- $spec
  uv run --extra pdf-review --with pdfplumber python tools/research/pdf_album/probe.py \
    --pdf C:/x/pdf-album-research/t_5b23c219/$1.pdf \
    --out C:/x/pdf-album-research/t_5b23c219/$1-C-all-v001 \
    --route C --pages $(seq 1 $2)
done
```

Initial paired `*-C-v001` runs used the same page sets as initial A.

## D — local OCR on renders, all pages

```bash
for spec in 'elv 42' 'cod20207 5' 'tec26 6'; do
  set -- $spec
  uv run --extra pdf-review --with rapidocr --with onnxruntime \
    python tools/research/pdf_album/probe.py \
    --pdf C:/x/pdf-album-research/t_5b23c219/$1.pdf \
    --out C:/x/pdf-album-research/t_5b23c219/$1-D-all-v001 \
    --route D --pages $(seq 1 $2)
done
uv run --extra pdf-review --with rapidocr --with onnxruntime \
  python tools/research/pdf_album/probe.py \
  --pdf C:/x/pdf-album-research/t_5b23c219/psu275-sheet1.pdf \
  --out C:/x/pdf-album-research/t_5b23c219/psu275-D-v001 --route D --pages 1
```

Initial paired `*-D-v001` runs used the same page sets as initial A/C.
Native vision was invoked with `vision_analyze` on the rendered PNG paths listed in
`vision-observations.json`, including the recorded PSU275 crop. These are real visual observations,
not outputs synthesized to imitate a metered vision API. Render generation used:
`pymupdf.open(pdf)[page-1].get_pixmap(dpi=110).save(png)`; PSU275 used 80 dpi.
OCR independently renders at 150 dpi; it does not consume these 110/80-dpi PNGs.

## Scoring, tests and seal

```bash
uv run pytest -q -p no:cacheprovider tools/research/pdf_album/test_probe.py --basetemp=C:/x/t_5b23c219-red
# 18 failed before probe.py existed; tests-first commit 3402bbb1
uv run pytest -q -p no:cacheprovider tools/research/pdf_album/test_probe.py --basetemp=C:/x/t_5b23c219-score-red
# 1 failed, 30 passed: RAL code after comma
uv run pytest -q -p no:cacheprovider tools/research/pdf_album/test_probe.py --basetemp=C:/x/t_5b23c219-score-green
# 31 passed after scorer boundary fix; additional fresh-process probes added subsequently
uv run python tools/research/pdf_album/summarize.py \
  --root C:/x/pdf-album-research/t_5b23c219 --out tools/research/pdf_album/results
```

Earlier generated summary directories were moved to `summary-v001` / `summary-v002` under the
external research root, never silently overwritten. The final summary adds the candidate sheet
index; raw extraction receipts were not rerun or edited. `results/` is the final generation.
Final tests/full-suite receipts are in the PR; the full suite always uses `suite_slot.py`.

```bash
uv run python tools/research/pdf_album/seal_evidence.py \
  --root C:/x/pdf-album-research/t_5b23c219 \
  --dest 'G:/Мой диск/AGR-evidence/pdf-album-research/t_5b23c219-v001' \
  --receipt tools/research/pdf_album/evidence.json
```

The seal verifies all discovered original/copy hashes, copies to a fresh directory, reads back
EVERY copied member and writes `SHA256SUMS.txt`. The committed receipt names its digest.
Failed HTTP fetches (403/404) are not interpreted as successful documentation; raw upstream
page.rst / RapidOCR README / pdfplumber README / ezdxf license downloads returned HTTP 200.
