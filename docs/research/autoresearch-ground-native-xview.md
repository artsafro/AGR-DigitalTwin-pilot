# Standing #33 — Ground near-vertex counter vs native 3ds Max xView (OBSERVE)

## Итог (OBSERVE)

_Filled in after the series; the contract below was committed before any measurement._

## Frozen contract (before any measurement)

Continue #32 (`research/autoresearch-standing-32@ebb32458a5673e2b142d7fc5b273733621201d71`, candidate
`Qv = 10000 * V / T`, V = unique vertex indices in repo xView 2 mm pairs on the Blender readback of the
`*_Ground` part). #32 measured V only on Blender readbacks; Artem checks xView in 3ds Max on Editable_Poly.
#370 (`docs/research/xview-parity-ground-v014.md`) showed the node state matters: Vatutino Ground v014 NPM has
0 Overlapping Vertices as imported (Editable_mesh) and 118 after `convertToPoly`.

**Hypothesis H33 (this corpus only):** the #32 counter agrees with native Max on the presence of near vertices:
for every input, `(V_repo > 0) == (V_max > 0)`, where `V_max` is the 3ds Max 2026 xView "Overlapping Vertices"
count at 2 mm on the selected Ground node in the runner's `plain` mode (Editable_Poly, Artem's working state).

- **Fixture (frozen):** A1–A8 = the #31 accepted FBX inputs, `C:/x/ev_t_193a0887/inputs/`, hashes as in
  `research/autoresearch-standing-31@8ee341f7:docs/research/autoresearch-ground-quality-harness/inputs.sha256`
  (Vatutino v015 + seven delivered NTR NPM). W1 = natural positive witness outside SIL13: Vatutino Ground v014 NPM
  `C:/x/t_d94665f2/ground_v014/npm/SM_Vatutino_Ground.fbx`, SHA-256
  `94357c5f048ba3343035dfa44c9d0d89d83b3d6697dcfd9cc81c54739a6dc2ef`. W1 is **rule-failed** (D152 xView-clean, Max
  118 OV in poly, #370) and superseded by v015 (D157); it is not an explicit Artem rejection of the file.
  SIL13 r1–r5 have no FBX (stopped before export) and the #1738 core outputs are OBJ only: the runner accepts
  `.fbx`/`.max`, so both are **not measured natively** here (no conversion stage is added).
- **Node:** the single `*_Ground` node named as in the #31 dumps (A) and `SM_Vatutino_Ground` (W1); no MAF/UCX/Flora.
- **Native command:** copies under `C:/x/ev_t_304e8c0c/max/run<k>/`, `tools/qa/xview_parity.py prepare_run` writes
  `jobs.txt` with a nonce, `python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --version 2026 --file
  tools/qa/xview_dump.ms` with `XVIEW_OUT=<run dir>`, accepted only when `xview_parity.py --check-run` passes.
  Three independent Max processes (run1–run3) in `plain`; run1 also `weldpoly` (perturbation).
- **Repo side:** A rows reuse the #32 receipt (V=0 on all eight, recomputed by #32's `measure`). W1 is dumped once with
  the #31 pipeline (`fbx_to_blend.py` at `8ee341f7` + `tools/blender/xview_dump.py` + `xview_gate.to_metres`) into
  `C:/x/ev_t_304e8c0c/dumps/W1_Vatutino_v014_NPM.npz`, then #32's `measure` three times.
- **Replay:** `../../.venv/Scripts/python.exe docs/research/autoresearch-ground-native-xview-r33.py <new.json>`
  from the worktree root (needs 3ds Max 2026 + Blender 5.1 on this workstation: replay limited to this PC).
- **Confirmed:** all three plain runs complete with zero spread on V_max, F_max, vertex and face counts per node,
  and the presence rule holds on all 9 inputs. **Refuted:** a completed series where any input breaks the rule
  (this includes W1 with V_repo = 0 while V_max > 0, i.e. the Blender-readback counter is blind to that defect class).
  **Inconclusive:** a series that could not be completed in budget or a failed check_run.
- **Expected directions (prior, not the verdict):** A1–A8 V_max = 0 (accepted); W1 V_max = 118 in plain (as #370).
  Perturbation `weldpoly` (weld 2 mm on the mesh, then poly): A stay 0; W1 stays > 0 (re-split of non-manifold
  vertices). Positive trigger witness: W1. Accepted control on which the rule fires: none known (#32 found V = 0 on
  all A); if any A has V_max > 0 it becomes the collateral control and is reported, never dropped.
- **Budget:** first pair = one Max call with A1 + W1 (plain); its wall time t1 projects a full 9-input call
  (`t_full ≈ t1 · (sum of faces)/(A1+W1 faces)`). Cap for the whole native series 45 min wall; if
  `3 · t_full + t_weldpoly > 45 min`, stop **inconclusive** and publish the next command. New-candidate budget: zero
  (no counter change is proposed in this card).
- **Recorded separately:** clean (plain, three runs), perturbed (weldpoly, run1), not measured (SIL13 r1–r5 native,
  #1738 OBJ native, VPM, faces/skirt/budget quality, visual deviation).
- **Forbidden:** fixture replacement, tolerance or validator changes, test deselection, edits to any delivered
  package or input, builds/repairs of Ground (#1738 owns them), saving any Max scene, touching other cards' files,
  using any result as a release gate. Owners: #1315/#1622 cold run, #1738 Ground core, #1742/#1770 body (closed).

**Amendment 1 (after the first-pair call failed, before any native count was obtained):** on 3ds Max 2026.3 the
runner stops with `XVIEW_ERROR -- .NET runtime exception: Operation is not supported on this platform.`
(`tools/qa/xview_dump.ms:83` compiles a helper with `Microsoft.CSharp.CSharpCodeProvider`, unsupported on .NET 8);
receipt `C:/x/ev_t_304e8c0c/r33.json` (`inconclusive`, first pair failed). The series runs on **3ds Max 2024**, the
route with retained native evidence (`docs/pipeline-tools.md`, #528). Everything else in the contract is unchanged.
Fixing the runner for 2026 is outside this card (side finding).

## Round log

_Filled in after the series._
