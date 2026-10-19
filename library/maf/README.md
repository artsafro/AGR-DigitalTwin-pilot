# MAF library catalogue (issue #183)

Audit of the user's single 3ds Max MAF library scene, turned into one `.max` + one FBX + one preview PNG per MAF.
Binaries stay **outside the repo** (`C:/x/t_3e6ff1b3/library/{max,fbx,preview}`, with versioned
preview repairs in `preview-v002`, and contact sheet
`C:/x/t_3e6ff1b3/library/contact_sheet-v002.png`); PNG/FBX/MAX are Git LFS types and the LFS budget is exhausted.
This folder holds only text: `catalogue.json` (every entry, paths to its files), `catalogue.md` (table),
`contact_sheet.html` (local image grid linking external previews/assets), and `audit.json` (verification evidence).
Status: technical audit only, not identification (T-MAF-1) and not user acceptance.

## Inputs (read only, worked on copies)

| Input | sha256 before = after |
|---|---|
| `МАФы_Union_ALLin.max` (319.5 MB, 3ds Max scene, metres) | `beeef9d418e81045bbc4933cc74077acd3d9f7a265319ceb9bf0ff0253050109` |
| `МАФЫ_НПМ.blend` (54.8 MB, NPM set, Blender 5.1.2) | `52ef2222b13a7cb4f4c3b728ee27e827cfaeb49499f3e7d7d03a5f7364d661dd` |
| `maf_spec_vedomost_3.xlsx` (MAF specification sheet, copy) | `9b4302c16501636fe4a522f54ff16091244ba0b6f20378763b2706d51f1eb2b3` |

## How it was built

```bash
# pass A: inventory + mesh elements of every object (headless 3ds Max 2026, copy of the scene)
AGR_MAF_SCENE=C:/x/t_3e6ff1b3/src.max AGR_MAF_OUT=C:/x/t_3e6ff1b3/elements.json \
  python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --file tools/library/maf_max_elements_job.py
# plan: one entry per spatial cluster of elements (gap 0.5 m) -> MAF_0001..
uv run python tools/library/maf_catalogue.py plan --elements elements.json --out plan.json --gap 0.5
# pass B: per entry .max (saveNodes) + FBX (selected) + Scanline preview; resumable (skips ok rows)
AGR_MAF_PLAN=plan.json AGR_MAF_LIB=C:/x/t_3e6ff1b3/library \
  python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --file tools/library/maf_max_build_job.py --timeout 3000
# catalogue: + NPM .blend matching, specification dimension candidates, duplicates, overlaps, contact sheet
uv run --with openpyxl python tools/library/maf_catalogue.py catalogue --plan plan.json --built library/built.jsonl \
  --blend blend_inventory.json --spec maf_spec_vedomost_3.xlsx --out-json catalogue.json --out-md catalogue.md \
  --contact-sheet library/contact_sheet.png
```

Rules used: an object whose mesh elements form several clusters farther apart than 0.5 m (Chebyshev gap between
element boxes) is a cluster of several MAF and is split; objects ≤ 12 tris and < 5 mm tall are helper planes;
text/shapes/dummies are non-geometry. Duplicates = equal tris and dims within 1 cm (X/Y swap allowed). NPM matching:
name (prefix `C_`/`crp_` and `.NNN` removed) plus dims within 10 cm, else dims only. Specification candidates are
dimension-only (tolerance 10 cm, user grilling Q8) — candidates, not identification.

`element_first_faces` (needed to rebuild a split) is kept in `plan.json` outside the repo and dropped here.

## Verification and interpretation

- `audit.json` records original-before/original-after/copy SHA-256 equality, export counts, timing and
  independent Blender 5.1.2 FBX readback. `fbx_readback_dims_m` measures **referenced** vertices; three
  source meshes contain loose vertices which enlarge all-vertex bounds but not their visible geometry.
- 927/931 FBX triangle counts match exactly. Four imports differ by 1–2 triangles (7 triangles total);
  the cause is not established by the audit and is not silently counted as a pass. All 931 referenced
  dimensions agree within 5 mm. Full per-object UV/material/topology/transform observations remain
  outside Git at the `details_path` in `audit.json`.
- The source library is not a ready NPM/VPM delivery: readback includes 14 meshes without UV layers,
  42 without material slots, non-triangle faces and degenerate triangles. This card inventories rather
  than repairs those source defects. No texture, material appearance or publication approval is claimed.
- Duplicate groups are **candidates** (triangle count + dimensions), not a topology identity proof.
  NPM name/dimension matches are likewise candidates, not manufacturer/article identification.
  Of the 289 meshes in the actual `НПМ` collection, 190 have name+dimension matches, 27 dimension-only
  candidates and 72 no candidate. The older `npm_*` catalogue totals include all 368 Blender meshes;
  `audit.json` separates the collection-specific counts. Sixteen NPM rows have lower-triangle candidates;
  no new light versions were generated.
- `preview_style=neutral-shape-only` explicitly marks repaired legacy-material previews. The original
  material-bearing Max/FBX files and original PNGs are retained. These previews establish shape only.

```bash
# Fresh-process independent FBX readback (AGR_MAF_READBACK must be a NEW report path)
AGR_MAF_LIB=C:/x/t_3e6ff1b3/library AGR_MAF_READBACK=C:/x/t_3e6ff1b3/fbx_readback_v004.json \
  "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --background --factory-startup \
  --python tools/library/maf_blender_readback.py
# Repair only confirmed blank IDs; refuses to overwrite preview-v002 / its manifest
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max \
  --file tools/library/maf_preview_repair_job.py --timeout 4400 --wait 3600
# Real-output regression (opt-in; normal CI skips absent external assets)
AGR_MAF_VERIFY_PLAN=C:/x/t_3e6ff1b3/plan.json \
AGR_MAF_VERIFY_BUILT=C:/x/t_3e6ff1b3/library/built-v002.jsonl \
  uv run pytest -q tests/test_maf_library_artifacts.py
```

Keep pytest `--basetemp` in a **child directory**, e.g. `C:/x/t_3e6ff1b3/full-v002`.
Never use the evidence root as basetemp: pytest recursively clears that directory.
Shared Max lock stale-age workaround: use a wrapper timeout at least as long as the current holder's;
see pilot issue #223. No lock was bypassed or manually removed by this continuation.

## Reproduce the committed outputs (#227)

Tracked tools rebuild `catalogue.json`, `catalogue.md`, `contact_sheet.html`, `audit.json` and the
per-entry `fbx_readback_*` fields from the inputs below. `<EVIDENCE>` is the issue #208 evidence root
(`C:/x/t_3e6ff1b3`). `<LIB>` is the pass-B library directory (`<EVIDENCE>/library` in #208; the #227
reproduction reused it and did not repeat pass B). `<OUT>` is a **new** directory (for example `C:/x/maf-audit-repro`). Every command
refuses to overwrite an existing output file unless `--overwrite` is passed.

Absent QA is recorded as `not measured`. When source integrity is not measured (no `--hash-before`
manifest supplied), `source_hashes` is recorded as `{"status": "not measured"}` rather than an empty
list (which is reserved for an explicitly empty measured manifest); source preservation is never inferred
when not measured. `preview_blank` stays null unless a preview-check report is supplied; it is never
written as false without that report. A readback row with `error` is not a pass. A readback row whose
dimensions are not exactly three finite numbers, or whose triangle count is not a non-negative integer,
is recorded as `invalid` and is never counted as a pass. Preview repair `blank_after` is a number only
when every override id was checked; otherwise it stays `not measured` and the unchecked override ids
are listed.

Merge rule for versioned preview manifests: rows are keyed by `id`. The base manifest defines the entry
set and order. Each `--override` manifest is applied in the order given; an override row updates the
matching base row field by field (`{**row, **override}`), and a later manifest wins over an earlier one.
An override `id` that is not in the base is an error — an override never creates an entry.

```bash
# 1. Blender inventory of the NPM .blend copy (read-only; does not save the .blend)
AGR_MAF_BLEND_INVENTORY=<OUT>/blend_inventory.json \
  blender --background <EVIDENCE>/src.blend --factory-startup \
  --python tools/library/maf_blender_inventory.py

# 2. plan (unchanged)
uv run python tools/library/maf_catalogue.py plan \
  --elements <EVIDENCE>/elements.json --out <OUT>/plan.json --gap 0.5

# 3. pass B (unchanged): per entry .max + FBX + Scanline preview
AGR_MAF_PLAN=<OUT>/plan.json AGR_MAF_LIB=<LIB> \
  python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max \
  --file tools/library/maf_max_build_job.py --timeout 3000

# 4. merge the base build manifest with versioned preview overrides
uv run python tools/library/maf_audit.py merge-manifests \
  --base <LIB>/built.jsonl \
  --override <LIB>/preview-v002.jsonl \
  --out <OUT>/merged.jsonl \
  --provenance-out <OUT>/merge_provenance.json

# 5. catalogue from the merged manifest
uv run --with openpyxl python tools/library/maf_catalogue.py catalogue \
  --plan <OUT>/plan.json --built <OUT>/merged.jsonl \
  --blend <OUT>/blend_inventory.json --spec <EVIDENCE>/maf_spec_vedomost_3.xlsx \
  --out-json <OUT>/catalogue_raw.json --out-md <OUT>/catalogue.md \
  --contact-sheet <OUT>/contact_sheet.png

# 6. blank-preview check. Omit it and preview_blank stays null.
uv run python tools/library/maf_audit.py preview-check \
  --catalogue <OUT>/catalogue_raw.json --out <OUT>/preview_check.json

# 7. independent FBX readback (existing script). A missing report stays "not measured".
AGR_MAF_LIB=<LIB> AGR_MAF_READBACK=<OUT>/fbx_readback.json \
  blender --background --factory-startup --python tools/library/maf_blender_readback.py

# 8. finalize catalogue JSON, contact_sheet.html and fbx_readback_* fields
uv run python tools/library/maf_audit.py finalize \
  --catalogue <OUT>/catalogue_raw.json \
  --readback <OUT>/fbx_readback.json \
  --preview-check <OUT>/preview_check.json \
  --contact-sheet-png <OUT>/contact_sheet.png \
  --out-json <OUT>/catalogue.json \
  --out-html <OUT>/contact_sheet.html

# 9. audit.json. Omit any QA flag to record that input as "not measured".
#    Omit --hash-before to record source_hashes as {"status": "not measured"}.
#    --built is the BASE pass-B manifest (build timing of pass B, not of the preview repair).
#    --blank-before is a JSON list of ids. --copy is matched to hash_before paths by suffix.
uv run python tools/library/maf_audit.py audit \
  --plan <OUT>/plan.json --built <LIB>/built.jsonl --library <LIB> \
  --readback <OUT>/fbx_readback.json --blend <OUT>/blend_inventory.json \
  --hash-before <EVIDENCE>/hash_before.txt \
  --copy <EVIDENCE>/src.max --copy <EVIDENCE>/src.blend \
  --override <LIB>/preview-v002.jsonl \
  --blank-before <OUT>/blank_before.json \
  --preview-check <OUT>/preview_check.json \
  --native-probe <EVIDENCE>/native_probe.json \
  --preview-repair-run <EVIDENCE>/preview_repair_run.json \
  --contact-sheet-png <OUT>/contact_sheet.png \
  --npm-matches-out <OUT>/npm_matches.json \
  --out <OUT>/audit.json

# 10. compare against the committed snapshot
uv run python tools/library/maf_audit.py compare \
  --old library/maf/catalogue.json --new <OUT>/catalogue.json \
  --out <OUT>/catalogue_diff.json
uv run python tools/library/maf_audit.py compare \
  --old library/maf/audit.json --new <OUT>/audit.json \
  --out <OUT>/audit_diff.json
```
