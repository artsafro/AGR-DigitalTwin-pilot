# Standing #38 — Qe across triangulation (OBSERVE)

## Contract (freeze before measurement)

One target: portability of the already calibrated Ground short-edge density `Qe = 10000 E/T` (#35). `E` counts
unique undirected index edges of length ≤ 0.002 m; `T` is the sum of polygon `n-2`. Lower is better. Since export
may triangulate while review preserves quads, a new diagonal can be short even when no original edge was short.
Do not confuse the two states if this happens. This is a diagnostic only, not an FBX/DCC export simulation or a gate.

**H38 (keep threshold for the observation, not for adoption).** On every fixture Qe is invariant (exact E and T,
ΔQe = 0) under both deterministic in-memory polygon fanizations, root at corner 0 and corner 1 in existing winding
(order modulo polygon length). No vertex movement, reordering outside each face, welding or scene write. Raw
`measure` is the unchanged #35 reader/scorer. Compare the complete clean E/T/Qe/V counters with sealed #35/#36
receipts. Every repeat (3 per state; median and max−min) must agree; parity of T and V must hold for both variants.
For each of the three states separately require `min(F) > max(A)` and `min(F) >= 2 * max(1, max(A))`, pooling the
accepted NPM and VPM controls; this is not VPM rejection calibration. An E change or failure of separation after
successful oracle/parity checks refutes H38; oracle/parity/determinism failure or incomplete budget is inconclusive.
This experiment does not test validity of triangulations for concave polygons or real exporter triangulation policy.

**Fixture (no substitutions).** All A1–A8 and F1–F5 #35 (Vatutino v015 and seven delivered NTR NPM Ground vs
SIL13 r1–r5; F3/F5 identical). Use #31 manifest `autoresearch-ground-quality-harness/dumps.sha256` and #35 receipt
from immutable `ec403b83113d89f6b8a98f648421a33a17819603`; score the same single `*_Ground` node. Add delivered
Skolkovo, COD and Donskoy VPM (paired with A2–A4), dump paths, hashes and exact census scope as frozen in
`c6e4fb78d6a77b1809600ef453a80a718d15ca0c:docs/research/autoresearch-ground-qe-transfer-r36.json` under
`C:/x/ev_t_cb0ffb18/r36-v001/`; the #36 Ground node may include merged context. Use no new deliveries and do not
change `C:/x/ground-etalons/` (copies/manifests already established in #31/#32/#36). After baseline separation is
confirmed, score both original and fan variants of the first #1738 export (same original OBJ and SHA-256 as #35;
v003 is byte-identical to v006 per #37). Require clean parity with all four #35 core counters and verify stability
with the same per-variant bounds; core is descriptive, not a calibration label.

**Trigger and collateral.** Positive witness (synthetic, never a delivered asset): append one convex quad, isolated
by +10000 m in X, to A1 using offsets `(-1,0,0),(0,-0.0005,0),(1,0,0),(0,0.0005,0)`; expected difference from
A1 in each corresponding state: ΔT=+2 and ΔE=(0,0,+1) for raw/fan0/fan1. Verify associated short-diagonal edge
IDs on the synthetic witness and real fixtures by comparing the raw and triangulated short edge sets: no removals,
and every added flag must be an inserted index diagonal. Record accepted controls with E>0 separately for each
state; for a firing control publish paired ΔQe (same upper bound 0). If none triggers, collateral on triggering
accepted work is not measured. No fake acceptance label for injection and no threshold retraining.

**Budget and stop.** One confirmation series, zero other candidates. Measure A1 + F4 and largest (Donskoy VPM)
first; project 10× first pair plus 2× largest, stop inconclusive if over 240 s or less remaining card time; absolute
series cap 240 s. Stop after the completed series; one fresh-process replay to compare receipts ignoring timing.
No tolerance changes, deselections, threshold/gate implementation, edits to deliveries or other cards’ files, no
Ground build or repair. Relief/skirt (#1738/#1787), cold delivery (#1315/#1622), body (closed) and atlas (#1649)
are not targets. Native Max/Blender exporter, rejected VPM, independent rejected site, UV/visual changes not measured.

**Replay** (repo root; same PC only, customer inputs outside Git):
`../../.venv/Scripts/python.exe docs/research/autoresearch-ground-qe-triangulation-r38.py docs/research/NEW-r38.json`.
