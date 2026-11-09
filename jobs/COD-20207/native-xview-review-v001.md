# COD 20207 v008 — exported readback and new material-junction question (#420)

Status: **not passed; model question below; no PR/review publication**.
The approved drive/garden joints ARE applied. They are not the remaining defect.
This report supplements ground-build-v008.md; old attempts remain immutable evidence.
Outputs are diagnostic candidates, NOT approved deliveries.

## Exact question for Artem

The source Tile and Geogrid contours intersect in **0.02918271661547149 m2**
(after the approved polygon-only 1 um normalization). Method C consequently emits
an additional Tile plate at +12 mm over Geogrid +6 mm. Some strips are only a few
millimetres wide. The two snapped fan witnesses are at WCS metres
**6661.908,15448.152** and **6668.001,15448.140**, on this extra Tile plate.

**Approve Tile priority for these Tile/Geogrid intersections: retain the complete
Tile contour as one continuous +6 mm plate and trim ONLY the Geogrid underneath
its 0.029182717 m2 intersection?** This is the recommendation: visible material
assignment is retained, while the thin duplicate +12 mm strips disappear. Or must
these overlaps remain layered / follow a different exact covering boundary?

No such priority/clipping is enabled or assumed in the committed builder. This is
an additional source-material junction decision, not another request to authorize
pipeline code repair. Flatness, footprint and the approved curb joints stay CLOSED.

Exact-contour schematic: `C:/x/ground-cod-22/source-tile-geogrid-overlaps-v001.png`.
Orange = original derived overlap, grey = Tile +6 mm, blue = Geogrid +6 mm; red =
snapped fan. Its X/Y drawing scales are explicitly unequal (vertical exaggerated).
The source overlap is not claimed to be itself a disconnected fan: the latter is
the meshing/conversion defect induced by representing these strips on the snap grid.

## Real execution / pipeline findings

1. v008 production command in ground-build-v008.md: exit 0, **11/11** geometry
   gates. Both master files 5852 total / 2514 surface triangles; internal xView
   0 vertex / 0 face pairs. All 9 source curb entities have modeled dispositions.
2. Self-review found unreported precision collapse. Tests-first `210ba5d`: 1 RED.
   `34d0b02` reports collapse/below-threshold pieces. Focused selection: **110 passed**
   in 11.15 s (`tmp/cod-final-focused2.log`). v009-verification using final code:
   exit 0, both complete COD master JSON files byte-identical to v008 (2/2).
3. Real Vatutino v014 command, same accepted input and exception manifest, with
   `--snap 0.003 --out C:/x/ground-cod-22/vatutino-parity-v001`: exit 0, both complete
   ordered master JSON files **byte-identical (2/2)**. NPM SHA-256
   `f1a03db9d7b2293db50817f8cb7c0c021d25737ff0c2f9ea984e47192b1979bb`;
   VPM `82cb1e6876ba98b92966aa7fc4242a2e9f354ee5ecdd42ed12806b57db666ae5`.
4. Blender **5.1.2/ec6e62d40fa9**, factory startup, one thread, python-exit-code 1:
   existing ground_json_to_fbx build/readback, shared ucx_build, and existing
   bind_ground_textures_blender bind/fingerprint: all **exit 0**. Commands/log hashes
   are retained in `ground-v008/execution-export-v001.json` and execution-qa-v001.json.
   Raw importer material layers, exact vertices/UV/faces, and collision inventories
   before/after diffuse binding compare equal for both profiles (2/2).
5. Clean final-FBX independent Python xView: 0/0 (`export-xview.json`). Native
   Max **2026.3**, copied final NPM, metres, Editable Poly conversion, built-in
   OverlappingVertices 2 mm / OverlappingFaces 5 mm: **4 vertex IDs / 5 face IDs**.
   Original 3282 vertices become 3284; source-indexed fan probe finds two split fans.
   Native IDs (1-based): vertices 1073,1364,3283,3284; faces 1188,1191,1821,1824,2222.
   Do NOT substitute Python pairs for native ID counts. VPM render geometry is the
   same, but native VPM was not separately measured. Native Max runtime returned
   **4294967166**, despite wrapper exit 0/status ok and COD_XVIEW_COMPLETE marker.
   Known polyunwrapper_autoload.mse startup exception is preserved in
   `tmp/cod-native-xview-run.json`; native measurements are diagnostic, not a clean exit.
6. No threshold/checker was relaxed. Precision diagnostic sweep (not production):
   v010 snap 4 mm: exit 1, off-outline open edge 1 and V004 2 pairs;
   v011 snap 5 mm: exit 1, off-outline open edges 6;
   v012 snap 2.2 mm: exit 1, V004 2 pairs, min 2.0476 mm.
   Contour-fidelity diagnostic: v013 snap 3 mm/chord 0: exit 1, 1 outside face at
   original 4 mm contour tolerance; v014 snap 3 mm/chord 1 mm: exit 0/11 gates,
   internal xView 0/0, but **one disconnected fan remains**. It is not a fix.
   These sweeps expose sensitivity, not permission to modify the covering policy.

## Vatutino v014 versus COD v008

Vatutino receipts: ../VATUTINO-SITE/ground-build-v014.md and the real parity rerun.
Numbers below are measured; missing native comparison is explicit.

| Check | Vatutino v014 | COD v008 |
|---|---:|---:|
| Plot / building hole m2 | 25854.04 / 9110.08 | 5101.59 / 1670.09 |
| NPM and VPM render tris each | 46343 | 5852 |
| Master surface tris / 50000 cap | 32821 | 2514 |
| Whole master / 150000 cap | 46343 | 5852 |
| VPM whole-Ground area cap | 4500000 | 1650000 |
| Skirt depth m | 1 | 1 |
| Geometry gates | 11/11, explicit D150 exception | 11/11, no exception |
| Relief | max error 9.963 mm | flat by user; relief check replaced by flatness |
| Flatness at covering corners / centres | not applicable | 7542 / 2514 samples; max 0 / 1.735e-18 m against level*6 mm |
| NPM exported non-skirt density px/m | 11.5555–30.2137 | 29.7446–30.2591 |
| VPM exported non-skirt density px/m | 589.6264–1442.0618 | 1002.2255–1049.7519 |
| Out-of-band / mirrored / down surface normals | 0 / 0 / 0 | 0 / 0 / 0 |
| VPM UDIM straddling / tiles | 0 / [1001] | 0 / [1001] |
| Raw material-order mismatches | 0 | 0 |
| Open edges, not automatically defects | 8307 | 636; off-outline surface edges 0 |
| Face Orientation back pixels top/45/135/225/315 | 0/2/4/3/1 | 0/0/0/0/0 (NPM; same render geometry VPM) |
| Python xView, same current checker on real rerun | 0 vertex / 222 face pairs | 0 / 0 |
| Native Max xView | not rerun here | 4 vertex IDs / 5 face IDs (diagnostic process status above) |
| UCX hulls / tris / cap | 715 / 8788 / 15000 | 501 / 5928 / 15000 |
| Independently closed / convex | 715/715 | 501/501 |
| UCX overlap / touch / below-band | 0 / 0 / 0 | 0 / 0 / 0 |
| Adjacent in-band / wide candidates | 1863 / 632 | 1451 / 1144 |
| Independent sampled forward max distance m | 0.077 | 0.046 (100000 samples, seed 165) |
| Reverse distance, diagnostic only | 2.269 m | 1.000 m |

The current Python xView metric did not exist in the stored v014 report. Its 222
face-pair result comes from the byte-identical real rerun, not a claimed new
Vatutino geometry regression or a native Max measurement. COD wide UCX candidates
have NOT had the v014 101-point corridor/void classifier rerun; they remain review,
not evidence that every candidate is a compliant direct neighbour.

## Automatic Ground versus hand-made reference

Native copied-Max snapshots are authoritative for etalon counts. Clean diagnostic
FBX imports drop etalon faces and are NOT used as budget substitutes.

| Same measurement | Etalon LP | Etalon hp | Automatic NPM/VPM |
|---|---:|---:|---:|
| Named Ground render tris | 2817 | 48765 | 5852 / 5852 |
| Up-facing tris (geometric proxy, includes curb tops) | 2033 | 13879 | 3184 / 3184 |
| All render triangle area m2 | 6158.163 | 10617.647 | 5233.986 |
| Up-facing XY union m2 | 5112.052 | 5112.978 | 3431.498 |
| Sum up-facing XY areas, overlaps included m2 | 5137.123 | 5982.762 | 4500.101 |
| UCX count / triangles | 0 / 0 | 23 / 296 | NPM 0/0; VPM 501/5928 |
| Geometry heights | 158.727219..161.326645, LP frame | -2.675156..5.503055, hp frame | approved flat datum; skirt -1, curb tops .068/.168 |
| Material source | Standard Legacy Ground_1 | Standard Legacy Ground_1 | 7 semantic materials from copied atlas; not Vatutino maps |
| Diffuse / normal source set | copied d_1 / n_1 atlas | native material identity retained | diffuse crops transferred; etalon normal map NOT transferred |

The etalon Ground includes a full plane beneath the building projection; our
approved 1670.085519 m2 footprint hole explains most XY-union difference. This is
not a missing paving claim. The original reference's surface/detail face-role split
is unavailable: up-facing counts above are explicitly a proxy, not its 50000-cap
surface-only receipt. Native etalon xView and original custom normals remain not
measured (original FBX import crash; authorized copied-Max fallback). Height matching
is replaced by flatness by Artem's decision, not silently scored against hp relief.

## Materials, images and transforms

Source copied diffuse atlas has 3x3 cells. Exact pixel crop rectangles (left,top,right,bottom):
Lawn [0,0,682,682], Tile [683,0,1364,682], Asphalt [1366,683,2048,1364],
Geogrid [0,683,682,1364], both curbs [0,1366,682,2048]. Native LP UV bucket
counts support curb white-cell identity (454/457 drive-near triangles, 32/47 garden-near).
No random synthesized texture is used. The hand-made LP plan also shows painted
parking-bay/road-marking polygons; the present automatic decomposition contains
coverings and 9 curb entities only and does not reproduce those separate markings.
This is a visible pipeline/source-coverage finding, not an assertion of material
or semantic equivalence. Original atlas crop resolution is ~682 px;
LANCZOS enlargement to NPM 2048 / VPM 4096 adds NO source detail. Skirt is a 256x256
single mean-asphalt colour. This changes atlas organization and physical repeat
from the etalon, so visual equivalence is NOT accepted or assumed.

`texture-crops-v001.json` records crop/source/output hashes; both final exported
FBX image-readbacks verify 7/7 image hashes/sizes (NPM packed, VPM external).
`npm|vpm/textured-{top,oblique}.png` are actual Cycles renders; new review.blend
files exist locally, not published to pending.json. Source TYPE6 still uses the
previously approved type-2 fallback; no unique TYPE6 material was invented.

Final FBX vertices match the single master in both directions within **2.057675 um**
(3282 vertices). Object scale/location/rotation = 1/0/0, one UV channel. Sidecar
origin remains the measured XY bbox centre, Z=0. The legacy exporter hardcodes an
MSK-77 label; the candidate sidecars explicitly correct ONLY that text to DWG WCS
metres/unspecified CRS, without changing any numeric placement. This portability
finding must be resolved generically before a final production export.

## Final artifact hashes and validation status

| File under C:/x/ground-cod-22/ | SHA-256 |
|---|---|
| spozu.dwg (rechecked unchanged) | 9b409b023a5dd494c91f6807e7aee392b6a684da48fac371209764770d5f764b |
| gp.dwg (rechecked unchanged) | 5f1155b8c317350515dcf0995c5dbcfb643f40c0d1dd28e2af1bd852e7f32300 |
| ground-v008/npm/SM_COD20207_Ground.fbx | b30e9a6cbdde57203e9fe63865e4a1d3d645ce825a17be95b0bec2901c811201 |
| ground-v008/vpm/SM_COD20207_Ground.fbx | 33b7b2a3e4c7c795248b7bafaa08f1fa7b186b9dfbc8eac4e07e9489ac324f67 |
| ground-v008/native-xview-npm.json | f633157b951ea18b27a4311dc4c6fd1892c3a2880dd89f559056fac6253469fa |
| source-tile-geogrid-overlaps-v001.png | 2a48ab715cf7bdb1937f77e421feffbaa54c6ccbc60dd4d436489f1f446e6ef6 |

build-settings.json SHA-256: a30078454f9e315f69893b1c036a31d48d08bd2729e1f60c82dc10de6dcca7a8.
Comparison metrics: `ground-v008/comparison-numbers-v001.json`. Stage logs:
`tmp/cod-validate-{npm,vpm}.log`, exact validate_package --profile --scene --json
commands, both exit **2**, no failed stages, review/not_run NOT counted as passes:
- NPM pass V002/V003/V006; review V004/V012; not_run V001/V005/V014/V015/V017.
- VPM pass V002/V008/V012; review V003/V004/V010; not_run
  V001/V005/V007/V009/V011/V013/V015/V016/V017.
- Native Max diagnostic above independently identifies an unresolved defect even
  though these incomplete general validator runs have no failed stage.

Regression evals: tmp/evals/report.json; 0 passed / 0 failed / 10 not measured
(no Claude transcript); eval command exit 2, exact --check-receipt command exit 0.
Full suite was queued through suite_slot.py, never started (2 occupied slots).
Cancelled the owned waiter on discovering the new model question; verified no
remaining Python/uv process command for this card. No full-suite receipt claimed.

## Handoff

All code/tests are committed; 110 focused tests GREEN, native exported geometry
not clean. No owned DCC/suite process remains. Do not publish v008 or diagnostic
v014 as an accepted result. After source priority answer: tests-first reusable
config/overlap treatment (if approved), rerun all exports/readbacks/UCX/comparisons,
resolve generic coordinate-label portability, classify UCX wide candidates, publish
versioned Max review scene + final-location readback + pending.json, run frozen
full suite/eval/trace/hostile probes, push and open the single PR. Human visual
approval and complete SINTEZ remain separate from machine checks.
