# Skolkovo — primary mast topology decision (v007)

**Needs user input. Not Gate 1; no building was built.**
The 108-component simplification decision is recorded and is not being reopened.
The question below concerns the **five explicitly unchanged primary meshes**.

## Exact question

May the five primary assemblies undergo **source-bound internal topology cleanup**
(remove proven duplicate/internal surfaces, resolve crossings and weld/retessellate
where needed), preserving supplied FBX placement, heights and exterior profiles,
without PDF rescaling or replacement masts? Or must they remain literally unchanged,
with their BODY-J/V004 failures explicitly retained and delivery not passed?

**Recommendation:** authorize the source-bound topology-cleanup route, not a quality
waiver or global threshold increase. Any changed allocation/operation still belongs
in the final PartsList for exact-hash Gate 1 before production. This is not a request
to approve the current incomplete diagnostic PartsList.

## Why the previous answer cannot answer this

Artem's task comment 2026-10-21 12:00 authorizes bounded simplification of 108
separately exported KNS components, silhouette <=0.02 m and target 10,000 triangles.
It separately states that the five primary meshes and their FBX positions do not
change. Repairing those five or treating their quality failures as passes is not
silently included in the 108-component permission.

The unchanged source geometry was checked read-only with the public
`twinqa.geometry.topology.count_defects` at `tol=0.002` m. BODY-J/V004 allows at most
100 duplicates plus self-intersections **per mesh**, not 100 duplicate triangles
alone. Each primary mesh individually exceeds 100:

| Rods census row (0-based) | Source triangles | Duplicate vertices | Duplicate edges | Duplicate polygons | Self-intersections | Combined defects |
|---|---:|---:|---:|---:|---:|---:|
| 3628 | 11,098 | 36 | 48 | 64 | 1,154 | 1,302 |
| 3651 | 11,940 | 38 | 48 | 64 | 1,157 | 1,307 |
| 3674 | 11,940 | 38 | 48 | 64 | 1,157 | 1,307 |
| 3697 | 10,114 | 36 | 48 | 58 | 1,154 | 1,296 |
| 3719 | 10,138 | 32 | 48 | 58 | 1,154 | 1,292 |

Isolated vertices/edges/polygons and zero-length edges are zero in this diagnostic.
This is raw source QA, not a final SINTEZ run, native Max xView receipt or kernel
operation receipt. Moving crossings between separately named output meshes to hide
a per-mesh counter would not establish correct geometry or kernel invariants.

## Independent witness, not only an aggregate counter

- Primary row 3628, original source faces **3823/6079** (0-based).
- One source edge crosses strictly inside the other source triangle; endpoint
  signed distances to its plane are `+0.05877485025508179` and
  `-0.01594499920341098` m, not a merely coincident triangle.
- Intersection point in the original rods frame:
  `[-7.505350553351109, 64.42371391940462, 13.19002478900021]` m.
- Six original face pairs have independent line/plane + barycentric witnesses
  with both endpoint distances >0.002 m and strictly interior barycentrics.
  The corresponding translated clean controls reject all six crossings.
- On the first complete mesh the checker reports 1,122 piercing pairs plus
  32 edge-on-plane pairs, totaling 1,154 self-intersections. Six witnesses do
  not independently certify all 1,154 pair classifications.

The small audit and witness JSON files pin all five source-buffer hashes and the
source FBX SHA-256
`f2167c8f48537cfaeaeab3bdad6a81ca1822b86029a1da4c473ec643312ac23e`.

## Evidence and reproduction

Drive: `G:/Мой диск/AGR-evidence/353-skolkovo-l4/evidence-v007b/`.
Question sheet: `primary-mast-topology-question-v007b.png` (source faces only).
Archive: `source-diagnostics-v007b.zip`, SHA-256
`d3ee69b77d025f29e86def9e83e0cfd10b8f701e24553f6ddb3b61cf40219dfd`.
The archive preserves 113 raw mast buffers, manifest, census, diagnostics and
job-only drivers; its 135 members and CRC were checked. It contains no fabricated
building FBX, no changed source FBX and no user approval.

Extract into an isolated copy of the same worktree layout and use fresh versioned
output paths; drivers deliberately refuse existing output files. Run:

```text
uv run python tmp/l4_primary_mast_audit_v007.py
uv run python tmp/l4_primary_mast_witness_v007.py
```

Focused topology + FBX/C5 tests: **311 passed in 15.62 s**. No checker code, tolerance,
source buffer, live DCC scene or official limit was modified. The two read-only
108-component profile preflights do not solve or authorize repair of these five.
