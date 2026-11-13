# KPP1 NPM derivation — benchmark track A (#1318)

## Verdict and boundary

**A repeatable diagnostic pilot, not a delivery pass or a positive quality oracle.**
Cell `oks-npm`; escalated to `full` because atlas tooling needed two explicit layout
arguments. [D280] authorizes a new geometry-preserving `.blend`/recipe from R1 FBX;
[D271] authorizes this route. No paid provider, Kimi comparison, paired-arm speedup,
Ground completion or $10 full-building claim is made. Native failures are results.

The accepted input is R1 `r1-v002`, **not** historical KPP1 v005. The source R1 FBX is
already triangulated; reconstructing quads would change topology and was not done.
The adapter is labelled `triangulated R1 adapter`, not a quad working master.
The independent validator therefore correctly fails DER-03. Ground, final Max/AGR
Tools, SINTEZ and human gates stay open. `jobs/KPP1/job.yaml` is not promoted.

## Frozen input

Local canonical packet: `C:/x/bench-npm-kpp1/packet-r1-v002/`.
Its root `SHA256SUMS.txt` binds **26 files**; raw-byte SHA-256:
`d3bbb7716247563c9e382eeda9317e2060944640f7f237ab7e36b5c4f2084cfa`.
The committed manifest is `jobs/KPP1/benchmark-1318/packet-SHA256SUMS.txt`.
Packet immutability means versioned, never intentionally rewritten, and full hash
inventory checks before/after each stage. Historical sealed preparation/context
receipts retain the original D279 label: after discovering #1330's earlier reservation,
this card's authorization was renumbered D280. That is a citation-only mapping;
no frozen packet, manifest, native export or historical receipt was rewritten.
This is **not** a hostile-writer ACL or
proof against transient changes restored between checks. Reject any mismatch;
never regenerate this manifest to accept a changed packet.

Input provenance:

- Source `G:/Мой диск/AGR-evidence/1230-kpp1-r1/r1-v002/SM_Kpp_1.fbx`:
  `1f46b0dd5973b6e3ba40acbe04d65fb3595dcacb0d90a7724e921eda9b56b676`.
- `source/` retains exact FBX, historical NPM comparison, atlas and source manifest.
  Derivation needs the VPM FBX and procedural recipe, not live Revit/Max or DWG decoding.
- `context/` retains job state, checklist, source registry, R1 texture/parts scope,
  route and `uv.lock`. `jobs/KPP1/TASK.md` is absent upstream; that fact is recorded
  in `provenance.json`, not silently replaced by fabricated acceptance.
- `spec.json` adapts the seven R1 finishes without choosing new RGB/periods. Its
  `source_ids` are recovered **finish ordinals**, not invented customer element IDs.
- `master-r1-v001.blend` adds only `finish_names` and FACE/INT `finish`, recovered
  strictly from each triangle's UDIM. Crossing/unknown tiles or unused finishes
  refuse preparation. `preparation.json` compares full vertices, polygon indices,
  UVs and transforms before/after/save/reopen: identical for all six meshes.
- Main finish faces: 3839 / 6126 / 7966 / 948 / 9016 / 1577 / 690, in spec order;
  Main 30162, Glass 504; four 12-triangle UCX meshes retained in input only.
- Atlas 2048, cell512, padding8, region496, S=2.048 m. R1's 3 mm procedural
  joint painter is reused through a small adapter; no new 1.5 px joint-width claim.
  Region positions follow the shared atlas's top-down ordering; UVs are remapped,
  not copied onto incompatible positions. New padded atlas pixels are not asserted
  byte-identical to the historical, unpadded R1 atlas.

This is preparation overhead, **not** a zero-code derivation result. The canonical
run used the original defaults409/6 but explicitly selected `--cell 512 --pad 8`.
After review r1, merge of main fd1c1738 (#1333) preserves [D278]'s shared default
409/16. R1's pinned512/8 is the recorded benchmark exception [D280], not a shared
padding policy. Current generation refuses pad0..3 before writes (8 px inter-island
floor); readback measures the exported cell/pad instead of hard-coding409/16.
The canonical code SHA, packet, hashes, run receipts and metrics remain immutable;
a repeat of the historical measurement must use its pinned implementation, not HEAD.
The converted master keeps the VPM's frames/mullions: unlike historical R1's
separately simplified NPM, this benchmark derives the same whole source geometry.

## Exact repeat protocol

Run from a private worktree at the code revision named by `summary.json` (canonical
execution revision, not a later documentation-only commit). No other attempt's
uncommitted files or live DCC scene are inputs. Blender 5.1.2, factory startup,
script auto-execution disabled; metre scale1; one owned process, no Max calls.

```bash
uv sync --frozen
uv run agr --help
uv run agr vpm-to-npm --help
uv run python jobs/KPP1/benchmark-1318/run_benchmark.py C:/x/bench-npm-kpp1/packet-r1-v002 C:/x/bench-npm-kpp1/run-NEW
```

`run-NEW` must not exist and must not overlap the packet. Absolute native paths
are required on this Windows/MSYS host. `DT_BLENDER` is set by the runner to
`C:/Program Files/Blender Foundation/Blender 5.1/blender.exe`. Python bytecode
writing is disabled for uv children; Blender ignores that environment switch,
so its exact `export_safety` cache is seeded **before packet freeze** and included
in the manifest. The frozen packet is the repeat input; do not rerun preparation
against it. Checksum changes, including unexpected new cache files, invalidate a run.

The retained `run.json` records exact argv, native exit and monotonic time for:

1. Fresh master xView.
2. `agr vpm-to-npm --blender BLENDER SPEC NEW_ATLAS --recipe-dir RECIPE
   --cell 512 --pad 8 --then-npm MASTER SPEC NEW_ATLAS NEW_EXPORT 0000
   --recipe-dir RECIPE`. Atlas success is required before export.
3. Fresh-process `tools/blender/fbx_readback.py` on the actual new FBX.
4. Fresh export xView.
5. Independent `account_readback.py`: source/output triangle multisets and affine UV
   mapping, not only counts; four excluded UCX identities get DER-15 reasons.
6. `agr validate FBX --profile npm --scene --master SOURCE_WORK_FBX --json`.
   The R1 FBX is supplied as the available work source, explicitly triangular.

All direct Blender commands use `--background --factory-startup --disable-autoexec
--threads 1 --python-exit-code 1`. Raw logs, JSON, atlas, FBX and review `.blend`
remain in each new run directory. Exit0 from orchestration means diagnostics ran;
it does **not** mean validator/xView passed. Read native per-stage exits and statuses.
No ZIP/Ground is fabricated just to obtain V001. `0000`, `Kpp_1`, local origin and
unsigned manual gates remain explicit; this does not apply #1255 placement.

For a separately authorized new packet version only:

```bash
uv run python jobs/KPP1/benchmark-1318/prepare_packet.py C:/x/bench-npm-kpp1/packet-NEW
"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --background --factory-startup --disable-autoexec --threads 1 --python-exit-code 1 --python jobs/KPP1/benchmark-1318/prepare_master.py -- C:/x/bench-npm-kpp1/packet-NEW
```

Then enumerate **every** file relative to that root, SHA-256 its raw bytes, write
`SHA256SUMS.txt` with `hash  relative/path` lines and freeze it before execution.
Use `run_benchmark.verify()` to check exact inventory, including caches. Preparation
is not part of the repeat timing, but is included in pilot engineering accounting.

## Measurements and retained failures

Canonical `run-r1-v003`: **35.7020414 s**, six pipeline invocations; stages
(master xView / derive / readback / export xView / accounting / validate):
4.760 / 4.781 / 3.572 / 4.292 / 2.476 / 15.450 s; exits1/0/0/1/0/1.
It starts on clean implementation commit `a5c015b760fa1068032db4d45e47244b45cde9fa`;
measured values, stage exits, hashes and accounting are committed in `summary.json`.
This is warm filesystem/dependency calibration, not a cold-model comparison. Raw evidence:
`G:/Мой диск/AGR-evidence/1318-npm-benchmark/v001/` with root `SHA256SUMS.txt`;
local packet and all local run versions remain available. Drive seal readback:
116/116 hashes match; root manifest SHA-256
`16de8cc1e73fcbbe1e68583a9b96d04c5b50519f65e96ff3da4ed8e8023ec14d`.
No binaries in Git/LFS.

Earlier calibration `run-r1-v002`: **38.7455044 s**, five pipeline invocations;
master xView1, derive0, readback0, export xView1, validate1. Independent accounting
was added after that timing, so its time is **not** hidden in the 38.75 s figure.
Canonical v003 includes accounting in the measured pipeline.

Observed diagnostic classes (v002; canonical identities/values in summary):

- Main30162 + Glass504 triangles; one UV channel per mesh; two embedded RGB2048
  images, diffuse19478 bytes and opacity15785 bytes, no NPM UCX.
- Triangle disposition **30666/30666**; no source triangles dropped; source/output
  geometry equal after the exporter's reported XY recenter within measured float32
  error `2.132481e-6 m` (accounting bound `1e-5 m`, not a regulatory waiver).
  Affine UV mapping maximum error0 for both meshes.
- Master xView:112 overlapping faces; export xView:116, zero overlapping vertices.
  Differences survive export indexing/numerics despite triangle identity; neither
  is a pass, and no topology or tolerance is altered to make them disappear.
- NPM validator: V002/V005/V006/V012 pass; V003 fail (triangular master), V004 review
  (clearance), V001/V014 not_run; V015/V017 manual pending. Machine counts4 pass /
  1 fail /1 review /2 not_run. 8 source T-junctions are review; no quad reconstruction.
- `run-r1-v001` failed integrity after Blender created a previously unlisted `.pyc`.
  Its export and logs are retained; no complete QA or immutable-packet claim.
  `packet-r1-v001` is historical failed preparation, not the repeat input.
- Initial census invocation failed on an MSYS `/c/` argument; a native `C:/` path
  worked. Initial accounting hit missing UCX UV; corrected to inventory UCX without
  manufacturing UV. All failed logs are retained; no rerun replaces a failed record.

Native session telemetry is captured separately in `telemetry.json`: new input,
cached input, output, reasoning and tool-call counters, timestamp and exact session.
It is an explicitly bounded **whole pilot prefix**, including discovery/preparation,
failed attempts and documentation up to that checkpoint, not tokens attributed to
35.70 seconds of subprocess execution. Final handoff tail and the prior blocked attempt
are separate, not zero. At the committed checkpoint the resumed native session reports
**187893 new input /9046656 cached input /25794 output /6342 reasoning tokens**,109
tool calls,63 API requests; reasoning is reported separately, not added to output.
The earlier blocked session separately reports118145 new /911104 cached /2819 output,
46 tool calls. These are raw runtime counters, not a synthetic Claude transcript.
The subprocess runner makes no model/API calls. No invoice
exists; subscription quota is not converted into fabricated dollar costs.

Executable-file/line inventory (including ignored census and inline payloads) is
written for this pilot: **8 executable files /497 physical lines**, including
ignored census/report scripts; shared-atlas modifications and nine inline `-c`
payloads are separately counted in the retained inventory. New code is well above the ~0 target: compatible-master preparation,
R1 recipe adapter, instrumentation and layout compatibility were missing. This is
engineering calibration, not evidence that a cold other model can finish at zero LOC
or that the route improved speed/cost. Future repeats reuse these exact bytes.

## Verification

Tests-first `ab558a23`: new512/8 layout regression fails1, existing/edge controls
pass11; after fix the initial12 pass. Extended affected set213 pass/1 skip;
preflight decisions/layout/Blender-doc/derivation83 pass. Final exact-head full-suite
receipt and hostile-probe witnesses are in the PR, not inferred from these counts.
