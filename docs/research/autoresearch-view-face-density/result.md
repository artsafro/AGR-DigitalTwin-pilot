# #146 — OBSERVE round result

**Hypothesis: inconclusive (budget stop). Adoption: no.** A complete fresh pair (212/212 full historical baseline rows equal across ELV, KPP1/AC08, OBR22) ran on `45314587c53413494e01a9cda4bbdf6e0cf95f0e`. The trial failed the safety bound on this pair; it is not a three-pair refutation. `receipt.json` contains the native case groups, candidate scores, historical verdicts, changed-pixel counts and pair digests. The frozen method and full input pins are in the contract and its referenced Git objects.

| Cohort / scope | A: correct / wrong / abstain | B: correct / wrong / abstain |
| --- | --- | --- |
| ELV full (clean) | 5 / 0 / 2 | 7 / 0 / 0 |
| ELV real fragments incl. top-cut (clean) | 1 / 0 / 2 | 1 / 0 / 2 |
| ELV synthetic partials (injected) | 15 / 13 / 35 | 37 / 1 / 25 |
| KPP1 full (clean) | 3 / 0 / 1 | 3 / 1 / 0 |
| KPP1 synthetic partials (injected) | 22 / 0 / 14 | 26 / 1 / 9 |
| AC08 full + synthetic partials | 0 / 0 / 40 | 0 / 0 / 40 |
| OBR22 full + synthetic partials | 0 / 0 / 40 | 0 / 0 / 40 |
| ELV mirror (injected) | 2 / 1 / 4 | 2 / 1 / 4 |
| KPP1 / AC08 / OBR22 mirror (injected) | 0 / 0 / 9 | 0 / 0 / 9 |

ELV synthetic answered accuracy 15/28 → 37/38, abstention 35/63 → 25/63. The one remaining wrong ELV crop (`p19 A-I`, `partial25@1.0`) still picked the dense east face. New KPP1 wrongs: `В-А` full, and `А-В` at `partial40@1.0`. Of the two clean real fragments that still abstained, one was top-cut. Three AC08 mirror views did not change any pixel and are **not exercised**; AC08 and OBR22 provide no positive-match retention evidence under this scorer. Not measured: other perturbations, real unlabeled inner-corner transfer, exact within-face position, G22, Vatutino, Sokolniki. No Sokolniki key was opened (#2001 OPEN).

Pair wall time 299.011 s (ELV 193.886, KPP1/AC08 34.659, OBR22 70.459). Series wall 299.110 s; projected requirement 986.835 s vs frozen 840 s. Three-pair median/spread and repeatability are **not measured**. Conditional replay from the pilot host (pinned branches available): `uv run --offline --locked --extra cad --extra pdf-review python docs/research/autoresearch-view-face-density/run.py tmp/ar146-idle-fresh`. First pair must be roughly 254.5 s or faster; the replay makes the exact stop decision. Inputs are readable on the pilot host; replay is limited off-host (workspace paths and mounted source files).

Recommendation for the shared OKS-trail step: expose the matched crop, top candidates, score/margin and source evidence; keep finish transfer manual when the raw and chance-corrected scorers disagree or the physical face/bay lacks independent support. This disagreement veto is a **next hypothesis**, not a measured gate. Next measure (1) disagreement veto on the exact same labeled cases (check both blocked wrongs and lost correct coverage); (2) footprint-edge IDs plus corner/return context on real ELV fragments, so similar directions do not collapse to an azimuth-only answer; (3) Sokolniki transfer only after #2001 closes. No production step or delivery artifact was changed.
