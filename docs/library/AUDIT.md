# Library audit and windows migration — #1259

Audit date: 2026-11-12. Base: `origin/main` at `5a9606d5` (pilot). Windows migration is
standard-generated geometry under [D204]/[D258], **not** a cleaned copy of the customer's
MAX mesh. Technical cleanliness, source confirmation, C35 and delivery approval remain separate.
Machine counts: [audit-counts.json](audit-counts.json). No live Max session was used.

## Audit table (file counts are not asset counts)

| Library | Files currently in AGR-assets | Catalogue/contents | Problems and action |
|---|---|---|---|
| Windows | 1 MAX, 1 BLEND (plus 2 desktop.ini) | 67 type rows: 37 confirmed, 30 unconfirmed. Existing K2 quality: 61 pass, 6 quarantine. Preview BLEND: 403 objects = 335 meshes + 67 labels + 1 camera; 1,340 triangles. | Old preview is a display scene with full frame slabs, not reusable frames: 68 nonidentity transforms, 0 hidden objects, 0 unused material slots. Extracting its cells would preserve the wrong slab representation. Regenerate from the existing D204 standard instead. |
| MAF | 932 MAX, 1,022 FBX, 4 BLEND, 116 ZIP, 1,032 PNG; other support files counted in JSON | Existing catalogue: 931 entries from 996 source objects; 20 helper planes + 97 nongeometry nodes explicitly excluded; 33 duplicate groups / 79 entries. NPM source BLEND: 368 meshes / 734,645 triangles. | NPM assembly has 368 nonidentity transforms, 96 hidden objects, 81 unused material slots. Each of 3 generated showcase files has 31 objects (20 meshes, 10 labels, 1 camera), 80 unused slots and an orphan Render Result. Keep showcases separate; these are not one-asset reusable files. Existing catalogue has 93 unmatched NPM rows and 30 overlap records; no identity/cleanup claim follows from `built_ok=931`. No MAF migration in this PR. |
| Flora | 2 MAX, 341 PNG, 1 CGEO (plus 20 desktop.ini); no BLEND | Current catalogue: 61 species (20 trees, 31 bushes, 9 flowers, 1 climber), 38 with VPM; 61 approved map pairs. 15 shared-stand-in gaps, 1 unresolved identity, 37 merged duplicates. | Historical native census of FLORA_Union: 90 plant meshes, 326 labels (4 hidden), 4 scale references, 80 display envelopes, 5 planters, 1 nonmesh. FLORIO: 46 plant meshes + 23 labels, all 23 label associations ambiguous. Scene-level leftovers are real; species labels must not be mistaken for distinct reusable meshes. Existing library README keeps VPM identity unverified. Preserve IDs/cultivars/maps; no invented botanical identity and no Flora production edits. |
| Roof equipment | 0 files / no dedicated AGR-assets/roof_equipment directory; no library/roof_equipment catalogue on base | Equipment may exist in delivered projects, not yet in a reusable library. MAF catalogue already contains roof-related candidates (e.g. MAF_0065 vent-shaft enclosure). | Zero means no dedicated library, **not** no equipment in projects. #1257 / child t_d0a92d95 owns delivered-project research, types and first 8–12 assets; it must reuse this template rather than duplicate it. |

### Coverage and provenance

Fresh native readback covers **all five BLEND files** found under the Windows/MAF asset roots,
on byte-identical, newly hashed copies in `audit-v002`. Their full object inventories, material
slots, transforms, hidden states, bounds and unused datablocks are in `audit-v002/audit.json`.
Original hashes were verified again after readback. The 932 MAF MAX / 1,022 FBX counts include
versions and project products: **not** 1,954 distinct models. We do not assert every MAX/ZIP/FBX
internally clean or dirty from an extension count. No MAX or CGEO was opened by this card;
Flora MAX contents above are explicitly the committed historical census, not a fresh Max claim:
`experiments/flora-library-audit/catalogue.json` and
`docs/experiments/flora-library-audit-findings.md`. Current consolidation and map-binding limits:
`library/flora/README.md`; MAF provenance/exclusions: `library/maf/catalogue.json`.
The two current Drive Flora MAX files are `v003/flora-library-v003.max` and
`a101/FLORIO_221.max`; their measured SHA-256 values are in EVIDENCE.json. They are **not**
the two historical source hashes: historical source leftovers are not asserted as current
v003/A101 object counts. Their fresh MAX/CGEO internal transforms/pivots/material cleanup
remain unmeasured on this Blender-only route, explicitly not a clean-library verdict.

A displaced showcase object is not automatically a bad production pivot. The audit records
nonidentity transforms relative to the proposed reusable-template convention; migration must
place mesh coordinates at the documented base anchor before applying transforms. It must not
blindly clear a transform and move the geometry. Units in all five BLEND inventories are metres.

## Migrated Windows release (catalogue v001, evidence attempt v003)

- **67/67 IDs accounted for**, source metadata, confirmations and unconfirmed sash/handing retained.
- **59 ready types, 118 native files**: each has separate NPM plane / VPM frame+glass parts.
- **8 quarantine rows, no offered meshes**: old K2 six `D04`, `CW_021`, `CW_022`, `WT-02`,
  `ELV-16`, `ELV-17`, plus `D03` and `D03_W` discovered by fresh native xView.
- `D03` / `D03_W` were K2-pass but their global frame-grid subdivisions store vertices within
  the inclusive 2 mm xView threshold after float32 export (32 / 18 pairs, respectively).
  We did **not** weld them, change dimensions or waive the check. Their complete source rows
  remain in both catalogues; they need a separately reviewed geometry repair before offering.
- Missing source names stay `original_name: null`; the sheet says `source name unspecified`,
  not an invented window type. Unconfirmed types are amber; quarantine is red.
- `quality.json` is retained as the historical K2 report, not overwritten with this new native
  cleanliness result. `catalogue.json` is derived; existing AGR Tools consumers still use their
  unchanged source JSON and standard. The common release is independently usable from its README.
- Material IDs are existing window 1 (frame face), 4 (frame back), 5 (opaque), 10 (glass).
  One finite UV layer is present; atlas baking, glass delivery consolidation, texel density,
  source-geometry fidelity and C35 are **not certified**. No sash geometry/direction is invented.

## Executed commands and evidence

All paths below are under `G:/Мой диск/AGR-evidence/1259-windows-library/`:

| Path | Evidence |
|---|---|
| `audit-v002/` | Five hashed source copies, raw native inventories, original/copy SHA-256 equality; SHA256SUMS.txt |
| `v001/` | Failed first build, retained. Source `name=null` caused TypeError before catalogue publication. |
| `v002/` | First full build: 61 types / 122 files. Separate xView found D03/D03_W failures; superseded, not approved. |
| `xview-v001/` | All 122 reports: 120 pass, 2 fail; zero overlapping face/contact pairs, but 50 vertex pairs in the two failed files. Raw failures preserved. |
| `v003/` | Current 59-type/118-file clean release; catalogue + grid PNG + showcase BLEND + SHA256SUMS.txt. Eight explicit quarantine cells. |
| `xview-v002/` | Fresh per-file xView reports and summary for current offered assets; SHA256SUMS.txt. |

```bash
# Pure contracts + existing affected tests
uv run pytest -q tests/test_library_cleanliness.py tests/test_library_windows_migration.py \
  tests/test_window_types.py tests/test_window_sashes.py -p no:cacheprovider \
  --basetemp=C:/x/t_785829b4-affected
# Actual Blender generation, readback, fresh-process checker, and no-overwrite regression
AGR_LIBRARY_MIGRATION_ROOT='G:/Мой диск/AGR-evidence/1259-windows-library/v003' \
  uv run pytest -q tests/test_library_blender_native.py -m blender -p no:cacheprovider \
  --basetemp=C:/x/t_785829b4-native-final
# Read only; safe to repeat (unlike the generation command above)
uv run python tools/library/check_library.py library/windows/catalogue.json \
  --root 'G:/Мой диск/AGR-evidence/1259-windows-library/v003'
# Repeated once per offered file/profile; reports are new paths only
uv run dt qa xview 'G:/Мой диск/AGR-evidence/1259-windows-library/v003/assets/W01/vpm.blend' \
  --profile VPM --blender 'C:/Program Files/Blender Foundation/Blender 5.1/blender.exe' \
  --out '<new existing report directory>/W01-vpm.json'
```

Read-only audit and xView reproduction drivers are stored beside their evidence; small receipts
with actual hashes and counts are in [EVIDENCE.json](EVIDENCE.json). The full-resolution PNG was
visually inspected as a complete grid and at label scale (header/first rows); no clipping was
seen. This is the requested showcase for Artem, **not Artem's visual approval**.
