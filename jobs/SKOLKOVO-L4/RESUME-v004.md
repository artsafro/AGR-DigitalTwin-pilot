# Skolkovo L4 — exterior-policy application and source diagnostics

Run 988 resumes the work left uncommitted by crashed run 981. This is **partial
intake, not L4 completion**, no generated building. `passed=false`. Main checked:
`896fcef` has no `jobs/SKOLKOVO-L4` and issue #353 remains open.

## Resolved policy, new source decision

Artem's exterior-only/opaque-glazing decision is recorded in
[DECISION-2026-10-21.md](DECISION-2026-10-21.md). The older interior question in
`RESUME-v002.md` is historical and answered. Scope remains this building, no Ground,
site fence, MAF/Flora libraries, second building or live Revit/Max edits.

A **different source question** now needs a decision: revision PDF physical page 3
labels M4 h=8 m / M5 h=12 m while two similarly positioned roof-FBX families are
named 10.4 m. Full measured facts and qualifications, drawing crop and the exact
question are in [SOURCE-QUESTION-v004.md](SOURCE-QUESTION-v004.md). Do not silently
choose between sources, equate an assembly bbox with pole length, or assert an
unverified M4/M5 identity. Production has not crossed the parts gate.

## What actually ran

1. Run 981 prepared a proposed grouped subset and per-object table across v1,
   September facade and September rods. **32,961 unique source rows**: 17,710 /
   11,510 / 3,741. All classifications are proposals, not approved drops.
2. Read-only Max 2026.3 imported staged FBXs and dumped source meshes for scope
   diagnostics. Application version, blank reset document and metre units are in
   the logs. No building master was generated; the live Max document was untouched.
3. **Repair #1, witnessed on real data:** the first dump applied `objectTransform`
   a second time after `snapshotAsMesh`. An independent node-bbox comparison rejects
   **11,510/11,510 objects**, max residual **62.105052948 m**. Raw old dump remains
   local for reproduction. Corrected world-space vertices pass **11,510/11,510**,
   max residual **0.0 m**, tolerance 0.0001 m, same **1,146,519 triangles**.
   Binary lengths, vertex/face counts, finite coordinates, index ranges and unique
   dump indices/files were checked too. Bbox parity does not verify face winding,
   topology, materials, UV, part identity across different imports or architecture.
4. Rasterized the corrected **raw source**, 5 cm grid, six cardinal views.
   **3,216 objects** receive at least one sample in four elevations or the top
   view (the underside is separately stored). Five retained PNGs show the source
   silhouette, roof screen, panel pattern and entrance recesses. Object colours
   are deterministic diagnostic colours, NOT a material legend. No sample is not
   proof of hidden geometry; diagonal/recess visibility, tiny details and interior
   leaks are not certified. Do not delete objects based on these samples.
5. Five roof-mast assemblies have finite vertices and exact independent bbox
   parity. Retained measurements support a source question, not an operation or
   lightning-protection calculation. No DCC run was repeated during run 988.
6. **Repair #2, witnessed on real data:** a verification assumption that display
   names are unique failed. Corrected checks identify **31 duplicated names /
   409 affected rows** in the facade census. The grouped subset used 5,267
   name-only references but only 4,987 unique names (RED). New v004 references pin
   the exact census hash and `objects/<row>` locator: **5,267/5,267 unique (GREEN)**,
   with all **32,961/32,961** table rows uniquely addressable. Never re-key the
   table or visibility data by display name. This repairs draft identity only;
   it is not whole-building source-coverage acceptance or kernel code change.
7. All **104/104 original inventory hashes unchanged**. The four Max-extracted
   files already reported by run 974 are not original inventory entries; no claim
   that they were removed is made. Current staging stays in the worktree.

## Candidate subset — deliberately not buildable

`evidence-v004/parts-subset-v004.json.gz` (decompress before reading) validates through the public
`dt_ai.core.models.PartsList` facade. It remains `status=draft`, `gate1=null`.
Its **20 groups / 81,496 target triangles** are an allocation, NOT a measured
master or a whole-building budget pass. Source triangles assigned to these proposed
groups total **221,492** before any operations. No output triangle count exists.

`object-decisions-v004.csv.gz` records source/row/name, operation, legend candidate,
target budget and reason for each input object. Original v1 rows remain baseline,
not blanket deletion: revision supersession still requires reconciliation.
**1,695 facade rows remain review**, including possible exterior soffits/entrances
versus interior/substrate. Source-name heuristics and axis-rectangle door/railing
classification remain unapproved. Material IDs are not mapped by fallback; per-part
joints are not approved. Several proposed legend tokens are placeholders, not
confirmed album mappings. The 20-group subset must NOT be presented for final
Gate 1 as though all source objects had dispositions and budgets.

The schema can validate an incomplete draft; that does not authorize a build.
No kernel operation, invariant receipt, geometry fix, final export, UCX, derivation,
visual approval or SINTEZ receipt is produced here.

## Real verification and timings (L5 partial baseline)

| Activity | Seconds | Hours | Meaning |
|---|---:|---:|---|
| Initial v1 structure read (prior run) | 1388.938926 | 0.385816368 | Actual source reader |
| C5 read/serialize/render 30 pages (prior run) | 50.954157 | 0.014153933 | Not human interpretation |
| Corrected facade Max batch wall (run 981) | 117.0 | 0.0325 | Includes startup/import/dump/shutdown |
| Corrected source raster diagnostic | 24.463990 | 0.006795553 | Not a building render |
| v004 independent probes | 4.308805 | 0.001196890 | Includes old/new dumps and input hashes |
| Focused reader tests | 5.02 | 0.001394444 | 133 passed |

Do not add nested per-file reader time to batch wall time. Failed launches and the
bad dump are rework, not useful production throughput. PartsList authoring,
manual interpretation, source-choice waiting, operations, final export/readback,
visual review and SINTEZ durations remain **not measured**, not zero. L5 is not complete.

Executed commands:

- `uv run python tmp/l4_source_raster_v003.py` — exit 0, bbox 11,510 verified,
  813,047 vertices / 1,146,519 triangles; raster completed in 24.463990 s.
- `uv run python tmp/l4_verify_v004.py` — first exit 1 on a false name-uniqueness
  assumption, then exit 0 after using unique census indices; the corrected run
  explicitly requires the bad transform dump to fail and corrected dump to pass.
- `uv run python tmp/l4_package_v004.py` — exit 0; old duplicate-reference witness
  fails; v004 unique references and Pydantic checks pass; ZIP CRC verified.
- `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run --extra pdf-review pytest -q -p no:cacheprovider tests/test_album_pdf_reader.py tests/test_album_below_line.py tests/parts/test_fbx_reader.py --basetemp=C:/x/t_b205c8e1-resume-v004`
  — **133 passed in 5.02 s**. No production-code RED/GREEN claim is made.
- An optional standalone JSON Schema validation probe could not import `jsonschema`
  in this environment. No dependency was installed (new libraries are out of scope).
  Only the executed public PartsList/Pydantic validation is claimed for v004.

Full suite still reserved for the first complete review head (rule 49), through
`suite_slot.py`; no incomplete intake PR was opened. No new shared Python module
or library added; all ad-hoc drivers remain in the versioned local evidence ZIP.

## Durable and local evidence

`resume-evidence-v004.json` pins committed evidence hashes and a local **1,468,016-byte**
ZIP, SHA-256 `05096e0af154b5c7fceea23a05a9d86a45c3da428d4dfbd8ffb19f891dd7cd52`.
Final packaging: `uv run python tmp/l4_finalize_v004.py`; gzip preserves the draft
without a 20k-line JSON diff. Job-local ignore exceptions include PNG/gzip evidence;
`.gitattributes` preserves exact evidence bytes rather than CRLF-normalizing hashes.
Small supporting fix: root `.gitignore` adds two exact job-local metadata exceptions;
only this job's child ignore file opts in PNG/gzip. Six PNGs retain repository LFS
storage, with pointer OIDs/sizes verified against actual evidence bytes. Raw FBX,
mesh buffers and delivery outputs remain local. No global ignore/attributes changed.
ZIP has the data, question/policy, sheet, drivers and Max run logs; no supplied FBX or mesh binary is
embedded. Correct/incorrect raw diagnostic binaries remain in
`tmp/skolkovo-l4-v003/source-geometry-v002/` and `source-geometry/`; these are source
diagnostics, not exported delivery artifacts. The old manifest/dump is used only
as a rejected witness. The corrected manifest and visibility data are compressed
in the committed evidence folder. The source question sheet is a drawing crop plus
facts, not the post-build board review required by D119/D125.

## Publication blocker

The push of local commit `5ae00b7` failed before updating the remote branch:
`This repository exceeded its LFS budget. The account responsible for the budget
should increase it to restore access.` LFS uploaded **0/6** objects. This is an
external repository quota, not a geometry/test failure. The source question PNGs,
compressed tables and portable ZIP remain intact in this worktree. No LFS skip,
quota bypass, history rewrite or alternate branch was attempted. Restore the LFS
budget/access before pushing this history; the source-choice answer is separately
needed before final PartsList/build. No PR or review request is claimed.

Next: answer the source-choice question; finish per-object exterior/supersession,
legend and joint decisions; obtain user Gate 1 on the exact final PartsList hash;
then kernel/invariants, master budget, versioned export/readback, delivered-reference
comparison, board-tool visual/user verdict, final SINTEZ and stage timings.

Transcript: Hermes session `local-3bbcf11e2aac40ab9c6f049126089e2f667d5f16eaeb8bdb656a7d82c28259bc`,
card `t_b205c8e1`, run 988; predecessor run 981 crashed during source diagnostics.
