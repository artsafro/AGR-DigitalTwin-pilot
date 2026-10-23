# Vyatskaya TOW02 — source class

Object: tower TOW02, ul. Vyatskaya vl. 47–49. Target profile recorded on the job: mid-poly master
of the curtain-wall tower. The three facts below are the recorded classification in
`jobs/vyatskaya-tow02/object.json` (`source_class`, `source_class_note`), not a fresh measurement.
The raw inventory `jobs/vyatskaya-tow02/outputs/measure-v001` is git-ignored and absent on this PC.

## Source class

| Fact | Value |
|---|---|
| Connected parts | 5561 (`RC_TOW_02`) |
| Largest part share | 11% of its area (z 37.5–71.5) |
| Shell present | no |
| Source class | `panelised` |
| Route | `measurement+direct-build` (measurement and a direct build). `dt spec extract` does not run on this class |

Rule 1 [D066] (`PANEL_HINT_SHARE` = 0.5 in `src/dt_ai/spec/mesh.py`; HARNESS_PLAN §4): a source is
`panelised` when the part count is at least two, the largest share is strictly below 0.5, and no
closed shell is present. 5561 parts, a largest share of 11%, and no shell meet that rule, so the
route is measurement and a direct build. Contours are taken from the panels on the slabs.
