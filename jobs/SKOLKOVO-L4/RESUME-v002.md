# Skolkovo L4 resumed intake — evidence and decision request

This is real-project **intake**, not a generated delivery. No kernel operation,
new building master, source replacement, final export or user approval is claimed.
`passed=false`. Originals and delivered references remain unchanged.

## What actually ran

- Reused the successful v1 Blender 5.1.2 facts; the public
  `python -m dt_ai.parts.readers.fbx` CLI verified the original FBX name/hash,
  recomputed contacts and validated its output against Pydantic and JSON Schema.
  Result: **17,710 parts / 73,110 questions / tier B / 6,644,287 triangles**.
- Coverage probe: 17,710/17,710 source meshes represented exactly once, zero missing
  or duplicate object references; 6,644,287/6,644,287 source triangles conserved.
  The default `keep` operations are reader placeholders, NOT approved decisions.
  Every legend item is unmapped; no joint decision is approved.
- Factory-startup Blender retried the lightning-rod revision with one thread,
  disabled autoexec and private TEMP. It still crashed before import (exit 11,
  `EXCEPTION_ACCESS_VIOLATION`, address `0x00007FF6FCE42509`). Crash preserved in
  the evidence archive and `C:/x/t_b205c8e1/crashes-v002/blender.crash.txt`.
- Followed the orchestrator's authorized Max fallback. Headless **3ds Max 2026.3
  (28.3.0.30732)** read all four remaining in-scope FBXs. The live Max 2024 was
  detected but never modified. One batch process at a time, no source saves.
- First fallback exported 1,146 small per-object FBXs before intentional cancellation:
  the file called lightning rods contains 3,745 scene nodes, not just five rods.
  Those partial diagnostic exports are not a completed artifact/readback or an
  accepted selection. Cancellation was verified to leave no batch Max process.
- The subsequent census completed with four JSON outputs and `L4_COMPLETE`.
  Native exit `4294967166` and the known PolyUnwrapper startup error are retained;
  `dcc_batch.py` returned wrapper exit 0/status `ok` **with warning**. Successful
  extraction is established by actual output content, not that wrapper status alone.
- Integrity probes verified all **104/104 inventoried input file hashes unchanged**,
  21/21 evidence hashes and ZIP CRC, plus 2/2 fresh-process output/input aliases
  rejected with exit 1 and unchanged facts. Max FBXIMP nevertheless extracted four
  embedded NPM textures into a new `03_LP/0809_BolshoyBulvar_64_01.fbm/` directory
  **inside the supplied working copy**, outside this worktree. They were not
  removed or treated as original inventory entries. No originals or existing
  source/reference files were overwritten. Future imports must stage their FBX
  inside the worktree first to contain this importer side effect. See the exact
  new-file list in `integrity-probes-v002.json`.

## Measured reference census

Counts are Max FBXIMP/snapshot measurements, not kernel invariants or architectural acceptance.

| Input | Meshes | Triangles | Reader seconds | Hours |
|---|---:|---:|---:|---:|
| September lightning-rod file, including other building objects | 3,741 | 1,030,375 | 13.770163 | 0.003825045 |
| September facade file | 11,510 | 1,146,519 | 38.038396 | 0.010566221 |
| Delivered NPM | 1 | 49,657 | 0.536801 | 0.000149111 |
| Delivered VPM, including UCX | 225 | 59,116 | 0.470928 | 0.000130813 |

VPM contains 2 non-UCX meshes (56,440 triangles: Main 55,998; MainGlass 442)
and 223 UCX meshes (2,676 triangles). NPM and VPM are therefore **not asserted
identical**; both reference surface counts fit the 150k project target, but that
is not a pass for our nonexistent output. VPM geometry materials include Main and
two MainGlass slots. No source material has been defaulted to one of these slots.

Census batch wall time was 120.9 s (0.033583333 h), including startup, import,
serialization and shutdown. Per-file times above must not be added to batch wall
time as extra work. v1 structure timing remains 1,388.938926 s / 0.385816368 h;
C5 page extraction/rendering remains 50.954157 s / 0.014153933 h. The PartsList
CLI was not wrapped with a timer: duration is **not measured**, not zero.
The failed startup and cancelled exports are rework, not production throughput.
Operation/build/export/review/SINTEZ hours are **not measured: not executed**.
This is a partial L5 baseline, not L5 readiness.

## Registration and version hazards

A shared-element-ID bbox-centre probe independently compares the v1 facts with
the two Max revision censuses; it does not apply a transform or accept changed geometry.

- Lightning file: 1,203 unique shared IDs; 1,202 centres match within 2 mm without
  translation. One outlier is about 40.895 m away and remains unresolved.
- Facade file: 2,938 unique shared IDs. The dominant measured offset, **revision
  minus v1**, is `[42.266, -35.629, 0] m`; 2,633 centres agree within 2 mm,
  2,663 within 1 cm. The other objects include changed/moved or ambiguous geometry;
  no nearest-neighbour replacement or blanket translation is approved.
- Delivered NPM is placed; VPM is local. Delivered GeoJSON records point
  `[-10116.728, 2467.929]`, `h_relief=186.8`, `h_otn=27.5`, `h_abs=213.77`.
  These are package metadata, not independent CRS/project-zero verification.
- Source v1 has no FBX Material nodes; importing it cannot recover an approved
  face/material mapping. September files do carry named materials. Matching only
  names or the first material would silently invent mapping.

Revision page 1 was visually inspected: changes are marked at the plinth and
at added mullion/stemalite infill on facade 7–1. Revision legend uses curtain-wall
profile RAL7015 versus album page 15 RAL7004; the specified September revision
is retained separately, not silently conflated with the album. Roof rods are
explicitly required by revision pages 3/4. The GeoJSON embedded preview was
extracted and inspected as a **delivered-package reference image**, not a newly
rendered output: rectangular massing, vertical facade pattern and roof screen
are visible; it does not certify source overlays or individual rods.

## Per-part triage, not an approved operation table

`per-part-triage-v001.csv` in the archive has one row for each of the 17,710 draft
parts, retaining its ID, object name, reader class, placeholder operation and
source triangle count. Proposed operation is explicitly `unresolved` and status
`not_approved` in every row. Name-only triage is a navigation aid:

| Candidate review bucket | Rows |
|---|---:|
| Fastener visibility | 5,130 |
| Structural visibility | 2,194 |
| Explicit interior-name visibility | 91 |
| Remaining exterior-scope/legend review | 10,295 |

These counts **do not** establish hidden/exterior geometry or authorize deleting
any object. In particular the lightning file contains walls/roof layers and
must not be appended wholesale as rods. Source coverage of the v1 draft is
complete; revision coverage and final exclusion reasons are still open.

The all-keep source census exceeds 150,000; its budget check is **fail**, not
review/pass. It must not be submitted as a buildable or approvable 150k master.
A final PartsList needs actual visibility filtering/drop list, exact per-part
operations and target budgets, material legend mapping and joint decisions.

## Exact user question before production

For the visible-through-glazing interior and source structural detail, please
confirm the proposed modelling policy: **retain only the exterior plus simplified
source walls/floors where actually visible through glazing; do not apply a global
Shell; exclude hidden structural steel, fasteners and interiors with an explicit
per-object drop list**. Or specify the different intended interior/thickness
policy. This resolves the applicable shell/interior ambiguity (BODY-L / C23).

This is a request for that model-policy decision, **not** approval of the
all-keep draft. After the answer, prepare the reduced, budgeted PartsList with
revision/material/joint mappings and obtain user Gate 1 approval of its exact
hash before any kernel build (D125). No approval receipt is fabricated.

## Reproducibility and remaining gates

`resume-evidence-v002.json` hashes all raw facts, draft, CSV, four Max censuses,
frame probe, logs, input-independent drivers and selected drawing/reference images.
The versioned ZIP contains no source or delivered FBX, only derived evidence.
Raw local files remain under `tmp/skolkovo-l4-v001/` and `tmp/skolkovo-l4-v002/`.

The original 133 focused tests passed in the prior attempt; no production code
changed in this retry, so no code-fix RED/GREEN claim is made. Full suite is not
run on this incomplete intake: rule 49 reserves it for the first review head.
No PR is opened with incomplete acceptance. Downstream gates remain open:
final PartsList/user Gate 1, kernel operations and before/after invariants,
budgets, export/clean readback, comparison report, board-tool visual review/user
verdict, final SINTEZ and complete stage timings.

Transcript: Hermes task t_b205c8e1 run 974 (resumed read-only intake).
