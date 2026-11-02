# Research #769: rectified slide overlay for bands and ribs on AC08

Verdict: **advisory.** The overlay meets the acceptance on facade 1-2: the largest band-edge offset is 1.43 px,
and a planted 0.1 m shift fails at 19.4-21.4 px. Its own bias is up to 2.19 px, so with a 2 px tolerance it gives
false fails on 2 of the 4 facades. It also cannot check rib positions against the slide, because the slide draws a
different rib step from the decided contract. Keep it as an advisory overlay next to the count check, not as a gate.
A follow-up issue decides about adoption; nothing in any checker, gate or threshold changed here.

Issue: https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/769. Card: t_6f974065.

## Primary source, checked

arXiv 2504.05249 is Tang et al. 2025, *Texture2LoD3: Enabling LoD3 Building Reconstruction With Panoramic Images*.
The abstract says: "prior low-detail building models can serve as valid planar targets for ortho-rectifying
street-level panoramic images". That checks out against the ideas-digest line. The +11 % segmentation figure in
the paper is about facade segmentation on their ReLoD3 dataset. It says nothing about drawing or slide overlays.
What we carry over is only the method: **the delivered model's facade plane is the rectification target.**

## Method (`jobs/TEC26-OKS/scripts/slide_overlay.py`, research only)

1. **Slide.** Slide 49 (sha256 checked against the spec). `compare_facades.slide_boxes` finds the facade box. Each
   side of the drawn body outline is fitted as a line through per-row or per-column darkness centroids, with
   sub-pixel accuracy. The corners are the intersections of those lines.
2. **Target.** The VPM readback body on that facade: vertical triangles facing the normal that reach above ±0.000,
   given as the camera-right coordinate u and the height z in metres.
3. **Homography.** A normalised 4-point DLT from the slide corners to the target corners. The slide is resampled at
   200 px/m into a frame that spans the body ±0.3 m and z −0.45..2.85 m, with 3×3 supersampling.
4. **VPM render.** The pilot-v010 render goes into the same (u, z) frame through its orthographic camera
   (`renders.json`). Transparent pixels become white.
5. **Measurement.** The same `measure()` runs on both images:
   - The field-outline lines are the inner edges of the four frame bands. They are the first and last dark lines on
     the HSV-value profiles, at least 0.03 m inside the body.
   - Each line centre is the darkness centroid over the dark run plus one pixel on each side.
   - Dark factor: 0.75 on the slide and 0.85 on the render, the factors that `slide_count` and the render
     `joint_count` already use.
   - The joints are counted by the unchanged `joint_count.count_joints` (tol 0.012, dark 0.85).
   - Pass condition: all 4 band-edge offsets are finite and within 2 px.
6. **Registration modes.** `model` (default) is the Texture2LoD3 target from step 2. `datum` uses the drawing's own
   body size (sheet `size_mm`), centred on the model body, with the body bottom at ±0.000; that is what the
   comparison sheets do.
7. **Planted errors.**
   - `--plant-u d` moves the delivered facade d m along u. It does this by offsetting the render camera centre,
     which gives an exact sub-pixel shift.
   - `--plant-top-band d` moves the render rows of the top field outline d m down, which makes the top band d m
     taller.

## Inputs (pilot PC, not in the repo; public-repo rule: no client paths)

| Input | sha256 |
|---|---|
| slide 49 PNG (spec `presentation.image`) | `256f32da2a04141fc6b62b46ed9710c1830c5ffd3f48f2bac578719c0208a8fd` |
| pilot-v010 `readback/vpm.readback.json` | `79195308ae9b70214f5d487880ed941298aee725f27a347c1f67485d3e095817` |
| pilot-v010 `renders/renders.json` | `b9929d3e69b59ece98cfdc97fb747df6dd48cb4cd9689ddc11a3790017687d6b` |
| pilot-v010 `renders/vpm_north.png` | `c89060df91018d20460b26fc23afe1eb1ecb81708bea2265c76c82426d09893f` |
| `jobs/TEC26-OKS/AC08/vpm_textures.json`, `sheet-facades.json` | the files in this commit |

Code: branch `improve/issue-769-research-rectified-slide-overlay-for-ban` on pilot main `1a417376a`.
Python 3.14.7 (uv venv), numpy, Pillow. No DCC was used. The renders are the existing pilot-v010 Blender renders.

## Reproduce

```bash
A="jobs/TEC26-OKS/AC08/vpm_textures.json jobs/TEC26-OKS/AC08/sheet-facades.json $PILOT/renders $PILOT/readback/vpm.readback.json"
S=jobs/TEC26-OKS/scripts/slide_overlay.py
uv run python $S $A out/base                              # facade 1-2, model registration, 200 px/m, tol 2 px
uv run python $S $A out/datum --register datum
uv run python $S $A out/u+0.1 --plant-u 0.1               # also -0.1, ±0.005, ±0.01, ±0.02
uv run python $S $A out/band0.1 --plant-top-band 0.1      # also 0.0025, 0.005, 0.01, 0.02, 0.05
uv run python $S $A out/fac_2-1 --facade 2-1              # also А-Б, Б-А
uv run pytest -q tests/jobs/test_tec26_ac08_slide_overlay.py
```

`$PILOT` is the AC08 pilot-v010 delivery folder. Exit code 0 = overlay pass, 1 = overlay fail, 2 = refused input
(nothing is written). Evidence (the overlay.json and 3 PNGs of every run below, plus SHA256SUMS.txt):
`G:/Мой диск/AGR-evidence/769-slide-overlay/`. `base/overlay.json` sha256 is
`88dcbb40c485d4770b14a9d848ee290f1d2271f917d893ef6c15711549f13235`.

## Measured (real runs, 2026-11-02, each run in a fresh process)

Offsets are slide minus VPM, in px at 200 px/m (1 px = 5 mm). Joints = `count_joints` found / dark lines on the
rectified slide; VPM = `count_joints` on the rectified render. "Joint Δ" = largest offset between paired joint
lines. Wall time includes Python start-up.

| Run | Facade | Reg. | left | right | top | bottom | max | Verdict | Slide joints | VPM joints | Joint Δ px | Exit | Wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| base | 1-2 | model | +0.16 | -0.64 | +1.43 | -0.89 | 1.43 | pass | 29/29 | 29 | 26.7 | 0 | 8.3 |
| datum | 1-2 | datum | +0.22 | -0.69 | +9.56 | +7.22 | 9.56 | FAIL | 29/29 | 29 | 26.6 | 1 | 7.5 |
| plant u +0.1 m | 1-2 | model | -18.51 | +19.36 | +1.43 | -0.89 | 19.36 | FAIL | 29/29 | 28 | 17.8 | 1 | 6.7 |
| plant u −0.1 m | 1-2 | model | -19.84 | +17.97 | +1.43 | -0.89 | 19.84 | FAIL | 29/29 | 28 | 18.7 | 1 | 7.9 |
| plant top band 0.1 m | 1-2 | model | +0.16 | -0.64 | +21.43 | -0.89 | 21.43 | FAIL | 29/29 | 29 | 26.7 | 1 | 10.0 |
| band 0.0025 | 1-2 | model | +0.16 | -0.64 | +1.89 | -0.89 | 1.89 | pass | 29/29 | 29 | 26.7 | 0 | 11.2 |
| band 0.005 | 1-2 | model | +0.16 | -0.64 | +2.43 | -0.89 | 2.43 | FAIL | 29/29 | 29 | 26.7 | 1 | 11.1 |
| band 0.01 | 1-2 | model | +0.16 | -0.64 | +3.43 | -0.89 | 3.43 | FAIL | 29/29 | 29 | 26.7 | 1 | 12.1 |
| band 0.02 | 1-2 | model | +0.16 | -0.64 | +5.43 | -0.89 | 5.43 | FAIL | 29/29 | 29 | 26.7 | 1 | 13.2 |
| band 0.05 | 1-2 | model | +0.16 | -0.64 | +11.43 | -0.89 | 11.43 | FAIL | 29/29 | 29 | 26.7 | 1 | 14.9 |
| u −0.02 | 1-2 | model | -3.84 | -4.64 | +1.43 | -0.89 | 4.64 | FAIL | 29/29 | 29 | 22.7 | 1 | 11.0 |
| u −0.01 | 1-2 | model | -1.84 | -2.64 | +1.43 | -0.89 | 2.64 | FAIL | 29/29 | 29 | 24.7 | 1 | 7.8 |
| u −0.005 | 1-2 | model | -0.84 | -1.64 | +1.43 | -0.89 | 1.64 | pass | 29/29 | 29 | 25.7 | 0 | 7.0 |
| u +0.005 | 1-2 | model | +1.16 | +0.36 | +1.43 | -0.89 | 1.43 | pass | 29/29 | 29 | 27.7 | 0 | 9.4 |
| u +0.01 | 1-2 | model | +2.16 | +1.36 | +1.43 | -0.89 | 2.16 | FAIL | 29/29 | 29 | 28.7 | 1 | 7.5 |
| u +0.02 | 1-2 | model | +4.16 | +3.36 | +1.43 | -0.89 | 4.16 | FAIL | 29/29 | 29 | 30.7 | 1 | 7.3 |
| other facade | А-Б | model | +0.68 | +0.20 | +1.44 | -0.89 | 1.44 | pass | 10/11 | 11 | 29.5 | 0 | 4.6 |
| other facade | Б-А | model | -0.07 | -0.64 | -0.25 | -2.19 | 2.19 | FAIL | 10/11 | 11 | 28.7 | 1 | 4.3 |
| other facade | 2-1 | model | +0.23 | -0.60 | -0.25 | -2.18 | 2.18 | FAIL | 28/27 | 25 | 155.5 | 1 | 8.0 |

Registration of the base run:
- Slide corners (px): (579.837, 80.5), (914.409, 80.5), (914.416, 223.5), (579.784, 223.5).
- Outline line fits: largest residual 0.169 px (left side), slopes at most 3.7e-4.
- Perspective terms of H: 7.5e-19 and 1.3e-6. The slide is already an orthographic elevation, so the 4-point
  homography reduces to scale plus translation.
- Corner back-projection: 3.6e-15 m. The rectified frame is 1332×660 px.
- The script's own time is 6.7 s. Every CLI run took ≤ 14.9 s including Python start-up, against the 60 s limit.

## Acceptance

| Acceptance | Result | Evidence |
|---|---|---|
| Slide 49 rectified onto the facade plane at 200 px/m | yes: 1-2, frame 1332×660 px, corner back-projection 3.6e-15 m | `test_real_facade_1_2_overlay_passes_and_ribs_agree` |
| Band-edge offset slide vs VPM ≤ 2 px (1 cm) | yes on 1-2: max 1.43 px (top band) | same |
| A planted 0.1 m shift fails | yes: u ±0.1 m → 19.4 / 19.8 px, top band +0.1 m → 21.4 px | `test_real_planted_0_1_m_shift_fails` ×3 |
| Rib count still agrees with joint_count (29) | yes: 29 on the rectified slide = 29 on the VPM render = 30 − 1 | `test_real_facade_1_2_overlay_passes_and_ribs_agree` |
| Headless run ≤ 60 s | yes: 6.7-14.9 s per CLI run | `test_real_cli_headless_under_60_s` |

## Findings

1. **Detection limit on 1-2.**
   - What the overlay measures (the planted shift) is linear: each 5 mm of planted shift changes the measured offset
     by 1.00 px (both sweeps).
   - Because the edges start with a bias, the smallest shift that fails depends on direction: a top band about
     3 mm taller already fails (+1.43 px start), while a 5 mm move along u in either direction still passes.
   - The bias is not noise. It is the slide raster: the slide is about 55 px/m, so 1 slide px = 18 mm = 3.6 px of
     the rectified frame. The 1 cm tolerance is 0.55 slide px.
2. **False fails at 2 px.** Facades Б-А and 2-1 sit in the lower row of the slide. Their bottom band comes out at
   −2.19 px (11 mm), against −0.89 px on the upper row. The model and the rectification are the same for both rows,
   so this is slide quantization, not a model defect. A 2 px gate would fail 2 of 4 correct facades. The tolerance
   would have to be ≥ 3 px (1.5 cm) to stay quiet.
3. **Rib positions cannot be checked against the slide.** The slide draws the ribs at the literal 200 mm drawing step
   (the 58 mm last strip). The delivered VPM spaces 30 ribs evenly at 195.3 mm, which is the decided contract
   (`test_count_joints_contract_and_counterexamples`). The overlay shows the drift growing along the facade to
   26.7 px (13.4 cm) at the far end. The slide's own count is right (29), but `count_joints` reports
   `ok=false` for the slide (largest position error 0.14 m). So the slide can give the rib **count** and the band
   **edges**, not the rib **positions**.
4. **Count can be right while position is not: the ±0.000 datum.** In `datum` registration both horizontal band
   edges move by +8.1 / +8.3 px, which matches 40.8 mm. Cause: the source Max body (`max-dump-008.json`, and the
   readback) spans z −0.0408..2.5502 m, while the drawing puts the 2.591 m body on ±0.000. The count-based compare
   (`compare_facades`, 29 = 29 = 29) cannot see this offset; the overlay does. Whether this is a source error or a
   datum convention is a question for Artem. Geometry edits are out of scope for AC08 colour work, so nothing was
   changed.
5. **Door facade 2-1.** The 30-70 % profile rows cross the door. The VPM count there is 25 (4 joints hidden, as the
   sheet says), and the joint pairing breaks (155 px). The band edges are still measured. Using the overlay on the
   door facade would need a door-aware row choice.

## Repair attempts inside the card (COORDINATION_RULES 56)

1. Dark threshold 0.75 on the RGB sum for both images. Error: on Б-А the render's thin left field outline has only
   0.79 contrast and was missed (offset −36.9 px).
2. Threshold 0.85 on both images. Error: on the slide it picked up the blurred tail of the body outline, and on the
   render it picked up the red ±0.000 marker line (bottom offset +21.9 px).
3. Final version: HSV value instead of the RGB sum (the red marker is bright in value), each image's existing dark
   factor (slide 0.75, render 0.85), and the centroid taken over the run ±1 px. Synthetic lines are now measured
   within 0.05 px; before that the bias was 0.22 px.

## Verdict

**Advisory.** As a reviewer's overlay it is useful: it measures band positions, which the count cannot, and it
exposed the 40.8 mm datum offset. As a gate at 2 px it is not usable, because the slide's 55 px/m raster gives
false fails on correct facades, and the slide's rib positions contradict the decided even-rib contract. If it is
adopted later:
- use the `model` registration;
- check band edges only, with tolerance ≥ 3 px at 200 px/m;
- take rib positions from the contract, never from the slide;
- report the datum offset separately.
