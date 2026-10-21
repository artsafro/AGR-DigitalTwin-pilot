# Skolkovo L4 — resume v006

**Partial intake, passed=false, buildable=false, no Gate 1, no PR.**
The material-authority question is answered. A newly discovered source-membership
error in the mast draft prevents an honest final PartsList/budget.

## Decisions recorded, not reopened

Artem's task comment 2026-10-21 10:52, «материалы из VPM», authorizes delivered
final VPM appearance for exterior surfaces not mapped by album/revision legend.
Geometry stays source/revision-derived. Associations must be explicit and
hash-pinned; the comparison is reference-derived, never independent material
validation. Real finish names, including LOGICROOF V-RP, remain source facts.
This is not Gate 1 or source-geometry replacement permission.

Interior stays exterior-only/opaque-glazing. The source FBX, not PDF labels,
controls mast geometry/placement; no rescaling or PDF rebuilding was performed.
Storage stays Drive, no new LFS objects or rewritten git history.

## New exact model question

Read [MAST-MEMBERSHIP-QUESTION-v006.md](MAST-MEMBERSHIP-QUESTION-v006.md).
The five named mast meshes contain **55,230 triangles**, but they are not the
whole source system: **108 separately exported КНС_* meshes add 90,168**.
Full conservative keep: **113 meshes / 145,398 triangles**. All 113 source
world bboxes were independently checked. Concrete bases extend beyond the
parent-like mesh; receptor heads also exist at different base/top elevations.
They cannot all be silently called duplicates or unrelated architecture.

The old v005 draft falsely drops all 108; the regression fails **3/8 checks**
(exit 1), listing every missing row. The corrected conservative v006 proposal
passes **8/8** (exit 0), but its total allocation is **226,918**, rejected by
`dt_ai.core.models.PartsList.model_validate` against **150,000**. The rejected
JSON is deliberately **not** a valid final PartsList; empty joints and proposed
face/source/legend associations remain unresolved, not implicitly approved.

Exact duplicate-triangle accounting leaves **142,542** distinct triangles in
the mast system. Position quantization at 0.00001/0.0001 m yields the same count.
A separate strict planar-retessellation diagnostic gives a feasibility count
of **140,371**, not an achieved output or global minimum. Neither diagnostic
modifies source/model geometry; neither proves that all other future plans are
impossible. They do not make the current full-keep plan budget-compliant.

Recommendation needing user permission: retain the five parent-like meshes
unchanged, allow bounded source-profile simplification of the 108 additional
components (proposed maximum silhouette deviation 0.02 m, target 10,000 triangles),
remove only proven coincident duplicate surfaces, do not silently drop shifted
base receptor heads. Proposed combined allocation would be **146,750**; not
measured, not guaranteed, not Gate 1. No model choice was silently applied.

## Source/revision coverage work

- New native baseline census: **17,710 meshes / 6,645,503 triangles**. Blender's
  existing reader reports **6,644,287**; difference **1,216** is retained as an
  importer/triangulation discrepancy, not presented as identical geometry.
- Read-only baseline diagnostic extracted **11,834 conservative exterior/roof
  candidates**, not 11,834 keep decisions. Independent binary bounds, finite
  vertices, valid indices and byte-size checks passed **11,834/11,834**.
- The facade revision is not a complete replacement of every baseline source:
  the baseline includes exterior roof decks/caps/access/guardrails, notably
  `Floor ADSK_Перекрытие_Профлист 75 [6422086]`, absent from the facade-only dump.
  Revision PDF p3 and delivered appearance diagnostic corroborate the rooftop
  composition; no VPM geometry is adopted to fill the source.
- The source-scope diagnostic covers **32,961 distinct hash-pinned rows**.
  Its **44 role groups / 45 homogeneous part candidates** are a proposal, not
  final approved geometry, face selection or source-scope certification.
  Native baseline references now pin the full-name Max census, not truncated
  Blender labels. Supersession uses unique full names, or explicit unique bbox
  matches for repeated names, and records replacement rows.
- Proposal dispositions: v1 7,059 explicit supersessions, 18 facade-package
  supersessions, 10,166 drops, 467 retains; facade 5,135 drops / 6,375 retains;
  rods 3,628 unrelated-content drops / **113 mast-system retains**. No unresolved
  label remains in this *draft classifier*, but semantic/face and joint audit is
  not complete. In particular proposed buried/interior drops are not proofs
  derived merely from absence of raster samples. Do not promote them to accepted.

## Appearance extraction and limitations

Read-only Max VPM extraction: two surface meshes, **56,440 triangles** excluding
UCX; source bbox parity and UV index/finite checks pass. The imported materials
have no bitmap links. Explicit supplied naming binds `Main_1` to `Diffuse_1`,
`ERM_1`, `Normal_1` UDIM 1001–1016: **48 files SHA-pinned**, no first-slot fallback.

Three explicitly identified baseline roof caps (native rows 7822, 7837, 7889)
register VPM XY to the source with maximum residual **0.0000020712 m**. Common
reference-to-source Z subtraction is **0.0867686272 m**. The first delivered cap
is another **0.100 m higher** than its source after this registration; report the
discrepancy, do not move source geometry to conceal it.

Source-derived original roof membrane/soffit/detail names are preserved alongside
explicit VPM triangle/UV/pixel swatches. The proposal contains **6,955 object
associations / 11 swatches**. These include revision-legend references, not just
VPM-derived references. They are provisional, not a final face-slot material map,
full texture transfer/bake, calibrated PBR recipe or independent finish validation.
Concrete pad and high-mast metal references are separate explicit selections,
even where sampled colours coincide. Mixed entrance/detail associations still
need source/material/face review; a resolved authority is not a material QA pass.

`vpm-appearance-top-v006.png` renders supplied-reference triangles using diffuse
centroid samples for inspection, not generated source geometry or an acceptance
render. `mast-system-question-v006.png` renders actual source triangles, orange
parent-like mesh versus blue KNS components. Neither is board-tool visual approval.

## Repairs and evidence of failure

- Initial cap registration picked a small non-cap upper face near the third cap:
  residuals 0.543/0.071/0.586 m, **0/3** under 2 mm, assertion stopped the script.
  Restricted the explicitly named cap regions to near-horizontal faces with
  cross-product area >1 m²; **3/3** under 2 mm, actual residuals in the committed
  registration JSON. This is comparison registration, not a new geometric tolerance.
- First homogeneous-part grouping asserted on the mixed baseline roof-access
  group (`railing` versus `rod_ladder`). Split by role/class/operation, giving
  45 diagnostic candidates; the next failure is the honest budget rejection,
  not a swallowed schema exception.
- Mast membership regression precedes the data correction: v005 **5/8 pass,
  3/8 fail**, corrected v006 **8/8 pass**. The old v005 8/8 mast-*policy* probe
  did not test full source membership; it is insufficient and is superseded here.

Existing focused FBX/C5 tests: **133 passed in 3.82 s**:
`env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run --extra pdf-review pytest -q -p no:cacheprovider tests/test_album_pdf_reader.py tests/test_album_below_line.py tests/parts/test_fbx_reader.py --basetemp=C:/x/t_b205c8e1-resume-v006`.
No full suite: rule 49 reserves it for the first complete review head through
`suite_slot.py`. No CI or SINTEZ success is claimed.

## Durable evidence and L5 timing

Drive directory: `G:/Мой диск/AGR-evidence/353-skolkovo-l4/evidence-v006/`.
Small committed index: `evidence-v006/index.json`. Drive manifest SHA-256:
`0e15bc2bf4f1a686d95edb88ce9b89d3f5764398df1df45cf91b993864f253f2`.

`source-diagnostics-v006.zip`: **30,799,389 bytes**, SHA-256
`63feb47f0f88f2d0c13ee8c572632c60b9a459472133f1dcd589c9d17a9d5925`.
ZIP CRC and **11,991/11,991** internal member hashes verified after reopening;
**11/11** Drive artifact hashes independently re-opened/rehashed. Archive includes
raw selected source/mast buffers, VPM appearance buffers, original reader facts,
native censuses, scripts and rejected diagnostic proposals, not supplied FBX/RVT
or invented building exports. All **104/104** original inventory files unchanged.

Three serial headless Max 2026.3 runs, using fresh staged FBX copies, completed
with expected markers and verified content. Native exit **4294967166** and the
known PolyUnwrapper startup warning are preserved separately from wrapper `ok`;
exit/wrapper status alone was not accepted as evidence. The user's live Max 2024
was only pinged; no live scene was imported, saved, held/restored or changed.

| Measured operation | Seconds | Hours |
|---|---:|---:|
| VPM appearance extraction, wrapper wall | 45.4 | 0.0126111111 |
| Baseline selected diagnostic, wrapper wall | 161.7 | 0.0449166667 |
| Complete mast-system dump, wrapper wall | 53.1 | 0.0147500000 |
| Exact/quantized mast duplicate probe | 0.624354 | 0.0001734317 |
| Strict planar feasibility probe | 2.8049308 | 0.0007791474 |
| Focused tests | 3.82 | 0.0010611111 |
| Packaging, original rehash, bbox/ZIP/Drive verification (nested total) | 14.8913842 | 0.0041364956 |

These are partial intake measurements, not complete L5 throughput. Do not add
nested timings as independent production stages. Original rehash timing and
native extraction timings are in the small index. Kernel/build, export, final
visual/user review and checker are **not measured**, not zero.

## Resume order

1. Answer only the new extra-mast-component cleanup/membership question.
2. Keep current diagnostics as unapproved proposals; finish face/scope/legend and
   real joint reconciliation and achievable budgets. Do not revive the invalid
   55,230-whole-system assumption or approve the rejected JSON.
3. Final schema-valid, source-complete PartsList exact hash -> Artem Gate 1.
4. Kernel/invariants -> versioned export/readback -> delivered comparison report
   -> board review/user approval -> complete final SINTEZ.
5. One full suite via suite_slot, receipts, push/open one PR, dt-reviewer.

No production module/library was added. No new scene/output was claimed delivered.
