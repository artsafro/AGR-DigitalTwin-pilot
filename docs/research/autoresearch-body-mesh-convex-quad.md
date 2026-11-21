# Body scorer calibration: convex-quad exception (standing #21, OBSERVE)

**Кратко для Артёма.** Проверяем один вариант локального штрафа R3: считать дефектом на горизонтальных плитах только
треугольники и вырожденные четырёхугольники, а любой нормальный выпуклый четырёхугольник (скос 45°, 60°, трапеция)
не штрафовать. Бадики, штатную оценку и сданные модели не меняем.

## Why this candidate

#20 R5 (exempt horizontal quads with corners within 1° of 45/90/135°) removed the 45° chamfer caps but left the
accepted 63B v007 penalty at 4.158 (gate 0.500). The #19 receipt `r19.json` already names the surviving maximum:
local 0.601876 at seeds 13308/13081, plan (75.918, 7.244), z 26.7/39.3, a horizontal quad with corners
121.59/56.65/60.15/121.60° — a valid oblique slab edge, not a defect. The labelled rejected bodies fail on other
geometry: 63B v001–v005 horizontal triangles, v006 a degenerate quad with a 180° corner (#19), 63C v001 corner
triangles (#13). So the separating feature is the face topology (triangle / degenerate quad), not the corner
angle value. R6 states this a priori; its only tolerance is the 1° already used by R3 `flat_cos` and R5.

## Frozen contract

Continue the #19 `localize.py` harness at `987f418a237e5931d695c278bcca177c789de3da` (script SHA-256
`e84c7bef192e1aa3f7a9a3295869d26a4d8e961bc6d976514e6f730340f160d7`) exactly as #20 did (same anchors), inheriting
its input hashes, zones, parity and witness checks, and its built-in confirmation that R0/R3 reproduce the #17
receipt on all 13 inputs. Fixture: the 13 frozen #13 inputs in nine same-building pairs (63B v007 vs v001–v006,
63C v002/v001, KPP1 v003 rest/corners, G22 k1 v003/v002); accepted-only holdouts 63A v005 and G22 k2 v002r1 (#18).
Dumps: `C:/x/ar15/r1/tmp` (hashes asserted against the #17 receipt). No cross-building ranking; distance to the
G22 etalon is not used (it rewards the rejection, #12).

**R6** changes only `bad` membership of R3. A face is exempt when all hold:
`abs(normal_z) >= flat_cos` (R3's 1° horizontal test), exactly 4 corners, every corner strictly inside
(1°, 179°), and the corner sum within 1° of 360° (convex, planar, non-degenerate). Triangles, n-gons, faces with a
0°/180° corner and non-horizontal faces stay `bad`. Global `irregular_area_share` is unchanged.

**Metric (one number):** worst accepted-minus-rejected margin (points) over the nine pairs at both shifts
`(0,0,0)` and `(-5,7,11)` m, median of three runs per input/variant/shift. **Keep (in OBSERVE: "would change")**
only if all: worst margin ≥ 0.500; v007 drop vs R0 ≤ 0.500; each holdout drop ≤ 0.500; translation invariance and
exact repeatability; canonical report parity outside `score`, `penalties.irregular_area_share`,
`local_irregular_area_share`. Paired spread = max−min of paired differences, reported per pair.

**Checks.** Clean: #14 rectangle + reset witness, canonical parity, frozen hashes, R0 rows equal to the #20 receipt
`r20.json` (SHA-256 `ab9ac3034ac2777aa05d7ddbe445ab706248f2596887ded7b78c90ff4009ca15`). Predicate witness
(must be RED with no exception, GREEN with R6): accept chamfer quad 45.5/45.5/134.5/134.5, the v007 survivor
121.59/56.65/60.15/121.60, a rectangle; refuse a triangle, a quad with a 180° corner, a quad with a 0° corner,
a concave quad (sum ≠ 360), a vertical quad, a pentagon. Injected: #14 skew witness. Not measured: fresh native
readback, an independently labelled pair, a clean curved/oblique control, body builders, delivery QA,
design-source confirmation of v007.

**Budget / stop rule.** One run of the harness = confirmation (step A) + one candidate R6 (step B); zero retunes;
stop at the first complete verdict or 15 min wall. Harness-mechanics failures: up to 3 different repairs, each
logged with its error. A valid negative result ends the round. Even a pass licenses no adoption: R6 is derived from
in-sample labels and must be checked on an independent labelled pair before any `mesh_quality_core` PR.

**Forbidden.** Changing R3/R6 after measuring, thresholds, weights, zones, `irregular_deg`, inputs or dumps;
editing `tools/qa/mesh_quality_core.py`, body builders, delivered models/packages, test selection, or files of
other cards. Ownership exclusions (readiness `2026-11-21_0249.json`): #1315/#1622/#1738 cold Ground,
#1748/#1751 cold entry/skeleton, #1722 63B stage 2, #1649 atlas, #1609/#1627 KPP1, #1736/#1742 builder/causes,
#1615 suite.

Replay: `../../.venv/Scripts/python.exe docs/research/autoresearch-body-mesh-convex-quad-harness/replay.py C:/x/ar15/r1/tmp <new-receipt.json>`
(`--witness` runs the predicate checks only).

## Round log

(filled after the run)
