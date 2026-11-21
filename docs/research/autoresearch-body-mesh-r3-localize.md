# Body mesh quality — standing #19, where R3 penalises accepted 63B v007 (OBSERVE)

**Кратко.** _(заполняется после замера)_

## Frozen contract (written before any measurement)

Continues #17 (`autoresearch-body-mesh-neighbours-r3.md`, immutable harness `6ae13568ca85bb3880e84f4f1a30f22f6c23a96d`)
and #18 (`autoresearch-body-mesh-holdout.md`, `789b2c895ae181ad098dbbd912c183a4393d6990`). R3 lowers the ACCEPTED
63B v007 by 4.29 points (local share 0.621, 84.332 → 80.039); #18 found no false drop on 63A v005 / G22 k2 and
left the v007 penalty unexplained.

**Metric (one number):** R3 false drop on accepted 63B v007 = median(R0) − median(variant) in score points, three
repeats on the retained #15 dumps `C:/x/ar15/r1/tmp/63B-v007.{1,2,3}/dump.json` (byte-content equal, SHA-256 in the
receipt). Baseline R3 = 4.293 (pinned #17 receipt `r3.json`).

**Step A — localisation (observation, no candidate).** Splice into the R3 candidate a read-only sink that exposes
R3's own `bad` set and edge-neighbour patches (no arithmetic change; the spliced score must equal R3 bit-for-bit,
and R3 must equal #17's 80.039). Report for v007: top 10 seed patches by local share (seed face, local share,
patch area, centroid, normal, corner angles), and the irregular area of all faces in patches with local
≥ 0.5 × max local split by class: `horizontal` (|n_z| ≥ cos 1°), `vertical` (|n_z| ≤ sin 1°), `sloped`
(other), and separately triangles. Same class split for the six rejected 63B versions (diagnostic only).

**Decision table (frozen; exactly one branch):**

| Dominant class of v007 worst-patch irregular area | Step B |
| --- | --- |
| horizontal quads/ngons ≥ 50 % | R4 = R3 with horizontal faces (\|n_z\| ≥ cos 1°, the core's `flat_deg`) excluded from `bad` (seeds and counted area); global share unchanged |
| vertical, sloped or triangles | no candidate this round; report the face groups for a design-source check |

**Step B keep threshold (in-sample + held-out, still OBSERVE):** v007 drop ≤ 0.500; worst accepted-minus-rejected
margin over the nine #13 pairs ≥ 0.500 at shifts (0,0,0) and (−5,7,11) m with identical scores across shifts;
drop on held-out accepted 63A v005 (`C:/x/ev_t_f55bc192/63A.dump.json`, from the #18 readback) and G22 k2 v002r1
(`C:/x/ev_1619/r7/k2_v002r1.mq.json`, SHA-256 `2e922754…431b`) ≤ 0.500; three repeats identical; report parity with
R0 outside `score`, `penalties.irregular_area_share`, `local_irregular_area_share` (#14 `canonical`); #14 clean
rectangle + reset and injected skew witnesses pass. A keep only licenses a separate PR on `mesh_quality_core`
after an independent labelled pair; nothing is applied here.

**Budget / stop rule:** one confirmation (R0 + R3 reproduce #17 for all 13 inputs at (0,0,0)), at most one new
candidate (R4, only via the table), zero retunes. Wall cap 30 min. Harness-mechanics failures: up to 3 different
repairs, each logged with its error. A valid negative result ends the round.

**Forbidden:** changing R3/R4 beyond the table, weights, zones, `irregular_deg`, inputs or dumps; editing
`tools/qa/mesh_quality_core.py`, body builders, delivered packages, test selection, or files of #1736/#1742
(builder / causes), #1739/#1751 (skeleton), #1722 (63B stage 2), #1649 (atlas), #1609 (KPP1), #1315/#1622
(cold runs), #1615 (suite). Distance-to-etalon on G22 k1 is not used (it rewards the rejection, #12).

Replay: `../../.venv/Scripts/python.exe docs/research/autoresearch-body-mesh-r3-localize-harness/localize.py C:/x/ar15/r1/tmp <out.json>`.

## Round log

_(filled after the run)_
