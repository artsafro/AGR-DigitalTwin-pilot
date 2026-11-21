# Standing #17 — R3 worst margin over the full translated fixture (OBSERVE)

## Frozen contract (written before any measurement)

Continues standing #16 (`docs/research/autoresearch-body-mesh-neighbours.md`, branch head `63960134`), which
stopped at its five-minute cap after the `(0,0,0)` shift and published no metric. This round measures exactly
the metric #16 froze; nothing in the formula, fixture or harness changes.

- Metric: minimum accepted-minus-rejected median `mesh_quality_score` over the nine #13 same-building pairs,
  over the four translations `(0,0,0)`, `(1,1,1)`, `(3,0,2)`, `(-5,7,11)` m, for variant R3 (edge-neighbour
  patch local irregular share, #16 splice, candidate core SHA-256
  `ec35063d3617c9cd000079ce184e75bc799645daf1040bcb13b84561aaa557df` UTF-8/LF; base core
  `6458a5a1282d31d9212ef195ffcd0f21f27165984b54677c93e1f0b1df7333dd`).
- Command (replay): `../../.venv/Scripts/python.exe docs/research/autoresearch-body-mesh-neighbours-harness/neighbours.py C:/x/ar15/r1/tmp C:/x/ev_t_79b9c690/r3.json`
  at the immutable harness revision `63960134e76d4730c4c2a7fef4466bc28ed0adf9`; scorer source pinned at
  `82875426d52dadd63b59814d97e46d44570806e2` (`tools/qa/mesh_quality_core.py` identical on `origin/main` `346b9b12`).
- Fixture: the 13 #13 inputs with labels, source SHA-256 and zones from `calibrate.py` at `82875426`; native
  dumps are the retained #15 R1 dumps `C:/x/ar15/r1/tmp/<key>.{1,2,3}/dump.json` (three per source, must be
  byte-content equal; their SHA-256 are written into the receipt). Sources re-hashed before and after.
- Repeats: three calls per input × translation × variant; the median per input is the score.
- Budget: one confirmation variant (R0, must reproduce all nine #13 margins at every translation) and one new
  variant (R3). No second candidate, no retune in this round. Measurement time cap: 30 minutes wall,
  run detached with the receipt as result file.
- Keep threshold (in-sample signal only): worst R3 margin ≥ 0.500 points, scores invariant across
  translations, all repeats identical, all parity checks pass. Even a pass is OBSERVE: no production rollout;
  it only licenses a held-out check (independent clean oblique/curved body + labelled held-out pair).
- Stop rule: one complete run. If the run fails inside the harness (not the formula), up to 3 different
  repairs of the harness mechanics only, each logged with its error.
- Forbidden: changing the R3 formula, weights, zones, angle threshold or inputs; deselecting tests; weakening
  checks; editing delivered packages, body builders, `tools/qa/mesh_quality_core.py`, or files of
  #1735/#1736/#1742/#1609/#1649.
- Parity: per input and translation, R3 report equals R0 except `penalties.irregular_area_share`, `score` and
  the new `local_irregular_area_share` diagnostic (#14 `canonical`). Clean = #14 synthetic rectangle control
  and reset; injected = #14 synthetic skew witness. Not measured: fresh native readback, held-out bodies,
  body builders.

## Round log

(filled after the run)
