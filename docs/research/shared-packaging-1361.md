# Shared packaging and export metadata — #1361

## Ownership and boundaries

`adapters/max/agr_tools/package_core.py::_write_zip` is the one ZIP writer used by
AGR Tools and both `tools/derive/package_{npm,vpm}.py` commands. It is dependency-free.
The VPM command retains its sorted flat members, ZIP timestamps/compression, GeoJSON
proposal and deferral semantics. The existing TEC26 byte-parity regression remains
unchanged. The core now refuses duplicate physical inputs, empty members, source/ZIP
snapshot mismatches and pre-existing partial files without deleting foreign files.
No job-local packager is rewritten. No geometry repair, placement or acceptance is performed.

`adapters/max/agr_tools/export_meta.py` owns metadata validation/emission;
`tools/derive/export_meta.py` is its CLI facade. The MZP builder includes the owner,
so embedded Max does not need Pydantic, jsonschema or a repository import.

## Contract

Schema: `schemas/ExportMeta.schema.json`. Validate with
`uv run python tools/derive/export_meta.py PATH` (nonzero and a named error on refusal).

Required fields:
- `address`: a filename naming token, **not** a certified postal address; `unknown` is
  allowed in a record but refused by packaging.
- `h_otn_model_max_z_m`: finite export-frame render top in metres, or literal `unknown`.
  The historical name does not mean height above an offset project zero (#1341).
- `thumbnail`: a JPEG path or literal `unknown`, never a generated customer substitute.

New producers additionally emit `profile`, `exported_files`, and `provenance` with a
source/question for every other field. Unknown facts remain unknown; numerical zero
is never substituted. The validator adds semantic finite-number, ordered-bound,
case-insensitive uniqueness and exact provenance-coverage checks beyond JSON Schema.
Unknown top-level keys and missing required fields name the offending fields.
Duplicate JSON keys are refused. Historical VPM metrics (`fbx`, pivot/bbox, triangle
and UCX counters) are explicitly recognized, not accepted through an open extras bag.
Historical records without provenance remain readable, not retroactively certified.

A producer for a dedicated single-export folder writes adjacent `export_meta.json`.
Multi-file producers write `<filename>.fbx.export_meta.json` to avoid overwriting a
sibling export's metadata. Packaging resolves the nearest canonical record, then a
unique non-light FBX sidecar, then the historical parent `export_meta.json`. Multiple
sidecars require `--meta PATH`; there is no first-entry fallback. Metadata stays out
of the delivery ZIP. A record is not a receipt that all package/scene checks passed.

### Producer coverage

- Shared NPM derivation `tools/derive/export_npm.py`: adjacent canonical metadata;
  top from the final export-copy render vertices, thumbnail unknown with a question.
  Existing `export_npm_meta.json` and editable export-copy outputs remain.
- Shared Ground construction `tools/blender/ground_json_to_fbx.py`: per-FBX sidecar,
  explicit Ground address/profile and unchanged export-frame Z top.
- Shared Ground texture binder `tools/materials/bind_ground_textures_blender.py`:
  per-FBX sidecar for both profiles, render top excluding UCX, profile from binding plan.
- Shared checked Max export `export_core.commit`, including the runtime subprocess
  fallback: per-FBX sidecar. Unmeasured top/thumbnail remain unknown with questions.
- Shared Max NPM split export `package_max._export_selected`: one sidecar per FBX;
  no invented height from an unmeasured native snapshot.
- Historical KPP1 / TEC26 / PSU275 VPM exporters already write the explicitly supported
  legacy record. They remain historical producers, not rewritten or newly certified.

Asset-generation fixtures, handoff snapshots and research-only technical FBX exporters
are not delivery-profile exporters. This change does not turn them into NPM/VPM
publication commands. Lighting thumbnails/heights are not inferred from body metadata.
The separate per-FBX `bounds_m` + `fbx_sha256` V013 producer gap is owned by #1342;
this naming/top/thumbnail record is not misrepresented as that checker mapping.

## Commands and regulation

`uv run agr package-npm PACKAGE_DIR [--meta PATH] [--allow-incomplete]`

`uv run agr package-vpm PACKAGE_DIR TEXTURES_DIR [--meta PATH] [--object OBJECT] [--no-geojson]`

NPM reuses the owner's existing `zip_plan`: `{code4}_{Address}.zip`, only FBX,
mandatory Ground plus contiguous OKS `01..20`, 2..21 members, embedded textures
(PKG-01/03/08/13, regulation physical pp.6/7/11). The input filename territorial code
is preserved; KPP1's `0000` is an approved placeholder, not a classifier determination.
No external atlas or metadata JSON is packed. Excluded inputs have reported reasons.

Default NPM packaging refuses an incomplete composition before writing. An explicit
`--allow-incomplete` writes a diagnostic ZIP/report, **exits 1** and retains problems;
it never creates missing Ground or changes `passed` to true. Complete composition
returns 0 with `status=packaged_not_validated`, still `passed=false`: packing is not QA.
VPM's historical `--no-geojson` remains a deferral, not a delivery pass.

PKG-01/02 and D015 use inclusive binary limits (NPM 1024 MiB, VPM OKS 500 MiB,
Ground 1024 MiB). Equality passes the explicit regulatory size rule; it is not an
invented exclusive threshold. Source hashes are compared with the ZIP and source
snapshots before publication; this is not a continuous filesystem lock. A pre-existing
ZIP/report/partial is not overwritten. The owner uses no-clobber publication; POSIX
rename is not used as a no-clobber fallback.

## Real continuation and remaining gates

See `jobs/KPP1/package-1361/REPORT.md`. Both commands were executed on verified copies;
the new ZIPs exist, but both V001 results remain fail (missing Ground / deferred
GeoJSON). No official delivery, survey, topology or manual gate is promoted to pass.
The reconstructed records contain per-field provenance and preserve D262/D279's
unknown legal address/height-system questions instead of inventing answers.

Program choice: CPython for schema, hashing, copies and ZIP/validator commands, since
packaging does not require a DCC. Blender 5.1.2 headless for exporter regressions on
copies, because the shared NPM/Ground producers are Blender entry points. Max boundary
logic is exercised with an explicit synthetic export API; no live Max scene is touched.

## Frozen duplicates / #1359 handoff

The card's prose says eight, but repository discovery finds **nine** files:

- `jobs/KPP1/scripts/package_vpm.py`
- `jobs/PSU275/scripts/package_vpm.py`
- `jobs/TEC26-OKS/scripts/package_vpm.py`
- `jobs/elv-tc-vpm/scripts/package_vpm_v001.py`
- `jobs/elv-tc-vpm/scripts/package_vpm_v002.py`
- `jobs/elv-tc-vpm/scripts/package_vpm_v003.py`
- `jobs/elv-tc-vpm/scripts/package_vpm_v004.py`
- `jobs/elv-tc-vpm/scripts/package_vpm_v005.py`
- `jobs/elv-tc-vpm/scripts/package_vpm_v006.py`

The #1359 guard is now on main (merged PR #1368); all nine historical paths are
already in `docs/architecture/contexts.yaml` with their #1106 references, and stay
untouched. This branch refreshes only its own moved shared-writer/exporter line
anchors and generated diagrams. The unrelated KPP1 allowlist drift on main belongs
to #1387; this branch does not duplicate that repair.
