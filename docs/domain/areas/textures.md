# Textures — L1 requirement sheet

**Area and profiles:** texture maps for NPM / VPM, including Ground relief, GroundEl and Flora
texture interfaces. Out: UV construction, Ground geometry, material production and packaging as
separate areas. Naming, UV density and embedding appear only as texture-delivery constraints.

**Readiness:** [roadmap §7.5 and §7.10](../../research/capability-roadmap.md#75-textures--l2-partial)
records Textures L2-partial and Ground textures L1-partial. This sheet supplies the T-TEX-1 /
T-GTX-1 texture index; it does not supply a skill, benchmark, complete L2 or user acceptance.
T-TEX-2 atlas reproduction and T-TEX-3 real-object VPM maps remain open.

**Reading:** one-based physical pages of the
[regulation](../../../standards/source/Rasporyajenies19012026trebovaniya(2).pdf); section labels
follow its tables (figures are explicitly identified). This is an index, not replacement rule text.
`none` means no implemented automatic check for the complete row; manual gates do not count as L2.
Partial checks name their scope, not an area pass. Inventory: [validation](../validation.md#implementation-status-inventory-static-audit),
[PNG helpers](../../../src/twinqa/png.py), [scene checks](../../../src/twinqa/scene.py).
V006 pixel checks require separately supplied PNG bytes: embedded-image extraction is missing.
Q7's rules are the existing user decisions [D013], [D014], [D020], not new regulation amendments.

| Requirement | reg page | NPM | VPM | How it is checked | L2 coverage | Detail in |
|---|---|---|---|---|---|---|
| TEX-01 — Map suffix vocabulary | reg p.10–11 §9; [D014] | `_d` Diffuse, `_n` Normal, `_o` opacity, `_m` metallic, `_r` roughness; `_n` is vocabulary, not permission to deliver normals under [D014] | Use TEX-03, not NPM letter suffixes | Compare exported map roles with names, then apply profile policy | none | [NPM naming](../geometry.md#naming---npm-reg-p10-13), [C6](../conflicts.md#a-inside-the-regulation) |
| TEX-02 — NPM names and editor/file equality | reg p.11 §10.1–10.2; reg p.12–13 §3.4 | `T_{Address}_{Number}_{GeometrySuffix}_{MapSuffix}_{SlotNumber}` for OKS; omit Number for Ground/GroundEl/Flora; editor texture name matches PNG filename; Latin/digits/underscore, ≤ 254 characters | Separate filename contract in TEX-03 | Compare editor image inventory to PNG filenames and semantic suffixes; sequential SlotNumber starts at 1 | none | [NPM names](../geometry.md#naming---npm-reg-p10-13) |
| TEX-03 — VPM map filenames | reg p.34 §4.3; reg p.30 §5.1.4 | See TEX-02 | `T_{Address}_{TypeTexture}_{SlotNumber}.{UDIM}.png`; Ground: `T_{Address}_Ground_{TypeTexture}_{SlotNumber}.{UDIM}.png`; TypeTexture = Diffuse / ERM / Normal | ZIP-root PNG name, address and per-slot/tile triplet checks; editor-name correspondence still manual | V007 — `vpm_texture_findings`, external filenames/triplets only | [VPM names](../geometry.md#naming---vpm-reg-p33-36), [PNG implementation](../../../src/twinqa/png.py) |
| TEX-04 — PNG count per VPM archive | reg p.26 §1.2 | Embedded-atlas contract, not this external-file range | 3-2100 PNG files per model ZIP, not per project and not a count of texture sets | Count PNG entries in each delivery ZIP; triplet validation alone does not enforce this ceiling | none | [VPM package](../npm-vpm.md#vpm-appendix-2), [validation limits](../validation.md#implementation-status-inventory-static-audit) |
| TEX-05 — Image storage and FBX paths | reg p.9 §5.1; reg p.30 §4.2, §5.1.1 | PNG atlases embedded in FBX | Separate PNGs, not embedded; all texture paths removed from FBX materials | Exported scene image flags and manual material-path readback; archive PNG validation is not proof of cleared paths | V006 — `scene_findings`, NPM embedding flags only | [Texture storage](../uv-textures.md), [materials](../materials.md#vpm) |
| TEX-06 — NPM image dimensions and bytes | reg p.9 §5.2–5.3; [D015] | Square 256, 512, 1024 or 2048 px; ≤ 3 MiB per map [D015]; placeholder exception TEX-09, target caps TEX-16 | See TEX-10 | Inspect supplied PNG headers/byte sizes; embedded pixels are not extracted | V006 — standalone `npm_texture_findings`, generic size/bytes only | [NPM textures](../uv-textures.md#npm-textures-app1), [C12](../conflicts.md#a-inside-the-regulation) |
| TEX-07 — Alpha and opacity / Q7 | reg p.9 §5.5, §5.8; reg p.30 §5.1.4, §5.1.6; [D020] | no alpha in any image; convert RGBA diffuse to RGB plus separate `_o_` opacity when transparent elements exist | Opacity may be in Diffuse alpha; ERM/Normal have no alpha | PNG channel inspection; manual diffuse/mask pixel correspondence and transparency applicability after conversion | V006/V007 — PNG alpha checks only; no end-to-end conversion proof | [Alpha rules](../uv-textures.md), [C8/C21](../conflicts.md) |
| TEX-08 — NPM map composition | reg p.9 §5.6–5.9; [D014] | Diffuse mandatory; roughness and metallic only as a pair; no normal delivery map [D014]; all set maps same size except placeholders | Mandatory triplet in TEX-10 | Audit map-role inventory, paired maps and dimensions across the set; generic PNG size checks alone are insufficient | none | [NPM maps](../uv-textures.md#npm-textures-app1), [C6](../conflicts.md#a-inside-the-regulation) |
| TEX-09 — NPM placeholders / Q7 | reg p.3–4 §2; reg p.9 §5.7; [D013] | PNG 128×128, 8 bit/channel, one averaged colour; Metallic/Roughness only, when those properties have no variation; exempt from density | See TEX-12; do not transfer NPM size | Header and constant-pixel check on supplied PNG; permitted map roles and source-average truth remain manual | V006 — `npm_texture_findings`, size/bit depth/constant colour only | [Placeholder rule](../uv-textures.md#npm-textures-app1), [C5](../conflicts.md#a-inside-the-regulation) |
| TEX-10 — VPM triplet, dimensions and bit depth | reg p.30 §5.1.2–5.1.4, §5.1.9 | See TEX-06/08 | Diffuse + ERM + Normal; square 2048×2048 or 4096×4096 except placeholders; Diffuse resolution ≥ ERM/Normal; 8 bit/channel (RGB 24, RGBA 32 bit) | Read PNG headers, group by slot/UDIM, compare resolutions; placeholder Diffuse exception is reported as review by current helper | V007 — `vpm_texture_findings`, headers/triplets/resolution | [VPM textures](../uv-textures.md#vpm-textures-app2), [implementation](../../../src/twinqa/png.py) |
| TEX-11 — VPM map semantics | reg p.23 §2; reg p.30 §5.1.7 | No normal delivery map [D014] | ERM RGB = Emissive / Roughness / Metallic, not ORM; DirectX Normal | Compare source maps and shader interpretation; ERM red-channel and normal curl heuristics cannot prove semantics | V007 — ERM/Normal heuristics only, undecidable results require review | [VPM maps](../uv-textures.md#vpm-textures-app2), [C6](../conflicts.md#a-inside-the-regulation) |
| TEX-12 — VPM placeholders | reg p.31 §3.1–3.5; [D013] | See TEX-09 | PNG 256×256, no alpha, one averaged colour; may mix with full maps in a set; only untextured or geometry-modelled finishes, not marble/brick/tile | Constant pixels and size automatically; source average and surface eligibility manually | V007 — placeholder pixel/alpha/size subset only | [VPM placeholders](../uv-textures.md#vpm-textures-app2), [C5](../conflicts.md#a-inside-the-regulation) |
| TEX-13 — Padding between unique images | reg p.9 §5.4; reg p.30 §5.1.5 | ≥ 8 px between neighbouring unique-image UV islands | ≥ 16 px at 2048; ≥ 32 px at 4096 | Inspect exported UV/image island edges; distinguish inter-island padding from tile-border margin | none | [Padding](../uv-textures.md), [V006/V007 limits](../validation.md#implementation-status-inventory-static-audit) |
| TEX-14 — No unused VPM maps | reg p.30 §5.1.8 | Review atlas use; no transferred VPM archive mandate | Each archive map projects onto ≥ 1 polygon; no unused maps | Trace material/slot/tile assignments to exported polygon UVs; PNG triplets do not establish usage | none | [Map usage](../uv-textures.md#vpm-textures-app2), [QA](../validation.md) |
| TEX-15 — Ground relief set ceiling | reg p.6–7 §1.5 | Ground relief ≤ 20 sets; whole Ground FBX ≤ 22 including GroundEl and Flora; glass parts have no sets; usable roof excluded | VPM Ground UDIM/map contract, not an inherited NPM set ceiling | Count semantic sets across complete Ground FBX; distinguish maps, sets and glass materials | none | [Ground structure](../npm-vpm.md#npm-appendix-1) |
| TEX-16 — GroundEl and Flora sets | reg p.10 §5.12–5.13 | GroundEl: one shared set ≤ 512×512 px; Flora: one shared set ≤ 2048×2048 px, Diffuse and opacity only if needed | VPM Ground contract, not these NPM caps | Inventory all elements and vegetation, count shared sets, inspect target-specific dimensions/map roles | none | [NPM target caps](../uv-textures.md#npm-textures-app1), [MAF interface](groundel-maf.md) |
| TEX-17 — Ground relief density and exclusions | reg p.10 §6.1–6.2; [D097] | 10-40 px/m with 2K textures by [D097]; relief surface inside site only; excludes perimeter extrusion, OKS, GroundEl and Flora | See TEX-18 | Metric surface/UV comparison with target classification; no general V009 delivery check | none | [Density applicability](../uv-textures.md#npm-textures-app1), [C4 / D097](../conflicts.md#a-inside-the-regulation) |
| TEX-18 — VPM Ground density interface | reg p.31–32 §6.1–6.2; [D097] | See TEX-17; no VPM density transplanted to NPM | Diffuse only; regulation 512-1706 px/m, project 520-1706 px/m at 4K [D097]; ERM/Normal/placeholders exempt; formula texture-side pixels / polygon length in metres | Measure exported metric UVs; distinguish page wording from project decision; V009 remains unimplemented | none | [Density](../uv-textures.md#vpm-uv--udim), [C4/C10](../conflicts.md#a-inside-the-regulation) |
| TEX-19 — Ground baking versus slicing | reg p.18 §fig.7–8; reg p.10 §6.1 | Figures show baking versus slicing for Ground geometry/atlas; examples, not a command to select one route | Do not treat NPM example figures as a VPM atlas exemption | Review Ground surface, atlas layout and density together against the two illustrated approaches | none | [Ground examples](../uv-textures.md#npm-textures-app1) |
| TEX-20 — Glass texture interface | reg p.9 §5.10; reg p.10 §7; reg p.32 §8.1 | Opaque atlas glass: Diffuse/Metallic white, Roughness black; opacity absent or glass region white; translucent separate glass has no texture maps | Translucent glass materials have no maps | Manual glass classification and region/channel inspection; PNG headers cannot certify material appearance | none | [Glass maps](../uv-textures.md#npm-textures-app1), [glass materials](../materials.md) |

## Source-image evidence

**20 requirement rows**, including Ground-specific TEX-15–19. Every printed numeric quantity
in the table was checked on rendered page images; project interpretations are attributed to
existing decisions, not presented as PDF quotations. Visually inspected physical pages:
3, 4, 6, 7, 9, 10, 11, 12, 13, 18, 23, 26, 30, 31, 32, 34.

PyMuPDF 1.28.2, matrix `(1.4, 1.4)`, `alpha=False`. The repository declares `pdf-review` as an
optional extra, not a dependency group: use `uv run --extra pdf-review python` with
`pymupdf.open(...)` and `page.get_pixmap(...)`. For example, from the worktree root:

```bash
uv run --extra pdf-review python -c "from pathlib import Path; import pymupdf; out=Path('tmp/l1-evidence/textures'); out.mkdir(parents=True,exist_ok=True); d=pymupdf.open('standards/source/Rasporyajenies19012026trebovaniya(2).pdf'); d[25].get_pixmap(matrix=pymupdf.Matrix(1.4,1.4),alpha=False).save(str(out/'p26.png'))"
```

Renders are local-only in ignored `tmp/l1-evidence/textures/pNN.png`, with no PNG links or
committed binaries. Fresh PyMuPDF renders matched all 16 inspected PNGs byte-for-byte (16/16).
The driver has copied the evidence from `tmp/l1-evidence/textures/` to the requested external
`C:/x/l1-evidence/textures/` location: 18 files total, including the 16 inspected page renders.
Five short verbatim anchors transcribed from the images:

- **TEX-01, reg p.11 §9:** “_d — диффузного цвета”; “_n — нормалей”; “_o — прозрачности”; “_m — металличности”; “_r — шероховатости” (table cells; dashes separate columns).
- **TEX-02, reg p.12 §3.4:** “Название текстурных карт внутри редактора должно быть идентичным соответствующим файлам формата PNG.”
- **TEX-04, reg p.26 §1.2:** “3-2100 файлов формата PNG.”
- **TEX-09, reg p.3 §2:** “Растровое изображение формата PNG с разрешением 128×128 пикселей”; continuation p.4: “глубиной цвета 8 бит на канал”.
- **TEX-19, reg p.18 fig.7–8:** “Пример двух подходов к созданию текстурного атласа модели благоустройства: а. «Запекание» б. «Нарезка»”.

Conflict status is maintained only in [conflicts.md](../conflicts.md): C4/[D097], C5/[D013],
C6/[D014], C8/C21/[D020], C10 and C12/[D015]. The roadmap's older open-density wording is not
a new decision; [D097] already records the user's interpretation. No new conflict or choice
is introduced here, and no rule file or machine-readable profile is changed.

## L2 gaps

**12** rows have `none`; these are follow-up inputs, not filed tickets:

- **TEX-01:** profile-aware suffix-to-map-role audit, including the NPM normal exclusion.
- **TEX-02:** internal image/filename equality and complete NPM semantic naming.
- **TEX-04:** per-archive PNG count range.
- **TEX-08:** NPM role inventory, Metallic/Roughness pairing and same-size set checks.
- **TEX-13:** image-aware inter-island padding measurement.
- **TEX-14:** exported polygon-to-map usage audit.
- **TEX-15:** complete Ground relief/FBX set count and glass/roof classification.
- **TEX-16:** shared GroundEl/Flora set count, special caps and allowed map roles.
- **TEX-17:** NPM Ground density and applicability, following [D097].
- **TEX-18:** VPM Ground metric density and exemptions, following [D097].
- **TEX-19:** Ground atlas/surface route review against the illustrated examples.
- **TEX-20:** glass classification and channel/region appearance audit.

Partial rows still need internal/editor correspondence (TEX-03), external paths/no-embedding
readback (TEX-05), embedded PNG extraction (TEX-06/07/09), lossless Q7 diffuse/mask conversion
verification (TEX-07), source-true placeholder roles/averages and surface eligibility
(TEX-09/12), and proven ERM/Normal semantics rather than heuristics (TEX-11).
These are not closed by the document contract tests. General Ground L2 remains incomplete;
this work ran no DCC, benchmark or real-object texture validation.

## Documentation regression

The supplied partial work (sheet plus regression) passed **77 tests** before any edits.
There was no observed RED on that supplied state. A reconstructed pre-sheet negative control
temporarily moved only this sheet to an ignored worktree-local backup and restored it on exit:
**25 failed, 48 passed**, all failures asserting the missing sheet. This is not a historical
pre-fix revision run. The regression validates the document seam, not production compliance.
The generic contract discovers the new sheet and exhaustively mutates its columns, sources,
coverage and gap entries. Issue-specific probes reject missing sources (20/20), missing
`none` gaps (12/12) and omitted scope/limit anchors (23/23). These test documentation only;
production texture limits remain subject to the L2 gaps above. Image review is manual evidence,
not automated by pytest. Copying evidence to the requested external location is complete.
Independent docs review (five rendered-page spot checks) and user acceptance remain pending.
