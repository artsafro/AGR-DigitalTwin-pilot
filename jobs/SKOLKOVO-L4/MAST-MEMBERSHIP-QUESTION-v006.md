# Skolkovo: full mast-system membership and bounded cleanup

Status: **needs a model/scope decision**, not Gate 1. The earlier choices remain:
FBX geometry/placement rather than PDF-derived rescaling, exterior-only/opaque
glazing, and VPM appearance-only authority. None is reopened here.

## Exact question

May the **108 separately exported `КНС_*` mast components** be simplified from
their source contours/profiles, with source dimensions/placement retained and
maximum silhouette deviation **0.02 m**, while keeping the five parent-like
`Молниеприёмник*` meshes unchanged? Recommendation: budget these extra components
at **10,000 triangles**, keep all five parent-like meshes at **55,230**, and
remove only independently proven coincident duplicate surfaces. This is a
proposed budget, not a measured or guaranteed output.

Alternatively, if complete unchanged geometry of all 113 meshes is required,
please explicitly choose that scope; it leaves only **4,602 triangles** for the
rest of the 150,000-triangle master before any cleanup, and the current building
proposal cannot be approved. Do not silently drop the extra components or raise
the master limit. A narrower intended source membership needs exact exclusions.

The five separate ESE receptor meshes near the **base**, as well as five at mast
tops, are source facts, not proven export mistakes. The recommended cleanup does
**not** authorize deleting those shifted meshes by calling them duplicates.
No source or production geometry was modified to make this question disappear.

## Why the old 55,230 budget was incomplete

The old draft kept only names starting `Молниеприёмник`; it incorrectly described
all other nodes in this FBX as unrelated architecture. The native census actually
contains **113 mast-related meshes**, all with `parent=null`:

| Family | Meshes | Source triangles |
|---|---:|---:|
| Five parent-like mast meshes | 5 | 55,230 |
| Concrete bases `КНС_ОсновниеБетонное...` | 40 | 17,520 |
| Other `КНС_*` bases, extenders, connectors and heads | 68 | 72,648 |
| Total | 113 | 145,398 |

The separately exported components are not all contained within those five
parent-like meshes. For example, zero-based rods census row **3628**, element
`6631253`, spans Z **11.9350004–23.6399994 m**; separate concrete base row **3629**,
`6631254`, spans Z **11.75–11.9300003 m** and extends beyond its XY boundary.
ESE rows **3641** (`6631266`) and **3643** (`6631268`) have similar shape but
separate Z ranges **11.75–12.1289997 m** and **23.2609997–23.6399994 m**.
Their different positions are not a triangle-duplication proof.

Source FBX SHA-256:
`f2167c8f48537cfaeaeab3bdad6a81ca1822b86029a1da4c473ec643312ac23e`.
The full native dump pins row, name, binary SHA-256 and independently checked
world bbox for **113/113** meshes. The earlier PDF/FBX height discrepancy remains
resolved in favour of FBX; this is newly established component membership.

## Self-repair investigated before asking

1. **Exact surface duplication diagnostic:** 145,398 input triangles contain
   **2,856** repeated unordered triangles; **142,542** distinct triangles remain.
   Across-object duplicate groups: **2,088**. This is a read-only count, not a
   performed deletion, material-equivalence proof or topology pass.
2. Quantizing positions to **0.00001 m** and **0.0001 m** finds the same counts;
   tolerance inflation does not justify treating shifted bases/heads as duplicates.
3. **Strict planar-retessellation feasibility:** per-object coplanar union with
   maximum allowed plane residual **0.0000001 m**, exact zero-tolerance removal of
   collinear projected vertices, retains nonplanar/invalid groups unchanged.
   Resulting count bound **140,371**; maximum accepted residual
   **0.00000003886444233103248 m**. This is neither an achieved mesh nor a lower
   bound on every possible future algorithm. It is not combined arithmetically
   with the duplication count, and does not establish an impossible global limit.

The current non-mast source-scope proposal allocates **81,520 triangles**.
Correcting membership without silently simplifying the extra geometry raises
its total to **226,918**. `dt_ai.core.models.PartsList.model_validate` rejects it:
`npm: part budgets add up to 226918, over the total 150000`.
This demonstrates that the current plan is invalid, not that all other possible
plans are impossible. A much leaner building plan would be a separate design
trade-off, not a fabricated budget pass.

The recommended 10,000-triangle extra-component allocation would make the
**proposed** total **146,750**, still subject to actual operations, source/face
and joint reconciliation, invariants, readback and both user gates.

## Review evidence

Drive: `G:/Мой диск/AGR-evidence/353-skolkovo-l4/evidence-v006/`.
Open **`mast-system-question-v006.png`**: actual source triangles of the first
mast family, orange parent-like mesh and blue separate KNS components, with top,
side and enlarged base views. This is a **source question**, not a building output,
Face Orientation result, board-tool visual approval or Gate 1.

`SHA256SUMS.txt` and the committed `evidence-v006/index.json` pin the sheet,
complete raw mast-system/source diagnostics, drivers, data probes and logs.
The v005 membership regression fails **3/8** checks (108 missing rows); the corrected
conservative keep proposal passes **8/8**, while honestly failing the master budget.

After the answer: apply only the approved extra-component policy, finish the
source/face/material/joint and budget reconciliation, then request Gate 1 on the
exact final PartsList hash. No current rejected draft is suitable for approval.
