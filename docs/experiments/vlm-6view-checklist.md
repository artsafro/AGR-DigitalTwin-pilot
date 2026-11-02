# Experiment: advisory 6-view VLM defect checklist before the human acceptance sheet (#768)

Research only. **No checker, gate, threshold or decision was changed**; nothing in the pipeline reads the output.
`docs/research/agent-harness-practices.md` (runner adds no LLM judges) stays true: the runner is a separate tool.

## Question

Can a VLM looking at 6 RGB views catch the "does not look like the slide" defects that the human acceptance sheet
[D125] catches, at recall >= 80 % on a known failing model and <= 1 false positive on an accepted one?

- **Variant A** — fixed 12-item binary checklist (panel colour, frame colour, plinth colour, rib count per facade x4,
  field outline, door, windows, no extra elements, NPM vs VPM consistency); `tools/qa/vlm_checklist.py`
  `CHECKLIST_A`. Idea: arXiv 2607.10826 (checklist judge), forum harvest; not re-checked against the paper body.
- **Variant B** — generated yes/no questions (arXiv 2410.05340 style): the VLM reads the slide + legend, writes
  8-12 yes/no questions with a category and a facade, then answers them on the renders. Questions are generated
  once per slide, so v007 and v010 get the same questions.
- **Both-order** (arXiv 2606.18451 idea): every checklist is answered twice, views in forward and reversed order;
  an item whose two answers differ is **dropped** (and counts as missed). Pairwise: v007 vs v010 per item,
  "first / second / equal", in both orders; only order-consistent winners are kept.

## Setup

- Objects (existing local evidence, no new client files): AC08 pilot-v007 (rejected; known failing), AC08
  pilot-v010 (the accepted control), AC09 build-v001 (no labelled ground truth). Config:
  `docs/experiments/vlm-6view-checklist.objects.json`.
- 6 views per object = the existing headless renders `vpm_south/north/east/west`, `vpm_iso`, `npm_iso` (no new DCC
  run; the repo renders have no top view, so the 6th view is the NPM iso). Reference = the facade colour-scheme slide
  of the building (AC08 slide 49, AC09 slide 53) and, for variant B, the legend rows of `vpm_textures.json`.
  The render-side -> slide facade label mapping comes from each object's `compare.json`.
- Ground truth, fixed in the config **before** the runs, from `jobs/TEC26-OKS/AC08/PILOT_REPORT.md` ("What changed
  after v007" + v007 counter-examples): 7 known v007 defects = rib count wrong on 1-2, 2-1, А-Б, Б-А (11/3 seams
  instead of 29/11), frame/edging grey instead of blue 5015 [D170], plinth blue instead of grey 7004, no dark field
  outline. v010: 0 defects (every flag is a false positive).
- VLM: Claude Code CLI 2.1.301, `claude -p --model sonnet` (resolved to `claude-sonnet-5-5`), image Read tool,
  `--setting-sources "" --strict-mcp-config --no-session-persistence`, cwd = an empty folder. 18 calls per run,
  4 in parallel. Cost = `total_cost_usd` of the CLI JSON (API list price equivalent); time = wall time per call.
- Input SHA-256: `docs/experiments/vlm-6view-checklist/input-SHA256SUMS.txt` (slide 49 `256f32da2a04…` = the slide
  hash in the AC08 pilot report). Per-run results: `vlm-6view-checklist/run-v00{1,2}.results.json`. Raw prompts and
  answers (they contain local paths): `G:/Мой диск/AGR-evidence/768-vlm-checklist/` + `SHA256SUMS.txt` (5/5 OK).

## Results (2 independent runs, same inputs)

Order-consistent answers only. "FP" = flagged item that covers no known defect.

| Object / variant | run | recall on v007 (7 known) | FP | dropped by order | order-consistent share |
|---|---|---|---|---|---|
| AC08-v007 A | 1 | **7/7 = 100 %** | 1 (A11 "irregular seams") | 0 | 12/12 |
| AC08-v007 A | 2 | **6/7 = 86 %** (missed outline: dropped) | 1 (A11) | A08, A12 | 10/12 |
| AC08-v007 B | 1 | 5/7 = 71 % (missed outline, plinth) | 1 (B04 "no step at door") | 0 | 12/12 |
| AC08-v007 B | 2 | 4/7 = 57 % (missed outline, plinth, 2-1 ribs: no question) | 0 | B12 | 11/12 |
| AC08-v010 A | 1 | — | **0** | A04-A07 (rib counts: fwd said "26 on slide, 30 in model", rev said ok) | 8/12 |
| AC08-v010 A | 2 | — | **0** | 0 | 12/12 |
| AC08-v010 B | 1 | — | **3** (B04 step, B06/B09 rib counts) | 0 | 12/12 |
| AC08-v010 B | 2 | — | **0** | 0 | 12/12 |
| AC09-build-v001 A | 1 / 2 | unlabelled | flags: none / none | 0 / A05 | 12/12, 11/12 |
| AC09-build-v001 B | 1 / 2 | unlabelled | flags: B02 (1-2 ribs) / none | B03, B07 / B05, B10 | 10/12, 10/12 |

Thresholds (recall >= 80 % on v007, FP <= 1 on v010):

| Variant | run 1 | run 2 | verdict |
|---|---|---|---|
| A fixed checklist | pass (100 %, 0) | pass (86 %, 0) | **meets both, 2/2 runs** |
| B generated questions | **fail** (71 %, 3) | **fail** (57 %, 0) | fails recall 2/2, FP 1/2 |

Pairwise v007 vs v010, both orders:

| Variant | run | order-consistent share | kept winners v010 / v007 / equal | dropped |
|---|---|---|---|---|
| A | 1 | 11/12 = 92 % | 8 / 0 / 3 | A08 |
| A | 2 | 11/12 = 92 % | 8 / 0 / 3 | A01 |
| B | 1 | 10/12 = 83 % | 9 / 0 / 1 | B04, B12 |
| B | 2 | 11/12 = 92 % | 10 / 0 / 1 | B09 |

No order-consistent pairwise verdict ever preferred the rejected v007.

### Why B loses

The generator counts ribs on the slide wrongly ("about 26 / 27 ribs" on 1-2, where the slide pixels give 29 seams =
30 ribs; "about 10 ribs" on AC09 1-2, where `compare.json` measured 13 seams on the slide and the render). A wrong
question turns a correct model into a false positive (v010 run 1: B06, B09; AC09 run 1: B02) and the generator
also leaves out items the fixed list always asks (plinth colour not phrased against the render ground line, field
outline merged into "narrow edging", in run 2 no 2-1 rib question at all). Variant A asks every item every time.

### What the VLM is good and bad at

- Colour items (frame, plinth, panels) were found in every run of A with consistent answers.
- Rib **counts** are unreliable: the VLM says "about 25" for a 29-seam slide, and on v010 run 1 the forward and
  reversed runs disagreed on all 4 rib items. Our count-based `compare_facades` measures these exactly (29/29/11/11 on
  pixels), so the VLM adds nothing there; the order filter is what kept v010 at 0 FP in run 1 (forward-only = 4 FP).
- Fine line items (field outline, 4 mm on VPM) are fragile: found in run 1, dropped by order in run 2.
- AC09: known discrepancies of the build report (top level +2.567 vs slide +2.450, illustrative glass reflection)
  were not flagged by either variant — the checklist has no level item and the VLM does not read elevation marks.

## Time and cost per building

| | VLM variant A (2 calls) | VLM variant B (2 calls + generation per slide) | human acceptance sheet |
|---|---|---|---|
| wall time | 33-41 s summed, ~20 s wall in parallel | 33-42 s + 14-21 s generation | **not measured** — the repo records no time for the sheet |
| cost | $0.18-0.23 | $0.18-0.24 + $0.04-0.05 per slide | Artem's time |
| pairwise v007/v010 (2 calls) | $0.32-0.33, 25-39 s | $0.33, 28-30 s | — |
| full run (3 objects, A+B, pairs, 18 calls) | | | run 1 $2.02 / 306 s summed; run 2 $2.02 / 333 s summed, 1 min 36 s wall |

The sheet stays mandatory [D125], so the VLM time and cost are **added**, not saved; they are small (< $0.25 and
< 1 min per building for A).

**Open acceptance point:** the "time and cost per building vs the human sheet" comparison is **not complete**. The
repository has no timed record of a human acceptance-sheet session, and no agent can produce one: it needs Artem to
time one sheet for AC08 v010 (start/end), or to amend the acceptance. Until then this report gives only the VLM side.

Pairwise answer validation (review round 1): every raw pairwise list is checked before scoring (each item exactly
once, value `first|second|equal`, no unknown id); duplicates fail with a named error and exit 1. Re-checked on the
retained raw bundles: 8/8 pairwise calls (run 1: 4/4, run 2: 4/4) pass the strict parser, so the measured numbers
above are unchanged.

## Verdict: **advisory** (variant A), not adopt; variant B: **no**

- Variant A met both thresholds in 2/2 runs on this one building pair, and pairwise never preferred the failing
  model. That is enough to run it as a pre-sheet hint ("look at the frame and plinth colours"), not enough to gate:
  one building, two runs, recall dropped from 100 % to 86 % between runs, and without the both-order filter v010
  would have had 4 false positives.
- Do not use it for counts or levels: `compare_facades` and the level checks already do that exactly.
- Variant B lost on recall in both runs; its question generator miscounts the slide.
- Adoption (where the hint shows up, which model, repeat count) is for a follow-up issue; this branch changes no gate.

## Reproduce

```bash
uv run pytest -q -p no:cacheprovider tests/test_vlm_checklist.py           # 28 scoring/fail-closed tests
python tools/qa/vlm_checklist.py --out C:/x/ev_<card>/run-v003 --workers 4  # needs the claude CLI logged in
# exit 0 = every call parsed; 1 = some call failed (listed under "errors"); 2 = refused input/output
```

The output folder must be new and outside every input folder (refused otherwise, nothing written).
