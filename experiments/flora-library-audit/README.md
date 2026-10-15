# Flora library audit (#189)

Standalone, card-scoped experiment. Production code and standards are untouched.

**Current status: incomplete, blocked on native archive cost.** Inventory and label
catalogue are real; 9 partial MAX assets and 1 unverified FBX are not a completed
136-entry archive. `partial-verification.json` records unchanged source hashes.
Missing catalogue paths are null; `planned_*` paths are not produced artifacts.
`export_assets.py` preserves the slow MAX baseline; `export_fbx.py` is the second,
unfinished native attempt. `verify_artifacts.py` must fail until full native
readback evidence exists. No all-asset verification report was produced.

## Inputs and safety

Use only the two hash-verified copies under `C:/x/t_366e8d9d/`. Original Desktop
scenes are **never** loaded into Max. `sources-verified.json` is the pre-copy hash
manifest. Do not run pytest with the card root as its destructive basetemp: use a
child such as `C:/x/t_366e8d9d/pytest-probes` so inputs/outputs survive.

`export_fbx.py` requires a new `assets-v002` directory. It refuses to overwrite
any asset or preview. For another audit, use a new versioned output root and keep
the previous evidence. A cancelled wrapper waiting for the shared lock must be
confirmed stopped before another wrapper is submitted. Never remove another
card's lock or start Max directly.

## Reproduce

From this worktree, with Max 2026 installed and the specified copied inputs:

```bash
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --ping --card t_366e8d9d
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --file experiments/flora-library-audit/inspect_scene.py --card t_366e8d9d --out C:/x/t_366e8d9d/inspect-detailed-batch.json
python experiments/flora-library-audit/catalogue.py --output experiments/flora-library-audit/catalogue.json
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --file experiments/flora-library-audit/export_fbx.py --card t_366e8d9d --timeout 1800 --out C:/x/t_366e8d9d/export-fbx-batch-v002.json
# The native extraction enriches detailed inventories with TextPlus strings.
python experiments/flora-library-audit/catalogue.py --output experiments/flora-library-audit/catalogue.json
python experiments/flora-library-audit/verify_artifacts.py
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

This is an inventory with known findings, **not a passed NPM/VPM delivery**. See
`docs/experiments/flora-library-audit.md` for measurements, caveats and verdicts.
