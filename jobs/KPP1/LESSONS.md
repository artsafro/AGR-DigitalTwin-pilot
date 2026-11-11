# KPP1 — lessons (job-local)

Rules learned on this job, for the next agent on KPP1. Source of each: the run named in brackets.

- **Sources are not on the asset store.** The АС.03 DWGs (L01 / L02 / L03) are in `C:/Users/artsafro/Downloads`
  (SHA-256 in `cold-run-1172/inputs-manifest.json`, equal to `sheet-census.json`). Check the hash before use;
  do not trust a `C:/x/...` readback path from an older report, those folders get wiped. [#1172]
- **DXF readback without Max:** `accoreconsole.exe /i <copy.dwg> /s <script>` with `_.DXFOUT <path> _V _2018 16`
  on a copy, never on the source; compare the copy's SHA-256 with the source. [#1172]
- **Reproduce the plan contour** with `cold-run-1172/layer-map-L03.txt` and the command in
  `cold-run-1172/plan-repro-v001.json`; bands, coverage and the 2 005-entity account come out identical. The
  committed `plan-contours.json` has three hand-written fields (`method`, `opening_decision`, `source`). [#1172]
- **One plan, two bands.** `plan_from_dxf` copies the L03 plan into 0.000-3.900 and 3.900-7.909, including the
  0.70 m entrance-frame bumps; Revit L1 is the plain rectangle. Do not build the upper band from it before
  the user answers question 1 of `parts-v001.json`. [#1172]
- **PartsList validator:** a `to_texture` part carries 0 triangles; a `pdf` source needs `page`; type a DWG
  source as `model` (as `jobs/COD-20207`). Validate with `dt_ai.core.models.PartsList` before the walk. [#1172]
- **job.yaml evidence is repo-relative only.** List external sources in a committed manifest and put the
  manifest in `inputs`; a direct absolute path makes the walker fail without writing output. [#1172]
- **No build before Gate 1.** The walk stops at `parts: review` until the user confirms the PartsList; record
  Max-only steps as `missing` with a `waits-max` note, never as `pass`. [#1172]
- **Write receipts with LF** (`open(..., newline='\n')`) and walk a fresh `git worktree add --detach` of the
  commit before review: `.gitattributes` turns CRLF into LF on commit and the hash no longer matches. [#1172]
- **Facades of a Revit-exported DWG are readable without a dimension parser.** Each view's blocks carry the facade suffix (`О_АР_Ф_Южный` ...); grid lines give the u origin and the drawing Y is the elevation in mm. Opening rectangles = merged insert bboxes per facade. [#1209, D238]
- **The regulation grammar joins parts.** VPM/NPM allow only `Main` / `MainGlass` (+UCX), so count per-part triangles before the join and expect V004 self-intersections where joined parts touch. [#1209]
- **A single FBX cannot reach `passed=true`.** V001/V011/V013 need the ZIP and the GeoJSON; record the blockers (stage, value, limit) instead of chasing a pass. [#1209]
- **Provisional geometry approval is not delivery certification.** Roof/parapet values are provisionally approved in [D248], while the architect question remains open. Resolve a new `passed=true` target against the existing [D224] placement deferral before rebuilding; never sign V015-V017 for the user. [#1209]
