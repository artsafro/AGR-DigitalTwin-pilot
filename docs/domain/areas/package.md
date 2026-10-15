# Package — export, package and validation L1 requirement sheet

Area: delivery archives (ZIP), FBX format and content, VPM lighting FBX, VPM GeoJSON, and the
map of delivery validator stages V001-V017 onto requirement rows, NPM / VPM.
Out of scope: geometry construction and triangle budgets (BODY/Decor/Ground sheets), UCX
construction ([UCX sheet](ucx.md)), texture/UV/material content, user acceptance and publication.

Readiness: [roadmap §7.8](../../research/capability-roadmap.md#78-export--package--validation--l2-partial)
records **L2-partial**. This sheet supplies T-PKG-1's rule index, not T-PKG-2 (GeoJSON and lights
produced for a real object), T-PKG-3 (SINTEZ/AGR checker gate), a benchmark or user acceptance.
No delivery package has ever been passed (`passed=false` everywhere).

This is an index, not replacement rule text. Sources `reg p.N` refer to one-based physical
pages of [the supplied regulation](../../../standards/source/Rasporyajenies19012026trebovaniya(2).pdf);
`§a.b` is table row `a`, item `b` on that page (`§10.4.5` = row 10, item 4.5). Project decisions are in
[the decision log](../../decisions.md). `L2 coverage` names implemented checks of
[`tools/qa/validate_package.py`](../../../tools/qa/validate_package.py) and
[`src/twinqa/`](../../../src/twinqa/scene.py); `none` means the complete row is manual today.
Scene checks run only with `--scene` (Blender FBX readback); no DCC or package validation was run here.

| Requirement | reg page | NPM | VPM | How it is checked | L2 coverage | Detail in |
|---|---|---|---|---|---|---|
| PKG-01 — NPM archive size and integrity | reg p.6 §1.1; [D015] | One ZIP <= 1 GB (1024 MiB, binary), no broken or unreadable files | VPM limits in PKG-02 | Read the ZIP without extraction (CRC, safe paths, duplicates) and compare its byte size with the binary limit | V001 — `read_bundle`, `size_status` | [NPM package](../npm-vpm.md#npm-appendix-1), [C12 / D015](../conflicts.md#a-inside-the-regulation), [V001](../validation.md#implementation-status-inventory-static-audit) |
| PKG-02 — VPM archive size and integrity | reg p.26 §1.1; [D015] | NPM limit in PKG-01 | OKS ZIP <= 500 MB (500 MiB); Ground ZIP <= 1 GB (1024 MiB); no broken or unreadable files | Same reader; limit chosen by the `_Ground` archive stem | V001 — `read_bundle`, `size_status` | [VPM package](../npm-vpm.md#vpm-appendix-2), [C12 / D015](../conflicts.md#a-inside-the-regulation) |
| PKG-03 — NPM archive composition | reg p.6 §1.2; reg p.7 §1.6 | 2-21 FBX: one Ground FBX (mandatory) + up to 20 OKS FBX; textures embedded, no other files | n/a (VPM in PKG-04) | Count FBX members, require `{prefix}_{Address}_Ground.fbx`, reject foreign files | V001 — `validate_npm_zip` FBX count, Ground FBX, foreign files | [NPM package](../npm-vpm.md#npm-appendix-1), [validator](../../../tools/qa/validate_package.py) |
| PKG-04 — VPM archive composition | reg p.26 §1.2 | n/a (NPM in PKG-03) | Flat ZIP: one FBX, optional lighting FBX, one GeoJSON, 3-2100 PNG; textures external | Check main FBX, optional `_Light.fbx`, exactly one `{stem}.geojson`, PNG count, no folders or foreign files | V001 — `validate_vpm_zip` | [VPM package](../npm-vpm.md#vpm-appendix-2), [validator](../../../tools/qa/validate_package.py) |
| PKG-05 — VPM archive per object | reg p.26 §1.3-1.4 | n/a (one NPM archive) | Separate model per free-standing OKS, including its stylobate, korpus and usable roof; Ground with all elements and vegetation is a separate mandatory model; existing non-reconstructed buildings not modelled | Compare the archive set with the OKS list of the approved project; one archive is validated at a time today | none | [VPM package](../npm-vpm.md#vpm-appendix-2), [V001 limits](../validation.md#implementation-status-inventory-static-audit) |
| PKG-06 — NPM OKS FBX object count | reg p.6 §1.4 | <= 40 geometry objects per OKS FBX total: OKS incl. usable roof <= 20 objects (max 40 texture sets) + translucent parts <= 20 objects (no texture sets) | n/a | Count objects and texture sets per OKS FBX on readback | none | [NPM package](../npm-vpm.md#npm-appendix-1) |
| PKG-07 — NPM Ground FBX composition | reg p.6-7 §1.5 | <= 22 texture sets: Ground (<= 20 sets, also limited by density), Ground translucent (none), GroundEl (1 set), GroundEl translucent (none), Flora (1 set); usable-roof objects excluded | n/a | Classify Ground FBX objects and count their texture sets on readback | none | [NPM package](../npm-vpm.md#npm-appendix-1) |
| PKG-08 — NPM split into several OKS FBX | reg p.7 §2.1-2.4; reg p.11 §10.3.2 | Split into <= 20 FBX only when one FBX exceeds the triangle limit; only by indivisible units; translucent parts split accordingly; FBX numbered `_01`..`_20` without gaps; object numbering continuous across the AGR | n/a | Name pattern from the archive; the reason for and the units of the split are reviewed manually | V012 — `validate_npm_zip` FBX name pattern only | [NPM split](../npm-vpm.md#npm-appendix-1), [V012 limits](../validation.md#implementation-status-inventory-static-audit) |
| PKG-09 — FBX format | reg p.4 §1.1; reg p.24 §1.1 | FBX 7.4 (FBX 2014), binary | Same | Read the FBX header magic and version | V002 — `check_fbx_header`; tests/qa/test_validator.py::test_fbx_7500_fails | [Delivery FBX](../export-import.md#regulation-delivery-fbx), [implementation](../../../src/twinqa/fbx_header.py) |
| PKG-10 — Units and scale | reg p.4 §2.1; reg p.24 §2.1 | Metric; 1 unit = 1 m; scale 1:1 | Same | Read the FBX unit settings and compare known source dimensions; the validator records units as `not_run` | none | [Delivery FBX](../export-import.md#regulation-delivery-fbx), [V002 limits](../validation.md#implementation-status-inventory-static-audit) |
| PKG-11 — FBX scene content | reg p.4 §4; reg p.6 §1.3; reg p.28 §3.1-3.2 | No empty objects, animation, deformations, cameras, sounds, bones, extra layers, animation keys, helpers, interiors, underground utilities, people or vehicles; lights removed | No extra objects (cameras, empty objects, empty geometry, utilities, characters, cars); all objects in the single default layer | Readback rejects non-mesh objects and zero-polygon meshes; layers, animation and modifier history are not inspected | V003 — `scene_findings` object types (with `--scene`) | [Delivery FBX](../export-import.md#regulation-delivery-fbx), [V003 limits](../validation.md#implementation-status-inventory-static-audit) |
| PKG-12 — Lights only in the lighting FBX | reg p.4 §4; reg p.33 §10.4.1; [D017] | No lights in any NPM FBX | Lights only in `SM_<Address>_Light.fbx`; any non-mesh object in the main FBX fails | Readback of each FBX by role; lights and empties are allowed only in the `_Light` role | V003 — `scene_findings`; tests/qa/test_scene.py::test_light_in_main_fbx_fails_conflict_14 | [C14 / D017](../conflicts.md#a-inside-the-regulation), [VPM lighting](../npm-vpm.md#vpm-lighting-fbx-architectural-light-design) |
| PKG-13 — Package file names | reg p.11 §10.1-10.3.2; reg p.33 §10.1-10.4.1; reg p.26 §3.7; [D019] | ZIP `{prefix}_{Address}` with a four-digit territorial code; FBX `{prefix}_{Address}_01..20` and `{prefix}_{Address}_Ground`; <= 254 characters; Latin, digits, `_` | ZIP, FBX and GeoJSON stems `SM_Address` / `SM_Address_Ground`; lighting `SM_Address_Light` / `SM_Address_Ground_Light`; <= 254 characters; `_001` index for free-standing buildings only with more than one OKS | Archive stem regex and member names; the `_001` index stays `review` | V012 — `validate_vpm_zip`, `validate_npm_zip` archive and FBX names | [Names](../npm-vpm.md#common-to-both), [C20 / D019](../conflicts.md#b-regulation-vs-local-yaml--docs), [V012 limits](../validation.md#implementation-status-inventory-static-audit) |
| PKG-14 — Light object names | reg p.4 §4; reg p.34-35 §10.4.5-10.4.6; reg p.35 §11; [D019] | n/a (no lights) | OKS: `Address_Root`, `Address_Spot_001..250`, `Address_Omni_001..250`; Ground: `Address_Ground_Root`, `Address_Ground_Spot_NNN`, `Address_Ground_Omni_NNN`; numbering per type from 001 | Read back light and root object names from the lighting FBX | none | [VPM lighting](../npm-vpm.md#vpm-lighting-fbx-architectural-light-design), [C20 / D019](../conflicts.md#b-regulation-vs-local-yaml--docs) |
| PKG-15 — Light count | reg p.4 §4; reg p.37 §15.2 | n/a (no lights) | <= 250 lights per lighting FBX; above that, only the most visible areas are lit | Count lights in the lighting FBX readback | none | [VPM lighting](../npm-vpm.md#vpm-lighting-fbx-architectural-light-design) |
| PKG-16 — Light types and settings | reg p.4 §4; reg p.37 §15.3-15.4; reg p.38 §15.6-15.7; [D019] | n/a (no lights) | Only omni point lights and conical spot lights; no renderer-specific lights (VRay, Octane, Corona, Arnold); only colour and intensity configured; light flux on surroundings by separate lights, not model geometry | Read back light types and changed properties | none | [VPM lighting](../npm-vpm.md#vpm-lighting-fbx-architectural-light-design) |
| PKG-17 — Light spacing | reg p.4 §4; reg p.38 §15.5 | n/a (no lights) | Minimum distance between nearest neighbour lights: omni 5 m, spot 1.5 m | Measure nearest-neighbour distances per light type | none | [VPM lighting](../npm-vpm.md#vpm-lighting-fbx-architectural-light-design) |
| PKG-18 — Light hierarchy and pivot | reg p.4 §4; reg p.38 §15.8-15.9 | n/a (no lights) | All lights parented to one root helper empty; root pivot coincides with the lit object's pivot | Read back hierarchy and compare root and model origins | none | [VPM lighting](../npm-vpm.md#vpm-lighting-fbx-architectural-light-design) |
| PKG-19 — GeoJSON encoding and syntax | reg p.26 §2.1; reg p.27 §2.5; reg p.28 §2.7 | n/a — not in the App.1 package; only with a separate customer specification | UTF-8; structure, syntax, names and values exactly as App.3; only values may change; no renamed, duplicated or miswritten keys | Decode UTF-8, parse JSON rejecting duplicate keys, compare the exact property key set | V011 — `geojson_findings`; tests/qa/test_validator.py::test_geojson_type_errors_fail | [GeoJSON](../npm-vpm.md#geojson-vpm-only-app3), [implementation](../../../src/twinqa/geojson.py) |
| PKG-20 — GeoJSON schema | reg p.51-53 | n/a — not in the App.1 package | `FeatureCollection` with one feature of literal type `ObjectFeature`, `properties`, `Point` geometry and `Glasses` | Schema check of top level, feature type, geometry type | V011 — `geojson_findings` | [GeoJSON](../npm-vpm.md#geojson-vpm-only-app3), [implementation](../../../src/twinqa/geojson.py) |
| PKG-21 — GeoJSON mandatory values | reg p.27 §2.6; reg p.53-54 table 1 rows 8, 18; [D011] | n/a — not in the App.1 package | OKS: every value except `other` mandatory and truthful; `FNO_code` mandatory (3, 6 or 9 digits), `act_AGR` may be empty; never invent; Ground may leave `FNO_name`, `FNO_code`, `h_otn`, `h_abs`, `s_obsh`, `s_naz`, `s_podz`, `spp_gns`, `other` empty | Empty-value check by profile and Ground role; FNO digit count | V011 — `geojson_findings`; tests/qa/test_validator.py::test_oks_empty_fields_follow_checker_conflict_2 | [C2 / D011](../conflicts.md#a-inside-the-regulation), [GeoJSON](../npm-vpm.md#geojson-vpm-only-app3) |
| PKG-22 — GeoJSON value formats | reg p.27 §2.2-2.4; reg p.53-54 table 1 rows 2-17; [D019] | n/a — not in the App.1 package | `okrug`, `rajon` <= 50 characters; `developer`, `designer`, `FNO_name` <= 255; `cadNum` and `FNO_code` masks; `ZU_area` <= 4 decimals; heights and areas <= 2 decimals; multiple values only in okrug, rajon, developer, designer, cadNum; organisation names with a typewriter apostrophe | Only the `FNO_code` digit count is checked; lengths, `cadNum` mask, decimals and multi-value rules are manual | V011 — `geojson_findings` FNO_code digits only | [GeoJSON](../npm-vpm.md#geojson-vpm-only-app3), [C20 / D019](../conflicts.md#b-regulation-vs-local-yaml--docs) |
| PKG-23 — GeoJSON image | reg p.54 table 1 row 19 | n/a — not in the App.1 package | `imageBase64`: a 256x256 JPG converted to base64 | Decode base64 and read JPEG size | V011 — `geojson_findings` (`_image`) | [GeoJSON](../npm-vpm.md#geojson-vpm-only-app3), [implementation](../../../src/twinqa/geojson.py) |
| PKG-24 — GeoJSON insertion point | reg p.55 table 1 row 21 | n/a — not in the App.1 package | `coordinates`: insertion point in MSK-77, 3 decimals, matches the plan position per SPOZU; maximum offset 50 cm | Precision from the file; position against survey DWG/SPOZU is V013 `not_run` plus V017 manual | V011 — `geojson_findings` 3-decimal precision only | [GeoJSON](../npm-vpm.md#geojson-vpm-only-app3), [V013 / V017](../validation.md#implementation-status-inventory-static-audit) |
| PKG-25 — GeoJSON Glasses | reg p.51-53; reg p.55 table 1 rows 22-22.5; reg p.56; [D016] | n/a — not in the App.1 package | `[]` without glass; else a list with one object keyed by glass material (`M_Address_MainGlass_1`..`_7`, `M_Address_GroundGlass_N`); `color_RGB` 0-255, `transparency` 0-1 (0 fully transparent), `refraction` 1-3, `roughness` 0-1, `metallicity` 0-1; names match the FBX glass materials | Structure and ranges from the file; the FBX glass-name cross-check is not wired (`glass_names=None`) | V011 — `geojson_findings` (`_glasses`); tests/qa/test_validator.py::test_glasses_follow_checker_conflict_13 | [C13 / D016](../conflicts.md#a-inside-the-regulation), [GeoJSON](../npm-vpm.md#geojson-vpm-only-app3) |

## Validator map V001-V017

The validator stages ([`standards/DELIVERY_VALIDATOR.yaml`](../../../standards/DELIVERY_VALIDATOR.yaml),
[implementation inventory](../validation.md#implementation-status-inventory-static-audit)) map onto rows
of this sheet and of the other area sheets. A stage that names a row here is not a complete stage:
partial rows above keep their unchecked part manual.

- **V001** (both, ZIP): PKG-01, PKG-02, PKG-03, PKG-04; PKG-05 not checked (one archive at a time).
- **V002** (both, FBX format and units): PKG-09; PKG-10 units `not_run`.
- **V003** (both, triangulation, budgets, object types): PKG-11, PKG-12; budgets in [BODY](body.md) and [Decor](decor.md).
- **V004** (both, topology and transforms): [UCX R16](ucx.md) and the geometry sheets; not a package row.
- **V005** (both, shaders and slots): materials area, no sheet yet; unimplemented.
- **V006** (NPM, embedded PNG): textures area, no sheet yet.
- **V007** (VPM, external PNG sets): textures area; the PNG count bound is PKG-04.
- **V008** (VPM, UV and UDIM): UV area, no sheet yet.
- **V009** (VPM, texel density): UV area; unimplemented.
- **V010** (VPM, UCX): [UCX sheet](ucx.md) R05-R15.
- **V011** (VPM, GeoJSON): PKG-19 to PKG-25.
- **V012** (both, names): PKG-08, PKG-13; light names PKG-14 not checked; mesh and material names in the geometry sheets.
- **V013** (VPM, pivot and MSK-77): PKG-24 position `not_run`; pivot in [UCX R17](ucx.md) and the geometry sheets; lighting root pivot PKG-18 not checked.
- **V014** (NPM, Moscow coordinates, reg p.10): placement area, no sheet yet; unimplemented.
- **V015** (both, manual): approved-project match; no package row.
- **V016** (VPM, manual): [UCX sheet](ucx.md) R01, R11-R13.
- **V017** (both, manual): PKG-24 plan position within 50 cm.
- **No stage**: lighting FBX content PKG-14 to PKG-18 has no validator stage; the lighting FBX is only
  admitted by name (V001) and header (V002) and allowed to hold lights and empties (V003).

## Source-image evidence

**25 requirement rows.** PyMuPDF 1.28.2 renders (matrix 2x) of physical pages **4, 6, 7, 11, 24,
26, 27, 28, 33, 34, 35, 36, 37, 38, 51, 52, 53, 54, 55, 56** were visually inspected, including every quantity
in the table: archive sizes and FBX counts, object and texture-set counts, the 254-character name
limit, light count, numbering range and spacing, GeoJSON lengths, decimals, image size, offset and
Glasses ranges. p.36 §13.3 (lighting FBX exempt from UCX) and the p.56 refraction table are context
for PKG-12 and PKG-25 and add no number to a row. Binary units are [D015], not regulation text.

Reproduce with `uv run --extra pdf-review python`:

```python
from pathlib import Path
import pymupdf

out = Path('C:/x/l1-evidence/package')
out.mkdir(parents=True, exist_ok=True)
doc = pymupdf.open('standards/source/Rasporyajenies19012026trebovaniya(2).pdf')
for number in (4, 6, 7, 11, 24, 26, 27, 28, 33, 34, 35, 36, 37, 38, 51, 52, 53, 54, 55, 56):
    doc[number - 1].get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).save(
        str(out / f'p{number:02}.png'))
```

Renders stay local under `C:/x/l1-evidence/package/`, never committed (PNG is Git LFS).
Short verbatim quotes transcribed from the images (the quotations intentionally retain Russian):

- **PKG-01, reg p.6 §1.1:** «в виде файла формата ZIP размером до 1 Гб».
- **PKG-02, reg p.26 §1.1:** «Модель ОКС должна передаваться в виде файлов формата ZIP размером до 500 мегабайт».
- **PKG-03, reg p.6 §1.2:** «входит от 2 до 21 файлов формата FBX».
- **PKG-04, reg p.26 §1.2:** «3-2100 файлов формата PNG».
- **PKG-14, reg p.34 §10.4.5:** «порядковый номер источника освещения данного типа, число от 001 до 250».
- **PKG-15, reg p.37 §15.2:** «может содержать не более 250 источников освещения».
- **PKG-17, reg p.38 §15.5:** «точечный всенаправленный источник — 5 метров»; «конический направленный прожектор — 1,5 метра».
- **PKG-24, reg p.55 table 1 row 21:** «Максимально допустимое смещение координат, относительно планового положения составляет 50 сантиметров».

Conflicts are referenced only through [the conflict register](../conflicts.md): C2/[D011], C12/[D015],
C13/[D016], C14/[D017], C20/[D019]. No conflict is decided, no new conflict was found, and no rule
file is changed here.

## L2 gaps

Rows with `none` (**9**); these are follow-up candidates (T-PKG-2/3), not filed tickets:

- **PKG-05:** multi-archive set check: one VPM ZIP per free-standing OKS plus the Ground ZIP against the project OKS list.
- **PKG-06:** NPM OKS FBX object and texture-set counts (<= 20 + <= 20 objects, <= 40 sets).
- **PKG-07:** NPM Ground FBX object classes and texture-set counts (<= 22 sets).
- **PKG-10:** FBX unit and scale readback in V002.
- **PKG-14:** lighting FBX root and light name masks, per-type numbering 001-250.
- **PKG-15:** light count <= 250 per lighting FBX.
- **PKG-16:** light type whitelist (omni point, conical spot) and renderer-specific light rejection.
- **PKG-17:** nearest-neighbour light spacing (omni 5 m, spot 1.5 m).
- **PKG-18:** single root helper hierarchy and root pivot equal to the lit object's pivot.

Partially covered rows are not gap entries, but their unchecked parts are follow-up inputs too:
PKG-08 split reason and units, PKG-11 layers, animation and modifiers, PKG-13 `_001` index,
PKG-22 lengths, masks and decimals, PKG-24 MSK-77 position against survey, PKG-25 FBX glass-name
cross-check. No row has L2 coverage of a real object: T-PKG-2 (GeoJSON and lights for PSU275) and
T-PKG-3 (AGR checker gate) remain open, and no complete L2 or L3 readiness is claimed.

## Documentation regression

`tests/test_area_requirement_sheet.py` discovers this sheet automatically.
`tests/test_package_requirement_sheet.py` pins the 25 row ids, the transcribed sources and numbers
of every row, the NPM `n/a` of lighting and GeoJSON rows, link targets and heading anchors, the eight
image-quote anchors, one map line per stage V001-V017, the gap inventory and the absence of PNG
evidence. Its generated probes remove every pinned token, bump every digit run by one, and drop each
map, quote and gap line. These are **documentation** checks, not package compliance or new validators.
