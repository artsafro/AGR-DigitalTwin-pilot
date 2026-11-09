# Experiment: advisory 6-view VLM defect checklist before the human acceptance sheet (#768)

Research only. **No checker, gate, threshold or decision was changed**; nothing in the pipeline reads the output.
`docs/research/agent-harness-practices.md` (runner adds no LLM judges) stays true: the runner is a separate tool.

## Question

Can a VLM looking at 6 RGB views catch the "does not look like the slide" defects that the human acceptance sheet
[D125] catches, at recall >= 80 % on a known failing model and <= 1 false positive on an accepted one?

- **Variant A** — fixed 12-item binary checklist (panel colour, frame colour, plinth colour, rib count per facade x4,
  field outline, door, windows, no extra elements, NPM vs VPM consistency); `tools/qa/vlm_checklist.py`
  `CHECKLIST_A`. The checklist output format and the 6-view RGB input follow arXiv 2607.10826; the 12 items
  themselves are our own (the paper's defects are generic and judged against a text prompt, not a slide). See
  "Primary-source provenance" below (M1-M3).
- **Variant B** — generated yes/no questions, adapted from arXiv 2410.05340 (CADCodeVerify): the VLM reads the
  slide + legend, writes 8-12 yes/no questions with a category and a facade, then answers them on the renders.
  Questions are generated once per slide, so v007 and v010 get the same questions (M4-M5).
- **Both-order.** Pairwise: v007 vs v010 per item, "first / second / equal", in both orders; only order-consistent
  winners are kept — the swap-and-keep-consistent correction of arXiv 2606.18451, adapted (M6). Checklist: every
  checklist is answered twice, views in forward and reversed order; an item whose two answers differ is
  **dropped** (and counts as missed) — **our own heuristic**, not in that paper (M7).

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

**Acceptance amended (Artem 2026-11-03, option b):** the point "time and cost per building vs the human sheet" is
reduced to "VLM time/cost only, human side not measured". The repository has no timed record of a human
acceptance-sheet session, so the human column above stays **not measured**; no human-side number is claimed.

Pairwise answer validation (review round 1): every raw pairwise list is checked before scoring (each item exactly
once, value `first|second|equal`, no unknown id); duplicates fail with a named error and exit 1. Re-checked on the
retained raw bundles: 8/8 pairwise calls (run 1: 4/4, run 2: 4/4) pass the strict parser, so the measured numbers
above are unchanged.

## Primary-source provenance (#781)

Checked 2026-11-04 against the arXiv abstract pages, the full-text HTML of the latest versions below, and
OpenReview. Snapshots: `G:/Мой диск/AGR-evidence/781-vlm-provenance/` + `SHA256SUMS.txt` (8/8 OK). All three are
arXiv preprints; only 2410.05340 has a venue (ICLR 2025 poster, OpenReview note `BLWaTeucYX`; its arXiv page has
no journal-ref). Quotes are verbatim from the HTML.

| arXiv | Title, authors, dates | Passage used |
|---|---|---|
| 2607.10826v2 | "3D-DefectBench: A Controlled Factorial Study of Vision-Language Model Evaluation Pipelines for Fine-Grained 3D Generation Defects", Zhao, Jia, Je, Tang, Chan, Spedden, Palleschi, Huang, Wang et al.; v1 12 Jul 2026, v2 6 Oct 2026; cs.CV | Abstract: “a compact six-view RGB protocol performs comparably to denser view sets and configurations augmented with depth or normal channels, making it a strong cost-effective default.” §4 Prompt schemas: “a full rubric with named failure examples emitted as a per-defect checklist (Rubric-Guided Checklist, used by c004 )”. Abstract: “the best of 12 VLMs still trail trained human labelers”. |
| 2606.18451v1 | "A Cross-Model VLM-Judge Protocol for Single-Image 3D Mesh Quality (and Why Cheap Proxies Fall Short)", Asaria, Salomone, Gandhi (Transformer Lab); v1 16 Jun 2026; cs.LG | §3 Position-bias correction: “For each pair we query the judge in both orders ( A,B and B,A ) and keep the verdict only if it is consistent across the swap; order-dependent verdicts are discarded as position-biased.” |
| 2410.05340v2 | "Generating CAD Code with Vision-Language Models for 3D Designs" (CADCodeVerify; CADPrompt benchmark), Alrashedy, Tambwekar, Zaidi, Langwasser, Xu, Gombolay; v1 7 Oct 2024, v2 28 Feb 2025; cs.LG; ICLR 2025 poster | §3.3: “CADCodeVerify first generates a set of binary “Yes/No” verification questions, …, based on the language description”; “CADCodeVerify generates between two to five questions per example”; “To answer these questions, CADCodeVerify uses the reference images of the generated 3D object”. |
| 2412.13810v3 | Mallis, Karadeniz et al.; v1 18 Dec 2024 | **Not a source** of this experiment; listed only to correct the #768 wording (below). Title: “CAD-Assistant: Tool-Augmented VLLMs as Generic CAD Task Solvers”. |

Method attribution. Status: `paper-supported` = the paper does this; `adapted` = the paper's mechanism with changed
inputs or use; `own heuristic` = in none of the three papers.

| id | element | status | basis / difference |
|---|---|---|---|
| M1 | 6 RGB views as VLM input | adapted | 2607.10826 §5.4: six oblique turntable views packed into one 3x2 grid image; ours = 4 orthographic elevations + VPM iso + NPM iso as 6 separate image files. |
| M2 | binary per-item checklist output | paper-supported | 2607.10826 Table 3, Rubric-Guided Checklist (c004). |
| M3 | the 12 items of `CHECKLIST_A`, judged against a colour-scheme slide | own heuristic | the paper's 9 defects are generic geometry/texture/prompt-adherence defects judged against a text prompt; no reference image. |
| M4 | VLM writes yes/no questions, then answers them on images of the object | paper-supported | 2410.05340 §3.3. |
| M5 | questions from slide image + legend, 8-12 per slide with category and facade; answers scored for recall/FP | adapted | paper: from a text description with few-shot examples, 2-5 questions, an "Unclear" answer allowed; answers feed code refinement, not defect scoring. |
| M6 | pairwise A/B in both presentation orders, keep only order-consistent verdicts | paper-supported | 2606.18451 §3; ours compares per item and allows "equal" (the paper describes no tie option), 6 views instead of its 24-view rig, Claude Sonnet instead of Qwen2.5-VL-7B / InternVL3-8B. |
| M7 | single-object checklist answered with views forward and reversed; inconsistent items dropped and counted as missed | own heuristic | 2606.18451 swaps the order of the two candidates in a pair, not the order of views; 2607.10826 mentions position bias only in related work and does not swap. |

Corrections to earlier attributions: the #768 issue text called variant B "CAD-Assistant/CADPrompt style".
CADPrompt is the benchmark of 2410.05340; **CAD-Assistant** is a different paper (arXiv 2412.13810, Mallis et al.)
and is not a source of this experiment.
"ICLR 2025" for 2410.05340 is confirmed by OpenReview, not by arXiv. Both-order on the checklist was earlier
credited to 2606.18451 as a whole; only its pairwise part is (M6 vs M7). None of the three papers measures recall
on architectural facade defects; the thresholds (recall >= 80 %, <= 1 FP) are ours. This section changes no number,
verdict or gate.

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
