# Production intake evidence — issue #1233

## Reproduce

```bash
uv run --extra pdf-review python -m dt_ai.album.intake INPUT.pdf --output NEW_DIRECTORY --page-budget-s 10
uv run --extra pdf-review python tools/research/pdf_album/run_intake.py --sources C:/x/pdf-album-research/t_5b23c219 --evidence NEW_EVIDENCE_DIRECTORY --receipts NEW_RECEIPT_DIRECTORY
```

`C:/x/pdf-album/` named by the issue does not exist on this host. The copies from
research #1228 were used read-only instead; all three hashes match the report.
`run_intake.py` checks those hashes before each album, runs twice, verifies physical
page accounting, compares canonical JSON bytes, and seals/readbacks every member.
It aborts on reused destinations. A source may be indexed repeatedly into distinct
new directories; the same destination cannot be reused, including after failure.

The committed JSONs are compact per-page receipts. Full **album_index.json** and
**manifest.json**, together with frozen sources and repeat outputs, are on the
mounted Drive (not git, not LFS):

`G:/Мой диск/AGR-evidence/pdf-album/1233/t_3996e752-v002/{elv,cod20207,tec26}/{first,repeat}/`

`SHA256SUMS.txt` SHA-256:
`77ae124f9107615f3e6913ad6b2c3595c34006a77b9a768154b6b2baa2d5ea9e`.
Every sealed member was read back and rehashed. Cloud-sync completion was not
queried. The earlier v001 is retained; v002 adds the schedule-context ROI fix.

## Measured result

| Album | Physical pages accounted | Frozen kind agreement | First / repeat wall seconds |
|---|---:|---:|---:|
| ELV | 42/42 | 42/42 | 31.351 / 28.700 |
| COD20207 | 5/5 | 5/5 | 2.237 / 2.926 |
| TEC26 | 6/6 | 6/6 | 6.216 / 4.410 |
| Total | 53/53 | 53/53 | See per-album measurements |

Both canonical JSON files were byte-identical across the two runs of each album.
All six first-run files validate against the committed standalone schemas.
Kinds use the same first-700-character heuristic as frozen research results;
`3D view` is represented by the requested enum `3D`. These references are explicitly
**unapproved heuristic candidates**, not independent semantic ground truth.

| Frozen label | Correct / predicted / reference | Precision | Recall |
|---|---:|---:|---:|
| plan | 2 / 2 / 2 | 1.0 | 1.0 |
| facade | 12 / 12 / 12 | 1.0 | 1.0 |
| section | 0 / 0 / 0 | unknown | unknown |
| schedule | 2 / 2 / 2 | 1.0 | 1.0 |
| 3D | 13 / 13 / 13 | 1.0 | 1.0 |
| unknown | 24 / 24 / 24 | 1.0 | 1.0 |

This is **label agreement precision/recall**, NOT extraction or modelling accuracy.
For example, the frozen COD p5 kind is unknown despite its specification content;
region routing independently detects its schedule context. No frozen label was
edited to improve agreement. No dimension/material/row precision is claimed.

## Coverage and limits

- 12 pages explicitly partial: ELV p18/19/21/25/26/28/31/32/33/34/35 and TEC26 p2.
  At 20,000 display operations (including equality), vector inspection is cut;
  searchable text remains and the entire uninspected display list has a counted
  OCR/vision fallback ROI. No mandatory page disappears. This conservative cap
  can route useful dense facades to fallback as well as irrelevant maps.
- Each page worker has a 10 s wall deadline including process startup; a timeout
  returns a retained partial record with `page_budget_exhausted`. Worker termination
  and joining have OS cleanup overhead. No geometry/table parsing is done in the
  parent. Dense-map line-segment extraction is deliberately never started.
- COD p1–4 each contain independent searchable-text, vector, outlined-label
  candidate and raster ROIs. Filled glyph-sized paths are conservative outline
  candidates, not certified text recognition. Spatial buckets can overlap.
- Schedule routing includes a conservative text envelope, not only the title;
  exact table/view boundaries remain for the follow-up extractor. Table, reader,
  OCR and vision are route proposals here, not executed extraction/approval.
- Only explicitly labelled printed-sheet numbers are parsed; standalone footer
  numbers are left null. Original title/text strings are retained, never reconciled.
- Units remain null and scale unknown. No model geometry or material default is
  inferred. All manifests have `passed=false` and all four approval gates open.
- Canonical artifacts exclude volatile elapsed values; manifest explains this and
  records the configured timing policy. Observed album wall timings are in these
  benchmark receipts. Deadline outcomes can vary under load; no guarantee of an
  identical completed/timeout outcome on arbitrarily overloaded machines is made.

## Test-first receipts

- `41ed5c7c`: accounting regression RED, 1 failed (missing production module).
- Initial implementation: same regression GREEN, 1 passed.
- Dense-cutoff/schema slice: RED 2 failed / 1 passed; GREEN 3 passed.
- Hostile mixed-page table-ROI witness: RED 1 failed (heading ROI excludes rows);
  context-envelope repair passes the combined text/vector/outline/raster test.
- Final affected command includes `tests/test_album_intake.py`,
  `tests/test_album_pdf_reader.py`, `tests/test_album_below_line.py`, and
  `tools/research/pdf_album/test_probe.py`: **164 passed** before full suite.
