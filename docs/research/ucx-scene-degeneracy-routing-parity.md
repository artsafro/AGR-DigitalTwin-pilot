# UCX scene degeneracy routing parity

## Summary

- Source pinned to `fc0a1fea4589ca48a59db6534a100f2fad87f517`; initial worktree status/diff were clean.
- **Yes: the raw review/count is absent on the scene route**, which does not call `classify`.
- A repeated-index extra triangle disappears during weld; scene SAT then measures the intact box.
- That does **not** erase all defect evidence: V004 reports its zero-length edge as `fail`.
- A nonzero-volume box with a retained collinear extra triangle is unsupported (`open`), not saved by volume alone.
- With separated bounding boxes, unsupported intersection coverage passes legitimately; gap measurement remains `not_run`.
- Face-split vertices and positive-area weld-collapsed triangles demonstrate normalization, not raw-area-policy equivalence.
- Own verification: 6 inventories, 12 public scene observations; no geometry-call exceptions; no pytest or package validation.
- Report only: **`delivery_passed=false`**. No policy change or claim that an entire delivery falsely passes.

## Findings with sources

### Scope, source claims and independently observed routing

The source below means the pinned tree, not a moving main branch. Relevant immutable browser anchor: [scene.py at the pinned SHA](https://github.com/artsafro/AGR-DigitalTwin-pilot/blob/fc0a1fea4589ca48a59db6534a100f2fad87f517/src/twinqa/scene.py#L165).

**External source claim:** [PR #466](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/466), retrieved read-only through [GitHub API](https://api.github.com/repos/artsafro/AGR-DigitalTwin-pilot/pulls/466), says `classify` now reviews raw degenerate triangles and leaves measurement helpers unchanged. API reports merged at `2026-10-21T10:02:22Z`, merge SHA `373367dd5a6df4fb22885280531258612df63f71`. Its out-of-scope note says scene is already protected by the volume fallback. Its historical test totals are author receipts, **not tests executed here**. The [PR files endpoint](https://api.github.com/repos/artsafro/AGR-DigitalTwin-pilot/pulls/466/files) shows changes only to `ucx_audit.py` and `test_ucx_audit.py`.

**Own verification:** the claim about raw `classify` behavior holds for the frozen corpus. The scene protection claim needs qualification: zero volume protects the existing tetra; the nonzero-volume collinear witness is protected by **edge closure**, not volume. Repeated-index evidence is dropped before the scene support decision but survives independently in topology. No new NaN-area corpus was run; #460's fixed overflow examples are not repeated.

Local citations (all at the pinned SHA):

| Source | Routing fact |
|---|---|
| `src/twinqa/geometry/ucx_audit.py:53-68` | Weld quantizes coordinates with `round(c/tol)`, default `1e-5`, and drops remapped triangles with fewer than three distinct indices. It is not a Euclidean-distance weld and returns no provenance/drop list. |
| `src/twinqa/geometry/ucx_audit.py:71-94,140-162` | Raw repeated-index/area inventory precedes weld in `classify`; review carries count/first five, raw V/F counts and null closed/convex. Clean classification returns no `status` key. |
| `src/twinqa/geometry/ucx_audit.py:106-126` | Closure counts edge uses; convexity skips null planes. Neither standalone measurement adopts the raw-review policy. |
| `src/twinqa/scene.py:165-191` | `_ucx_piece` welds first; closure, convexity and volume determine support. No raw inventory/classify call. |
| `src/twinqa/scene.py:216-278` | Pair routing: distant bbox skip, unsupported pair accounting, SAT, distance, independent intersections/coverage/advisory statuses. |
| `src/twinqa/geometry/ucx_audit.py:342-375,397-461` | `_unmeasurable`, `pair_findings`, `collision_findings` do not call `classify` or weld; raw and explicitly welded inputs need not route alike. |
| `tests/qa/test_ucx_audit.py:161-211` | Existing tetra, on-face sliver, repeated-index and clean controls (read, not executed). Our repeated triangle is appended, not the test's replacement of the last box face. |

### Frozen geometry and independent expectations

Before any standalone geometry call, froze exactly the six inputs reproduced below. All are **synthetic**, metres, zero-based triangle indices. Start with the unit box `[0,1]^3` and its 12 outward-wound triangles. `collinear` adds `(0.5,0,0)` and `(0,8,4)`; its three indices and positions are distinct. `repeated` **appends** `(0,0,1)`, leaving every box face intact. `weld_only` adds `(1e-6,0,0)` and `(0,8,2)`; its raw area is `5e-7 m²`, above `1e-10`, but vertices 0 and 8 quantize to one weld key. `split` copies every triangle corner into separate indices (36 vertices), without any degenerate raw triangle.

For each first hull A, B is a second clean unit box translated along X:

| Placement | B bounds | Independently derived geometric expectation (not a helper verdict oracle) |
|---|---|---|
| overlap | `[0.5,1.5] × [0,1] × [0,1]` | Box volumes overlap with axis penetration `0.5 m`; extras do not change the intact box's extent. For tetra, only planar contact/extent exists: it is not a volumetric collision hull. |
| gap | `[1.02,2.02] × [0,1] × [0,1]` | `1.02 - 1 = 0.02 m`; nearest points can share Y/Z for every input, including tetra vertex `(1,0,0)`. Bboxes prove separation. The known 20 mm distance is outside the 2–10 mm band and within 100 mm neighbour range. An unsupported surface need not be measured by the checker. |

No policy-equivalent dictionary comparison is used: `classify` is a piece diagnostic; pair support and pair findings have different inputs and contracts.

### Exact piece outcomes

`D` lists every raw/post-weld degenerate index in this corpus, not just the first five. V/F counts are vertices/triangles; volume is scene's post-weld absolute tetrahedron sum.

| Input | Raw V/F | Raw D | Weld V/F | Weld D | Volume m³ | `classify` output code | Scene piece `reason` |
|---|---:|---|---:|---|---:|---|---|
| clean | 8/12 | `[]` | 8/12 | `[]` | 1.0 | B | `None` |
| tetra | 4/4 | `[1]` | 4/4 | `[1]` | 0.0 | R(4,4,1) | `degenerate` |
| collinear | 9/13 | `[12]` | 9/13 | `[12]` | 1.0 | R(9,13,12) | `open` |
| repeated | 8/13 | `[12]` | 8/12 | `[]` | 1.0 | R(8,13,12) | `None` |
| weld_only | 9/13 | `[]` | 8/12 | `[]` | 1.0 | B | `None` |
| split | 36/12 | `[]` | 8/12 | `[]` | 1.0 | B | `None` |

Exact dictionary expansion:

```text
B = {"kind":"box_aabb","closed":true,"convex":true,"verts":8,"tris":12}
R(V,F,I) = {"kind":"custom","closed":null,"convex":null,"verts":V,"tris":F,
            "status":"review","degenerate_triangles":{"count":1,"triangles":[I]}}
```

For `collinear`, two new edges have one use and box edge `(0,4)` gains a third use. The zero-area face survives weld, so closure fails even though its enclosed volume remains 1. For `repeated`, the raw review cannot appear in V010 because the offending face no longer exists in the hull tested there. For `weld_only`, **both** classify and scene normalize it: this is outside the raw degeneracy inventory, not a regression of #460's area gate.

### Exact public scene outcomes

I = `UCX intersections`; C = `UCX intersections coverage`; G = `UCX piece gap (advisory)`. The following are finding statuses, not stage or delivery verdicts.

| Input | Placement | I | C | G | Gap counts `(touch,below,in,wide,unmeasured)` | Evidence code |
|---|---|---|---|---|---|---|
| clean | overlap | fail | pass | pass | (0,0,0,0,0) | O |
| clean | gap | pass | pass | review | (0,0,0,1,0) | W |
| tetra | overlap | not_run | not_run | not_run | (0,0,0,0,1) | U(degenerate) |
| tetra | gap | pass | pass | not_run | (0,0,0,0,1) | S |
| collinear | overlap | not_run | not_run | not_run | (0,0,0,0,1) | U(open) |
| collinear | gap | pass | pass | not_run | (0,0,0,0,1) | S |
| repeated | overlap | fail | pass | pass | (0,0,0,0,0) | O |
| repeated | gap | pass | pass | review | (0,0,0,1,0) | W |
| weld_only | overlap | fail | pass | pass | (0,0,0,0,0) | O |
| weld_only | gap | pass | pass | review | (0,0,0,1,0) | W |
| split | overlap | fail | pass | pass | (0,0,0,0,0) | O |
| split | gap | pass | pass | review | (0,0,0,1,0) | W |

Exact observed-string templates, substituting `A=UCX_SM_A_Main_001`, `B=UCX_SM_A_Main_002`, `src=SM_A.fbx` (A/B are substituted inside the quoted tuple/list strings):

```text
O.I: src: 1 overlapping pair(s): [('A', 'B', 500.0)]; unresolved pairs: 0
O.C = W.C = S.C: src: every neighbour pair evaluated
O.G: src: touch=0 below_band=0 in_band=0 wide=0 unmeasured=0; []
W.I = S.I: src: no overlapping pairs among 2 pieces
W.G: src: touch=0 below_band=0 in_band=0 wide=1 unmeasured=0; [('A', 'B', 20.0)]
U.I: src: 1 unresolved pair(s)
U.C: src: 1 unresolved pair(s); unsupported: ['A (REASON)']
U.G = S.G: src: touch=0 below_band=0 in_band=0 wide=0 unmeasured=1; []
```

I/C passing for S means **intersection ruled out by bounding boxes**, not supported hull geometry. Here the named unsupported reason is absent from all V010 findings; the remaining specific evidence is `unmeasured=1` in G. Generic `UCX shape and coverage` also remains `not_run`, but does not identify the defect. This distinction is intentional in the existing pair routing (`scene.py:236-243,264-277`), not evidence of delivery acceptance. Conversely a G pass for O says no offending *gap* was measured: it does not cancel I fail.

### Other helper outcomes: normalization versus unsupported evidence

The snippet also invokes `pair_findings` on raw A and on explicitly welded A; B is clean in both calls. Exact outputs can be expanded from these codes:

```text
N(r) = [{"type":"not_run","req":"2.13.4","reason":r,"hull":"A"}]
P = [{"type":"intersect","req":"2.13.4","gap_m":0.0,
      "penetration_m":0.5,"a":"A","b":"B"}]
Q = [{"type":"gap_out_of_band","req":"2.13.4","gap_m":0.020000000000000018,
      "penetration_m":0.0,"a":"A","b":"B"}]
```

| Input | Raw overlap / gap | Welded overlap / gap |
|---|---|---|
| clean | P / Q | P / Q |
| tetra | N(degenerate) / N(degenerate) | N(degenerate) / N(degenerate) |
| collinear | N(open) / N(open) | N(open) / N(open) |
| repeated | N(open) / N(open) | P / Q |
| weld_only | N(open) / N(open) | P / Q |
| split | N(open) / N(open) | P / Q |

`split` proves that raw-helper `open` versus scene support can be the required FBX normalization, not a bug. `repeated` demonstrates raw evidence loss at that same normalization step. `_unmeasurable` does not inventory degenerate triangles either; `collision_findings` calls it and then `pair_findings` without normalizing (`ucx_audit.py:432-461`, read-only trace, not separately executed). The Blender audit uses raw `classify` and stores its diagnostic alongside welded hulls; its pair loop calls **ungated** `pair_relation` rather than turning review into pair support (`tools/blender/ucx_audit.py:120-129,149-156,218-221`). It retains piece review but its pair figures are not a delivery verdict. No Blender invocation was made.

### Surviving evidence through all findings

Topology was calculated on the original synthetic triangles using `count_defects`, default `tol=0.002`, internal broad phase, no loose edges; **not fabricated as all-zero input**. These observations do not reproduce Blender's import/tessellation/BVH handling. Production readback measures original polygons and edges with Blender BVH candidate pairs, independently from the UCX loop-triangle hull (`tools/blender/fbx_readback.py:104-117,135-137`). The synthetic polygon list here equals the triangle list.

Topology tuple order: duplicate vertices, duplicate edges, duplicate polygons, self-intersections, isolated vertices, isolated edges, isolated polygons, zero-length edges, duplicates+self-intersections total. Exact own measurements:

| Input | Topology tuple | V004 `topology defects` in both placements | Specific surviving evidence |
|---|---|---|---|
| clean | (0,0,0,0,0,0,0,0,0) | pass | none |
| tetra | (0,0,0,0,0,0,0,0,0) | pass | V010 unsupported label only at overlap; gap unmeasured at both placements |
| collinear | (0,0,0,0,0,0,0,0,0) | pass | V010 `open` label only at overlap; gap unmeasured at both placements |
| repeated | (0,0,0,0,0,0,0,1,0) | fail | `UCX_SM_A_Main_001 (zero_length_edges=1)` |
| weld_only | (1,1,0,0,0,0,0,1,2) | fail | `UCX_SM_A_Main_001 (duplicates_and_self_intersections=2, zero_length_edges=1)` |
| split | (28,18,0,0,0,0,12,0,46) | fail | `UCX_SM_A_Main_001 (duplicates_and_self_intersections=46, isolated_polygons=12)` |

V004 pass observed text for the first three is `SM_A.fbx: max 0 duplicates/self-intersections, no isolated or zero-length elements`. Failure text is `SM_A.fbx: ['<specific surviving evidence>']`. `src/twinqa/geometry/topology.py:5-18,82-90,103-146` defines these counts; `scene.py:282-327` applies the duplicate ceiling and zero isolated/zero-length rule. A collinear face is not itself an explicit area diagnostic in that schema. The face-split control is geometrically clean and suitable for welded SAT but not topology-clean by these raw-index metrics. No normalization or acceptance-policy change is inferred from that difference.

All findings were inspected, including those outside V010. The synthetic readback contains **only two UCX meshes, no render target**, so many checks are vacuous; it cannot represent a complete delivery:

| Remaining public findings | Exact status/result in all 12 final scenes |
|---|---|
| V002 system units, scale 1:1 | pass; 100 cm per unit, every scale 1 |
| V003 triangulated, triangle count | pass; all triangles, 0 non-UCX triangles |
| V004 applied transforms, co-directional clearance | pass; rotation 0/scale 1; 0 non-UCX face pairs |
| V008 one UV channel, mirrored islands | pass; no non-UCX channel offenders, no mirrored UV |
| V010 UCX present, material slots | pass; 2 meshes, no slots |
| V010 triangle budget | pass; clean/split 24, tetra 16, others 25 UCX triangles for 0 model triangles, limit 15000 |
| V010 shape and coverage | not_run; `convex, closed, coverage, offsets` |
| V012 mesh names, UCX names | pass; `0 name(s) follow the grammar`, `2 name(s) follow the grammar` |
| V013 MSK-77 point | not_run; `GeoJSON point vs survey coordinates and project zero` |
| V006 | no findings |

Nothing elsewhere in these scene outputs restores #460's count/triangle-index review. The repeated case **does** retain a named, failing topology diagnostic; the unsupported separated cases **do** retain an unmeasured-gap signal. No full package was evaluated. `tools/qa/validate_package.py:145-168` appends scene findings rather than replacing topology with SAT coverage. `src/twinqa/report.py:8-9,35-39,56-59` ranks fail > review > not_run > pass and requires every blocking stage to pass; one helper or one coverage pass cannot establish package `passed=true`. Technical QA is distinct from manual/user delivery acceptance (`AGENTS.md`, Rules for every task; `docs/domain/areas/ucx.md`, R06/R09/R10 and current limitations).

### Exceptions and execution accounting

| Invocation | Exact exception/outcome | Interpretation |
|---|---|---|
| System `python -B -c "import twinqa; ..."` | `ModuleNotFoundError: No module named 'twinqa'` | Import setup only; not a geometry verdict. |
| System Python with `PYTHONPATH=src`, import scene/topology | `ModuleNotFoundError: No module named 'numpy'` | Existing system interpreter lacks project dependencies; no installation attempted. |
| Existing project venv Python, `PYTHONPATH=src`, `-B` | Imports OK; NumPy `2.5.3` | Used existing interpreter only; dependencies not changed. |
| Frozen inventories | 6/6 complete; classify 6/6 and scene piece 6/6 returned; 0 exceptions | Values above, not test GREEN. |
| Public scenes | 12/12 returned; 0 exceptions | Table above. |
| Raw/welded pair calls | 24/24 returned; 0 exceptions | Table above; unsupported is a returned finding, not an exception. |

First observation run used source label `SM_A_Main.fbx`, producing an unrelated V012 naming fail (`not UCX_SM_A_Main_Main_001..999`). Corrected **only the synthetic source label**, not frozen geometry, to `SM_A.fbx` per `src/twinqa/naming.py:7-10,43-51`; reran all observations. Tables record the final run. Both runs completed 6 inventories/12 scenes; counts are not inflated by reruns. No geometry failed and was silently discarded. Both probe processes exited 0.

RED: N/A (research); GREEN: N/A (research); full suite: N/A (research). No tests executed, written or changed. Invariant guarantees: N/A (no new implementation guarantees). Observation coverage -> frozen six-input corpus × two placements -> **12/12**, inventory capture -> **6/6**; these are not generated/exhaustive proofs of a universal degeneracy policy.

## How it applies (paths)

- Production package route: `tools/qa/validate_package.py:add_scene` -> `tools/blender/fbx_readback.py:mesh_facts` -> `scene.scene_findings` -> `_ucx_pair_findings` -> `_ucx_piece`. Raw topology and hull records are independent. UCX names select this route via prefix (`scene.py:389-390`); VPM non-light restriction is at `scene.py:429-448`.
- Measurement audit route: `tools/blender/ucx_audit.py` -> raw `ua.classify` plus welded pair/distance measurements. The diagnostic survives in `report['pieces']`; it is not a gate for its pair loop.
- Helper parity route: `tests/qa/test_ucx_parity.py:1-15,221-225` uses `ucx_audit`, not the public scene registry. Its passing historical receipts cannot establish scene-policy equivalence. Current runtime callers of `pair_findings`/`collision_findings` are within `ucx_audit`; `tools/sintez_parity.py:173,214` instead calls public `scene_findings`.
- Requirement index: `docs/domain/areas/ucx.md` R09 allows bounding boxes apart as intersection evidence; R06 hull geometry and final coverage remain distinct, incomplete checks. No changes to the index or procedure were made.

## Proposed next tasks (maximum two)

Read-only API equivalent of the prohibited `gh issue list --state open --label roadmap` was consulted: [open roadmap query](https://api.github.com/repos/artsafro/AGR-DigitalTwin-pilot/issues?state=open&labels=roadmap&per_page=100). It returned 8 issues: #426, #425, #371, #352, #349, #337, #298, #149. **Source claim:** [#149](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/149) is open, roadmap-labelled and names the public delivery-check seam and UCX L2 work. This is planning linkage, not evidence of geometry correctness. No dependency on or work toward active #480 or #462 is assumed.

1. **Public routing characterization for the six frozen witnesses** — value M / effort S; **Advances #149**. Input: `collinear + overlap B` -> expected I/C/G `not_run/not_run/not_run`, reason `open`; same A + 20 mm B -> `pass/pass/not_run`, `unmeasured=1`. Input: `split + overlap B` -> I fail with 500 mm, C pass; 20 mm B -> I/C pass, G review at 20 mm. Keep assertions on public outcomes and separate topology diagnostics, not dictionary equality across helpers. This proposed future test-only task documents existing behavior without changing eligibility, thresholds or recall.
2. **Decision-ready raw-versus-weld reporting/eligibility table** — value M / effort S; **Advances #149**. Input: appended repeated triangle -> expected decision brief explicitly contrasts current `classify=review,count=1`, supported welded SAT and V004 zero-length fail. Input: positive-area `weld_only` -> expected brief says raw D empty, weld drops one face, while clean `split` drops zero faces. Output must list whether each proposed signal is diagnostic-only or affects SAT eligibility; approval remains pending. Any change to raw-vs-weld degeneracy eligibility/reporting requires a **separate decision**, not adoption in this research or an instruction to make every helper return the same policy verdict.

## Open questions and limits

- Should a raw triangle dropped by weld have a separate scene diagnostic, and should it affect only reporting or SAT eligibility? Not decided here; blanket raw rejection would conflate the normalization control with unsupported input unless designed carefully.
- Should separated unsupported pieces retain named support reasons outside the overlap-specific coverage finding? Current gap says unmeasured but omits names/reasons; bbox separation remains sound intersection evidence.
- How do actual FBX import/tessellation and Blender BVH preserve these synthetic raw witnesses? Not observed: no DCC/export was authorized. Topology results here use the pure-Python/NumPy counter, not a real readback.
- The requested external `C:/Users/artsafro/hermes_kanban/profiles/COORDINATION_RULES.md` was **not read**, because the harness restricts file access to this worktree. AGENTS, PROJECT_STATE and UCX area were read first; no external local files were inspected or modified for research. Existing installed Python executables/dependencies were used read-only to run the probes.
- No production/test/schema/threshold/evaluator/recall/CI/guard/procedure/data/dependency changes, no DCC or exports, no commit/push/PR creation. Driver handles publication, only to `artsafro/AGR-DigitalTwin-pilot`. Final delivery acceptance remains unperformed: **`delivery_passed=false`**.

## Reproduction

Frozen synthetic corpus, defined before observations; no test modules imported, no DCC or files written by the probe. Execute from the repository root with an existing NumPy-enabled project interpreter, `PYTHONPATH=src`, and `-B` (no dependency installation or bytecode writes). The observed interpreter was `C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/.venv/Scripts/python.exe`; only repository modules and the existing installed runtime were used, with no source substitutions.

Exact execution pattern (set `PYTHON` to that existing interpreter; stdout only):

```bash
PYTHONPATH=src "$PYTHON" -B - <<'PY'
from pathlib import Path
text = Path('docs/research/ucx-scene-degeneracy-routing-parity.md').read_text()
# Select the standalone corpus block, not this launcher.
code = text.split('```python\n', 1)[1].split('\n```', 1)[0]
exec(code)
PY
```

```python
import json
from twinqa import scene
from twinqa.geometry import ucx_audit as ua
from twinqa.geometry.topology import count_defects

T = [(0,1,3),(0,3,2),(4,6,7),(4,7,5),(0,4,5),(0,5,1),
     (2,3,7),(2,7,6),(0,2,6),(0,6,4),(1,5,7),(1,7,3)]
def box(x=0):
    return [(x + (1 if i & 4 else 0), 1 if i & 2 else 0,
             1 if i & 1 else 0) for i in range(8)], list(T)
v, t = box()
corpus = {
    'clean': (v, t),
    'tetra': ([(0,0,0),(1,0,0),(0,1,0),(0.5,0,0)],
              [(0,1,2),(0,1,3),(0,2,3),(1,2,3)]),
    'collinear': (v + [(0.5,0,0)], t + [(0,8,4)]),
    'repeated': (v, t + [(0,0,1)]),
    'weld_only': (v + [(1e-6,0,0)], t + [(0,8,2)]),
    'split': ([v[i] for tri in t for i in tri],
              [(3*k,3*k+1,3*k+2) for k in range(12)]),
}
# Minimal synthetic profile values from VPM_STANDARD.yaml, not a delivery profile.
profile = {'geometry': {'oks_triangles_per_fbx_max_excluding_collision': 1000000,
    'near_coplanar_spacing_m': {'min': 0.005, 'max': 0.02},
    'duplicate_or_self_intersection_count_max': 100,
    'geometric_error_tolerance_m': 0.002}, 'naming': {'max_characters': 254}}
def mesh(n, geom):
    v, t = geom
    return {'name': n, 'hull': {'verts': v, 'tris': t},
        'triangles': len(t), 'polygon_degrees': {'3': len(t)},
        'rotation_euler_deg': [0,0,0], 'scale': [1,1,1], 'location': [0,0,0],
        'uv_channels': 1, 'mirrored_uv_triangles': 0, 'udim_tiles': [1001],
        'materials': [], 'topology': count_defects(v, t)}
def outcome(call):
    try:
        return call()
    except Exception as e:
        return {'exception': type(e).__name__, 'message': str(e)}
for key, geom in corpus.items():
    v, t = geom
    wv, wt = ua.weld(v, t)
    a = mesh('UCX_SM_A_Main_001', geom)
    print(json.dumps({'case': key, 'raw_VF': [len(v),len(t)],
        'raw_degenerate': ua.degenerate_triangles(v,t),
        'weld_VF': [len(wv),len(wt)], 'weld_degenerate': ua.degenerate_triangles(wv,wt),
        'volume': scene._enclosed_volume(wv,wt), 'classify': outcome(lambda: ua.classify(v,t)),
        'piece_reason': outcome(lambda: scene._ucx_piece(a)['reason']),
        'topology': a['topology']}))
    for placement, x in [('overlap',0.5), ('gap',1.02)]:
        bgeom = box(x)
        b = mesh('UCX_SM_A_Main_002', bgeom)
        rb = {'source': 'SM_A.fbx', 'readback_ok': True, 'meshes': [a,b],
              'other_objects': [], 'fbx_units': {'unit_scale_factor': 100}}
        findings = outcome(lambda: scene.scene_findings(rb,'vpm','oks',profile))
        if 'exception' not in findings:
            findings = {stage: [(f.name,f.status,f.observed) for f in fs]
                        for stage,fs in findings.items()}
        print(json.dumps({'case': key, 'placement': placement, 'findings': findings,
            'raw_pair': outcome(lambda: ua.pair_findings(geom,bgeom,'A','B')),
            'weld_pair': outcome(lambda: ua.pair_findings((wv,wt),bgeom,'A','B'))}))
```
