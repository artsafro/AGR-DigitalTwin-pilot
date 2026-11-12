# One library format — AGR library/1

Scope: windows, MAF, Flora and roof equipment. This is a **library cleanliness** contract,
not a building delivery format, SINTEZ certificate, architectural approval or licence grant.
[D258] permits D204 geometric VPM/mid window frames (F100/F73/F58) and a separate NPM
plane. C35 stays open; neither this template nor its checker resolves geometry versus bake
for an actual delivery. NPM planes here are UV-ready templates, **not baked window atlases**.

## Layout and authority

```text
library/<library>/                    # Git: small text only
  catalogue.json                     # schemas/library_catalogue.schema.json
  README.md                          # exact external version root + commands/limits
  sources/, confirmations.json, ...   # preserve existing source-specific authorities
G:/Мой диск/AGR-evidence/<issue>-<topic>/<new-run>/
  catalogue.json                     # byte-identical copy of committed catalogue
  assets/<stable-id>/npm.blend        # one reusable asset, one profile
  assets/<stable-id>/vpm.blend
  previews/<sheet>.png                # labels/grid; never inside an asset file
  previews/<showcase>.blend           # cameras/text/lights allowed HERE, not assets/
  SHA256SUMS.txt
```

A library release is immutable. Generate into a new version directory; never overwrite a
source, accepted version or failed attempt. Promotion into AGR-assets is a separate action;
this issue publishes review evidence, not an approved replacement of the source store.
MAX/FBX may remain source/provenance formats; the common reusable master is `.blend`.
A multi-part set is ONE asset only when it is one inseparable assembly. A bench collection,
species assortment or window grid is a showcase, never a reusable asset. No Git LFS.

## Catalogue

Validate with the Draft 2020-12 schema and the semantic checker, not schema alone.
Stable `id` is unique case-insensitively and is never reassigned. Preserve original IDs;
`name` is the human label, not a project-specific object name. Source records keep original
names, path/object/page provenance, unconfirmed readings and unresolved identities. Explicitly
mark standard-generated or synthetic geometry. Missing source identity is not a confirmation.

- `schema = agr-library/1`, library category, release `version`, and pivot convention.
- `inputs`: repository-relative paths + SHA-256 of source catalogues, standards and generators.
- `showcase`: external-root-relative sheet path + hash; each asset has a unique 1-based `preview_cell`.
- `confirmation`: `confirmed` / `unconfirmed`, independent of technical availability.
- `status`: `ready` means both reusable profile files exist; `quarantine` requires reasons,
  retains its ID/provenance/cell, and has **no** offered variants. Never silently drop a row.
- Each ready `npm` / `vpm`: path/hash, measured triangle-equivalent count, XYZ dimensions in
  metres, exact object names and exact used material IDs/names. Zero depth is valid for a plane;
  width/height and triangle count must be positive. Unsupported profiles fail, not fall back.
- Materials use `matid_<stable-id>` plus integer `agr_material_id` in Blender. Slots are local;
  stable IDs are not slot ordinals. Unknown IDs/slots fail with their names. Preserve the existing
  library's ID meaning (window 1/4/5/10; Flora species ranges), never globally renumber libraries.

## File cleanliness

One scene, one view layer, metres (`METRIC`, `scale_length=1`), Z up. Window geometry faces
-Y: origin at the opening's **bottom-left/front**, XYZ bounds `[0,0,0]..[W,D,H]`.
MAF/roof assets use `bottom-center`: base at Z=0, X/Y extents centred on origin.
Flora MUST use `flora-bbox-plus-0.1` [D100]: X/Y bbox centred on origin, lowest vertex
at Z=-0.1 m, so the pivot is 10 cm above it. Placement on Ground adds no further sinking.
All part-object origins share that assembly anchor. Geometry lives in mesh coordinates;
object world transforms are identity. No unapplied modifiers, constraints, parents, instances,
linked libraries, animation/drivers, shape keys (including inactive/Basis keys),
hidden objects/collections, cameras, labels, helpers,
loose geometry, duplicate faces, zero-area triangles, unused slots or orphan datablocks.
Required parts are explicitly listed in the catalogue. Materials are used; dependencies are
local and packed (no external image paths). One finite UV layer per mesh; no claim of texel
compliance, atlas packing or botanical accuracy follows from that check.

The native readback fails on triangle area **<= 1e-12 m²**, distinct vertices **<= 2 mm** apart
(D152, within each part, after native float32 storage), nonfinite geometry/UVs, empty meshes,
wrong object/material inventories and missing measurements. Size/pivot comparisons allow
absolute roundtrip error **<= 1e-5 m**; identity transforms and unit scale are exact. These are
library numeric hygiene tolerances, not new regulatory budgets. Open glazing planes are valid;
watertightness is not globally required. xView overlaps are measured separately on every export;
a cleanliness result alone does not replace xView, delivery QA or a user's visual gate.

## Checker and reproducible windows migration

```bash
uv run python tools/library/check_library.py library/windows/catalogue.json \
  --root "G:/Мой диск/AGR-evidence/1259-windows-library/v003"
# Fresh own Blender process; actual files read back, input hashes before AND after.
# stdout JSON only; exit 0 = clean ready subset, exit 1 = error/dirty/not measured.
```

No report/output/temp argument exists in the checker: it cannot clobber an input via a report
alias. It rejects missing/extra asset files, traversal, physical aliases, duplicate IDs/JSON keys,
partial native inventories and stale hashes. It does not consume stored `pass` verdicts.
Before/after fingerprints detect persistent changes, not a malicious edit restored between reads;
producers must retain exclusive ownership of their output version. Not a hostile-.blend sandbox.

Windows retain `window_types.json`, `standard.json`, `confirmations.json` and `sources/` as
editing authorities. The common catalogue is derived, never hand-edited. Rebuild **then** apply
#246 sash candidates; never promote them to `sashes`/`handing` confirmations:

```bash
uv run python tools/library/build_window_types.py \
  --base library/windows/window_types.json \
  --census-source library/windows/sources/elv-tc-vpm-census-v001.json \
  --sashes library/windows/sources/win-typical-max-sashes-v001.json \
  --output tmp/windows-rebuilt-v001.json
uv run python tools/library/migrate_windows.py \
  --output "G:/Мой диск/AGR-evidence/1259-windows-library/<new-run>"
```

The rebuild writes a **new** output with `--sashes`, rejecting existing/aliased targets.
Compare/review its data before adopting it as the source catalogue. Migration independently
reapplies the same sash-source evidence idempotently and uses the existing D204 generator;
it does not interpret unconfirmed opening directions or replace untyped rows with guessed shapes.
MAF/Flora remain on their existing catalogues until an authorized migration; #1257 reuses this
schema/checker for roof equipment. No second competing library standard is introduced.
