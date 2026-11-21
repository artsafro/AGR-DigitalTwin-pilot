# Album schedule/legend results (#1235)

Produced by `src/dt_ai/album/schedules.py` through `run_schedules.py` (this folder's parent). Not acceptance:
`passed` is false everywhere; row types are `heuristic_unapproved`, legend items stay `unbound`.

```bash
uv run --extra pdf-review --with pdfplumber==0.11.10 python tools/research/pdf_album/run_schedules.py \
  --sources C:/x/pdf-album-research/t_5b23c219 \
  --index-root "G:/Мой диск/AGR-evidence/pdf-album/1233/t_3996e752-v002" \
  --evidence NEW_DIR --receipts NEW_DIR
```

`C:/x/pdf-album/` named by the issue does not exist on this host; the #1228 copies were used read only (hashes
checked against `results/*.json` before and after each album). Album index = #1233 v002 output of the same hash.

Committed here: `receipts/*.json` (scores, timings, suspect reasons, row types, SHA-256 of every output file),
full outputs of COD20207 and TEC26, and for ELV `materials.json`, `schedules.json` and the reference table
`schedules/p27-t1.{csv,json}`. Full outputs of all three albums (two identical runs, v002 = v003 byte for byte):
`G:/Мой диск/AGR-evidence/pdf-album/1235/t_759bcfaa-v001/` + `SHA256SUMS.txt` (59 members, read back with
`sha256sum -c`; SHA-256 of `SHA256SUMS.txt`: `b5cd6bb93439687c0ba17facea8071be685bf20fa2b6ceb87e9acf835221a628`).
Review round 1 rerun (materials entries now carry `cell_status`, `text_alt`, `codes_by_engine`; summary
`suspect`, `single_engine`): `G:/Мой диск/AGR-evidence/pdf-album/1235/t_759bcfaa-v002/` + `SHA256SUMS.txt`
(56 members, `sha256sum -c` OK; SHA-256 of `SHA256SUMS.txt`:
`0843f2eeacf562361597d82faa60932ab5f2c65c31ef2c9ff145b22dad50798b`). Schedules/CSV unchanged byte for byte;
only `materials.json` and receipts changed. The corpus has no schedule-derived material entries (ELV 30 legend
lines, COD/TEC26 0), so the suspect/single_engine counts are 0; timings below are from this rerun.

| Album | Pages routed / accounted | Tables | Cells | Suspect cells | Rows found / ref | Cells found / ref | RAL found / ref | Ref-page codes in ref / extracted | Seconds |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ELV | 6 (3, 4, 5, 27, 29, 30) / 42 | 24 | 839 | 69 | 3/3 | 9/9 | 3/3 | 3/4 | 8.347 |
| COD20207 | 1 (5) / 5 | 1 | 32 | 0 | 1/1 | 2/2 | 0/3 | 0/0 | 0.153 |
| TEC26 | 0 / 6 | 0 | 0 | 0 | n/a (0 ref) | n/a | n/a | n/a | 0.164 |

- ELV suspect cells: 32 `engines_disagree` (pdfplumber drops spaces in title-block text, e.g. `Торговый Центр`
  vs `ТорговыйЦентр`), 37 `primary_engine_missed_table` (pdfplumber-only tables on p4/p5/p30). Every one is listed
  in its sidecar with both strings; none is picked silently. The three reference rows of p27 are `data` rows,
  value column `area` / `m2`, both engines `agree`.
- ELV p18 extracts RAL 1001 / 7021 / 5024 (reference) and RAL 7040 (not in the reference sample); precision is
  not claimed because the reference lists samples, not every legend line. 30 legend entries on p7/18/19/20/41,
  all `unbound region_application_requires_review`; same code with different labels is linked in `conflicts`.
- COD p5: the #1233 text-envelope ROI ended inside the specification (x 742 < table x1 822); tables are now
  detected on the routed page and kept when they touch the ROI (regression test). pdfplumber coordinates
  are shifted by the page cropbox (-14.4, -12.0) so both engines pair: 32/32 cells agree. `LACE RGBW Custom`
  quantity `1` is in the `Кол-во` column (`quantity`, unit empty: never guessed); the cell text's
  `5 505 метров` / `16x15 мм` are listed as `length` measures of the row - quantity 1 is not 1 m.
- COD RAL 0/3: the p1 facade legend is outlined text (no text layer, #1228); OCR/vision is #1228's 4th
  follow-up, not this card. TEC26 is a visualization booklet: no schedule regions, empty denominator.
- Timings: wall seconds of `export_schedules` in one process (both engines, all routed pages, legend scan of all
  pages), measured while other work ran on this PC.
