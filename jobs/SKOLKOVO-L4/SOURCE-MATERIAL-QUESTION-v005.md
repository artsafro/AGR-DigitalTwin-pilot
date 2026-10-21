# Skolkovo: exterior finish authority before final PartsList

Status: **needs user input**, not Gate 1, not a request to approve the current
subset. Interior/opaque-glazing and roof-mast decisions are already answered and
are NOT reopened. No kernel build or automatic material fallback has run.

## Exact question

May the **delivered final VPM appearance** be used as material authority for
exterior surfaces not explicitly mapped to the album/revision legend (roof
membrane, soffits, small exterior details and exposed rooftop-shaft substrates),
while geometry remains derived from the source/revision FBX? Alternatively,
please supply their intended finishes or an explicit job-level finish choice.

Recommendation: authorize delivered VPM **appearance only** for those unmapped
surfaces; keep every such association explicit and hash-pinned. Do not copy its
geometry, do not assign the first material slot, and report that those material
comparisons are reference-derived rather than independent validation. Source
material names that identify actual finishes, such as LOGICROOF V-RP, remain
recorded; they must not be silently replaced with an arbitrary RAL colour.

## Concrete witness, not a speculative missing-texture claim

Corrected source geometry has three small rooftop enclosures whose twelve walls
are named `Basic Wall ADSK_Наружная_Утеплитель_100`. Their sole census material is
`ADSK_Изоляция_Минеральная_Вата минеральная`. This establishes a substrate role,
not an approved visible finish. Each wall has positive raw-source exterior
raster samples, all above Z=11.5 m. They cannot simply be dropped as interior
because their names contain insulation, nor assigned Ф.1 or Ф.10 by default.
Positive samples are not proof of intended architectural exposure.

| Sheet marker | Zero-based facade census rows | Source Z range (m) |
|---|---|---|
| 1 | 5402–5405 | 11.55–14.00 |
| 2 | 5406–5409 | 11.55–13.60 |
| 3 | 5410–5413 | 11.55–14.00 |

The twelve exact names, SHA-pinned census-row locators, bboxes and per-view
samples are in `evidence-v005/source-material-witness-v005.json`: **12 objects,
924 positive samples**. No absent-sample inference is used for a drop.
The diagnostic is geometrical source visibility, not a delivery render.

Investigated: all 26 extracted album texts and all 4 revision texts; album
pages 15/16 define the facade legend; album page 21 identifies roof levels and
drainage, not a material association for these twelve substrate walls. Visual
inspection of album page 6 and revision page 1 does not establish that missing
association. The existing subset also still uses provisional `source:*`
legend tokens; neither a census material name nor an image pixel is treated as
a confirmed material mapping. This does not assert that every page image or
unread Revit parameter has been checked. Revit was not run.

## Viewing and provenance

Drive folder: `G:/Мой диск/AGR-evidence/353-skolkovo-l4/evidence-v005/`.
Open `source-material-question-v005.png`; its numbered boxes locate the three
source enclosures. Object colours are diagnostic colours, **not** a material
legend. Hashes and the source-only reproducibility ZIP are indexed by
`SHA256SUMS.txt` and `evidence-v005/resume-v005.json`.

The delivered VPM supplied as the comparison reference has a 55,998-triangle
Main and 442-triangle MainGlass in the prior native census. Its use as missing
finish authority has not been assumed from its reference role. No finish has
been invented to make the draft appear complete.

After this answer: finish the exterior/revision/legend/joint reconciliation,
then request Gate 1 on the exact final source-complete PartsList hash. The
current 20-group subset still has 1,695 facade review rows; it is NOT that final
PartsList and its allocation is not a measured output budget.
