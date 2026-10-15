# Flora library audit (#189)

Standalone, card-scoped experiment. Production code and standards are untouched.

**Current status: native v003 exports complete; corrected v004 verification pending.**
All 136 FBX files exist. The v003 measurement wrongly applied node.transform to
already-world-space snapshot vertices; six readbacks disagreed and the independent
bbox probe exposed the measurement bug. `tools/max_flora_verify.py` probes the
coordinate convention, re-extracts expected signatures and creates new v004 SVG
previews, then re-reads the SAME unchanged FBX files. No binary is overwritten.
`verify_archive.py` accepts only full v004 receipts; `--partial` never means pass.

## Inputs and safety

Use only the two hash-verified copies under `C:/x/t_366e8d9d/`. Original Desktop
scenes are **never** loaded into Max. `sources-verified.json` is the pre-copy hash
manifest. Do not run pytest with the card root as its destructive basetemp: use a
child such as `C:/x/t_366e8d9d/pytest-probes` so inputs/outputs survive.

`tools/max_flora_archive.py` creates `out/assets-v003` and resumes existing
**hash-verified per-row receipts**, never replacing binary outputs. Interrupted
unreceipted files cause a fail-closed error (use a new version, do not delete or
pretend they are verified). A cancelled wrapper waiting for the shared lock must be
confirmed stopped before another wrapper is submitted. Never remove another
card's lock or start Max directly.

## Reproduce

From this worktree, with Max 2026 installed and the specified copied inputs:

```bash
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --ping --card t_366e8d9d
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --file tools/max_flora_inventory.py --card t_366e8d9d --out C:/x/t_366e8d9d/inspect-detailed-batch.json
python experiments/flora-library-audit/catalogue.py --output experiments/flora-library-audit/catalogue.json
FLORA_JOB_SECONDS=3900 python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --file tools/max_flora_archive.py --card t_366e8d9d --timeout 4400 --out C:/x/t_366e8d9d/export-fbx-batch-v003.json
# Repeat the SAME archive command to skip hash-verified finished exports.
FLORA_JOB_SECONDS=1200 python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --file tools/max_flora_verify.py --card t_366e8d9d --wait 3600 --timeout 4400 --out C:/x/t_366e8d9d/verify-fbx-batch-v004.json
# Repeat the SAME verification command to skip hash-verified v004 rows/readbacks.
python experiments/flora-library-audit/catalogue.py --output experiments/flora-library-audit/catalogue.json
python experiments/flora-library-audit/report_findings.py
python experiments/flora-library-audit/verify_archive.py
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q experiments/flora-library-audit/test_catalogue.py -p no:cacheprovider --basetemp=C:/x/t_366e8d9d/pytest-probes
```

Long native calls should run through the terminal's tracked background mode; poll
that existing process instead of submitting duplicates after a gateway timeout.
All `dcc_batch` calls retain the shared one-batch-session lock.

## Interpretation

- `catalogue.json`: every Text/TextPlus, candidate mesh handles, raw labels,
  dimensions, triangles, material/bitmap references, proposed budgets and external
  asset/preview paths. Handles are inventory-local, not persistent asset IDs;
  isolated exports resolve unique source names. `id` is the catalogue entry key.
- `verification.json` (absent until a complete native run): source hashes after the native audit, per-asset file and
  mesh/UV/material-ID hashes, native readback equality and timings.
- MAX/FBX assets, SVG previews, detailed inventories and complete native logs stay
  outside Git. SVG previews are **untextured XZ wireframes**, not plant appearance
  or material approval. Missing bitmap references are reported, not repathed.
- `LP`, `HP`, `LP -> HP` stay intact. NPM/VPM candidates are an audit interpretation,
  not a delivery check. The library's front-facing grid is paired in XZ; the
  project's left-hand multiline schedule is paired by Y row to both high/low
  meshes. Multi-species rows and co-located alternatives remain ambiguous.
- Library tree/bush grouping follows the two display heading regions; bush includes
  ornamental perennials. It is not a botanical classification. Hedge has no
  labelled samples: no budget is invented.
- `Box*` meshes are reported as unverified display envelopes, not assumed UCX or
  plants. Size references, planters and nonmesh helpers are accounted separately.
- No library height/diameter dimension strings were found in the ordinary Text
  labels. The project has `Hnnn` tokens; cm interpretation is explicit, and all
  alternatives in a multiline row are retained. Missing dimensions remain null.

## Catalogue fields (`flora-audit-v1`)

- `artifact_root`: authorized external root; all `file`, `preview`, `planned_*`
  values are relative to it. Source user roots are redacted as `<USER>`.
- `sources[]`: original byte counts and before/after/copy SHA-256 strings.
- `scenes[].labels[]`: complete raw string, class, hidden flag, position, bbox,
  `parsed` type/profile/dimension candidates, role, candidate handles, status,
  association distances/method and ambiguity reasons. `category_heading` counts
  as an explicit non-asset orphan in the accounting invariant.
- `entries[]`: stable audit row `id`, original name/handle, raw species/profile
  labels and profile candidates, type with inference basis, measured bbox XYZ m,
  labelled H-token alternatives and their unverified unit convention, triangles,
  UV/vertex counts, material/submaterial/bitmap references and sharing counts.
- `artifact_status`: `not_produced`, `produced_unverified`, `readback_equal` or
  `readback_mismatch`. Planned paths are not proof of an output. Native per-row
  receipts and `verify_archive.py` check hashes independently of these strings.
- `proposed_budgets[]` / `project_statistics[]`: type/profile `n`, min, median,
  nearest-rank p90, max and review-only rounded observed ceiling. Empty groups
  have null numbers; overlapping LP -> HP candidates are not deduplicated.
- `project_vs_library`: normalized exact-caption matches, both missing-name lists,
  per-project name candidates, and exact-triangle/bbox-within-20% candidates.
  No synonym/spelling repair, species substitution or appearance approval.
- `pairing_comparison[]`: same-node XY, display-plane and final bounded-row
  comparisons, each timed three times; only the median is a performance claim.
- `delivery_passed`: always false. This catalogue is not an AGR package checker.

Complete ambiguous/orphan lists, unlabelled plants, >10% dimension candidates and
all library-vs-project differences are generated in
`docs/experiments/flora-library-audit-findings.md` (not hidden in summary counts).
`verify_artifacts.py` remains the legacy v002 verifier; use `verify_archive.py`
for v003. `export_assets.py` / `export_fbx.py` retain the earlier native variants.

This is an inventory with known findings, **not a passed NPM/VPM delivery**. See
`docs/experiments/flora-library-audit.md` for measurements, caveats and verdicts.
