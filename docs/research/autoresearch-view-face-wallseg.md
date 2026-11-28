# H163 — Silikatny: view -> WALL by frontal per-segment renders (OBSERVE)

## Кратко для Артёма

(заполняется после замера; см. Round log)

## Frozen contract (committed before any score was computed)

Card t_627437b1 (standing #163), focus 0 (view<->face map sheet). #2001 is OPEN: Sokolniki held out, not opened.
Takes #161/#162 next step (1): candidates per footprint WALL (plane segment), not per camera direction. #161 showed
every confusion was the 30-degree neighbour direction (the same wall compressed by cos 30); #162 showed datum scale does
not fix it (A'-K still wrong 0 instead of 330). #2073/#2074 own finish-partition scoring, #2075 wall exercise;
atlas/form/trainer not reopened.

**Fixture (unchanged from #161/#162).** Silikatny album PDF SHA-256 `785e4015…9131`, Revit OBJ by category
`6ab64e6b…ea62` (pinned in #161 `fixture.json` at `f4a7f22b`), Blender 4.4 `fd21f4b9…77b5`. Same 7 views and clips;
view masks = exact #162 `native_drawing` + `register` with the #162 datum anchors (pinned #162 `run.py` blob
`9492c08c…0f54` at `238e576d`). Grid 0.25 m, band z 0–12.9 m, NCC/offset/overlap 0.8 = #161 `best_offset`.

**Candidates (one variant, `blender_walls.py` + `params.json`, frozen).** Exterior vertical faces of `Ctx_steny`,
`Ctx_okna`, `Ctx_paneli_vitrazha` (|nz| < 0.2, area >= 0.05 m², centroid z 0–12.9; exterior = 45-degree sky ray
along the normal hits nothing within 300 m). Faces within ±12° of the 8 #161 directions; per direction cluster plane
offset (gap > 1.0 m splits) then connected u-runs (gap > 4.0 m splits); keep runs with area >= 10 m² and length >= 4 m.
Each wall is rendered frontally: ortho camera along its own normal, lateral window = run + 1 m each side, depth window
5 m in front of the plane to 3 m behind (camera clip), glass objects black, others grey, slabs hidden, 0.1 m/px.

**Decision.** Eligible wall: drawn view width <= 1.10 × wall render width (a view must fit on its wall). Answer = top
eligible wall if NCC >= 0.30 and margin over the best other eligible wall >= 0.10 (#140 values, inherited); with one
eligible wall the margin is against a null candidate (0). No eligible wall -> abstain.

**Pre-score geometry check (walls only, no view scored; `C:/x/ar163/probe1`).** 64 003 vertical facade faces in the band,
9 543 exterior; 20 walls W00–W19. Key: W19 az 330, L 70.07 m, (59.11,−18.53)–(94.15,42.15) = oblique wing curtain-wall
side with the 7 glazed boxes; W17 az 270 L 38.4 m = top wing courtyard side; W09 az 150 L 22.1 m = oblique wing
courtyard side; W13 az 180 L 38.3 m; W04/W06/W07/W08 north side pieces at three plane offsets (14–26 m each). The
curved glazed stair (courtyard) yields NO wall (its normals spread over many directions; runs < 4 m). Longest wall
70.07 m -> eligibility limit 79.3 m.

**Wall-level truth (frozen here, from geometry and #161 labels, before any score).**

| View | Truth | Expected non-wrong outcome |
|---|---|---|
| A'-K (73–74 m, 7 boxes) | W19 | correct = W19 |
| fragment 1 (box bay, 10.7 m) | W19 | correct = W19 |
| 4'-1 (92.8 m, north, several planes) | no single wall | abstain (wider than every wall) |
| 1-4' (84.3 m, developed courtyard, inner) | no single wall | abstain |
| fragment 2 (curved stair, inner) | curved zone, no candidate | abstain; any answer = wrong |
| K-A, A-G | none | diagnostic only |

So this design CANNOT score an inner view correct; inner rows test only that it does not guess. That is a declared
limit, not a result.

**Primary metric.** correct / wrong / abstain on the 5 scored rows; answered accuracy correct/(correct+wrong).
Secondary per row: truth-wall score vs best opposite-direction wall and best 30°-neighbour wall (hard negatives).

**Acceptance H163 (frozen).** All of: wrong = 0; A'-K = W19 (positive witness, #161/#162 wrong row flips); fragment 1 =
W19 (a real partial view placed on its wall among >= 2 eligible walls); fragment 2 abstains; `blank` abstains on 7/7;
on at least one clean-answered row the `shuffle` state abstains (content, not width elimination, carries the answer);
3 pairs byte-identical. Any miss refutes.

**Perturbations (per-state changed cells recorded).** `mirror` (left-right flip; reported, near-symmetric rows may
keep), `blank` (zero mask; must abstain), `shuffle` (2 m column blocks permuted, seed 163: same glass amount, bay order
destroyed; expected to lose the margin on content-carried answers). Candidate-order reversal must give the same
decision (checked in every state). Not measured: curved-wall candidates, multi-wall developed views, bay interval
inside the wall, rotated sheets, fresh Revit export, rejected deliveries (none), Sokolniki transfer (#2001 open).

**Stability / budget.** Replay: `git fetch origin research/autoresearch-standing-161 research/autoresearch-standing-162`;
`uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-wallseg/run.py C:/x/ar163/<fresh>`
(pilot host with the owner's Weltbau folder). Three pairs, each a fresh Blender extraction+render and PDF read; rows +
wall table must be byte-identical; median/spread wall time reported. One candidate, zero retunes; stop `inconclusive`
over 30 min or on parity failure. Pre-score geometry probe: one Blender run, 10 s.

**Forbidden.** Changing params, truth, clips or states after a score; opening Sokolniki; editing source drawings,
models, deliveries, production `src/` or other cards' files; weakening guards.

## Round log

(after measurement)

Full suite: deferred to merge batch (rule 68).
