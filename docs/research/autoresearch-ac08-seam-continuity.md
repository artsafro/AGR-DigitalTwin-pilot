# Standing #67 — AC08 cross-seam Diffuse continuity (OBSERVE)

## Frozen contract (written before the runner exists and before any score)

H67: on the delivered AC08 NPM, the texture break across UV seams of the 4K panel finish is larger on the
visually rejected v007 (wrong joint pitch/phase, #559 comment 6341991856) than on the accepted visual
reference v010 (#559 comment 6345392389). Unlike #58/#64 (render mean vs VPM), #61-#63 (joint count against
slide 49) and #66 (density), this signal needs **no source or VPM reference**: it compares the Diffuse texels the
two faces of one mesh edge show on either side of that edge. If it separated the labels it would transfer to
objects without a counted source (MAF boards). Diagnostic only, not a new check or threshold.

- Inputs and reuse: as #66 — delivered `SM_Nku_1.zip` + external `npm_atlas.json` under
  `G:/Мой диск/AGR-evidence/559-tec26-oks-ac08-pilot-v007/` and `...-v010/` (same SHA-256 pins as #66, below),
  fresh Blender `twinqa.scene.readback` per round, `twinqa.sintez_uv._polygons`; Diffuse PNGs decoded from the
  ZIP. No repack, no export, no production patch. Textured targets = planning finishes with `px_per_m`
  (decoded square 4096 Diffuse): v007 tile 1001, v010 tiles 1001/1002. 256 px solid tiles are excluded and
  reported as **not measured**. UCX and glass meshes excluded by name.
- Seam edge: a mesh edge (vertex-index pair inside one mesh) with exactly two faces, both faces' UV centroids
  in the **same** target tile, and the two faces' loop UVs at either endpoint differing by > 1e-6. Edges between
  different tiles are material borders and are excluded (counted). Continuous-UV edges are counted, not scored.
- Sampling: K = max(2, ceil(edge_length_m × 1000)) points at t = (k + 0.5)/K along the edge; on each side the
  point is moved 2 px into its own face perpendicular to the UV edge (towards the face UV centroid), wrapped into
  the tile, and read with nearest-texel lookup (row = (1 − v_frac)·side). Sample difference = mean |ΔRGB| / 255.
- Score `SD67` = mean sample difference over all seam samples of all target tiles (one number per version);
  per-tile seam edges, samples, mean, p95 and fraction of samples > 0.10 are evidence only.
- Calibration (the single decision): `D67 = SD67(v007) − SD67(v010)`, median of 3 fresh paired rounds;
  confirmed needs D67 ≥ max(0.01, 0.25 × SD67(v010)) with spread 0 in every state.
- Positive witness on **both** labels (in readback memory only): shift the V coordinate of every target face
  whose geometric normal points to +X (|n_x| > 0.9, n_x > 0) by +2 and +5 px of its tile; all other faces
  unchanged. Expected: SD67 rises on both labels at +5 px (strict increase); per-state changed faces > 0 on the
  shifted set and 0 elsewhere; zero changed faces = `not_exercised` = not measured. Clean state changes 0 by
  definition. The witness is synthetic and is not a human label.
- Verdict: confirmed if parity, coverage (≥ 1 seam edge per label), witness, stability and separation hold;
  refuted if all hold except separation; inconclusive if inputs, applicability, parity, witness, stability or the
  budget stop the series.
- Budget (frozen): zero production keep rounds; one first measured pair then two confirmation pairs; no tuning,
  no second candidate. 60 s first-pair cap, 240 s total, continue only if remaining ≥ 2 × first pair + 15 s,
  otherwise `budget_stop` → inconclusive; replay the same command in a fresh directory in an idle slot.
- Forbidden: editing delivered packages or other cards' files, changing production checks/tolerances,
  deselecting tests, silent coverage drops, rescoring one dump as an independent import, changing the sampling
  rule after the first score.
- Not taken: form (closed), G22 atlas #1649, KPP1 #1817/#1818, Staropetrovskiy #1500, MAF numbering #1809;
  padding (#65: no per-tile pad band in the UDIM delivery), density (#66 refuted), render mean (#58/#64 wrong
  ordering), joint oracle (#61-#63 already confirmed with a source). Readiness 2026-11-24 13:45: blockers
  #1507/#1608, KPP1 #1817/D377 — none owns this signal.

Replay: `uv run --frozen python docs/research/atlas-seam-r67/replay.py tmp/r67-run-NEW` (limited: Windows,
pinned Blender 5.1.2, Drive access). Reference code (`src tools standards adapters uv.lock pyproject.toml`) must
equal `4288c54de328db7a5037b57707862319f7aa6ff0`.

| Asset | SHA-256 |
| --- | --- |
| v007 ZIP | `271ee11bf78200ef883814a4ac108ef289098d0f106da01e8d9fc57da888c295` |
| v010 ZIP | `2fe983791566477e297aeefa09f04a1b7d176312c3fce1a8c9f1cf26138013bb` |
| v007 planning JSON | `9feb8685a71dec4cd2bb746bd3695bccdce3e648199dc0f32cb3738f6c430ea2` |
| v010 planning JSON | `338edcd767c0c6c99f762d4b7a9dcfd9407da030086ccb5b96e551d3bffae0cc` |
| Blender executable | `1e6624af112b3c936f4b038b025ebd2bf00ae72c4b62881a6787166d71c58fa5` |

## R1 — inconclusive (witness not exercised); completed, OBSERVE only

Runner `atlas-seam-r67/replay.py` (SHA-256 `e62dbd59…9191`, commit `6b3e09df`), `tmp/r67-run-001`, receipt
[`atlas-seam-r67/receipt-r1.json`](atlas-seam-r67/receipt-r1.json) (SHA-256 `f8daee54…d0e2`). Status completed,
3 fresh pairs (2.791 / 2.473 / 2.435 s, total 7.959 s), every state spread 0, input parity before/after held.

| Label | Seam edges / samples (tile 1001) | SD67 clean | p95 | samples > 0.10 |
| --- | ---: | ---: | ---: | ---: |
| v007 (rejected) | 10 / 9522 | 0.1434673 | 0.2863 | 52.0 % |
| v010 (accepted) | 10 / 9522 | 0.0715975 | 0.2797 | 25.9 % |

D67 = +0.0718698 (spread 0) ≥ max(0.01, 0.25 × 0.0716) — the separation condition holds. Edge census is the
same on both labels (seam 10, continuous 28, tile border 57, non-target 467, boundary 34); v010 tile 1002 has
no seam edges (**not measured**). Witness **not exercised**: the 4 +X-facing target faces were shifted on both
labels but none owns a seam edge, so SD67 did not move (+2/+5 px = clean). By the frozen verdict rule the
hypothesis is **inconclusive** for R1; the separation is descriptive until the score path is shown to react.

## R2 — witness amendment (frozen after R1, before running it)

Only the witness selection changes; the score, sampling, labels, pins, threshold and budget stay as R1.
Witness faces = for every seam edge on a target tile, the face with the smaller polygon index of the pair
(the "first side"); V shift +2 / +5 px on those faces only. Expected: +5 px strictly raises SD67 on both
labels, changed faces > 0 and equal to the number of distinct first-side faces. Clean SD67 and D67 must equal
R1 exactly (same bytes, fresh imports) — any difference = instability. Confirmed/refuted/inconclusive as frozen
above. Known confound recorded in advance: v007 and v010 bake different Diffuse images, so SD67 also scales
with texture contrast; one labelled pair cannot separate "seam break" from "contrast". R2 can only confirm the
calibration on this pair, not a general seam detector.
