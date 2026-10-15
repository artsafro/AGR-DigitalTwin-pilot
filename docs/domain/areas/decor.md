# Decor — L1 requirement sheet

Area: OKS facade portals, belts, pilasters, cornices and decorative panels, NPM / VPM.
Out of scope: BODY construction, windows/doors, atlas/texture production, UCX construction,
Ground and delivery packaging. Their shared OKS budget is an interface, not a decor-only allowance.

Readiness: [roadmap §7.3](../../research/capability-roadmap.md#73-decor--l1-partial)
records **L1-partial**. This sheet supplies T-DEC-1's rule index, not a completed skill,
benchmark, L2 certification or user acceptance. The facade-decor pattern is draft;
OBJ03 was unsuccessful and remains EXPERIMENTAL, not resumed here. K02 awaits the user's
source/etalon files; B03 awaits an etalon. Engine profiles `npm_min` / `mid` are not delivery
certificates and do not prove the VPM full-detail route.

This is an index, not replacement rule text. Sources `reg p.N` refer to one-based physical
pages of [the supplied regulation](../../../standards/source/Rasporyajenies19012026trebovaniya(2).pdf).
Project decisions are in [the decision log](../../decisions.md). `L2 coverage` names implemented
checks only; `none` means the complete row is manual today. Partial scene checks require
exported-file readback and correct OKS classification; this task runs no DCC/model validation.

| Requirement | reg page | NPM | VPM | How it is checked | L2 coverage | Detail in |
|---|---|---|---|---|---|---|
| DEC-01 — Profile representation | [D051]; [D010]; reg p.7 §3.1; reg p.28 §3.3 | Mid-poly simple solids, one per geometric decor element; project route does not require baking; texture-classified relief follows the linked pattern | Full detail of source-defined decor, subject to silhouette economy, DEC-06 and the whole-OKS budget; not unlimited source-mesh copying | Compare source sections and repeated runs with exported geometry; existing NPM spec checker does not certify full-detail VPM | none | [Facade decor and profile limits](../patterns/facade-decor-inset.md), [profile baseline](../npm-vpm.md), [project target / C1](../conflicts.md#a-inside-the-regulation) |
| DEC-02 — Silhouette economy | reg p.7 §3.1; reg p.28 §3.3 | Minimum triangles for the silhouette; minor non-shape-forming detail represented in texture | Minimum triangles for the silhouette; extra splits allowed for UV optimization | Manual source silhouette/section comparison; full detail does not waive simplification | none | [Geometry rules](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted) |
| DEC-03 — NPM shared hard budget | reg p.7 §3.6 | <= 150 000 triangles per OKS FBX including usable roof and decor, not per element | Separate VPM hard limit in DEC-04 | Sum exported triangles of the complete OKS FBX, including decor; no independent decor allowance | V003 — `scene_findings`, whole-OKS triangle count only | [NPM budget](../npm-vpm.md#npm-appendix-1), [implementation](../../../src/twinqa/scene.py) |
| DEC-04 — VPM shared hard budget | reg p.28 §3.9; [D010] | NPM limit in DEC-03 | <= 1 000 000 triangles per OKS FBX including usable roof and decor, excluding UCX | Count complete non-UCX exported OKS geometry; table/figure discrepancy is C1, not decided by this sheet | V003 — `scene_findings`, whole-OKS triangle count only | [VPM budget](../npm-vpm.md#vpm-appendix-2), [C1, user-decided](../conflicts.md#a-inside-the-regulation), [implementation](../../../src/twinqa/scene.py) |
| DEC-05 — Shared master project target | [D010] | One mid-poly master per OKS FBX: <= 150 000 triangles for the whole object, decor included | Same <= 150 000 project target; above target but within DEC-04 is review, not hard-limit failure | Readback whole-OKS sum; use the linked user-decided fallback rather than inventing a decor sub-budget | V003 — `scene_findings`, project target / hard-limit distinction | [Project target](../npm-vpm.md#vpm-appendix-2), [C1 / D010](../conflicts.md#a-inside-the-regulation), [implementation](../../../src/twinqa/scene.py) |
| DEC-06 — VPM small-detail baking interface | reg p.32 §7; [D051] | NPM project simple-solid / texture classification follows DEC-01 and the linked pattern; do not transfer the VPM threshold | Decorative/minor details recessed into or protruding from main building geometry up to 5 cm baked into texture; curb projections excepted | Manual source-depth classification and geometry/texture comparison; this is the qualification to full detail, not a new NPM baking mandate | none | [Baking applicability](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted), [NPM project pattern](../patterns/facade-decor-inset.md) |
| DEC-07 — Export triangulation | reg p.8 §3.11; reg p.29 §3.17 | Triangulated geometry in derived FBX | Same exported-geometry requirement | Read back face degrees from the export, not the editable master | V003 — `scene_findings`, triangulation only | [Export geometry](../geometry.md#regulation-geometry-rules-both-profiles-unless-noted), [implementation](../../../src/twinqa/scene.py) |

## Source-image evidence

**7 requirement rows.** PyMuPDF 1.28.2 renders of physical pages **7, 8, 28, 29, 32**
were visually inspected, including each quantity in the table: the NPM and VPM OKS triangle
ceilings and the VPM small-detail depth. The shared-master target is attributed to [D010],
not presented as another regulatory limit. The OKS limit is on p.28 §3.9; p.29 continues
§3.10's Ground table, not the OKS allowance.

Reproduce with `uv run --extra pdf-review python` (the repository declares `pdf-review`
as an optional extra, not a dependency group):

```python
from pathlib import Path
import pymupdf

out = Path('tmp/l1-evidence/decor')
out.mkdir(parents=True, exist_ok=True)
doc = pymupdf.open('standards/source/Rasporyajenies19012026trebovaniya(2).pdf')
for number in (7, 8, 28, 29, 32):
    doc[number - 1].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False).save(
        str(out / f'p{number:02}.png'))
```

The task requests local evidence under `C:/x/l1-evidence/decor/`; this run's harness forbids
writing outside the worktree. Renders were therefore reviewed in ignored
`tmp/l1-evidence/decor/` and removed after inspection, not committed. Reproduction does not
require stored images or Git LFS. Five short verbatim quotes transcribed from the images
(the source quotations below intentionally retain Russian):

- **DEC-02, reg p.7 §3.1:** «минимально необходимое количество треугольных полигонов».
- **DEC-03, reg p.7 §3.6:** «модели ОКС и его эксплуатируемой кровли в рамках одного файла формата FBX – 150 000».
- **DEC-04, reg p.28 §3.9:** «не включая объекты геометрии коллизии»; «1 000 000 треугольных полигонов».
- **DEC-06, reg p.32 §7:** «выступающие за основную геометрию здания до 5 см, запекаются в текстурную карту»; «Исключение: бордюрные выступы».
- **DEC-07, reg p.29 §3.17:** «Объекты геометрии должны быть триангулированы перед экспортом в файл формата FBX» (also checked on p.8 §3.11).

Conflicts are referenced only through [the conflict register](../conflicts.md), particularly
C1/[D010]. No conflict is decided or rule file changed here.

## L2 gaps

Rows with `none` (**3**); these are follow-up candidates, not filed tickets:

- **DEC-01:** profile-aware source-to-model decor inventory and full-detail VPM verification.
- **DEC-02:** source-derived silhouette economy and minor-detail classification.
- **DEC-06:** source-depth/baking applicability and end-to-end geometry/texture verification.

Partial coverage in DEC-03/04/05/07 checks sums and polygon degrees, not architectural
accuracy, semantic completeness or per-element suitability. The existing
[`check_decor`](../../../src/twinqa/geometry/checks.py) and
[spec-decor tests](../../../tests/qa/test_from_spec_decor.py) exercise bounded NPM construction
and readback rules, not an accepted Decor benchmark or full-detail VPM.
[T-DEC-2/3](../../research/capability-roadmap.md#73-decor--l1-partial) still require the user's
K02 source/etalon and B03 etalon. No complete L2 or L3 readiness is claimed.

## Documentation regression

`tests/test_area_requirement_sheet.py` discovers this sheet automatically.
`tests/test_decor_requirement_sheet.py` pins the requested profile distinction and budget
scope, five image-quote anchors, valid detail links and absence of PNG evidence links.
Generated negative probes remove every required scope/source clause, mutate inclusive
budget bounds independently in each profile cell, omit each uncovered-row gap and inject
all eight case variants of PNG links and artifact names. These are **documentation** checks,
not generated-model compliance or new production validators.

The supplied partial worktree passed **55 tests** unchanged (area contract plus Decor
regression). A missing-sheet replay temporarily moved only this new sheet to an ignored
worktree path, preserving its contents: **3 failed, 48 passed**, all three failures being
explicit missing-deliverable assertions. Restoring the sheet is the fix for that replay;
this is not a historical RED claim about the already-present partial sheet. Tests run with
`env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/pi-t_40ace6b2 tests/test_area_requirement_sheet.py tests/test_decor_requirement_sheet.py`.
GREEN after restoration: **55 passed**. Decor probes rejected **64/64** column mutations,
**14/14** source mutations, **11/11** gap-inventory mutations, **34/34** scope/limit mutations,
**3/3** gap omissions and **8/8** each PNG-link/artifact-name case variants.

The full suite was run once with the same command, omitting the two test paths, and a
400-second runner timeout. Progress last reached **74%**; no final pytest counts were
produced. Final runner line: `Command timed out after 400 seconds`. The full suite is
incomplete, not GREEN. Independent docs review of five rendered row anchors and user
acceptance remain pending.
