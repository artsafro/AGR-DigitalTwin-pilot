# Skolkovo L4 — resume v007

**Partial source intake; passed=false, buildable=false. No Gate 1, build or PR.**

## Decisions applied

Artem's 2026-10-21 task comment 12:00 answers v006: source-profile simplification of
108 separately exported KNS components is authorized, silhouette <=0.02 m, target
10,000 triangles. Five primary source mast meshes and their FBX positions remain
unchanged; only proven coincident surfaces may be removed. Existing exterior-only /
opaque-glazing, preserve-FBX-versus-PDF, VPM appearance-only and Drive/no-LFS decisions
remain in force. None is exact-hash Gate 1.

The policy/data draft now separates five `keep` primaries (55,230 source triangles)
from 108 `contour_rebuild` components (10,000 allocated triangles). Per-component
allocation uses deterministic source-triangle weights/largest remainder, not a claim
of measured output or feasibility. All 32,961 source references remain unique and
accounted for; no source member is silently dropped to fit the budget.

The generated **46-part diagnostic** validates via `dt_ai.core.models.PartsList`:
allocation **146,750**, master ceiling **150,000**, reserve **3,250**. It is deliberately
NOT final: joints are still empty and face/legend mappings remain proposals. Do not
ask the user to approve its hash as Gate 1. Large CSV/PartsList stay on Drive.

Policy regression, written and exercised before changing the data:

```text
uv run python tmp/l4_cleanup_policy_probe_v007.py <decisions.csv.gz>
```

Old v006: **6/10 pass, 4 fail, exit 1**. Updated v007: **10/10 pass, exit 0**.
This fixes recording of the authorized policy, not source topology or a model.

## New decision needed: primary source topology

Read [PRIMARY-MAST-TOPOLOGY-QUESTION-v007.md](PRIMARY-MAST-TOPOLOGY-QUESTION-v007.md).
Read-only public BODY-J/V004 audit finds **1,302 / 1,307 / 1,307 / 1,296 / 1,292**
duplicates+self-intersections in the five individual unchanged meshes, against
**100 per mesh**, tolerance **0.002 m**. This is not just 58–64 duplicate triangles.
The first source mesh alone has 1,122 piercing and 32 edge-on-plane pairs.
Six original face pairs have independent strict-crossing witnesses and six translated
clean controls reject them. Exact identities, coordinates and source hashes are in
committed JSON. No cleanup, rescale, replacement, model partitioning or waiver was
silently applied. Need permission for source-bound topology repair of these five,
or keep their explicit failed quality status. The 108-component decision does not
resolve that contradiction. This is a model-policy question, not a DCC crash.

## Preflight attempts preserved, not promoted to successful output

1. World-axis straight contour prisms: only **5/108** components pass the conservative
   `0.0199 m` buffered-region test in all three cardinal projections. With source
   fallback, analytical count **88,708**, versus 90,168 input / 10,000 target.
2. Connected-source components + PCA-aligned prisms: analytical count **85,212**
   with source fallback, still not 10,000. Small connector parts are reducible;
   bases, extenders and receptor heads need richer, varying source profiles.

These are analytical 2D projected-prism diagnostics, not created 3D output meshes,
kernel operations, arbitrary-angle/surface-distance certificates or achieved budgets.
No production build was attempted before Gate 1. Their poor counts do not prove all
allowed source-profile methods impossible; they cannot justify dropping members.
The newly discovered immutable-primary conflict needs user permission independently
of further 108-component algorithm experiments.

Revision legend was re-read on album p15 and revision p1 images: revision profiles /
flashings / reveals and plinth use RAL7015. F.9 lamellae have no explicit lamella /
RAL6018 source name/material; this is a retained mapping-audit item, not permission
to assign the first panel slot or omit source geometry. Previously authorized VPM
appearance-only associations remain provisional, not final material QA.

## Tests and evidence integrity

Focused command:

```text
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run --extra pdf-review pytest -q -p no:cacheprovider tests/qa/test_topology.py tests/test_album_pdf_reader.py tests/test_album_below_line.py tests/parts/test_fbx_reader.py --basetemp=C:/x/t_b205c8e1-resume-v007
```

**311 passed in 15.62 s**. No full suite: incomplete production gates; reserve it for
the first complete review head through `suite_slot.py` (rule49). CI: not run (billing
lock). No production modules or new libraries added. No Blender/Max/Revit launched;
all run-owned Python diagnostic processes completed.

**104/104** original inventory files and **113/113** mast buffers rehashed unchanged.
Drive final directory: `G:/Мой диск/AGR-evidence/353-skolkovo-l4/evidence-v007b/`.
Index: `evidence-v007/index.json`. ZIP **2,542,552 bytes**,
SHA-256 `d3ee69b77d025f29e86def9e83e0cfd10b8f701e24553f6ddb3b61cf40219dfd`;
CRC + **135/135** internal hashes verified, **4/4** published Drive artifacts rehashed.
`SHA256SUMS.txt` SHA-256:
`7082553456251c52606cc11ca36b9f44d11abe1e9ba30b4199d56ab57a203f6a`.

Storage self-repair: direct ZIP writing to Drive v007 initially raised `BadZipFile`
on immediate reopen. A later read saw a valid 2,542,333-byte ZIP (SHA-256
`b2f2d4f3b8f91d48023219f5fc40e0e7439236c3bbc418e96058e0dbf79d529d`).
Preserved that failed publication attempt; final v007b was staged/CRC+member-verified
locally, then copied to a new Drive directory and independently reopened/hashed.
Do not reuse the initial v007 ZIP as the final evidence index.

## Partial L5 timing (not total production throughput)

| Measured pre-Gate1 operation | Seconds | Hours |
|---|---:|---:|
| World-axis profile feasibility | 116.9713974 | 0.0324920548 |
| Connected-component PCA profile feasibility | 33.3583195 | 0.0092661999 |
| Five raw primary mast topology audits | 83.7750649 | 0.0232708514 |
| Independent witness extraction/recheck | 16.8488351 | 0.0046802320 |
| Focused tests | 15.62 | 0.0043388889 |
| Successful packaging/integrity (nested total) | 0.9489323 | 0.0002635923 |

Older source/album timings remain in v001–v006. Kernel/build/export/visual/final
SINTEZ remain **not measured**, not zero. Do not add nested diagnostic timings as
independent complete production stages.

## Resume after the answer

1. Do not reopen interior, PDF/FBX authority, material authority, storage or 108-KNS
   permission. Apply only the exact primary-topology answer to job policy.
2. Finish source-bound profile strategy/count feasibility, source face scope,
   explicit legend/material mappings and real joints. Keep raw failed evidence.
3. Final source-complete, schema-valid PartsList exact hash -> Artem Gate 1.
4. Kernel operations/all applicable invariants -> versioned export/readback ->
   delivered comparison -> board-tool/user visual approval -> final complete SINTEZ.
5. One full suite via suite_slot, author receipts, one PR, dt-reviewer. No PR yet.
