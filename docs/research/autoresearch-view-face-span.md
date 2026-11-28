# H165 — full-view length-agreement veto (OBSERVE)

## Кратко для Артёма

(заполняется после замеров — см. Round log)

## Frozen contract

Standing #165, `t_ce910adf`. Continues #163/#164 on the same Silikatny wall-segment fixture (#164 next (2):
plan corroboration for the singleton A'-K vs the exclusion K-A). Not the finish-partition work (#2073/#2074),
not the wall-exercise scorer (#2075). Readiness 2026-11-28_0836. #2001 is OPEN: no Sokolniki input or key opened.
Atlas, form and trainer targets stay parked.

**Problem.** #163 answers K-A -> W19 (false: K-A is a separate nine-column facade, #164 exclusion witness) and
A'-K -> W19 (correct). #164's singleton veto removed both. The #163 width gate is one-sided
(`view_w <= 1.10 * render_w`), so a 55.75 m full elevation may land on a 72 m wall.

**Hypothesis H165.** A pure veto on the #163 answer: for a view of kind `full` (frozen #161 fixture label), the answered
wall must also satisfy the plan length agreement `|view_w / render_w - 1| <= fit_tol` (the same frozen `fit_tol = 0.10`
and `render_w_m` the #163 gate uses; no new parameter, no sweep). Fragments are exempt. The veto never changes the
top wall, the margin or the competitor set, so it cannot create an answer. Expected on the clean native views:
K-A W19 -> abstain (55.75 / 72.068 = 0.774), A'-K W19 kept (74.25 / 72.068 = 1.030), fragment 1 W19 kept (exempt),
the four native abstentions unchanged. Expected directions were set from the published #163 receipt numbers.

**Diagnostic arm C (not a keep candidate).** Two-sided eligibility (rerank inside the narrowed set). Recorded to show
whether narrowing the competitor set manufactures margins; expected A-G (ungraded) to become an answer.

**Fixture.** Seven fixed #163 views (Silikatny AGR album PDF SHA-256 `785e4015…`, Revit OBJ `6ab64e6b…`, pinned in #161
fixture.json; Blender 4.4 hash pinned in #163). Revisions: #163 `56f608b577090a8f82cf4e2df2c722879199e378` (staged blobs
hash-pinned as in #164), #164 native baseline body SHA-256 `5cedce6e622d06b092a0b7be146623feee51a23a83b2ea0a6d79d03849709aca`
(must match in every pair). Graded rows: the five #163 GT rows; K-A only as the W19 exclusion witness; A-G diagnostic.

**Metric.** correct / wrong / abstain on the five graded rows + answered accuracy + abstain rate; K-A exclusion separately.

| Acceptance point | Concrete input | Expected | Check |
|---|---|---|---|
| Positive trigger | native K-A, A = W19 | B abstains | replay + `test_short_full_view_vetoed` |
| Correct answer kept | native A'-K (full), fragment 1 (fragment) | B = W19 for both | replay + `test_matching_full_view_kept`, `test_fragment_exempt` |
| Accepted control on which the rule fires | A'-K resampled x0.85 horizontally (I1) | B vetoes the A answer | replay |
| Lever isolation | K-A stretched to 72.068 m (I2) | veto does not fire (B = A, ungraded) | replay |
| Load-bearing label | fragment 1 relabelled `full` (I3) | veto fires -> abstain; reset (I4) restores W19 | replay |
| No invented answers | A abstentions, 7 blank masks, mirror/shuffle | B never answers where A abstains | replay + `test_never_creates_answer` |
| Stable evidence | three fresh Blender + PDF pairs | baseline hash = #164 body; B digest identical | replay |

**Keep predicate (follow-up recommendation only).** All three pairs finished, parity holds, graded B = 2/0/3, K-A B =
abstain, every other clean B equals A, I1 and I3 veto, I4 restores, B never answers where A abstains.
A completed series missing any bound = `refuted`; parity failure or budget stop = `inconclusive`.

**Budget and stop.** Three pairs, hard 10 min; after pair 1, continue only if 2x its wall time fits. No threshold sweep,
no other candidates. Forbidden: production code, delivered models/drawings, locked standards, other cards' files,
deselecting tests, loosening #163 parameters, protected holdout (Sokolniki).

**Not measured by design.** Automatic full/fragment detection on untitled views (the veto depends on the frozen label);
K-A's true wall; A-G truth; curved/developed walls; bay intervals; accepted/rejected delivery calibration; STOP 04.

**Replay** (pilot host with the owner's Weltbau folder and Blender 4.4):

```bash
git fetch origin research/autoresearch-standing-161 research/autoresearch-standing-162 research/autoresearch-standing-163
uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-span/run.py C:/x/ar165/<fresh>
```

## Round log

(after measurement)
